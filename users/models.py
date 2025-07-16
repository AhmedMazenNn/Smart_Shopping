# C:\Users\DELL\SER SQL MY APP\users\models.py

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from django.utils.text import slugify
import secrets
import string
from django.utils import timezone
from enum import Enum

# استيراد Firebase Admin SDK هنا
# تأكد أن Firebase Admin SDK مهيأ في settings.py أو AppConfig
import firebase_admin
from firebase_admin import auth, exceptions as firebase_exceptions
import logging

logger = logging.getLogger(__name__)


# تعريف UserType كتعداد (Enum)
class UserType(Enum):
    APP_OWNER = 'app_owner'
    PROJECT_MANAGER = 'project_manager'
    APP_STAFF = 'app_staff'
    STORE_ACCOUNT = 'store_account'
    STORE_MANAGER = 'store_manager' # This is for human managers
    BRANCH_MANAGER = 'branch_manager'
    GENERAL_STAFF = 'general_staff'
    CASHIER = 'cashier'
    SHELF_ORGANIZER = 'shelf_organizer'
    CUSTOMER_SERVICE = 'customer_service'
    PLATFORM_CUSTOMER = 'platform_customer'

    @classmethod
    def choices(cls):
        return [(key.value, key.name.replace('_', ' ').title()) for key in cls]


# Helper function to generate a secure random password
def generate_temporary_password(length=12):
    """توليد كلمة مرور مؤقتة آمنة."""
    characters = string.ascii_letters + string.digits + string.punctuation
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(string.punctuation),
    ]
    password += [secrets.choice(characters) for _ in range(length - len(password))]
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)

## Role Model
class Role(models.Model):
    role_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role_name = models.CharField(_('Role Name'), max_length=50, unique=True)
    description = models.TextField(_('Description'), blank=True, null=True)

    is_staff_role = models.BooleanField(
        _('Is Staff Role'),
        default=False,
        help_text=_('Designates whether users with this role can log into the admin site.')
    )

    class Meta:
        verbose_name = _('Role')
        verbose_name_plural = _('Roles')

    def __str__(self):
        return self.role_name

