import json
import os
import re
import shutil
import tempfile
import datetime as dt
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from authapp.models import Account
from core.models import Order, OrderItem, Product, ProductCategory
from core.views import report_context, report_range


def png_upload(name="glow.png", width=8, height=8):
    """A real PNG, so content-type sniffing has something honest to read."""
    buffer = BytesIO()
    Image.new("RGB", (width, height), (11, 122, 91)).save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


def jpeg_upload(name="serum.jpg", width=8, height=8):
    buffer = BytesIO()
    Image.new("RGB", (width, height), (200, 120, 160)).save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/jpeg")


def product_form_data(product=None):
    """Every field the dialog posts, with an optional image left out."""
    data = {
        "name": product.name if product else "Shea Repair Balm",
        "sku": product.sku if product else "SHB01",
        "category": product.category if product else "skincare",
        "stock": product.stock if product else 12,
        "cost": product.cost if product else Decimal("9.00"),
        "price": product.price if product else Decimal("18.00"),
        "low_stock_threshold": (
            product.low_stock_threshold if product else 5
        ),
    }
    return data


class LedgerTestCase(TestCase):
    """Shared fixtures for the orders-ledger tests."""

    def setUp(self):
        self.admin = Account.objects.create_user(
            username="aba", password="pw", user_type="ADMIN"
        )
        self.kwame = Account.objects.create_user(
            username="kwame", password="pw", user_type="ADMIN"
        )
        self.elixir = Product.objects.create(
            name="Hydrating Glow Elixir",
            sku="ELX01",
            stock=50,
            cost=Decimal("60.00"),
            price=Decimal("140.00"),
            profit_rate=Decimal("0.57"),
        )
        self.lipstick = Product.objects.create(
            name="Velvet Matte Lipstick",
            sku="LIP01",
            stock=50,
            cost=Decimal("40.00"),
            price=Decimal("105.00"),
            profit_rate=Decimal("0.62"),
        )
        self.client.force_login(self.admin)

    def make_order(self, code, user, items, hours_ago=0, days_ago=0):
        """items: list of (product, qty) tuples."""
        order = Order.objects.create(user=user, code=code)
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                product=product,
                qty_bought=qty,
                paid_amount=product.price * qty,
            )
            for product, qty in items
        )
        Order.objects.filter(pk=order.pk).update(
            overall_amount_paid=sum(
                (product.price * qty for product, qty in items), Decimal("0.00")
            )
        )
        if hours_ago or days_ago:
            Order.objects.filter(pk=order.pk).update(
                created=timezone.now()
                - timedelta(days=days_ago)
                - timedelta(hours=hours_ago)
            )
        return order


