from decimal import Decimal
from uuid import UUID, uuid5

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify

from .inventory import (
    MAX_QUANTITY,
    ReceiptLine,
    _check_replay,
    _decimal,
    _existing_replay,
    _fingerprint,
    _require_admin,
    _uuid,
    receive_stock,
)
from .models import (
    Product,
    ProductCategory,
    ProductImportOperation,
    StockBatch,
    StockReceiptSource,
)

PROFIT_RATE_MAX = Decimal("9.99")
CATEGORY_BY_NAME = {
    key: value
    for value, label in ProductCategory.choices
    for key in (value.lower(), label.lower())
}


def clean_category(value):
    """Compatibility helper for callers that prefer the historical fallback."""
    if not value:
        return ProductCategory.SKINCARE
    return CATEGORY_BY_NAME.get(
        value.strip().lower(),
        ProductCategory.SKINCARE,
    )


def _quantity(value, row_number):
    if isinstance(value, bool):
        raise ValidationError(f"Row {row_number}: quantity must be a whole number.")
    if isinstance(value, int):
        quantity = value
    elif isinstance(value, str) and value.strip().isdigit():
        quantity = int(value.strip())
    else:
        raise ValidationError(f"Row {row_number}: quantity must be a whole number.")
    if not 0 <= quantity <= MAX_QUANTITY:
        raise ValidationError(f"Row {row_number}: quantity is outside the supported range.")
    return quantity


def _parse_rows(rows):
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValidationError("The import must contain at least one product row.")

    parsed = []
    seen_names = set()
    seen_skus = set()
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValidationError(f"Row {row_number}: expected a product row.")
        name = row.get("PRODUCT")
        if not isinstance(name, str):
            raise ValidationError(f"Row {row_number}: PRODUCT is required.")
        name = name.strip()
        if not name or len(name) > 255:
            raise ValidationError(
                f"Row {row_number}: PRODUCT must contain 1 to 255 characters."
            )
        sku = row.get("SKU") or ""
        if not isinstance(sku, str):
            raise ValidationError(f"Row {row_number}: SKU must be text.")
        sku = sku.strip().upper() or None
        if sku and len(sku) > 32:
            raise ValidationError(f"Row {row_number}: SKU cannot exceed 32 characters.")
        normalized_name = name.casefold()
        if normalized_name in seen_names:
            raise ValidationError(f"Row {row_number}: duplicate product name.")
        if sku and sku in seen_skus:
            raise ValidationError(f"Row {row_number}: duplicate SKU.")
        seen_names.add(normalized_name)
        if sku:
            seen_skus.add(sku)

        try:
            cost = _decimal(row.get("COST PRICE", "0") or "0", "COST PRICE")
            price = _decimal(row.get("SELLING PRICE", "0") or "0", "SELLING PRICE")
        except ValidationError as error:
            raise ValidationError(f"Row {row_number}: {error.messages[0]}") from error
        quantity = _quantity(row.get("QUANTITY", ""), row_number)
        category = row.get("CATEGORY") or ""
        if not isinstance(category, str):
            raise ValidationError(f"Row {row_number}: CATEGORY must be text.")
        category_key = category.strip().lower()
        if category_key and category_key not in CATEGORY_BY_NAME:
            raise ValidationError(f"Row {row_number}: CATEGORY is not recognized.")
        category = CATEGORY_BY_NAME.get(category_key, ProductCategory.SKINCARE)
        parsed.append(
            {
                "name": name,
                "sku": sku,
                "cost": cost,
                "price": price,
                "quantity": quantity,
                "category": category,
            }
        )
    return parsed


