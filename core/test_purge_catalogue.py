from decimal import Decimal
from io import StringIO
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from authapp.models import Account
from core.models import (
    Order,
    OrderItem,
    Product,
    ProductImportOperation,
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
    StockReceipt,
    StockReceiptDraft,
)


class PurgeCatalogueCommandTests(TestCase):
    def setUp(self):
        self.admin = Account.objects.create_user(
            username="purge-admin",
            password="test-password",
            user_type="ADMIN",
        )
        self.product = Product.objects.create(
            name="Purge Test Product",
            stock=1,
            cost=Decimal("10.00"),
            price=Decimal("20.00"),
            profit_rate=Decimal("0.50"),
            slug="purge-test-product",
        )
        self.draft = StockReceiptDraft.objects.create(
            recorded_by=self.admin,
            request_key=uuid4(),
        )
        self.receipt = StockReceipt.objects.create(
            source="PURCHASE",
            received_at=timezone.now(),
            recorded_by=self.admin,
            draft=self.draft,
            draft_group_index=0,
            request_key=uuid4(),
        )
        batch = StockBatch.objects.create(
            receipt=self.receipt,
            product=self.product,
            line_number=1,
            quantity_received=1,
            quantity_remaining=0,
            unit_cost=Decimal("10.00"),
        )
        order = Order.objects.create(user=self.admin, code="PURGE1")
        order_item = OrderItem.objects.create(
            order=order,
            product=self.product,
            qty_bought=1,
            paid_amount=Decimal("20.00"),
            cost_amount=Decimal("10.00"),
        )
        SaleBatchAllocation.objects.create(
            order_item=order_item,
            batch=batch,
            quantity=1,
            unit_cost=Decimal("10.00"),
        )
        StockAdjustment.objects.create(
            batch=batch,
            recorded_by=self.admin,
            quantity_delta=-1,
            reason="Test adjustment",
            request_key=uuid4(),
            request_fingerprint="test",
        )
        ProductImportOperation.objects.create(
            request_key=uuid4(),
            recorded_by=self.admin,
            request_fingerprint="test",
        )

    def test_default_is_dry_run(self):
        output = StringIO()

        call_command("purge_catalogue", stdout=output)

        self.assertIn("Dry run; no records deleted:", output.getvalue())
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertEqual(SaleBatchAllocation.objects.count(), 1)
        self.assertEqual(StockAdjustment.objects.count(), 1)
        self.assertEqual(StockBatch.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(Order.objects.count(), 1)
        self.assertTrue(StockReceipt.objects.filter(pk=self.receipt.pk).exists())
        self.assertTrue(StockReceiptDraft.objects.filter(pk=self.draft.pk).exists())
        self.assertEqual(ProductImportOperation.objects.count(), 1)

    def test_execute_deletes_products_and_protected_history(self):
        output = StringIO()

        call_command("purge_catalogue", "--execute", stdout=output)

        self.assertIn(
            "Catalogue, sales, and inventory history purged.", output.getvalue()
        )
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(SaleBatchAllocation.objects.count(), 0)
        self.assertEqual(StockAdjustment.objects.count(), 0)
        self.assertEqual(StockBatch.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(StockReceipt.objects.count(), 0)
        self.assertEqual(StockReceiptDraft.objects.count(), 0)
        self.assertEqual(ProductImportOperation.objects.count(), 0)
        self.assertTrue(Account.objects.filter(pk=self.admin.pk).exists())
