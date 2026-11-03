from uuid import UUID

from celery import shared_task
from celery_progress.backend import ProgressRecorder
from django.db import connection, transaction
from django.db.models.deletion import ProtectedError

from authapp.models import Account
from core.catalog_imports import clean_category, import_catalogue_rows
from core.models import OrderItem, Product, StockBatch


@shared_task(bind=True)
def import_products_task(
    self,
    rows: list[dict],
    update_existing: bool = False,
    actor_id: str | None = None,
    request_key: str | None = None,
):
    """Apply one authorized, retry-safe catalogue import."""
    progress_recorder = ProgressRecorder(self)
    if actor_id is None or request_key is None:
        raise ValueError("An importing ADMIN and stable request key are required.")
    actor = Account.objects.filter(pk=actor_id, is_active=True).first()
    if actor is None or actor.user_type != "ADMIN":
        raise ValueError("The importing account is missing, inactive, or not an ADMIN.")
    try:
        request_uuid = UUID(request_key)
    except ValueError as error:
        raise ValueError("The import request key must be a UUID.") from error

    progress_recorder.set_progress(
        current=0,
        total=100,
        description="Validating catalogue import",
    )
    import_catalogue_rows(
        actor=actor,
        request_key=request_uuid,
        rows=rows,
        update_existing=update_existing,
    )
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE core_product")
    progress_recorder.set_progress(
        current=100,
        total=100,
        description="Catalogue import complete",
    )
    return "Done"


@shared_task(bind=True)
def remove_products_task(self, ids: list[str]):
    """Delete only zero-stock products that have never been referenced."""
    progress_recorder = ProgressRecorder(self)
    if not ids:
        raise ValueError("Select at least one product to remove.")

    requested = Product.objects.filter(pk__in=ids)
    number_of_products = requested.count()
    chunk_size = 500
    count = 0
    processed = 0
    product_ids = list(requested.values_list("pk", flat=True))
    for offset in range(0, len(product_ids), chunk_size):
        for product_id in product_ids[offset : offset + chunk_size]:
            try:
                with transaction.atomic():
                    product = (
                        Product.objects.select_for_update()
                        .filter(pk=product_id, stock=0)
                        .first()
                    )
                    if (
                        product is None
                        or OrderItem.objects.filter(product=product).exists()
                        or StockBatch.objects.filter(product=product).exists()
                    ):
                        pass
                    else:
                        product.delete()
                        count += 1
            except ProtectedError:
                pass
            processed += 1
            progress_recorder.set_progress(
                current=(processed / number_of_products) * 100,
                total=100,
                description=(
                    f"{count} out of {number_of_products} selected products removed"
                ),
            )
    blocked = number_of_products - count
    return (
        f"Done: removed {count}; "
        f"{blocked} products were protected by stock or history."
    )
