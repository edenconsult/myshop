import datetime as dt
import uuid
from decimal import Decimal
from html.parser import HTMLParser

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


class AdjustDialogTests(BatchUiTestCase):
    def seed_batches(self):
        # Deliberately spaced timestamps: two back-to-back timezone.now()
        # calls can land on the same Windows clock tick, and then the FIFO
        # ordering (and "oldest") below would be a coin flip.
        received_at = timezone.now() - dt.timedelta(days=1)
        for qty, cost in ((10, "20.00"), (5, "25.00")):
            receive_stock(
                actor=self.admin, request_key=uuid.uuid4(),
                lines=[ReceiptLine(self.product.pk, qty, Decimal(cost))],
                received_at=received_at,
            )
            received_at += dt.timedelta(hours=1)

    def test_question_dialog_lists_open_batches_fifo(self):
        self.seed_batches()
        response = self.client.get(
            reverse("core:adjust-stock-question", args=[self.product.pk])
        )
        self.assertContains(response, 'name="batch_id"')
        self.assertContains(response, 'name="quantity_delta"')
        self.assertContains(response, 'name="reason"')
        self.assertContains(response, 'name="request_key"')
        batches = list(response.context["batches"])
        self.assertEqual(
            [b.quantity_received for b in batches], [10, 5]
        )  # FIFO order, older first

    def test_short_count_adjustment_consumes_selected_batch(self):
        self.seed_batches()
        oldest = StockBatch.objects.order_by("receipt__received_at").first()
        response = self.client.post(
            reverse("core:update-product-stock", args=[self.product.pk]),
            {"batch_id": str(oldest.pk), "quantity_delta": "-2",
             "reason": "Damaged in transit", "request_key": str(uuid.uuid4())},
        )
        oldest.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(oldest.quantity_remaining, 8)
        # The brief expected 15, but adjust_batch syncs the shelf with the
        # batch (core/inventory.py:402-406): a short count takes the two
        # missing units off the shelf too, so 10+5-2 lands at 13.
        self.assertEqual(self.product.stock, 13)
        self.assertContains(response, "Shea Repair Balm")
        self.assertNotContains(response, "could not be saved")

    def test_missing_batch_shows_visible_error_on_the_row(self):
        self.seed_batches()
        response = self.client.post(
            reverse("core:update-product-stock", args=[self.product.pk]),
            {"quantity_delta": "-1", "reason": "x", "request_key": str(uuid.uuid4())},
        )
        self.assertContains(response, "Select a batch")

    def test_saleperson_blocked_from_question_dialog(self):
        self.client.force_login(self.cashier)
        response = self.client.get(
            reverse("core:adjust-stock-question", args=[self.product.pk])
        )
        self.assertEqual(response.status_code, 302)


class AdjustDialogMarkupTests(BatchUiTestCase):
    def test_rendered_dialog_carries_one_parseable_x_data(self):
        receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 4, Decimal("10.00"))],
            received_at=timezone.now(),
        )
        response = self.client.get(
            reverse("core:adjust-stock-question", args=[self.product.pk])
        )
        names = []

        class DialogDivProbe(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == "div" and not names and "x-data" in dict(attrs):
                    names.extend(sorted(dict(attrs)))

        DialogDivProbe().feed(response.content.decode())
        self.assertEqual(names, ["class", "x-data"])
