"""Multi-line receipts and the selling prices they carry (design doc 2026-11-03).

One file for the whole feature: the service tests would otherwise sit in
core/test_inventory.py, which the backend lane holds, and the markup pins reuse
the probes core/test_batch_ui.py already paid for.
"""

import datetime as dt
import json
import re
import shutil
import subprocess
import unittest
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import migrations
from django.db.migrations.loader import MigrationLoader
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core.checkout import SaleLine, checkout
from core.inventory import (
    MAX_SELLING_PRICE,
    ReceiptLine,
    _normalize_receipt_lines,
    receive_stock,
)
from core.models import Product, StockBatch, StockReceipt, StockReceiptSource
from core.test_batch_ui import BatchUiTestCase


def compile_js(test_case, html, **shapes):
    """Compile every rendered inline handler with the real JS engine.

    ``x-data`` is an expression, an ``@click`` handler binds ``$event`` and an
    ``hx-on::…`` handler binds ``event``. A value that compiles under one shape
    and not another is the ReferenceError class this repo has already paid for
    twice, and only node can see it.
    """
    if not shutil.which("node"):
        raise unittest.SkipTest("node is not on PATH")
    scripts = {
        "expression": "new Function('return ' + d.body)",
        "alpine": "new Function('$event', d.body)",
        "htmx": "new Function('event', d.body)",
    }
    for attribute, shape in shapes.items():
        for value in test_case.attribute_values(html, attribute):
            result = subprocess.run(
                ["node", "-e",
                 "const d=JSON.parse(require('fs').readFileSync(0,'utf8')); "
                 + scripts[shape] + ";"],
                input=json.dumps({"body": value}),
                capture_output=True,
                text=True,
            )
            test_case.assertEqual(
                result.returncode,
                0,
                f"{attribute} fails to compile as {shape}: {result.stderr.strip()}",
            )


def _normalize(lines):
    """The service's own line normalisation, without touching the database."""
    return _normalize_receipt_lines(lines)


class ReceiptPricingTestCase(BatchUiTestCase):
    """Fixture: a 18.00 priced product from the base case, plus a second product."""

    def setUp(self):
        super().setUp()
        # stock 0, not 3: receive_stock runs _assert_product_stock on every
        # product a line names, and a product whose stock column disagrees with
        # the batches it has (here: none) is refused as drift. Only a shelf count
        # of zero with no batches is bookable without first booking an opening.
        self.bottle = Product.objects.create(
            name="Bottle Gargle", sku="BTL01", stock=0,
            cost=Decimal("4.00"), price=Decimal("7.50"),
            profit_rate=Decimal("0.47"),
        )

    def book(self, lines, *, key=None, source=StockReceiptSource.PURCHASE, reason=""):
        return receive_stock(
            actor=self.admin,
            request_key=key or uuid.uuid4(),
            lines=lines,
            received_at=timezone.now(),
            source=source,
            reason=reason,
        )

    def booked_receipts(self):
        """Every receipt this feature booked, and nothing the cutover left behind.

        Migration 0015 plants one OPENING receipt in every database it builds --
        test data included -- so an absolute StockReceipt.objects.count() is
        always one too many. test_inventory.py:148 made the same exclusion.
        """
        return StockReceipt.objects.exclude(source=StockReceiptSource.OPENING)


