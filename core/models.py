import uuid
from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex, OpClass
from django.core.exceptions import ValidationError
from django.db import models

# from django.contrib.auth import get_user_model
from django.conf import settings

# Create your models here.


class ProductCategory(models.TextChoices):
    SKINCARE = "skincare", "Skincare"
    MAKEUP = "makeup", "Makeup"
    HAIRCARE = "haircare", "Haircare"
    FRAGRANCE = "fragrance", "Fragrance"
    BODY = "body", "Body & Bath"


class Product(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    name = models.CharField(max_length=255, unique=True)
    # null (not blank) so products without a code do not collide on the
    # unique index, which Postgres only treats as distinct for NULLs
    sku = models.CharField(max_length=32, unique=True, null=True, blank=True)
    category = models.CharField(
        max_length=20,
        choices=ProductCategory.choices,
        default=ProductCategory.SKINCARE,
    )
    # per-product restock point; the register warns at or below this count
    low_stock_threshold = models.PositiveSmallIntegerField(default=5)
    stock = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    profit_rate = models.DecimalField(max_digits=3, decimal_places=2)
    # optional shelf photo; blank so CSV imports and older rows stay image-free
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    # slugs are never queried, so skip the two indexes SlugField adds
    slug = models.SlugField(max_length=255, db_index=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        indexes = [
            # the product list is paginated by newest first
            models.Index(fields=["-created"], name="product_created_idx"),
            # makes name__icontains (ILIKE '%term%') index-backed
            GinIndex(
                OpClass("name", name="gin_trgm_ops"),
                name="product_name_trgm_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if not self._state.adding and (
            update_fields is None or "stock" in update_fields
        ):
            stored_stock = (
                type(self).objects.filter(pk=self.pk)
                .values_list("stock", flat=True)
                .first()
            )
            if stored_stock is not None and stored_stock != self.stock:
                raise ValidationError(
                    "Product stock must be changed through the inventory services."
                )
        return super().save(*args, **kwargs)

    @property
    def margin(self):
        """Gross margin on revenue: what share of the retail price is profit."""
        if self.price:
            return (self.price - self.cost) / self.price * 100
        return Decimal("0")


class StockReceiptSource(models.TextChoices):
    PURCHASE = "PURCHASE", "Purchase"
    OPENING = "OPENING", "Opening balance"
    IMPORT_OPENING = "IMPORT_OPENING", "Imported opening balance"
    ADJUSTMENT_OPENING = "ADJUSTMENT_OPENING", "Adjustment opening balance"


class StockReceipt(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    source = models.CharField(max_length=24, choices=StockReceiptSource.choices)
    purchased_on = models.DateField(null=True, blank=True)
    received_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_receipts",
        null=True,
        blank=True,
    )
    supplier_name = models.CharField(max_length=255, blank=True)
    external_reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    reason = models.CharField(max_length=500, blank=True)
    request_key = models.UUIDField(null=True, blank=True, unique=True)
    request_fingerprint = models.CharField(max_length=64, blank=True, default="")

    objects = models.Manager()

    class Meta:
        indexes = [
            models.Index(fields=["received_at", "id"], name="receipt_fifo_idx"),
        ]


class StockBatch(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    receipt = models.ForeignKey(
        StockReceipt, on_delete=models.PROTECT, related_name="batches"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="batches"
    )
    line_number = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField()
    quantity_remaining = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    cost_is_estimated = models.BooleanField(default=False)

    objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["receipt", "line_number"],
                name="stock_receipt_line_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_received__gt=0),
                name="stock_batch_received_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(line_number__gt=0),
                name="stock_batch_line_number_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="stock_batch_cost_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["product", "receipt"],
                name="batch_product_receipt_idx",
            ),
        ]


class SaleBatchAllocation(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    order_item = models.ForeignKey(
        "OrderItem", on_delete=models.PROTECT, related_name="batch_allocations"
    )
    batch = models.ForeignKey(
        StockBatch, on_delete=models.PROTECT, related_name="sale_allocations"
    )
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

    objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order_item", "batch"],
                name="sale_order_item_batch_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sale_batch_allocation_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="sale_batch_cost_nonnegative",
            ),
        ]


class StockAdjustment(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    batch = models.ForeignKey(
        StockBatch, on_delete=models.PROTECT, related_name="adjustments"
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_adjustments",
    )
    quantity_delta = models.IntegerField()
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    request_key = models.UUIDField(unique=True)
    request_fingerprint = models.CharField(max_length=64)

    objects = models.Manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity_delta=0),
                name="stock_adjustment_delta_nonzero",
            ),
        ]


class ProductImportOperation(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    request_key = models.UUIDField(unique=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="product_imports",
    )
    request_fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()


class Order(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    code = models.CharField(max_length=6)
    # covered by the composite (user, created) index below
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_index=False
    )
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    overall_amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    checkout_request_key = models.UUIDField(null=True, blank=True, unique=True)
    checkout_fingerprint = models.CharField(max_length=64, blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        indexes = [
            # nearly every report/order view filters or sorts on created
            models.Index(fields=["created"], name="order_created_idx"),
            # daily per-salesperson order lists
            models.Index(fields=["user", "created"], name="order_user_created_idx"),
        ]


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    order = models.ForeignKey(Order, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty_bought = models.PositiveIntegerField()
    paid_amount = models.DecimalField(max_digits=6, decimal_places=2)
    cost_amount = models.DecimalField(max_digits=20, decimal_places=2)
    cost_is_estimated = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(qty_bought__gt=0),
                name="order_item_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.product},{self.qty_bought},{self.created:%d-%m-%y %H:%M}"
