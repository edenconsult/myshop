from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render
from core.models import Product, Order, OrderItem
import io
from celery_progress.backend import Progress
import csv
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
import json
import datetime as dt
from django.utils import timezone
from django.views.decorators.http import require_POST
from utils import generate_code, is_sale_person, render_attached_pdf


@login_required
@user_passes_test(is_sale_person)
def index(request):
    return render(request, "sales/index.html")


@login_required
@user_passes_test(is_sale_person)
def orders_products(request):
    products = Product.objects.filter(Q(stock__gt=0)).order_by("name")

    paginator = Paginator(products, 10)

    page_obj = paginator.get_page(1)
    context = {
        "page_obj": page_obj,
    }
    return render(request, "sales/orders/products_for_sale_table.html", context)


@login_required
@user_passes_test(is_sale_person)
def load_orders_products(request):
    products = Product.objects.filter(Q(stock__gt=0)).order_by("name")

    if request.GET.get("p") is not None and request.GET.get("p") != "":
        page = int(request.GET.get("p"))

    if request.GET.get("s") is not None and request.GET.get("s") != "":
        products = products.filter(Q(name__icontains=request.GET.get("s"))).order_by(
            "name"
        )

    paginator = Paginator(products, 10)

    page_obj = paginator.get_page(page)

    context = {"page_obj": page_obj}
    return render(request, "sales/orders/products_with_stocks_table_rows.html", context)


@require_POST
@login_required
@user_passes_test(is_sale_person)
def make_order(request):
    items = [json.loads(item) for item in request.POST.getlist("items")]

    if len(items) == 0:
        msg_type = "danger"
        message = "No items in the cart. Add items to the cart and make payment."
        context = {"type": msg_type, "message": message}
        return render(request, "sales/orders/order_made.html", context)

    new_order_items = []
    order_errors = []
    # check order items
    for item in items:
        product_check_valid = True
        product = Product.objects.get(id=item.get("id"))

        # if the product does not exist
        if product is None:
            product_check_valid = False
            order_errors.append(
                {"item": item, "error": f"Product {item.get('id')} not found"}
            )

        # else if stock is less than the required quantity
        elif int(item.get("qty")) > product.stock:
            product_check_valid = False
            order_errors.append(
                {
                    "item": item,
                    "error": f"Product {item.get('id')}'s is less than the quantity needed.",
                }
            )

        # else if the calculated total price send is wrong,
        elif float(item.get("total_price")) != float(
            product.price * int(item.get("qty"))
        ):
            product_check_valid = False
            order_errors.append(
                {
                    "item": item,
                    "error": f"Product {product} items calculation was wrong",
                }
            )

        # if item passed the product checks
        if product_check_valid is False:
            print(order_errors)
        else:
            new_order_items.append({"product": product, "item": item})

    if len(items) != len(new_order_items):
        message = "Something weitemsnt wrong. Your order could not be initiated."
        context = {"type": "danger", "message": message}
        return render(request, "sales/orders/order_made.html", context)

    with transaction.atomic():
        try:
            # create new order
            order_obj = Order.objects.create(
                user=request.user, code=generate_code(max_length=6)
            )
            for ordItem in new_order_items:
                OrderItem.objects.create(
                    order=order_obj,
                    product=ordItem["product"],
                    qty_bought=int(ordItem["item"].get("qty")),
                    paid_amount=float(ordItem["item"].get("total_price")),
                )

                # update each product's stock to reflect the last order
                ordItem["product"].stock -= int(ordItem["item"].get("qty"))
                ordItem["product"].save()

            # update overall amount paid in this order
            order_obj.overall_amount_paid = sum(
                float(item.get("total_price")) for item in items
            )
            order_obj.save()
        except Exception:
            # if anything goes wrong, all changes will be reversed.
            message = "Your order was not successfully. Try again at a later time."
            msg_type = "danger"
        else:
            # order was successful
            today = dt.date.today()
            date_start = timezone.make_aware(
                dt.datetime(year=today.year, month=today.month, day=today.day, hour=6)
            )
            date_end = timezone.make_aware(
                dt.datetime(year=today.year, month=today.month, day=today.day, hour=20)
            )
            order_list = Order.objects.filter(
                Q(user=request.user),
                Q(created__gte=date_start),
                Q(created__lt=date_end),
            ).order_by("created")
            order_number = len(order_list)
            message = f"Order Number {order_obj.code} totaling GHs {order_obj.overall_amount_paid:.2f} was successful. Thank you."  # noqa: E501
            msg_type = "success"
            context = {
                "type": msg_type,
                "message": message,
                "order": order_obj,
                "order_number": order_number,
            }
            response = render(request, "sales/orders/order_made.html", context)
            response["HX-TRIGGER"] = "reload_products_with_stocks"
            return response

    context = {"type": msg_type, "message": message}
    return render(request, "sales/orders/order_made.html", context)