class OrdersLedgerPageTests(LedgerTestCase):
    def test_anonymous_is_redirected(self):
        self.client.logout()
        response = self.client.get(reverse("core:orders"), {"view": "orders"})
        self.assertEqual(response.status_code, 302)

    def test_a_receipt_deep_link_seeds_the_search_and_drops_today(self):
        """The reports ledger links here with ?q=<code>, so the shell has to
        start from that search across the whole history, not from today."""
        self.make_order("DEEP01", self.admin, [(self.elixir, 1)], days_ago=5)

        response = self.client.get(
            reverse("core:orders"), {"view": "orders", "q": "DEEP01"}
        )

        self.assertContains(response, "q: 'DEEP01'")
        self.assertContains(response, "date: ''")

    def test_page_renders_ledger_with_today_kpis(self):
        self.make_order("TODAY1", self.admin, [(self.elixir, 2)])  # 280.00
        self.make_order("YSTDY1", self.kwame, [(self.lipstick, 1)], hours_ago=30)

        response = self.client.get(reverse("core:orders"), {"view": "orders"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/orders/orders_ledger.html")

        kpi = response.context["kpi"]
        self.assertEqual(kpi["order_count"], 1)
        self.assertEqual(kpi["revenue"], Decimal("280.00"))
        self.assertEqual(kpi["cashier_count"], 1)
        # 2 * (140 - 60)
        self.assertEqual(kpi["profit"], Decimal("160.00"))
        self.assertEqual(kpi["avg_items"], Decimal("2"))

    def test_kpis_ignore_yesterday(self):
        self.make_order("YSTDY1", self.admin, [(self.lipstick, 1)], hours_ago=30)
        response = self.client.get(reverse("core:orders"), {"view": "orders"})
        kpi = response.context["kpi"]
        self.assertEqual(kpi["order_count"], 0)
        self.assertEqual(kpi["revenue"], Decimal("0.00"))
        self.assertIsNone(kpi["aov"])


class OrdersLedgerPartialTests(LedgerTestCase):
    url_name = "core:orders-ledger"

    def test_lists_newest_first_with_basket_annotation(self):
        first = self.make_order("OLD001", self.admin, [(self.elixir, 1)], hours_ago=2)
        second = self.make_order(
            "NEW001", self.kwame, [(self.lipstick, 1), (self.elixir, 2)]
        )
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/orders/ledger_table.html")
        rows = list(response.context["page_obj"].object_list)
        self.assertEqual([o.code for o in rows], ["NEW001", "OLD001"])
        newest = rows[0]
        self.assertEqual(newest.items_count, 2)
        # first_item is deterministic: alphabetically first line of the basket
        self.assertEqual(newest.first_item, "Hydrating Glow Elixir")

    def test_search_filters_by_code(self):
        self.make_order("ABC123", self.admin, [(self.elixir, 1)])
        self.make_order("XYZ789", self.admin, [(self.elixir, 1)])
        response = self.client.get(reverse(self.url_name), {"q": "abc"})
        rows = list(response.context["page_obj"].object_list)
        self.assertEqual([o.code for o in rows], ["ABC123"])

    def test_cashier_filter_uses_username(self):
        self.make_order("ABA001", self.admin, [(self.elixir, 1)])
        self.make_order("KWA001", self.kwame, [(self.elixir, 1)])
        response = self.client.get(reverse(self.url_name), {"users": "kwame"})
        rows = list(response.context["page_obj"].object_list)
        self.assertEqual([o.code for o in rows], ["KWA001"])

    def test_date_filter_excludes_other_days_and_empty_shows_all(self):
        self.make_order("TODAYX", self.admin, [(self.elixir, 1)])
        self.make_order("PAST01", self.admin, [(self.elixir, 1)], hours_ago=30)

        today = timezone.localdate().isoformat()
        response = self.client.get(reverse(self.url_name), {"date": today})
        rows = list(response.context["page_obj"].object_list)
        self.assertEqual([o.code for o in rows], ["TODAYX"])

        response = self.client.get(reverse(self.url_name), {"date": ""})
        self.assertEqual(response.context["page_obj"].paginator.count, 2)

    def test_pagination_bounds(self):
        for i in range(12):
            self.make_order(f"C{i:04d}", self.admin, [(self.elixir, 1)])
        response = self.client.get(reverse(self.url_name))
        paginator = response.context["page_obj"].paginator
        self.assertEqual(paginator.num_pages, 2)
        self.assertEqual(len(response.context["page_obj"]), 10)

        response = self.client.get(reverse(self.url_name), {"p": 2})
        self.assertEqual(len(response.context["page_obj"]), 2)

        # out-of-range pages clamp instead of 404
        response = self.client.get(reverse(self.url_name), {"p": 99})
        self.assertTrue(response.context["page_obj"].number == 2)

    def test_invalid_date_is_ignored(self):
        self.make_order("GOOD0A", self.admin, [(self.elixir, 1)])
        response = self.client.get(reverse(self.url_name), {"date": "not-a-date"})
        self.assertEqual(response.status_code, 200)
        rows = list(response.context["page_obj"].object_list)
        self.assertEqual([o.code for o in rows], ["GOOD0A"])


class OrdersLedgerCsvTests(LedgerTestCase):
    def test_csv_export_matches_filters(self):
        self.make_order("CSV001", self.admin, [(self.elixir, 2)])
        self.make_order("OTH001", self.kwame, [(self.lipstick, 1)])

        response = self.client.get(
            reverse("core:orders-export-csv"), {"users": "aba"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment", response["Content-Disposition"])

        body = response.content.decode("utf-8")
        lines = [line for line in body.splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)  # header + one order
        self.assertIn("CSV001", lines[1])
        self.assertNotIn("OTH001", body)


class OrderInspectorPartialTests(LedgerTestCase):
    def test_view_order_partial_renders(self):
        order = self.make_order("INSP01", self.admin, [(self.elixir, 1)])
        response = self.client.get(
            reverse("core:view-order", args=(order.id, 1))
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/orders/order_details.html")
        self.assertContains(response, "INSP01")
        self.assertContains(response, "Hydrating Glow Elixir")


class ProductImageUploadTests(LedgerTestCase):
    """Uploads land in a throwaway MEDIA_ROOT so runs never touch ./media."""

    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp(prefix="myshop-test-media-")
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.addCleanup(shutil.rmtree, self.media_root, True)
        self.addCleanup(self.media_override.disable)

    def test_new_product_saves_uploaded_image(self):
        response = self.client.post(
            reverse("core:add-product"),
            {**product_form_data(), "image": png_upload()},
        )
        self.assertEqual(response.status_code, 200)

        product = Product.objects.get(name="Shea Repair Balm")
        self.assertTrue(product.image)
        self.assertIn("glow", product.image.name)

    def test_edit_without_touching_image_keeps_the_existing_file(self):
        self.elixir.image = png_upload("elixir.png")
        self.elixir.save()
        stored_name = self.elixir.image.name

        response = self.client.post(
            reverse("core:update-product", args=(self.elixir.id,)),
            product_form_data(self.elixir),
        )
        self.assertEqual(response.status_code, 200)

        self.elixir.refresh_from_db()
        self.assertEqual(self.elixir.image.name, stored_name)

    def test_image_clear_checkbox_detaches_the_file(self):
        self.elixir.image = png_upload("lipstick.png")
        self.elixir.save()

        response = self.client.post(
            reverse("core:update-product", args=(self.elixir.id,)),
            {**product_form_data(self.elixir), "image-clear": "on"},
        )
        self.assertEqual(response.status_code, 200)

        self.elixir.refresh_from_db()
        self.assertFalse(self.elixir.image)

    def test_add_dialog_offers_an_image_input(self):
        response = self.client.get(reverse("core:add-product"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="image"')
        # an empty src would make the browser re-request the page itself
        self.assertNotContains(response, 'src=""')

    def test_edit_dialog_offers_to_remove_the_existing_image(self):
        self.elixir.image = png_upload("elixir.png")
        self.elixir.save()

        response = self.client.get(
            reverse("core:update-product", args=(self.elixir.id,))
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="image-clear"')
        self.assertContains(response, self.elixir.image.url)
        # the widget attrs and the template must not both emit accept
        self.assertEqual(
            response.content.decode().count('accept="image/*"'), 1
        )

    def test_oversized_image_is_downscaled_before_it_is_stored(self):
        response = self.client.post(
            reverse("core:add-product"),
            {**product_form_data(), "image": jpeg_upload("huge.jpg", 1600, 1000)},
        )
        self.assertEqual(response.status_code, 200)

        product = Product.objects.get(name="Shea Repair Balm")
        with Image.open(product.image.path) as stored:
            self.assertEqual(max(stored.size), 512)
            self.assertEqual(stored.format, "JPEG")

    def test_a_large_transparent_png_keeps_its_alpha_when_resized(self):
        buffer = BytesIO()
        Image.new("RGBA", (900, 700), (255, 0, 0, 128)).save(buffer, format="PNG")
        upload = SimpleUploadedFile(
            "badge.png", buffer.getvalue(), content_type="image/png"
        )

        response = self.client.post(
            reverse("core:add-product"),
            {**product_form_data(), "image": upload},
        )
        self.assertEqual(response.status_code, 200)

        product = Product.objects.get(name="Shea Repair Balm")
        with Image.open(product.image.path) as stored:
            self.assertEqual(max(stored.size), 512)
            self.assertEqual(stored.format, "PNG")
            self.assertEqual(stored.getpixel((0, 0))[3], 128)

    def test_file_over_the_size_cap_is_rejected(self):
        # random noise does not compress, so this is a genuinely heavy PNG
        noise = os.urandom(1500 * 1500 * 3)
        heavy = Image.frombytes("RGB", (1500, 1500), noise)
        buffer = BytesIO()
        heavy.save(buffer, format="PNG")
        upload = SimpleUploadedFile(
            "heavy.png", buffer.getvalue(), content_type="image/png"
        )
        self.assertGreater(upload.size, 5 * 1024 * 1024)

        response = self.client.post(
            reverse("core:add-product"),
            {**product_form_data(), "image": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(name="Shea Repair Balm").exists())

    def test_non_image_bytes_are_rejected(self):
        fake = SimpleUploadedFile(
            "notes.png", b"not a picture at all", content_type="image/png"
        )

        response = self.client.post(
            reverse("core:add-product"),
            {**product_form_data(), "image": fake},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(name="Shea Repair Balm").exists())

    def test_ledger_row_shows_the_photo_when_there_is_one(self):
        self.elixir.image = png_upload("elixir.png")
        self.elixir.save()

        response = self.client.get(reverse("core:load-products"), {"s": "Elixir"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<img')
        self.assertContains(response, self.elixir.image.url)
        self.assertContains(response, 'alt="Hydrating Glow Elixir"')

    def test_ledger_row_falls_back_to_the_monogram_without_a_photo(self):
        response = self.client.get(reverse("core:load-products"), {"s": "Elixir"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<img")
        self.assertContains(response, "HY")

    def test_pos_tile_shows_the_photo_when_there_is_one(self):
        self.lipstick.image = png_upload("lipstick.png")
        self.lipstick.save()

        response = self.client.get(reverse("core:load-orders-products"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lipstick.image.url)


class ReportRangeTests(TestCase):
    """report_range turns the filter bar's query string into a concrete
    inclusive [start, end] pair of local dates."""

    def setUp(self):
        self.today = timezone.localdate()

    def test_nothing_selected_is_today(self):
        rng = report_range({})
        self.assertEqual((rng["start"], rng["end"]), (self.today, self.today))
        self.assertEqual(rng["preset"], "today")

    def test_yesterday_shifts_both_ends(self):
        yesterday = self.today - timedelta(days=1)
        rng = report_range({"preset": "yesterday"})
        self.assertEqual((rng["start"], rng["end"]), (yesterday, yesterday))

    def test_last_seven_days_includes_today(self):
        rng = report_range({"preset": "7d"})
        self.assertEqual(rng["start"], self.today - timedelta(days=6))
        self.assertEqual(rng["end"], self.today)

    def test_month_to_date_starts_on_the_first(self):
        rng = report_range({"preset": "mtd"})
        self.assertEqual(rng["start"], self.today.replace(day=1))
        self.assertEqual(rng["end"], self.today)

    def test_custom_dates_are_used_as_given(self):
        rng = report_range(
            {"preset": "custom", "start": "2026-03-02", "end": "2026-03-09"}
        )
        self.assertEqual(rng["start"], dt.date(2026, 3, 2))
        self.assertEqual(rng["end"], dt.date(2026, 3, 9))
        self.assertEqual(rng["preset"], "custom")

    def test_a_reversed_custom_range_is_swapped(self):
        rng = report_range(
            {"preset": "custom", "start": "2026-03-09", "end": "2026-03-02"}
        )
        self.assertEqual((rng["start"], rng["end"]), (dt.date(2026, 3, 2), dt.date(2026, 3, 9)))

    def test_unparseable_custom_dates_fall_back_to_today(self):
        rng = report_range({"preset": "custom", "start": "yesterday-ish", "end": ""})
        self.assertEqual((rng["start"], rng["end"]), (self.today, self.today))
        self.assertEqual(rng["preset"], "today")

    def test_an_unknown_preset_falls_back_to_today(self):
        rng = report_range({"preset": "last_century"})
        self.assertEqual(rng["preset"], "today")

    def test_the_previous_period_is_the_same_length_immediately_before(self):
        rng = report_range({"preset": "7d"})
        self.assertEqual(rng["previous_start"], self.today - timedelta(days=13))
        self.assertEqual(rng["previous_end"], self.today - timedelta(days=7))


class ReportAggregatesTests(LedgerTestCase):
    """Every number on the reports page has to come from these aggregates."""

    def setUp(self):
        super().setUp()
        Product.objects.filter(pk=self.elixir.pk).update(category="skincare")
        Product.objects.filter(pk=self.lipstick.pk).update(category="makeup")

    def context(self, **params):
        rng = report_range(params)
        return report_context(rng)

    def test_kpis_cover_only_the_selected_range(self):
        self.make_order("IN0001", self.admin, [(self.elixir, 2)])
        self.make_order("OUT001", self.kwame, [(self.lipstick, 3)], days_ago=2)

        kpi = self.context()["kpi"]
        self.assertEqual(kpi["order_count"], 1)
        self.assertEqual(kpi["units"], 2)
        self.assertEqual(kpi["revenue"], Decimal("280.00"))
        self.assertEqual(kpi["cost"], Decimal("120.00"))
        self.assertEqual(kpi["profit"], Decimal("160.00"))
        self.assertEqual(kpi["margin_pct"], Decimal("57.1"))
        self.assertEqual(kpi["cost_share_pct"], Decimal("42.9"))
        self.assertEqual(kpi["profit_multiplier"], Decimal("1.33"))
        self.assertEqual(kpi["aov"], Decimal("280.00"))

    def test_deltas_compare_the_previous_equal_length_period(self):
        self.make_order("TDY001", self.admin, [(self.elixir, 2)])  # 280.00
        self.make_order("YSD001", self.admin, [(self.lipstick, 1)], days_ago=1)  # 105

        kpi = self.context()["kpi"]
        self.assertEqual(kpi["previous_revenue"], Decimal("105.00"))
        # (280 - 105) / 105 * 100
        self.assertEqual(kpi["revenue_delta_pct"], Decimal("166.7"))
        # 2 units vs 1, and 160 profit vs 65
        self.assertEqual(kpi["units_delta_pct"], Decimal("100.0"))
        self.assertEqual(kpi["profit_delta_pct"], Decimal("146.2"))

    def test_delta_is_none_when_the_previous_period_is_empty(self):
        self.make_order("TDY002", self.admin, [(self.elixir, 1)])

        kpi = self.context()["kpi"]
        self.assertIsNone(kpi["revenue_delta_pct"])
        self.assertEqual(kpi["previous_revenue"], Decimal("0.00"))

    def test_cashier_rows_split_the_revenue(self):
        self.make_order("ABA001", self.admin, [(self.elixir, 2)])  # 280
        self.make_order("KWA001", self.kwame, [(self.elixir, 2)])  # 280

        rows = self.context()["by_cashier"]
        self.assertEqual([row["orders"] for row in rows], [1, 1])
        self.assertEqual([row["revenue"] for row in rows], [Decimal("280.00")] * 2)
        self.assertEqual([row["share_pct"] for row in rows], [Decimal("50.0")] * 2)
        self.assertEqual(sum(row["share_pct"] for row in rows), Decimal("100.0"))

    def test_category_rows_report_units_and_share(self):
        self.make_order("CAT001", self.admin, [(self.elixir, 2)])  # 280 skincare
        self.make_order("CAT002", self.admin, [(self.lipstick, 1)])  # 105 makeup

        rows = self.context()["by_category"]
        self.assertEqual(
            [(row["label"], row["units"], row["revenue"]) for row in rows],
            [("Skincare", 2, Decimal("280.00")), ("Makeup", 1, Decimal("105.00"))],
        )
        self.assertEqual([row["share_pct"] for row in rows], [Decimal("72.7"), Decimal("27.3")])
        self.assertEqual(self.context()["categories_active"], 2)

    def test_top_sku_is_the_best_seller_by_units(self):
        self.make_order("TOP001", self.admin, [(self.elixir, 1)])
        self.make_order("TOP002", self.admin, [(self.lipstick, 4)])

        top = self.context()["top_sku"]
        self.assertEqual(top["name"], "Velvet Matte Lipstick")
        self.assertEqual(top["sku"], "LIP01")
        self.assertEqual(top["units"], 4)

    def test_an_empty_range_returns_zeros_not_errors(self):
        data = self.context()
        kpi = data["kpi"]
        self.assertEqual(kpi["order_count"], 0)
        self.assertEqual(kpi["revenue"], Decimal("0.00"))
        self.assertEqual(kpi["profit"], Decimal("0.00"))
        self.assertIsNone(kpi["aov"])
        self.assertIsNone(kpi["margin_pct"])
        self.assertEqual(data["by_cashier"], [])
        self.assertEqual(data["by_category"], [])
        self.assertIsNone(data["top_sku"])

    def test_a_cashier_filter_narrows_every_figure(self):
        self.make_order("FILT01", self.admin, [(self.elixir, 2)])
        self.make_order("FILT02", self.kwame, [(self.lipstick, 1)])

        rng = report_range({"users": self.kwame.username})
        data = report_context(rng)

        self.assertEqual(data["kpi"]["revenue"], Decimal("105.00"))
        self.assertEqual([row["username"] for row in data["by_cashier"]], ["kwame"])


class SalesReportScreenTests(LedgerTestCase):
    """The ?view=reports surface: shell, htmx body, ledger rows."""

    def test_page_renders_the_shell_with_todays_report(self):
        self.make_order("SCN001", self.admin, [(self.elixir, 2)])  # 280.00
        self.make_order("SCN002", self.kwame, [(self.lipstick, 1)], days_ago=9)

        response = self.client.get(reverse("core:orders"), {"view": "reports"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/orders/sales_reports.html")
        self.assertTemplateUsed(response, "core/orders/report_body.html")
        self.assertEqual(response.context["report"]["kpi"]["revenue"], Decimal("280.00"))
        self.assertEqual(response.context["report"]["kpi"]["order_count"], 1)

    def test_a_saleperson_is_turned_away(self):
        rep = Account.objects.create_user(
            username="rep", password="pw", user_type="SALEPERSON"
        )
        self.client.force_login(rep)
        for url in (
            reverse("core:orders"),
            reverse("core:sales-report"),
            reverse("core:sales-report-ledger"),
            reverse("core:sales-report-csv"),
            reverse("core:sales-report-pdf"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url, {"view": "reports"})
                self.assertEqual(response.status_code, 302)

    def test_the_screen_promises_no_tenders_and_no_z_report(self):
        response = self.client.get(reverse("core:orders"), {"view": "reports"})
        body = response.content.decode()

        for phrase in ("Tender", "Payment", "MoMo", "Z-Report", "Visa"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, body)

    def test_the_range_label_tells_the_truth_about_the_window(self):
        response = self.client.get(reverse("core:orders"), {"view": "reports"})
        today = timezone.localdate()

        self.assertContains(response, f"{today:%b} {today.day}, {today:%Y}")
        self.assertNotContains(response, "Daily Takings &amp; Tax Audited")

    def test_body_partial_reacts_to_the_preset(self):
        self.make_order("PRS001", self.admin, [(self.elixir, 1)])  # 140 today
        self.make_order("PRS002", self.admin, [(self.lipstick, 2)], days_ago=1)  # 210

        response = self.client.get(reverse("core:sales-report"), {"preset": "yesterday"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/orders/report_body.html")
        self.assertEqual(response.context["report"]["kpi"]["revenue"], Decimal("210.00"))

    def test_cashier_filter_narrows_the_ledger_rows(self):
        self.make_order("CFR001", self.admin, [(self.elixir, 1)])
        self.make_order("CFR002", self.kwame, [(self.lipstick, 1)])

        response = self.client.get(
            reverse("core:sales-report-ledger"), {"users": "kwame"}
        )
        codes = [order.code for order in response.context["page_obj"]]
        self.assertEqual(codes, ["CFR002"])

    def test_ledger_rows_carry_units_cost_and_profit(self):
        self.make_order("LNCH01", self.admin, [(self.elixir, 2)])  # 280 / 120 / 160

        response = self.client.get(reverse("core:sales-report-ledger"))
        body = response.content.decode()

        self.assertTemplateUsed(response, "core/orders/report_ledger_rows.html")
        row = next(
            order
            for order in response.context["page_obj"]
            if order.code == "LNCH01"
        )
        self.assertEqual(row.units, 2)
        self.assertEqual(row.cost_outlay, Decimal("120.00"))
        self.assertEqual(row.line_profit, Decimal("160.00"))
        self.assertEqual(row.items_count, 1)
        self.assertIn("ELX01", body)
        self.assertIn("160.00", body)

    def test_ledger_search_filters_by_receipt_code(self):
        self.make_order("SRCH01", self.admin, [(self.elixir, 1)])
        self.make_order("OTHER1", self.admin, [(self.elixir, 1)])

        response = self.client.get(reverse("core:sales-report-ledger"), {"q": "srch"})
        codes = [order.code for order in response.context["page_obj"]]
        self.assertEqual(codes, ["SRCH01"])

    def test_ledger_paginates_at_the_shared_page_size(self):
        for i in range(12):
            self.make_order(f"PG{i:04d}", self.admin, [(self.elixir, 1)])

        response = self.client.get(reverse("core:sales-report-ledger"))
        self.assertEqual(len(response.context["page_obj"]), 10)
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 2)

    def test_an_empty_range_renders_the_no_sales_state(self):
        response = self.client.get(reverse("core:sales-report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No sales in this range")
        self.assertContains(response, "GH₵ 0.00")

    def test_every_tag_in_the_body_renders(self):
        """A tag or comment split across lines is not one: Django's lexer needs
        {% %}, {{ }} and {# #} on a single line, or the source ships to the
        browser as text."""
        self.make_order("KPI001", self.admin, [(self.elixir, 2)])  # 280.00

        body = self.client.get(reverse("core:sales-report")).content.decode()

        for marker in ("{%", "{{", "{#"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, body)
        for label in ("Products Sold", "Gross Revenue", "Cost Outlay", "Realized Profit"):
            with self.subTest(label=label):
                self.assertIn(label, body)
        self.assertIn("GH₵ 280.00", body)

    def test_the_ledger_rows_render_no_raw_template_source(self):
        self.make_order("KPI002", self.admin, [(self.elixir, 2)])

        body = self.client.get(reverse("core:sales-report-ledger")).content.decode()

        for marker in ("{%", "{{", "{#"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, body)
        self.assertIn("Cost Outlay", body)
        self.assertIn("+GH₵ 160.00", body)

    def test_a_broken_range_still_renders(self):
        for params in ({"preset": "custom"}, {"preset": "nonsense"}, {"p": "abc"}):
            with self.subTest(**params):
                response = self.client.get(reverse("core:sales-report"), params)
                self.assertEqual(response.status_code, 200)


class SalesReportExportTests(LedgerTestCase):
    def test_csv_respects_the_range_and_the_cashier(self):
        self.make_order("EXE001", self.admin, [(self.elixir, 2)])
        self.make_order("EXE002", self.kwame, [(self.lipstick, 1)])
        self.make_order("EXE003", self.admin, [(self.lipstick, 1)], days_ago=20)

        response = self.client.get(
            reverse("core:sales-report-csv"), {"users": "aba"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        body = response.content.decode("utf-8")
        lines = [line for line in body.splitlines() if line.strip()]

        self.assertEqual(lines[0], "S/No,Receipt,Date,Time,Cashier,Units,Cost,Total,Profit")
        self.assertEqual(len(lines), 2)  # only today's aba receipt is in range
        self.assertIn("EXE001", lines[1])
        self.assertNotIn("EXE002", body)
        self.assertNotIn("EXE003", body)

    def test_pdf_uses_the_same_range_as_the_screen(self):
        self.make_order("PDF001", self.admin, [(self.elixir, 2)])

        response = self.client.get(reverse("core:sales-report-pdf"), {"preset": "today"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTemplateUsed(response, "core/orders/prints/all_reports.html")
        self.assertIn(b"%PDF", response.content[:5])


class LedgerStockViewTests(LedgerTestCase):
    """The tab bar pins ?status in its own URL while hx-include also submits the
    stock select, so the two values arrive in one request and only the last one
    is ever read."""

    def setUp(self):
        super().setUp()
        self.kohl = Product.objects.create(
            name="Kohl Eye Pencil",
            sku="KHL01",
            stock=3,
            low_stock_threshold=5,
            cost=Decimal("12.00"),
            price=Decimal("30.00"),
            profit_rate=Decimal("0.60"),
        )

    def partial(self, **params):
        query = {"l": 10, "p": 1, **params}
        return self.client.get(reverse("core:load-products"), query).content.decode()

    def tab_anchors(self, body, wanted_status):
        return [
            anchor
            for anchor in re.findall(r"<a\b[^>]*>", body)
            if 'hx-include="#ledger-filters"' in anchor
            and f"status={wanted_status}" in anchor
        ]

    def test_alert_status_narrows_the_ledger_to_at_or_below_threshold(self):
        body = self.partial(status="alert")

        self.assertIn("Kohl Eye Pencil", body)
        self.assertNotIn("Velvet Matte Lipstick", body)
        self.assertNotIn("Hydrating Glow Elixir", body)

    def test_low_and_out_of_stock_tab_is_not_overridden_by_the_stock_select(self):
        tabs = self.tab_anchors(self.partial(status="all"), "alert")

        self.assertEqual(len(tabs), 1)
        hx_params = re.search(r'hx-params="([^"]*)"', tabs[0])
        self.assertIsNotNone(
            hx_params,
            "the tab pins status in its URL, so the included select must not "
            "send a second status that Django would read instead",
        )
        self.assertNotIn("status", [p.strip() for p in hx_params.group(1).split(",")])

    def test_active_alert_view_is_reflected_in_the_stock_select(self):
        """Pagination links carry no status of their own -- if the select cannot
        hold 'alert', the next page of the tab's view reverts to everything."""
        body = self.partial(status="alert")

        self.assertRegex(body, r'<option value="alert"[^>]*selected')

    def test_all_products_tab_is_not_overridden_by_the_stock_select(self):
        tabs = self.tab_anchors(self.partial(status="alert"), "all")

        self.assertEqual(len(tabs), 1)
        hx_params = re.search(r'hx-params="([^"]*)"', tabs[0])
        self.assertIsNotNone(hx_params)
        self.assertNotIn("status", [p.strip() for p in hx_params.group(1).split(",")])


class StockLedgerSearchShortcutTests(LedgerTestCase):
    """The ledger advertises a shortcut key, so the key has to do something."""

    def test_slash_key_focuses_the_ledger_search(self):
        body = self.client.get(reverse("core:products")).content.decode()

        self.assertIn('key !== "/"', body)

    def test_search_hint_advertises_slash_not_f3(self):
        body = self.client.get(reverse("core:load-products"), {"l": 10, "p": 1}).content.decode()

        self.assertIn(">/</kbd>", body)
        self.assertNotIn("F3", body)


class ImportCategoryMappingTests(TestCase):
    """Spreadsheet exports carry the human label ("Body & Bath"), so the label
    has to round-trip to its own value; everything else stays skincare."""

    def test_every_choice_label_and_value_maps_to_itself(self):
        from core.tasks import clean_category

        for value, label in ProductCategory.choices:
            with self.subTest(label=label):
                self.assertEqual(clean_category(label), value)
                self.assertEqual(clean_category(value), value)
                self.assertEqual(clean_category(f"  {label} "), value)

    def test_unknown_and_empty_fall_back_to_skincare(self):
        from core.tasks import clean_category

        self.assertEqual(clean_category("Wigs"), "skincare")
        self.assertEqual(clean_category(""), "skincare")
        self.assertEqual(clean_category(None), "skincare")


class ImportProgressEndpointTests(LedgerTestCase):
    def test_completed_track_response_carries_the_reload_trigger(self):
        with mock.patch("core.views.Progress") as progress:
            progress.return_value.get_info.return_value = {
                "complete": True, "success": True,
                "state": "SUCCESS", "progress": {"percent": 100},
            }
            response = self.client.get(
                reverse("core:import-products-status", args=("fake-task",)),
                headers={"hx-request": "true"},
            )
        self.assertIn("reload_products_table", response["HX-Trigger"])

    def test_running_track_response_has_no_trigger(self):
        with mock.patch("core.views.Progress") as progress:
            progress.return_value.get_info.return_value = {
                "complete": False, "success": None,
                "state": "PROGRESS", "progress": {"percent": 40},
            }
            response = self.client.get(
                reverse("core:import-products-status", args=("fake-task",)),
                headers={"hx-request": "true"},
            )
        self.assertNotIn("HX-Trigger", response)


class DoImportProductsTests(LedgerTestCase):
    def _post_upload(self, name="Shea Butter Cubes"):
        csv_bytes = (
            "PRODUCT,CATEGORY,QUANTITY,COST PRICE,SELLING PRICE\n"
            f"{name},Body & Bath,4,7.0,10\n"
        ).encode()
        return self.client.post(
            reverse("core:do-import-products"),
            {"file": SimpleUploadedFile("rows.csv", csv_bytes, "text/csv")},
        )

    def test_already_complete_upload_response_triggers_the_reload(self):
        """With a warm worker a small import finishes before the progress
        modal's first render, so no polling ever runs; this response itself
        has to broadcast the ledger refresh."""
        with mock.patch("core.views.import_products_task") as task:
            task.delay.return_value.task_id = "task-abc"
            with mock.patch("core.views.Progress") as progress:
                progress.return_value.get_info.return_value = {
                    "complete": True, "success": True,
                    "state": "SUCCESS", "progress": {"percent": 100},
                }
                response = self._post_upload()

        self.assertIn("reload_products_table", response["HX-Trigger"])


class DoRemoveProductsTests(LedgerTestCase):
    def test_already_complete_removal_response_triggers_the_reload(self):
        """Same first-render hole as the import: a small deletion can finish
        before the progress modal ships, and the ledger still has to refresh."""
        with mock.patch("core.views.remove_products_task") as task:
            task.delay.return_value.task_id = "task-rmi"
            with mock.patch("core.views.Progress") as progress:
                progress.return_value.get_info.return_value = {
                    "complete": True, "success": True,
                    "state": "SUCCESS", "progress": {"percent": 100},
                }
                response = self.client.post(
                    reverse("core:do-remove-products"),
                    {"ids": str(self.elixir.pk)},
                )

        self.assertIn("reload_products_table", response["HX-Trigger"])


class TaskCommitButtonGuardTests(LedgerTestCase):
    """Buttons that queue worker tasks take seconds to answer; without a
    synchronous disabled state a fast double click dispatches the task twice."""

    def test_ledger_ships_the_synchronous_commit_guard(self):
        body = self.client.get(reverse("core:products")).content.decode()

        self.assertIn("__taskCommitGuard", body)
        self.assertIn("[data-task-commit]", body)

    def test_remove_confirm_is_guarded(self):
        body = self.client.post(
            reverse("core:remove-products-question"), {"ids": str(self.elixir.pk)}
        ).content.decode()

        self.assertIn("data-task-commit", body)
        self.assertIn('@htmx:beforeRequest="busy = true"', body)
        self.assertIn(':disabled="busy"', body)

    def test_import_form_is_guarded(self):
        body = self.client.get(reverse("core:import-products")).content.decode()

        self.assertIn('id="import-form"', body)
        self.assertIn("data-task-commit", body)
        self.assertIn('@htmx:beforeRequest="busy = true"', body)
        self.assertIn(':disabled="!schemaOk || busy"', body)


class BulkRemovalDialogTests(LedgerTestCase):
    """The confirm button reads its id list out of a node in the same swap, so a
    dialog whose script never rendered silently refuses to submit."""

    def question(self, ids):
        return self.client.post(
            reverse("core:remove-products-question"), {"ids": ids}
        ).content.decode()

    def test_dialog_javascript_only_reads_nodes_it_ships(self):
        body = self.question([str(self.elixir.pk), str(self.lipstick.pk)])

        targets = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", body))
        self.assertTrue(targets, "this dialog is expected to read a node by id")
        for target in targets:
            self.assertIn(
                f'id="{target}"',
                body,
                f"the confirm button reads #{target}, which this dialog never renders",
            )

    def test_dialog_ships_the_selected_ids_as_json(self):
        body = self.question([str(self.elixir.pk)])

        shipped = re.search(
            r'<script id="remove_ids" type="application/json">(.*?)</script>',
            body,
            re.S,
        )
        self.assertIsNotNone(shipped)
        self.assertEqual(json.loads(shipped.group(1)), [str(self.elixir.pk)])


class LedgerSelectionStateTests(LedgerTestCase):
    """ids is the only selection state. A second selectAll flag plus imperative
    el.checked left the header box inverted once the table re-rendered."""

    def test_no_second_selection_flag(self):
        body = self.client.get(reverse("core:products")).content.decode()

        self.assertNotIn("selectAll", body)
        self.assertNotIn(".checked =", body)

    def test_header_checkbox_shows_whether_the_page_is_selected(self):
        body = self.client.get(
            reverse("core:load-products"), {"l": 10, "p": 1}
        ).content.decode()

        header = re.search(r'<input id="checkbox-all-search"[^>]*>', body)
        self.assertIsNotNone(header)
        self.assertIn(":checked=", header.group(0))

    def test_page_alpine_scope_stays_one_attribute(self):
        """A double quote inside x-data ends the attribute early: the remaining
        JavaScript renders as page text and Alpine never builds the scope."""
        body = self.client.get(reverse("core:products")).content.decode()

        scope = re.search(r'x-data="\{ids:(.*?)\}">', body, re.S)
        self.assertIsNotNone(scope, "the ledger page renders no selection scope")
        self.assertIn("toggleAllCheckboxes", scope.group(1))
        self.assertNotIn('"', scope.group(1))
