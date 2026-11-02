from django.urls import include, path

from . import batch_views, views

app_name = "core"

urlpatterns = [
    path("", views.index, name="base"),
    path(
        "products/",
        include(
            [
                path("", views.products_home, name="products"),
                path("summary/", views.products_summary, name="products-summary"),
                path("load-products/", views.load_products, name="load-products"),
                path(
                    "<uuid:product_id>/update-stocks",
                    views.update_product_stock,
                    name="update-product-stock",
                ),
                path("import-products/", views.import_products, name="import-products"),
                path(
                    "import-products/do",
                    views.do_import_products,  # type: ignore
                    name="do-import-products",
                ),
                path(
                    "import-products/track_progress/<task_id>",
                    views.track_import_progress,
                    name="import-products-status",
                ),
                path(
                    "remove-products/question",
                    views.remove_all_products_question,
                    name="remove-products-question",
                ),
                path(
                    "remove-products/do",
                    views.do_remove_products,
                    name="do-remove-products",
                ),
                path(
                    "remove-products/track_progress/<task_id>",
                    views.track_remove_product_progress,
                    name="remove-products-status",
                ),
                path(
                    "add-product",
                    views.add_product,
                    name="add-product",
                ),
                path(
                    "<uuid:product_id>/update-product",
                    views.add_product,
                    name="update-product",
                ),
                path(
                    "<uuid:product_id>/restock-product",
                    views.restock_product,
                    name="restock-product",
                ),
                path(
                    "stock/<uuid:product_id>/adjust/",
                    batch_views.adjust_stock_question,
                    name="adjust-stock-question",
                ),
                path(
                    "stock/<uuid:product_id>/batches/",
                    batch_views.product_batches,
                    name="product-batches",
                ),
                path("receipts/", batch_views.stock_receipts, name="stock-receipts"),
                path(
                    "receipts/<uuid:receipt_id>/",
                    batch_views.stock_receipt_detail,
                    name="stock-receipt-detail",
                ),
                path(
                    "<uuid:product_id>/remove-product",
                    views.remove_a_product_question,
                    name="remove-a-product-question",
                ),
                path(
                    "<uuid:product_id>/remove-product/do",
                    views.do_remove_a_product,
                    name="do-remove-a-product",
                ),
            ]
        ),
    ),
    path(
        "orders/",
        include(
            [
                path("", views.orders, name="orders"),
                path("sell-products/", views.orders_products, name="orders-products"),
                path(
                    "sell-products/load/",
                    views.load_orders_products,
                    name="load-orders-products",
                ),
                path("make-order/", views.make_order, name="make-order"),
                path("check-orders/", views.today_orders, name="today-orders"),
                path(
                    "check-orders/ledger/",
                    views.orders_ledger,
                    name="orders-ledger",
                ),
                path(
                    "check-orders/export-csv/",
                    views.export_orders_csv,
                    name="orders-export-csv",
                ),
                path(
                    "check-orders/days",
                    views.fetch_days_orders,
                    name="fetch-days-orders",
                ),
                path(
                    "checks-orders/<date>/<users>/print",
                    views.print_todays_orders,
                    name="print-todays-orders",
                ),
                path("shop-cart/", views.shop_cart, name="shop-cart"),
                path(
                    "view-order/<uuid:order_id>/<int:order_number>",
                    views.view_order,
                    name="view-order",
                ),
                path(
                    "view-order/<uuid:order_id>/<int:order_number>/print-pdf",
                    views.print_order_pdf,
                    name="print-order-pdf",
                ),
                path(
                    "sales-reports/body/",
                    views.sales_report_body,
                    name="sales-report",
                ),
                path(
                    "sales-reports/ledger/",
                    views.sales_report_ledger,
                    name="sales-report-ledger",
                ),
                path(
                    "sales-reports/export-csv/",
                    views.sales_report_csv,
                    name="sales-report-csv",
                ),
                path(
                    "sales-reports/print-pdf/",
                    views.sales_report_pdf,
                    name="sales-report-pdf",
                ),
            ]
        ),
    ),
]
