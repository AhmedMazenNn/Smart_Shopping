# stores/models.py

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from uuid import uuid4

from users.models import UserAccount
from .signals import *  # Connect post_save signals

# --- StoreType ---
class StoreType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _("Store Type")
        verbose_name_plural = _("Store Types")

    def __str__(self):
        return self.name

# --- StorePermissionProfile ---
class StorePermissionProfile(models.Model):
    name = models.CharField(_("Profile Name"), max_length=100, unique=True)
    description = models.TextField(_("Description"), blank=True)

    can_manage_products = models.BooleanField(_("Manage Products"), default=False)
    can_manage_branches = models.BooleanField(_("Manage Branches"), default=False)
    can_manage_staff_accounts = models.BooleanField(_("Manage Staff Accounts"), default=False)
    can_view_reports = models.BooleanField(_("View Reports"), default=False)
    can_manage_discounts_offers = models.BooleanField(_("Manage Discounts & Offers"), default=False)

    class Meta:
        verbose_name = _("Store Permission Profile")
        verbose_name_plural = _("Store Permission Profiles")
        ordering = ['name']

    def __str__(self):
        return self.name

# --- BranchPermissionProfile ---
class BranchPermissionProfile(models.Model):
    name = models.CharField(_("Profile Name"), max_length=100, unique=True)
    description = models.TextField(_("Description"), blank=True)

    can_manage_branch_profile = models.BooleanField(_("Manage Branch Profile"), default=False)
    can_manage_local_staff = models.BooleanField(_("Manage Local Staff"), default=False)
    can_manage_local_products = models.BooleanField(_("Manage Local Products"), default=False)
    can_manage_local_offers = models.BooleanField(_("Manage Local Offers"), default=False)
    can_view_local_reports = models.BooleanField(_("View Local Reports"), default=False)
    can_review_ratings = models.BooleanField(_("Review Ratings"), default=False)

    can_manage_cart = models.BooleanField(_("Manage Cart (Cashier)"), default=False)
    can_apply_discounts = models.BooleanField(_("Apply Discounts (Cashier)"), default=False)
    can_finalize_invoice = models.BooleanField(_("Finalize Invoice (Cashier)"), default=False)
    can_assist_customer_rating = models.BooleanField(_("Assist Customer Rating"), default=False)

    can_create_promotions = models.BooleanField(_("Create Promotions"), default=False)
    can_track_offer_performance = models.BooleanField(_("Track Offer Performance"), default=False)

    can_manage_daily_statuses = models.BooleanField(_("Manage Daily Statuses"), default=False)
    can_set_display_priority = models.BooleanField(_("Set Display Priority"), default=False)

    class Meta:
        verbose_name = _("Branch Permission Profile")
        verbose_name_plural = _("Branch Permission Profiles")
        ordering = ['name']

    def __str__(self):
        return self.name

# --- Store ---
class Store(models.Model):
    name = models.CharField(_("Store Name"), max_length=255, unique=True)
    address = models.TextField(_("Address"))
    phone_number = models.CharField(_("Phone Number"), max_length=20, blank=True, null=True)
    email = models.EmailField(_("Email"), blank=True, null=True)

    tax_id = models.CharField(_("Tax ID"), max_length=50, unique=True, blank=True, null=True)

    store_type = models.ForeignKey(StoreType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Store Type"))
    user = models.OneToOneField(UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='store_account', verbose_name=_("Primary Store Account"))
    created_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='stores_created', verbose_name=_("Created By"))
    permission_profile = models.ForeignKey(StorePermissionProfile, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Permission Profile"))

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    total_yearly_operations = models.DecimalField(_("Total Yearly Operations ($)"), max_digits=15, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    last_yearly_update = models.DateField(_("Last Yearly Update"), null=True, blank=True)

    class Meta:
        verbose_name = _("Store")
        verbose_name_plural = _("Stores")
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.login_email:
            # Make sure no other store uses the same login_email
            if Store.objects.filter(login_email=self.login_email).exclude(pk=self.pk).exists():
                raise ValidationError({'login_email': _("A store with this primary login email already exists.")})
            if UserAccount.objects.filter(email=self.login_email).exclude(pk=self.user_id if self.user else None).exists():
                raise ValidationError({'login_email': _("A user account with this email already exists.")})

# --- Branch ---
class Branch(models.Model):
    branch_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='branches', verbose_name=_("Store"))
    name = models.CharField(_("Branch Name"), max_length=255)
    address = models.TextField(_("Address"))
    phone_number = models.CharField(_("Phone Number"), max_length=20, blank=True, null=True)
    email = models.EmailField(_("Email"), blank=True, null=True)
    branch_tax_id = models.CharField(_("Branch Tax ID"), max_length=50, blank=True, null=True)

    manager_employee = models.OneToOneField(UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_branch', verbose_name=_("Branch Manager Account"))
    created_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='branches_created', verbose_name=_("Created By"))
    permission_profile = models.ForeignKey(BranchPermissionProfile, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Permission Profile"))

    fee_percentage = models.DecimalField(_("Fee Percentage (%)"), max_digits=5, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))])

    latitude = models.DecimalField(_("Latitude"), max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(_("Longitude"), max_digits=9, decimal_places=6, null=True, blank=True)

    daily_operations = models.DecimalField(_("Daily Operations ($)"), max_digits=15, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    monthly_operations = models.DecimalField(_("Monthly Operations ($)"), max_digits=15, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    total_yearly_operations = models.DecimalField(_("Total Yearly Operations ($)"), max_digits=15, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])

    last_daily_update = models.DateField(_("Last Daily Update"), null=True, blank=True)
    last_monthly_update = models.DateField(_("Last Monthly Update"), null=True, blank=True)
    last_yearly_update = models.DateField(_("Last Yearly Update"), null=True, blank=True)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Branch")
        verbose_name_plural = _("Branches")
        unique_together = ('store', 'name')
        ordering = ['store__name', 'name']

    def __str__(self):
        return f"{self.name} ({self.branch_id_number})"

    def clean(self):
        super().clean()
        if Branch.objects.filter(store=self.store, name=self.name).exclude(pk=self.pk).exists():
            raise ValidationError(_("A branch with this name already exists for this store."))
