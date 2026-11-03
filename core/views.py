from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, render
from django.db.models import (
    Case,
    Count,
    ExpressionWrapper,
    F,
    OuterRef,
    Prefetch,
    Subquery,
    Sum,
    When,
    DecimalField,
)
from django.http import HttpResponse
from decimal import Decimal
from uuid import UUID, uuid4

from authapp.models import Account
from .catalog_imports import PROFIT_RATE_MAX
from .checkout import SaleLine, checkout
from .inventory import ReceiptLine, adjust_batch, receive_stock
from .models import Product, ProductCategory, Order, OrderItem, StockBatch, StockReceiptSource
from utils import (
    can_ring_up,
    is_admin,
    parse_cart,
    render_attached_pdf,
    static_image_data_uri,
)
import io
import logging
from .tasks import (
    import_products_task,
    remove_products_task,
)
from celery.result import AsyncResult
from celery_progress.backend import Progress
import csv
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import ProductCreationForm
import math
import datetime as dt
from django.conf import settings
from django.utils import timezone
from django_htmx.http import trigger_client_event
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)

# the register grid is 2/3/4 columns wide, so a page fills every column
POS_PAGE_SIZE = 12

LEDGER_PAGE_SIZE = 10

# how many names the bulk-removal dialog lists before falling back to a count
REMOVAL_SAMPLE_SIZE = 6

MONEY_FIELD = DecimalField(max_digits=24, decimal_places=2)


def _posted_request_key(request):
    raw_key = request.POST.get("request_key")
    if not raw_key:
        return uuid4()
    try:
        return UUID(raw_key)
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError({"request_key": "Enter a valid request key."}) from error


# the ledger's Margin column is gross margin on revenue: (retail - cost) /
# retail, the same figure the add and restock dialogs show. price = 0 is
# quarantined in the CASE so a free sample cannot divide by zero. The alias
# cannot be "margin" -- that name is taken by Product.margin, which has no
# setter -- because sorting needs a column the database can order on.
LEDGER_MARGIN_SQL = ExpressionWrapper(
    Case(
        When(
            price__gt=0,
            then=(F("price") - F("cost")) / F("price") * 100,
        ),
        default=Decimal("0.00"),
        output_field=MONEY_FIELD,
    ),
    output_field=MONEY_FIELD,
)

LEDGER_SORTS = {
    "updated": ["-updated"],
    "stock_asc": ["stock", "-updated"],
    "stock_desc": ["-stock", "-updated"],
    "price_desc": ["-price"],
    "margin_desc": ["-ledger_margin"],
}

LEDGER_STATUSES = {"all", "in_stock", "low", "out_of_stock", "alert"}


@login_required
@user_passes_test(can_ring_up)
def index(request):
    if not is_admin(request.user):
        return render(
            request, "core/orders/register_screen.html", register_context(request)
        )

    today = timezone.localdate()
    yesterday = today - dt.timedelta(days=1)

    todays_orders = Order.objects.filter(created__date=today)
    today_sales = todays_orders.aggregate(total=Sum("overall_amount_paid"))["total"] or Decimal("0.00")
    yesterday_sales = (
        Order.objects.filter(created__date=yesterday).aggregate(
            total=Sum("overall_amount_paid")
        )["total"]
        or Decimal("0.00")
    )

    if yesterday_sales > 0:
        sales_change = round(
            float((today_sales - yesterday_sales) / yesterday_sales * 100)
        )
    else:
        sales_change = None

    out_of_stock_products = Product.objects.filter(stock=0).order_by("name")
    out_of_stock_count = out_of_stock_products.count()

    recent_orders = (
        Order.objects.select_related("user")
        .prefetch_related(
            Prefetch(
                "orderitem_set",
                queryset=OrderItem.objects.select_related("product"),
            )
        )
        .order_by("-created")[:4]
    )

    cashier_rows = (
        todays_orders.values("user__first_name", "user__last_name", "user__username")
        .annotate(total=Sum("overall_amount_paid"))
        .order_by("-total")[:3]
    )
    cashier_sales = []
    for row in cashier_rows:
        name = f"{row['user__first_name']} {row['user__last_name']}".strip()
        cashier_sales.append(
            {
                "name": name or row["user__username"],
                "total": row["total"] or Decimal("0.00"),
            }
        )

    context = {
        "today_sales": today_sales,
        "sales_change": sales_change,
        "sales_change_positive": sales_change is not None and sales_change >= 0,
        "orders_today": todays_orders.count(),
        "products_listed": Product.objects.count(),
        "out_of_stock_count": out_of_stock_count,
        "restock_products": list(
            out_of_stock_products.values_list("name", flat=True)[:3]
        ),
        "recent_orders": recent_orders,
        "cashier_sales": cashier_sales,
    }
    return render(request, "core/index.html", context)


@login_required
@user_passes_test(is_admin)
def products_home(request):
    initial_view = request.GET.get("view", "")
    if initial_view not in {"add", "import", "out-of-stock"}:
        initial_view = ""

    context = {
        "initial_view": initial_view,
        "initial_status": "alert" if initial_view == "out-of-stock" else "all",
    }
    return render(request, "core/products/products.html", context)


