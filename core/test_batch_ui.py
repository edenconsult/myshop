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
    """Shared fixture and the two markup probes every task in this module uses.

    Both helpers were hoisted here after the Task 4 review: ``tbody_rows`` lived
    in ``BatchesDialogTests`` while ``ReceiptPagesTests`` reached across the class
    to call it, and the directive-attribute probe existed twice — once scanning a
    dialog fragment whole, once scanning a full page's ``<main>`` — with the same
    prefix list copy-pasted between them.
    """

    # Attribute names that mean "this markup carries behaviour": Alpine's x-
    # prefix and its @ / : shorthands, every htmx verb (hx-get, hx-target,
    # hx-on …) and inline event handlers (onclick, onload …). The list the Task 3
    # probe shipped with — ("x-", "hx-on", "@", ":") — was narrower than the
    # "no inline JS" claim: a plain onclick="…" or an hx-get button passed it.
    JS_ATTRIBUTE_PREFIXES = ("x-", "hx-", "on", "@", ":")

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

    @staticmethod
    def tbody_rows(html):
        """Every <tbody> row of the rendered table as a list of whitespace-collapsed cells.

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

    @classmethod
    def js_attribute_names(cls, html, *, within_main=False):
        """Every inline-JS marker the rendered markup carries.

        A marker is a directive attribute name (see JS_ATTRIBUTE_PREFIXES) or the
        literal ``"script"`` for a ``<script>`` element, so an inline handler, an
        htmx verb and a page-local script all fail a "this markup is inert"
        assertion instead of slipping past it.

        ``within_main=True`` narrows the scan to ``<main id="main-content">``, i.e.
        what a page's own block renders: templates/_base.html legitimately owns the
        shell's Alpine scope and its own scripts outside that element. A dialog
        fragment carries no such wrapper, so it scans whole (``within_main=False``)
        — narrowing it to ``<main>`` would have made the probe trivially empty.
        """
        void = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                "meta", "param", "source", "track", "wbr"}

        class DirectiveProbe(HTMLParser):
            def __init__(self):
                super().__init__()
                self.depth = 0  # nesting inside <main id="main-content">; 0 = outside
                self.found = []

            def visit(self, tag, attrs, self_closing=False):
                if within_main:
                    if not self.depth:
                        if tag == "main" and dict(attrs).get("id") == "main-content":
                            self.depth = 1
                        return
                    if not self_closing and tag not in void:
                        self.depth += 1
                if tag == "script":
                    self.found.append("script")
                self.found.extend(
                    name
                    for name, _ in attrs
                    if name.startswith(cls.JS_ATTRIBUTE_PREFIXES)
                )

            def handle_starttag(self, tag, attrs):
                self.visit(tag, attrs)

            def handle_startendtag(self, tag, attrs):
                self.visit(tag, attrs, self_closing=True)

            def handle_endtag(self, tag):
                if within_main and self.depth and tag not in void:
                    self.depth -= 1

        probe = DirectiveProbe()
        probe.feed(html)
        return probe.found


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


class ReceiptPagesTests(BatchUiTestCase):
    """Task 4 — the owner-facing receipt register: the list page and the line detail."""

    def make_receipts(self):
        """The two receipts the brief seeds, returned oldest first."""
        # An hour apart on purpose: two back-to-back timezone.now() calls can
        # land on the same Windows clock tick, and the newest-first ordering
        # must never be a coin flip.
        purchase = receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 10, Decimal("20.00"))],
            received_at=timezone.now(), supplier_name="Noble",
        )
        later = receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 5, Decimal("25.00"))],
            received_at=timezone.now() + dt.timedelta(hours=1),
        )
        return purchase, later

    def drop_cutover_receipts(self):
        """Remove every line-free receipt the database happens to already hold.

        Migration 0015_backfill_opening_stock_and_costs creates one cutover
        StockReceipt on every database — in the test database, where no product
        has stock yet, it stays line-free. Tests that need exact page arithmetic
        drop it (in-transaction, rolled back), and the tests below that care about
        a line-free receipt drop it before writing their own, so nothing in this
        module reads a row another session's migration decided to create.
        """
        StockReceipt.objects.filter(batches__isnull=True).delete()

    def make_batchless_receipt(self, *, reason="Cutover opening stock."):
        """Write a receipt with no StockBatch line, the way the cutover leaves one.

        Field names and nullability read off core/models.py:93-118: `source` and
        `received_at` are the only required columns (`id` defaults to a UUID,
        `created_at` is auto_now_add, `recorded_by` is nullable and `supplier_name`
        / `external_reference` / `notes` / `reason` are blank CharTextFields, not
        null), so this is the same shape migration
        0015_backfill_opening_stock_and_costs:84-89 writes — written here, so the
        test owns its own fixture instead of `.get()`ing precisely one of them.
        """
        return StockReceipt.objects.create(
            source=StockReceiptSource.OPENING,
            received_at=timezone.now(),
            reason=reason,
            notes="Created by the receipt register test.",
        )

    def seed_receipts(self, total):
        """`total` one-line receipts, index 0 the newest, written through the ORM.

        The register is a read path and the page-size check needs 26 of them;
        receive_stock would only rebuild, line by line, rows this test never
        reads through a service.
        """
        for index in range(total):
            receipt = StockReceipt.objects.create(
                source=StockReceiptSource.PURCHASE,
                received_at=timezone.now() - dt.timedelta(minutes=index),
                recorded_by=self.admin,
                supplier_name=f"Supplier {index}",
            )
            StockBatch.objects.create(
                receipt=receipt,
                product=self.product,
                line_number=1,
                quantity_received=1,
                quantity_remaining=1,
                unit_cost=Decimal("1.00"),
            )

    def open_detail(self, receipt):
        return self.client.get(reverse("core:stock-receipt-detail", args=[receipt.pk]))

    def test_list_is_newest_first_with_totals_and_source_badges(self):
        # the line-free cutover receipt 0015 leaves behind has its own test; this
        # one is about the arithmetic of receipts that do have lines.
        self.drop_cutover_receipts()
        purchase, later = self.make_receipts()
        response = self.client.get(reverse("core:stock-receipts"))
        receipts = list(response.context["page_obj"].object_list)
        self.assertEqual(len(receipts), 2)
        self.assertEqual([r.pk for r in receipts], [later.pk, purchase.pk])
        # The plan's `receipts[0].batches__units` is a plan defect: annotate()
        # publishes the plain alias, never a join-keyed attribute.
        self.assertEqual(receipts[0].units, 5)   # newest first
        self.assertEqual(receipts[0].value, Decimal("125.00"))
        # get_source_display() yields the humanised label ("Purchase"), so that
        # is the string the badge shows and the string asserted here; the raw
        # choice value is never printed.
        self.assertContains(response, "Purchase")
        self.assertContains(response, "Noble")
        self.assertContains(response, "GH₵ 125.00")
        rows = self.tbody_rows(response.content.decode())
        self.assertEqual([row[3] for row in rows], ["Purchase", "Purchase"])  # Source
        self.assertEqual([row[4] for row in rows], ["—", "Noble"])  # newest has no supplier
        self.assertEqual([row[2] for row in rows], ["—", "—"])  # purchased_on unset
        self.assertEqual([row[5] for row in rows], ["1", "1"])  # Lines
        self.assertEqual([row[6] for row in rows], ["5", "10"])  # Units
        self.assertEqual([row[7] for row in rows], ["GH₵ 125.00", "GH₵ 200.00"])  # Cost
        self.assertIn(
            timezone.localtime(receipts[0].received_at).strftime("%d %b %Y %H:%M"), rows[0][1]
        )

    def test_cutover_receipt_without_lines_reads_as_zero(self):
        """A line-free receipt reads as zeros, never as blanks.

        The register keeps these rows (controller ruling), and the cutover state
        that produces one is real: a StockReceipt with no StockBatch, because the
        backfill only gives lines to products that already had stock. A bare
        Subquery annotation would put None in the units, lines and cost cells and
        leave the detail page with an empty table and no totals.

        The row is written here instead of fetched with
        `StockReceipt.objects.filter(batches__isnull=True).distinct().get()`. That
        version passed only while precisely one batch-less receipt happened to
        exist, so a change to another session's migration — make the creation
        conditional, add lines, run it twice — errored this UI test with
        DoesNotExist / MultipleObjectsReturned over something outside this task.
        """
        self.drop_cutover_receipts()
        cutover = self.make_batchless_receipt()
        rows = self.tbody_rows(
            self.client.get(reverse("core:stock-receipts")).content.decode()
        )
        # the single row on the page is the receipt this test wrote
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0][0].startswith(cutover.id.hex[:8]))
        self.assertEqual(rows[0][3:8], ["Opening balance", "—", "0", "0", "GH₵ 0.00"])
        detail = self.open_detail(cutover)
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "This receipt has no lines.")
        self.assertContains(detail, "GH₵ 0.00")
        # one tbody row only, and it is the empty-state row, not a line row
        self.assertEqual(len(self.tbody_rows(detail.content.decode())), 1)
        self.assertEqual(detail.context["remaining_total"], 0)
        self.assertEqual(detail.context["remaining_value_total"], Decimal("0.00"))

    def test_several_line_free_receipts_each_read_as_zero(self):
        """The zero reading is per row, so nothing may assume there is only one.

        Paired with the test above: a fixture that *searches* for the line-free
        row is singular by construction and breaks the day a second one exists.
        Writing two, then reading the register, is what proves the page arithmetic
        and the annotations hold whatever the cutover left behind.
        """
        self.drop_cutover_receipts()
        receipts = [
            self.make_batchless_receipt(reason="Cutover opening stock."),
            self.make_batchless_receipt(reason="A second line-free receipt."),
        ]
        rows = self.tbody_rows(
            self.client.get(reverse("core:stock-receipts")).content.decode()
        )
        # both stay visible — the register filters nothing — and each reads zero
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row[0][:8] for row in rows}, {receipt.id.hex[:8] for receipt in receipts}
        )
        self.assertEqual(
            [row[3:8] for row in rows],
            [["Opening balance", "—", "0", "0", "GH₵ 0.00"]] * 2,
        )
        for receipt in receipts:
            detail = self.open_detail(receipt)
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(len(self.tbody_rows(detail.content.decode())), 1)
            self.assertEqual(detail.context["remaining_total"], 0)
            self.assertEqual(detail.context["remaining_value_total"], Decimal("0.00"))

    def test_list_pages_at_twenty_five_receipts(self):
        self.drop_cutover_receipts()
        self.seed_receipts(26)
        response = self.client.get(reverse("core:stock-receipts"))
        page = response.context["page_obj"]
        self.assertEqual(page.paginator.per_page, 25)
        self.assertEqual(page.paginator.num_pages, 2)
        self.assertEqual(len(page.object_list), 25)
        self.assertEqual(len(self.tbody_rows(response.content.decode())), 25)
        # the footer links are plain hrefs: this page carries no script at all
        self.assertContains(response, 'href="?page=2"')
        second = self.client.get(reverse("core:stock-receipts"), {"page": "2"})
        self.assertEqual(second.context["page_obj"].number, 2)
        rows = self.tbody_rows(second.content.decode())
        self.assertEqual([row[4] for row in rows], ["Supplier 25"])  # the oldest one
        self.assertContains(second, "Showing rows 26–26 of 26 receipts")
        self.assertContains(second, 'href="?page=1"')
        # Paginator.get_page clamps instead of raising: junk and far-out numbers
        # both answer 200, never a 500 on the owner's page.
        self.assertEqual(self.client.get(reverse("core:stock-receipts"), {"page": "junk"}).status_code, 200)
        oversized = self.client.get(reverse("core:stock-receipts"), {"page": "99"})
        self.assertEqual(oversized.status_code, 200)
        self.assertEqual(oversized.context["page_obj"].number, 2)

    def test_list_without_receipts_says_so(self):
        self.drop_cutover_receipts()
        response = self.client.get(reverse("core:stock-receipts"))
        self.assertEqual(len(response.context["page_obj"].object_list), 0)
        self.assertContains(response, "No receipts have been recorded yet.")
        self.assertContains(response, "Restock a product to open the ledger.")
        # the footer's zero branch, worded so only it can satisfy this assertion
        self.assertContains(response, "Nothing to page through")

    def test_detail_lists_lines_with_remaining_and_estimated_flags(self):
        purchase, _ = self.make_receipts()
        response = self.open_detail(purchase)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Line 1")
        self.assertContains(response, "GH₵ 20.00")
        self.assertContains(response, str(purchase.id)[:8])
        # a PURCHASE receipt never carries the flag (inventory.py:279 derives it
        # from the source), so the word must not appear on this page...
        self.assertNotContains(response, "estimated")
        rows = self.tbody_rows(response.content.decode())
        self.assertEqual(rows[0][-4:], ["0", "0", "10", "GH₵ 200.00"])
        # ...while a non-purchase receipt does: same page, estimated cost and
        # the humanised source label.
        opening = receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 3, Decimal("7.50"))],
            received_at=timezone.now() + dt.timedelta(hours=2),
            source=StockReceiptSource.OPENING, reason="Opened the till",
        )
        detail = self.open_detail(opening)
        self.assertContains(detail, "Opening balance")
        self.assertContains(detail, "Opened the till")
        row = self.tbody_rows(detail.content.decode())[0]
        self.assertEqual(row[1], "Shea Repair Balm SHB01")
        self.assertEqual(row[3], "GH₵ 7.50 estimated")
        self.assertEqual(row[-4:], ["0", "0", "3", "GH₵ 22.50"])

    def test_detail_shows_what_is_still_on_the_shelf(self):
        """Sold / adjusted / remaining per line, and the footer that totals them."""
        receipt = receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 10, Decimal("20.00"))],
            received_at=timezone.now(),
        )
        checkout(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[SaleLine(self.product.pk, 4, Decimal("72.00"))],
        )
        response = self.open_detail(receipt)
        row = self.tbody_rows(response.content.decode())[0]
        self.assertEqual(row[-4:], ["4", "0", "6", "GH₵ 120.00"])
        self.assertEqual([b.sold for b in response.context["batches"]], [4])
        self.assertEqual(response.context["remaining_total"], 6)
        self.assertEqual(response.context["remaining_value_total"], Decimal("120.00"))
        self.assertContains(response, "GH₵ 200.00")  # received value
        self.assertContains(response, "GH₵ 120.00")  # still on the shelf

    def test_detail_orders_multi_line_receipts_by_line_number(self):
        baobab = Product.objects.create(
            name="Baobab Oil", sku="BOO1", stock=0,
            cost=Decimal("5.00"), price=Decimal("10.00"), profit_rate=Decimal("0.50"),
        )
        receipt = receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[
                ReceiptLine(baobab.pk, 6, Decimal("8.00")),
                ReceiptLine(self.product.pk, 3, Decimal("20.00")),
            ],
            received_at=timezone.now(),
            supplier_name="Market Runner",
            external_reference="GRN-11",
            purchased_on=dt.date(2026, 10, 31),
        )
        response = self.open_detail(receipt)
        self.assertEqual([b.line_number for b in response.context["batches"]], [1, 2])
        rows = self.tbody_rows(response.content.decode())
        self.assertEqual([row[0] for row in rows], ["Line 1", "Line 2"])
        self.assertEqual([row[1] for row in rows], ["Baobab Oil BOO1", "Shea Repair Balm SHB01"])
        # header card carries what the receipt was: supplier, GRN, purchase date
        self.assertContains(response, "Market Runner")
        self.assertContains(response, "GRN-11")
        self.assertContains(response, "31 Oct 2026")
        # the same per-receipt totals annotation, read on the detail page
        self.assertEqual(response.context["receipt"].line_count, 2)
        self.assertEqual(response.context["receipt"].units, 9)
        self.assertEqual(response.context["receipt"].value, Decimal("108.00"))
        # Drop the migration's line-free row first: object_list[0] used to be this
        # receipt only because of when 0015 happened to run (and, on an equal
        # received_at, because of a random-UUID -id tie-break). The row is now
        # addressed by pk, so the assertion is about this receipt, not about sort
        # order someone else's migration can change.
        self.drop_cutover_receipts()
        listed = self.client.get(reverse("core:stock-receipts"))
        page = listed.context["page_obj"]
        self.assertEqual([r.pk for r in page.object_list], [receipt.pk])
        # Money columns pinned on the suite's ONLY multi-line receipt. Every other
        # list assertion reads one-line receipts, where even an annotation that
        # fans out across a join still adds up right by accident. Here:
        # 6 + 3 = 9 units, 6 x 8.00 + 3 x 20.00 = GH₵ 108.00, over 2 lines.
        self.assertEqual(page.object_list[0].line_count, 2)
        self.assertEqual(page.object_list[0].units, 9)
        self.assertEqual(page.object_list[0].value, Decimal("108.00"))
        # and the same three figures as the cell the owner reads them in
        self.assertEqual(
            self.tbody_rows(listed.content.decode())[0][3:8],
            ["Purchase", "Market Runner", "2", "9", "GH₵ 108.00"],
        )

    def test_unknown_receipt_is_a_404(self):
        self.assertEqual(
            self.client.get(reverse("core:stock-receipt-detail", args=[uuid.uuid4()])).status_code,
            404,
        )

    def test_saleperson_blocked_from_both_pages(self):
        self.client.force_login(self.cashier)
        receipt = receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 1, Decimal("1.00"))],
            received_at=timezone.now(),
        )
        # the brief's loop only covered the list page; both are ADMIN-only
        for name in ("core:stock-receipts", "core:stock-receipt-detail"):
            with self.subTest(page=name):
                arguments = [] if name == "core:stock-receipts" else [receipt.pk]
                self.assertEqual(
                    self.client.get(reverse(name, args=arguments)).status_code, 302
                )

    def test_signed_out_requests_are_redirected(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("core:stock-receipts")).status_code, 302)
        self.assertEqual(
            self.client.get(reverse("core:stock-receipt-detail", args=[uuid.uuid4()])).status_code,
            302,
        )

    def test_both_pages_are_get_only(self):
        receipt = receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 1, Decimal("1.00"))],
            received_at=timezone.now(),
        )
        self.assertEqual(
            self.client.post(reverse("core:stock-receipts"), {}).status_code, 405
        )
        self.assertEqual(
            self.client.post(reverse("core:stock-receipt-detail", args=[receipt.pk]), {}).status_code,
            405,
        )

    def test_products_header_links_to_the_register(self):
        response = self.client.get(reverse("core:products"))
        self.assertContains(response, "Purchase Receipts")
        self.assertContains(response, f'href="{reverse("core:stock-receipts")}"')
        self.assertIn("#receipt_long", response.content.decode())

    def test_register_pages_are_inert_markup(self):
        """Both pages are read-only tables: no Alpine scope, no htmx verb, no script."""
        receipt = receive_stock(
            actor=self.admin, request_key=uuid.uuid4(),
            lines=[ReceiptLine(self.product.pk, 2, Decimal("3.00"))],
            received_at=timezone.now(),
        )
        self.assertEqual(
            self.js_attribute_names(
                self.client.get(reverse("core:stock-receipts")).content.decode(),
                within_main=True,
            ),
            [],
        )
        self.assertEqual(
            self.js_attribute_names(
                self.open_detail(receipt).content.decode(), within_main=True
            ),
            [],
        )

    def test_the_inert_markup_probe_reports_every_marker_it_claims(self):
        """A scope-based probe is only evidence when it can also return non-zero.

        Pinned straight from a markup string, not from a template: the shipped
        pages must stay JS-free, so the only way to prove the widened prefix list
        and the <script> check actually bite — and that the <main> region is
        really being entered rather than skipped — is to feed the probe the
        markers it claims to catch.
        """
        marked = (
            '<main id="main-content">'
            '<button onclick="steal()">x</button>'
            '<div hx-get="/products/receipts/" hx-target="#modal_root"></div>'
            '<div x-data="{}" @click="go()" :class="c" hx-on:click="f()"></div>'
            "<script>alert(1)</script>"
            "</main>"
            # outside the reviewed region, so deliberately not reported
            '<div x-data="{never: true}"></div>'
        )
        self.assertEqual(
            self.js_attribute_names(marked, within_main=True),
            ["onclick", "hx-get", "hx-target", "x-data", "@click", ":class",
             "hx-on:click", "script"],
        )
        # Task 3's whole-document mode is the same probe, minus the region: a
        # dialog fragment's x-data is still reported and a data-* attribute is
        # still not mistaken for an inline handler.
        self.assertEqual(
            self.js_attribute_names('<div x-data="{}" data-modal-close></div>'),
            ["x-data"],
        )
