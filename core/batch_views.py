"""The batch dialogs and the owner's receipt register.

Most views here are GET-only fragments; the multi-line receipt dialog books its
own POST here, because the single-product write it replaces lived in
core/views.py and this dialog has no single product to hang a URL on.
Every view repeats the same decorator trio, in this order, so unauthenticated
and non-admin requests both leave through a 302.
"""

import datetime as dt
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid5

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
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
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.formats import date_format
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
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
    StockReceiptDraft,
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
MAX_RECEIPT_SUPPLIER_GROUPS = 20

# was core/views.MAX_RESTOCK_UNITS: a per-line input ceiling for the dialog, not
# a service rule -- the service's own ceilings stay MAX_QUANTITY / MAX_RECEIPT_LINES.
MAX_RECEIPT_LINE_UNITS = 100_000
MAX_RECEIPT_DIALOG_ROWS = 50
RECEIPT_UNIT_PRESETS = (12, 24, 48, 100)


def _line_context(
    product_id="",
    product=None,
    units="",
    unit_cost="",
    selling_price="",
    group_index=0,
    error=False,
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
        "group_index": group_index,
        "error": error,
    }


def _supplier_group_context(
    group_index=0,
    *,
    supplier_name="",
    external_reference="",
    lines=None,
):
    return {
        "group_index": group_index,
        "supplier_name": supplier_name,
        "external_reference": external_reference,
        "lines": lines if lines is not None else [_line_context(group_index=group_index)],
    }


def _dialog_context(
    request,
    *,
    groups=None,
    request_key="",
    message="",
    draft_id="",
    purchased_on="",
    selected_restock=False,
    selected_count=0,
):
    context = {
        "groups": groups if groups is not None else [_supplier_group_context()],
        "request_key": request_key,
        "message": message,
        "draft_id": draft_id,
        "purchased_on": purchased_on,
        "selected_restock": selected_restock,
        "selected_count": selected_count,
        "max_units": MAX_RECEIPT_LINE_UNITS,
        "max_rows": MAX_RECEIPT_DIALOG_ROWS,
        "max_groups": MAX_RECEIPT_SUPPLIER_GROUPS,
        "price_cap": MAX_SELLING_PRICE,
        "presets": RECEIPT_UNIT_PRESETS,
    }
    context["line_count"] = sum(len(group["lines"]) for group in context["groups"])
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
    drafts = list(
        StockReceiptDraft.objects.filter(
            recorded_by=request.user,
            booked_at__isnull=True,
        ).order_by("-updated_at")
    )
    for draft in drafts:
        groups = draft.payload.get("groups", [])
        draft.supplier_count = len(groups)
        draft.line_count = sum(len(group.get("lines", [])) for group in groups)
        draft.supplier_summary = ", ".join(
            group.get("supplier_name", "").strip()
            for group in groups
            if group.get("supplier_name", "").strip()
        ) or "Supplier not entered"
    return render(
        request,
        "core/inventory/receipts.html",
        {"page_obj": page, "drafts": drafts},
    )


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


class _ReceiptBookingProblem(Exception):
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
        if not unit_cost.is_finite():
            raise _ReceiptLineProblem(row, f"Line {row} has an unreadable unit cost.")
        if abs(unit_cost) > Decimal("99999999.99"):
            raise _ReceiptLineProblem(row, f"Line {row} has a unit cost that is too large.")
        selling_price = None
        if raw_price:
            try:
                selling_price = Decimal(raw_price)
            except InvalidOperation:
                raise _ReceiptLineProblem(
                    row, f"Line {row} has an unreadable selling price."
                ) from None
            if not selling_price.is_finite():
                raise _ReceiptLineProblem(
                    row, f"Line {row} has an unreadable selling price."
                )
            if selling_price < -MAX_SELLING_PRICE:
                raise _ReceiptLineProblem(
                    row, f"Line {row} has an invalid selling price."
                )
            if selling_price > MAX_SELLING_PRICE:
                raise _ReceiptLineProblem(
                    row,
                    f"Line {row} cannot sell above GH₵ {MAX_SELLING_PRICE}; "
                    "checkout refuses a sale line bigger than that.",
                )
        lines.append(ReceiptLine(UUID(product_id), quantity, unit_cost, selling_price))
    return lines


