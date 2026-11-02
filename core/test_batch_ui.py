import datetime as dt
import uuid
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authapp.models import Account
from core.inventory import ReceiptLine, receive_stock
from core.models import Product, StockBatch, StockReceipt, StockReceiptSource


class BatchUiTestCase(TestCase):
    def setUp(self):
        self.admin = Account.objects.create_user(
            username="aba", password="pw", user_type="ADMIN"
        )
        self.cashier = Account.objects.create_user(
            username="kwame", password="pw", user_type="SALEPERSON"
        )
        self.product = Product.objects.create(
            name="Shea Repair Balm", sku="SHB01", stock=0,
            cost=Decimal("9.00"), price=Decimal("18.00"),
            profit_rate=Decimal("0.50"),
        )
        self.client.force_login(self.admin)


class RestockDialogTests(BatchUiTestCase):
    def test_dialog_exposes_cost_purchase_fields_and_request_key(self):
        response = self.client.get(
            reverse("core:restock-product", args=[self.product.pk])
        )
        self.assertContains(response, 'name="unit_cost"')
        self.assertContains(response, 'name="request_key"')
        self.assertContains(response, 'name="purchased_on"')
        self.assertContains(response, 'name="supplier_name"')
        self.assertContains(response, 'name="external_reference"')

    def test_posted_cost_date_and_supplier_are_persisted_not_catalogue_defaults(self):
        key = str(uuid.uuid4())
        self.client.post(
            reverse("core:restock-product", args=[self.product.pk]),
            {"units": "10", "unit_cost": "20.00", "purchased_on": "2026-10-31",
             "supplier_name": "Noble", "external_reference": "INV-7",
             "request_key": key},
        )
        receipt = StockReceipt.objects.get(request_key=key)
        self.assertEqual(receipt.source, StockReceiptSource.PURCHASE)
        self.assertEqual(receipt.purchased_on, dt.date(2026, 10, 31))
        self.assertEqual(receipt.supplier_name, "Noble")
        batch = StockBatch.objects.get(receipt=receipt)
        self.assertEqual(batch.unit_cost, Decimal("20.00"))
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.cost),
                         (10, Decimal("20.00")))

    def test_replaying_the_same_dialog_key_adds_stock_once(self):
        url = reverse("core:restock-product", args=[self.product.pk])
        payload = {"units": "10", "unit_cost": "20.00",
                   "request_key": str(uuid.uuid4())}
        self.client.post(url, payload)
        self.client.post(url, payload)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(StockBatch.objects.count(), 1)

    def test_saleperson_cannot_open_or_post_restock(self):
        self.client.force_login(self.cashier)
        url = reverse("core:restock-product", args=[self.product.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(
            self.client.post(url, {"units": "5", "request_key": str(uuid.uuid4())}).status_code,
            302,
        )
