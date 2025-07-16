import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _

from products.models import Product
from users.models import UserAccount , Customer
from stores.models import Branch
from .constants import OrderStatus , PaymentMethod ,RefundMethod , ZatcaSubmissionStatus
from .utils import calculate_order_totals, calculate_return_total


# === TEMP ORDER ===
class TempOrder(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Customer")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_temp_orders", verbose_name=_("Created By")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = _("Temp Order")
        verbose_name_plural = _("Temp Orders")
        ordering = ["-created_at"]

    def __str__(self):
        return f"TempOrder #{self.pk} - Total: {self.total_amount}"

    def calculate_totals(self):
        self.total_amount = sum(
            item.product.price_after_discount() * item.quantity for item in self.items.all()
        )


class TempOrderItem(models.Model):
    temp_order = models.ForeignKey(
        TempOrder, on_delete=models.CASCADE, related_name="items", verbose_name=_("Temp Order")
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = _("Temp Order Item")
        verbose_name_plural = _("Temp Order Items")

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


# === MAIN ORDER ===
class Order(models.Model):

    # order_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    status = models.CharField(max_length=30, choices=OrderStatus.choices, default=OrderStatus.PENDING_PAYMENT)
    performed_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount_before_vat = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        ordering = ['-created_at']

    def __str__(self):
        return f"{_('Order')} {self.order_id}"

    def calculate_totals(self):
        calculate_order_totals(self)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = _("Order Item")
        verbose_name_plural = _("Order Items")
        unique_together = ('order', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


# === PAYMENT ===
class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name=_("Payment Amount")
    )
    payment_date = models.DateTimeField(auto_now_add=True)

    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='received_payments'
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ['-payment_date']

    def __str__(self):
        return f"{_('Payment')} {self.amount} {_('for Order')} {self.order.order_id}"


# === RETURN ===
class Return(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='returns')
    return_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    return_date = models.DateTimeField(auto_now_add=True)
    total_returned_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    reason = models.TextField(blank=True, null=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='processed_returns'
    )
    refund_method = models.CharField(
    max_length=20, choices=RefundMethod.choices,
    default=RefundMethod.CASH, verbose_name=_("Refund Method")
    )

    class Meta:
        verbose_name = _("Return")
        verbose_name_plural = _("Returns")
        ordering = ['-return_date']

    def __str__(self):
        return f"{_('Return')} {self.return_id} {_('for Order')} {self.order.order_id}"

    def calculate_total_returned_amount(self):
        calculate_return_total(self)


class ReturnItem(models.Model):
    return_obj = models.ForeignKey(Return, on_delete=models.CASCADE, related_name='returned_items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_returned = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_at_return = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = _("Returned Item")
        verbose_name_plural = _("Returned Items")
        unique_together = ('return_obj', 'product')

    def __str__(self):
        return f"{self.quantity_returned} x {self.product.name} {_('returned in')} {self.return_obj.return_id}"

    def save(self, *args, **kwargs):
        if not self.price_at_return and self.product:
            self.price_at_return = self.product.price_after_discount()
        super().save(*args, **kwargs)
