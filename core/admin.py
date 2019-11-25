from django.contrib import admin

from .models import Item, OrderItem, Order, Address, Payment, Coupon


class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'item', 'quantity', 'ordered')
    search_fields = ['item__title']


def accept_refund(modeladmin, request, queryset):
    queryset.update(refund_requested=False, refund_granted=True)


def reject_refund(modeladmin, request, queryset):
    queryset.update(refund_requested=False, refund_granted=True)


def revert_refund_to_pending(modeladmin, request, queryset):
    queryset.update(refund_requested=True, refund_granted=False)


def update_to_being_delivered(modeladmin, request, queryset):
    queryset.update(being_delivered=True)


def update_to_received(modeladmin, request, queryset):
    queryset.update(received=True)


accept_refund.short_description = 'Update orders to refund granted'
reject_refund.short_description = 'Update orders to refund rejected'
revert_refund_to_pending.short_description = 'Update orders to refund decision pending'
update_to_being_delivered.short_description = 'Update to being delivered'
update_to_received.short_description = 'Update to received'


class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'ordered',
        'being_delivered',
        'received',
        'refund_requested',
        'refund_granted',
        'billing_address',
        'shipping_address',
        'payment',
        'coupon',
    ]
    list_filter = [
        'user',
        'ordered',
        'being_delivered',
        'received',
        'refund_requested',
        'refund_granted'
    ]
    list_display_links = [
        'user',
        'billing_address',
        'shipping_address',
        'payment',
        'coupon'
    ]
    search_fields = [
        'user__username',
        'ref_code'
    ]

    actions = [
        accept_refund,
        reject_refund,
        revert_refund_to_pending,
        update_to_being_delivered,
        update_to_received,
    ]


class AddressAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'street_address',
        'apartment_address',
        'city',
        'country',
        'post_code',
        'address_type',
        'default',
    ]
    list_filter = [
        'default',
        'address_type',
        'country',
    ]
    search_fields = [
        'user__username',
        'street_address',
        'apartment_address',
        'post_code',
    ]


admin.site.register(Item)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(Payment)
admin.site.register(Coupon)
