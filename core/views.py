from django.contrib import messages
from django.views.generic import ListView, DetailView, View
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required

from .models import Item, OrderItem, Order, BillingAddress
from .forms import CheckoutForm
from django.core.exceptions import ObjectDoesNotExist


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
                street_address = form.cleaned_data.get['street_address']
                apartment_address = form.cleaned_data.get['apartment_address']
                city = form.cleaned_data.get['city']
                country = form.cleaned_data.get['countries']
                post_code = form.cleaned_data.get['post_code']
                # TODO: add functionality for these fields
                # same_billing_address = form.cleaned_data.get['same_billing_address']
                # save_info = form.cleaned_data.get['save_info']
                payment_option = form.cleaned_data.get['payment_option']

                billing_address = BillingAddress(
                    user=request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    city=city,
                    post_code=post_code
                )
                billing_address.save()
                order.billing_adress = billing_address
                order.save()
                # TODO: add redirect to the selected payment option
                return redirect('core:checkout')
            messages.warning(self.request, "Failed checkout")
            return redirect('core:checkout')
        except ObjectDoesNotExist:
            messages.error(request, "You do not have an active order")
            return redirect("/")


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