def _read_receipt_groups(request):
    """Validate supplier headers and assign every product line to its supplier."""
    supplier_names = request.POST.getlist("supplier_name[]")
    references = request.POST.getlist("external_reference[]")
    raw_group_ids = request.POST.getlist("supplier_group_index[]")
    if not supplier_names and "supplier_name" in request.POST:
        supplier_names = [request.POST.get("supplier_name", "")]
    if not references and "external_reference" in request.POST:
        references = [request.POST.get("external_reference", "")]
    if not supplier_names:
        supplier_names = [""]
    if not references:
        references = [""]
    if not raw_group_ids:
        raw_group_ids = [str(index) for index in range(len(supplier_names))]
    if len(supplier_names) != len(references):
        raise _ReceiptLineProblem(
            0, "Supplier details arrived incomplete. Review the delivery and try again."
        )
    if len(raw_group_ids) != len(supplier_names):
        raise _ReceiptLineProblem(
            0, "Supplier groups arrived incomplete. Review the delivery and try again."
        )
    if len(supplier_names) > MAX_RECEIPT_SUPPLIER_GROUPS:
        raise _ReceiptLineProblem(
            0, f"A delivery can have at most {MAX_RECEIPT_SUPPLIER_GROUPS} suppliers."
        )

    try:
        group_ids = [int(value) for value in raw_group_ids]
    except (TypeError, ValueError):
        raise _ReceiptLineProblem(0, "A supplier group has an invalid identifier.") from None
    if (
        len(set(group_ids)) != len(group_ids)
        or any(index < 0 or index >= MAX_RECEIPT_SUPPLIER_GROUPS for index in group_ids)
    ):
        raise _ReceiptLineProblem(0, "A supplier group has an invalid identifier.")
    group_positions = {group_id: position for position, group_id in enumerate(group_ids)}

    raw_indexes = request.POST.getlist("line_group_index[]")
    raw_line_ids = request.POST.getlist("line_product_id[]")
    if not raw_indexes:
        raw_indexes = ["0"] * len(raw_line_ids)
    if len(raw_indexes) != len(raw_line_ids):
        raise _ReceiptLineProblem(
            0, "Supplier line assignments arrived incomplete. Review and try again."
        )
    try:
        indexes = [int(value) for value in raw_indexes]
    except (TypeError, ValueError):
        raise _ReceiptLineProblem(0, "A line has an invalid supplier assignment.") from None
    if any(index not in group_positions for index in indexes):
        raise _ReceiptLineProblem(0, "A line has an invalid supplier assignment.")

    lines = _read_receipt_lines(request)
    groups = [
        {
            "supplier_name": supplier_names[index].strip(),
            "external_reference": references[index].strip(),
            "group_index": group_ids[index],
            "lines": [],
        }
        for index in range(len(supplier_names))
    ]
    for index, line in zip(indexes, lines):
        groups[group_positions[index]]["lines"].append(line)
    return [group for group in groups if group["lines"]]


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


def _posted_groups(request, error_row=0):
    """The supplier groups and rows the owner typed, back into template contexts.

    A product id that no longer resolves keeps its raw value in the hidden
    field and shows no name, so the owner sees exactly what is wrong rather
    than a silently emptied row.
    """
    product_ids = request.POST.getlist("line_product_id[]")
    units = request.POST.getlist("line_units[]")
    costs = request.POST.getlist("line_unit_cost[]")
    prices = request.POST.getlist("line_selling_price[]")
    supplier_names = request.POST.getlist("supplier_name[]") or [
        request.POST.get("supplier_name", "")
    ]
    references = request.POST.getlist("external_reference[]") or [
        request.POST.get("external_reference", "")
    ]
    raw_indexes = request.POST.getlist("line_group_index[]") or ["0"] * len(product_ids)
    raw_group_ids = request.POST.getlist("supplier_group_index[]") or [
        str(index) for index in range(len(supplier_names))
    ]
    try:
        group_indexes = [int(value) for value in raw_indexes]
    except (ValueError, TypeError):
        group_indexes = [0] * len(product_ids)
    try:
        group_ids = [int(value) for value in raw_group_ids]
    except (ValueError, TypeError):
        group_ids = list(range(len(supplier_names)))
    group_ids.extend(
        index
        for index in sorted(set(group_indexes))
        if index not in group_ids
    )
    group_ids = group_ids[:MAX_RECEIPT_SUPPLIER_GROUPS]
    group_positions = {group_id: index for index, group_id in enumerate(group_ids)}
    groups = [
        _supplier_group_context(
            group_id,
            supplier_name=supplier_names[index] if index < len(supplier_names) else "",
            external_reference=references[index] if index < len(references) else "",
            lines=[],
        )
        for index, group_id in enumerate(group_ids)
    ]
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
        raw_group_index = group_indexes[index - 1] if index - 1 < len(group_indexes) else 0
        group_index = group_positions.get(raw_group_index, 0)
        rows.append(
            _line_context(
                product_id=raw_id,
                product=known.get(pk),
                units=raw_units,
                unit_cost=raw_cost,
                selling_price=raw_price,
                group_index=groups[group_index]["group_index"],
                error=(index == error_row),
            )
        )
    for row in rows:
        groups[group_positions.get(row["group_index"], 0)]["lines"].append(row)
    for group in groups:
        if not group["lines"]:
            group["lines"].append(_line_context(group_index=group["group_index"]))
    return groups


