from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum, F
from django.utils.translation import gettext_lazy as _
import logging

from .models import Order, OrderItem, TempOrderItem, Return, ReturnItem
from products.models import BranchProductInventory
from integrations.models import InventoryMovement
from customers.models import Rating

logger = logging.getLogger(__name__)


# === OrderItem signals ===
@receiver(post_save, sender=OrderItem)
def update_order_totals_on_item_save(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    order = instance.order
    order.calculate_totals()
    order.save(update_fields=[
        'total_amount',
        'total_amount_before_vat',
        'total_vat_amount',
        'fee_amount'
    ])


@receiver(post_delete, sender=OrderItem)
def update_order_totals_on_item_delete(sender, instance, **kwargs):
    order = instance.order
    order.refresh_from_db()
    order.calculate_totals()
    order.save(update_fields=[
        'total_amount',
        'total_amount_before_vat',
        'total_vat_amount',
        'fee_amount'
    ])


# === TempOrderItem signals ===
@receiver(post_save, sender=TempOrderItem)
def update_temp_order_totals_on_item_save(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    temp_order = instance.temp_order
    temp_order.calculate_totals()
    temp_order.save(update_fields=['total_amount'])


@receiver(post_delete, sender=TempOrderItem)
def update_temp_order_totals_on_item_delete(sender, instance, **kwargs):
    temp_order = instance.temp_order
    temp_order.refresh_from_db()
    temp_order.calculate_totals()
    temp_order.save(update_fields=['total_amount'])


# === ReturnItem signals ===
@receiver(post_save, sender=ReturnItem)
def update_return_totals_on_item_save(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    return_obj = instance.return_obj
    return_obj.calculate_total_returned_amount()
    return_obj.save(update_fields=['total_returned_amount'])


@receiver(post_delete, sender=ReturnItem)
def update_return_totals_on_item_delete(sender, instance, **kwargs):
    return_obj = instance.return_obj
    return_obj.refresh_from_db()
    return_obj.calculate_total_returned_amount()
    return_obj.save(update_fields=['total_returned_amount'])


# === Inventory movement on Order COMPLETED ===
@receiver(post_save, sender=Order)
def manage_inventory_and_movements_on_order_status_change(sender, instance, created, **kwargs):
    if kwargs.get('raw'):
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
        status_changed = (old_instance.status != instance.status)
    except sender.DoesNotExist:
        status_changed = True if created else False

    if created or (status_changed and instance.status == instance.OrderStatus.COMPLETED):
        if instance.status == instance.OrderStatus.COMPLETED:
            with transaction.atomic():
                for item in instance.items.all():
                    inventory = BranchProductInventory.objects.select_for_update().get(
                        product=item.product,
                        branch=instance.branch
                    )
                    old_quantity = inventory.quantity
                    new_quantity = old_quantity - item.quantity

                    if new_quantity < 0:
                        raise ValidationError(_(
                            f"Insufficient stock for product {item.product.name} in branch {instance.branch.name}"
                        ))

                    inventory.quantity = new_quantity
                    inventory.save(update_fields=['quantity'])

                    InventoryMovement.objects.create(
                        inventory=inventory,
                        product=item.product,
                        branch=instance.branch,
                        movement_type='OUT',
                        quantity_change=-item.quantity,
                        old_quantity=old_quantity,
                        new_quantity=new_quantity,
                        reason=f"Sale (Order {instance.order_id})",
                        moved_by=instance.performed_by
                    )


# === Inventory movement on ReturnItem created ===
@receiver(post_save, sender=ReturnItem)
def manage_inventory_and_movements_on_return_item_save(sender, instance, created, **kwargs):
    if kwargs.get('raw'):
        return

    return_obj = instance.return_obj
    product = instance.product
    quantity = instance.quantity_returned
    branch = return_obj.order.branch

    with transaction.atomic():
        inventory = BranchProductInventory.objects.select_for_update().get(
            product=product,
            branch=branch
        )
        old_quantity = inventory.quantity
        new_quantity = old_quantity + quantity

        inventory.quantity = new_quantity
        inventory.save(update_fields=['quantity'])

        InventoryMovement.objects.create(
            inventory=inventory,
            product=product,
            branch=branch,
            movement_type='IN',
            quantity_change=quantity,
            old_quantity=old_quantity,
            new_quantity=new_quantity,
            reason=f"Return (Return ID: {return_obj.return_id})",
            moved_by=return_obj.processed_by
        )


# === Inventory adjustment on ReturnItem deleted ===
@receiver(post_delete, sender=ReturnItem)
def manage_inventory_and_movements_on_return_item_delete(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return

    return_obj = instance.return_obj
    product = instance.product
    quantity = instance.quantity_returned
    branch = return_obj.order.branch

    with transaction.atomic():
        inventory = BranchProductInventory.objects.select_for_update().get(
            product=product,
            branch=branch
        )
        old_quantity = inventory.quantity
        new_quantity = old_quantity - quantity

        if new_quantity < 0:
            logger.warning(f"Negative stock after deleting ReturnItem for {product.name} in {branch.name}")
            new_quantity = 0

        inventory.quantity = new_quantity
        inventory.save(update_fields=['quantity'])

        InventoryMovement.objects.create(
            inventory=inventory,
            product=product,
            branch=branch,
            movement_type='ADJUSTMENT',
            quantity_change=-quantity,
            old_quantity=old_quantity,
            new_quantity=new_quantity,
            reason=f"ReturnItem deleted (Return ID: {return_obj.return_id})",
            moved_by=return_obj.processed_by
        )


# === Create Rating automatically on Order creation ===
@receiver(post_save, sender=Order)
def create_or_update_rating_for_order(sender, instance, created, **kwargs):
    if created:
        try:
            if not Rating.objects.filter(order=instance).exists():
                Rating.objects.create(
                    order=instance,
                    customer=instance.customer
                )
                logger.info(f"Rating created for Order: {instance.order_id or instance.id}")
            else:
                logger.info(f"Rating already exists for Order: {instance.order_id or instance.id}")
        except Exception as e:
            logger.error(f"Error creating Rating for Order {instance.order_id or instance.id}: {e}")