@login_required
@user_passes_test(is_admin)
def load_products(request):
    limit = int(request.GET.get("l") or LEDGER_PAGE_SIZE)
    page = request.GET.get("p") or 1
    search_term = request.GET.get("s") or ""
    category = request.GET.get("c") or ""
    status = request.GET.get("status") or "all"
    sort = request.GET.get("sort") or "updated"

    products = Product.objects.annotate(ledger_margin=LEDGER_MARGIN_SQL)

    if search_term != "":
        products = products.filter(
            Q(name__icontains=search_term) | Q(sku__icontains=search_term)
        )
    if category in ProductCategory.values:
        products = products.filter(category=category)

    if status == "in_stock":
        products = products.filter(stock__gt=F("low_stock_threshold"))
    elif status == "low":
        products = products.filter(stock__gt=0, stock__lte=F("low_stock_threshold"))
    elif status == "out_of_stock":
        products = products.filter(stock=0)
    elif status == "alert":
        products = products.filter(stock__lte=F("low_stock_threshold"))

    products = products.order_by(*(LEDGER_SORTS.get(sort) or LEDGER_SORTS["updated"]))

    page_obj = Paginator(object_list=products, per_page=limit).get_page(page)
    total = products.count()

    starting_number = (page_obj.number - 1) * limit + 1
    stopping_number = min(page_obj.number * limit, total)

    pages = [
        {"number": number, "allow": type(number) is int}
        for number in list(page_obj.paginator.get_elided_page_range())  # type: ignore
    ]

    context = {
        "page_obj": page_obj,
        "number_of_products": total,
        "starting_number": starting_number,
        "stopping_number": stopping_number,
        "limit": limit,
        "search_term": search_term,
        "category": category,
        "categories": ProductCategory.choices,
        "status": status if status in LEDGER_STATUSES else "all",
        "sort": sort if sort in LEDGER_SORTS else "updated",
        "pages": pages,
    }
    return render(request, "core/partials/table_search.html", context)


@require_POST
@login_required
@user_passes_test(is_admin)
def update_product_stock(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    try:
        batch_id = UUID(request.POST.get("batch_id", ""))
        get_object_or_404(StockBatch, pk=batch_id, product=product)
        quantity_delta = int(request.POST.get("quantity_delta", ""))
        reason = request.POST.get("reason", "")
        request_key = _posted_request_key(request)
        adjust_batch(
            actor=request.user,
            request_key=request_key,
            batch_id=batch_id,
            quantity_delta=quantity_delta,
            reason=reason,
        )
    except (ValueError, ValidationError) as error:
        message = (
            error.messages[0]
            if isinstance(error, ValidationError)
            else "Select a batch and enter a whole-number correction."
        )
        return render(
            request,
            "core/partials/product_table_row.html",
            {"product": product, "error": message},
        )
    except DatabaseError:
        logger.exception("Stock adjustment failed for product %s", product.pk)
        return render(
            request,
            "core/partials/product_table_row.html",
            {"product": product, "error": "The stock correction could not be saved."},
        )
    product.refresh_from_db(fields=["stock"])
    context = {"product": product}
    return render(request, "core/partials/product_table_row.html", context)


@login_required
@user_passes_test(is_admin)
def import_products(request):
    context = {"sku_count": Product.objects.count()}
    return render(request, "core/products/modals/import_products.html", context)


@require_POST
@login_required
@user_passes_test(is_admin)
def do_import_products(request):
    upload = request.FILES.get("file")
    if not upload:
        return render(
            request,
            "core/products/modals/import_products.html",
            {"error": "Choose a .csv file to import."},
        )

    update_existing = request.POST.get("update_existing") == "on"

    try:
        # utf-8-sig: the dialog promises UTF-8 and Excel exports stamp a BOM
        csv_reader = csv.DictReader(io.TextIOWrapper(upload, encoding="utf-8-sig"))
        rows = list(csv_reader)
    except (UnicodeDecodeError, csv.Error):
        return render(
            request,
            "core/products/modals/import_products.html",
            {"error": "That file could not be read as a UTF-8 CSV."},
        )

    if not rows:
        return render(
            request,
            "core/products/modals/import_products.html",
            {"error": "No product rows found. A PRODUCT column is required."},
        )

    try:
        request_key = _posted_request_key(request)
    except ValidationError as error:
        return render(
            request,
            "core/products/modals/import_products.html",
            {"error": error.messages[0]},
        )

    import_task = import_products_task.delay(
        rows,
        update_existing,
        str(request.user.pk),
        str(request_key),
    )  # type: ignore
    task_id = import_task.task_id
    progress = Progress(AsyncResult(task_id))
    info = progress.get_info()
    context = {
        "task_id": task_id,
        "info": info,
    }
    response = render(request, "core/products/import_products_progress.html", context)
    # a small import can finish before this first render; then the template
    # ships no polling loop, so this response itself has to refresh the ledger
    if not info["complete"]:
        return response

    return trigger_client_event(response, "reload_products_table")


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
def track_remove_product_progress(request, task_id):
    progress = Progress(AsyncResult(task_id))
    info = progress.get_info()

    context = {
        "task_id": task_id,
        "info": info,
    }
    response = render(request, "core/products/modals/remove_products_progress.html", context)
    if not info["complete"]:
        return response

    return trigger_client_event(response, "reload_products_table")


@login_required
@user_passes_test(is_admin)
@require_POST
def remove_all_products_question(request):
    """Confirm the bulk delete before handing it to the worker."""
    ids = request.POST.getlist("ids")
    products = Product.objects.filter(pk__in=ids)
    totals = products.aggregate(units=Sum("stock"))
    sample_names = list(
        products.order_by("name").values_list("name", flat=True)[:REMOVAL_SAMPLE_SIZE]
    )

    context = {
        "ids": ids,
        "count": products.count(),
        "units": totals["units"] or 0,
        "order_lines": OrderItem.objects.filter(product__in=ids).count(),
        "sample_names": sample_names,
        "remaining": max(products.count() - len(sample_names), 0),
    }
    return render(request, "core/products/modals/remove_selected.html", context)


@login_required
@user_passes_test(is_admin)
@require_POST
def do_remove_products(request):
    ids = request.POST.getlist("ids")
    if not ids:
        context = {
            "type": "danger",
            "message": "No products were selected, so nothing was queued. "
            "Tick the rows to remove and try again.",
        }
        return render(request, "core/products/response.html", context)

    remove_task = remove_products_task.delay(ids)  # type: ignore
    task_id = remove_task.task_id
    progress = Progress(AsyncResult(task_id))
    info = progress.get_info()

    context = {
        "task_id": task_id,
        "info": info,
    }
    response = render(
        request, "core/products/modals/remove_products_progress.html", context
    )
    # as with the import: a small removal can finish before this first render,
    # leaving no polling loop that would ever broadcast the ledger refresh
    if not info["complete"]:
        return response

    return trigger_client_event(response, "reload_products_table")


@login_required
@user_passes_test(is_admin)
def add_product(request, product_id=None):
    """Create or edit one product; the same dialog serves both."""
    product = get_object_or_404(Product, pk=product_id) if product_id else None
    form = ProductCreationForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=product,
    )

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save(commit=False)
                initial_stock = (
                    form.cleaned_data["stock"] if product is None else 0
                )
                if product is not None:
                    locked_product = Product.objects.select_for_update().get(
                        pk=product.pk
                    )
                    saved.stock = locked_product.stock
                else:
                    saved.stock = 0
                cost = form.cleaned_data["cost"]
                price = form.cleaned_data["price"]
                saved.profit_rate = (
                    min(cost / price, PROFIT_RATE_MAX)
                    if price > 0
                    else Decimal("0.00")
                )
                saved.save()
                form.save_m2m()
                if initial_stock:
                    receive_stock(
                        actor=request.user,
                        request_key=_posted_request_key(request),
                        lines=[
                            ReceiptLine(
                                saved.pk,
                                initial_stock,
                                cost,
                            )
                        ],
                        received_at=timezone.now(),
                        source=StockReceiptSource.OPENING,
                        reason="Initial stock entered when the product was created.",
                    )
        except ValidationError as error:
            label = product.name if product else "New product"
            context = {
                "type": "danger",
                "message": f"{label} could not be saved: {error.messages[0]}",
            }
            return render(request, "core/products/response.html", context)
        except DatabaseError:
            logger.exception("Product save failed for %s", product.pk if product else "new")
            label = product.name if product else "New product"
            context = {
                "type": "danger",
                "message": f"{label} could not be saved. Try again later.",
            }
            return render(request, "core/products/response.html", context)
        else:
            verb = "updated in" if product else "added to"
            context = {
                "type": "success",
                "message": f"{saved.name} was {verb} the stock ledger.",
            }
            response = render(request, "core/products/response.html", context)
            return trigger_client_event(response, "reload_products_table")

    context = {
        "form": form,
        "product": product,
        "is_update": product is not None,
    }
    return render(request, "core/products/modals/product_form.html", context)


