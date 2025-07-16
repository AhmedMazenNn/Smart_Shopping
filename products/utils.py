# products/utils.py

from decimal import Decimal
from django.utils import timezone

def is_offer_active(start_date, end_date):
    if start_date and end_date:
        today = timezone.localdate()
        return start_date <= today <= end_date
    return False

def calculate_discounted_price(price, discount_percentage):
    if discount_percentage is not None and discount_percentage > Decimal("0.00"):
        return price * (1 - discount_percentage / 100)
    return price

def calculate_vat_amount(price, vat_rate):
    return price * vat_rate
