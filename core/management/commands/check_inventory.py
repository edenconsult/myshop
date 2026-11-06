from django.core.management.base import BaseCommand, CommandError
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
    Value,
)
from django.db.models.functions import Coalesce

from core.models import (
    Order,
    OrderItem,
    Product,
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
)


class Command(BaseCommand):
    help = "Read-only reconciliation of product, batch, and sale-cost invariants"

    def handle(self, *args, **options):
        issues = []
        product_totals = Product.objects.annotate(
            batch_total=Coalesce(
                Sum("batches__quantity_remaining"),
                Value(0),
                output_field=IntegerField(),
            )
        )
        self._record(
            issues,
            "Product stock differs from remaining batches",
            product_totals.exclude(stock=F("batch_total")).values_list("pk", flat=True),
        )
        self._record(
            issues,
            "Products have negative reference cost or selling price",
            Product.objects.filter(Q(cost__lt=0) | Q(price__lt=0)).values_list(
                "pk", flat=True
            ),
        )

        sale_quantity = (
            SaleBatchAllocation.objects.filter(batch_id=OuterRef("pk"))
            .values("batch_id")
            .annotate(total=Sum("quantity"))
            .values("total")[:1]
        )
        adjustment_quantity = (
            StockAdjustment.objects.filter(batch_id=OuterRef("pk"))
            .values("batch_id")
            .annotate(total=Sum("quantity_delta"))
            .values("total")[:1]
        )
        batches = StockBatch.objects.annotate(
            sold=Coalesce(
                Subquery(sale_quantity, output_field=IntegerField()),
                Value(0),
                output_field=IntegerField(),
            ),
            adjusted=Coalesce(
                Subquery(adjustment_quantity, output_field=IntegerField()),
                Value(0),
                output_field=IntegerField(),
            ),
        )
        self._record(
            issues,
            "Batch remainder differs from receipt, adjustments, and allocations",
            batches.exclude(
                quantity_remaining=(
                    F("quantity_received") + F("adjusted") - F("sold")
                )
            ).values_list("pk", flat=True),
        )

        allocation_quantity = (
            SaleBatchAllocation.objects.filter(order_item_id=OuterRef("pk"))
            .values("order_item_id")
            .annotate(total=Sum("quantity"))
            .values("total")[:1]
        )
        allocation_count = (
            SaleBatchAllocation.objects.filter(order_item_id=OuterRef("pk"))
            .values("order_item_id")
            .annotate(total=Count("pk"))
            .values("total")[:1]
        )
        allocation_cost = (
            SaleBatchAllocation.objects.filter(order_item_id=OuterRef("pk"))
            .values("order_item_id")
            .annotate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantity") * F("unit_cost"),
                        output_field=DecimalField(max_digits=20, decimal_places=2),
                    )
                )
            )
            .values("total")[:1]
        )
        items = OrderItem.objects.annotate(
            allocation_units=Coalesce(
                Subquery(allocation_quantity, output_field=IntegerField()),
                Value(0),
                output_field=IntegerField(),
            ),
            allocation_count=Coalesce(
                Subquery(allocation_count, output_field=IntegerField()),
                Value(0),
                output_field=IntegerField(),
            ),
            allocation_cost=Coalesce(
                Subquery(
                    allocation_cost,
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                ),
                Value(0, output_field=DecimalField(max_digits=20, decimal_places=2)),
            ),
        )
        invalid_items = items.filter(
            Q(
                order__checkout_request_key__isnull=False,
                allocation_count=0,
            )
            | (
                Q(order__checkout_request_key__isnull=False)
                & (
                    ~Q(allocation_units=F("qty_bought"))
                    | ~Q(cost_amount=F("allocation_cost"))
                )
            )
        )
        self._record(
            issues,
            "Sale line allocation or cost snapshot is inconsistent",
            invalid_items.values_list("pk", flat=True),
        )
        self._record(
            issues,
            "Sale allocation product does not match its sale line",
            SaleBatchAllocation.objects.exclude(
                order_item__product_id=F("batch__product_id")
            ).values_list("pk", flat=True),
        )

        line_totals = (
            OrderItem.objects.filter(order_id=OuterRef("pk"))
            .values("order_id")
            .annotate(total=Sum("paid_amount"))
            .values("total")[:1]
        )
        orders = Order.objects.annotate(
            line_total=Subquery(
                line_totals,
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            line_count=Count("orderitem"),
        )
        self._record(
            issues,
            "Order header total differs from its sale lines",
            orders.filter(line_count__gt=0).exclude(
                overall_amount_paid=F("line_total")
            ).values_list("pk", flat=True),
        )
        self._record(
            issues,
            "Orders have no sale lines",
            orders.filter(line_count=0).values_list("pk", flat=True),
        )

        if issues:
            for label, count, examples in issues:
                self.stderr.write(
                    self.style.ERROR(
                        f"{label}: {count} record(s); examples: {', '.join(examples)}"
                    )
                )
            raise CommandError(f"Inventory reconciliation failed with {len(issues)} issue(s).")
        self.stdout.write(self.style.SUCCESS("Inventory reconciliation passed."))

    def _record(self, issues, label, queryset):
        count = queryset.count()
        if count:
            examples = [str(pk) for pk in queryset[:10]]
            issues.append((label, count, examples))
