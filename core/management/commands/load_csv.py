import csv
import os
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from authapp.models import Account
from core.catalog_imports import import_catalogue_rows


class Command(BaseCommand):
    help = "Load catalogue data and estimated opening balances"

    def add_arguments(self, parser):
        parser.add_argument("csv", type=str)
        parser.add_argument("--actor-id", required=True, help="Existing ADMIN account UUID")
        parser.add_argument(
            "--request-key",
            required=True,
            help="Stable UUID to make this import safe to retry",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing product metadata without changing stock",
        )

    def handle(self, *args, **options):
        file_path = settings.BASE_DIR / options["csv"]
        if not os.path.isfile(file_path):
            raise CommandError(f"CSV file not found: {file_path}")
        try:
            actor = Account.objects.get(
                pk=options["actor_id"],
                is_active=True,
                user_type="ADMIN",
            )
            request_key = UUID(options["request_key"])
        except (Account.DoesNotExist, ValidationError, ValueError) as error:
            raise CommandError(
                "Provide a valid active ADMIN UUID and request key."
            ) from error

        try:
            with open(file_path, encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            operation = import_catalogue_rows(
                actor=actor,
                request_key=request_key,
                rows=rows,
                update_existing=options["update_existing"],
            )
        except (OSError, csv.Error, ValidationError) as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(f"Catalogue import {operation.pk} completed.")
        )
