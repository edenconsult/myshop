from celery import shared_task
from celery_progress.backend import ProgressRecorder
from core.models import Order, Product


@shared_task(bind=True)
def import_products_task(self, rows: list[dict]):
    """Import product rows in bulk instead of saving one row at a time."""
    progress_recorder = ProgressRecorder(self)
    total_rows = len(rows)

    batch: list[Product] = []
    batch_size = 500
    progress_step = 100
    imported = 0

    def flush():
        nonlocal imported
        # ignore_conflicts lets duplicate product names skip just like the
        # old row-by-row save did, without failing the whole batch
        if batch:
            Product.objects.bulk_create(batch, batch_size, ignore_conflicts=True)
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
            name = row["PRODUCT"]
        except (KeyError, TypeError, ValueError):
            # skip malformed rows just like the old per-row try/except did
            continue

        profit_rate = abs(price) / abs(cost) if cost != 0 else 0
        batch.append(
            Product(
                name=name,
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
