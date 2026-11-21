from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import F

from products.models import Product
from inventory.models import StockTransaction
from .models import Order, OrderItem


@login_required
def create_order(request):

    products = Product.objects.all()

    if request.method == 'POST':

        selected_products = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')

        if not selected_products:
            messages.error(request, "Please select products")
            return redirect('create_order')

        try:
            with transaction.atomic():

                order = Order.objects.create(
                    customer=request.user
                )

                total = 0
                order_items = []

                for product_id, qty in zip(selected_products, quantities):

                    product = Product.objects.select_for_update().get(
                        id=product_id
                    )

                    quantity = int(qty)

                    if quantity <= 0:
                        raise ValueError("Quantity must be greater than zero")

                    if product.quantity < quantity:
                        raise ValueError(
                            f"Only {product.quantity} units available for {product.name}"
                        )

                    subtotal = product.price * quantity

                    Product.objects.filter(
                        id=product.id,
                        quantity__gte=quantity
                    ).update(quantity=F('quantity') - quantity)

                    order_items.append(
                        OrderItem(
                            order=order,
                            product=product,
                            quantity=quantity,
                            price=product.price
                        )
                    )

                    StockTransaction.objects.create(
                        product=product,
                        product_name=product.name,
                        transaction_type='OUT',
                        quantity=quantity
                    )

                    total += subtotal

                OrderItem.objects.bulk_create(order_items)

                order.total_price = total
                order.save()

            messages.success(request, "Order placed successfully!")

            return redirect('order_list')

        except (ValueError, Product.DoesNotExist) as e:

            messages.error(request, str(e))
            return redirect('create_order')

    return render(request, 'order.html', {
        'products': products
    })


@login_required
def order_list(request):

    if request.user.is_staff:
        orders = Order.objects.all()
    else:
        orders = Order.objects.filter(customer=request.user)

    return render(request, 'order_list.html', {
        'orders': orders
    })


# @login_required
# def cancel_order(request, id):

#     if request.method == 'POST':

#         try:
#             with transaction.atomic():

#                 if request.user.is_staff:
#                     order = get_object_or_404(
#                         Order.objects.select_for_update(),
#                         id=id
#                     )
#                 else:
#                     order = get_object_or_404(
#                         Order.objects.select_for_update(),
#                         id=id,
#                         customer=request.user
#                     )

#                 if order.status != 'Pending':
#                     messages.error(request, "Order already cancelled or cannot be cancelled.")
#                     return redirect('order_list')

#                 items = list(order.items.all())

#                 for item in items:

#                     Product.objects.filter(
#                         id=item.product_id
#                     ).update(
#                         quantity=F('quantity') + item.quantity
#                     )

#                     StockTransaction.objects.create(
#                         product=item.product,
#                         product_name=item.product.name,
#                         transaction_type='IN',
#                         quantity=item.quantity
#                     )

#                 order.status = 'Cancelled'
#                 order.save()

#             messages.success(request, "Order cancelled successfully!")

#         except Exception as e:
#             messages.error(request, str(e))

#     return redirect('order_list')
@login_required
def cancel_order(request, id):

    if request.user.is_staff:
        order = get_object_or_404(Order, id=id)
    else:
        order = get_object_or_404(
            Order,
            id=id,
            customer=request.user
        )

    if request.method == 'POST':

        try:
            with transaction.atomic():

                order = Order.objects.select_for_update().get(id=id)

                if not request.user.is_staff and order.customer != request.user:
                    messages.error(request, "Unauthorized access")
                    return redirect('order_list')

                if order.status != 'Pending':
                    messages.error(request, "Order already cancelled")
                    return redirect('order_list')

                for item in order.items.all():

                    Product.objects.filter(
                        id=item.product_id
                    ).update(
                        quantity=F('quantity') + item.quantity
                    )

                    StockTransaction.objects.create(
                        product=item.product,
                        product_name=item.product.name,
                        transaction_type='IN',
                        quantity=item.quantity
                    )

                order.status = 'Cancelled'
                order.save()

            messages.success(request, "Order cancelled successfully")

        except Exception as e:
            messages.error(request, str(e))

        return redirect('order_list')

    return render(request, 'cancel_order.html', {
        'order': order
    })