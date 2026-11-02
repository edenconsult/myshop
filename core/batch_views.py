"""GET-only question views for the batch dialogs.

Writes keep flowing through the existing POST endpoints in core/views.py;
every view in this module repeats the same decorator trio, in this order,
so unauthenticated and non-admin requests both leave through a 302.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import IntegerField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from core.models import (
    Product,
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
)
from utils import is_admin  # same helper core/views.py uses


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
    # sold and adjusted come from two different multi-valued relationships.
    # One annotate() over both would multiply the joins (2 allocations x 2
    # adjustments => each Sum reads 4 rows and both totals inflate), so each
    # relation is aggregated on its own in a correlated subquery, the same
    # fan-out-safe shape the receipt register uses.
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
    batches = list(
        StockBatch.objects.filter(product=product)
        .select_related("receipt")
        .annotate(
            sold=Coalesce(
                Subquery(allocation_sum, output_field=IntegerField()),
                0,
                output_field=IntegerField(),
            ),
            adjusted=Coalesce(
                Subquery(adjustment_sum, output_field=IntegerField()),
                0,
                output_field=IntegerField(),
            ),
        )
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
