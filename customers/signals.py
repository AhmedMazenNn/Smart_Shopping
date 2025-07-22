# customers/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from sales.models import Order
from .models import Rating

@receiver(post_save, sender=Order)
def create_rating_on_order_created(sender, instance, created, **kwargs):
    """
    Create a Rating when a new Order is created (if one doesn't exist already).
    """
    if created and instance.customer:
        if not Rating.objects.filter(order=instance).exists():
            Rating.objects.create(order=instance, customer=instance.customer)
