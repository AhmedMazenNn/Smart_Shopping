# C:\Users\DELL\SER SQL MY APP\stores\models.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import UserAccount, Role
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
import secrets
import string
from django.utils.text import slugify
import uuid # <--- تأكد من استيراد مكتبة uuid هنا

# --- StoreType Model (MUST BE PRESENT) ---
class StoreType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _("Store Type")
        verbose_name_plural = _("Store Types")

    def __str__(self):
        return self.name

# --- Store Permission Profile Model ---
class StorePermissionProfile(models.Model):
    name = models.CharField(
        _("Profile Name"), max_length=100, unique=True,
        help_text=_("A unique name for this store permission profile.")
    )
    description = models.TextField(
        _("Description"), blank=True,
        help_text=_("A brief description of what this profile entails.")
    )

    can_manage_products = models.BooleanField(
        _("Manage Products"), default=False,
        help_text=_("Can manage products (add, edit, delete, set pricing) within the store.")
    )
    can_manage_branches = models.BooleanField(
        _("Manage Branches"), default=False,
        help_text=_("Can manage branches (add, edit, delete branches, assign branch managers).")
    )
    can_manage_staff_accounts = models.BooleanField(
        _("Manage Staff Accounts"), default=False,
        help_text=_("Can create, edit, and deactivate staff accounts for the store and its branches.")
    )
    can_view_reports = models.BooleanField(
        _("View Reports"), default=False,
        help_text=_("Can view various operational and sales reports for the store.")
    )
    can_manage_discounts_offers = models.BooleanField(
        _("Manage Discounts & Offers"), default=False,
        help_text=_("Can create, edit, and manage store-wide discounts and promotional offers.")
    )

    class Meta:
        verbose_name = _("Store Permission Profile")
        verbose_name_plural = _("Store Permission Profiles")
        ordering = ['name']

    def __str__(self):
        return self.name

# --- Branch Permission Profile Model ---
class BranchPermissionProfile(models.Model):
    name = models.CharField(
        _("Profile Name"), max_length=100, unique=True,
        help_text=_("A unique name for this branch permission profile.")
    )
    description = models.TextField(
        _("Description"), blank=True,
        help_text=_("A brief description of what this profile entails.")
    )

    can_manage_branch_profile = models.BooleanField(
        _("Manage Branch Profile"), default=False,
        help_text=_("Can edit the branch's general information (e.g., address, phone, email).")
    )
    can_manage_local_staff = models.BooleanField(
        _("Manage Local Staff"), default=False,
        help_text=_("Can manage staff accounts specific to this branch (e.g., cashiers, local employees).")
    )
    can_manage_local_products = models.BooleanField(
        _("Manage Local Products"), default=False,
        help_text=_("Can manage products available at this specific branch (e.g., stock levels, local pricing).")
    )
    can_manage_local_offers = models.BooleanField(
        _("Manage Local Offers"), default=False,
        help_text=_("Can create and manage promotional offers specific to this branch.")
    )
    can_view_local_reports = models.BooleanField(
        _("View Local Reports"), default=False,
        help_text=_("Can view operational and sales reports for this specific branch.")
    )
    can_review_ratings = models.BooleanField(
        _("Review Ratings"), default=False,
        help_text=_("Can review customer ratings and feedback for the branch.")
    )

    can_manage_cart = models.BooleanField(
        _("Manage Cart (Cashier)"), default=False,
        help_text=_("Can add/remove items from customer cart and calculate totals.")
    )
    can_apply_discounts = models.BooleanField(
        _("Apply Discounts (Cashier)"), default=False,
        help_text=_("Can apply available discounts to customer orders.")
    )
    can_finalize_invoice = models.BooleanField(
        _("Finalize Invoice (Cashier)"), default=False,
        help_text=_("Can finalize sales transactions and issue invoices.")
    )
    can_assist_customer_rating = models.BooleanField(
        _("Assist Customer Rating"), default=False,
        help_text=_("Can assist customers in submitting ratings after a transaction.")
    )

    can_create_promotions = models.BooleanField(
        _("Create Promotions"), default=False,
        help_text=_("Can create new promotional campaigns or offers.")
    )
    can_track_offer_performance = models.BooleanField(
        _("Track Offer Performance"), default=False,
        help_text=_("Can monitor the performance and effectiveness of promotions.")
    )

    can_manage_daily_statuses = models.BooleanField(
        _("Manage Daily Statuses"), default=False,
        help_text=_("Can update daily operational statuses (e.g., open/closed, special announcements).")
    )
    can_set_display_priority = models.BooleanField(
        _("Set Display Priority"), default=False,
        help_text=_("Can set the display priority for products or offers on digital displays or apps.")
    )

    class Meta:
        verbose_name = _("Branch Permission Profile")
        verbose_name_plural = _("Branch Permission Profiles")
        ordering = ['name']

    def __str__(self):
        return self.name

