from celery import shared_task
from celery_progress.backend import ProgressRecorder
from decimal import Decimal
from django.db import connection

from core.models import Order, Product, ProductCategory

# spreadsheet exports carry the human label ("Body & Bath"), while hand
# entered files may carry the raw value; both spellings must resolve
CATEGORY_BY_NAME = {
    key: value
    for value, label in ProductCategory.choices
    for key in (value.lower(), label.lower())
}

# profit_rate is a legacy decimal(3,2) column, so it only holds up to 9.99;
# the ledger's Margin column is computed from cost/price instead.
PROFIT_RATE_MAX = Decimal("9.99")

UPDATED_FIELDS = ["name", "category", "cost", "price", "stock", "profit_rate"]


def clean_category(value):
    if not value:
        return ProductCategory.SKINCARE
    return CATEGORY_BY_NAME.get(value.strip().lower(), ProductCategory.SKINCARE)


@shared_task(bind=True)
def import_products_task(self, rows: list[dict], update_existing: bool = False):
    """Import product rows in bulk instead of saving one row at a time."""
    progress_recorder = ProgressRecorder(self)
    total_rows = len(rows)

    batch: list[Product] = []
    batch_size = 500
    progress_step = 100
    imported = 0

    def flush():
        nonlocal imported
        if not batch:
            progress_recorder.set_progress(
                current=(imported / total_rows) * 100,
                total=100,
                description=f"{imported} items out of {total_rows} products imported",
            )
            return

        inserts = batch
        if update_existing:
            # ON CONFLICT needs the name unique index to agree with the sku
            # one, so match on sku first and bulk_update rather than risk
            # the whole statement aborting on a renamed product.
            known = set(
                Product.objects.filter(sku__in=[p.sku for p in batch if p.sku]).values_list(
                    "sku", flat=True
                )
            )
            updates = [product for product in batch if product.sku in known]
            inserts = [product for product in batch if product.sku not in known]
            if updates:
                Product.objects.bulk_update(updates, UPDATED_FIELDS, batch_size)

        # ignore_conflicts lets duplicate product names skip just like the
        # old row-by-row save did, without failing the whole batch
        Product.objects.bulk_create(inserts, batch_size, ignore_conflicts=True)
        batch.clear()
        progress_recorder.set_progress(
            current=(imported / total_rows) * 100,
            total=100,
            description=f"{imported} items out of {total_rows} products imported",
        )

    for row in rows:
        try:
            cost = (
                float(row["COST PRICE"])
                if row.get("COST PRICE") not in ("", " ", None)
                else 0
            )
            price = (
                float(row["SELLING PRICE"])
                if row.get("SELLING PRICE") not in ("", " ", None)
                else 0
            )
            stock = int(row["QUANTITY"])
            name = row["PRODUCT"].strip()
        except (AttributeError, KeyError, TypeError, ValueError):
            # skip malformed rows just like the old per-row try/except did
            continue

        if not name:
            continue

        sku = (row.get("SKU") or "").strip() or None
        profit_rate = min(cost / price, PROFIT_RATE_MAX) if price > 0 else Decimal("0")
        batch.append(
            Product(
                name=name,
                sku=sku,
                category=clean_category(row.get("CATEGORY")),
                stock=stock,
                cost=cost,
                price=price,
                profit_rate=profit_rate,
            )
        )
        imported += 1

        if imported % progress_step == 0:
            flush()

    flush()

    # bulk_create does not update planner statistics; refresh them so the
    # product list/search queries plan well immediately after an import
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE core_product")

    return "Done"


@shared_task(bind=True)
def remove_products_task(self, ids: list[str]):
    """Delete products (and their orders) in chunks instead of one by one."""
    progress_recorder = ProgressRecorder(self)
    products = Product.objects.all()
    if len(ids) > 0:
        products = products.filter(pk__in=ids)

    number_of_products = products.count()
    if number_of_products == 0:
        return "Done"

    chunk_size = 500
    count = 0
    while True:
        pks = list(products.values_list("pk", flat=True)[:chunk_size])
        if not pks:
            break

        # delete orders that reference these products first (cascades
        # their order items); after the product delete the FK cascade
        # would make this filter match nothing
        Order.objects.filter(orderitem__product__in=pks).delete()

        # removes the products, cascading any remaining order items
        Product.objects.filter(pk__in=pks).delete()

        count += len(pks)
        progress_recorder.set_progress(
            current=(count / number_of_products) * 100,
            total=100,
            description=f"{count} out of {number_of_products} products removed",
        )
    return "Done"
