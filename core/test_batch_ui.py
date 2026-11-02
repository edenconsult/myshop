import datetime as dt
import uuid
from decimal import Decimal
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authapp.models import Account
from core.checkout import SaleLine, checkout
from core.inventory import ReceiptLine, receive_stock
from core.models import (
    Order,
    OrderItem,
    Product,
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
    StockReceipt,
    StockReceiptSource,
)


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


class BatchesDialogTests(BatchUiTestCase):
    """Task 3 — the read-only per-product batch history dialog."""

    def receive(self, units, cost, *, received_at, source=None, reason=""):
        """One single-line receipt, returned as the batch it created."""
        receive_stock(
            actor=self.admin,
            request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, units, Decimal(cost))],
            received_at=received_at,
            **({} if source is None else {"source": source, "reason": reason}),
        )
        return StockBatch.objects.get(receipt__received_at=received_at)

    def open_dialog(self):
        return self.client.get(reverse("core:product-batches", args=[self.product.pk]))

    @staticmethod
    def tbody_rows(html):
        """Every <tbody> row of the dialog as a list of whitespace-collapsed cells.

        Pinned through the parser instead of assertContains so a movement number
        can only be matched against the cell it is actually rendered in.
        """

        class TbodyProbe(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_tbody = False
                self.rows = []

            def handle_starttag(self, tag, attrs):
                if tag == "tbody":
                    self.in_tbody = True
                elif self.in_tbody and tag == "tr":
                    self.rows.append([])
                elif self.in_tbody and tag == "td":
                    self.rows[-1].append("")

            def handle_endtag(self, tag):
                if tag == "tbody":
                    self.in_tbody = False

            def handle_data(self, data):
                if self.in_tbody and self.rows and self.rows[-1]:
                    self.rows[-1][-1] += data

        probe = TbodyProbe()
        probe.feed(html)
        return [[" ".join(cell.split()) for cell in row] for row in probe.rows]

    def test_sold_and_adjusted_totals_do_not_multiply_each_other(self):
        """2 allocations of 3 and 2 adjustments of +1 read 6 and 2 — not 12 and 4.

        Seeded straight through the ORM (no checkout call): the dialog is a read
        path, and the fan-out the annotations must avoid is purely a query shape.
        The shortcut is what leaves this row deliberately violating a real
        invariant — check_inventory.py:78-82 requires
        remaining == received + adjusted - sold, and this batch is seeded as
        10 received / 6 sold / 2 adjusted / 10 remaining, which no service would
        ever write. Harmless here because the dialog only prints the numbers and
        never enforces them, and it isolates the query shape from any arithmetic.
        Do NOT copy this fixture for a scenario that must balance: sell through
        checkout instead, as test_sold_is_read_per_batch_not_per_product does.
        """
        batch = self.receive(10, "20.00", received_at=timezone.now())
        order = Order.objects.create(code="MOV001", user=self.cashier)
        for _ in range(2):
            item = OrderItem.objects.create(
                order=order,
                product=self.product,
                qty_bought=3,
                paid_amount=Decimal("54.00"),
                cost_amount=Decimal("60.00"),
            )
            # the unique (order_item, batch) constraint forces one item per line
            SaleBatchAllocation.objects.create(
                order_item=item, batch=batch, quantity=3, unit_cost=Decimal("20.00")
            )
            StockAdjustment.objects.create(
                batch=batch,
                recorded_by=self.admin,
                quantity_delta=1,
                reason="Counted one more",
                request_key=uuid.uuid4(),
                request_fingerprint="mov001",
            )

        response = self.open_dialog()
        row = response.context["batches"][0]
        self.assertEqual(row.sold, 6)
        self.assertEqual(row.adjusted, 2)
        # the same numbers the owner actually sees: received, sold, adjusted,
        # remaining — remaining is the seeded 10, not the invariant's 10-6+2=6
        self.assertEqual(self.tbody_rows(response.content.decode())[0][-4:],
                         ["10", "6", "2", "10"])

    def test_shows_movement_columns_and_reconciliation(self):
        receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 10, Decimal("20.00"))],
            received_at=timezone.now(),
        )
        response = self.client.get(
            reverse("core:product-batches", args=[self.product.pk])
        )
        row = response.context["batches"][0]
        self.assertEqual(row.sold, 0)
        self.assertEqual(row.adjusted, 0)
        # the brief asserted assertContains(response, "10"), which any "10" in the
        # document satisfied; pin the number to the Received cell it belongs to.
        self.assertEqual(self.tbody_rows(response.content.decode())[0][-4:],
                         ["10", "0", "0", "10"])
        self.assertContains(response, "GH₵ 20.00")

    def test_sold_is_read_per_batch_not_per_product(self):
        """A 5-unit FIFO sale split 4 + 1 across two batches must not read 5 + 5.

        The fan-out test above has one batch, so any correlation key that widens
        to the product still returns that batch's own total there and passes.
        Sold through the real checkout service, so the whole fixture stays inside
        check_inventory.py's invariant: both batches and the shelf agree.
        """
        # Spaced timestamps: two back-to-back timezone.now() calls can land on
        # the same Windows clock tick, which would make FIFO order a coin flip.
        older = timezone.now() - dt.timedelta(days=1)
        self.receive(4, "10.00", received_at=older)
        self.receive(6, "12.00", received_at=older + dt.timedelta(hours=1))
        checkout(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[SaleLine(self.product.pk, 5, Decimal("90.00"))],
        )
        self.product.refresh_from_db()
        response = self.open_dialog()
        # newest receipt first: the 6-unit batch gave 1 unit, the 4-unit batch all 4
        self.assertEqual(
            [(b.quantity_received, b.sold, b.adjusted, b.quantity_remaining)
             for b in response.context["batches"]],
            [(6, 1, 0, 5), (4, 4, 0, 0)],
        )
        rows = self.tbody_rows(response.content.decode())
        self.assertEqual(
            [row[-4:] for row in rows],
            [["6", "1", "0", "5"], ["4", "4", "0", "0 Depleted"]],
        )
        # the per-batch split is what the guard is for: one shared number fails
        self.assertNotEqual(rows[0][-3], rows[1][-3])
        # and the sums still agree, so the footer stays on its balanced branch
        self.assertEqual(response.context["remaining_total"], self.product.stock)
        self.assertNotContains(response, "out of balance")

    def test_saleperson_blocked(self):
        self.client.force_login(self.cashier)
        self.assertEqual(
            self.client.get(reverse("core:product-batches", args=[self.product.pk])).status_code,
            302,
        )

    def test_reconciliation_line_flags_a_shelf_that_disagrees(self):
        batch = self.receive(10, "20.00", received_at=timezone.now())
        # A pre-tracking sale leaves 7 in the batch against 10 on the shelf;
        # Product.save() forbids touching stock by hand, so drift is written
        # through the batch, which is exactly what the owner must be shown.
        batch.quantity_remaining = 7
        batch.save(update_fields=["quantity_remaining"])
        response = self.open_dialog()
        self.assertEqual(response.context["remaining_total"], 7)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertContains(response, "Sum of batches")
        self.assertContains(
            response,
            "out of balance, use Adjust Stock Count from the Current stock column",
        )

    def test_balanced_shelf_does_not_claim_to_be_out_of_balance(self):
        self.receive(10, "20.00", received_at=timezone.now())
        self.product.refresh_from_db()
        response = self.open_dialog()
        self.assertEqual(response.context["remaining_total"], self.product.stock)
        self.assertContains(response, "Sum of batches")
        self.assertNotContains(response, "out of balance")

    def test_depleted_batches_stay_visible_newest_first(self):
        # Spaced timestamps: two back-to-back timezone.now() calls can land on
        # the same Windows clock tick, which would make the ordering a coin flip.
        older = timezone.now() - dt.timedelta(days=1)
        self.receive(4, "10.00", received_at=older)
        self.receive(6, "12.00", received_at=older + dt.timedelta(hours=1))
        oldest = StockBatch.objects.order_by("receipt__received_at").first()
        # the landed adjustment service writes the ledger and the shelf together
        self.client.post(
            reverse("core:update-product-stock", args=[self.product.pk]),
            {"batch_id": str(oldest.pk), "quantity_delta": "-4",
             "reason": "Written off at the market", "request_key": str(uuid.uuid4())},
        )
        self.product.refresh_from_db()
        response = self.open_dialog()
        self.assertEqual(
            [(b.quantity_remaining, b.sold, b.adjusted) for b in response.context["batches"]],
            [(6, 0, 0), (0, 0, -4)],
        )
        self.assertEqual(response.context["remaining_total"], 6)
        self.assertEqual(self.product.stock, 6)
        rows = self.tbody_rows(response.content.decode())
        self.assertEqual(
            [row[-4:] for row in rows],
            [["6", "0", "0", "6"], ["4", "0", "-4", "0 Depleted"]],
        )

    def test_source_badge_and_estimated_cost_pill(self):
        self.receive(
            8, "12.00", received_at=timezone.now(),
            source=StockReceiptSource.OPENING, reason="Opened the till",
        )
        response = self.open_dialog()
        row = self.tbody_rows(response.content.decode())[0]
        self.assertIn("Opening balance", row[0])
        self.assertNotIn("Purchase", row[0])
        self.assertEqual(row[1], "GH₵ 12.00 estimated")
        self.assertEqual(row[-4:], ["8", "0", "0", "8"])

    def test_empty_history_asks_for_a_restock(self):
        response = self.open_dialog()
        self.assertEqual(list(response.context["batches"]), [])
        self.assertEqual(response.context["remaining_total"], 0)
        self.assertContains(response, "Restock this product to start batch tracking.")

    def test_unknown_product_is_a_404(self):
        self.assertEqual(
            self.client.get(reverse("core:product-batches", args=[uuid.uuid4()])).status_code,
            404,
        )

    @staticmethod
    def js_attribute_names(html):
        """Every Alpine/htmx directive attribute the rendered markup carries."""

        class DirectiveProbe(HTMLParser):
            def __init__(self):
                super().__init__()
                self.found = []

            def handle_starttag(self, tag, attrs):
                self.found.extend(
                    name for name, _ in attrs
                    if name.startswith(("x-", "hx-on", "@", ":"))
                )

        probe = DirectiveProbe()
        probe.feed(html)
        return probe.found

    def test_history_dialog_is_inert_markup(self):
        """A read-only history needs no script: no Alpine scope, no htmx handler.

        Pinned because the dialog's only job is showing numbers; the trigger
        that opens it lives in the row, not in this markup.
        """
        # empty state first, then the same check with a row to show
        self.assertEqual(self.js_attribute_names(self.open_dialog().content.decode()), [])
        self.receive(10, "20.00", received_at=timezone.now())
        self.assertEqual(self.js_attribute_names(self.open_dialog().content.decode()), [])

    def test_row_action_opens_the_dialog_in_the_modal_root(self):
        """The fourth icon button of the actions cell is the dialog's only trigger."""
        body = self.client.get(
            reverse("core:load-products"), {"l": 10, "p": 1}
        ).content.decode()

        class TriggerProbe(HTMLParser):
            def __init__(self):
                super().__init__()
                self.triggers = []

            def handle_starttag(self, tag, attrs):
                if tag == "button":
                    attributes = dict(attrs)
                    if attributes.get("title") == "Batch history":
                        self.triggers.append(attributes)

        probe = TriggerProbe()
        probe.feed(body)
        self.assertEqual(len(probe.triggers), 1)
        self.assertEqual(
            probe.triggers[0],
            {
                "title": "Batch history",
                "type": "button",
                "hx-get": reverse("core:product-batches", args=[self.product.pk]),
                "hx-target": "#modal_root",
                "hx-swap": "innerHTML",
                "class": probe.triggers[0]["class"],  # styling is the row's own idiom
            },
        )
        self.assertIn("#sell", body)  # the local sprite symbol the button draws
