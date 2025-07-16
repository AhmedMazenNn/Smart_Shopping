# customers/models.py

from decimal import Decimal
from django.db import models
from django.conf import settings
from django.db.models import Sum, F, Q, UniqueConstraint
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

# External app imports
from products.models import Product
from stores.models import Branch
from users.models import Customer  # Using the Customer model from users.models
from sales.models import Order


class CustomerCart(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        null=True, blank=True, related_name='carts',
        verbose_name=_("Customer Profile")
    )
    session_key = models.CharField(
        max_length=255, blank=True, null=True,
        unique=True, verbose_name=_("Session Key")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Last Updated At"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='customer_carts',
        verbose_name=_("Associated Branch")
    )

    class Meta:
        verbose_name = _("Customer Cart")
        verbose_name_plural = _("Customer Carts")
        ordering = ['-created_at']
        constraints = [
            UniqueConstraint(
                fields=['customer', 'branch'],
                condition=Q(is_active=True, customer__isnull=False),
                name='unique_active_customer_cart_per_branch'
            ),
            UniqueConstraint(
                fields=['session_key', 'branch'],
                condition=Q(is_active=True, session_key__isnull=False),
                name='unique_active_guest_cart_per_branch'
            ),
        ]

    def __str__(self):
        if self.customer:
            username = self.customer.user_account.username if self.customer.user_account else f"Customer ID: {self.customer.pk}"
        elif self.session_key:
            username = f"Guest ({self.session_key})"
        else:
            username = _("Unknown User")

        branch_info = f" - {_('Branch')}: {self.branch.name}" if self.branch else ""
        return f"{_('Cart for')} {username}{branch_info} - ID: {self.id}"

    def get_total_price(self):
        total = self.items.aggregate(
            sum_items=Sum(F('quantity') * F('product__price'), output_field=models.DecimalField())
        )['sum_items']
        return total if total is not None else Decimal('0.00')


class CustomerCartItem(models.Model):
    cart = models.ForeignKey(
        CustomerCart, on_delete=models.CASCADE,
        related_name='items', verbose_name=_("Cart")
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name=_("Product"))
    quantity = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        verbose_name=_("Quantity")
    )
    added_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Added At"))

    class Meta:
        verbose_name = _("Customer Cart Item")
        verbose_name_plural = _("Customer Cart Items")
        unique_together = ('cart', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.name} {_('in Cart')} {self.cart.id}"


class Rating(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        related_name='given_ratings',
        verbose_name=_("Reviewing Customer Profile")
    )
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE,
        related_name='rating', null=True, blank=True,
        verbose_name=_("Related Order")
    )
    cashier_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True, verbose_name=_("Cashier Rating (1-5)")
    )
    branch_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True, verbose_name=_("Branch Rating (1-5)")
    )
    app_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True, verbose_name=_("App Rating (1-5)")
    )
    comments = models.TextField(blank=True, null=True, verbose_name=_("Additional Comments"))
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Submitted At"))

    class Meta:
        verbose_name = _("Rating")
        verbose_name_plural = _("Ratings")
        ordering = ['-submitted_at']

    def __str__(self):
        order_info = ""
        if self.order and self.order.invoice_number:
            order_info = f" ({_('Order')}: {self.order.invoice_number})"
        elif self.order:
            order_info = f" ({_('Order ID')}: {self.order.pk})"

        customer_username = (
            self.customer.user_account.username if self.customer and self.customer.user_account else _("Unknown Customer")
        )

        return f"{_('Rating by')} {customer_username}{order_info} - ID: {self.id}"
