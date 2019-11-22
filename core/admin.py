from django.contrib import admin

from .models import Item, OrderItem, Order, BillingAddress, Payment, Coupon


class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'item', 'quantity', 'ordered')
    search_fields = ['item__title']


class OrderAdmin(admin.ModelAdmin):
    list_display = ['user', 'ordered']


admin.site.register(Item)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(BillingAddress)
admin.site.register(Payment)
admin.site.register(Coupon)