def _booking_payload(purchased_on, groups):
    return {
        "purchased_on": purchased_on.isoformat() if purchased_on else "",
        "groups": [
            {
                "supplier_name": group["supplier_name"],
                "external_reference": group["external_reference"],
                "lines": [
                    {
                        "product_id": str(line.product_id),
                        "units": line.quantity,
                        "unit_cost": format(line.unit_cost.quantize(Decimal("0.01")), ".2f"),
                        "selling_price": (
                            format(line.selling_price.quantize(Decimal("0.01")), ".2f")
                            if line.selling_price is not None
                            else ""
                        ),
                    }
                    for line in group["lines"]
                ],
            }
            for group in groups
        ],
    }


def _book_receipt(request):
    """Book all supplier receipts together, or none of them."""
    try:
        groups = _read_receipt_groups(request)
    except _ReceiptLineProblem as problem:
        return _refused(request, problem.row, problem.message)

    raw_purchased_on = request.POST.get("purchased_on", "")
    try:
        purchased_on = dt.date.fromisoformat(raw_purchased_on) if raw_purchased_on else None
    except ValueError:
        return _refused(request, 0, "Enter a purchase date as YYYY-MM-DD, or leave it empty.")

    try:
        request_key = _posted_request_key(request)
        draft_id = request.POST.get("draft_id", "").strip()
        booking_payload = _booking_payload(purchased_on, groups)
        with transaction.atomic():
            draft = None
            legacy_replay = False
            if draft_id:
                try:
                    draft_uuid = UUID(draft_id)
                except (ValueError, TypeError):
                    return _refused(request, 0, "This saved draft could not be found.")
                draft = (
                    StockReceiptDraft.objects.select_for_update()
                    .filter(pk=draft_uuid, recorded_by=request.user)
                    .first()
                )
                if draft is None:
                    return _refused(request, 0, "This saved draft could not be found.")
                if draft.booked_at is not None:
                    receipts = list(draft.receipts.order_by("draft_group_index"))
                    if not receipts:
                        logger.error(
                            "Booked receipt draft %s has no linked receipts", draft.pk
                        )
                        return _refused(
                            request,
                            0,
                            "This saved draft has no linked receipts. Contact an administrator.",
                        )
                    return _booked_response(request, receipts)
            else:
                draft = (
                    StockReceiptDraft.objects.select_for_update()
                    .filter(request_key=request_key)
                    .first()
                )
                if draft is not None:
                    if draft.recorded_by_id != request.user.pk:
                        raise ValidationError(
                            {"request_key": "This request key belongs to another account."}
                        )
                    if draft.payload != booking_payload:
                        raise ValidationError(
                            {"request_key": "This request key was already used for different data."}
                        )
                    if draft.booked_at is not None:
                        receipts = list(draft.receipts.order_by("draft_group_index"))
                        if not receipts:
                            logger.error(
                                "Booked receipt operation %s has no linked receipts",
                                draft.pk,
                            )
                            return _refused(
                                request,
                                0,
                                "This saved delivery has no linked receipts. Contact an administrator.",
                            )
                        return _booked_response(request, receipts)
                    raise ValidationError(
                        {"request_key": "This delivery booking is already in progress. Try again."}
                    )

                # Preserve replay behavior for single receipts recorded before
                # delivery-level request keys were introduced.
                prior_receipt = StockReceipt.objects.filter(
                    request_key=request_key,
                    draft__isnull=True,
                ).first()
                if prior_receipt is not None:
                    if len(groups) != 1 or groups[0]["group_index"] != 0:
                        raise ValidationError(
                            {"request_key": "This request key was already used for different data."}
                        )
                    legacy_replay = True
                else:
                    draft = StockReceiptDraft.objects.create(
                        recorded_by=request.user,
                        request_key=request_key,
                        payload=booking_payload,
                    )

            receipts = []
            received_at = timezone.now()
            all_product_ids = {
                line.product_id
                for group in groups
                for line in group["lines"]
            }
            list(
                Product.objects.select_for_update()
                .filter(pk__in=all_product_ids)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            row_offset = 0
            for group in groups:
                group_index = group["group_index"]
                group_key = (
                    request_key
                    if len(groups) == 1 and group_index == 0
                    else uuid5(request_key, f"supplier-group-{group_index}")
                )
                try:
                    receipts.append(
                        receive_stock(
                            actor=request.user,
                            request_key=group_key,
                            lines=group["lines"],
                            received_at=received_at,
                            source=StockReceiptSource.PURCHASE,
                            purchased_on=purchased_on,
                            supplier_name=group["supplier_name"],
                            external_reference=group["external_reference"],
                            draft=None if legacy_replay else draft,
                            draft_group_index=group_index if draft is not None else None,
                        )
                    )
                except (ValueError, ValidationError) as error:
                    row, message = _describe_service_error(error)
                    if row:
                        row += row_offset
                        message = re.sub(r"^Line \d+:", f"Line {row}:", message)
                    raise _ReceiptBookingProblem(row, message) from error
                row_offset += len(group["lines"])
            if draft is not None:
                draft.booked_at = received_at
                draft.save(update_fields=["booked_at", "updated_at"])
    except _ReceiptBookingProblem as problem:
        return _refused(request, problem.row, problem.message)
    except (ValueError, ValidationError) as error:
        row, message = _describe_service_error(error)
        return _refused(request, row, message)
    except DatabaseError:
        logger.exception("Multi-supplier receipt failed for user %s", request.user.pk)
        return _refused(request, 0, "The receipt could not be saved. Try again.")

    return _booked_response(request, receipts)


def _booked_response(request, receipts):
    line_count = sum(receipt.batches.count() for receipt in receipts)
    units = sum(
        batch.quantity_received
        for receipt in receipts
        for batch in receipt.batches.all()
    )
    receipt_codes = ", ".join(f"#{str(receipt.pk)[:8]}" for receipt in receipts)
    response = render(
        request,
        "core/products/response.html",
        {
            "type": "success",
            "message": f"{line_count} line(s) booked across {len(receipts)} receipt(s) "
            f"{receipt_codes}: {units:,} units onto the shelf.",
        },
    )
    response = trigger_client_event(response, "reload_products_table")
    return trigger_client_event(response, "reload_stock_receipts")


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
    draft_id = request.POST.get("draft_id", "")
    try:
        draft_id = str(UUID(draft_id)) if draft_id else ""
    except (ValueError, TypeError, AttributeError):
        draft_id = ""
    return render(
        request,
        "core/products/modals/receive_stock.html",
        _dialog_context(
            request,
            groups=_posted_groups(request, error_row=row),
            request_key=key,
            message=message,
            draft_id=draft_id,
            purchased_on=request.POST.get("purchased_on", ""),
        ),
    )


@login_required
@require_GET
@user_passes_test(is_admin)
def receipt_line_blank(request):
    """One empty line, swapped into the open dialog by 'Add another product'."""
    try:
        group_index = int(request.GET.get("group_index", "0"))
    except ValueError:
        group_index = 0
    group_index = max(0, min(group_index, MAX_RECEIPT_SUPPLIER_GROUPS - 1))
    return render(
        request,
        "core/products/partials/receipt_line_row.html",
        {
            "line": _line_context(group_index=group_index),
            "max_units": MAX_RECEIPT_LINE_UNITS,
            "presets": RECEIPT_UNIT_PRESETS,
        },
    )


def _clean_draft_payload(raw_payload):
    if not isinstance(raw_payload, dict):
        raise ValueError("Draft data must be an object.")
    purchased_on = raw_payload.get("purchased_on", "")
    if not isinstance(purchased_on, str) or len(purchased_on) > 10:
        raise ValueError("Enter a valid purchase date.")
    if purchased_on:
        try:
            dt.date.fromisoformat(purchased_on)
        except ValueError as error:
            raise ValueError("Enter a valid purchase date.") from error
    raw_groups = raw_payload.get("groups")
    if (
        not isinstance(raw_groups, list)
        or not 1 <= len(raw_groups) <= MAX_RECEIPT_SUPPLIER_GROUPS
    ):
        raise ValueError(
            f"A draft needs between 1 and {MAX_RECEIPT_SUPPLIER_GROUPS} supplier groups."
        )
    groups = []
    total_lines = 0
    for group in raw_groups:
        if not isinstance(group, dict):
            raise ValueError("Draft supplier data is invalid.")
        supplier_name = group.get("supplier_name", "")
        external_reference = group.get("external_reference", "")
        raw_lines = group.get("lines")
        if (
            not isinstance(supplier_name, str)
            or len(supplier_name) > 255
            or not isinstance(external_reference, str)
            or len(external_reference) > 255
            or not isinstance(raw_lines, list)
        ):
            raise ValueError("Draft supplier details are invalid.")
        lines = []
        for line in raw_lines:
            if not isinstance(line, dict):
                raise ValueError("Draft line data is invalid.")
            values = {
                key: line.get(key, "")
                for key in ("product_id", "units", "unit_cost", "selling_price")
            }
            if any(not isinstance(value, str) or len(value) > 64 for value in values.values()):
                raise ValueError("Draft line values are invalid.")
            lines.append(values)
        total_lines += len(lines)
        groups.append(
            {
                "supplier_name": supplier_name,
                "external_reference": external_reference,
                "lines": lines,
            }
        )
    if total_lines > MAX_RECEIPT_DIALOG_ROWS:
        raise ValueError(f"A draft can contain at most {MAX_RECEIPT_DIALOG_ROWS} lines.")
    return {"purchased_on": purchased_on, "groups": groups}


@login_required
@require_POST
@user_passes_test(is_admin)
def save_receipt_draft(request):
    raw_payload = request.POST.get("draft_payload", "")
    if len(raw_payload) > 256_000:
        return JsonResponse({"error": "This delivery is too large to save."}, status=413)
    try:
        payload = _clean_draft_payload(json.loads(raw_payload))
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=400)

    raw_id = request.POST.get("draft_id", "").strip()
    try:
        with transaction.atomic():
            if raw_id:
                try:
                    draft_id = UUID(raw_id)
                except (ValueError, TypeError):
                    return JsonResponse({"error": "This saved draft could not be found."}, status=404)
                draft = (
                    StockReceiptDraft.objects.select_for_update()
                    .filter(pk=draft_id, recorded_by=request.user)
                    .first()
                )
                if draft is None:
                    return JsonResponse({"error": "This saved draft could not be found."}, status=404)
                if draft.booked_at is not None:
                    return JsonResponse({"error": "This delivery has already been booked."}, status=409)
                draft.payload = payload
                draft.save(update_fields=["payload", "updated_at"])
            else:
                draft = StockReceiptDraft.objects.create(
                    recorded_by=request.user,
                    payload=payload,
                )
    except DatabaseError:
        logger.exception("Receipt draft save failed for user %s", request.user.pk)
        return JsonResponse({"error": "The draft could not be saved. Try again."}, status=500)
    return JsonResponse(
        {
            "id": str(draft.pk),
            "updated_at": draft.updated_at.isoformat(),
            "updated_at_display": date_format(
                timezone.localtime(draft.updated_at), "d M Y H:i"
            ),
        }
    )