## UserAccount Manager
class UserAccountManager(BaseUserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError(_('The Email Address field must be set.'))
        email = self.normalize_email(email)

        role = extra_fields.pop('role', None)
        if not role:
            try:
                role = Role.objects.get(role_name=UserType.PLATFORM_CUSTOMER.value)
            except Role.DoesNotExist:
                raise ValueError(_("A default 'platform_customer' role must exist in the database or a role must be provided."))

        username = extra_fields.get('username')
        if not username or username.strip() == '':
            base_slug = slugify(email.split('@')[0])
            prefix = f"{role.role_name.upper().replace(' ', '_')}-" if role else ''
            username_candidate = f"{prefix}{base_slug}"
            counter = 0
            while self.model.objects.filter(username__iexact=username_candidate).exists():
                counter += 1
                username_candidate = f"{prefix}{base_slug}-{counter}"
            extra_fields['username'] = username_candidate

        extra_fields['is_staff'] = role.is_staff_role

        user = self.model(email=email, role=role, **extra_fields)

        is_temp_password_generated = False
        temp_password = None

        if password is None or password == '':
            temp_password = generate_temporary_password()
            user.set_password(temp_password)
            user.is_temporary_password = True
            user._temporary_password = temp_password # Store for retrieval in admin/forms
            is_temp_password_generated = True
        else:
            user.set_password(password)
            user.is_temporary_password = False

        # --- Firebase User Creation ---
        if not user.firebase_uid:
            try:
                firebase_auth_password = temp_password if is_temp_password_generated else password
                
                if not user.email or not firebase_auth_password:
                    raise ValueError(_("Email and password are required for Firebase user creation."))

                firebase_user = auth.create_user(
                    email=user.email,
                    password=firebase_auth_password,
                    display_name=user.get_full_name() or user.username,
                    disabled=not user.is_active
                )
                user.firebase_uid = firebase_user.uid
                logger.info(f"Firebase user created: {user.email} (UID: {user.firebase_uid})")

            except ValueError as e:
                logger.error(f"Data error creating Firebase user for {user.email}: {e}")
                raise ValidationError(_(f"Failed to create Firebase user due to data error: {e}"))
            except firebase_exceptions.FirebaseError as e:
                logger.error(f"Firebase API error creating user {user.email}: {e.code} - {e.message}", exc_info=True)
                if e.code == 'auth/email-already-exists':
                    try:
                        existing_firebase_user = auth.get_user_by_email(user.email)
                        user.firebase_uid = existing_firebase_user.uid
                        logger.warning(f"User {user.email} already exists in Firebase. Linked existing UID: {user.firebase_uid}")
                    except firebase_exceptions.FirebaseError as inner_e:
                        logger.error(f"Failed to get existing Firebase user {user.email}: {inner_e}")
                        raise ValidationError(_(f"Firebase user already exists for {user.email}, but failed to link: {inner_e.message}"))
                else:
                    raise ValidationError(_(f"Failed to create Firebase user: {e.message}"))
        else:
            try:
                update_data = {
                    'email': user.email,
                    'display_name': user.get_full_name() or user.username,
                    'disabled': not user.is_active
                }
                if is_temp_password_generated:
                    update_data['password'] = temp_password
                elif password is not None and password != '':
                    update_data['password'] = password

                auth.update_user(user.firebase_uid, **update_data)
                logger.info(f"Firebase user updated: {user.email} (UID: {user.firebase_uid})")

            except firebase_exceptions.FirebaseError as e:
                logger.error(f"Firebase API error updating user {user.email} (UID: {user.firebase_uid}): {e.code} - {e.message}", exc_info=True)
                raise ValidationError(_(f"Failed to update Firebase user: {e.message}"))

        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_active', True)

        if 'role' not in extra_fields:
            try:
                default_role = Role.objects.get(role_name=UserType.PLATFORM_CUSTOMER.value)
                extra_fields['role'] = default_role
            except Role.DoesNotExist:
                raise ValueError(_("Default 'platform_customer' role not found. Please create it or specify a role."))

        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        try:
            app_owner_role = Role.objects.get(role_name=UserType.APP_OWNER.value)
            extra_fields['role'] = app_owner_role
        except Role.DoesNotExist:
            raise ValueError(_("Default 'app_owner' role not found. Please create it."))

        if password is None:
            raise ValueError(_('Superuser must have a password set.'))

        return self._create_user(email, password, **extra_fields)

## UserAccount Model
class UserAccount(AbstractBaseUser, PermissionsMixin):
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('Email Address'), unique=True, blank=False, null=False)

    username = models.CharField(
        _('Username'),
        max_length=150,
        unique=True,
        blank=True,
        null=True,
        help_text=_('Optional. A unique string identifier. Will be auto-generated based on role and email if left blank.')
    )

    firebase_uid = models.CharField(
        max_length=128, unique=True, null=True, blank=True,
        help_text=_("Firebase User ID (UID) for users authenticated via Firebase.")
    )

    first_name = models.CharField(_('First Name'), max_length=150, blank=True)
    last_name = models.CharField(_('Last Name'), max_length=150, blank=True)

    role = models.ForeignKey(
        'Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=False, # Role should generally not be blank
        related_name='user_accounts',
        verbose_name=_('Role')
    )
    
    # NEW FIELD: created_by
    created_by = models.ForeignKey(
        'self', # يشير إلى نفس النموذج UserAccount
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users',
        verbose_name=_('Created By')
    )

    is_active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    is_staff = models.BooleanField(
        _('Staff Status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site. Derived from the assigned role.')
    )
    date_joined = models.DateTimeField(_('Date Joined'), default=timezone.now)

    is_temporary_password = models.BooleanField(
        _('Temporary Password'),
        default=False,
        help_text=_("Designates if the user's current password is a temporary one and needs to be changed on first login.")
    )

    objects = UserAccountManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] # No longer requires username as it's auto-generated if blank

    class Meta:
        verbose_name = _('User Account')
        verbose_name_plural = _('User Accounts')
        constraints = [
            models.UniqueConstraint(
                fields=['username'],
                condition=Q(username__isnull=False) & ~Q(username=''),
                name='unique_username_if_not_null_or_empty_ua',
                violation_error_message=_("A user with that username already exists.")
            ),
        ]

    def __str__(self):
        return self.email if self.email else self.username

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    def is_app_owner(self):
        return self.is_superuser or (self.role and self.role.role_name == UserType.APP_OWNER.value)

    def is_project_manager(self):
        return self.role and self.role.role_name == UserType.PROJECT_MANAGER.value

    def is_app_staff_user(self):
        return self.role and self.role.role_name == UserType.APP_STAFF.value
        
    @property
    def is_store_account(self):
        return self.role and self.role.role_name == UserType.STORE_ACCOUNT.value

    def is_store_manager_user(self):
        return self.role and self.role.role_name == UserType.STORE_MANAGER.value

    def is_branch_manager_user(self):
        return self.role and self.role.role_name == UserType.BRANCH_MANAGER.value

    def is_general_staff_user(self):
        return self.role and self.role.role_name == UserType.GENERAL_STAFF.value

    def is_cashier_user(self):
        return self.role and self.role.role_name == UserType.CASHIER.value

    def is_shelf_organizer_user(self):
        return self.role and self.role.role_name == UserType.SHELF_ORGANIZER.value

    def is_customer_service_user(self):
        return self.role and self.role.role_name == UserType.CUSTOMER_SERVICE.value

    def is_platform_customer(self):
        return self.role and self.role.role_name == UserType.PLATFORM_CUSTOMER.value

    # إزالة حقول store و branch من هنا لأنها الآن في Customer و Employee
    # store = models.ForeignKey('stores.Store', on_delete=models.SET_NULL, null=True, blank=True,
    #                           related_name='store_users', verbose_name=_("Associated Store"),
    #                           help_text=_("The main store this user account is associated with."))
    # branch = models.ForeignKey('stores.Branch', on_delete=models.SET_NULL, null=True, blank=True,
    #                           related_name='branch_users', verbose_name=_("Associated Branch"),
    #                           help_text=_("The specific branch this user account is associated with."))


