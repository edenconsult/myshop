from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from authapp.models import Account
from core.catalog_imports import import_catalogue_rows
from core.inventory import ReceiptLine, receive_stock
from core.models import (
    Product,
    ProductImportOperation,
    StockBatch,
    StockReceiptSource,
)


class CatalogueImportTests(TestCase):
    def setUp(self):
        self.admin = Account.objects.create_user(
            username="catalogue-admin",
            password="test-password",
            user_type="ADMIN",
        )

    def row(self, **overrides):
        return {
            "PRODUCT": "Imported Face Cream",
            "SKU": "IFC01",
            "CATEGORY": "Skincare",
            "QUANTITY": "4",
            "COST PRICE": "7.25",
            "SELLING PRICE": "12.00",
            **overrides,
        }

    def test_new_products_receive_estimated_opening_batches(self):
        request_key = uuid4()
        operation = import_catalogue_rows(
            actor=self.admin,
            request_key=request_key,
            rows=[self.row()],
        )
        replay = import_catalogue_rows(
            actor=self.admin,
            request_key=request_key,
            rows=[self.row()],
        )

        product = Product.objects.get(sku="IFC01")
        batch = StockBatch.objects.get(product=product)
        self.assertEqual(operation.pk, replay.pk)
        self.assertEqual(product.stock, 4)
        self.assertEqual(batch.quantity_received, 4)
        self.assertEqual(batch.unit_cost, Decimal("7.25"))
        self.assertTrue(batch.cost_is_estimated)
        self.assertEqual(batch.receipt.source, StockReceiptSource.IMPORT_OPENING)
        self.assertEqual(ProductImportOperation.objects.count(), 1)

    def test_existing_sku_updates_metadata_without_changing_stock_or_identity(self):
        product = Product.objects.create(
            name="Old Cream Name",
            sku="IFC01",
            stock=0,
            cost=Decimal("5.00"),
            price=Decimal("9.00"),
            profit_rate=Decimal("0.55"),
            slug="old-cream-name",
        )
        receive_stock(
            actor=self.admin,
            request_key=uuid4(),
            lines=[ReceiptLine(product.pk, 6, Decimal("4.00"))],
            received_at=timezone.now(),
        )

        import_catalogue_rows(
            actor=self.admin,
            request_key=uuid4(),
            rows=[self.row(QUANTITY="99", **{"PRODUCT": "Updated Cream"})],
            update_existing=True,
        )

        product.refresh_from_db()
        self.assertEqual(Product.objects.filter(sku="IFC01").count(), 1)
        self.assertEqual(product.name, "Updated Cream")
        self.assertEqual(product.stock, 6)
        self.assertEqual(product.cost, Decimal("7.25"))
        self.assertEqual(StockBatch.objects.filter(product=product).count(), 1)
        self.assertEqual(StockBatch.objects.get(product=product).quantity_remaining, 6)

    def test_duplicate_or_malformed_rows_fail_before_any_write(self):
        with self.assertRaises(ValidationError):
            import_catalogue_rows(
                actor=self.admin,
                request_key=uuid4(),
                rows=[self.row(), self.row(PRODUCT=" imported face cream ")],
            )
        with self.assertRaises(ValidationError):
            import_catalogue_rows(
                actor=self.admin,
                request_key=uuid4(),
                rows=[self.row(QUANTITY="1.5")],
            )

        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(ProductImportOperation.objects.count(), 0)

    def test_request_key_cannot_be_reused_for_another_import(self):
        key = uuid4()
        import_catalogue_rows(
            actor=self.admin,
            request_key=key,
            rows=[self.row()],
        )

        with self.assertRaises(ValidationError):
            import_catalogue_rows(
                actor=self.admin,
                request_key=key,
                rows=[self.row(QUANTITY="5")],
            )
        self.assertEqual(Product.objects.get(sku="IFC01").stock, 4)

