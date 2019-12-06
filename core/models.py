import os
from django.dispatch import receiver
from django.conf import settings
from django.db import models
from django.shortcuts import reverse
from django_countries.fields import CountryField

CATEGORY_CHOICES = (
    ('S', 'Shirt'),
    ('SW', 'Sport Wear'),
    ('OW', 'Outwear'),
)

LABEL_CHOICES = (
    ('P', 'primary'),
    ('S', 'secondary'),
    ('D', 'danger'),
)

ADDRESS_CHOICES = (
    ('B', 'Billing'),
    ('S', 'Shipping'),
)


class Item(models.Model):
    title = models.CharField(max_length=100)
    price = models.IntegerField()
    discount_price = models.IntegerField(blank=True, null=True)
    category = models.CharField(choices=CATEGORY_CHOICES, max_length=2)
    label = models.CharField(choices=LABEL_CHOICES, max_length=1)
    slug = models.SlugField()
    description = models.TextField()
    image = models.ImageField()
    image_secondary_1 = models.ImageField(blank=True, null=True)
    image_secondary_2 = models.ImageField(blank=True, null=True)
    image_secondary_3 = models.ImageField(blank=True, null=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        # Return a reverse to 'core' namespace
        # and 'product' url name
        return reverse("core:product", kwargs={
            'slug': self.slug
        })

    def get_add_to_cart_url(self):
        return reverse("core:add-to-cart", kwargs={
            'slug': self.slug,
        })

    def get_remove_from_cart_url(self):
        return reverse("core:remove-from-cart", kwargs={
            'slug': self.slug,
        })

    def get_secondary_images(self):
        secondary_images = []
        if self.image_secondary_1:
            secondary_images.append(self.image_secondary_1)
        if self.image_secondary_2:
            secondary_images.append(self.image_secondary_2)
        if self.image_secondary_3:
            secondary_images.append(self.image_secondary_3)
        return secondary_images

# These two auto-delete files from filesystem when they are unneeded


@receiver(models.signals.post_delete, sender=Item)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes file from filesystem
    when corresponding 'MediaFile' oject is deleted.
    """
    if os.path.isfile(instance.image.path):
        os.remove(instance.image.path)
    if instance.image_secondary_1:
        if os.path.isfile(instance.image_secondary_1.path):
            os.remove(instance.image_secondary_1.path)
    if instance.image_secondary_2:
        if os.path.isfile(instance.image_secondary_2.path):
            os.remove(instance.image_secondary_2.path)
    if instance.image_secondary_3:
        if os.path.isfile(instance.image_secondary_3.path):
            os.remove(instance.image_secondary_3.path)


@receiver(models.signals.pre_save, sender=Item)
def auto_delete_file_on_change(sender, instance, **kwargs):
    """
    Deletes old file from filesystem
    when corresponding 'MediaFile' object is updated
    with new file.
    """
    if not instance.pk:
        return False

    old_image = Item.objects.get(pk=instance.pk).image
    old_image_secondary_1 = Item.objects.get(
        pk=instance.pk).image_secondary_1
    old_image_secondary_2 = Item.objects.get(
        pk=instance.pk).image_secondary_2
    old_image_secondary_3 = Item.objects.get(
        pk=instance.pk).image_secondary_3

    new_image = instance.image
    new_image_secondary_1 = instance.image_secondary_1
    new_image_secondary_2 = instance.image_secondary_2
    new_image_secondary_3 = instance.image_secondary_3
    if not old_image == new_image:
        if os.path.isfile(old_image.path):
            os.remove(old_image.path)
    if old_image_secondary_1 and not old_image_secondary_1 == new_image_secondary_1:
        if os.path.isfile(old_image_secondary_1.path):
            os.remove(old_image_secondary_1.path)
    if old_image_secondary_2 and not old_image_secondary_2 == new_image_secondary_2:
        if os.path.isfile(old_image_secondary_2.path):
            os.remove(old_image_secondary_2.path)
    if old_image_secondary_3 and not old_image_secondary_3 == new_image_secondary_3:
        if os.path.isfile(old_image_secondary_3.path):
            os.remove(old_image_secondary_3.path)


class OrderItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f'{self.quantity} of {self.item.title}'

    def get_total_item_price(self):
        return self.quantity * self.item.price

    def get_total_discount_item_price(self):
        if self.item.discount_price:
            return self.quantity * self.item.discount_price

    def get_amount_saved(self):
        return self.get_total_item_price() - self.get_total_discount_item_price()

    def get_final_price(self):
        if self.item.discount_price:
            return self.get_total_discount_item_price()
        else:
            return self.get_total_item_price()


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    ref_code = models.CharField(max_length=20, blank=True, null=True)
    items = models.ManyToManyField(OrderItem, )
    start_date = models.DateTimeField(auto_now_add=True)
    ordered_date = models.DateTimeField()
    ordered = models.BooleanField(default=False)
    billing_address = models.ForeignKey(
        'Address', related_name='billing_address', on_delete=models.SET_NULL, blank=True, null=True)
    shipping_address = models.ForeignKey(
        'Address', related_name='shipping_address', on_delete=models.SET_NULL, blank=True, null=True)
    payment = models.ForeignKey(
        'Payment', on_delete=models.SET_NULL, blank=True, null=True)
    coupon = models.ForeignKey(
        'Coupon', on_delete=models.SET_NULL, blank=True, null=True)
    being_delivered = models.BooleanField(default=False)
    received = models.BooleanField(default=False)
    refund_requested = models.BooleanField(default=False)
    refund_granted = models.BooleanField(default=False)

    '''
    --- Stages of an Order ---
    1. Item added to cart
    2. Adding billing address
    (Failed checkout)
    3. Payment
    (Preprocessing, processing, packaging, etc.)
    4. Being delivered
    5. Received
    6. Refunds
    '''

    def __str__(self):
        return self.user.username

    def get_total(self):
        total = 0
        for order_item in self.items.all():
            total += order_item.get_final_price()
        if self.coupon:
            total -= self.coupon.amount
        return total if total > 0 else 0

    def get_total_quantity(self):
        total_quantity = 0
        for order_item in self.items.all():
            total_quantity += order_item.quantity
        return total_quantity


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)
    street_address = models.CharField(max_length=100)
    apartment_address = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    country = CountryField(multiple=False)
    post_code = models.CharField(max_length=20)
    address_type = models.CharField(max_length=1, choices=ADDRESS_CHOICES)
    # Use as default billing/shipping
    default = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.username}:{self.city}'

    class Meta:
        verbose_name_plural = 'Addresses'


class Payment(models.Model):
    stripe_charge_id = models.CharField(max_length=50)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.SET_NULL, blank=True, null=True)
    amount = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


class Coupon(models.Model):
    code = models.CharField(max_length=15)
    amount = models.IntegerField()

    def __str__(self):
        return self.code


class Refund(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    reason = models.TextField()
    email = models.EmailField()
    accepted = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.pk}'