## Customer Model
class Customer(models.Model):
    customer_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_account = models.OneToOneField(
        'UserAccount',
        on_delete=models.CASCADE,
        related_name='customer_profile',
        verbose_name=_('User Account')
    )
    phone_number = models.CharField(_('Phone Number'), max_length=20, blank=True, null=True)
    address = models.TextField(_('Address'), blank=True, null=True)
    credit_balance = models.DecimalField(
        _("Credit Balance"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    # إضافة حقل المتجر هنا
    store = models.ForeignKey(
        'stores.Store',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers',
        verbose_name=_('Preferred Store')
    )

    class Meta:
        verbose_name = _('Customer Profile')
        verbose_name_plural = _('Customer Profiles')

    def __str__(self):
        return self.user_account.email

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


## Employee Model
class Employee(models.Model):
    employee_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_account = models.OneToOneField(
        'UserAccount',
        on_delete=models.CASCADE,
        related_name='employee_profile',
        verbose_name=_('User Account')
    )

    job_title = models.CharField(
        _('Job Title'),
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Specific job title for this employee (e.g., 'Cashier', 'Branch Manager').")
    )

    store = models.ForeignKey(
        'stores.Store',
        on_delete=models.SET_NULL, null=True, blank=True, related_name='employees',
        verbose_name=_('Associated Store')
    )
    branch = models.ForeignKey(
        'stores.Branch',
        on_delete=models.SET_NULL, null=True, blank=True, related_name='employees',
        verbose_name=_('Associated Branch')
    )
    department = models.ForeignKey(
        'products.Department',
        on_delete=models.SET_NULL, null=True, blank=True, related_name='employees',
        verbose_name=_('Associated Department')
    )

    phone_number = models.CharField(_('Phone Number'), max_length=20, blank=True, null=True)
    tax_id = models.CharField(
        _('Tax ID (VAT/TRN/SSN)'),
        max_length=50,
        blank=True, null=True
    )
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text=_("Commission percentage for sales (e.g., for cashiers)"),
        verbose_name=_("Commission Percentage (%)")
    )

    class Meta:
        verbose_name = _('Employee')
        verbose_name_plural = _('Employees')

    def __str__(self):
        return f"Employee: {self.user_account.email} ({self.job_title if self.job_title else 'N/A'})"

    def clean(self):
        super().clean()

        if not self.user_account:
            raise ValidationError(_("Employee must be linked to a User Account."))

        role_name = self.user_account.role.role_name if self.user_account.role else None

        non_employee_roles = [UserType.PLATFORM_CUSTOMER.value, UserType.APP_OWNER.value, UserType.PROJECT_MANAGER.value, UserType.APP_STAFF.value, UserType.STORE_ACCOUNT.value]
        if role_name in non_employee_roles:
            raise ValidationError(
                _("A user with the role '%(role)s' cannot have an Employee profile."),
                params={'role': role_name}
            )

        if role_name in [UserType.STORE_MANAGER.value, UserType.BRANCH_MANAGER.value, UserType.GENERAL_STAFF.value, UserType.CASHIER.value, UserType.SHELF_ORGANIZER.value, UserType.CUSTOMER_SERVICE.value]:
            if not self.store:
                raise ValidationError(_("Employees with this role must be associated with a store."))

        if role_name == UserType.BRANCH_MANAGER.value:
            if not self.branch:
                raise ValidationError(_("A Branch Manager must be associated with a branch."))

            if self.branch:
                existing_managers = Employee.objects.filter(
                    branch=self.branch,
                    user_account__role__role_name=UserType.BRANCH_MANAGER.value
                ).exclude(pk=self.pk)

                if existing_managers.exists():
                    raise ValidationError(
                        _("Only one branch manager can be assigned per branch. Branch '%(branch_name)s' already has a manager."),
                        params={'branch_name': self.branch.name}
                    )

            if self.branch and (not self.store or self.store != self.branch.store):
                self.store = self.branch.store
            if self.department:
                raise ValidationError(_("A Branch Manager cannot be associated with a department directly."))
            if not self.job_title:
                raise ValidationError(_("A Branch Manager must have a job title."))
            if self.commission_percentage != Decimal('0.00'):
                self.commission_percentage = Decimal('0.00')

        if role_name in [UserType.GENERAL_STAFF.value, UserType.CASHIER.value, UserType.SHELF_ORGANIZER.value, UserType.CUSTOMER_SERVICE.value]:
            if not self.branch:
                raise ValidationError(_("This employee role must be associated with a branch."))
            if not self.job_title:
                raise ValidationError(_("This employee role must have a job title."))

            if self.branch and (not self.store or self.store != self.branch.store):
                self.store = self.branch.store

            if self.department:
                if not self.department.branch:
                    raise ValidationError(_("The associated department must be linked to a branch."))
                if self.department.branch != self.branch:
                    raise ValidationError(_("The associated department's branch must match the employee's assigned branch."))
                if self.department.branch.store != self.store:
                    raise ValidationError(_("The associated department's store must match the employee's assigned store."))

            if role_name != UserType.CASHIER.value and self.commission_percentage != Decimal('0.00'):
                self.commission_percentage = Decimal('0.00')

            if role_name == UserType.CASHIER.value and self.commission_percentage < Decimal('0.00'):
                raise ValidationError(_("Commission percentage cannot be negative."))

            if role_name != UserType.CASHIER.value and self.commission_percentage != Decimal('00.00'):
                self.commission_percentage = Decimal('0.00')


    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

