import uuid

from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models

# from django.contrib.auth import get_user_model
from django.conf import settings

# Create your models here.


class Product(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    name = models.CharField(max_length=255, unique=True)
    stock = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    profit_rate = models.DecimalField(max_digits=3, decimal_places=2)
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
