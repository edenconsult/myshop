import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Product,
    StockAdjustment,
    StockBatch,
    StockReceipt,
    StockReceiptSource,
)

MAX_QUANTITY = 2_147_483_647
MAX_RECEIPT_LINES = 500
MAX_MONEY_DIGITS = 10


@dataclass(frozen=True)
class ReceiptLine:
    product_id: UUID
    quantity: int
    unit_cost: Decimal


def _uuid(value, field_name):
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError({field_name: "Enter a valid UUID."}) from error


def _quantity(value, field_name="quantity"):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError({field_name: "Enter a whole number."})
    if not 0 < value <= MAX_QUANTITY:
        raise ValidationError(
            {field_name: f"Enter a quantity between 1 and {MAX_QUANTITY}."}
        )
    return value


def _decimal(value, field_name, *, max_digits=MAX_MONEY_DIGITS):
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValidationError({field_name: "Enter a valid amount."}) from error
    if not amount.is_finite() or amount < 0:
        raise ValidationError({field_name: "Enter a finite, non-negative amount."})
    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -2:
        raise ValidationError({field_name: "Use no more than two decimal places."})
    if amount > Decimal(10) ** (max_digits - 2) - Decimal("0.01"):
        raise ValidationError({field_name: "The amount is too large."})
    return amount.quantize(Decimal("0.01"))


def _fingerprint(payload):
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _require_admin(actor):
    if (
        not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or getattr(actor, "user_type", None) != "ADMIN"
    ):
        raise ValidationError("An active administrator is required.")


def _check_replay(
    record,
    actor,
    fingerprint,
    *,
    actor_field,
    fingerprint_field="request_fingerprint",
):
    if getattr(record, actor_field + "_id") != actor.pk:
        raise ValidationError("This request key belongs to another account.")
    if getattr(record, fingerprint_field) != fingerprint:
        raise ValidationError("This request key was already used for different data.")
    return record


def _existing_replay(
    model,
    request_key,
    actor,
    fingerprint,
    *,
    actor_field,
    key_field="request_key",
    fingerprint_field="request_fingerprint",
):
    record = model.objects.filter(**{key_field: request_key}).first()
    if record is None:
        return None
    return _check_replay(
        record,
        actor,
        fingerprint,
        actor_field=actor_field,
        fingerprint_field=fingerprint_field,
    )


def _create_with_retry(model, request_key, actor, fingerprint, *, actor_field, create):
    try:
        with transaction.atomic():
            return create(), True
    except IntegrityError:
        record = model.objects.filter(request_key=request_key).first()
        if record is None:
            raise
        return (
            _check_replay(record, actor, fingerprint, actor_field=actor_field),
            False,
        )


def _normalize_receipt_lines(lines):
    if not isinstance(lines, (list, tuple)) or not lines:
        raise ValidationError({"lines": "Add at least one receipt line."})
    if len(lines) > MAX_RECEIPT_LINES:
        raise ValidationError({"lines": "A receipt cannot exceed 500 lines."})

    normalized = []
    for index, line in enumerate(lines, start=1):
        if not isinstance(line, ReceiptLine):
            raise ValidationError({"lines": "Receipt lines must use ReceiptLine."})
        normalized.append(
            ReceiptLine(
                product_id=_uuid(line.product_id, f"lines[{index}].product_id"),
                quantity=_quantity(line.quantity, f"lines[{index}].quantity"),
                unit_cost=_decimal(line.unit_cost, f"lines[{index}].unit_cost"),
            )
        )
    return normalized


def _validate_text(value, field_name, limit):
    if not isinstance(value, str):
        raise ValidationError({field_name: "Enter text."})
    value = value.strip()
    if len(value) > limit:
        raise ValidationError({field_name: f"Use no more than {limit} characters."})
    return value


def _assert_product_stock(product):
    quantity = (
        StockBatch.objects.filter(product=product).aggregate(
            total=Sum("quantity_remaining")
        )["total"]
        or 0
    )
    if quantity != product.stock:
        raise ValidationError(
            f"Inventory is inconsistent for {product.name}; reconcile it before writing."
        )