# --- Store Model ---
class Store(models.Model):
    name = models.CharField(_("Store Name"), max_length=255, unique=True)
    address = models.TextField(_("Address"))
    phone_number = models.CharField(_("Phone Number"), max_length=20, blank=True, null=True)
    email = models.EmailField(_("Email"), blank=True, null=True)
    login_email = models.EmailField(
        _("Primary Login Email"), unique=True,
        help_text=_("The email used for the main store account login.")
    )
    tax_id = models.CharField(_("Tax ID"), max_length=50, unique=True, blank=True, null=True)
    
    store_type = models.ForeignKey(
        StoreType, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Store Type"),
        help_text=_("Categorize the store type (e.g., Restaurant, Retail, Service).")
    )

    user = models.OneToOneField(
        UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='store_account',
        verbose_name=_("Primary Store Account"),
        help_text=_("The primary user account associated with this store.")
    )
    created_by = models.ForeignKey(
        UserAccount, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='stores_created',
        verbose_name=_("Created By")
    )
    permission_profile = models.ForeignKey(
        StorePermissionProfile, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Permission Profile"),
        help_text=_("Assign a permission profile to this store for operational access.")
    )

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    total_yearly_operations = models.DecimalField(
        _("Total Yearly Operations ($)"), max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text=_("Accumulated gross sales/operations for the current fiscal year.")
    )
    last_yearly_update = models.DateField(
        _("Last Yearly Update"), null=True, blank=True,
        help_text=_("The last date when yearly operations were reset or updated.")
    )

    class Meta:
        verbose_name = _("Store")
        verbose_name_plural = _("Stores")
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.login_email and Store.objects.filter(login_email=self.login_email).exclude(pk=self.pk).exists():
            raise ValidationError({'login_email': _("A store with this primary login email already exists.")})
        if self.login_email and UserAccount.objects.filter(email=self.login_email).exclude(pk=self.user_id if self.user else None).exists():
            raise ValidationError({'login_email': _("A user account with this email already exists.")})

@receiver(post_save, sender=Store)
def create_store_primary_user(sender, instance, created, **kwargs):
    if created and instance.login_email and not instance.user:
        try:
            with transaction.atomic():
                base_slug = slugify(instance.name)
                store_account_role = Role.objects.get(role_name='store_account')
                username_prefix = f"{store_account_role.role_name.upper().replace(' ', '_')}-"
                username_candidate = f"{username_prefix}{base_slug}"
                counter = 0
                while UserAccount.objects.filter(username__iexact=username_candidate).exists():
                    counter += 1
                    username_candidate = f"{username_prefix}{base_slug}-{counter}"

                alphabet = string.ascii_letters + string.digits
                store_account_raw_password = ''.join(secrets.choice(alphabet) for i in range(12))

                store_account_user = UserAccount.objects.create_user(
                    email=instance.login_email,
                    password=store_account_raw_password,
                    username=username_candidate,
                    role=store_account_role,
                    is_active=True,
                    store=instance, # This field is expected to be on UserAccount model for linking
                    first_name=instance.name,
                    last_name=_("Account")
                )
                instance.user = store_account_user
                instance.save(update_fields=['user'])
                print(f"\n--- STORE PRIMARY ACCOUNT CREATED for {instance.name} ---")
                print(f"  Username: {store_account_user.username}")
                print(f"  Email: {store_account_user.email}")
                print(f"  Temporary Password (for login): {store_account_raw_password}")
                print(_("  Please change this password immediately after first login for security."))
                print("---------------------------------------------------\n")

        except Role.DoesNotExist:
            raise ValidationError(_("The 'store_account' role does not exist. Please create it in the admin first."))
        except Exception as e:
            print(f"Error creating store primary user: {e}")
            if instance.pk:
                instance.delete()
            raise ValidationError(_(f"Failed to create primary account for store. Details: {e}"))

