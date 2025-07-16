import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.exceptions import ValidationError
# from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from enum import Enum

from .utils import generate_temporary_password
from .firebase_services import create_firebase_user, update_firebase_user, get_existing_firebase_user_uid

# تعريف UserType كتعداد (Enum)
class UserType(Enum):
    APP_OWNER = 'app_owner'
    PROJECT_MANAGER = 'project_manager'
    APP_STAFF = 'app_staff'
    STORE_ACCOUNT = 'store_account'
    STORE_MANAGER = 'store_manager'
    BRANCH_MANAGER = 'branch_manager'
    GENERAL_STAFF = 'general_staff'
    CASHIER = 'cashier'
    SHELF_ORGANIZER = 'shelf_organizer'
    CUSTOMER_SERVICE = 'customer_service'
    PLATFORM_CUSTOMER = 'platform_customer'

    @classmethod
    def choices(cls):
        return [(key.value, key.name.replace('_', ' ').title()) for key in cls]

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
            base_slug = email.split('@')[0].replace('.', '_')
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
            user._temporary_password = temp_password
            is_temp_password_generated = True
        else:
            user.set_password(password)
            user.is_temporary_password = False

        if not user.firebase_uid:
            try:
                firebase_auth_password = temp_password if is_temp_password_generated else password
                user.firebase_uid = create_firebase_user(
                    email=user.email,
                    password=firebase_auth_password,
                    display_name=user.get_full_name() or user.username,
                    is_active=user.is_active
                )
            except ValidationError:
                try:
                    user.firebase_uid = get_existing_firebase_user_uid(user.email)
                except ValidationError as e:
                    raise e
        else:
            update_firebase_user(
                uid=user.firebase_uid,
                email=user.email,
                password=temp_password if is_temp_password_generated else password,
                display_name=user.get_full_name() or user.username,
                is_active=user.is_active
            )

        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_active', True)
        if 'role' not in extra_fields:
            try:
                extra_fields['role'] = Role.objects.get(role_name=UserType.PLATFORM_CUSTOMER.value)
            except Role.DoesNotExist:
                raise ValueError(_("Default 'platform_customer' role not found."))
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        try:
            extra_fields['role'] = Role.objects.get(role_name=UserType.APP_OWNER.value)
        except Role.DoesNotExist:
            raise ValueError(_("Default 'app_owner' role not found."))
        if password is None:
            raise ValueError(_('Superuser must have a password set.'))
        return self._create_user(email, password, **extra_fields)

class UserAccount(AbstractBaseUser, PermissionsMixin):
    user_id = models.UUIDField(primary_key=True, default= uuid.uuid4, editable=False)
    email = models.EmailField(_('Email Address'), unique=True)
    username = models.CharField(_('Username'), max_length=150, unique=True, blank=True, null=True)
    firebase_uid = models.CharField(max_length=128, unique=True, null=True, blank=True)
    first_name = models.CharField(_('First Name'), max_length=150, blank=True)
    last_name = models.CharField(_('Last Name'), max_length=150, blank=True)
    role = models.ForeignKey('Role', on_delete=models.SET_NULL, null=True, related_name='user_accounts')
    created_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users')
    is_active = models.BooleanField(_('Active'), default=True)
    is_staff = models.BooleanField(_('Staff Status'), default=False)
    date_joined = models.DateTimeField(_('Date Joined'), default=timezone.now)
    is_temporary_password = models.BooleanField(_('Temporary Password'), default=False)

    objects = UserAccountManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('User Account')
        verbose_name_plural = _('User Accounts')
        constraints = [
            models.UniqueConstraint(
                fields=['username'],
                condition=Q(username__isnull=False) & ~Q(username=''),
                name='unique_username_if_not_null_or_empty_ua'
            ),
        ]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    def is_app_owner(self): return self.is_superuser or (self.role and self.role.role_name == UserType.APP_OWNER.value)
    def is_project_manager(self): return self.role and self.role.role_name == UserType.PROJECT_MANAGER.value
    def is_app_staff_user(self): return self.role and self.role.role_name == UserType.APP_STAFF.value
    @property
    def is_store_account(self): return self.role and self.role.role_name == UserType.STORE_ACCOUNT.value
    def is_store_manager_user(self): return self.role and self.role.role_name == UserType.STORE_MANAGER.value
    def is_branch_manager_user(self): return self.role and self.role.role_name == UserType.BRANCH_MANAGER.value
    def is_general_staff_user(self): return self.role and self.role.role_name == UserType.GENERAL_STAFF.value
    def is_cashier_user(self): return self.role and self.role.role_name == UserType.CASHIER.value
    def is_shelf_organizer_user(self): return self.role and self.role.role_name == UserType.SHELF_ORGANIZER.value
    def is_customer_service_user(self): return self.role and self.role.role_name == UserType.CUSTOMER_SERVICE.value
    def is_platform_customer(self): return self.role and self.role.role_name == UserType.PLATFORM_CUSTOMER.value
