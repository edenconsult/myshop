import uuid
from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex, OpClass
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

    @property
    def margin(self):
        """Gross margin on revenue: what share of the retail price is profit."""
        if self.price:
            return (self.price - self.cost) / self.price * 100
        return Decimal("0")


class Order(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    code = models.CharField(max_length=6)
    # covered by the composite (user, created) index below
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_index=False
    )
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    overall_amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
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
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    qty_bought = models.PositiveIntegerField()
    paid_amount = models.DecimalField(max_digits=6, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    def __str__(self):
        return f"{self.product},{self.qty_bought},{self.created:%d-%m-%y %H:%M}"
