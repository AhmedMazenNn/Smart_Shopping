# C:\Users\DELL\SER SQL MY APP\mysite\custom_admin_site.py

from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _
from django import forms
from users.models import UserAccount, Role, UserType, Employee, Customer # استيراد Employee, Customer و UserType
# ******************** تأكد من أن UserAccountAdmin موجودة في users/admin.py ********************
from users.admin import UserAccountAdmin as MainUserAccountAdmin

from stores.models import Store, Branch
from stores.admin import BranchAdmin, StoreAdmin

from products.models import Department, Product, ProductCategory, BranchProductInventory
from sales.models import TempOrder, TempOrderItem, Order, OrderItem
from integrations.models import AccountingSystemConfig, ProductSyncLog, SaleInvoiceSyncLog, ZatcaInvoice

from decimal import Decimal # لاستخدام Decimal في get_commission_percentage
from django.db.models import Q


# -------------------------------------------------------------
# 1. موقع الإدارة الخاص بمالك التطبيق/المشرف العام (App Owner / Superuser Admin Site)
# -------------------------------------------------------------
class AppOwnerAdminSite(AdminSite):
    site_header = _("My App Admin")
    site_title = _("My App Admin Portal")
    index_title = _("Welcome to My App Administration")
    name = 'app_owner_admin'

    def has_permission(self, request):
        if request.user.is_authenticated:
            if request.user.is_superuser:
                return True
            if hasattr(request.user, 'is_app_owner') and request.user.is_app_owner():
                return True
            if hasattr(request.user, 'is_project_manager') and request.user.is_project_manager():
                return True
        return False

app_owner_admin_site = AppOwnerAdminSite(name='app_owner_admin')

app_owner_admin_site.register(UserAccount, MainUserAccountAdmin)
app_owner_admin_site.register(Store, StoreAdmin)
app_owner_admin_site.register(Branch, BranchAdmin)
app_owner_admin_site.register(Department)
app_owner_admin_site.register(Product)
app_owner_admin_site.register(ProductCategory)
app_owner_admin_site.register(BranchProductInventory)
app_owner_admin_site.register(TempOrder)
app_owner_admin_site.register(TempOrderItem)
app_owner_admin_site.register(Order)
app_owner_admin_site.register(OrderItem)
app_owner_admin_site.register(AccountingSystemConfig)
app_owner_admin_site.register(ProductSyncLog)
app_owner_admin_site.register(SaleInvoiceSyncLog)
app_owner_admin_site.register(ZatcaInvoice)
app_owner_admin_site.register(Role)

# -------------------------------------------------------------
# 2. موقع الإدارة الخاص بمدراء المتاجر (Store Manager Admin Site)
# -------------------------------------------------------------
class StoreManagerAdminSite(AdminSite):
    site_header = _("Store Manager Dashboard")
    site_title = _("Store Admin Panel")
    index_title = _("Welcome to your Store Management Panel")
    name = 'store_manager_admin'

    def has_permission(self, request):
        return request.user.is_authenticated and (
            (hasattr(request.user, 'is_store_manager_user') and request.user.is_store_manager_user()) or
            (hasattr(request.user, 'is_branch_manager_user') and request.user.is_branch_manager_user()) or # إضافة مديري الفروع هنا
            request.user.is_superuser or
            (hasattr(request.user, 'is_app_owner') and request.user.is_app_owner()) or
            (hasattr(request.user, 'is_project_manager') and request.user.is_project_manager())
        )

store_manager_panel = StoreManagerAdminSite(name='store_manager_admin')