def import_catalogue_rows(
    *,
    actor,
    request_key: UUID,
    rows: list[dict],
    update_existing: bool = False,
) -> ProductImportOperation:
    """Atomically import catalogue metadata and estimated opening balances."""
    _require_admin(actor)
    request_key = _uuid(request_key, "request_key")
    if not isinstance(update_existing, bool):
        raise ValidationError({"update_existing": "Choose a valid import mode."})
    parsed_rows = _parse_rows(rows)
    fingerprint = _fingerprint(
        {
            "update_existing": bool(update_existing),
            "rows": [
                {
                    **row,
                    "cost": str(row["cost"]),
                    "price": str(row["price"]),
                }
                for row in parsed_rows
            ],
        }
    )
    replay = _existing_replay(
        ProductImportOperation,
        request_key,
        actor,
        fingerprint,
        actor_field="recorded_by",
    )
    if replay is not None:
        return replay

    with transaction.atomic():
        replay = _existing_replay(
            ProductImportOperation,
            request_key,
            actor,
            fingerprint,
            actor_field="recorded_by",
        )
        if replay is not None:
            return replay

        try:
            with transaction.atomic():
                operation = ProductImportOperation.objects.create(
                    request_key=request_key,
                    recorded_by=actor,
                    request_fingerprint=fingerprint,
                )
        except IntegrityError:
            existing = ProductImportOperation.objects.filter(
                request_key=request_key
            ).first()
            if existing is None:
                raise
            return _check_replay(
                existing,
                actor,
                fingerprint,
                actor_field="recorded_by",
            )

        sku_values = [row["sku"] for row in parsed_rows if row["sku"]]
        name_values = [row["name"].lower() for row in parsed_rows]
        matches = (
            Product.objects.annotate(name_lower=Lower("name"))
            .filter(Q(sku__in=sku_values) | Q(name_lower__in=name_values))
            .order_by("pk")
        )
        existing_products = list(matches)
        by_sku = {product.sku: product for product in existing_products if product.sku}
        by_name = {}
        for product in existing_products:
            name_key = product.name.casefold()
            if name_key in by_name and by_name[name_key].pk != product.pk:
                raise ValidationError(
                    f"Existing product names are ambiguous: {product.name}."
                )
            by_name[name_key] = product
        locked_products = {
            product.pk: product
            for product in Product.objects.select_for_update()
            .filter(pk__in=[product.pk for product in existing_products])
            .order_by("pk")
        }
        resolved = set()
        imports_to_apply = []
        for row_number, row in enumerate(parsed_rows, start=1):
            sku_product = by_sku.get(row["sku"]) if row["sku"] else None
            name_product = by_name.get(row["name"].casefold())
            if (
                sku_product is not None
                and name_product is not None
                and sku_product.pk != name_product.pk
            ):
                raise ValidationError(
                    f"Row {row_number}: the SKU and name belong to different products."
                )
            product = sku_product or name_product
            if product is not None:
                product = locked_products[product.pk]
                if not update_existing:
                    raise ValidationError(
                        f"Row {row_number}: product already exists; enable update existing."
                    )
                if product.pk in resolved:
                    raise ValidationError(
                        f"Row {row_number}: multiple rows resolve to the same product."
                    )
                resolved.add(product.pk)
            elif row["name"].casefold() in by_name:
                raise ValidationError(f"Row {row_number}: product name conflict.")
            imports_to_apply.append((row_number, row, product))

        for row_number, row, product in imports_to_apply:
            price = row["price"]
            profit_rate = (
                min(row["cost"] / price, PROFIT_RATE_MAX)
                if price > 0
                else Decimal("0.00")
            )
            if product is None:
                product = Product.objects.create(
                    name=row["name"],
                    sku=row["sku"],
                    category=row["category"],
                    stock=0,
                    cost=row["cost"],
                    price=price,
                    profit_rate=profit_rate,
                    slug=slugify(row["name"]),
                )
            else:
                product.name = row["name"]
                product.sku = row["sku"]
                product.category = row["category"]
                product.cost = row["cost"]
                product.price = price
                product.profit_rate = profit_rate
                product.slug = slugify(row["name"])
                product.save(
                    update_fields=[
                        "name",
                        "sku",
                        "category",
                        "cost",
                        "price",
                        "profit_rate",
                        "slug",
                        "updated",
                    ]
                )

            if (
                product.stock != 0
                and not StockBatch.objects.filter(product_id=product.pk).exists()
            ):
                raise ValidationError(
                    f"Row {row_number}: existing stock has no batch history."
                )
            if row["quantity"] and product.pk not in locked_products:
                receive_stock(
                    actor=actor,
                    request_key=uuid5(request_key, f"opening-row-{row_number}"),
                    lines=[
                        ReceiptLine(
                            product.pk,
                            row["quantity"],
                            row["cost"],
                        )
                    ],
                    received_at=timezone.now(),
                    source=StockReceiptSource.IMPORT_OPENING,
                    reason="Catalogue import opening quantity; not a purchase receipt.",
                )
        return operation
