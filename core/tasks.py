

from typing import Optional
from xml.etree.ElementTree import QName
from celery import shared_task
from celery_progress.backend import ProgressRecorder
import time
from core.models import Order, Product


@shared_task(bind=True)
def import_products_task(self, rows: list[dict]):
    progress_recorder = ProgressRecorder(self)
    total_rows = len(rows)
    count = 0
    print(total_rows)
    for row in rows:
        try:
            profit_rate = 0
            cost = 0
            price = 0
            if row['COST PRICE'] != '' or row['COST PRICE'] != ' ':
                cost = float(row['COST PRICE']) 

            if row['SELLING PRICE'] != '' or row['SELLING PRICE'] != ' ':
                price = float(row['SELLING PRICE'])
            stock = int(row['QUANTITY'])

            if cost != 0:
                profit_rate = (abs(price) / abs(cost))

            product = Product(name=row['PRODUCT'],
                              stock=stock,
                              cost=cost,
                              price=price,
                              profit_rate=profit_rate)

            product.save()
        except Exception as e:
            print(e)
        else:
            count += 1
            progress_recorder.set_progress(
                current=(count / total_rows) * 100, 
                total=100, 
                description=f"{count} items out of {total_rows} products imported"
            )
    return 'Done'


@shared_task(bind=True)
def remove_products_task(self, ids: list[str]):
    progress_recorder = ProgressRecorder(self)
    products = Product.objects.all()
    if len(ids) > 0:
        products = Product.objects.filter(pk__in=ids)
        
    number_of_products = len(products)
    count = 0
    
    for product in products:
        try:
            product.delete()
            Order.objects.filter(orderitem__product=product).delete()
        except Exception as e:
            print(e)
        else:
            count += 1
            progress_recorder.set_progress(
                current=(count / number_of_products) * 100, 
                total=100, 
                description=f"{count} out of {number_of_products} products removed"
            )
    return 'Done'