# --- Branch Model ---
class Branch(models.Model):
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name='branches',
        verbose_name=_("Store")
    )
    name = models.CharField(_("Branch Name"), max_length=255)
    address = models.TextField(_("Address"))
    phone_number = models.CharField(_("Phone Number"), max_length=20, blank=True, null=True)
    email = models.EmailField(_("Email"), blank=True, null=True)
    
    # ** تم تحديث هذا الحقل لإنشاء UUID تلقائيًا **
    branch_id_number = models.UUIDField(
        default=uuid.uuid4,  # يقوم بتوليد UUID جديد تلقائيًا
        unique=True,         # يضمن التفرد
        editable=False,      # (اختياري) يمنع التعديل من Admin بعد الإنشاء
        verbose_name=_("Branch ID Number"),
        help_text=_("معرف فريد يتم إنشاؤه تلقائيًا لهذا الفرع.")
    )

    branch_tax_id = models.CharField(
        _("Branch Tax ID"), max_length=50, blank=True, null=True,
        help_text=_("Optional: A tax ID specific to this branch if different from the main store.")
    )

    manager_employee = models.OneToOneField(
        UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_branch',
        verbose_name=_("Branch Manager Account"),
        help_text=_("The user account assigned as the manager of this branch.")
    )
    created_by = models.ForeignKey(
        UserAccount, on_delete=models.SET_NULL, null=True, related_name='branches_created',
        verbose_name=_("Created By")
    )
    permission_profile = models.ForeignKey(
        BranchPermissionProfile, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Permission Profile"),
        help_text=_("Assign a permission profile to this branch for operational access.")
    )

    fee_percentage = models.DecimalField(
        _("Fee Percentage (%)"), max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text=_("The percentage fee charged by this branch for certain operations.")
    )

    latitude = models.DecimalField(
        _("Latitude"), max_digits=9, decimal_places=6, null=True, blank=True,
        help_text=_("Geographical latitude of the branch.")
    )
    longitude = models.DecimalField(
        _("Longitude"), max_digits=9, decimal_places=6, null=True, blank=True,
        help_text=_("Geographical longitude of the branch.")
    )

    daily_operations = models.DecimalField(
        _("Daily Operations ($)"), max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    monthly_operations = models.DecimalField(
        _("Monthly Operations ($)"), max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_yearly_operations = models.DecimalField(
        _("Total Yearly Operations ($)"), max_digits=15, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
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
        # يفضل عرض المعرف جنبًا إلى جنب مع الاسم لسهولة التعرف
        return f"{self.name} ({self.branch_id_number})"

    # تم إزالة التحقق اليدوي من branch_id_number في clean() لأنه يتم توليده تلقائيًا وهو فريد
    def clean(self):
        super().clean()
        # لم نعد بحاجة لهذا التحقق حيث أن UUIDField مع unique=True يتعامل مع التفرد تلقائيًا
        # if self.branch_id_number and Branch.objects.filter(branch_id_number=self.branch_id_number).exclude(pk=self.pk).exists():
        #     raise ValidationError({'branch_id_number': _("A branch with this ID number already exists.")})

        if self.store and self.name and Branch.objects.filter(store=self.store, name=self.name).exclude(pk=self.pk).exists():
            raise ValidationError(_("A branch with this name already exists for this store."))

@receiver(post_save, sender=Branch)
def link_branch_manager_to_branch(sender, instance, created, **kwargs):
    if instance.manager_employee:
        if instance.manager_employee.branch != instance:
            instance.manager_employee.branch = instance
            instance.manager_employee.save(update_fields=['branch'])
        if instance.manager_employee.store != instance.store:
            instance.manager_employee.store = instance.store
            instance.manager_employee.save(update_fields=['store'])