MAX_RESTOCK_UNITS = 100_000  # keeps stock inside the int4 column
RESTOCK_PRESETS = (12, 24, 48, 100)


@login_required
@user_passes_test(is_admin)
def restock_product(request, product_id):
    """Record an inbound shipment as a costed stock receipt."""
    product = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":
        try:
            units = int(request.POST.get("units"))
        except (TypeError, ValueError):
            units = 0

        if not 0 < units <= MAX_RESTOCK_UNITS:
            context = {
                "type": "danger",
                "message": "Enter a whole number of units between 1 and "
                f"{MAX_RESTOCK_UNITS:,}.",
            }
            return render(request, "core/products/response.html", context)

        try:
            raw_cost = request.POST.get("unit_cost", product.cost)
            receive_stock(
                actor=request.user,
                request_key=_posted_request_key(request),
                lines=[
                    ReceiptLine(
                        product.pk,
                        units,
                        raw_cost,
                    )
                ],
                received_at=timezone.now(),
                source=StockReceiptSource.PURCHASE,
                purchased_on=(
                    dt.date.fromisoformat(request.POST["purchased_on"])
                    if request.POST.get("purchased_on")
                    else None
                ),
                supplier_name=request.POST.get("supplier_name", ""),
                external_reference=request.POST.get("external_reference", ""),
            )
        except (ValueError, ValidationError) as error:
            message = (
                error.messages[0]
                if isinstance(error, ValidationError)
                else "Enter a valid acquisition cost and purchase date."
            )
            return render(
                request,
                "core/products/response.html",
                {"type": "danger", "message": message},
            )
        except DatabaseError:
            logger.exception("Product receipt failed for product %s", product.pk)
            return render(
                request,
                "core/products/response.html",
                {"type": "danger", "message": "The receipt could not be saved."},
            )
        product.refresh_from_db(fields=["stock", "cost"])

        context = {
            "type": "success",
            "message": f"{units:,} units of {product.name} logged. "
            f"Shelf count is now {product.stock:,}.",
        }
        response = render(request, "core/products/response.html", context)
        return trigger_client_event(response, "reload_products_table")

    context = {
        "product": product,
        "presets": RESTOCK_PRESETS,
        "max_units": MAX_RESTOCK_UNITS,
    }
    return render(request, "core/products/modals/restock_product.html", context)


