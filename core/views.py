from django.contrib import messages
from django.views.generic import ListView, DetailView, View
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.conf import settings
import stripe

from .models import Item, OrderItem, Order, BillingAddress, Payment
from .forms import CheckoutForm
from django.core.exceptions import ObjectDoesNotExist

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

                billing_address = BillingAddress()
                billing_address.user = request.user
                billing_address.street_address = street_address
                billing_address.apartment_address = apartment_address
                billing_address.city = city
                billing_address.country = country
                billing_address.post_code = post_code

                billing_address.save()
                order.billing_adress = billing_address
                # Payment options
                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option="paypal")
                else:
                    messages.error("Invalid payment option")
                    return redirect('core:checkout')
            messages.warning(self.request, "Failed checkout")
            return redirect('core:checkout')
        except ObjectDoesNotExist:
            messages.error(request, "You do not have an active order")
            return redirect("/")


class PaymentView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if self.kwargs['payment_option'] == 'stripe':
            try:
                order = Order.objects.get(user=request.user, ordered=False)
                context = {
                    'order': order
                }
                return render(request, 'payment.html', context)
            except ObjectDoesNotExist:
                message.error(request, "You do not have an active order")
                return redirect('/')
        else:
            messages.error(request, "Invalid payment method")
            return redirect('core:checkout')

    def post(self, request, *args, **kwargs):
        if self.kwargs['payment_option'] == 'stripe':
            order = Order.objects.get(user=request.user, ordered=False)
            token = self.request.POST.get('stripeToken')
            amount = order.get_total()
            try:
                # `source` is obtained with Stripe.js; see https://stripe.com/docs/payments/accept-a-payment-charges#web-create-token
                charge = stripe.Charge.create(
                    amount=amount,
                    currency="bdt",
                    source=token,
                    description=f"Charge for {request.user.username} on order ID {order.id}",
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
                for order_item in order.items.all():
                    order_item.ordered = True
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
                messages.error(request, f"{e.error.message}")

            except stripe.error.RateLimitError as e:
                # Too many requests made to the API too quickly
                messages.error(request, "Rate limit error")

            except stripe.error.InvalidRequestError as e:
                # Invalid parameters were supplied to Stripe's API
                messages.error(request, "Invalid parameters")
            except stripe.error.AuthenticationError as e:
                # Authentication with Stripe's API failed
                # (maybe you changed API keys recently)
                messages.error(request, "Not authenticated")

            except stripe.error.APIConnectionError as e:
                # Network communication with Stripe failed
                messages.error(request, "Network error")

            except stripe.error.StripeError as e:
                # Display a very generic error to the user, and maybe send
                # yourself an email
                messages.error(
                    request, "Something went wrong. You were not charged. Please try again.")

            except Exception as e:
                # Something else happened, completely unrelated to Stripe
                # TODO: send an email to ourselves because it is on our end
                messages.error(
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