@login_required
@require_POST
@user_passes_test(is_admin)
def delete_receipt_draft(request, draft_id):
    with transaction.atomic():
        draft = get_object_or_404(
            StockReceiptDraft.objects.select_for_update().filter(booked_at__isnull=True),
            pk=draft_id,
            recorded_by=request.user,
        )
        draft.delete()
    return redirect("core:stock-receipts")


@login_required
@require_GET
@user_passes_test(is_admin)
def receipt_supplier_group_blank(request):
    try:
        group_index = int(request.GET.get("group_index", ""))
    except ValueError:
        return JsonResponse({"error": "Choose a valid supplier group."}, status=400)
    if not 0 <= group_index < MAX_RECEIPT_SUPPLIER_GROUPS:
        return JsonResponse({"error": "This delivery already has the maximum suppliers."}, status=400)
    return render(
        request,
        "core/products/partials/receipt_supplier_group.html",
        {
            "group": _supplier_group_context(group_index),
            "max_units": MAX_RECEIPT_LINE_UNITS,
            "presets": RECEIPT_UNIT_PRESETS,
            "is_first": False,
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
    groups = [_supplier_group_context()]
    draft_id = request.GET.get("draft_id", "").strip()
    purchased_on = ""
    if draft_id:
        draft = get_object_or_404(
            StockReceiptDraft,
            pk=draft_id,
            recorded_by=request.user,
        )
        if draft.booked_at is not None:
            receipts = list(draft.receipts.order_by("draft_group_index"))
            if receipts and request.headers.get("HX-Request") == "true":
                return _booked_response(request, receipts)
            if not receipts:
                logger.error("Booked receipt draft %s has no linked receipts", draft.pk)
            return redirect("core:stock-receipts")
        raw_groups = draft.payload.get("groups", [])
        product_ids = []
        for group in raw_groups:
            for line in group.get("lines", []):
                try:
                    product_ids.append(UUID(line.get("product_id", "")))
                except (ValueError, TypeError):
                    pass
        products = {
            product.pk: product
            for product in Product.objects.filter(pk__in=product_ids)
        }
        groups = []
        for index, raw_group in enumerate(raw_groups):
            lines = []
            for raw_line in raw_group.get("lines", []):
                try:
                    product_id = UUID(raw_line.get("product_id", ""))
                except (ValueError, TypeError):
                    product_id = None
                lines.append(
                    _line_context(
                        product_id=str(product_id or raw_line.get("product_id", "")),
                        product=products.get(product_id),
                        units=raw_line.get("units", ""),
                        unit_cost=raw_line.get("unit_cost", ""),
                        selling_price=raw_line.get("selling_price", ""),
                        group_index=index,
                    )
                )
            groups.append(
                _supplier_group_context(
                    index,
                    supplier_name=raw_group.get("supplier_name", ""),
                    external_reference=raw_group.get("external_reference", ""),
                    lines=lines or [_line_context(group_index=index)],
                )
            )
        purchased_on = draft.payload.get("purchased_on", "")
    raw_product_id = request.GET.get("product_id")
    if raw_product_id and not draft_id:
        product = Product.objects.filter(pk=raw_product_id).first()
        if product is not None:
            groups = [
                _supplier_group_context(
                    lines=[_line_context(
                    product_id=str(product.pk),
                    product=product,
                    units=RECEIPT_UNIT_PRESETS[1],
                    unit_cost=product.cost,
                    )]
                )
            ]
        # a product that is gone leaves a blank dialog rather than a 404: the
        # dialog is for the delivery, and the owner can still book the rest of it.
    return render(
        request,
        "core/products/modals/receive_stock.html",
        _dialog_context(
            request,
            groups=groups,
            draft_id=draft_id,
            purchased_on=purchased_on,
        ),
    )


@login_required
@user_passes_test(is_admin)
@require_POST
def receive_selected_stock_question(request):
    """Open the receipt dialog with the selected depleted products prefilled."""
    raw_ids = request.POST.getlist("ids")
    try:
        product_ids = list(dict.fromkeys(UUID(raw_id) for raw_id in raw_ids))
    except (TypeError, ValueError):
        return _selected_restock_error(
            request,
            "The selection is invalid. Refresh the depleted products and try again.",
        )

    if not product_ids:
        return _selected_restock_error(
            request, "Select at least one depleted product to restock."
        )
    if len(product_ids) > MAX_RECEIPT_DIALOG_ROWS:
        product_label = "product" if MAX_RECEIPT_DIALOG_ROWS == 1 else "products"
        return _selected_restock_error(
            request,
            f"Batch restock supports up to {MAX_RECEIPT_DIALOG_ROWS} selected {product_label}. "
            "Select fewer products and try again.",
        )

    products = {
        product.pk: product
        for product in Product.objects.filter(pk__in=product_ids)
    }
    if len(products) != len(product_ids) or any(
        products[product_id].stock != 0
        for product_id in product_ids
        if product_id in products
    ):
        return _selected_restock_error(
            request,
            "Some selected products could not be found or are no longer depleted. "
            "Refresh the list and try again.",
        )

    lines = [
        _line_context(
            product_id=str(product_id),
            product=products[product_id],
            unit_cost=products[product_id].cost,
            group_index=0,
        )
        for product_id in product_ids
    ]
    return render(
        request,
        "core/products/modals/receive_stock.html",
        _dialog_context(
            request,
            groups=[_supplier_group_context(lines=lines)],
            selected_restock=True,
            selected_count=len(lines),
        ),
    )


def _selected_restock_error(request, message):
    return render(
        request,
        "core/products/modals/receive_stock.html",
        _dialog_context(request, message=message, selected_restock=True),
    )
