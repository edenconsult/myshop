from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
import csv
from core.models import Product


class Command(BaseCommand):
    help = "Load shop data"

    def add_arguments(self, parser):
        parser.add_argument("csv", type=str)

    def handle(self, *args, **options):
        if os.path.isfile(settings.BASE_DIR / options["csv"]):
            file_path = settings.BASE_DIR / options["csv"]
            with open(file_path) as file:
                csv_reader = csv.DictReader(file)
                counter = 0
                for row in csv_reader:
                    try:
                        # print(row['PRODUCT '], row['COST PRICE '],
                        #     row['SELLING PRICE '])
                        profit_rate = (
                            (
                                abs(float(row["SELLING PRICE"]))
                                / abs(float(row["COST PRICE"]))
                            )
                            if abs(float(row["COST PRICE"])) > 0
                            else 0
                        )
                        product = Product(
                            name=row["PRODUCT"],
                            stock=row["QUANTITY"],
                            cost=row["COST PRICE"],
                            price=row["SELLING PRICE"],
                            profit_rate=profit_rate,
                            # slug=slugify(row['PRODUCT'])
                        )
                        product.save()
                    except Exception as e:
                        print(e)
                    else:
                        counter += 1
            self.stdout.write(
                self.style.SUCCESS(f"{counter} products has been loaded.")
            )
