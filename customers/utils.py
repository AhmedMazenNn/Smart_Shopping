# customers/utils.py

from decimal import Decimal
from django.db.models import Sum, F, DecimalField
from .models import CustomerCart

def calculate_cart_total(cart: CustomerCart) -> Decimal:
    """
    Calculates the total amount of items in the customer's cart.
    """
    total = cart.items.aggregate(
        total=Sum(F('quantity') * F('product__price'), output_field=DecimalField())
    )['total']
    return total or Decimal('0.00')
