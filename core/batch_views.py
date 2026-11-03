"""The batch dialogs and the owner's receipt register.

Most views here are GET-only fragments; the multi-line receipt dialog books its
own POST here, because the single-product write it replaces lived in
core/views.py and this dialog has no single product to hang a URL on.
Every view repeats the same decorator trio, in this order, so unauthenticated
and non-admin requests both leave through a 302.
"""

import datetime as dt
import logging
import re
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET
from django_htmx.http import trigger_client_event

from core.inventory import (
    MAX_SELLING_PRICE,
    ReceiptLine,
    receive_stock,
)
from core.models import (
    Product,
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
    StockReceipt,
    StockReceiptSource,
)
from core.views import _posted_request_key  # the same posted-key read the other write views use

from utils import is_admin  # same helper core/views.py uses

logger = logging.getLogger(__name__)

# the service names the offending line in its error_dict keys: lines[3].selling_price
LINE_KEY_RE = re.compile(r"^lines\[(\d+)\]\.(\w+)$")
FIELD_LABELS = {
    "product_id": "product",
    "quantity": "units",
    "unit_cost": "unit cost",
    "selling_price": "selling price",
}

# quantity x unit cost, with room for the largest receipt the backend accepts.
BATCH_VALUE = DecimalField(max_digits=24, decimal_places=2)

# the picker returns a page of options, not a catalogue: twenty is what a
# dialog's dropdown can be scanned without the owner scrolling.
RECEIPT_SEARCH_RESULTS = 20

# was core/views.MAX_RESTOCK_UNITS: a per-line input ceiling for the dialog, not
# a service rule -- the service's own ceilings stay MAX_QUANTITY / MAX_RECEIPT_LINES.
MAX_RECEIPT_LINE_UNITS = 100_000
MAX_RECEIPT_DIALOG_ROWS = 50
RECEIPT_UNIT_PRESETS = (12, 24, 48, 100)


def _line_context(
    product_id="", product=None, units="", unit_cost="", selling_price="", error=False
):
    """One receipt line as the row partial reads it: flat, all keys present.

    The partial is the only renderer for a row -- GET, failed POST and the
    blank-line endpoint all pass this dict -- so a row cannot look different
    depending on which of the three built it.
    """
    return {
        "product_id": product_id,
        "product": product,
        "units": units,
        "unit_cost": unit_cost,
        "selling_price": selling_price,
        "error": error,
    }


def _dialog_context(request, *, lines=None, request_key="", message="", posted=None):
    context = {
        "lines": lines if lines is not None else [_line_context()],
        "request_key": request_key,
        "message": message,
        "max_units": MAX_RECEIPT_LINE_UNITS,
        "max_rows": MAX_RECEIPT_DIALOG_ROWS,
        "price_cap": MAX_SELLING_PRICE,
        "presets": RECEIPT_UNIT_PRESETS,
    }
    if posted is not None:
        context["posted_supplier_name"] = posted.get("supplier_name", "")
        context["posted_external_reference"] = posted.get("external_reference", "")
        context["posted_purchased_on"] = posted.get("purchased_on", "")
    return context


def _movement_annotations():
    """The per-batch ``sold`` and ``adjusted`` aliases, safe against fan-out.

    sold and adjusted come from two different multi-valued relationships.
    One annotate() over both would multiply the joins (2 allocations x 2
    adjustments => each Sum reads 4 rows and both totals inflate), so each
    relation is aggregated on its own in a correlated subquery. The precedent
    in this repo is check_inventory.py:51-62, which recomputes the very same
    two sums that way to test the batch invariant.

    Built per call, never cached in a constant: a Subquery binds to the one
    query it is used in, and each view annotates its own queryset.
    """
    allocation_sum = (
        SaleBatchAllocation.objects.filter(batch=OuterRef("pk"))
        .values("batch")
        .annotate(s=Sum("quantity"))
        .values("s")[:1]
    )
    adjustment_sum = (
        StockAdjustment.objects.filter(batch=OuterRef("pk"))
        .values("batch")
        .annotate(a=Sum("quantity_delta"))
        .values("a")[:1]
    )
    return {
        "sold": Coalesce(
            Subquery(allocation_sum, output_field=IntegerField()),
            0,
            output_field=IntegerField(),
        ),
        "adjusted": Coalesce(
            Subquery(adjustment_sum, output_field=IntegerField()),
            0,
            output_field=IntegerField(),
        ),
    }