def receive_stock(
    *,
    actor,
    request_key: UUID,
    lines: list[ReceiptLine],
    received_at: datetime,
    purchased_on: date | None = None,
    source: str = StockReceiptSource.PURCHASE,
    supplier_name: str = "",
    external_reference: str = "",
    notes: str = "",
    reason: str = "",
) -> StockReceipt:
    """Record a receipt and its batches as one retry-safe inventory operation."""
    _require_admin(actor)
    request_key = _uuid(request_key, "request_key")
    lines = _normalize_receipt_lines(lines)
    if not isinstance(received_at, datetime) or timezone.is_naive(received_at):
        raise ValidationError({"received_at": "Use a timezone-aware date and time."})
    if purchased_on is not None and (
        not isinstance(purchased_on, date) or isinstance(purchased_on, datetime)
    ):
        raise ValidationError({"purchased_on": "Enter a valid purchase date."})
    try:
        source = StockReceiptSource(source)
    except (TypeError, ValueError) as error:
        raise ValidationError({"source": "Choose a valid receipt source."}) from error
    supplier_name = _validate_text(supplier_name, "supplier_name", 255)
    external_reference = _validate_text(external_reference, "external_reference", 255)
    notes = _validate_text(notes, "notes", 5000)
    reason = _validate_text(reason, "reason", 500)
    if source != StockReceiptSource.PURCHASE and not reason:
        raise ValidationError({"reason": "A reason is required for non-purchase stock."})

    line_data = [
        {
            "product_id": str(line.product_id),
            "quantity": line.quantity,
            "unit_cost": str(line.unit_cost),
        }
        for line in lines
    ]
    fingerprint = _fingerprint(
        {
            "source": source.value,
            "lines": line_data,
            "purchased_on": purchased_on.isoformat() if purchased_on else None,
            "supplier_name": supplier_name,
            "external_reference": external_reference,
            "notes": notes,
            "reason": reason,
        }
    )
    replay = _existing_replay(
        StockReceipt, request_key, actor, fingerprint, actor_field="recorded_by"
    )
    if replay is not None:
        return replay

    product_ids = sorted({line.product_id for line in lines}, key=str)
    with transaction.atomic():
        replay = _existing_replay(
            StockReceipt, request_key, actor, fingerprint, actor_field="recorded_by"
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

        def create_receipt():
            return StockReceipt.objects.create(
                request_key=request_key,
                request_fingerprint=fingerprint,
                recorded_by=actor,
                source=source,
                purchased_on=purchased_on,
                received_at=received_at,
                supplier_name=supplier_name,
                external_reference=external_reference,
                notes=notes,
                reason=reason,
            )

        receipt, created = _create_with_retry(
            StockReceipt,
            request_key,
            actor,
            fingerprint,
            actor_field="recorded_by",
            create=create_receipt,
        )
        if not created:
            return receipt

        quantities = {product_id: 0 for product_id in product_ids}
        last_cost = {}
        batches = []
        estimated = source != StockReceiptSource.PURCHASE
        for line_number, line in enumerate(lines, start=1):
            product = products[line.product_id]
            quantities[line.product_id] += line.quantity
            last_cost[line.product_id] = line.unit_cost
            batches.append(
                StockBatch(
                    receipt=receipt,
                    product=product,
                    line_number=line_number,
                    quantity_received=line.quantity,
                    quantity_remaining=line.quantity,
                    unit_cost=line.unit_cost,
                    cost_is_estimated=estimated,
                )
            )
        StockBatch.objects.bulk_create(batches)

        for product_id, product in products.items():
            new_stock = product.stock + quantities[product_id]
            if new_stock > MAX_QUANTITY:
                raise ValidationError({"lines": f"Stock exceeds the limit for {product.name}."})
            product.stock = new_stock
            if source == StockReceiptSource.PURCHASE:
                product.cost = last_cost[product_id]
            product.updated = timezone.now()
        Product.objects.bulk_update(
            products.values(),
            ["stock", "cost", "updated"],
            batch_size=len(products),
        )
        return receipt


def adjust_batch(
    *,
    actor,
    request_key: UUID,
    batch_id: UUID,
    quantity_delta: int,
    reason: str,
) -> StockAdjustment:
    """Apply a reasoned correction to a known batch without rewriting its receipt."""
    _require_admin(actor)
    request_key = _uuid(request_key, "request_key")
    batch_id = _uuid(batch_id, "batch_id")
    if isinstance(quantity_delta, bool) or not isinstance(quantity_delta, int):
        raise ValidationError({"quantity_delta": "Enter a whole number."})
    if quantity_delta == 0 or abs(quantity_delta) > MAX_QUANTITY:
        raise ValidationError({"quantity_delta": "Enter a non-zero valid quantity."})
    reason = _validate_text(reason, "reason", 500)
    if not reason:
        raise ValidationError({"reason": "A reason is required."})
    fingerprint = _fingerprint(
        {
            "batch_id": str(batch_id),
            "quantity_delta": quantity_delta,
            "reason": reason,
        }
    )
    replay = _existing_replay(
        StockAdjustment,
        request_key,
        actor,
        fingerprint,
        actor_field="recorded_by",
    )
    if replay is not None:
        return replay

    with transaction.atomic():
        replay = _existing_replay(
            StockAdjustment,
            request_key,
            actor,
            fingerprint,
            actor_field="recorded_by",
        )
        if replay is not None:
            return replay
        batch_identity = StockBatch.objects.filter(pk=batch_id).values(
            "product_id"
        ).first()
        if batch_identity is None:
            raise ValidationError({"batch_id": "The selected batch does not exist."})
        product = (
            Product.objects.select_for_update()
            .filter(pk=batch_identity["product_id"])
            .first()
        )
        if product is None:
            raise ValidationError({"batch_id": "The selected batch does not exist."})
        batch = StockBatch.objects.select_for_update().get(pk=batch_id)
        _assert_product_stock(product)
        new_batch_stock = batch.quantity_remaining + quantity_delta
        new_product_stock = product.stock + quantity_delta
        if new_batch_stock < 0 or new_product_stock < 0:
            raise ValidationError({"quantity_delta": "The correction would make stock negative."})
        if new_product_stock > MAX_QUANTITY:
            raise ValidationError({"quantity_delta": "The correction exceeds the stock limit."})

        def create_adjustment():
            return StockAdjustment.objects.create(
                request_key=request_key,
                request_fingerprint=fingerprint,
                recorded_by=actor,
                batch=batch,
                quantity_delta=quantity_delta,
                reason=reason,
            )

        adjustment, created = _create_with_retry(
            StockAdjustment,
            request_key,
            actor,
            fingerprint,
            actor_field="recorded_by",
            create=create_adjustment,
        )
        if not created:
            return adjustment
        batch.quantity_remaining = new_batch_stock
        batch.save(update_fields=["quantity_remaining"])
        product.stock = new_product_stock
        Product.objects.filter(pk=product.pk).update(
            stock=new_product_stock,
            updated=timezone.now(),
        )
        return adjustment
