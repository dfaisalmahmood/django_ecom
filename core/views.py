from django.contrib import messages
from django.views.generic import ListView, DetailView, View
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.conf import settings
import stripe
import random
import string

from .models import Item, OrderItem, Order, Address, Payment, Coupon, Refund, UserProfile
from .forms import CheckoutForm, CouponForm, RefundForm, PaymentForm
from django.core.exceptions import ObjectDoesNotExist
from . import helpers

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


class HomeView(ListView):
    model = Item
    paginate_by = 10
    template_name = 'home.html'


class OrderSummary(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        context = {
            "order": None
        }
        order_qs = Order.objects.filter(user=request.user, ordered=False)
        if order_qs.exists():
            context["order"] = order_qs[0]
        return render(request, 'order_summary.html', context)


class ItemDetailView(DetailView):
    model = Item
    template_name = 'product.html'


def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid


class CheckoutView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        try:
            # form
            order = Order.objects.get(user=request.user, ordered=False)
            form = CheckoutForm()
            context = {
                "form": form,
                "order": order,
                "coupon_form": CouponForm(),
                "DISPLAY_COUPON_FORM": True,
            }
            shipping_address_qs = Address.objects.filter(
                user=request.user,
                address_type='S',
                default=True,
            )
            billing_address_qs = Address.objects.filter(
                user=request.user,
                address_type='B',
                default=True,
            )
            if shipping_address_qs.exists():
                context.update(
                    {'default_shipping_address': shipping_address_qs[0]})
            if billing_address_qs.exists():
                context.update(
                    {'default_billing_address': billing_address_qs[0]})
            return render(request, 'checkout.html', context)
        except ObjectDoesNotExist:
            messages.warning(request, "You do not have an active order.")
            return redirect("/")

    def post(self, request, *args, **kwargs):
        form = CheckoutForm(request.POST or None)
        try:
            order = Order.objects.get(user=request.user, ordered=False)
            if form.is_valid():
                user = request.user
                use_default_shipping = form.cleaned_data.get(
                    'use_default_shipping')
                if use_default_shipping:
                    print("Using default shipping address")
                    address_qs = Address.objects.filter(
                        user=user,
                        address_type='S',
                        default=True
                    )
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        shipping_address.save()
                    else:
                        messages.warning(
                            'No default shipping address available.')
                        return redirect('core:checkout')
                else:
                    print("User is entering a new shipping address")
                    shipping_address1 = form.cleaned_data.get(
                        'shipping_address')
                    shipping_address2 = form.cleaned_data.get(
                        'shipping_address2')
                    shipping_country = form.cleaned_data.get(
                        'shipping_country')
                    shipping_city = form.cleaned_data.get('shipping_city')
                    shipping_post = form.cleaned_data.get('shipping_post')

                    if is_valid_form([shipping_address1, shipping_country, shipping_city, shipping_post]):
                        shipping_address = Address(
                            user=user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            city=shipping_city,
                            country=shipping_country,
                            post_code=shipping_post,
                            address_type='S',
                        )
                        shipping_address.save()

                        set_default_shipping = form.cleaned_data.get(
                            'set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save(update_fields=['default'])
                    else:
                        messages.warning(
                            request, "Please fill in the required shipping address fields.")
                        return redirect("core:checkout")

                use_default_billing = form.cleaned_data.get(
                    'use_default_billing')
                same_billing_address = form.cleaned_data.get(
                    'same_billing_address')
                # Check if billing address same as shipping address
                # If so create a billing address the same as shipping but with pk:None
                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.save()
                    billing_address.address_type = 'B'
                    billing_address.save()
                elif use_default_billing:
                    print("Using default billing address")
                    address_qs = Address.objects.filter(
                        user=user,
                        address_type='B',
                        default=True
                    )
                    if address_qs.exists():
                        billing_address = address_qs[0]
                        billing_address.save()
                    else:
                        messages.warning(
                            'No default billing address available.')
                        return redirect('core:checkout')
                else:
                    print("User is entering a new billing address")
                    billing_address1 = form.cleaned_data.get(
                        'billing_address')
                    billing_address2 = form.cleaned_data.get(
                        'billing_address2')
                    billing_country = form.cleaned_data.get(
                        'billing_country')
                    billing_city = form.cleaned_data.get('billing_city')
                    billing_post = form.cleaned_data.get('billing_post')
                    print(
                        f'Billing Form: {[billing_address1, billing_address2, billing_country, billing_city, billing_post]}')
                    if is_valid_form([billing_address1, billing_country, billing_city, billing_post]):
                        billing_address = Address(
                            user=user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            city=billing_city,
                            country=billing_country,
                            post_code=billing_post,
                            address_type='B',
                        )
                        billing_address.save()

                        set_default_billing = form.cleaned_data.get(
                            'set_default_billing')
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save(update_fields=['default'])
                    else:
                        messages.warning(
                            request, "Please fill in the required billing address fields.")
                        return redirect("core:checkout")

                order.shipping_address = shipping_address
                order.billing_address = billing_address
                order.save(update_fields=[
                           'shipping_address', 'billing_address'])

                # Payment options
                payment_option = form.cleaned_data.get('payment_option')
                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option="paypal")
                else:
                    messages.warning("Invalid payment option")
                    return redirect('core:checkout')
            messages.warning(self.request, "Failed checkout")
            return redirect('core:checkout')
        except ObjectDoesNotExist:
            messages.warning(request, "You do not have an active order")
            return redirect("/")


class PaymentView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if self.kwargs['payment_option'] == 'stripe':
            try:
                order = Order.objects.get(user=request.user, ordered=False)
            except ObjectDoesNotExist:
                messages.error(request, "You do not have an active order")
                return redirect('/')
            if order.billing_address:
                context = {
                    'order': order,
                    'coupon_form': CouponForm(),
                    "DISPLAY_COUPON_FORM": False,
                }
                userprofile = UserProfile(user=request.user)
                if userprofile.one_click_purchasing:
                    # fetch the users card list
                    cards = stripe.Customer.list_sources(
                        userprofile.stripe_customer_id,
                        limit=3,
                        object='card'
                    )
                    card_list = cards['data']
                    if len(card_list) > 0:
                        # update the context with the default card
                        context.update({
                            'card': card_list[0]
                        })
                return render(request, 'payment.html', context)
            else:
                messages.warning(
                    request, "You have not added a billing address")
                return redirect("core:checkout")
        else:
            messages.warning(request, "Invalid payment method")
            return redirect('core:checkout')

    def post(self, request, *args, **kwargs):
        if self.kwargs['payment_option'] == 'stripe':
            order = Order.objects.get(user=request.user, ordered=False)
            form = PaymentForm(request.POST)
            userprofile = UserProfile.objects.get(user=request.user)
            if form.is_valid():
                token = form.cleaned_data.get('stripeToken')
                save = form.cleaned_data.get('save')
                use_default = form.cleaned_data.get('use_default')

            if save:
                # allow to fetch cards
                if not userprofile.stripe_customer_id:
                    customer = stripe.Customer.create(
                        email=request.user.email,
                        source=token
                    )
                    userprofile.stripe_customer_id = customer['id']
                    userprofile.one_click_purchasing = True
                    userprofile.save()
                else:
                    stripe.Customer.create_source(
                        userprofile.stripe_customer_id,
                        source=token
                    )

            amount = order.get_total()
            description = f"Charge for {request.user.username} on order ID {order.id}"
            try:
                # print(
                #    f"amount: {amount}, source: {token}, description: {description}")
                # `source` is obtained with Stripe.js; see https://stripe.com/docs/payments/accept-a-payment-charges#web-create-token
                if use_default:
                    charge = stripe.Charge.create(
                        amount=amount,
                        currency='bdt',
                        customer=userprofile.stripe_customer_id,
                        description=description
                    )
                else:
                    charge = stripe.Charge.create(
                        amount=amount,
                        currency="bdt",
                        source=token,
                        description=description
                    )

                # create payment
                payment = Payment()
                payment.stripe_charge_id = charge['id']
                payment.user = request.user
                payment.amount = amount
                payment.save()

                # assign payment to order
                order.payment = payment
                order.ref_code = create_ref_code()
                order_items = order.items.all()
                order_items.update(ordered=True)
                for order_item in order_items:
                    order_item.save()

                order.ordered = True
                order.save()

                messages.success(request, "Your order was successful")

            # Error handling
            except stripe.error.CardError as e:
                # Since it's a decline, stripe.error.CardError will be caught
                # print('Status is: %s' % e.http_status)
                # print('Type is: %s' % e.error.type)
                # print('Code is: %s' % e.error.code)
                # # param is '' in this case
                # print('Param is: %s' % e.error.param)
                # print('Message is: %s' % e.error.message)
                messages.warning(request, f"{e.error.message}")

            except stripe.error.RateLimitError as e:
                # Too many requests made to the API too quickly
                messages.warning(request, "Rate limit error")

            except stripe.error.InvalidRequestError as e:
                # Invalid parameters were supplied to Stripe's API
                messages.warning(request, "Invalid parameters")
            except stripe.error.AuthenticationError as e:
                # Authentication with Stripe's API failed
                # (maybe you changed API keys recently)
                messages.warning(request, "Not authenticated")

            except stripe.error.APIConnectionError as e:
                # Network communication with Stripe failed
                messages.warning(request, "Network error")

            except stripe.error.StripeError as e:
                # Display a very generic error to the user, and maybe send
                # yourself an email
                messages.warning(
                    request, "Something went wrong. You were not charged. Please try again.")

            except Exception as e:
                # Something else happened, completely unrelated to Stripe
                # TODO: send an email to ourselves because it is on our end
                messages.warning(
                    request, "A serious error occured. Technical team has been automatically notified.")
            finally:
                return redirect('/')


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    # check if an unordered Order exists for user
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This item quantity was updated.")
            return redirect("core:product", slug=slug)
        else:
            messages.info(request, "This item was added to your cart.")
            order.items.add(order_item)
            order_item.quantity = 1
            order_item.save()
            return redirect("core:product", slug=slug)
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "This item was added to your cart.")
        return redirect("core:product", slug=slug)


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    # check if an unordered Order exists for user
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item, _ = OrderItem.objects.get_or_create(
                item=item,
                user=request.user,
                ordered=False
            )
            order.items.remove(order_item)
            messages.info(request, "This item was removed from your cart.")
            return redirect("core:product", slug=slug)
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("core:product", slug=slug)
    else:
        # add a message saying the user doesn't have an order
        messages.info(request, "You do not have an active order.")
        return redirect("core:product", slug=slug)


