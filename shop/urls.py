from django.urls import path
from . import views
from django.urls import path, include
urlpatterns = [
    path("accounts/", include("shop.auth_urls")),
    path("", views.home, name="home"),
    path("productos/", views.product_list, name="product_list"),
    path("producto/<int:pk>/", views.product_detail, name="product_detail"),

    path("carrito/", views.cart_detail, name="cart_detail"),
    path("carrito/agregar/<int:pk>/", views.cart_add, name="cart_add"),
    path("carrito/bajar/<int:pk>/", views.cart_decrease, name="cart_decrease"),
    path("carrito/quitar/<int:pk>/", views.cart_remove, name="cart_remove"),
    path("carrito/vaciar/", views.cart_clear, name="cart_clear"),

    path("checkout/", views.checkout, name="checkout"),

    # ✅ Seguimiento por código + comprobante
    path("mis-pedidos/", views.track_order, name="track_order"),
    path("pedido/<str:code>/", views.order_detail_code, name="order_detail_code"),
    path("pedido/<str:code>/comprobante/", views.upload_receipt, name="upload_receipt"),
    path("panel/mis-pedidos/", views.my_orders, name="my_orders"),

    # extras
    path("sobre/", views.about, name="about"),
    path("contacto/", views.contact, name="contact"),
]
