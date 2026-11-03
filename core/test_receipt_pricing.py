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
from core.inventory import ReceiptLine, receive_stock
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