@login_required
@user_passes_test(is_admin)
def remove_a_product_question(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    context = {
        "product": product,
        "order_lines": OrderItem.objects.filter(product=product).count(),
    }
    return render(request, "core/products/modals/remove_product.html", context)


@login_required
@user_passes_test(is_admin)
@require_POST
def do_remove_a_product(request, product_id):
    name = ""
    try:
        with transaction.atomic():
            product = get_object_or_404(
                Product.objects.select_for_update(),
                pk=product_id,
            )
            name = product.name
            if (
                product.stock != 0
                or OrderItem.objects.filter(product=product).exists()
                or StockBatch.objects.filter(product=product).exists()
            ):
                raise ProtectedError(
                    "Products with inventory history cannot be deleted.",
                    {product},
                )
            product.delete()
    except ProtectedError:
        return render(
            request,
            "core/products/response.html",
            {
                "type": "danger",
                "message": f"{name} has inventory or history and cannot be deleted.",
            },
        )
    context = {
        "type": "success",
        "message": f"{name} was removed from the ledger.",
    }
    response = render(request, "core/products/response.html", context)
    return trigger_client_event(response, "reload_products_table")


@login_required
@user_passes_test(is_admin)
def orders(request):
    initial_view = request.GET.get("view", "reports")
    if initial_view not in {"pos", "orders", "reports"}:
        initial_view = "reports"

    context = {"initial_view": initial_view}
    if initial_view == "orders":
        context["kpi"] = ledger_today_kpis()
        context["cashiers"] = Account.objects.order_by("username")
    elif initial_view == "reports":
        # the reports tab owns its whole viewport, so it renders ready-filled
        context.update(report_screen_context(request.GET))
    return render(request, "core/orders/orders.html", context)


def ledger_today_kpis():
    """Today's headline metrics for the ledger KPI cards."""
    today = timezone.localdate()
    today_orders = Order.objects.filter(created__date=today)
    totals = today_orders.aggregate(
        count=Count("id"),
        revenue=Sum("overall_amount_paid"),
        cashier_count=Count("user", distinct=True),
    )
    count = totals["count"]
    revenue = totals["revenue"] or Decimal("0.00")

    today_items = OrderItem.objects.filter(order__in=today_orders)
    today_totals = today_items.aggregate(
        profit=Sum(
            ExpressionWrapper(
                F("paid_amount") - F("cost_amount"),
                output_field=MONEY_FIELD,
            )
        ),
        estimated_lines=Count("id", filter=Q(cost_is_estimated=True)),
        actual_lines=Count("id", filter=Q(cost_is_estimated=False)),
        actual_cost=Sum("cost_amount", filter=Q(cost_is_estimated=False)),
        estimated_cost=Sum("cost_amount", filter=Q(cost_is_estimated=True)),
    )
    profit = today_totals["profit"] or Decimal("0.00")
    units = today_items.aggregate(units=Sum("qty_bought"))["units"] or 0

    yesterday_revenue = (
        Order.objects.filter(created__date=today - dt.timedelta(days=1)).aggregate(
            r=Sum("overall_amount_paid")
        )["r"]
        or Decimal("0.00")
    )
    revenue_delta_pct = None
    if yesterday_revenue:
        revenue_delta_pct = (
            (revenue - yesterday_revenue) / yesterday_revenue * 100
        ).quantize(Decimal("0.1"))

    return {
        "date": today,
        "order_count": count,
        "revenue": revenue,
        "cashier_count": totals["cashier_count"],
        "yesterday_revenue": yesterday_revenue,
        "revenue_delta_pct": revenue_delta_pct,
        "aov": (revenue / count).quantize(Decimal("0.01")) if count else None,
        "avg_items": (Decimal(units) / count).quantize(Decimal("0.1"))
        if count
        else None,
        "profit": profit,
        "actual_cost": today_totals["actual_cost"] or Decimal("0.00"),
        "estimated_cost": today_totals["estimated_cost"] or Decimal("0.00"),
        "estimated_line_count": today_totals["estimated_lines"],
        "actual_line_count": today_totals["actual_lines"],
        "profit_is_estimated": today_totals["estimated_lines"] > 0,
        "margin_pct": (profit / revenue * 100).quantize(Decimal("0.1"))
        if revenue
        else None,
    }


def ledger_filtered_orders(params):
    """Ledger queryset shared by the table partial and the CSV export."""
    orders_qs = Order.objects.select_related("user").annotate(
        items_count=Count("orderitem"),
        first_item=Subquery(
            OrderItem.objects.filter(order=OuterRef("pk"))
            .order_by("product__name")
            .values("product__name")[:1]
        ),
    )

    q = (params.get("q") or "").strip()
    if q:
        orders_qs = orders_qs.filter(code__icontains=q)

    users = (params.get("users") or "all").strip()
    if users and users != "all":
        orders_qs = orders_qs.filter(user__username=users)

    date_str = (params.get("date") or "").strip()
    if date_str:
        try:
            day = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            day = None
        if day is not None:
            orders_qs = orders_qs.filter(created__date=day)

    return orders_qs.order_by("-created")


# --- Sales reports -----------------------------------------------------------
#
# The reports page is driven by one inclusive [start, end] window over local
# dates, shared by the screen, the CSV export and the PDF so all three always
# agree on what "the report" is.

REPORT_PRESETS = ("today", "yesterday", "7d", "mtd", "custom")


def _report_date(value):
    """An ISO date out of the query string, or None when it is blank/nonsense."""
    try:
        return dt.date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _pct(part, whole):
    """part as a percentage of whole, or None when there is nothing to divide.

    Units aggregate to an int and money to a Decimal, so each side goes through
    str() before Decimal(): int / int would land on a float, which has no
    .quantize(), and float maths would quietly round the percentage.
    """
    if not whole:
        return None
    return (Decimal(str(part)) / Decimal(str(whole)) * 100).quantize(Decimal("0.1"))


def report_range(params):
    """The filter bar's query string as concrete dates.

    Anything unrecognised falls back to today rather than raising, and the
    previous window of the same length travels along with the range so the KPI
    deltas always compare like with like.
    """
    today = timezone.localdate()
    preset = (params.get("preset") or "today").strip()
    start = end = today

    if preset == "yesterday":
        start = end = today - dt.timedelta(days=1)
    elif preset == "7d":
        start = today - dt.timedelta(days=6)
    elif preset == "mtd":
        start = today.replace(day=1)
    elif preset == "custom":
        custom_start = _report_date(params.get("start"))
        custom_end = _report_date(params.get("end"))
        if custom_start and custom_end:
            start, end = min(custom_start, custom_end), max(custom_start, custom_end)
        else:
            preset = "today"
    else:
        preset = "today"

    length = end - start
    cashier = (params.get("users") or "").strip()

    return {
        "preset": preset,
        "start": start,
        "end": end,
        "days": (length.days + 1),
        "previous_start": start - length - dt.timedelta(days=1),
        "previous_end": start - dt.timedelta(days=1),
        "cashier": "" if cashier == "all" else cashier,
    }


def report_orders(rng, start_key="start", end_key="end"):
    """Receipts inside one window of the range, narrowed to a cashier."""
    orders = Order.objects.filter(
        created__date__gte=rng[start_key], created__date__lte=rng[end_key]
    )
    if rng["cashier"]:
        orders = orders.filter(user__username=rng["cashier"])
    return orders


def report_metrics(orders):
    """Aggregate receipt revenue and frozen actual/estimated acquisition costs."""
    totals = orders.aggregate(
        order_count=Count("id"),
        revenue=Sum("overall_amount_paid"),
    )
    lines = OrderItem.objects.filter(order__in=orders).aggregate(
        units=Sum("qty_bought"),
        cost=Sum("cost_amount"),
        profit=Sum(
            ExpressionWrapper(
                F("paid_amount") - F("cost_amount"),
                output_field=MONEY_FIELD,
            )
        ),
        actual_cost=Sum("cost_amount", filter=Q(cost_is_estimated=False)),
        estimated_cost=Sum("cost_amount", filter=Q(cost_is_estimated=True)),
        actual_profit=Sum(
            ExpressionWrapper(
                F("paid_amount") - F("cost_amount"),
                output_field=MONEY_FIELD,
            ),
            filter=Q(cost_is_estimated=False),
        ),
        estimated_profit=Sum(
            ExpressionWrapper(
                F("paid_amount") - F("cost_amount"),
                output_field=MONEY_FIELD,
            ),
            filter=Q(cost_is_estimated=True),
        ),
        actual_line_count=Count("id", filter=Q(cost_is_estimated=False)),
        estimated_line_count=Count("id", filter=Q(cost_is_estimated=True)),
        estimated_order_count=Count(
            "order_id",
            filter=Q(cost_is_estimated=True),
            distinct=True,
        ),
    )

    revenue = totals["revenue"] or Decimal("0.00")
    cost = lines["cost"] or Decimal("0.00")
    profit = lines["profit"] or Decimal("0.00")
    count = totals["order_count"]

    return {
        "order_count": count,
        "units": lines["units"] or 0,
        "revenue": revenue.quantize(Decimal("0.01")),
        "cost": cost.quantize(Decimal("0.01")),
        "profit": profit.quantize(Decimal("0.01")),
        "actual_cost": (lines["actual_cost"] or Decimal("0.00")).quantize(
            Decimal("0.01")
        ),
        "estimated_cost": (lines["estimated_cost"] or Decimal("0.00")).quantize(
            Decimal("0.01")
        ),
        "actual_profit": (lines["actual_profit"] or Decimal("0.00")).quantize(
            Decimal("0.01")
        ),
        "estimated_profit": (
            lines["estimated_profit"] or Decimal("0.00")
        ).quantize(Decimal("0.01")),
        "actual_line_count": lines["actual_line_count"],
        "estimated_line_count": lines["estimated_line_count"],
        "estimated_order_count": lines["estimated_order_count"],
        "profit_is_estimated": lines["estimated_line_count"] > 0,
        "margin_pct": _pct(profit, revenue),
        "cost_share_pct": _pct(cost, revenue),
        "profit_multiplier": (profit / cost).quantize(Decimal("0.01"))
        if cost
        else None,
        "aov": (revenue / count).quantize(Decimal("0.01")) if count else None,
    }


def report_context(rng):
    """Everything the reports screen shows for one range."""
    orders = report_orders(rng)
    kpi = report_metrics(orders)

    previous = report_metrics(report_orders(rng, "previous_start", "previous_end"))
    kpi["previous_revenue"] = previous["revenue"]
    kpi["revenue_delta_pct"] = _pct(
        kpi["revenue"] - previous["revenue"], previous["revenue"]
    )
    kpi["units_delta_pct"] = _pct(kpi["units"] - previous["units"], previous["units"])
    kpi["profit_delta_pct"] = _pct(kpi["profit"] - previous["profit"], previous["profit"])

    revenue = kpi["revenue"]
    category_labels = dict(ProductCategory.choices)

    by_cashier = [
        {
            "username": row["user__username"],
            "name": f"{row['user__first_name']} {row['user__last_name']}".strip()
            or row["user__username"],
            "orders": row["receipts"],
            "revenue": (row["revenue"] or Decimal("0.00")).quantize(Decimal("0.01")),
            "share_pct": _pct(row["revenue"], revenue),
        }
        for row in orders.values(
            "user__username", "user__first_name", "user__last_name"
        ).annotate(receipts=Count("id"), revenue=Sum("overall_amount_paid"))
    ]
    by_cashier.sort(key=lambda row: row["revenue"], reverse=True)

    by_category = [
        {
            "key": row["product__category"],
            "label": category_labels.get(
                row["product__category"], row["product__category"]
            ),
            "units": row["units"],
            "revenue": (row["revenue"] or Decimal("0.00")).quantize(Decimal("0.01")),
            "share_pct": _pct(row["revenue"], revenue),
        }
        for row in OrderItem.objects.filter(order__in=orders)
        .values("product__category")
        .annotate(units=Sum("qty_bought"), revenue=Sum("paid_amount"))
    ]
    by_category.sort(key=lambda row: row["revenue"], reverse=True)

    top_row = (
        OrderItem.objects.filter(order__in=orders)
        .values("product__name", "product__sku")
        .annotate(units=Sum("qty_bought"), revenue=Sum("paid_amount"))
        .order_by("-units", "product__name")
        .first()
    )
    top_sku = None
    if top_row:
        top_sku = {
            "name": top_row["product__name"],
            "sku": top_row["product__sku"],
            "units": top_row["units"],
            "revenue": top_row["revenue"].quantize(Decimal("0.01")),
        }

    return {
        "range": rng,
        "kpi": kpi,
        "by_cashier": by_cashier,
        "by_category": by_category,
        "categories_active": len(by_category),
        "top_sku": top_sku,
    }


@login_required
@user_passes_test(is_admin)
def orders_ledger(request):
    try:
        page = int(request.GET.get("p") or 1)
    except ValueError:
        page = 1

    orders_qs = ledger_filtered_orders(request.GET)
    paginator = Paginator(orders_qs, LEDGER_PAGE_SIZE)
    page_obj = paginator.get_page(page)

    context = {
        "page_obj": page_obj,
        "q": (request.GET.get("q") or "").strip(),
        "users": (request.GET.get("users") or "all").strip() or "all",
        "date": (request.GET.get("date") or "").strip(),
    }
    return render(request, "core/orders/ledger_table.html", context)


@require_GET
@login_required
@user_passes_test(is_admin)
def export_orders_csv(request):
    orders_qs = ledger_filtered_orders(request.GET)

    stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="orders_{stamp}.csv"'

    writer = csv.writer(response)
    writer.writerow(["Receipt", "Date", "Time", "Cashier", "Items", "Total (GHs)"])
    for order in orders_qs.values(
        "code",
        "created",
        "user__username",
        "items_count",
        "overall_amount_paid",
    ).iterator():
        local_created = timezone.localtime(order["created"])
        writer.writerow(
            [
                order["code"],
                f"{local_created:%Y-%m-%d}",
                f"{local_created:%H:%M:%S}",
                order["user__username"],
                order["items_count"],
                order["overall_amount_paid"],
            ]
        )
    return response


@login_required
@user_passes_test(is_admin)
def products_summary(request):
    totals = Product.objects.aggregate(
        sum_stock=Sum("stock"),
        sum_sales=Sum(F("price") * F("stock"), output_field=MONEY_FIELD),
        total=Count("id"),
        depleted=Count("id", filter=Q(stock=0)),
        low=Count("id", filter=Q(stock__gt=0, stock__lte=F("low_stock_threshold"))),
        categories=Count("category", distinct=True),
    )

    batch_value = StockBatch.objects.aggregate(
        cost_value=Sum(
            ExpressionWrapper(
                F("quantity_remaining") * F("unit_cost"),
                output_field=MONEY_FIELD,
            )
        ),
        estimated_cost_value=Sum(
            ExpressionWrapper(
                F("quantity_remaining") * F("unit_cost"),
                output_field=MONEY_FIELD,
            ),
            filter=Q(cost_is_estimated=True),
        ),
        estimated_units=Sum(
            "quantity_remaining",
            filter=Q(cost_is_estimated=True),
        ),
    )
    cost_value = batch_value["cost_value"] or Decimal("0.00")
    estimated_cost_value = (
        batch_value["estimated_cost_value"] or Decimal("0.00")
    )
    retail_value = totals["sum_sales"] or Decimal("0.00")
    valuation_margin = (
        (retail_value - cost_value) / retail_value * 100
        if retail_value > 0
        else Decimal("0.00")
    )

    depleted_names = (
        list(
            Product.objects.filter(stock=0)
            .order_by("name")
            .values_list("name", flat=True)[:3]
        )
        if totals["depleted"]
        else []
    )

    context = {
        "total_skus": totals["total"],
        "categories_count": totals["categories"],
        "units_in_stock": totals["sum_stock"] or 0,
        "cost_value": cost_value,
        "actual_cost_value": cost_value - estimated_cost_value,
        "estimated_cost_value": estimated_cost_value,
        "estimated_stock_units": batch_value["estimated_units"] or 0,
        "cost_value_is_estimated": (batch_value["estimated_units"] or 0) > 0,
        "retail_value": retail_value,
        "valuation_margin": valuation_margin,
        "low_stock_count": totals["low"],
        "out_of_stock_count": totals["depleted"],
        "depleted_names": depleted_names,
        "remaining_depleted": max(totals["depleted"] - len(depleted_names), 0),
    }
    return render(request, "core/products/summary.html", context)


def todays_takings(user=None):
    """Gross takings booked today, shared by the register header and the
    post-checkout refresh. A cashier reads their own figure, not the store's."""
    orders = Order.objects.filter(created__date=timezone.localdate())
    if user is not None:
        orders = orders.filter(user=user)
    return orders.aggregate(total=Sum("overall_amount_paid"))["total"] or Decimal("0.00")


def register_context(request):
    """The register both roles share. Everything owner-only -- cost, margin,
    the ledger, other people's sales -- stays out of this context."""
    products = Product.objects.filter(Q(stock__gt=0)).order_by("name")
    page_obj = Paginator(products, POS_PAGE_SIZE).get_page(1)
    cashier = None if is_admin(request.user) else request.user
    return {
        "page_obj": page_obj,
        "today_takings": todays_takings(cashier),
        "personal_takings": cashier is not None,
    }


@login_required
@user_passes_test(can_ring_up)
def orders_products(request):
    return render(request, "core/orders/pos_register.html", register_context(request))


@login_required
@user_passes_test(can_ring_up)
def load_orders_products(request):
    products = Product.objects.filter(Q(stock__gt=0)).order_by("name")

    page = 1
    if request.GET.get("p") is not None and request.GET.get("p") != "":
        page = int(request.GET.get("p"))

    if request.GET.get("s") is not None and request.GET.get("s") != "":
        products = products.filter(
            Q(name__icontains=request.GET.get("s"))
            | Q(sku__icontains=request.GET.get("s"))
        ).order_by("name")

    paginator = Paginator(products, POS_PAGE_SIZE)

    page_obj = paginator.get_page(page)

    context = {
        "page_obj": page_obj,
    }
    return render(request, "core/orders/pos_product_cards.html", context)


@require_POST
@login_required
@user_passes_test(can_ring_up)
def make_order(request):
    raw_cart = request.POST.get("items")
    items = parse_cart(raw_cart)

    if items is None:
        logger.error(
            "make_order got a cart that is not a JSON array of lines for user %s: %r",
            request.user.pk,
            raw_cart,
        )
        message = (
            "The cart could not be read. Reload the register and run the sale again."
        )
        context = {"type": "danger", "message": message}
        return render(request, "core/orders/order_made.html", context)

    if len(items) == 0:
        msg_type = "danger"
        message = "No items in the cart. Add items to the cart and make payment."
        context = {"type": msg_type, "message": message}
        return render(request, "core/orders/order_made.html", context)

    try:
        sale_lines = []
        for item in items:
            raw_quantity = item.get("qty")
            if isinstance(raw_quantity, bool):
                raise ValidationError({"quantity": "Enter a whole number."})
            try:
                quantity = int(raw_quantity)
            except (TypeError, ValueError) as error:
                raise ValidationError({"quantity": "Enter a whole number."}) from error
            if isinstance(raw_quantity, float) and not raw_quantity.is_integer():
                raise ValidationError({"quantity": "Enter a whole number."})
            if isinstance(raw_quantity, str) and raw_quantity.strip() != str(quantity):
                raise ValidationError({"quantity": "Enter a whole number."})
            sale_lines.append(
                SaleLine(
                    product_id=item.get("id"),
                    quantity=quantity,
                    total_price=item.get("total_price"),
                )
            )
        order_obj = checkout(
            actor=request.user,
            request_key=_posted_request_key(request),
            lines=sale_lines,
        )
    except ValidationError as error:
        logger.info(
            "make_order rejected a cart for user %s: %s",
            request.user.pk,
            error.messages,
        )
        message = "The sale could not be completed: " + "; ".join(error.messages)
        context = {"type": "danger", "message": message}
        return render(request, "core/orders/order_made.html", context)
    except DatabaseError:
        logger.exception("make_order failed for user %s", request.user.pk)
        message = "The sale could not be completed. Try again."
        context = {"type": "danger", "message": message}
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
    cashier = None if is_admin(request.user) else request.user
    context = {
        "type": msg_type,
        "message": message,
        "order": order_obj,
        "order_number": order_number,
        "today_takings": todays_takings(cashier),
    }
    response = render(request, "core/orders/order_made.html", context)
    return trigger_client_event(response, "reload_products_with_stocks")


@login_required
@user_passes_test(can_ring_up)
def shop_cart(request):
    return render(request, "core/orders/pos_cart_panel.html")


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
@user_passes_test(can_ring_up)
def view_order(request, order_id, order_number):
    order = get_receipt(request, order_id)
    context = {"order": order, "order_number": order_number}
    return render(request, "core/orders/order_details.html", context)


RECEIPT_LOGO = "images/eden-logo.png"
RECEIPT_LOGO_HEIGHT_MM = 24.0  # 14mm logo plus its contact and credit lines


def receipt_sheet_length_mm(order, company, logo_mm=0.0):
    """WeasyPrint refuses content-sized pages, so size the 80mm sheet by hand.
    The 60mm base is the measured furniture (head, meta, rules, footer) plus a
    ~1mm margin, then 4.9mm per wrapped text line — a 3.9mm 8pt line with row
    padding — plus the colophon allowance the caller passes, and a line each
    for the optional email and customer rows."""
    items = order.orderitem_set.select_related("product")
    name_lines = sum(max(1, math.ceil(len(i.product.name) / 22)) for i in items)
    extra = (4 if company["email"] else 0) + (4 if order.customer_name else 0)
    return max(80.0, round(60 + name_lines * 4.9 + extra + logo_mm, 1))


def get_receipt(request, order_id):
    """The owner reads any receipt; a cashier reads only the ones they rang up."""
    receipts = Order.objects.prefetch_related(
        Prefetch(
            "orderitem_set",
            queryset=OrderItem.objects.select_related("product"),
        )
    )
    if not is_admin(request.user):
        receipts = receipts.filter(user=request.user)
    return get_object_or_404(receipts, id=order_id)


@login_required
@user_passes_test(can_ring_up)
def print_order_pdf(request, order_id, order_number):
    order = get_receipt(request, order_id)
    logo = static_image_data_uri(RECEIPT_LOGO)
    context = {
        "order": order,
        "order_number": order_number,
        "logo_data_uri": logo,
    }
    today = dt.datetime.now()
    todays_date = f"{today:%d%m%Y%H%M%S}"
    filename = f"Invoice-{order.code}-{todays_date}.pdf"
    pdf = render_attached_pdf(
        relative_template_path="core/orders/prints/order_details.html",
        context=context,
        file_name=filename,
        css=["css/receipt.css"],
        page_size_mm=(
            80,
            receipt_sheet_length_mm(
                order,
                settings.COMPANY_INFO,
                RECEIPT_LOGO_HEIGHT_MM if logo else 0.0,
            ),
        ),
    )
    return pdf



def report_ledger_rows(orders_qs):
    """The per-receipt money columns, using frozen cost snapshots."""
    lines = OrderItem.objects.filter(order=OuterRef("pk"))
    return (
        orders_qs.select_related("user")
        .annotate(
            items_count=Count("orderitem"),
            units=Sum("orderitem__qty_bought"),
            cost_outlay=Sum("orderitem__cost_amount"),
            actual_cost_outlay=Sum(
                "orderitem__cost_amount",
                filter=Q(orderitem__cost_is_estimated=False),
            ),
            estimated_cost_outlay=Sum(
                "orderitem__cost_amount",
                filter=Q(orderitem__cost_is_estimated=True),
            ),
            line_profit=Sum(
                ExpressionWrapper(
                    F("orderitem__paid_amount") - F("orderitem__cost_amount"),
                    output_field=MONEY_FIELD,
                )
            ),
            actual_line_profit=Sum(
                ExpressionWrapper(
                    F("orderitem__paid_amount") - F("orderitem__cost_amount"),
                    output_field=MONEY_FIELD,
                ),
                filter=Q(orderitem__cost_is_estimated=False),
            ),
            estimated_line_profit=Sum(
                ExpressionWrapper(
                    F("orderitem__paid_amount") - F("orderitem__cost_amount"),
                    output_field=MONEY_FIELD,
                ),
                filter=Q(orderitem__cost_is_estimated=True),
            ),
            estimated_lines=Count(
                "orderitem",
                filter=Q(orderitem__cost_is_estimated=True),
            ),
            first_item=Subquery(
                lines.order_by("product__name").values("product__name")[:1]
            ),
            first_sku=Subquery(
                lines.order_by("product__name").values("product__sku")[:1]
            ),
        )
        .order_by("-created")
    )


def report_ledger_queryset(rng, q=""):
    """Receipts in the range, optionally narrowed by receipt code."""
    orders = report_orders(rng)
    if q:
        orders = orders.filter(code__icontains=q)
    return report_ledger_rows(orders)


def report_screen_context(params):
    """One context for the page, the htmx body, the CSV and the PDF, so the
    screen and its two exports can never disagree about the range."""
    rng = report_range(params)
    q = (params.get("q") or "").strip()

    try:
        page = int(params.get("p") or 1)
    except ValueError:
        page = 1

    return {
        "rng": rng,
        "report": report_context(rng),
        "q": q,
        # the month label is computed, never hardcoded in the template
        "preset_buttons": (
            ("today", "Today"),
            ("yesterday", "Yesterday"),
            ("7d", "Last 7 Days"),
            ("mtd", f"MTD: {timezone.localdate():%b %Y}"),
        ),
        "page_obj": Paginator(
            report_ledger_queryset(rng, q), LEDGER_PAGE_SIZE
        ).get_page(page),
        "cashiers": Account.objects.order_by("username"),
    }


@login_required
@user_passes_test(is_admin)
def sales_report_body(request):
    """KPIs, breakdowns and ledger for the selected range."""
    return render(
        request, "core/orders/report_body.html", report_screen_context(request.GET)
    )


@login_required
@user_passes_test(is_admin)
def sales_report_ledger(request):
    """Ledger rows on their own, so paging never re-runs the aggregates."""
    return render(
        request,
        "core/orders/report_ledger_rows.html",
        report_screen_context(request.GET),
    )


@require_GET
@login_required
@user_passes_test(is_admin)
def sales_report_csv(request):
    rng = report_range(request.GET)
    q = (request.GET.get("q") or "").strip()

    stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="sales_report_{rng["start"]:%Y%m%d}_{stamp}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(
        [
            "S/No",
            "Receipt",
            "Date",
            "Time",
            "Cashier",
            "Units",
            "Actual Cost",
            "Estimated Cost",
            "Revenue",
            "Actual Profit",
            "Estimated Profit",
            "Estimated Lines",
        ]
    )
    for number, order in enumerate(
        report_ledger_queryset(rng, q)
        .values(
            "code",
            "created",
            "user__username",
            "units",
            "actual_cost_outlay",
            "estimated_cost_outlay",
            "overall_amount_paid",
            "actual_line_profit",
            "estimated_line_profit",
            "estimated_lines",
        )
        .iterator(),
        start=1,
    ):
        local_created = timezone.localtime(order["created"])
        writer.writerow(
            [
                number,
                order["code"],
                f"{local_created:%Y-%m-%d}",
                f"{local_created:%H:%M:%S}",
                order["user__username"],
                order["units"] or 0,
                order["actual_cost_outlay"] or Decimal("0.00"),
                order["estimated_cost_outlay"] or Decimal("0.00"),
                order["overall_amount_paid"],
                order["actual_line_profit"] or Decimal("0.00"),
                order["estimated_line_profit"] or Decimal("0.00"),
                order["estimated_lines"],
            ]
        )
    return response


@require_GET
@login_required
@user_passes_test(is_admin)
def sales_report_pdf(request):
    context = report_screen_context(request.GET)
    context["rows"] = report_ledger_queryset(context["rng"], context["q"])

    stamp = timezone.localtime().strftime("%d%m%Y%H%M%S")
    return render_attached_pdf(
        relative_template_path="core/orders/prints/all_reports.html",
        context=context,
        file_name=f"Reports_{stamp}.pdf",
    )
