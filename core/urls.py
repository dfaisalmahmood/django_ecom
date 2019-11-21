from django.urls import path

from .views import (
    HomeView,
    ItemDetailView,
    add_to_cart,
    remove_from_cart,
    OrderSummary,
    CheckoutView,
    PaymentView,
    add_item_quantity_in_cart,
    reduce_item_quantity_in_cart,
    remove_item_in_cart
)


app_name = 'core'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('product/<slug>', ItemDetailView.as_view(), name='product'),
    path('order-summary/', OrderSummary.as_view(), name='order-summary'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('payment/<payment_option>', PaymentView.as_view(), name='payment'),
    path('add-to-cart/<slug>', add_to_cart, name='add-to-cart'),
    path('remove-from-cart/<slug>', remove_from_cart, name='remove-from-cart'),
    path('add-item-quantity-in-cart/<slug>',
         add_item_quantity_in_cart, name="add-item-quantity-in-cart"),
    path('reduce-item-quantity-in-cart/<slug>',
         reduce_item_quantity_in_cart, name='reduce-item-quantity-in-cart'),
    path('remove-item-in-cart/<slug>',
         remove_item_in_cart, name='remove-item-in-cart')
]
