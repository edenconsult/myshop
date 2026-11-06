from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections
from django.db.models import Sum
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from authapp.models import Account
from core.checkout import SaleLine, checkout
from core.inventory import ReceiptLine, adjust_batch, receive_stock
from core.models import (
    Order,
    OrderItem,
    Product,
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
    StockReceipt,
)


class InventoryServiceTests(TestCase):
    def setUp(self):
        self.admin = Account.objects.create_user(
            username="inventory-admin",
            password="test-password",
            user_type="ADMIN",
        )
        self.cashier = Account.objects.create_user(
            username="inventory-cashier",
            password="test-password",
            user_type="SALEPERSON",
        )
        self.product = self.make_product()

    def make_product(self, *, name="Batch Test Product", price="40.00", stock=0):
        return Product.objects.create(
            name=name,
            sku=None,
            stock=stock,
            cost=Decimal("10.00"),
            price=Decimal(price),
            profit_rate=Decimal("0.75"),
            slug=name.lower().replace(" ", "-"),
        )

    def receive(self, lines, *, request_key=None, received_at=None, **kwargs):
        return receive_stock(
            actor=self.admin,
            request_key=request_key or uuid4(),
            lines=lines,
            received_at=received_at or timezone.now(),
            **kwargs,
        )

    def test_receipt_groups_products_and_allows_distinct_lines_for_one_product(self):
        other = self.make_product(name="Another Product")
        key = uuid4()

        receipt = self.receive(
            [
                ReceiptLine(self.product.pk, 10, Decimal("20.00")),
                ReceiptLine(self.product.pk, 5, Decimal("25.00")),
                ReceiptLine(other.pk, 3, Decimal("12.50")),
            ],
            request_key=key,
            purchased_on=timezone.localdate(),
            supplier_name="Supplier",
        )

        self.assertEqual(StockBatch.objects.filter(receipt=receipt).count(), 3)
        self.product.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.product.stock, 15)
        self.assertEqual(self.product.cost, Decimal("25.00"))
        self.assertEqual(other.stock, 3)
        self.assertEqual(other.cost, Decimal("12.50"))
        self.assertEqual(self.product.price, Decimal("40.00"))

    def test_receipt_retry_does_not_add_stock_twice(self):
        key = uuid4()
        line = ReceiptLine(self.product.pk, 4, Decimal("9.00"))
        received_at = timezone.now()

        first = self.receive([line], request_key=key, received_at=received_at)
        replay = self.receive(
            [line],
            request_key=key,
            received_at=received_at + timedelta(seconds=1),
        )

        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(first.received_at, received_at)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(StockBatch.objects.filter(receipt=first).count(), 1)

    def test_request_key_cannot_be_reused_for_another_payload_or_actor(self):
        key = uuid4()
        received_at = timezone.now()
        lines = [ReceiptLine(self.product.pk, 4, Decimal("9.00"))]
        self.receive(
            lines,
            request_key=key,
            received_at=received_at,
        )

        with self.assertRaises(ValidationError):
            self.receive(
                [ReceiptLine(self.product.pk, 5, Decimal("9.00"))],
                request_key=key,
                received_at=received_at,
            )
        another_admin = Account.objects.create_user(
            username="another-admin",
            password="test-password",
            user_type="ADMIN",
        )
        with self.assertRaises(ValidationError):
            receive_stock(
                actor=another_admin,
                request_key=key,
                lines=lines,
                received_at=received_at,
            )

    def test_invalid_receipts_do_not_mutate_inventory(self):
        invalid_lines = (
            [ReceiptLine(self.product.pk, 0, Decimal("5.00"))],
            [ReceiptLine(self.product.pk, 1, Decimal("-0.01"))],
            [ReceiptLine(uuid4(), 1, Decimal("5.00"))],
        )
        for lines in invalid_lines:
            with self.subTest(lines=lines), self.assertRaises(ValidationError):
                self.receive(lines)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(
            StockReceipt.objects.exclude(source="OPENING").count(),
            0,
        )

    def test_non_purchase_receipt_requires_reason_and_uses_estimated_cost(self):
        with self.assertRaises(ValidationError):
            self.receive(
                [ReceiptLine(self.product.pk, 2, Decimal("8.00"))],
                source="IMPORT_OPENING",
            )

        receipt = self.receive(
            [ReceiptLine(self.product.pk, 2, Decimal("8.00"))],
            source="IMPORT_OPENING",
            reason="Imported opening quantity",
        )

        batch = StockBatch.objects.get(receipt=receipt)
        self.assertTrue(batch.cost_is_estimated)
        self.product.refresh_from_db()
        self.assertEqual(self.product.cost, Decimal("10.00"))

    def test_adjustment_requires_a_reason_and_preserves_receipt_facts(self):
        receipt = self.receive(
            [ReceiptLine(self.product.pk, 5, Decimal("8.00"))]
        )
        batch = StockBatch.objects.get(receipt=receipt)

        with self.assertRaises(ValidationError):
            adjust_batch(
                actor=self.admin,
                request_key=uuid4(),
                batch_id=batch.pk,
                quantity_delta=-1,
                reason=" ",
            )
        adjustment = adjust_batch(
            actor=self.admin,
            request_key=uuid4(),
            batch_id=batch.pk,
            quantity_delta=-2,
            reason="Damaged units",
        )

        batch.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(adjustment.quantity_delta, -2)
        self.assertEqual(batch.quantity_received, 5)
        self.assertEqual(batch.quantity_remaining, 3)
        self.assertEqual(self.product.stock, 3)

    def test_adjustment_retry_is_idempotent_and_cannot_make_stock_negative(self):
        receipt = self.receive(
            [ReceiptLine(self.product.pk, 2, Decimal("8.00"))]
        )
        batch = StockBatch.objects.get(receipt=receipt)
        key = uuid4()

        first = adjust_batch(
            actor=self.admin,
            request_key=key,
            batch_id=batch.pk,
            quantity_delta=-1,
            reason="Count correction",
        )
        replay = adjust_batch(
            actor=self.admin,
            request_key=key,
            batch_id=batch.pk,
            quantity_delta=-1,
            reason="Count correction",
        )
        with self.assertRaises(ValidationError):
            adjust_batch(
                actor=self.admin,
                request_key=uuid4(),
                batch_id=batch.pk,
                quantity_delta=-2,
                reason="Count correction",
            )

        batch.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(batch.quantity_remaining, 1)
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(StockAdjustment.objects.count(), 1)

    def test_checkout_allocates_fifo_and_freezes_acquisition_cost(self):
        received_at = timezone.now()
        self.receive(
            [ReceiptLine(self.product.pk, 10, Decimal("20.00"))],
            received_at=received_at,
        )
        self.receive(
            [ReceiptLine(self.product.pk, 5, Decimal("25.00"))],
            received_at=received_at + timedelta(seconds=1),
        )

        order = checkout(
            actor=self.admin,
            request_key=uuid4(),
            lines=[SaleLine(self.product.pk, 12, Decimal("480.00"))],
        )
        item = OrderItem.objects.get(order=order)
        allocations = list(
            SaleBatchAllocation.objects.filter(order_item=item)
            .order_by("unit_cost")
            .values_list("quantity", "unit_cost")
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(item.cost_amount, Decimal("250.00"))
        self.assertEqual(item.paid_amount - item.cost_amount, Decimal("230.00"))
        self.assertEqual(
            allocations,
            [(10, Decimal("20.00")), (2, Decimal("25.00"))],
        )

        self.product.cost = Decimal("99.00")
        self.product.price = Decimal("120.00")
        self.product.save(update_fields=["cost", "price"])
        item.refresh_from_db()
        self.assertEqual(item.cost_amount, Decimal("250.00"))

    def test_opening_stock_is_allocated_before_receipts_even_with_backdated_receipt(self):
        opening_time = timezone.now()
        self.receive(
            [ReceiptLine(self.product.pk, 2, Decimal("10.00"))],
            received_at=opening_time,
            source="OPENING",
            reason="Cutover opening stock",
        )
        self.receive(
            [ReceiptLine(self.product.pk, 2, Decimal("20.00"))],
            received_at=opening_time - timedelta(days=1),
        )

        order = checkout(
            actor=self.admin,
            request_key=uuid4(),
            lines=[SaleLine(self.product.pk, 1, Decimal("40.00"))],
        )

        item = OrderItem.objects.get(order=order)
        allocation = SaleBatchAllocation.objects.get(order_item=item)
        self.assertEqual(allocation.unit_cost, Decimal("10.00"))
        self.assertTrue(item.cost_is_estimated)

    def test_checkout_retry_does_not_sell_twice(self):
        self.receive([ReceiptLine(self.product.pk, 5, Decimal("8.00"))])
        key = uuid4()
        line = SaleLine(self.product.pk, 2, Decimal("80.00"))

        first = checkout(actor=self.admin, request_key=key, lines=[line])
        replay = checkout(actor=self.admin, request_key=key, lines=[line])

        self.product.refresh_from_db()
        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(Order.objects.count(), 1)

    def test_checkout_rejects_duplicate_products_stale_prices_and_missing_stock(self):
        self.receive([ReceiptLine(self.product.pk, 2, Decimal("8.00"))])

        invalid_carts = (
            [
                SaleLine(self.product.pk, 1, Decimal("40.00")),
                SaleLine(self.product.pk, 1, Decimal("40.00")),
            ],
            [SaleLine(self.product.pk, 1, Decimal("39.99"))],
            [SaleLine(self.product.pk, 3, Decimal("120.00"))],
        )
        for lines in invalid_carts:
            with self.subTest(lines=lines), self.assertRaises(ValidationError):
                checkout(actor=self.admin, request_key=uuid4(), lines=lines)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.assertEqual(SaleBatchAllocation.objects.count(), 0)

    def test_checkout_requires_active_register_actor(self):
        self.receive([ReceiptLine(self.product.pk, 1, Decimal("8.00"))])
        self.cashier.is_active = False
        self.cashier.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            checkout(
                actor=self.cashier,
                request_key=uuid4(),
                lines=[SaleLine(self.product.pk, 1, Decimal("40.00"))],
            )

    def test_checkout_failure_rolls_back_order_and_inventory(self):
        other = self.make_product(name="Insufficient Product")
        self.receive([ReceiptLine(self.product.pk, 2, Decimal("8.00"))])

        with self.assertRaises(ValidationError):
            checkout(
                actor=self.admin,
                request_key=uuid4(),
                lines=[
                    SaleLine(self.product.pk, 1, Decimal("40.00")),
                    SaleLine(other.pk, 1, Decimal("40.00")),
                ],
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(
            StockBatch.objects.filter(product=self.product).aggregate(
                total=Sum("quantity_remaining")
            )["total"],
            2,
        )

    def test_inventory_reconciliation_passes_for_a_receipt_and_sale(self):
        self.receive([ReceiptLine(self.product.pk, 3, Decimal("8.00"))])
        checkout(
            actor=self.admin,
            request_key=uuid4(),
            lines=[SaleLine(self.product.pk, 1, Decimal("40.00"))],
        )

        call_command("check_inventory")

    def test_inventory_reconciliation_reports_aggregate_stock_mismatch(self):
        self.receive([ReceiptLine(self.product.pk, 3, Decimal("8.00"))])
        Product.objects.filter(pk=self.product.pk).update(stock=4)

        with self.assertRaises(CommandError):
            call_command("check_inventory")

    def test_receipt_and_sale_history_protect_product_and_order_deletion(self):
        self.receive([ReceiptLine(self.product.pk, 3, Decimal("8.00"))])
        with self.assertRaises(ProtectedError):
            self.product.delete()
        order = checkout(
            actor=self.admin,
            request_key=uuid4(),
            lines=[SaleLine(self.product.pk, 1, Decimal("40.00"))],
        )
        with self.assertRaises(ProtectedError):
            order.delete()


class InventoryConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.admin = Account.objects.create_user(
            username="concurrent-admin",
            password="test-password",
            user_type="ADMIN",
        )
        self.product = Product.objects.create(
            name="Concurrent Product",
            sku="CONCURRENT01",
            stock=0,
            cost=Decimal("5.00"),
            price=Decimal("12.00"),
            profit_rate=Decimal("0.58"),
            slug="concurrent-product",
        )
        receive_stock(
            actor=self.admin,
            request_key=uuid4(),
            lines=[ReceiptLine(self.product.pk, 1, Decimal("5.00"))],
            received_at=timezone.now(),
        )

    def _concurrent_checkout(self, request_key, barrier):
        try:
            connections.close_all()
            barrier.wait(timeout=10)
            return checkout(
                actor=self.admin,
                request_key=request_key,
                lines=[SaleLine(self.product.pk, 1, Decimal("12.00"))],
            ).pk
        except ValidationError:
            return None
        finally:
            connections.close_all()

    def test_overlapping_sales_cannot_oversell(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._concurrent_checkout, uuid4(), barrier)
                for _ in range(2)
            ]
            outcomes = [future.result(timeout=30) for future in futures]

        self.product.refresh_from_db()
        self.assertEqual(sum(outcome is not None for outcome in outcomes), 1)
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(Order.objects.count(), 1)
