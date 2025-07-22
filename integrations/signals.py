from django.db.models.signals import post_save
from django.dispatch import receiver
from sales.models import Order
from .models import ZatcaInvoice

@receiver(post_save, sender=Order)
def create_zatca_invoice_if_needed(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'zatca_details'):
        ZatcaInvoice.objects.create(order=instance)
