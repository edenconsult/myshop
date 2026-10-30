from django.urls import include, path
from . import views

app_name = "sales"

urlpatterns = [
    path(
        "",
        include(
            [
                path("", views.index, name="base"),
                path("sell-products/", views.orders_products, name="orders-products"),
                path(
                    "sell-products/load/",
                    views.load_orders_products,
                    name="load-orders-products",
                ),
                path("make-order/", views.make_order, name="make-order"),
                path("today-orders/", views.today_orders, name="today-orders"),
                path(
                    "today-orders/print",
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
            ]
        ),
    )
]