@login_required
@user_passes_test(is_sale_person)
def shop_cart(request):
    return render(request, "sales/orders/cart_table.html")


@login_required
@user_passes_test(is_sale_person)
def get_todays_orders(request):
    return render(request, "sales/orders/cart_table.html")


@login_required
@user_passes_test(is_sale_person)
def out_of_stock(request):
    products = Product.objects.filter(Q(stock=0)).order_by("name")

    paginator = Paginator(products, 10)

    page_obj = paginator.get_page(1)
    context = {
        "page_obj": page_obj,
    }
    return render(request, "sales/products/out_of_stock.html", context)


@login_required
@user_passes_test(is_sale_person)
def load_out_of_stock(request):
    products = Product.objects.filter(Q(stock=0)).order_by("name")

    page = None
    # if page is set
    if request.GET.get("p") is not None and request.GET.get("p") != "":
        page = int(request.GET.get("p"))
    else:
        page = 1

    # if search term is set
    if request.GET.get("s") is not None and request.GET.get("s") != "":
        products = products.filter(Q(name__icontains=request.GET.get("s"))).order_by(
            "name"
        )

    paginator = Paginator(products, 10)

    page_obj = paginator.get_page(page)

    context = {"page_obj": page_obj}
    return render(request, "sales/products/out_of_stock_items.html", context)


def retrieve_todays_sale(user, today):
    date_start = timezone.make_aware(
        dt.datetime(year=today.year, month=today.month, day=today.day, hour=6)
    )
    date_end = timezone.make_aware(
        dt.datetime(year=today.year, month=today.month, day=today.day, hour=22)
    )

    order_list = Order.objects.filter(
        Q(user=user), Q(created__gte=date_start), Q(created__lt=date_end)
    ).order_by("created")

    aggregated = order_list.aggregate(sum_total=Sum("overall_amount_paid"))

    return order_list, aggregated["sum_total"]


@login_required
@user_passes_test(is_sale_person)
def today_orders(request):
    today = dt.date.today()
    orders, sum_total = retrieve_todays_sale(request.user, today)

    context = {"orders": orders, "todays_total_orders": sum_total}
    return render(request, "sales/orders/todays_orders.html", context)


@login_required
@user_passes_test(is_sale_person)
def print_todays_orders(request):
    today = dt.date.today()

    orders, sum_total = retrieve_todays_sale(request.user, today)

    context = {"orders": orders, "todays_total_orders": sum_total}

    todays_date = f"{today:%d%m%Y}"
    filename = "Sale_%s.pdf" % (todays_date)
    pdf = render_attached_pdf(
        relative_template_path="sales/orders/prints/todays_sales.html",
        context=context,
        file_name=filename,
    )
    return pdf


@login_required
@user_passes_test(is_sale_person)
def view_order(request, order_id, order_number):
    # order_stock = Order.objects.aggregate(sum_stock = Sum('orderitem__stock'))
    order = Order.objects.get(id=order_id)
    context = {"order": order, "order_number": order_number}
    return render(request, "sales/orders/order_details.html", context)


@login_required
@user_passes_test(is_sale_person)
def print_order_pdf(request, order_id, order_number):
    order = Order.objects.get(id=order_id)
    context = {"order": order, "order_number": order_number}
    filename = "Invoice_%s.pdf" % (order_id)
    pdf = render_attached_pdf(
        relative_template_path="sales/orders/prints/order_details.html",
        context=context,
        file_name=filename,
    )
    return pdf