class PriceTrailColumnsTests(ReceiptPricingTestCase):
    def test_both_price_columns_are_nullable_two_place_decimals(self):
        for name in ("price_before", "price_applied"):
            field = StockBatch._meta.get_field(name)
            self.assertTrue(field.null, name)
            # blank follows the nullable columns already on this model (actor,
            # request_key); neither field is ever rendered by a ModelForm.
            self.assertTrue(field.blank, name)
            self.assertEqual(field.decimal_places, 2, name)
            self.assertEqual(field.max_digits, 10, name)

    def test_the_columns_exist_in_the_database(self):
        receipt = self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"))])
        batch = StockBatch.objects.get(receipt=receipt)
        StockBatch.objects.filter(pk=batch.pk).update(
            price_before=Decimal("18.00"), price_applied=Decimal("20.00")
        )
        batch.refresh_from_db()
        self.assertEqual(batch.price_before, Decimal("18.00"))
        self.assertEqual(batch.price_applied, Decimal("20.00"))

    def test_exactly_one_additive_migration_adds_both_columns(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        found = [
            (name, migration)
            for (app, name), migration in loader.disk_migrations.items()
            if app == "core"
            and any(
                # model_name is how a migration spells a model -- lowercase --
                # and AddField carries one field on .name/.field, unlike
                # CreateModel's .fields list.
                isinstance(op, migrations.AddField)
                and op.model_name == "stockbatch"
                and op.name in {"price_before", "price_applied"}
                for op in migration.operations
            )
        ]
        self.assertEqual(len(found), 1, f"expected one trail migration, got {[n for n, _ in found]}")
        _name, migration = found[0]
        for op in migration.operations:
            self.assertIsInstance(op, migrations.AddField, "the trail migration must be additive only")


class SellingPriceValidationTests(ReceiptPricingTestCase):
    def test_no_price_means_no_change_and_stays_none(self):
        line = _normalize([ReceiptLine(self.product.pk, 4, Decimal("10.00"))])[0]
        self.assertIsNone(line.selling_price)

    def test_a_zero_price_is_refused_naming_the_line(self):
        with self.assertRaises(ValidationError) as caught:
            self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("0.00"))])
        self.assertEqual(list(caught.exception.error_dict), ["lines[1].selling_price"])

    def test_a_price_above_the_checkout_cap_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            self.book(
                [ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("10000.00"))]
            )
        self.assertIn(str(MAX_SELLING_PRICE), caught.exception.messages[0])

    def test_a_price_with_three_decimal_places_is_refused(self):
        with self.assertRaises(ValidationError):
            self.book(
                [ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("19.999"))]
            )

    def test_a_price_is_quantised_to_two_places(self):
        line = _normalize([ReceiptLine(self.product.pk, 4, Decimal("10.00"), "19.9")])[0]
        self.assertEqual(line.selling_price, Decimal("19.90"))

    def test_replaying_a_key_with_a_different_price_is_refused(self):
        key = uuid.uuid4()
        self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"))], key=key)
        with self.assertRaises(ValidationError) as caught:
            self.book(
                [ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00"))],
                key=key,
            )
        self.assertIn("already used for different data", str(caught.exception))

    def test_replaying_a_key_with_the_same_price_returns_the_same_receipt(self):
        key = uuid.uuid4()
        lines = [ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00"))]
        first = self.book(lines, key=key)
        second = self.book(lines, key=key)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.booked_receipts().count(), 1)

    def test_the_service_ceiling_still_refuses_a_five_hundred_and_first_line(self):
        """500 lines is the service's own boundary and it fires before any query;
        the dialog's 50-row cap is a usability limit, not this one."""
        lines = [
            ReceiptLine(self.product.pk, 1, Decimal("1.00"), Decimal("2.00"))
            for _ in range(501)
        ]
        with self.assertRaises(ValidationError) as caught:
            _normalize(lines)
        self.assertIn("500", caught.exception.messages[0])
        self.assertEqual(self.booked_receipts().count(), 0)


class PriceWriteTests(ReceiptPricingTestCase):
    def test_three_lines_book_one_receipt_three_batches_and_move_three_shelf_counts(self):
        balm = self.product
        receipt = self.book(
            [
                ReceiptLine(balm.pk, 4, Decimal("10.00")),
                ReceiptLine(self.bottle.pk, 6, Decimal("5.00"), Decimal("9.00")),
                ReceiptLine(balm.pk, 1, Decimal("11.00")),
            ]
        )
        self.assertEqual(self.booked_receipts().count(), 1)
        batches = list(StockBatch.objects.filter(receipt=receipt).order_by("line_number"))
        self.assertEqual([b.line_number for b in batches], [1, 2, 3])
        self.assertEqual([b.quantity_received for b in batches], [4, 6, 1])
        balm.refresh_from_db()
        self.bottle.refresh_from_db()
        self.assertEqual((balm.stock, balm.cost), (5, Decimal("11.00")))
        self.assertEqual((self.bottle.stock, self.bottle.price), (6, Decimal("9.00")))

    def test_a_priceless_line_leaves_both_trail_columns_null(self):
        receipt = self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"))])
        batch = StockBatch.objects.get(receipt=receipt)
        self.assertIsNone(batch.price_before)
        self.assertIsNone(batch.price_applied)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("18.00"))

    def test_a_priced_line_writes_the_price_and_chains_the_trail(self):
        receipt = self.book(
            [ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00"))]
        )
        batch = StockBatch.objects.get(receipt=receipt)
        self.assertEqual(batch.price_before, Decimal("18.00"))
        self.assertEqual(batch.price_applied, Decimal("20.00"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("20.00"))

    def test_the_second_priced_line_of_a_product_starts_where_the_first_ended(self):
        receipt = self.book(
            [
                ReceiptLine(self.product.pk, 2, Decimal("10.00"), Decimal("20.00")),
                ReceiptLine(self.product.pk, 3, Decimal("12.00"), Decimal("25.00")),
            ]
        )
        first, second = StockBatch.objects.filter(receipt=receipt).order_by("line_number")
        self.assertEqual(
            (first.price_before, first.price_applied), (Decimal("18.00"), Decimal("20.00"))
        )
        self.assertEqual(
            (second.price_before, second.price_applied), (Decimal("20.00"), Decimal("25.00"))
        )
        self.product.refresh_from_db()
        self.assertEqual((self.product.price, self.product.cost), (Decimal("25.00"), Decimal("12.00")))

    def test_a_priced_line_leaves_unpriced_products_prices_alone(self):
        self.book(
            [
                ReceiptLine(self.product.pk, 2, Decimal("10.00"), Decimal("22.00")),
                ReceiptLine(self.bottle.pk, 2, Decimal("5.00")),
            ]
        )
        self.bottle.refresh_from_db()
        self.assertEqual(self.bottle.price, Decimal("7.50"))

    def test_the_applied_price_is_the_one_checkout_charges(self):
        self.book([ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00"))])
        # the cart still holds the OLD price: the register is refused, not re-priced
        with self.assertRaises(ValidationError) as caught:
            checkout(
                actor=self.admin,
                request_key=uuid.uuid4(),
                lines=[SaleLine(self.product.pk, 2, Decimal("36.00"))],
            )
        self.assertIn("The cart price changed", str(caught.exception))
        checkout(
            actor=self.admin,
            request_key=uuid.uuid4(),
            lines=[SaleLine(self.product.pk, 2, Decimal("40.00"))],
        )

    def test_one_bad_line_among_three_leaves_no_receipt_no_batch_and_no_price(self):
        self.product.refresh_from_db()
        before = (StockReceipt.objects.count(), StockBatch.objects.count(), self.product.price)
        with self.assertRaises(ValidationError):
            self.book(
                [
                    ReceiptLine(self.product.pk, 4, Decimal("10.00"), Decimal("20.00")),
                    ReceiptLine(self.bottle.pk, 6, Decimal("5.00")),
                    ReceiptLine(self.product.pk, 1, Decimal("11.00"), Decimal("0.00")),
                ]
            )
        self.product.refresh_from_db()
        self.assertEqual(
            before, (StockReceipt.objects.count(), StockBatch.objects.count(), self.product.price)
        )

    def test_a_drift_on_the_third_product_refuses_the_whole_receipt(self):
        Product.objects.filter(pk=self.bottle.pk).update(stock=99)
        with self.assertRaises(ValidationError) as caught:
            self.book(
                [
                    ReceiptLine(self.product.pk, 4, Decimal("10.00")),
                    ReceiptLine(self.bottle.pk, 6, Decimal("5.00"), Decimal("9.00")),
                ]
            )
        self.assertIn(self.bottle.name, str(caught.exception))
        self.assertEqual(self.booked_receipts().count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("18.00"))


class ReceiptProductSearchTests(ReceiptPricingTestCase):
    def url(self):
        return reverse("core:receipt-product-options")

    def test_the_search_finds_by_name_and_by_sku(self):
        for term in ("Shea", "SHB01"):
            response = self.client.get(self.url(), {"q": term})
            self.assertEqual(response.status_code, 200, term)
            self.assertContains(response, 'data-product-name="Shea Repair Balm"')
            self.assertNotContains(response, "Bottle Gargle")

    def test_a_blank_term_still_offers_the_first_products(self):
        response = self.client.get(self.url())
        self.assertContains(response, "Shea Repair Balm")

    def test_no_match_says_so_instead_of_returning_an_empty_box(self):
        response = self.client.get(self.url(), {"q": "zzz-nothing"})
        self.assertContains(response, "Nothing in the catalogue matches")

    def test_the_list_is_capped_at_twenty_products(self):
        for index in range(25):
            Product.objects.create(
                name=f"Cap filler {index}", stock=1, cost=Decimal("1.00"),
                price=Decimal("2.00"), profit_rate=Decimal("0.50"),
            )
        html = self.client.get(self.url(), {"q": "Cap filler"}).content.decode()
        self.assertEqual(
            sum(
                1
                for _tag, attributes in self.elements_with_attributes(html)
                if "data-product-id" in attributes
            ),
            20,
        )

    def test_the_cashier_and_the_anonymous_visitor_are_turned_away(self):
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_a_product_name_never_reaches_a_js_attribute(self):
        """Names belong in data-*, because a name is exactly what breaks a JS literal."""
        awkward = Product.objects.create(
            name='O\'Neil "Reserve" Balm', sku="ONE1", stock=1,
            cost=Decimal("1.00"), price=Decimal("2.00"), profit_rate=Decimal("0.50"),
        )
        response = self.client.get(self.url(), {"q": "Reserve"})
        html = response.content.decode()
        for _tag, attributes in self.elements_with_attributes(html):
            for name, value in attributes.items():
                if name.startswith(self.JS_ATTRIBUTE_PREFIXES):
                    self.assertNotIn("Reserve", value)
        # html.parser unescapes attribute values, so this is what the DOM sees:
        # the name verbatim, quotes and all -- inside data-*, never a directive.
        self.assertEqual(
            [
                attributes["data-product-name"]
                for _tag, attributes in self.elements_with_attributes(html)
                if "data-product-name" in attributes
            ],
            [awkward.name],
        )
        compile_js(self, html, **{"@click": "alpine"})


class ReceiptDialogTests(ReceiptPricingTestCase):
    def dialog(self, product_id=None):
        url = reverse("core:receive-stock-question")
        if product_id:
            url = f"{url}?product_id={product_id}"
        return self.client.get(url)

    def test_opening_the_dialog_seeds_one_blank_line(self):
        response = self.dialog()
        html = response.content.decode()
        self.assertEqual(html.count('class="receipt-row '), 1)
        for name in ("line_product_id[]", "line_units[]", "line_unit_cost[]",
                     "line_selling_price[]"):
            self.assertIn(f'name="{name}"', html)
        self.assertIn('name="request_key"', html)
        self.assertEqual(html.count("data-autofocus"), 1)

    def test_a_product_id_prefers_that_product_and_says_so(self):
        html = self.dialog(self.bottle.pk).content.decode()
        self.assertIn("Bottle Gargle", html)
        self.assertEqual(html.count("data-autofocus"), 1)
        self.assertEqual(html.count('class="receipt-row '), 1)
        # the search box is answered, so focus must sit further along the row
        searches = [
            attributes
            for _tag, attributes in self.elements_with_attributes(html)
            if "receipt-row-search" in attributes.get("class", "")
        ]
        self.assertEqual(len(searches), 1)
        self.assertNotIn("data-autofocus", searches[0])

    def test_the_prefill_defaults_cost_from_the_catalogue_and_leaves_price_blank(self):
        response = self.dialog(self.bottle.pk)
        self.assertContains(response, 'value="4.00"')
        self.assertContains(response, 'placeholder="no change"')
        self.assertContains(response, f'value="{self.bottle.pk}"')

    def test_an_unresolvable_product_id_still_opens_a_blank_dialog(self):
        response = self.dialog(uuid.uuid4())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Bottle Gargle", response.content.decode())

    def test_the_dialog_carries_exactly_one_parseable_x_data(self):
        html = self.dialog().content.decode()
        scopes = self.attribute_values(html, "x-data")
        self.assertEqual(len(scopes), 1, "a dialog with two Alpine scopes has two ideas about the rows")
        compile_js(self, html, **{"x-data": "expression"})

    def test_no_js_attribute_carries_a_raw_double_quote(self):
        html = self.dialog().content.decode()
        for _tag, attributes in self.elements_with_attributes(html):
            for name, value in attributes.items():
                if name.startswith(self.JS_ATTRIBUTE_PREFIXES):
                    self.assertNotIn('"', value, f"{name} would close its own attribute")

    def test_every_handler_compiles_with_the_library_that_binds_it(self):
        """htmx binds 'event', Alpine binds '$event' -- mixing them is a ReferenceError."""
        html = self.dialog().content.decode()
        compile_js(
            self,
            html,
            **{
                "@click": "alpine",
                "@input": "alpine",
                "x-text": "expression",
                "x-show": "expression",
                "x-init": "expression",
                "hx-on::after-request": "htmx",
            },
        )

    def test_the_blank_line_endpoint_returns_one_row_with_no_product(self):
        response = self.client.get(reverse("core:receipt-line-blank"))
        html = response.content.decode()
        self.assertEqual(html.count('class="receipt-row '), 1)
        self.assertIn('name="line_product_id[]"', html)
        self.assertIn('value=""', html)
        self.assertContains(response, "Name or code")

    def test_the_cashier_cannot_open_either_endpoint(self):
        self.client.force_login(self.cashier)
        self.assertEqual(self.dialog().status_code, 302)
        self.assertEqual(
            self.client.get(reverse("core:receipt-line-blank")).status_code, 302
        )
