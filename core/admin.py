from django.contrib import admin

from .models import (
    Order,
    OrderItem,
    Product,
    ProductImportOperation,
    SaleBatchAllocation,
    StockAdjustment,
    StockBatch,
    StockReceipt,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    readonly_fields = ("stock",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyHistoryAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Order, ReadOnlyHistoryAdmin)
admin.site.register(OrderItem, ReadOnlyHistoryAdmin)
admin.site.register(StockReceipt, ReadOnlyHistoryAdmin)
admin.site.register(StockBatch, ReadOnlyHistoryAdmin)
admin.site.register(SaleBatchAllocation, ReadOnlyHistoryAdmin)
admin.site.register(StockAdjustment, ReadOnlyHistoryAdmin)
admin.site.register(ProductImportOperation, ReadOnlyHistoryAdmin)