def _receipt_totals():
    """The per-receipt ``units`` / ``value`` / ``line_count`` register columns.

    A receipt row reaches its batches through the reverse ``batches`` key, and
    annotating joins over it would multiply the sums, so every figure is
    aggregated per receipt in its own correlated subquery; the
    ``values("receipt")`` groups it there, which is why each subquery returns
    exactly one row.

    Coalesced to zero because a batch-less receipt is real, not hypothetical:
    0015_backfill_opening_stock_and_costs writes one cutover StockReceipt
    unconditionally, and it only gains lines for products that had stock. The
    register therefore has to show 0 units / GH₵ 0.00 / 0 lines for it rather
    than the blanks a bare Subquery would yield.
    """
    return {
        "units": Coalesce(
            Subquery(
                StockBatch.objects.filter(receipt_id=OuterRef("pk"))
                .values("receipt")
                .annotate(s=Sum("quantity_received"))
                .values("s")[:1],
                output_field=IntegerField(),
            ),
            0,
            output_field=IntegerField(),
        ),
        "value": Coalesce(
            Subquery(
                StockBatch.objects.filter(receipt_id=OuterRef("pk"))
                .values("receipt")
                .annotate(
                    s=Sum(
                        F("quantity_received") * F("unit_cost"),
                        output_field=BATCH_VALUE,
                    )
                )
                .values("s")[:1],
                output_field=BATCH_VALUE,
            ),
            0,
            output_field=BATCH_VALUE,
        ),
        "line_count": Coalesce(
            Subquery(
                StockBatch.objects.filter(receipt_id=OuterRef("pk"))
                .values("receipt")
                .annotate(c=Count("pk"))
                .values("c")[:1],
                output_field=IntegerField(),
            ),
            0,
            output_field=IntegerField(),
        ),
    }


