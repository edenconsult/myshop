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
        self.bottle = Product.objects.create(
            name="Bottle Gargle", sku="BTL01", stock=3,
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
