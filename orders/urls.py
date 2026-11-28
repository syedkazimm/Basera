from django.urls import path

from . import views

# The cart lives with the orders app: CartItem is its model (ERD, entity 5).
urlpatterns = [
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:pk>/", views.add_to_cart, name="cart_add"),
    path("cart/update/<int:pk>/", views.update_cart, name="cart_update"),
    path("cart/remove/<int:pk>/", views.remove_from_cart, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/<int:pk>/", views.order_summary, name="order_summary"),
]
