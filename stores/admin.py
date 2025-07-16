# C:\Users\DELL\SER SQL MY APP\stores\admin.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Store, Branch, StorePermissionProfile, BranchPermissionProfile
from django import forms
from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model
from users.models import Role, UserAccount, UserType, generate_temporary_password, Employee # تأكد من استيراد UserAccount و Employee
from django.contrib import messages
from django.utils.html import format_html
from decimal import Decimal
from django.contrib.auth.models import Permission, Group
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.db.models import Q

# استيراد Firebase Admin SDK
import firebase_admin
from firebase_admin import auth
from firebase_admin import exceptions as firebase_exceptions
import logging

logger = logging.getLogger(__name__)

User = get_user_model() # هذا سيشير إلى UserAccount الآن

# --- Store Permission Profile Admin ---
@admin.register(StorePermissionProfile)
class StorePermissionProfileAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'can_manage_products', 'can_manage_branches',
        'can_manage_staff_accounts', 'can_view_reports', 'can_manage_discounts_offers'
    )
    search_fields = ('name', 'description')
    list_filter = (
        'can_manage_products', 'can_manage_branches',
        'can_manage_staff_accounts', 'can_view_reports', 'can_manage_discounts_offers'
    )
    fieldsets = (
        (None, {
            'fields': ('name', 'description'),
        }),
        (_('Store Operational Permissions'), {
            'fields': (
                'can_manage_products',
                'can_manage_branches',
                'can_manage_staff_accounts',
                'can_view_reports',
                'can_manage_discounts_offers'
            ),
            'description': _("Define the operational permissions for stores assigned to this profile."),
        }),
    )

# --- Branch Permission Profile Admin ---
@admin.register(BranchPermissionProfile)
class BranchPermissionProfileAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'can_manage_branch_profile', 'can_manage_local_staff',
        'can_manage_local_products', 'can_manage_local_offers', 'can_view_local_reports',
        'can_review_ratings', 'can_manage_cart',
    )
    search_fields = ('name', 'description')
    list_filter = (
        'can_manage_branch_profile', 'can_manage_local_staff',
        'can_manage_local_products', 'can_manage_local_offers',
        'can_view_local_reports', 'can_review_ratings',
        'can_apply_discounts', 'can_finalize_invoice', 'can_assist_customer_rating',
        'can_create_promotions', 'can_track_offer_performance',
        'can_manage_daily_statuses', 'can_set_display_priority',
    )
    fieldsets = (
        (None, {
            'fields': ('name', 'description'),
        }),
        (_('Branch General Permissions'), {
            'fields': (
                'can_manage_branch_profile', 'can_manage_local_staff',
                'can_manage_local_products', 'can_manage_local_offers',
                'can_view_local_reports', 'can_review_ratings',
            ),
            'description': _("General management permissions for the branch."),
        }),
        (_('Cashier Permissions'), {
            'fields': (
                'can_manage_cart', 'can_apply_discounts', 'can_finalize_invoice',
                'can_assist_customer_rating',
            ),
            'description': _("Permissions related to cashier operations."),
        }),
        (_('Offers Management Permissions'), {
            'fields': (
                'can_create_promotions', 'can_track_offer_performance',
            ),
            'description': _("Permissions for managing branch-specific offers and promotions."),
        }),
        (_('Marketing & Display Permissions'), {
            'fields': (
                'can_manage_daily_statuses', 'can_set_display_priority',
            ),
            'description': _("Permissions for managing marketing content and display priorities."),
        }),
    )

