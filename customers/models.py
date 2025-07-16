# C:\Users\DELL\SER SQL MY APP\customers\models.py
from django.db import models
from django.conf import settings 
from decimal import Decimal
from django.db.models import Sum, F, Q, UniqueConstraint 
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

# IMPORTS FROM OTHER APPS
from products.models import Product, BranchProductInventory 
from stores.models import Branch 
from users.models import Customer # THIS IS THE CRUCIAL CHANGE: IMPORT CUSTOMER FROM USERS APP

# === CustomerCart Model (Customer Shopping Cart - Pre-Cashier Stage) ===
# This model is for customers who use their own app and add products to their cart.
# The cashier will use a "temporary order" system instead of this.
class CustomerCart(models.Model):
    # Link the cart to the Customer profile (from users.models) instead of UserAccount directly
    # Can be null for guest customers who don't have a registered account
    customer = models.ForeignKey(
        Customer, # Now references Customer from users.models
        on_delete=models.CASCADE,
        null=True, blank=True, # Can be null for guests
        related_name='carts',
        verbose_name=_("Customer Profile")
    )
    session_key = models.CharField(max_length=255, blank=True, null=True, unique=True, verbose_name=_("Session Key"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Last Updated At"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='customer_carts',
        verbose_name=_("Associated Branch")
    )

    class Meta:
        verbose_name = _("Customer Cart")
        verbose_name_plural = _("Customer Carts")
        ordering = ['-created_at']
        
        # Unique constraint to ensure one active cart per customer (or guest) per specific branch
        # For registered customers: one active cart per branch (or one cart without a branch)
        # For guest customers (session_key): one active cart per session_key per specific branch
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
        # Note: If both customer and session_key are null, this is not covered here, but this depends on cart creation logic.
        # Usually one of them must exist.

    def __str__(self):
        customer_info = ""
        if self.customer:
            # Access the username via the user_account linked to the Customer profile
            customer_info = self.customer.user_account.username if self.customer.user_account else f"Customer ID: {self.customer.pk}"
        elif self.session_key:
            customer_info = f"Guest ({self.session_key})"
        else:
            customer_info = _("Unknown User")

        branch_info = f" - {_('Branch')}: {self.branch.name}" if self.branch else ""
        return f"{_('Cart for')} {customer_info}{branch_info} - ID: {self.id}"

    def get_total_price(self):
        # This function should consider price_after_discount() and branch inventory quantity
        # But for calculating the total price of items in the cart, we use the base product price
        # If you want to use price_after_discount, there must be a way to access it from Product or CartItem
        total = self.items.aggregate(
            sum_items=Sum(F('quantity') * F('product__price'), output_field=models.DecimalField())
        )['sum_items']
        return total if total is not None else Decimal('0.00')


# === CustomerCartItem Model (Item in Customer Shopping Cart) ===
class CustomerCartItem(models.Model):
    cart = models.ForeignKey(CustomerCart, on_delete=models.CASCADE, related_name='items', verbose_name=_("Cart"))
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name=_("Product"))
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name=_("Quantity"))
    added_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Added At"))

    class Meta:
        verbose_name = _("Customer Cart Item")
        verbose_name_plural = _("Customer Cart Items")
        unique_together = ('cart', 'product') # Ensure each product is unique in each cart

    def __str__(self):
        return f"{self.quantity} x {self.product.name} {_('in Cart')} {self.cart.id}"


# === Rating Model (Customer Rating) ===
class Rating(models.Model):
    # Link the rating to the Customer profile (from users.models) instead of UserAccount directly
    customer = models.ForeignKey(
        Customer, # Now references Customer from users.models
        on_delete=models.CASCADE,
        related_name='given_ratings',
        verbose_name=_("Reviewing Customer Profile")
    )
    
    order = models.OneToOneField(
        'sales.Order', 
        on_delete=models.CASCADE,
        related_name='rating',
        null=True, blank=True, # Can be null if the rating is not linked to a direct order (e.g., general app rating)
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
        # OneToOneField on 'order' ensures each order can have only one rating.
        # If you want to allow general ratings not tied to an order, this is allowed due to null=True, blank=True in 'order'.

    def __str__(self):
        order_info = ""
        if self.order and self.order.invoice_number:
            order_info = f" ({_('Order')}: {self.order.invoice_number})"
        elif self.order:
            order_info = f" ({_('Order ID')}: {self.order.pk})"
            
        # Access the username via the linked customer profile's user account
        customer_username = self.customer.user_account.username if self.customer and self.customer.user_account else _("Unknown Customer")
            
        return f"{_('Rating by')} {customer_username}{order_info} - ID: {self.id}"
