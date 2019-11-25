from django.contrib import messages
from django.views.generic import ListView, DetailView, View
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.conf import settings
import stripe

from .models import Item, OrderItem, Order, BillingAddress, Payment, Coupon
from .forms import CheckoutForm, CouponForm
from django.core.exceptions import ObjectDoesNotExist
from . import helpers

stripe.api_key = settings.STRIPE_SECRET_KEY


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


class CheckoutView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # form
        form = CheckoutForm()
        context = {
            "form": form,
            "order": None,
            "coupon_form": CouponForm(),
            "DISPLAY_COUPON_FORM": True,
        }
        order_qs = Order.objects.filter(user=request.user, ordered=False)
        if order_qs.exists():
            context["order"] = order_qs[0]
        return render(request, 'checkout.html', context)

    def post(self, request, *args, **kwargs):
        form = CheckoutForm(request.POST or None)
        try:
            order = Order.objects.get(user=request.user, ordered=False)
            if form.is_valid():
                user = request.user
                street_address = form.cleaned_data.get('street_address')
                apartment_address = form.cleaned_data.get('apartment_address')
                city = form.cleaned_data.get('city')
                country = form.cleaned_data.get('country')
                post_code = form.cleaned_data.get('post_code')
                # TODO: add functionality for these fields
                # same_billing_address = form.cleaned_data.get('same_billing_address')
                # save_info = form.cleaned_data.get('save_info')
                payment_option = form.cleaned_data.get('payment_option')

                billing_address = BillingAddress(
                    user=user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    city=city,
                    country=country,
                    post_code=post_code
                )
                billing_address.save()
                order.billing_address = billing_address
                order.save(update_fields=['billing_address'])
                # Payment options
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
                if order.billing_address:
                    context = {
                        'order': order,
                        'coupon_form': CouponForm(),
                        "DISPLAY_COUPON_FORM": False,
                    }
                    return render(request, 'payment.html', context)
                else:
                    messages.warning(
                        request, "You have not added a billing address")
                    return redirect("core:checkout")
            except ObjectDoesNotExist:
                message.error(request, "You do not have an active order")
                return redirect('/')
        else:
            messages.warning(request, "Invalid payment method")
            return redirect('core:checkout')

    def post(self, request, *args, **kwargs):
        if self.kwargs['payment_option'] == 'stripe':
            order = Order.objects.get(user=request.user, ordered=False)
            token = self.request.POST.get('stripeToken')
            amount = order.get_total()
            description = f"Charge for {request.user.username} on order ID {order.id}"
            try:
                print(
                    f"amount: {amount}, source: {token}, description: {description}")
                # `source` is obtained with Stripe.js; see https://stripe.com/docs/payments/accept-a-payment-charges#web-create-token
                charge = stripe.Charge.create(
                    amount=amount,
                    currency="bdt",
                    source=token,
                    description=description,
                )
                order.ordered = True

                # create payment
                payment = Payment()
                payment.stripe_charge_id = charge['id']
                payment.user = request.user
                payment.amount = amount
                payment.save()

                # assign payment to order
                order.payment = payment
                order_items = order.items.all()
                order_items.update(ordered=True)
                for order_item in order_items:
                    order_item.save()
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
                return redirect(helpers.replace_dash_with_slash(prev_path))
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
