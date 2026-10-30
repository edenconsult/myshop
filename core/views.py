from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.db.models import F, Sum, ExpressionWrapper, DecimalField, Prefetch
from decimal import Decimal

from authapp.models import Account
from .models import Product, Order, OrderItem
from utils import generate_code, is_admin, render_attached_pdf
import io
from .tasks import import_products_task, remove_products_task
from celery.result import AsyncResult
from celery_progress.backend import Progress
import csv
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from .forms import ProductCreationForm
import json
import datetime as dt
from django.utils import timezone
from django.db.models import QuerySet
from django_htmx.http import trigger_client_event
from django.views.decorators.http import require_POST


@login_required
@user_passes_test(is_admin)
def index(request):
    return render(request, "core/index.html")


@login_required
@user_passes_test(is_admin)
def products_home(request):
    products = Product.objects.all()
    context = {
        "products": products,
    }
    return render(request, "core/products/products.html", context)


@login_required
@user_passes_test(is_admin)
def load_products(request):
    limit = request.GET.get("l")
    page = request.GET.get("p")
    search_term = request.GET.get("s") if request.GET.get("s") is not None else ""

    if limit is not None:
        limit = int(limit)

    products = Product.objects.all().order_by("-created")
    if search_term != "":
        products = products.filter(Q(name__icontains=search_term)).order_by("-created")

    paginator = Paginator(object_list=products, per_page=limit)

    if page is None:
        page = 1

    page_obj = paginator.get_page(page)

    starting_number = 1
    stopping_number = limit

    if page_obj.has_previous():
        starting_number = page_obj.previous_page_number() * limit
        stopping_number = starting_number + limit

    pages = [
        {"number": page, "allow": type(page) == int}
        for page in list(page_obj.paginator.get_elided_page_range())  # type: ignore
    ]

    context = {
        "page_obj": page_obj,
        "number_of_products": products.count(),
        "starting_number": starting_number,
        "stopping_number": stopping_number,
        "limit": limit,
        "search_term": search_term,
        "pages": pages,
    }
    return render(request, "core/partials/table_search.html", context)