# --- فئة Admin مخصصة للمستخدمين داخل لوحة إدارة مدير المتجر ---
# هذه الفئة ستكون مسؤولة فقط عن إنشاء وتعديل المستخدمين التابعين للمتجر/الفرع
class ManagerUserAdmin(MainUserAccountAdmin): # ترث من MainUserAccountAdmin
    # استخدام علاقات Employee لإظهار الحقول الخاصة بالموظفين
    list_display = (
        'email', 'username', 'get_role_display', # استخدام get_role_display من MainUserAccountAdmin
        'get_job_title', 'get_branch_name', 'get_department_name', # -> استخدام دوال مساعدة
        'is_active', 'get_commission_percentage' # -> استخدام دوال مساعدة
    )
    # حقول البحث والفلترة
    search_fields = (
        'email', 'username', 'role__role_name',
        'employee_profile__phone_number', 'employee_profile__job_title',
        'employee_profile__branch__name', 'employee_profile__department__name'
    )
    list_filter = ('role__role_name', 'is_active', 'employee_profile__branch__name', 'employee_profile__department__name') # -> استخدام علاقة employee_profile

    # تم تبسيط fieldsets و add_fieldsets لتعكس أن حقول Employee Profile لا تظهر هنا مباشرة
    fieldsets = (
        (None, {'fields': ('email', 'username', 'firebase_uid')}),
        (_('Personal Info & Contact'), {'fields': ('first_name', 'last_name', 'phone_number', 'tax_id', 'job_title')}), # أعدت phone_number, tax_id, job_title
        (_('Role & Association'), {'fields': ('role', 'store', 'branch', 'department')}), # أعدت store, branch, department
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions', 'is_temporary_password')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password', 'password2')
        }),
        (_('Personal Info & Contact'), {'fields': ('first_name', 'last_name', 'phone_number', 'tax_id', 'job_title')}), # أعدت phone_number, tax_id, job_title
        (_('Role & Association'), {'fields': ('role', 'store', 'branch', 'department')}), # أعدت store, branch, department
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )

    # إزالة readonly_fields التي كانت تسبب المشكلة
    readonly_fields = ('date_joined', 'last_login', 'firebase_uid', 'is_temporary_password')


    # دوال مساعدة لـ list_display للوصول إلى حقول Employee
    def get_job_title(self, obj):
        return obj.employee_profile.job_title if hasattr(obj, 'employee_profile') and obj.employee_profile else _("N/A")
    get_job_title.short_description = _("Job Title")
    get_job_title.admin_order_field = 'employee_profile__job_title'

    def get_branch_name(self, obj):
        return obj.employee_profile.branch.name if hasattr(obj, 'employee_profile') and obj.employee_profile.branch else _("N/A")
    get_branch_name.short_description = _("Branch")
    get_branch_name.admin_order_field = 'employee_profile__branch__name'

    def get_department_name(self, obj):
        return obj.employee_profile.department.name if hasattr(obj, 'employee_profile') and obj.employee_profile.department else _("N/A")
    get_department_name.short_description = _("Department")
    get_department_name.admin_order_field = 'employee_profile__department__name'

    def get_commission_percentage(self, obj):
        return obj.employee_profile.commission_percentage if hasattr(obj, 'employee_profile') else Decimal('0.00')
    get_commission_percentage.short_description = _("Commission (%)")
    get_commission_percentage.admin_order_field = 'employee_profile__commission_percentage'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        is_new_user = obj is None

        current_user = request.user
        current_user_role_name = current_user.role.role_name if hasattr(current_user, 'role') and current_user.role else 'N/A'
        is_app_owner_or_superuser = current_user.is_app_owner() or current_user.is_superuser

        print(f"\n--- ManagerUserAdmin get_form Debug for user: {current_user.email} (Is Superuser: {current_user.is_superuser}, Role: {current_user_role_name}) ---")

        # Password visibility for new users
        if is_new_user:
            if 'password' in form.base_fields:
                form.base_fields['password'].widget = forms.TextInput(attrs={
                    'placeholder': _("Enter password (visible as text)"),
                    'class': 'vTextField'
                })
            if 'password2' in form.base_fields:
                form.base_fields['password2'].widget = forms.TextInput(attrs={
                    'placeholder': _("Confirm password (visible as text)"),
                    'class': 'vTextField'
                })
            if 'username' in form.base_fields:
                form.base_fields['username'].required = False
                if form.base_fields['username'].initial is None:
                    form.base_fields['username'].widget = forms.HiddenInput()

        # Filter role choices based on current user's role
        if is_app_owner_or_superuser:
            form.base_fields['role'].queryset = Role.objects.all()
            print("ManagerUserAdmin: All roles visible for App Owner/Superuser.")
        elif current_user.is_store_manager_user():
            form.base_fields['role'].queryset = Role.objects.filter(
                role_name__in=[
                    UserType.BRANCH_MANAGER.value, UserType.GENERAL_STAFF.value,
                    UserType.CASHIER.value, UserType.SHELF_ORGANIZER.value,
                    UserType.CUSTOMER_SERVICE.value, UserType.PLATFORM_CUSTOMER.value
                ]
            )
            print(f"ManagerUserAdmin: Filtering roles for Store Manager: {form.base_fields['role'].queryset.values_list('role_name', flat=True)}")
        elif current_user.is_branch_manager_user():
            form.base_fields['role'].queryset = Role.objects.filter(
                role_name__in=[
                    UserType.GENERAL_STAFF.value, UserType.CASHIER.value,
                    UserType.SHELF_ORGANIZER.value, UserType.CUSTOMER_SERVICE.value,
                    UserType.PLATFORM_CUSTOMER.value
                ]
            )
            print(f"ManagerUserAdmin: Filtering roles for Branch Manager: {form.base_fields['role'].queryset.values_list('role_name', flat=True)}")
        else:
            # If the current user's role doesn't grant permission to create/manage other roles,
            # or if their role is not staff-related, they should not see role options.
            # However, if their own role is not set, they should still see it.
            if obj and obj.pk and obj.role:
                # If editing an existing user, and their role is already set, show only that role
                form.base_fields['role'].queryset = Role.objects.filter(pk=obj.role.pk)
                form.base_fields['role'].widget.attrs['disabled'] = 'disabled'
                print(f"ManagerUserAdmin: Only current user's role '{obj.role.role_name}' visible and disabled.")
            else:
                # For new users or users without a role, and not an admin, no roles are selectable
                form.base_fields['role'].queryset = Role.objects.none()
                print(f"ManagerUserAdmin: No roles visible for current user type or new user without admin privileges.")
                
        # Handle Store, Branch, Department fields
        user_store_from_profile = None
        user_branch_from_profile = None
        if hasattr(current_user, 'employee_profile') and current_user.employee_profile:
            user_store_from_profile = current_user.employee_profile.store
            user_branch_from_profile = current_user.employee_profile.branch

        if current_user.is_store_manager_user() and user_store_from_profile:
            form.base_fields['store'].initial = user_store_from_profile
            form.base_fields['store'].widget = forms.HiddenInput()
            form.base_fields['store'].required = False
            form.base_fields['branch'].queryset = Branch.objects.filter(store=user_store_from_profile)
            form.base_fields['department'].queryset = Department.objects.filter(branch__store=user_store_from_profile)
            print(f"ManagerUserAdmin: Store manager ({user_store_from_profile.name}), pre-filling store, filtering branch/dept.")
        elif current_user.is_branch_manager_user() and user_branch_from_profile:
            form.base_fields['store'].initial = user_branch_from_profile.store
            form.base_fields['store'].widget = forms.HiddenInput()
            form.base_fields['store'].required = False
            form.base_fields['branch'].initial = user_branch_from_profile
            form.base_fields['branch'].widget = forms.HiddenInput()
            form.base_fields['branch'].required = False
            form.base_fields['department'].queryset = Department.objects.filter(branch=user_branch_from_profile)
            print(f"ManagerUserAdmin: Branch manager ({user_branch_from_profile.name}), pre-filling store/branch, filtering dept.")
        elif not is_app_owner_or_superuser: # For other non-admin roles, hide these fields
            form.base_fields['store'].widget = forms.HiddenInput()
            form.base_fields['store'].required = False
            form.base_fields['branch'].widget = forms.HiddenInput()
            form.base_fields['branch'].required = False
            form.base_fields['department'].widget = forms.HiddenInput()
            form.base_fields['department'].required = False
            print("ManagerUserAdmin: Non-admin user, hiding store/branch/department fields.")
        
        print(f"--- End ManagerUserAdmin get_form Debug ---\n")
        return form

    # Override save_model to automatically set the store for the new user AND create/update Employee profile
    def save_model(self, request, obj, form, change):
        is_new_user = not change
        
        # Determine the creator of the new user
        if not change and not obj.created_by:
            obj.created_by = request.user

        # If the user is a Store Manager or Branch Manager, auto-assign store/branch to the new user's profile
        current_user_store = None
        current_user_branch = None
        if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
            current_user_store = request.user.employee_profile.store
            current_user_branch = request.user.employee_profile.branch

        # These fields are on the UserAccountAdminForm, and their values are passed through form.cleaned_data
        # The form's clean method already handles setting these for non-superuser/app-owner users.
        # So we just retrieve them from cleaned_data.
        store_from_form = form.cleaned_data.get('store')
        branch_from_form = form.cleaned_data.get('branch')
        department_from_form = form.cleaned_data.get('department')

        # If no username is provided manually, generate one.
        if not obj.username:
            base_username = obj.email.split('@')[0] if obj.email else "newuser"
            username_candidate = base_username
            counter = 0
            while UserAccount.objects.filter(username=username_candidate).exists():
                counter += 1
                username_candidate = f"{base_username}_{counter}"
            obj.username = username_candidate

        super().save_model(request, obj, form, change) # Save the UserAccount instance first
        obj.refresh_from_db() # Ensure obj has the latest data after super().save_model

        # Now handle the Employee/Customer profile creation/update based on the role
        role_name = obj.role.role_name if obj.role else None

        if role_name in [UserType.STORE_MANAGER.value, UserType.BRANCH_MANAGER.value, UserType.GENERAL_STAFF.value, UserType.CASHIER.value, UserType.SHELF_ORGANIZER.value, UserType.CUSTOMER_SERVICE.value]:
            employee_profile, created = Employee.objects.get_or_create(user_account=obj)
            employee_profile.store = store_from_form
            employee_profile.branch = branch_from_form
            employee_profile.department = department_from_form
            # Update other employee fields if they were on the form
            employee_profile.phone_number = form.cleaned_data.get('phone_number', employee_profile.phone_number)
            employee_profile.tax_id = form.cleaned_data.get('tax_id', employee_profile.tax_id)
            employee_profile.job_title = form.cleaned_data.get('job_title', employee_profile.job_title)
            employee_profile.save()
            # Ensure no customer profile exists for this user
            Customer.objects.filter(user_account=obj).delete()
        elif role_name == UserType.PLATFORM_CUSTOMER.value:
            customer_profile, created = Customer.objects.get_or_create(user_account=obj)
            customer_profile.store = store_from_form # Customers can have a preferred store
            # Update other customer fields if they were on the form
            customer_profile.phone_number = form.cleaned_data.get('phone_number', customer_profile.phone_number)
            customer_profile.save()
            # Ensure no employee profile exists for this user
            Employee.objects.filter(user_account=obj).delete()
        elif role_name == UserType.STORE_ACCOUNT.value:
            # If it's a STORE_ACCOUNT, ensure it manages the selected store
            if store_from_form:
                obj.managed_store = store_from_form
                obj.save(update_fields=['managed_store'])
            Employee.objects.filter(user_account=obj).delete()
            Customer.objects.filter(user_account=obj).delete()
        else:
            # For roles like App Owner, Project Manager, App Staff, delete profiles if they exist
            Employee.objects.filter(user_account=obj).delete()
            Customer.objects.filter(user_account=obj).delete()
            # Also clear managed_store if it's not a STORE_ACCOUNT
            if hasattr(obj, 'managed_store') and obj.managed_store:
                obj.managed_store = None
                obj.save(update_fields=['managed_store'])


        # Display password message for new users
        if is_new_user and obj.is_temporary_password:
            messages.success(request, format_html(
                "<strong>تم إنشاء حساب المستخدم '{}' بنجاح.</strong><br>"
                "<strong>البريد الإلكتروني:</strong> {}<br>"
                "<strong>اسم المستخدم:</strong> {}<br>"
                "<strong>كلمة المرور المؤقتة (انسخها الآن):</strong> <code style='font-weight: bold; background-color: #e0ffe0; padding: 5px; border-radius: 3px;'>{}</code><br>"
                "يرجى تقديم هذه المعلومات للمستخدم ونصحه بتغييرها فوراً.<br>"
                "<strong>Firebase UID:</strong> {}",
                obj.get_full_name() or obj.username,
                obj.email, obj.username, obj._temporary_password, obj.firebase_uid # Access temp password
            ))
        elif change and form.cleaned_data.get('password'):
             messages.success(request, format_html(
                "<strong>تم تحديث كلمة المرور المؤقتة للمستخدم '{}' بنجاح.</strong><br>"
                "<strong>البريد الإلكتروني:</strong> {}<br>"
                "<strong>كلمة المرور المؤقتة الجديدة (انسخها الآن):</strong> <code style='font-weight: bold; background-color: #e0ffe0; padding: 5px; border-radius: 3px;'>{}</code><br>"
                "يرجى تزويد المستخدم بها ونصحه بتغييرها فوراً.",
                obj.get_full_name() or obj.username,
                obj.email, form.cleaned_data.get('password')
            ))
        elif is_new_user: # Fallback if password wasn't captured for some reason
            messages.info(request, _(f"تم إنشاء المستخدم '{obj.username}' بنجاح. يرجى إبلاغ المستخدم بكلمة المرور أو توجيهه لإعادة تعيينها."))
        elif change:
            messages.success(request, _(f"تم تحديث المستخدم '{obj.username}' بنجاح."))


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        print(f"\n--- ManagerUserAdmin get_queryset Debug for user: {request.user.email} (Is Superuser: {request.user.is_superuser}) ---")

        # Start with a base queryset that always includes the current user
        # This ensures the current user can always see their own account, preventing empty lists.
        base_qs = qs.filter(pk=request.user.pk)

        # Allow superusers and App Owners/Project Managers to see all user accounts
        if request.user.is_superuser or \
           (hasattr(request.user, 'role') and request.user.role and request.user.role.role_name in [UserType.APP_OWNER.value, UserType.PROJECT_MANAGER.value]):
            print("User is Superuser/App Owner/Project Manager, returning all users.")
            return qs # Return all users, not just base_qs, as they have full access

        # Determine the user's associated store based on their role and available profiles
        user_store = None
        current_user_role_name = request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else None

        if current_user_role_name == UserType.STORE_ACCOUNT.value and hasattr(request.user, 'managed_store') and request.user.managed_store:
            user_store = request.user.managed_store
        elif hasattr(request.user, 'employee_profile') and request.user.employee_profile and request.user.employee_profile.store:
            user_store = request.user.employee_profile.store
        elif hasattr(request.user, 'customer_profile') and request.user.customer_profile and request.user.customer_profile.store:
            user_store = request.user.customer_profile.store

        # If the user is a Store Account or Store Manager
        if current_user_role_name in [UserType.STORE_ACCOUNT.value, UserType.STORE_MANAGER.value]:
            if user_store:
                # Combine base_qs with users related to the store
                filtered_qs = qs.filter(
                    Q(employee_profile__store=user_store) |
                    Q(customer_profile__store=user_store) |
                    Q(pk=user_store.store_account.pk if hasattr(user_store, 'store_account') else None) # Include the store's own account if it's a STORE_ACCOUNT
                ).exclude(
                    role__role_name__in=[UserType.APP_OWNER.value, UserType.PROJECT_MANAGER.value, UserType.APP_STAFF.value]
                )
                final_qs = (base_qs | filtered_qs).distinct()
                print(f"User is Store Account/Manager ({user_store.name}), filtering by store. Count: {final_qs.count()}")
                return final_qs
            else:
                # If store manager/account has no associated store, they only see themselves
                print("User is Store Account/Manager but no associated store found, returning only themselves.")
                return base_qs

        # For Branch Managers
        if current_user_role_name == UserType.BRANCH_MANAGER.value:
            user_branch = request.user.employee_profile.branch if hasattr(request.user, 'employee_profile') and request.user.employee_profile else None
            user_store_for_customers = user_branch.store if user_branch else None
            
            if user_branch:
                filtered_qs = qs.filter(
                    Q(employee_profile__branch=user_branch) |
                    Q(customer_profile__store=user_store_for_customers)
                ).exclude(
                    role__role_name__in=[
                        UserType.APP_OWNER.value, UserType.PROJECT_MANAGER.value, UserType.APP_STAFF.value,
                        UserType.STORE_ACCOUNT.value, UserType.STORE_MANAGER.value, UserType.BRANCH_MANAGER.value
                    ]
                )
                final_qs = (base_qs | filtered_qs).distinct()
                print(f"User is Branch Manager ({user_branch.name}), filtering by branch/store. Count: {final_qs.count()}")
                return final_qs
            else:
                # If branch manager has no associated branch, they only see themselves
                print("User is Branch Manager but no associated branch found, returning only themselves.")
                return base_qs

        # For all other roles (General Staff, Cashiers, etc.), only allow them to see themselves
        print(f"User is General Staff/Customer etc., only seeing themselves. Count: {base_qs.count()}")
        return base_qs


# تسجيل النماذج في لوحة الإدارة الخاصة بمدراء المتاجر
store_manager_panel.register(Branch, BranchAdmin)
store_manager_panel.register(UserAccount, ManagerUserAdmin)
store_manager_panel.register(Product)
store_manager_panel.register(Department)
store_manager_panel.register(ProductCategory)
store_manager_panel.register(BranchProductInventory)
store_manager_panel.register(Order)
store_manager_panel.register(OrderItem)
store_manager_panel.register(TempOrder)
store_manager_panel.register(TempOrderItem)
store_manager_panel.register(AccountingSystemConfig)
store_manager_panel.register(ProductSyncLog)
store_manager_panel.register(SaleInvoiceSyncLog)
store_manager_panel.register(ZatcaInvoice)