# --- Store Admin (StoreAdmin) ---
class StoreAdminForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple(
            _('groups'),
            False,
        ),
        help_text=_('The groups this store account will belong to.'),
    )
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple(
            _('user permissions'),
            False,
        ),
        help_text=_('Specific permissions for this store account.'),
    )

    class Meta:
        model = Store
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide the 'user' field (the link to UserAccount) from the form
        # because we will handle this link automatically in save_model.
        if 'user' in self.fields:
            self.fields['user'].widget = forms.HiddenInput()
            self.fields['user'].required = False

        if self.instance and self.instance.pk and self.instance.user:
            self.fields['groups'].initial = self.instance.user.groups.all()
            self.fields['user_permissions'].initial = self.instance.user.user_permissions.all()


    def clean(self):
        cleaned_data = super().clean()
        login_email = cleaned_data.get('login_email')
        
        # Check if an existing UserAccount with the same login_email exists
        existing_user = UserAccount.objects.filter(email=login_email).first()
        
        # If we are creating a new store, and a user with this email already exists, raise an error
        if not self.instance.pk and existing_user:
            self.add_error(
                'login_email', 
                _("A user account with this email already exists. Please choose a different email for the store login.")
            )

        return cleaned_data


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    form = StoreAdminForm

    list_display = (
        'name', 'login_email', 'user', 'permission_profile',
        'tax_id', 'phone_number', 'created_at', 'display_human_store_managers'
    )

    search_fields = ('name', 'login_email', 'tax_id', 'phone_number')
    list_filter = ('created_at', 'permission_profile',)

    readonly_fields = ('user', 'created_at', 'updated_at', 'total_yearly_operations', 'last_yearly_update')

    fieldsets = (
        (_('Store Details'), {
            'fields': ('name', 'address', 'phone_number', 'email', 'tax_id', 'login_email', 'permission_profile'),
            'description': _("Basic information about the store and its primary login email."),
        }),
        (_('Store Account Permissions'), {
            'fields': ('groups', 'user_permissions'),
            'description': _("Define specific Django permissions for the primary store account."),
        }),
        (_('Store Account & System Information'), {
            'fields': ('user', 'created_by', 'created_at', 'updated_at', 'total_yearly_operations', 'last_yearly_update'),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('name', 'login_email', 'tax_id', 'address', 'phone_number', 'email', 'created_by', 'permission_profile'),
            'description': _("Use this form to create a new store. A primary store account will be created automatically."),
        }),
        (_('Store Account Permissions'), {
            'fields': ('groups', 'user_permissions'),
            'description': _("Define specific Django permissions for the primary store account upon creation."),
        }),
    )

    raw_id_fields = ('created_by',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Allow superusers and App Owners to see all stores
        if request.user and (request.user.is_app_owner() or request.user.is_superuser):
            return qs

        # If the user is a Store Account, they only see their managed store
        if hasattr(request.user, 'role') and request.user.role and request.user.role.role_name == UserType.STORE_ACCOUNT.value:
            if hasattr(request.user, 'managed_store') and request.user.managed_store:
                return qs.filter(pk=request.user.managed_store.pk)
            return qs.none() # If they are a store account but no store is managed, show none

        # If the user is an Employee (Store Manager, Branch Manager, etc.), they see their associated store
        if hasattr(request.user, 'employee_profile') and request.user.employee_profile and request.user.employee_profile.store:
            return qs.filter(pk=request.user.employee_profile.store.pk)
        
        return qs.none() # For all other users, show no stores

    def display_human_store_managers(self, obj):
        managers = UserAccount.objects.filter(employee_profile__store=obj, role__role_name=UserType.STORE_MANAGER.value, is_active=True) # استخدام UserAccount
        if managers.exists():
            return ", ".join([manager.email for manager in managers])
        return _("N/A")
    display_human_store_managers.short_description = _("Human Store Manager(s)")

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        is_new_store = not change
        captured_user_password = None
        firebase_uid = None

        logger.debug(f"save_model started. is_new_store: {is_new_store}, obj.pk: {obj.pk}")

        # تعيين created_by تلقائياً عند إنشاء كائن جديد
        if not change and not obj.created_by:
            obj.created_by = request.user
            print(f"StoreAdmin save_model: Auto-setting created_by to {request.user.email}")

        try:
            obj.full_clean()
        except ValidationError as e:
            error_message = e.message_dict if hasattr(e, 'message_dict') else str(e)
            self.message_user(request, format_html(_("<strong>خطأ في التحقق من الصحة:</strong> {}"), error_message), level=messages.ERROR)
            return

        if is_new_store and not obj.pk and obj.login_email:
            base_slug = slugify(obj.name)

            try:
                store_account_role = Role.objects.get(role_name=UserType.STORE_ACCOUNT.value)
            except Role.DoesNotExist:
                self.message_user(request, _("Error: 'store_account' role not found. Please create it in the admin first."), level=messages.ERROR)
                return

            username_candidate = f"{store_account_role.role_name.upper().replace(' ', '_')}-{base_slug}"
            counter = 0
            while UserAccount.objects.filter(username__iexact=username_candidate).exists(): # استخدام UserAccount
                counter += 1
                username_candidate = f"{store_account_role.role_name.upper().replace(' ', '_')}-{base_slug}-{counter}"

            try:
                with transaction.atomic():
                    super().save_model(request, obj, form, change)
                    obj.refresh_from_db()
                    logger.debug(f"Initial super().save_model for new store completed. obj.pk: {obj.pk}")

                    new_temp_password = generate_temporary_password()
                    logger.debug(f"Generated new_temp_password: '{new_temp_password}' for email: {obj.login_email}")

                    logger.debug(f"Attempting to create Firebase user for email: {obj.login_email}")
                    try:
                        if not firebase_admin._apps:
                            logger.error("Firebase Admin SDK is NOT initialized. Cannot create user in Firebase.")
                            raise Exception("Firebase Admin SDK is not initialized. Cannot create user in Firebase.")
                            
                        firebase_user = auth.create_user(
                            email=obj.login_email,
                            password=new_temp_password,
                            display_name=obj.name,
                            email_verified=False,
                            disabled=False
                        )
                        firebase_uid = firebase_user.uid
                        logger.info(f"Firebase user created successfully with UID: {firebase_uid} for email: {obj.login_email}")

                    except firebase_exceptions.FirebaseError as e:
                        logger.error(f"Firebase user creation failed for email {obj.login_email}: {e}", exc_info=True)
                        if "EMAIL_ALREADY_EXISTS" in str(e):
                            messages.error(request, _("خطأ في Firebase: البريد الإلكتروني هذا موجود بالفعل في Firebase. يرجى استخدام بريد إلكتروني آخر أو إعادة تعيين كلمة المرور يدوياً في Firebase."))
                        else:
                            messages.error(request, format_html(_("خطأ في Firebase: {}"), str(e)))
                        raise
                    except Exception as e:
                        logger.error(f"General error during Firebase user creation for email {obj.login_email}: {e}", exc_info=True)
                        messages.error(request, format_html(_("خطأ عام أثناء إنشاء مستخدم Firebase: {}"), str(e)))
                        raise

                    store_account_user = UserAccount.objects.create_user( # استخدام UserAccount
                        email=obj.login_email,
                        password=new_temp_password,
                        username=username_candidate,
                        role=store_account_role,
                        is_staff=True,
                        is_active=True,
                        # لا نربط المتجر هنا مباشرة بـ UserAccount
                        # store=obj, 
                        first_name=obj.name,
                        last_name=_("Account"),
                        firebase_uid=firebase_uid
                    )
                    obj.user = store_account_user
                    
                    store_account_user.is_temporary_password = True
                    store_account_user.save(update_fields=['is_temporary_password', 'firebase_uid'])

                    # ربط المتجر بحساب المستخدم عبر managed_store (لأن هذا هو STORE_ACCOUNT)
                    store_account_user.managed_store = obj
                    store_account_user.save(update_fields=['managed_store'])


                    captured_user_password = new_temp_password
                    logger.debug(f"Captured password for message: '{captured_user_password}'")

                    logger.info(f"\n--- STORE PRIMARY ACCOUNT CREATED for {obj.name} ---")
                    logger.info(f"  Username: {store_account_user.username}")
                    logger.info(f"  Email: {store_account_user.email}")
                    if captured_user_password:
                        logger.info(f"  Temporary Password (for login): {captured_user_password}")
                        logger.info(_("  Please change this password immediately after first login for security."))
                    else:
                        logger.info("  Error: Temporary password was not generated or retrieved.")
                    logger.info("---------------------------------------------------\n")

                    store_account_user.groups.set(form.cleaned_data.get('groups'))
                    store_account_user.user_permissions.set(form.cleaned_data.get('user_permissions'))
                    store_account_user.save()
                    logger.debug(f"User account permissions saved. captured_user_password at end of atomic: '{captured_user_password}'")

            except IntegrityError as e:
                logger.error(f"Django IntegrityError during store account creation: {e}", exc_info=True)
                self.message_user(request, format_html(_("<strong>خطأ:</strong> فشل إنشاء حساب المتجر الرئيسي. قد يكون هناك مستخدم بنفس البريد الإلكتروني/اسم المستخدم أو حساب معين بالفعل. التفاصيل: {}"), str(e)), level=messages.ERROR)
                if firebase_uid:
                    try:
                        auth.delete_user(firebase_uid)
                        logger.warning(f"Rolled back Firebase user {firebase_uid} due to Django error.")
                    except firebase_exceptions.FirebaseError as fe:
                        logger.error(f"ERROR: Failed to delete Firebase user {firebase_uid} during rollback: {fe}")
                return
            except Exception as e:
                logger.error(f"Unexpected error during store account creation (after Firebase attempt): {e}", exc_info=True)
                self.message_user(request, format_html(_("<strong>خطأ غير متوقع:</strong> حدث خطأ أثناء إنشاء حساب المتجر الرئيسي: {}. تم إلغاء إنشاء المتجر."), str(e)), level=messages.ERROR)
                if firebase_uid:
                    try:
                        auth.delete_user(firebase_uid)
                        logger.warning(f"Rolled back Firebase user {firebase_uid} due to Django error.")
                    except firebase_exceptions.FirebaseError as fe:
                        logger.error(f"ERROR: Failed to delete Firebase user {firebase_uid} during rollback: {fe}")
                return
            
        if change:
            super().save_model(request, obj, form, change)
            if obj.user:
                obj.user.groups.set(form.cleaned_data.get('groups'))
                obj.user.user_permissions.set(form.cleaned_data.get('user_permissions'))
                obj.user.save()
            messages.success(request, _("تم تحديث المتجر وصلاحياته بنجاح."))
        else:
            super().save_model(request, obj, form, change)

        if is_new_store and captured_user_password:
            messages.success(
                request,
                format_html(
                    _("تم إنشاء المتجر '{}' وحسابه الرئيسي بنجاح.<br>"
                      "<strong>البريد الإلكتروني لتسجيل الدخول:</strong> {}<br>"
                      "<strong>اسم المستخدم لتسجيل الدخول:</strong> {}<br>"
                      "<strong>كلمة المرور المؤقتة لتسجيل الدخول (انسخها الآن):</strong> {}<br>"
                      "يرجى تقديم هذه المعلومات لمالك المتجر ونصحه بتغييرها فوراً.<br>"
                      "<strong>Firebase UID:</strong> {}"),
                    obj.name,
                    obj.login_email,
                    obj.user.username,
                    captured_user_password,
                    obj.user.firebase_uid
                ),
                extra_tags='safe'
            )
            logger.info(f"Success message ADDED for new store with password.")
        elif is_new_store:
            messages.warning(request, _("تم إنشاء المتجر بنجاح، ولكن لم يتم عرض كلمة المرور المؤقتة. يرجى إعادة تعيين كلمة المرور يدوياً للمستخدم من خلال قسم 'Accounts'."))
            logger.warning(f"Warning message ADDED (password not found).")


# --- Branch Admin (BranchAdmin) ---

class BranchAdminForm(forms.ModelForm):
    # حقل لعرض معلومات المتجر المرتبط بشكل غير قابل للتعديل
    _display_store_info = forms.CharField(
        label=_("Associated Store"),
        required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly'})
    )
    # حقل لعرض معلومات الفرع المرتبط بشكل غير قابل للتعديل (إذا كان المستخدم مدير فرع)
    _display_branch_info = forms.CharField(
        label=_("Associated Branch"),
        required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly'})
    )

    class Meta:
        model = Branch
        exclude = (
            'created_at', 'updated_at',
            'daily_operations', 'monthly_operations', 'total_yearly_operations',
            'last_daily_update', 'last_monthly_update', 'last_yearly_update',
            'latitude', 'longitude',
            'branch_id_number',
        )
        widgets = {
            'manager_employee': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        current_user = self.request.user if self.request else None
        
        print(f"\n--- BranchAdminForm __init__ Debug ---")
        if current_user and current_user.is_authenticated:
            current_user_role_name = current_user.role.role_name if hasattr(current_user, 'role') and current_user.role else 'N/A'
            print(f"Current User: {current_user.email}, Is Superuser: {current_user.is_superuser}, Role: {current_user_role_name}")
            
            # الحصول على المتجر/الفرع المرتبط بالمستخدم الحالي عبر ملف التعريف
            current_user_profile_store = None
            current_user_profile_branch = None
            
            # Check for STORE_ACCOUNT first
            if current_user_role_name == UserType.STORE_ACCOUNT.value and hasattr(current_user, 'managed_store') and current_user.managed_store:
                current_user_profile_store = current_user.managed_store
                print(f"Current User is STORE_ACCOUNT, managed_store: {current_user_profile_store.name}")
            elif hasattr(current_user, 'employee_profile') and current_user.employee_profile:
                current_user_profile_store = current_user.employee_profile.store
                current_user_profile_branch = current_user.employee_profile.branch
                print(f"Current User is Employee. Store: {current_user_profile_store.name if current_user_profile_store else 'None'}, Branch: {current_user_profile_branch.name if current_user_profile_branch else 'None'}")
            elif hasattr(current_user, 'customer_profile') and current_user.customer_profile:
                current_user_profile_store = current_user.customer_profile.store
                print(f"Current User is Customer. Store: {current_user_profile_store.name if current_user_profile_store else 'None'}")

            print(f"Current User Profile Store (final): {current_user_profile_store.name if current_user_profile_store else 'None'}")
            print(f"Current User Profile Branch (final): {current_user_profile_branch.name if current_user_profile_branch else 'None'}")
        else:
            print("No authenticated user in request or current_user is None.")

        # تحميل القيمة الأولية للمتجر إذا كان كائن الفرع موجودًا
        if self.instance and self.instance.pk and self.instance.store:
            self.fields['store'].initial = self.instance.store
            self.fields['_display_store_info'].initial = f"{self.instance.store.name} (ID: {self.instance.store.store_id})" # Use store_id
            print(f"Editing existing branch, initial store: {self.instance.store.name}")
            
        # تعيين المتجر تلقائياً وإخفاء الحقل إذا كان المستخدم الحالي مرتبطاً بمتجر
        if current_user and current_user.is_authenticated:
            is_app_owner_or_superuser = current_user.is_app_owner() or current_user.is_superuser

            # Logic for hiding 'store' field and setting initial value
            if current_user_profile_store and not is_app_owner_or_superuser:
                print(f"BranchAdminForm: Hiding 'store' field and displaying info for user {current_user.email}")
                self.fields['store'].initial = current_user_profile_store
                self.fields['store'].widget = forms.HiddenInput()
                self.fields['store'].required = False
                self.fields['_display_store_info'].initial = f"{current_user_profile_store.name} (ID: {current_user_profile_store.store_id})" # Use store_id
                self.fields['_display_store_info'].widget.attrs['readonly'] = 'readonly'
            else:
                # If App Owner/Superuser, or no store associated, keep 'store' field visible
                print(f"BranchAdminForm: Not hiding 'store' field. User Profile Store: {current_user_profile_store.name if current_user_profile_store else 'N/A'}, Is App Owner/Superuser: {is_app_owner_or_superuser}")
                # Ensure _display_store_info is removed if 'store' is visible
                if '_display_store_info' in self.fields:
                    del self.fields['_display_store_info']
            
            # فلترة مديري الفروع المتاحين للمتجر الحالي
            if current_user_profile_store:
                # Query for Employee profiles associated with the current user's store
                # Exclude App Owners and Superusers
                # Also exclude existing Branch Managers unless it's the current object's manager
                queryset = Employee.objects.filter(
                    store=current_user_profile_store
                ).exclude(
                    Q(user_account__role__role_name=UserType.APP_OWNER.value) |
                    Q(user_account__is_superuser=True)
                )

                # If editing an existing branch, allow its current manager to be selected
                if self.instance and self.instance.pk and self.instance.manager_employee:
                    queryset = queryset.filter(
                        Q(user_account__role__role_name=UserType.BRANCH_MANAGER.value) |
                        Q(user_account=self.instance.manager_employee) # Include current manager
                    )
                else:
                    # For new branches, exclude existing branch managers
                    queryset = queryset.exclude(user_account__role__role_name=UserType.BRANCH_MANAGER.value)
                
                self.fields['manager_employee'].queryset = UserAccount.objects.filter(pk__in=queryset.values_list('user_account__pk', flat=True))
                print(f"Filtered manager_employee queryset for store {current_user_profile_store.name}: {self.fields['manager_employee'].queryset.values_list('email', flat=True)}")
            else:
                # If no store is associated with the current user, or they are App Owner/Superuser,
                # they can select from all users who are not App Owners/Superusers.
                # This might need further refinement based on business logic.
                self.fields['manager_employee'].queryset = UserAccount.objects.all().exclude(
                    Q(role__role_name=UserType.APP_OWNER.value) | Q(is_superuser=True)
                )
                print(f"Manager_employee queryset for App Owner/No Store: {self.fields['manager_employee'].queryset.values_list('email', flat=True)}")
        else: # إذا لم يكن هناك مستخدم مسجل الدخول
            self.fields['manager_employee'].queryset = UserAccount.objects.none() # لا تظهر أي موظفين
            print("No authenticated user, manager_employee queryset is empty.")

        print(f"--- End BranchAdminForm __init__ Debug ---\n")

    def clean_store(self):
        current_user = self.request.user if self.request else None
        if current_user and current_user.is_authenticated:
            current_user_profile_store = None
            
            if hasattr(current_user, 'role') and current_user.role and current_user.role.role_name == UserType.STORE_ACCOUNT.value and hasattr(current_user, 'managed_store') and current_user.managed_store:
                current_user_profile_store = current_user.managed_store
            elif hasattr(current_user, 'employee_profile') and current_user.employee_profile and current_user.employee_profile.store:
                current_user_profile_store = current_user.employee_profile.store

            if current_user_profile_store and not (current_user.is_app_owner() or current_user.is_superuser):
                return current_user_profile_store
        
        # If the user is an App Owner/Superuser, or no store is associated, return the value from the form
        return self.cleaned_data.get('store')


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    form = BranchAdminForm

    list_display = (
        'name', 'store', 'phone_number', 'email', 'branch_id_number',
        'manager_employee', 'permission_profile',
        'created_at', 'updated_at'
    )
    search_fields = ('name', 'store__name', 'branch_id_number', 'email')
    list_filter = ('store', 'created_at', 'permission_profile',)
    raw_id_fields = ('store', 'manager_employee', 'created_by')

    readonly_fields = (
        'created_at', 'updated_at', 'branch_id_number',
        'daily_operations', 'monthly_operations', 'total_yearly_operations',
        'last_daily_update', 'last_monthly_update', 'last_yearly_update',
        'latitude', 'longitude'
    )

    fieldsets = (
        (None, {
            'fields': ('store', 'name', 'address', 'phone_number', 'email', 'branch_tax_id', 'permission_profile'),
            'description': _("Basic information and identification for the branch."),
        }),
        (_('Geographical Data'), {
            'fields': ('latitude', 'longitude'),
            'description': _("Location coordinates for the branch (auto-generated if address provided)."),
            'classes': ('collapse',),
        }),
        (_('Operational Details'), {
            'fields': ('fee_percentage', 'daily_operations', 'monthly_operations', 'total_yearly_operations', 'last_daily_update', 'last_monthly_update', 'last_yearly_update'),
            'description': _("Operational statistics and fee structure for the branch."),
            'classes': ('collapse',),
        }),
        (_('Manager Assignment & System Information'), {
            'fields': ('manager_employee', 'created_by'),
            'description': _("Assign a manager and set the branch status."),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('store', 'name', 'address', 'phone_number', 'email', 'branch_tax_id', 'manager_employee', 'created_by', 'fee_percentage', 'permission_profile'),
            'description': _("Use this form to add a new branch to an existing store."),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.request = request # Pass the request to the form
        return form
        
    def get_fieldsets(self, request, obj=None):
        print(f"\n--- BranchAdmin get_fieldsets Debug ---")
        print(f"Request User: {request.user.email}")
        
        fieldsets_to_display = super().get_fieldsets(request, obj)
        request_user_role_name = request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else None
        print(f"Request User Role Name: {request_user_role_name}")

        # الحصول على المتجر/الفرع المرتبط بالمستخدم الحالي عبر ملف التعريف
        current_user_profile_store = None
        current_user_profile_branch = None
        
        # Check for STORE_ACCOUNT first
        if request_user_role_name == UserType.STORE_ACCOUNT.value and hasattr(request.user, 'managed_store') and request.user.managed_store:
            current_user_profile_store = request.user.managed_store
        elif hasattr(request.user, 'employee_profile') and request.user.employee_profile:
            current_user_profile_store = request.user.employee_profile.store
            current_user_profile_branch = request.user.employee_profile.branch
        elif hasattr(request.user, 'customer_profile') and request.user.customer_profile:
            current_user_profile_store = request.user.customer_profile.store

        mutable_fieldsets = [list(fs) for fs in fieldsets_to_display]

        for i, (name, opts) in enumerate(mutable_fieldsets):
            if name == None or name == _('Store Details'): # Check for both initial None and actual label
                current_fields = list(opts['fields'])
                print(f"Original fields in 'Store Details' (or None): {current_fields}")
                
                is_app_owner_or_superuser = request.user and (request.user.is_superuser or (request_user_role_name == UserType.APP_OWNER.value))
                print(f"get_fieldsets: Is current user App Owner or Superuser? {is_app_owner_or_superuser}")
                print(f"get_fieldsets: Request User Profile Store: {current_user_profile_store.name if current_user_profile_store else 'None'}")

                if current_user_profile_store and not is_app_owner_or_superuser:
                    print(f"get_fieldsets: Replacing 'store' with '_display_store_info'")
                    if 'store' in current_fields:
                        store_index = current_fields.index('store')
                        current_fields[store_index:store_index+1] = ['_display_store_info'] # Replace 'store'
                    else:
                        current_fields.insert(0, '_display_store_info') # Add at the beginning if 'store' not found
                else:
                    print(f"get_fieldsets: 'store' field remains as is or will be removed if not relevant.")
                    if '_display_store_info' in current_fields:
                        current_fields.remove('_display_store_info')
                
                mutable_fieldsets[i] = (name, {'fields': tuple(current_fields)})
                break

        print(f"--- End BranchAdmin get_fieldsets Debug ---\n")
        return [tuple(fs) for fs in mutable_fieldsets]

    def get_add_fieldsets(self, request):
        print(f"\n--- BranchAdmin get_add_fieldsets Debug ---")
        print(f"Request User: {request.user.email}")
        
        add_fieldsets_to_display = super().get_add_fieldsets(request)
        request_user_role_name = request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else None
        print(f"Request User Role Name: {request_user_role_name}")

        # الحصول على المتجر/الفرع المرتبط بالمستخدم الحالي عبر ملف التعريف
        current_user_profile_store = None
        current_user_profile_branch = None
        
        # Check for STORE_ACCOUNT first
        if request_user_role_name == UserType.STORE_ACCOUNT.value and hasattr(request.user, 'managed_store') and request.user.managed_store:
            current_user_profile_store = request.user.managed_store
        elif hasattr(request.user, 'employee_profile') and request.user.employee_profile:
            current_user_profile_store = request.user.employee_profile.store
            current_user_profile_branch = request.user.employee_profile.branch
        elif hasattr(request.user, 'customer_profile') and request.user.customer_profile:
            current_user_profile_store = request.user.customer_profile.store

        mutable_add_fieldsets = [list(fs) for fs in add_fieldsets_to_display]

        for i, (name, opts) in enumerate(mutable_add_fieldsets):
            if name == None: # Add fieldsets often start with a None-named fieldset
                current_fields = list(opts['fields'])
                print(f"Original fields in add_fieldsets (None): {current_fields}")

                is_app_owner_or_superuser = request.user and (request.user.is_superuser or (request_user_role_name == UserType.APP_OWNER.value))
                print(f"get_add_fieldsets: Is current user App Owner or Superuser? {is_app_owner_or_superuser}")
                print(f"get_add_fieldsets: Request User Profile Store: {current_user_profile_store.name if current_user_profile_store else 'None'}")

                if current_user_profile_store and not is_app_owner_or_superuser:
                    print(f"get_add_fieldsets: Replacing 'store' with '_display_store_info'")
                    if 'store' in current_fields:
                        store_index = current_fields.index('store')
                        current_fields[store_index:store_index+1] = ['_display_store_info'] # Replace 'store'
                    else:
                        current_fields.insert(0, '_display_store_info') # Add at the beginning if 'store' not found
                else:
                    print(f"get_add_fieldsets: 'store' field remains as is or will be removed if not relevant.")
                    if '_display_store_info' in current_fields:
                        current_fields.remove('_display_store_info')

                mutable_add_fieldsets[i] = (name, {'fields': tuple(current_fields)})
                break

        print(f"--- End BranchAdmin get_add_fieldsets Debug ---\n")
        return [tuple(fs) for fs in mutable_add_fieldsets]


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Allow superusers and App Owners to see all branches
        if request.user and (request.user.is_app_owner() or request.user.is_superuser):
            return qs

        # If the user is a Store Account, they only see branches of their managed store
        if hasattr(request.user, 'role') and request.user.role and request.user.role.role_name == UserType.STORE_ACCOUNT.value:
            if hasattr(request.user, 'managed_store') and request.user.managed_store:
                return qs.filter(store=request.user.managed_store)
            return qs.none()

        # If the user is a Store Manager, they only see branches of their associated store
        if hasattr(request.user, 'employee_profile') and request.user.employee_profile and request.user.employee_profile.store:
            return qs.filter(store=request.user.employee_profile.store)
        
        # If the user is a Branch Manager, they only see their specific branch
        if hasattr(request.user, 'employee_profile') and request.user.employee_profile and request.user.employee_profile.branch:
            return qs.filter(pk=request.user.employee_profile.branch.pk)

        return qs.none() # For all other users, show no branches

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        is_new_branch = not change
        created_manager_password = None

        # تعيين created_by تلقائياً عند إنشاء كائن جديد
        if not change and not obj.created_by:
            obj.created_by = request.user
            print(f"BranchAdmin save_model: Auto-setting created_by to {request.user.email}")

        # تعيين المتجر تلقائيًا إذا كان المستخدم الحالي مرتبطًا بمتجر
        current_user_profile_store = None
        current_user_role_name = request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else None

        if current_user_role_name == UserType.STORE_ACCOUNT.value and hasattr(request.user, 'managed_store') and request.user.managed_store:
            current_user_profile_store = request.user.managed_store
        elif hasattr(request.user, 'employee_profile') and request.user.employee_profile and request.user.employee_profile.store:
            current_user_profile_store = request.user.employee_profile.store

        # If the 'store' field was hidden (meaning current user is store-affiliated and not superuser/app_owner),
        # then set the store from the current user's profile.
        if '_display_store_info' in form.fields and current_user_profile_store and not (request.user.is_app_owner() or request.user.is_superuser):
            obj.store = current_user_profile_store
            print(f"BranchAdmin save_model: Auto-setting store to '{obj.store.name}' from current user's context.")
        elif not obj.store and request.user and not (request.user.is_app_owner() or request.user.is_superuser):
            # This case means 'store' field was visible but not selected, and user is not superuser/app_owner
            # This should ideally be caught by form validation if 'store' is required.
            self.message_user(request, _("يجب تحديد المتجر للفرع."), level=messages.ERROR)
            return

        try:
            obj.full_clean()
        except ValidationError as e:
            error_message = e.message_dict if hasattr(e, 'message_dict') else str(e)
            self.message_user(request, format_html(_("<strong>خطأ في التحقق من الصحة:</strong> {}"), error_message), level=messages.ERROR)
            return

        selected_user_from_form = form.cleaned_data.get('manager_employee')

        if selected_user_from_form is None:
            messages.error(request, _("يجب اختيار حساب مدير فرع موجود لربطه بالفرع."))
            return

        obj.manager_employee = selected_user_from_form
        try:
            branch_manager_role = Role.objects.get(role_name=UserType.BRANCH_MANAGER.value)
        except Role.DoesNotExist:
            self.message_user(request, _("Error: 'branch_manager' role not found. Please create it in the admin first."), level=messages.ERROR)
            return

        if obj.manager_employee.role != branch_manager_role:
            obj.manager_employee.role = branch_manager_role
            obj.manager_employee.is_staff = True
            obj.manager_employee.is_active = True
            # تحديث Employee profile للمدير
            employee_profile, created = Employee.objects.get_or_create(user_account=obj.manager_employee)
            employee_profile.store = obj.store
            employee_profile.branch = obj
            employee_profile.job_title = _("Branch Manager")
            employee_profile.save(update_fields=['store', 'branch', 'job_title'])
            obj.manager_employee.save(update_fields=['role', 'is_staff', 'is_active']) # حفظ التغييرات على UserAccount
        else:
            updated_fields = []
            employee_profile, created = Employee.objects.get_or_create(user_account=obj.manager_employee) # Use get_or_create to ensure it exists
            if employee_profile.store != obj.store:
                employee_profile.store = obj.store
                updated_fields.append('store')
            if employee_profile.branch != obj:
                employee_profile.branch = obj
                updated_fields.append('branch')
            if updated_fields:
                employee_profile.save(update_fields=updated_fields)

        if not obj.manager_employee.firebase_uid or obj.manager_employee.is_temporary_password:
            try:
                try:
                    firebase_user = auth.get_user(obj.manager_employee.firebase_uid)
                    logger.info(f"Firebase user {obj.manager_employee.firebase_uid} already exists for existing Django user.")
                    if obj.manager_employee.is_temporary_password:
                        new_firebase_password = generate_temporary_password()
                        auth.update_user(
                            obj.manager_employee.firebase_uid,
                            password=new_firebase_password
                        )
                        created_manager_password = new_firebase_password
                        obj.manager_employee.is_temporary_password = True
                        obj.manager_employee.save(update_fields=['is_temporary_password'])
                        logger.info(f"Firebase password reset for existing user {obj.manager_employee.email}.")
                except auth.UserNotFoundError:
                    logger.warning(f"Firebase UID {obj.manager_employee.firebase_uid} not found in Firebase for existing Django user. Attempting to create.")
                    new_firebase_password = generate_temporary_password() 
                    firebase_user = auth.create_user(
                        email=obj.manager_employee.email,
                        password=new_firebase_password,
                        display_name=obj.manager_employee.get_full_name() or obj.manager_employee.username,
                        email_verified=False,
                        disabled=False,
                        uid=obj.manager_employee.firebase_uid
                    )
                    obj.manager_employee.firebase_uid = firebase_user.uid
                    obj.manager_employee.is_temporary_password = True
                    obj.manager_employee.save(update_fields=['firebase_uid', 'is_temporary_password'])
                    created_manager_password = new_firebase_password
                    logger.info(f"Firebase user created for existing Django user: {firebase_user.uid}")
            except firebase_exceptions.FirebaseError as e:
                logger.error(f"Failed to create/update Firebase user for existing Django user {obj.manager_employee.email}: {e}", exc_info=True)
                messages.error(request, format_html(_("خطأ في Firebase أثناء مزامنة مستخدم موجود: {}"), str(e)))
            except Exception as e:
                logger.error(f"General error during Firebase user create/update for existing Django user: {e}", exc_info=True)
                messages.error(request, format_html(_("خطأ عام أثناء مزامنة مستخدم Firebase موجود: {}"), str(e)))

        super().save_model(request, obj, form, change)

        if is_new_branch and obj.manager_employee:
            if created_manager_password:
                messages.success(
                    request,
                    format_html(
                        _("تم إنشاء الفرع '{}' بنجاح وربطه بمديره.<br>"
                          "<strong>البريد الإلكتروني لمدير الفرع:</strong> {}<br>"
                          "<strong>اسم المستخدم لمدير الفرع:</strong> {}<br>"
                          "<strong>كلمة المرور المؤقتة لمدير الفرع (انسخها الآن):</strong> {}<br>"
                          "يرجى تقديم هذه المعلومات للمدير ونصحه بتغييرها فوراً.<br>"
                          "<strong>Firebase UID:</strong> {}"),
                        obj.name,
                        obj.manager_employee.email,
                        obj.manager_employee.username,
                        created_manager_password,
                        obj.manager_employee.firebase_uid
                    ),
                    extra_tags='safe'
                )
            else:
                messages.info(request, format_html(_("تم إنشاء الفرع '{}' بنجاح وربطه بمديره: <strong>{}</strong>. لم يتم إنشاء كلمة مرور مؤقتة لأن الحساب موجود بالفعل."), obj.name, obj.manager_employee.email))
        elif not is_new_branch and obj.manager_employee:
            messages.success(request, format_html(_("تم تحديث الفرع '{}' بنجاح. تم تحديث بيانات المدير: <strong>{}</strong>"), obj.name, obj.manager_employee.email))

