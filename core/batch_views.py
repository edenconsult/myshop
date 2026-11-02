"""GET-only views for the batch dialogs and the owner's receipt register.

Writes keep flowing through the existing POST endpoints in core/views.py;
every view in this module repeats the same decorator trio, in this order,
so unauthenticated and non-admin requests both leave through a 302.
"""

from decimal import Decimal

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from core.models import (
    Product,
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
    StockReceipt,
)
from utils import is_admin  # same helper core/views.py uses

# quantity x unit cost, with room for the largest receipt the backend accepts.
BATCH_VALUE = DecimalField(max_digits=24, decimal_places=2)


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
