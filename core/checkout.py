from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from .inventory import (
    MAX_QUANTITY,
    _assert_product_stock,
    _check_replay,
    _decimal,
    _existing_replay,
    _fingerprint,
    _uuid,
)
from .models import Order, OrderItem, Product, SaleBatchAllocation, StockBatch

MAX_SALE_LINES = 100
MAX_ORDER_AMOUNT = Decimal("99999999.99")


@dataclass(frozen=True)
class SaleLine:
    product_id: UUID
    quantity: int
    total_price: Decimal


def _normalize_lines(lines):
    if not isinstance(lines, (list, tuple)) or not lines:
        raise ValidationError({"lines": "Add at least one product to the sale."})
    if len(lines) > MAX_SALE_LINES:
        raise ValidationError({"lines": "A sale cannot exceed 100 product lines."})

    normalized = []
    seen_product_ids = set()
    for index, line in enumerate(lines, start=1):
        if not isinstance(line, SaleLine):
            raise ValidationError({"lines": "Sale lines must use SaleLine."})
        product_id = _uuid(line.product_id, f"lines[{index}].product_id")
        if product_id in seen_product_ids:
            raise ValidationError({"lines": "A product may appear only once per sale."})
        seen_product_ids.add(product_id)
        if (
            isinstance(line.quantity, bool)
            or not isinstance(line.quantity, int)
            or not 0 < line.quantity <= MAX_QUANTITY
        ):
            raise ValidationError(
                {f"lines[{index}].quantity": "Enter a positive whole number."}
            )
        total_price = _decimal(
            line.total_price,
            f"lines[{index}].total_price",
            max_digits=6,
        )
        normalized.append(SaleLine(product_id, line.quantity, total_price))
    return normalized


def _require_cashier(actor):
    if (
        not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "user_type", None) not in {"ADMIN", "SALEPERSON"}
    ):
        raise ValidationError("An active register account is required.")


def checkout(*, actor, request_key: UUID, lines: list[SaleLine]) -> Order:
    """Create one customer order and consume its FIFO batches atomically."""
    _require_cashier(actor)
    request_key = _uuid(request_key, "request_key")
    lines = _normalize_lines(lines)
    fingerprint = _fingerprint(
        {
            "lines": [
                {
                    "product_id": str(line.product_id),
                    "quantity": line.quantity,
                    "total_price": str(line.total_price),
                }
                for line in lines
            ]
        }
    )
    replay = _existing_replay(
        Order,
        request_key,
        actor,
        fingerprint,
        actor_field="user",
        key_field="checkout_request_key",
        fingerprint_field="checkout_fingerprint",
    )
    if replay is not None:
        return replay

    product_ids = sorted((line.product_id for line in lines), key=str)
    with transaction.atomic():
        replay = _existing_replay(
            Order,
            request_key,
            actor,
            fingerprint,
            actor_field="user",
            key_field="checkout_request_key",
            fingerprint_field="checkout_fingerprint",
        )
        if replay is not None:
            return replay
        products = {
            product.pk: product
            for product in Product.objects.select_for_update()
            .filter(pk__in=product_ids)
            .order_by("pk")
        }
        missing = [str(product_id) for product_id in product_ids if product_id not in products]
        if missing:
            raise ValidationError({"lines": f"Unknown product(s): {', '.join(missing)}."})
        for product in products.values():
            _assert_product_stock(product)

        batches = list(
            StockBatch.objects.select_for_update()
            .select_related("product")
            .filter(product_id__in=product_ids, quantity_remaining__gt=0)
            .order_by(
                "product_id",
                Case(
                    When(receipt__source="OPENING", then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                ),
                "receipt__received_at",
                "receipt_id",
                "line_number",
                "pk",
            )
        )
        batches_by_product = {}
        for batch in batches:
            batches_by_product.setdefault(batch.product.pk, []).append(batch)

        total_paid = Decimal("0.00")
        validated_lines = []
        for line in lines:
            product = products[line.product_id]
            expected_total = product.price * line.quantity
            if expected_total < 0 or expected_total != line.total_price:
                raise ValidationError(
                    {str(product.pk): "The cart price changed. Refresh the register."}
                )
            if expected_total > Decimal("9999.99"):
                raise ValidationError(
                    {str(product.pk): "The sale line exceeds the supported amount."}
                )
            available = sum(
                batch.quantity_remaining
                for batch in batches_by_product.get(product.pk, ())
            )
            if line.quantity > available:
                raise ValidationError(
                    {str(product.pk): f"Only {available} units are available."}
                )
            total_paid += expected_total
            validated_lines.append((line, product))
        if total_paid > MAX_ORDER_AMOUNT:
            raise ValidationError({"lines": "The order exceeds the supported total."})

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    user=actor,
                    code=_generate_order_code(),
                    overall_amount_paid=total_paid,
                    checkout_request_key=request_key,
                    checkout_fingerprint=fingerprint,
                )
        except IntegrityError:
            existing = Order.objects.filter(
                checkout_request_key=request_key
            ).first()
            if existing is None:
                raise
            return _check_replay(
                existing,
                actor,
                fingerprint,
                actor_field="user",
                fingerprint_field="checkout_fingerprint",
            )

        product_stock_changes = {}
        for line, product in validated_lines:
            item = OrderItem.objects.create(
                order=order,
                product=product,
                qty_bought=line.quantity,
                paid_amount=line.total_price,
                cost_amount=Decimal("0.00"),
                cost_is_estimated=False,
            )

            remaining_to_allocate = line.quantity
            cost_amount = Decimal("0.00")
            allocation_rows = []
            for batch in batches_by_product.get(product.pk, ()):
                if remaining_to_allocate == 0:
                    break
                allocated = min(remaining_to_allocate, batch.quantity_remaining)
                batch.quantity_remaining -= allocated
                remaining_to_allocate -= allocated
                cost_amount += batch.unit_cost * allocated
                item.cost_is_estimated |= batch.cost_is_estimated
                allocation_rows.append(
                    SaleBatchAllocation(
                        order_item=item,
                        batch=batch,
                        quantity=allocated,
                        unit_cost=batch.unit_cost,
                    )
                )
            if remaining_to_allocate:
                raise ValidationError(
                    {str(product.pk): "Available batch stock changed during checkout."}
                )
            item.cost_amount = cost_amount
            item.save(update_fields=["cost_amount", "cost_is_estimated", "updated"])
            SaleBatchAllocation.objects.bulk_create(allocation_rows)
            product.stock -= line.quantity
            product.updated = timezone.now()
            product_stock_changes[product.pk] = product

        StockBatch.objects.bulk_update(
            batches,
            ["quantity_remaining"],
            batch_size=max(len(batches), 1),
        )
        Product.objects.bulk_update(
            product_stock_changes.values(),
            ["stock", "updated"],
            batch_size=max(len(product_stock_changes), 1),
        )
        return order


def _generate_order_code():
    from utils import generate_code

    return generate_code(max_length=6)