@login_required
@require_GET
@user_passes_test(is_admin)
def adjust_stock_question(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    batches = (
        StockBatch.objects.filter(product=product, quantity_remaining__gt=0)
        .select_related("receipt")
        .order_by("receipt__received_at", "line_number")
    )
    return render(
        request,
        "core/inventory/adjust_stock.html",
        {"product": product, "batches": batches},
    )


@login_required
@require_GET
@user_passes_test(is_admin)
def product_batches(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    batches = list(
        StockBatch.objects.filter(product=product)
        .select_related("receipt")
        .annotate(**_movement_annotations())
        .order_by("-receipt__received_at", "-line_number")
    )
    # Every batch counts, depleted ones included: the reconciliation line only
    # means something against the full history the backend keeps.
    return render(
        request,
        "core/inventory/product_batches.html",
        {
            "product": product,
            "batches": batches,
            "remaining_total": sum(b.quantity_remaining for b in batches),
        },
    )


@login_required
@require_GET
@user_passes_test(is_admin)
def stock_receipts(request):
    """The register: one row per receipt, newest first, twenty-five to a page."""
    receipts = (
        StockReceipt.objects.select_related("recorded_by")
        .annotate(**_receipt_totals())
        .order_by("-received_at", "-id")
    )
    # get_page() maps a non-integer to page 1 but an EmptyPage to the LAST page,
    # so ?page=0 or ?page=-3 would silently open the oldest page of the register.
    # Anything below 1 is normalised here; junk and far-out numbers keep the
    # clamping behaviour the tests pin (page 1 and the last page).
    requested_page = request.GET.get("page")
    try:
        if int(requested_page) < 1:
            requested_page = "1"
    except (TypeError, ValueError):
        pass
    page = Paginator(receipts, 25).get_page(requested_page)
    return render(request, "core/inventory/receipts.html", {"page_obj": page})


@login_required
@require_GET
@user_passes_test(is_admin)
def stock_receipt_detail(request, receipt_id):
    """One receipt's lines, with what is still on the shelf behind each of them."""
    receipt = get_object_or_404(
        StockReceipt.objects.select_related("recorded_by").annotate(**_receipt_totals()),
        pk=receipt_id,
    )
    batches = list(
        StockBatch.objects.filter(receipt=receipt)
        .select_related("product")
        .annotate(
            remaining_value=ExpressionWrapper(
                F("quantity_remaining") * F("unit_cost"),
                output_field=BATCH_VALUE,
            ),
            **_movement_annotations(),
        )
        .order_by("line_number")
    )
    return render(
        request,
        "core/inventory/receipt_detail.html",
        {
            "receipt": receipt,
            "batches": batches,
            "sold_total": sum(b.sold for b in batches),
            "adjusted_total": sum(b.adjusted for b in batches),
            "remaining_total": sum(b.quantity_remaining for b in batches),
            "remaining_value_total": sum(
                (b.remaining_value for b in batches), Decimal("0.00")
            ),
        },
    )


@login_required
@require_GET
@user_passes_test(is_admin)
def receipt_product_options(request):
    """The receipt dialog's picker: selectable options, never a ledger row.

    ``load_products`` is not reusable -- it renders table rows for the ledger.
    The filter is copied from the one the ledger itself runs
    (core/views.py:1163-1167) so a name and a code search identically in both,
    and an empty term still answers (the dialog offers something to click).
    """
    term = request.GET.get("q", "").strip()
    products = Product.objects.all()
    if term:
        products = products.filter(
            Q(name__icontains=term) | Q(sku__icontains=term)
        ).order_by("name")
    else:
        products = products.order_by("name")
    return render(
        request,
        "core/products/partials/receipt_product_options.html",
        {"products": products[:RECEIPT_SEARCH_RESULTS], "term": term},
    )


class _ReceiptLineProblem(Exception):
    """A dialog line the view cannot turn into a ReceiptLine, and its row number.

    Row 0 means "not one line's fault" -- an incomplete array, no lines at all,
    or too many of them.
    """

    def __init__(self, row, message):
        super().__init__(message)
        self.row = row
        self.message = message


def _read_receipt_lines(request):
    """Zip the dialog's parallel arrays into receipt lines, rows numbered from 1.

    An empty ``line_selling_price[]`` entry is 'change nothing', never a zero
    price, so it becomes None rather than Decimal('0.00'). Unequal array lengths
    are refused here: zipping them would silently drop a line off the end, which
    is the difference between the receipt the owner typed and one they did not.
    The per-line unit ceiling is the view's (100,000); the service keeps its own
    MAX_QUANTITY and MAX_RECEIPT_LINES rules, and this view adds the row number
    on top of them, which the service cannot know.

    The products are resolved in one query before any number is read, because a
    row has no meaning until it names a real product -- and because the service
    reports an unknown product as a single ``lines`` error that cannot say which
    row it came from.
    """
    product_ids = [value.strip() for value in request.POST.getlist("line_product_id[]")]
    units = [value.strip() for value in request.POST.getlist("line_units[]")]
    costs = [value.strip() for value in request.POST.getlist("line_unit_cost[]")]
    prices = [value.strip() for value in request.POST.getlist("line_selling_price[]")]
    if len({len(product_ids), len(units), len(costs), len(prices)}) > 1:
        raise _ReceiptLineProblem(
            0,
            "The receipt lines arrived incomplete. Close the dialog, reopen it and try again.",
        )
    rows = list(zip(product_ids, units, costs, prices))
    if not rows:
        raise _ReceiptLineProblem(0, "Add at least one product to the receipt.")
    if len(rows) > MAX_RECEIPT_DIALOG_ROWS:
        raise _ReceiptLineProblem(
            0, f"This dialog books at most {MAX_RECEIPT_DIALOG_ROWS} lines per receipt."
        )

    picked = []
    for row, (product_id, _units, _costs, _prices) in enumerate(rows, start=1):
        if not product_id:
            raise _ReceiptLineProblem(
                row, f"Line {row} has no product yet. Pick one from the search box."
            )
        try:
            picked.append((row, UUID(product_id)))
        except (ValueError, TypeError):
            raise _ReceiptLineProblem(
                row, f"Line {row} names a product that is not a stock item."
            ) from None
    known = set(
        Product.objects.filter(pk__in=[pk for _row, pk in picked]).values_list("pk", flat=True)
    )
    for row, pk in picked:
        if pk not in known:
            raise _ReceiptLineProblem(
                row, f"Line {row} names a product that is no longer in the catalogue."
            )

    lines = []
    for row, (product_id, raw_units, raw_cost, raw_price) in enumerate(rows, start=1):
        try:
            quantity = int(raw_units)
        except (TypeError, ValueError):
            raise _ReceiptLineProblem(
                row, f"Line {row} needs a whole number of units."
            ) from None
        if not 0 < quantity <= MAX_RECEIPT_LINE_UNITS:
            raise _ReceiptLineProblem(
                row,
                f"Line {row} takes between 1 and {MAX_RECEIPT_LINE_UNITS:,} units.",
            )
        if not raw_cost:
            raise _ReceiptLineProblem(row, f"Line {row} needs a unit cost.")
        try:
            unit_cost = Decimal(raw_cost)
        except InvalidOperation:
            raise _ReceiptLineProblem(row, f"Line {row} has an unreadable unit cost.") from None
        selling_price = None
        if raw_price:
            try:
                selling_price = Decimal(raw_price)
            except InvalidOperation:
                raise _ReceiptLineProblem(
                    row, f"Line {row} has an unreadable selling price."
                ) from None
            if selling_price > MAX_SELLING_PRICE:
                raise _ReceiptLineProblem(
                    row,
                    f"Line {row} cannot sell above GH₵ {MAX_SELLING_PRICE}; "
                    "checkout refuses a sale line bigger than that.",
                )
        lines.append(ReceiptLine(UUID(product_id), quantity, unit_cost, selling_price))
    return lines


def _describe_service_error(error):
    """(row number, message) for a ValidationError raised inside the service.

    The service already names the line in its error_dict key -- lines[3].
    selling_price -- so the dialog can highlight the row rather than guess it.
    Keys it raises on its own terms (``lines``, ``received_at``, the header
    fields) carry no row, and the first of those messages is the one shown.
    """
    if not isinstance(error, ValidationError):
        return 0, "Enter a valid cost, price and purchase date."
    error_dict = getattr(error, "error_dict", None)
    if error_dict:
        unrowed = None
        for key, messages in error_dict.items():
            message = (
                messages[0].message
                if hasattr(messages[0], "message")
                else str(messages[0])
            )
            match = LINE_KEY_RE.match(key)
            if match:
                row, field = int(match.group(1)), match.group(2)
                label = FIELD_LABELS.get(field, field.replace("_", " "))
                return row, f"Line {row}: {label} — {message}"
            unrowed = unrowed or message
        if unrowed:
            return 0, unrowed
    return 0, error.messages[0]


def _posted_lines(request, error_row=0):
    """The rows the owner typed, back into row-partial contexts.

    A product id that no longer resolves keeps its raw value in the hidden
    field and shows no name, so the owner sees exactly what is wrong rather
    than a silently emptied row.
    """
    product_ids = request.POST.getlist("line_product_id[]")
    units = request.POST.getlist("line_units[]")
    costs = request.POST.getlist("line_unit_cost[]")
    prices = request.POST.getlist("line_selling_price[]")
    parsed = []
    for raw_id in product_ids:
        try:
            parsed.append(UUID(raw_id))
        except (ValueError, TypeError):
            parsed.append(None)
    known = {
        product.pk: product
        for product in Product.objects.filter(
            pk__in=[pk for pk in parsed if pk is not None]
        )
    }
    rows = []
    for index, (raw_id, pk, raw_units, raw_cost, raw_price) in enumerate(
        zip(product_ids, parsed, units, costs, prices), start=1
    ):
        rows.append(
            _line_context(
                product_id=raw_id,
                product=known.get(pk),
                units=raw_units,
                unit_cost=raw_cost,
                selling_price=raw_price,
                error=(index == error_row),
            )
        )
    return rows or [_line_context()]


def _book_receipt(request):
    """One post is one receipt, or nothing at all (spec decision 3)."""
    try:
        lines = _read_receipt_lines(request)
    except _ReceiptLineProblem as problem:
        return _refused(request, problem.row, problem.message)

    raw_purchased_on = request.POST.get("purchased_on", "")
    try:
        purchased_on = dt.date.fromisoformat(raw_purchased_on) if raw_purchased_on else None
    except ValueError:
        return _refused(request, 0, "Enter a purchase date as YYYY-MM-DD, or leave it empty.")

    try:
        receipt = receive_stock(
            actor=request.user,
            request_key=_posted_request_key(request),
            lines=lines,
            received_at=timezone.now(),
            source=StockReceiptSource.PURCHASE,
            purchased_on=purchased_on,
            supplier_name=request.POST.get("supplier_name", ""),
            external_reference=request.POST.get("external_reference", ""),
        )
    except (ValueError, ValidationError) as error:
        row, message = _describe_service_error(error)
        return _refused(request, row, message)
    except DatabaseError:
        logger.exception("Multi-line receipt failed for user %s", request.user.pk)
        return _refused(request, 0, "The receipt could not be saved. Try again.")

    response = render(
        request,
        "core/products/response.html",
        {
            "type": "success",
            "message": f"{len(lines)} line(s) booked as receipt "
            f"#{str(receipt.pk)[:8]}: {sum(line.quantity for line in lines):,} units onto the shelf.",
        },
    )
    return trigger_client_event(response, "reload_products_table")


def _refused(request, row, message):
    """Re-render the dialog with its lines intact -- never response.html.

    The single-line dialog could afford to discard one shipment; ten rows of
    typed units and prices cannot be retyped because of one typo, and the
    posted request key has to survive so the corrected submission is still the
    same request to the ledger.
    """
    key = request.POST.get("request_key", "")
    # only a key that parses as a UUID is echoed back; anything else is dropped
    # so the dialog's own generator produces a fresh, safe one.
    try:
        key = str(UUID(key)) if key else ""
    except (ValueError, TypeError, AttributeError):
        key = ""
    return render(
        request,
        "core/products/modals/receive_stock.html",
        _dialog_context(
            request,
            lines=_posted_lines(request, error_row=row),
            request_key=key,
            message=message,
            posted=request.POST,
        ),
    )


@login_required
@require_GET
@user_passes_test(is_admin)
def receipt_line_blank(request):
    """One empty line, swapped into the open dialog by 'Add another product'."""
    return render(
        request,
        "core/products/partials/receipt_line_row.html",
        {
            "line": _line_context(),
            "max_units": MAX_RECEIPT_LINE_UNITS,
            "presets": RECEIPT_UNIT_PRESETS,
        },
    )


@login_required
@user_passes_test(is_admin)
def receive_stock_question(request):
    """Book one delivery, however many products it carried.

    Deliberately not ``@require_GET``: this is the dialog's POST target too, the
    way ``restock_product`` and ``add_product`` both answer GET and POST.
    """
    if request.method == "POST":
        return _book_receipt(request)
    lines = [_line_context()]
    raw_product_id = request.GET.get("product_id")
    if raw_product_id:
        product = Product.objects.filter(pk=raw_product_id).first()
        if product is not None:
            lines = [
                _line_context(
                    product_id=str(product.pk),
                    product=product,
                    units=RECEIPT_UNIT_PRESETS[1],
                    unit_cost=product.cost,
                )
            ]
        # a product that is gone leaves a blank dialog rather than a 404: the
        # dialog is for the delivery, and the owner can still book the rest of it.
    return render(
        request,
        "core/products/modals/receive_stock.html",
        _dialog_context(request, lines=lines),
    )