@login_required
def reduce_item_quantity_in_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    # check if an unordered order exists for user
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item, _ = OrderItem.objects.get_or_create(
                item=item,
                user=request.user,
                ordered=False
            )
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
                messages.info(request, "This item quantity was updated.")
                return redirect("core:order-summary")
            else:
                return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("core:product", slug=slug)
    else:
        # add a message saying the user doesn't have an order
        messages.info(request, "You do not have an active order.")
        return redirect("core:product", slug=slug)


@login_required
def add_item_quantity_in_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    # check if an unordered order exists for user
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item, _ = OrderItem.objects.get_or_create(
                item=item,
                user=request.user,
                ordered=False
            )
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This item quantity was updated.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("core:product", slug=slug)
    else:
        # add a message saying the user doesn't have an order
        messages.info(request, "You do not have an active order.")
        return redirect("core:product", slug=slug)


@login_required
def remove_item_in_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    # check if an unordered Order exists for user
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item, _ = OrderItem.objects.get_or_create(
                item=item,
                user=request.user,
                ordered=False
            )
            order.items.remove(order_item)
            messages.info(request, "This item was removed from your cart.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("core:product", slug=slug)
    else:
        # add a message saying the user doesn't have an order
        messages.info(request, "You do not have an active order.")
        return redirect("core:product", slug=slug)


@login_required
def add_coupon(request, slug):
    prev_path = slug
    if request.method == "POST":
        form = CouponForm(request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(user=request.user, ordered=False)
                coupon = get_coupon(request, code, prev_path)
                if coupon == None:
                    raise ValueError
                order.coupon = coupon
                order.save()
                messages.success(request, "Successfully added coupon")
                return redirect(f'core:{helpers.replace_dash_with_slash(prev_path)}')
            except ObjectDoesNotExist:
                messages.warning(request, "You do not have an active order.")
                return redirect("/")
            except ValueError:
                messages.warning(request, "This coupon does not exist.")
                return redirect(f'core:{helpers.replace_dash_with_slash(prev_path)}')
    else:
        # TODO: raise error
        return None


@login_required
def get_coupon(request, code, prev_path):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        return


class RequestRefundView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(request, 'request_refund.html', context)

    def post(self, request, *args, **kwargs):
        form = RefundForm(request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            # edit the order
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                # store the refund
                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.info(request, "Your request has been received.")
                return redirect("core:request-refund")
            except ObjectDoesNotExist:
                messages.warning(request, "This order does not exist.")
                return redirect("core:request-refund")
