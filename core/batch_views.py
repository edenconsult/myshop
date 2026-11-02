"""GET-only question views for the batch dialogs.

Writes keep flowing through the existing POST endpoints in core/views.py;
every view in this module repeats the same decorator trio, in this order,
so unauthenticated and non-admin requests both leave through a 302.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from core.models import Product, StockBatch
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
