from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.deletion import ProtectedError

from core.models import (
    Order,
    OrderItem,
    Product,
    ProductImportOperation,
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
    StockReceipt,
    StockReceiptDraft,
)


PURGE_ORDER = (
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
    OrderItem,
    Order,
    StockReceipt,
    StockReceiptDraft,
    ProductImportOperation,
    Product,
)


class Command(BaseCommand):
    help = (
        "Permanently remove all products and their sales/inventory history. "
        "Preview counts by default; pass --execute to perform the purge."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Delete the listed records (otherwise only show counts).",
        )

    def handle(self, *args, **options):
        execute = options["execute"]

        try:
            with transaction.atomic():
                counts = {model: model.objects.count() for model in PURGE_ORDER}

                self.stdout.write(
                    "Records to delete:" if execute else "Dry run; no records deleted:"
                )
                for model, count in counts.items():
                    self.stdout.write(f"  {model._meta.label}: {count}")

                if not execute:
                    self.stdout.write(
                        "Run again with --execute to permanently delete these records."
                    )
                    return

                for model in PURGE_ORDER:
                    model.objects.all().delete()
        except ProtectedError as error:
            raise CommandError(
                f"Purge aborted because other records still protect the data: {error}"
            ) from error

        self.stdout.write(
            self.style.SUCCESS("Catalogue, sales, and inventory history purged.")
        )