@require_POST
@login_required
@user_passes_test(is_admin)
def update_product_stock(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    stock = request.POST.get("stock")

    try:
        product.stock = int(stock)
    except (TypeError, ValueError):
        context = {
            "type": "danger",
            "message": "Stock must be a whole number.",
        }
        return render(request, "core/products/response.html", context)

    product.save()
    context = {"product": product}
    return render(request, "core/partials/product_table_row.html", context)


@login_required
@user_passes_test(is_admin)
def import_products(request):
    context = {}
    return render(
        request,
        "core/products/import_products.html",
        context,
    )


@require_POST
@login_required
@user_passes_test(is_admin)
def do_import_products(request):
    if bool(request.FILES.get("file")):
        file = io.TextIOWrapper(request.FILES.get("file"))
        csv_reader = csv.DictReader(file)
        rows = [row for row in csv_reader if row.get("PRODUCT") != ""]

        import_task = import_products_task.delay(rows)  # type: ignore
        task_id = import_task.task_id
        progress = Progress(AsyncResult(task_id))
        info = progress.get_info()
        context = {
            "task_id": task_id,
            "info": info,
        }
        return render(request, "core/products/import_products_progress.html", context)
    else:
        context = {"error": "No file submitted"}

        return render(
            request,
            "core/products/import_products.html",
            context,
        )


@login_required
@user_passes_test(is_admin)
def track_import_progress(request, task_id):
    progress = Progress(AsyncResult(task_id))
    info = progress.get_info()

    context = {
        "task_id": task_id,
        "info": info,
    }
    response = render(request, "core/products/import_products_progress.html", context)
    if not info["complete"]:
        return response

    return trigger_client_event(response, "reload_products_table")


@login_required
@user_passes_test(is_admin)
def remove_all_products(request):
    context = {}
    return render(request, "core/products/remove_products_question.html", context)


@login_required
@user_passes_test(is_admin)
def track_remove_product_progress(request, task_id):
    progress = Progress(AsyncResult(task_id))
    info = progress.get_info()

    context = {
        "task_id": task_id,
        "info": info,
    }
    response = render(request, "core/products/remove_products_progress.html", context)
    if not info["complete"]:
        return response

    return trigger_client_event(response, "reload_products_table")


@login_required
@user_passes_test(is_admin)
def get_product_action_buttons(request):
    return render(request, "core/partials/product_action_buttons.html")


@login_required
@user_passes_test(is_admin)
def remove_all_products_question(request):
    context = {"ids": []}
    if request.method == "POST":
        context["ids"] = request.POST.getlist("ids")
    return render(request, "core/products/remove_all_products_question.html", context)


@login_required
@user_passes_test(is_admin)
def do_remove_products(request):
    ids = []
    if request.method == "POST":
        if request.POST.getlist("ids") is not None:
            ids = request.POST.getlist("ids")

    remove_task = remove_products_task.delay(ids)  # type: ignore
    task_id = remove_task.task_id
    progress = Progress(AsyncResult(task_id))
    info = progress.get_info()

    context = {
        "task_id": task_id,
        "info": info,
        "selected_removal": len(ids) > 0,
        "count": len(ids) if len(ids) > 0 else Product.objects.count(),
    }
    return render(request, "core/products/remove_products_progress.html", context)


@login_required
@user_passes_test(is_admin)
def add_product(request):
    form_title = "Enter new product details below"
    form = ProductCreationForm()
    if request.method == "POST":
        form = ProductCreationForm(request.POST)

        if form.is_valid():
            try:
                product = form.save(commit=False)

                if int(form.cleaned_data["cost"]) > 0:
                    product.profit_rate = abs(int(form.cleaned_data["cost"])) / abs(
                        int(form.cleaned_data["price"])
                    )
                else:
                    product.profit_rate = 0
                product.save()
            except Exception as e:
                print(e)
                context = {
                    "type": "danger",
                    "message": "New product could not be saved. Try again later.",
                }
                return render(request, "core/products/response.html", context)
            else:
                context = {
                    "type": "success",
                    "message": "New product successfully saved.",
                }
                response = render(request, "core/products/response.html", context)
                return trigger_client_event(response, "reload_products_table")

    context = {"form": form, "form_title": form_title}
    return render(request, "core/products/new_product.html", context)


@login_required
@user_passes_test(is_admin)
def update_product(request, product_id):
    form_title = "Update product details below"
    product = Product.objects.get(pk=product_id)
    form = ProductCreationForm(instance=product)
    if request.method == "POST":
        form = ProductCreationForm(request.POST, instance=product)
        if form.is_valid():
            try:
                product = form.save(commit=False)
                if int(form.cleaned_data["cost"]) > 0:
                    product.profit_rate = abs(int(form.cleaned_data["cost"])) / abs(
                        int(form.cleaned_data["price"])
                    )
                else:
                    product.profit_rate = 0
                product.save()
            except Exception as e:
                print(e)
                context = {
                    "type": "danger",
                    "message": "The product's update could not be saved. Try again later.",  # noqa: E501
                }
                return render(request, "core/products/response.html", context)
            else:
                context = {
                    "type": "success",
                    "message": "Product successfully updated.",
                }
                response = render(request, "core/products/response.html", context)
                return trigger_client_event(response, "reload_products_table")

    context = {"form": form, "form_title": form_title, "product": product}
    return render(request, "core/products/new_product.html", context)


@login_required
@user_passes_test(is_admin)
def remove_a_product_question(request, product_id):
    product = Product.objects.get(pk=product_id)
    context = {"product": product}
    return render(request, "core/products/remove_a_product_question.html", context)


@login_required
@user_passes_test(is_admin)
def do_remove_a_product(request, product_id):
    product = Product.objects.get(pk=product_id)
    product.delete()
    context = {
        "type": "success",
        "message": f"Product '{product}' successfully removed.",
        "product": product,
    }
    response = render(request, "core/products/response.html", context)
    return trigger_client_event(response, "reload_products_table")


@login_required
@user_passes_test(is_admin)
def orders(request):
    context = {}
    return render(request, "core/orders/orders.html", context)


@login_required
@user_passes_test(is_admin)
def products_summary(request):
    money_field = DecimalField(max_digits=12, decimal_places=2)
    totals = Product.objects.aggregate(
        sum_stock=Sum("stock"),
        sum_cost=Sum(F("cost") * F("stock"), output_field=money_field),
        sum_sales=Sum(F("price") * F("stock"), output_field=money_field),
    )

    if totals["sum_sales"] is not None and totals["sum_cost"] is not None:
        profit = round(float(totals["sum_sales"]) - float(totals["sum_cost"]), 2)
    else:
        profit = 0

    context = {
        "stock_sum": totals["sum_stock"] if totals["sum_stock"] is not None else 0,
        "cash_invested": totals["sum_cost"] if totals["sum_cost"] is not None else 0,
        "after_orders": totals["sum_sales"] if totals["sum_sales"] is not None else 0,
        "profit": profit,
    }
    return render(request, "core/products/summary.html", context)


@login_required
@user_passes_test(is_admin)
def orders_products(request):
    products = Product.objects.filter(Q(stock__gt=0)).order_by("name")

    paginator = Paginator(products, 10)

    page_obj = paginator.get_page(1)
    context = {
        "page_obj": page_obj,
    }
    return render(request, "core/orders/products_for_sale_table.html", context)


@login_required
@user_passes_test(is_admin)
def load_orders_products(request):
    products = Product.objects.filter(Q(stock__gt=0)).order_by("name")

    page = 1
    if request.GET.get("p") is not None and request.GET.get("p") != "":
        page = int(request.GET.get("p"))

    if request.GET.get("s") is not None and request.GET.get("s") != "":
        products = products.filter(Q(name__icontains=request.GET.get("s"))).order_by(
            "name"
        )

    paginator = Paginator(products, 10)

    page_obj = paginator.get_page(page)

    context = {"page_obj": page_obj}
    return render(request, "core/orders/products_with_stocks_table_rows.html", context)


@require_POST
@login_required
@user_passes_test(is_admin)  # type: ignore
def make_order(request):
    items = [json.loads(item) for item in request.POST.getlist("items")]

    if len(items) == 0:
        msg_type = "danger"
        message = "No items in the cart. Add items to the cart and make payment."
        context = {"type": msg_type, "message": message}
        return render(request, "core/orders/order_made.html", context)

    order_obj = None
    try:
        with transaction.atomic():
            # fetch all products at once, locking their rows for the duration
            # of the transaction so two parallel sales cannot oversell stock
            products = {
                str(product.id): product
                for product in Product.objects
                .select_for_update()
                .filter(id__in=[item.get("id") for item in items])
            }

            order_errors = []
            new_order_items = []
            for item in items:
                product = products.get(str(item.get("id")))
                qty = int(item.get("qty", 0))

                # if the product does not exist
                if product is None:
                    order_errors.append(
                        {"item": item, "error": f"Product {item.get('id')} not found"}
                    )
                    continue

                # else if stock is less than the required quantity
                if qty > product.stock:
                    continue

                # else if the calculated total price send is wrong,
                if float(item.get("total_price")) != float(product.price * qty):
                    order_errors.append(
                        {
                            "item": item,
                            "error": f"Product {product} items calculation was wrong",  # noqa: E501
                        }
                    )
                    continue

                # if item passed the product checks
                new_order_items.append({"product": product, "item": item, "qty": qty})

            if len(items) != len(new_order_items):
                raise ValueError("Order validation failed")

            # create new order
            order_obj = Order.objects.create(
                user=request.user, code=generate_code(max_length=6)
            )

            # insert every order item in a single query
            OrderItem.objects.bulk_create(
                OrderItem(
                    order=order_obj,
                    product=entry["product"],
                    qty_bought=entry["qty"],
                    paid_amount=Decimal(str(entry["item"].get("total_price"))),
                )
                for entry in new_order_items
            )

            # update each product's stock to reflect the last order
            for entry in new_order_items:
                entry["product"].stock -= entry["qty"]
            Product.objects.bulk_update(
                (entry["product"] for entry in new_order_items),
                ["stock"],
                batch_size=100,
            )

            # update overall amount paid in this order
            order_obj.overall_amount_paid = sum(
                Decimal(str(item.get("total_price"))) for item in items
            )
            order_obj.save(update_fields=["overall_amount_paid", "updated"])
    except ValueError:
        # one or more items failed validation, nothing was saved
        message = "Something went wrong. Your order could not be initiated."
        msg_type = "danger"
        context = {"type": msg_type, "message": message}
        return render(request, "core/orders/order_made.html", context)
    except Exception:
        # if anything goes wrong, all changes will be reversed.
        message = "Your order was not successfully. Try again at a later time."
        msg_type = "danger"
        context = {"type": msg_type, "message": message}
        return render(request, "core/orders/order_made.html", context)

    # order was successful
    today = dt.date.today()
    date_start = timezone.make_aware(
        dt.datetime(year=today.year, month=today.month, day=today.day, hour=6)
    )
    date_end = timezone.make_aware(
        dt.datetime(year=today.year, month=today.month, day=today.day, hour=20)
    )
    order_number = Order.objects.filter(
        Q(user=request.user),
        Q(created__gte=date_start),
        Q(created__lt=date_end),
    ).count()
    message = f"Order Number {order_obj.code} totaling GHs {order_obj.overall_amount_paid:.2f} was successful. Thank you."  # noqa: E501
    msg_type = "success"
    context = {
        "type": msg_type,
        "message": message,
        "order": order_obj,
        "order_number": order_number,
    }
    response = render(request, "core/orders/order_made.html", context)
    return trigger_client_event(response, "reload_products_with_stocks")


@login_required
@user_passes_test(is_admin)
def shop_cart(request):
    return render(request, "core/orders/cart_table.html")


@login_required
@user_passes_test(is_admin)
def get_todays_orders(request):
    return render(request, "core/orders/cart_table.html")


@login_required
@user_passes_test(is_admin)
def out_of_stock(request):
    products = Product.objects.filter(Q(stock=0)).order_by("name")

    paginator = Paginator(products, 10)

    page_obj = paginator.get_page(1)
    context = {
        "page_obj": page_obj,
    }
    return render(request, "core/products/out_of_stock.html", context)


@login_required
@user_passes_test(is_admin)
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
    return render(request, "core/products/out_of_stock_items.html", context)


def retrieve_todays_sale(
    date,
    user=None,
):
    order_list = None
    if user is None:
        order_list = Order.objects.filter(
            Q(created__day=date.day),
            Q(created__month=date.month),
        ).order_by("created")
    else:
        order_list = Order.objects.filter(
            Q(user=user),
            Q(created__day=date.day),
            Q(created__month=date.month),
        ).order_by("created")
    aggregated = order_list.aggregate(sum_total=Sum("overall_amount_paid"))

    return order_list, aggregated["sum_total"]


@login_required
@user_passes_test(is_admin)
def today_orders(request):
    created_order_dates = (
        Order.objects.values("created")
        .distinct("created__day")
        .order_by("-created__day")
    )
    dates = [
        dt.date(
            year=created_dates["created"].year,
            month=created_dates["created"].month,
            day=created_dates["created"].day,
        )
        for created_dates in created_order_dates
    ]
    context = {"dates": dates, "users": Account.objects.all()}
    return render(request, "core/orders/todays_orders.html", context)


@require_POST
@login_required
@user_passes_test(is_admin)
def fetch_days_orders(request):
    date = request.POST.get("order_date")
    users = request.POST.get("users")

    today = dt.datetime.strptime(date, "%Y-%m-%d")
    orders, sum_total = retrieve_todays_sale(user=None, date=today)
    if users != "all":
        users = Account.objects.get(pk=users)
        # order_lists = order_lists.filter(user=users)
        orders, sum_total = retrieve_todays_sale(user=users, date=today)

    context = {
        "orders": orders,
        "todays_total_orders": sum_total,
        "date": date,
        "users": users,
    }
    return render(request, "core/orders/all_orders.html", context)


@login_required
@user_passes_test(is_admin)
def print_todays_orders(request, date, users):
    today = dt.datetime.strptime(date, "%Y-%m-%d")

    orders, sum_total = retrieve_todays_sale(user=None, date=today)

    if users != "all":
        users = Account.objects.get(username=users)
        orders, sum_total = retrieve_todays_sale(user=users, date=today)

    context = {
        "orders": orders,
        "todays_total_orders": sum_total,
        "users": users,
        "date": today,
    }

    todays_date = f"{today:%d%m%Y}"
    filename = "Sale_%s.pdf" % (todays_date)

    pdf = render_attached_pdf(
        relative_template_path="core/orders/prints/todays_sales.html",
        context=context,
        file_name=filename,
        # css=css
    )

    return pdf


@login_required
@user_passes_test(is_admin)
def view_order(request, order_id, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related(
            Prefetch(
                "orderitem_set",
                queryset=OrderItem.objects.select_related("product"),
            )
        ),
        id=order_id,
    )
    context = {"order": order, "order_number": order_number}
    return render(request, "core/orders/order_details.html", context)


@login_required
@user_passes_test(is_admin)
def print_order_pdf(request, order_id, order_number):
    order = Order.objects.get(id=order_id)
    context = {"order": order, "order_number": order_number}
    today = dt.datetime.now()
    todays_date = f"{today:%d%m%Y%H%M%S}"
    filename = f"Invoice-{order.code}-{todays_date}.pdf"
    pdf = render_attached_pdf(
        relative_template_path="core/orders/prints/order_details.html",
        context=context,
        file_name=filename,
    )
    return pdf


@login_required
@user_passes_test(is_admin)
def retrive_reports(request):
    today = dt.date.today()
    this_week_number = today.isocalendar().week
    this_year_number = today.year
    week_start = dt.date.fromisocalendar(this_year_number, this_week_number, 1)
    week_end = week_start + dt.timedelta(days=6)

    start_date = f"{week_start:%Y-%m-%d}"
    end_date = f"{week_end:%Y-%m-%d}"
    users = Account.objects.all()
    return render(
        request,
        "core/orders/sales_reports.html",
        {"start_date": start_date, "end_date": end_date, "users": users},
    )


def generate_reports(order_list):
    orderitems = OrderItem.objects.filter(order__in=order_list)

    money_field = DecimalField(max_digits=14, decimal_places=2)

    total_cost_expr = ExpressionWrapper(
        F("qty_bought") * F("product__cost"),
        output_field=money_field,
    )

    total_sold_expr = ExpressionWrapper(
        F("qty_bought") * F("product__price"),
        output_field=money_field,
    )

    total_profit_expr = ExpressionWrapper(
        F("qty_bought") * (
            F("product__price") - F("product__cost")
        ),
        output_field=money_field,
    )

    orderitems_summary = orderitems.aggregate(
        total_cost=Sum(total_cost_expr),
        total_sold=Sum(total_sold_expr),
        stock_sold=Sum("qty_bought"),
        total_profit=Sum(total_profit_expr),
    )

    order_items = (
        orderitems.values("product__name")
        .annotate(
            sum_qty=Sum("qty_bought"),
            amount=Sum("paid_amount"),
        )
        .order_by("-sum_qty")
    )

    return {
        "total_cost": orderitems_summary["total_cost"] or Decimal("0.00"),
        "total_sold": orderitems_summary["total_sold"] or Decimal("0.00"),
        "stock_sold": orderitems_summary["stock_sold"] or 0,
        "profit": orderitems_summary["total_profit"] or Decimal("0.00"),
        "items": order_items,
    }



@require_POST
@login_required
@user_passes_test(is_admin)
def retrive_reports_by_duration(request):
    duration = "weekly"
    if request.POST.get("duration") != "":
        duration = request.POST.get("duration")
    today = dt.date.today()
    order_lists = []
    if duration == "weekly":
        this_week_number = today.isocalendar().week
        this_year_number = today.year
        week_start_date = dt.date.fromisocalendar(this_year_number, this_week_number, 1)
        week_end_date = week_start_date + dt.timedelta(days=7)
        week_start = dt.date(
            year=today.year, month=today.month, day=week_start_date.day
        )
        week_end = dt.date(year=today.year, month=today.month, day=week_end_date.day)
        order_lists = Order.objects.filter(created__range=(week_start, week_end))
    elif duration == "monthly":
        # month_start = dt.date(year=today.year, month=today.month, day=1)
        # _, number_of_days = cal.monthrange(year=today.year, month=today.month)
        # month_end = month_start + dt.timedelta(days=number_of_days - 1)
        # print(month_start, month_end)
        order_lists = Order.objects.filter(created__month=today.month)
    elif duration == "yearly":
        order_lists = Order.objects.filter(created__year=today.year)
    else:
        order_lists = Order.objects.filter(
            created__day=today.day,
            created__month=today.month,
            created__year=today.year,
        )

    summary = generate_reports(order_lists)
    return render(
        request,
        "core/orders/report.html",
        {
            "summary": summary,
        },
    )


@require_POST
@login_required
@user_passes_test(is_admin)
def retrive_reports_by_dates(request):
    start_date_str = request.POST.get("date_start")
    end_date_str = request.POST.get("date_end")
    users = request.POST.get("users")
    start_date = None
    end_date = None
    order_lists: QuerySet[Order] = []
    summary = None

    if start_date_str != "":
        start_date = timezone.make_aware(
            dt.datetime.strptime(start_date_str, "%Y-%m-%d") + dt.timedelta(hours=6)
        )

    if end_date_str != "":
        end_date = timezone.make_aware(dt.datetime.strptime(end_date_str, "%Y-%m-%d"))

    if start_date is not None and end_date is not None:
        order_lists = Order.objects.filter(
            Q(created__date__gte=start_date.date()),
            Q(created__date__lte=end_date.date()),
        )
    if users != "all":
        users = Account.objects.get(pk=users)
        order_lists = order_lists.filter(user=users)

    summary = generate_reports(order_list=order_lists)

    return render(
        request,
        "core/orders/report.html",
        {
            "summary": summary,
            "start_date": start_date.date(),
            "end_date": end_date.date(),
            "users": users,
        },
    )


@login_required
@user_passes_test(is_admin)
def retrive_reports_print(request, start_date, end_date, users):
    today = dt.datetime.now()
    todays_date = f"{today:%d%m%Y%H%M%S}"
    filename = "Reports_%s.pdf" % (todays_date)
    context = None
    if start_date is not None and end_date is not None:
        order_lists = Order.objects.filter(created__range=(start_date, end_date))

        if users != "all":
            users = Account.objects.get(username=users)
            order_lists = order_lists.filter(user=users)
        context = generate_reports(order_list=order_lists)

        context["start_date"] = dt.datetime.strptime(start_date, "%Y-%m-%d")
        context["end_date"] = dt.datetime.strptime(end_date, "%Y-%m-%d")
        context["users"] = users

    pdf = render_attached_pdf(
        relative_template_path="core/orders/prints/all_reports.html",
        context=context,
        file_name=filename,
    )

    return pdf
