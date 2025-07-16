# C:\Users\DELL\SER SQL MY APP\users\admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.contrib import messages
from django.utils.html import format_html
from django.urls import path
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.http import Http404
from django import forms

# استيراد النماذج
from .models import UserAccount, Role, generate_temporary_password, Customer, Employee, UserType

# استيراد نموذج Department و Store و Branch
from products.models import Department
from stores.models import Store, Branch

# استيراد النماذج المخصصة من ملف forms.py
from .forms import CustomUserCreationForm, CustomUserChangeForm

# استيراد Firebase Admin SDK
import firebase_admin
from firebase_admin import auth, exceptions as firebase_exceptions
import logging
from django.db import transaction

logger = logging.getLogger(__name__)

# --- Role Admin ---
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('role_name', 'description', 'is_staff_role')
    search_fields = ('role_name', 'description')
    list_filter = ('is_staff_role',)
    ordering = ('role_name',)

    fieldsets = (
        (None, {'fields': ('role_name', 'description', 'is_staff_role')}),
    )

# --- UserAccount Admin Form ---
class UserAccountAdminForm(CustomUserChangeForm):
    store = forms.ModelChoiceField(queryset=Store.objects.all(), required=False, label=_("Store"))
    branch = forms.ModelChoiceField(queryset=Branch.objects.all(), required=False, label=_("Branch"))
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=False, label=_("Department"))

    class Meta(CustomUserChangeForm.Meta):
        model = UserAccount
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        current_user = self.request.user if self.request else None
        
        print(f"\n--- UserAccountAdminForm __init__ Debug ---")
        if current_user and current_user.is_authenticated:
            current_user_role_name = current_user.role.role_name if hasattr(current_user, 'role') and current_user.role else 'N/A'
            print(f"Current User: {current_user.email}, Is Superuser: {current_user.is_superuser}, Role: {current_user_role_name}")
            
            current_user_profile_store = None
            current_user_profile_branch = None
            if hasattr(current_user, 'employee_profile') and current_user.employee_profile:
                current_user_profile_store = current_user.employee_profile.store
                current_user_profile_branch = current_user.employee_profile.branch

            print(f"Current User Profile Store: {current_user_profile_store.name if current_user_profile_store else 'None'}")
            print(f"Current User Profile Branch: {current_user_profile_branch.name if current_user_profile_branch else 'None'}")
        else:
            print("No authenticated user in request or current_user is None.")
            
        # Initializing form fields for an existing object
        if self.instance and self.instance.pk:
            print(f"Editing existing user: {self.instance.email}")
            if hasattr(self.instance, 'employee_profile') and self.instance.employee_profile:
                self.fields['store'].initial = self.instance.employee_profile.store
                self.fields['branch'].initial = self.instance.employee_profile.branch
                self.fields['department'].initial = self.instance.employee_profile.department
                print(f"  Initial values from employee_profile: Store={self.instance.employee_profile.store}, Branch={self.instance.employee_profile.branch}, Dept={self.instance.employee_profile.department}")
            elif hasattr(self.instance, 'customer_profile') and self.instance.customer_profile:
                self.fields['store'].initial = self.instance.customer_profile.store
                print(f"  Initial value from customer_profile: Store={self.instance.customer_profile.store}")
            elif hasattr(self.instance, 'managed_store') and self.instance.managed_store:
                self.fields['store'].initial = self.instance.managed_store
                print(f"  Initial value from managed_store: Store={self.instance.managed_store}")
        
        # Filtering querysets and hiding fields based on current user's role
        if current_user and current_user.is_authenticated:
            is_app_owner_or_superuser = current_user.is_app_owner() or current_user.is_superuser
            
            # Filtering role choices based on current user's role
            # IMPORTANT: Ensure App Owner/Superuser always sees all roles
            if is_app_owner_or_superuser:
                self.fields['role'].queryset = Role.objects.all()
                print("All roles visible for App Owner/Superuser.")
            elif current_user.is_store_manager_user():
                self.fields['role'].queryset = Role.objects.filter(
                    role_name__in=[UserType.BRANCH_MANAGER.value, UserType.GENERAL_STAFF.value, UserType.CASHIER.value, UserType.SHELF_ORGANIZER.value, UserType.CUSTOMER_SERVICE.value, UserType.PLATFORM_CUSTOMER.value]
                )
                print(f"Filtering roles for Store Manager: {self.fields['role'].queryset.values_list('role_name', flat=True)}")
            elif current_user.is_branch_manager_user():
                self.fields['role'].queryset = Role.objects.filter(
                    role_name__in=[UserType.GENERAL_STAFF.value, UserType.CASHIER.value, UserType.SHELF_ORGANIZER.value, UserType.CUSTOMER_SERVICE.value, UserType.PLATFORM_CUSTOMER.value]
                )
                print(f"Filtering roles for Branch Manager: {self.fields['role'].queryset.values_list('role_name', flat=True)}")
            else:
                # If the current user's role doesn't grant permission to create/manage other roles,
                # or if their role is not staff-related, they should not see role options.
                # However, if their own role is not set, they should still see it.
                if self.instance and self.instance.pk and self.instance.role:
                    # If editing an existing user, and their role is already set, show only that role
                    self.fields['role'].queryset = Role.objects.filter(pk=self.instance.role.pk)
                    self.fields['role'].widget.attrs['disabled'] = 'disabled'
                    print(f"Only current user's role '{self.instance.role.role_name}' visible and disabled.")
                else:
                    # For new users or users without a role, and not an admin, no roles are selectable
                    self.fields['role'].queryset = Role.objects.none()
                    print(f"No roles visible for current user type or new user without admin privileges.")
                    
            # Handle Store, Branch, Department field visibility and querysets
            if (hasattr(current_user, 'role') and current_user.role and current_user.role.role_name == UserType.STORE_ACCOUNT.value) or current_user.is_store_manager_user():
                user_store = current_user_profile_store or (hasattr(current_user, 'managed_store') and current_user.managed_store)
                if user_store:
                    self.fields['store'].initial = user_store
                    self.fields['store'].widget = forms.HiddenInput()
                    self.fields['store'].required = False
                    self.fields['branch'].queryset = Branch.objects.filter(store=user_store)
                    self.fields['department'].queryset = Department.objects.filter(branch__store=user_store)
                    print(f"Filtering branches and departments for Store user: {user_store.name}")
                else:
                    # If store account/manager has no store, hide these fields
                    self.fields['store'].widget = forms.HiddenInput()
                    self.fields['store'].required = False
                    self.fields['branch'].widget = forms.HiddenInput()
                    self.fields['branch'].required = False
                    self.fields['department'].widget = forms.HiddenInput()
                    self.fields['department'].required = False
                    print("Store Account/Manager without associated store, hiding store/branch/department fields.")

            elif current_user.is_branch_manager_user():
                user_branch = current_user_profile_branch
                if user_branch:
                    user_store = user_branch.store
                    self.fields['store'].initial = user_store
                    self.fields['store'].widget = forms.HiddenInput()
                    self.fields['store'].required = False
                    self.fields['branch'].initial = user_branch
                    self.fields['branch'].widget = forms.HiddenInput()
                    self.fields['branch'].required = False
                    self.fields['department'].queryset = Department.objects.filter(branch=user_branch)
                    print(f"Filtering departments for Branch user: {user_branch.name}")
                else:
                    # If branch manager has no branch, hide these fields
                    self.fields['store'].widget = forms.HiddenInput()
                    self.fields['store'].required = False
                    self.fields['branch'].widget = forms.HiddenInput()
                    self.fields['branch'].required = False
                    self.fields['department'].widget = forms.HiddenInput()
                    self.fields['department'].required = False
                    print("Branch Manager without associated branch, hiding store/branch/department fields.")
            
            # Hide department field for roles that don't need it
            is_department_visible_role = is_app_owner_or_superuser or current_user.is_project_manager()
            if not is_department_visible_role:
                self.fields['department'].widget = forms.HiddenInput()
                self.fields['department'].required = False
                print("Hiding department field as user is not App Owner/Superuser/Project Manager.")
            
        else: # No authenticated user
            self.fields['store'].widget = forms.HiddenInput()
            self.fields['store'].required = False
            self.fields['branch'].widget = forms.HiddenInput()
            self.fields['branch'].required = False
            self.fields['department'].widget = forms.HiddenInput()
            self.fields['department'].required = False
            self.fields['role'].queryset = Role.objects.none()
            print("No authenticated user, form fields and role queryset are empty/hidden.")

        print(f"--- End UserAccountAdminForm __init__ Debug ---\n")

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        store = cleaned_data.get('store')
        branch = cleaned_data.get('branch')
        department = cleaned_data.get('department')
        
        # Auto-set store/branch based on the creating user's context
        current_user = self.request.user if self.request else None
        if current_user and current_user.is_authenticated:
            is_app_owner_or_superuser = current_user.is_app_owner() or current_user.is_superuser
            if not is_app_owner_or_superuser:
                if hasattr(current_user, 'employee_profile') and current_user.employee_profile:
                    # If current user is a staff member, auto-assign their store/branch
                    if not cleaned_data.get('store'): # Only set if not already set by user (e.g., for App Owner)
                        cleaned_data['store'] = current_user.employee_profile.store
                        print(f"Clean: Auto-setting store to {current_user.employee_profile.store.name} from creator.")
                    if not cleaned_data.get('branch'): # Only set if not already set by user
                        cleaned_data['branch'] = current_user.employee_profile.branch
                        print(f"Clean: Auto-setting branch to {current_user.employee_profile.branch.name if current_user.employee_profile.branch else 'None'}.")
            
            # Ensure proper associations for non-app-owner/superuser roles
            if role:
                if role.role_name in [UserType.STORE_MANAGER.value, UserType.BRANCH_MANAGER.value, UserType.GENERAL_STAFF.value, UserType.CASHIER.value, UserType.SHELF_ORGANIZER.value, UserType.CUSTOMER_SERVICE.value]:
                    if not cleaned_data.get('store'):
                        self.add_error('store', _("يجب تحديد متجر لهذا الدور."))
                
                if role.role_name == UserType.BRANCH_MANAGER.value:
                    if not cleaned_data.get('branch'):
                        self.add_error('branch', _("يجب تحديد فرع لهذا الدور."))
                    if cleaned_data.get('department'):
                        self.add_error('department', _("لا يمكن تعيين قسم لمدير الفرع."))
                
                if role.role_name in [UserType.GENERAL_STAFF.value, UserType.CASHIER.value, UserType.SHELF_ORGANIZER.value, UserType.CUSTOMER_SERVICE.value]:
                    if not cleaned_data.get('branch'):
                        self.add_error('branch', _("يجب تحديد فرع لهذا الدور."))
                
                if role.role_name == UserType.PLATFORM_CUSTOMER.value:
                    # Customer accounts are not necessarily linked to a store upon creation
                    pass # Keep store/branch/department fields as optional
                
                if role.role_name in [UserType.APP_OWNER.value, UserType.PROJECT_MANAGER.value, UserType.APP_STAFF.value, UserType.STORE_ACCOUNT.value]:
                    # For these roles, store/branch/department should generally not be set,
                    # unless it's a STORE_ACCOUNT explicitly managing a store.
                    # We will handle the managed_store field directly in save_model for STORE_ACCOUNT.
                    pass 

        return cleaned_data


# --- UserAccount Admin ---
@admin.register(UserAccount)
class UserAccountAdmin(BaseUserAdmin):
    form = UserAccountAdminForm
    add_form = CustomUserCreationForm

    list_display = (
        'email',
        'username',
        'get_role_display',
        'is_staff',
        'is_active',
        'date_joined',
        'get_associated_store',
        'get_associated_branch',
        'is_temporary_password',
        'reset_password_action'
    )

    # تم تعديل readonly_fields هنا
    readonly_fields = ('date_joined', 'last_login', 'firebase_uid', 'is_temporary_password')

    fieldsets = (
        (None, {'fields': ('email', 'username', 'firebase_uid')}),
        (_('Personal Info & Contact'), {'fields': ('first_name', 'last_name', 'phone_number', 'tax_id', 'job_title')}),
        (_('Role & Association'), {'fields': ('role', 'store', 'branch', 'department')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions', 'is_temporary_password')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password', 'password2')
        }),
        (_('Personal Info & Contact'), {'fields': ('first_name', 'last_name', 'phone_number', 'tax_id', 'job_title')}),
        (_('Role & Association'), {'fields': ('role', 'store', 'branch', 'department')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )

    search_fields = (
        'email',
        'username',
        'role__role_name',
        'employee_profile__phone_number',
        'employee_profile__tax_id',
        'employee_profile__store__name',
        'employee_profile__branch__name',
        'employee_profile__department__name'
    )
    list_filter = (
        'role__role_name',
        'is_staff',
        'is_active',
        'employee_profile__store',
        'employee_profile__branch',
        'employee_profile__department'
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.request = request
        if request.user.is_authenticated:
            request_user_role_name = request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else None

            if not (request.user.is_superuser or request_user_role_name == UserType.APP_OWNER.value):
                for field_name in ['is_staff', 'is_superuser', 'groups', 'user_permissions']:
                    if field_name in form.base_fields:
                        form.base_fields[field_name].widget.attrs['disabled'] = 'disabled'
                        form.base_fields[field_name].help_text = _("You do not have permission to modify this field.")

            if obj and request.user.pk == obj.pk and request_user_role_name == UserType.APP_OWNER.value:
                for field_name in ['is_staff', 'is_superuser', 'groups', 'user_permissions']:
                    if field_name in form.base_fields:
                        if 'disabled' in form.base_fields[field_name].widget.attrs:
                            del form.base_fields[field_name].widget.attrs['disabled']
                        form.base_fields[field_name].help_text = _("As an App Owner, you can modify this field.")

        return form

    def get_fieldsets(self, request, obj=None):
        fieldsets_to_display = super().get_fieldsets(request, obj)
        current_user = request.user
        request_user_role_name = current_user.role.role_name if hasattr(current_user, 'role') and current_user.role else None

        is_app_owner_or_superuser = current_user.is_app_owner() or current_user.is_superuser
        
        mutable_fieldsets = [list(fs) for fs in fieldsets_to_display]

        for i, (name, opts) in enumerate(mutable_fieldsets):
            if name == _('Role & Association'):
                current_fields = list(opts['fields'])
                mutable_fieldsets[i] = (name, {'fields': tuple(current_fields)})
                break
            elif name == _('Permissions'):
                current_fields = list(opts['fields'])
                if not (request.user.is_superuser or request_user_role_name == UserType.APP_OWNER.value):
                    current_fields_copy = current_fields[:]
                    if 'groups' in current_fields_copy: current_fields_copy.remove('groups')
                    if 'user_permissions' in current_fields_copy: current_fields_copy.remove('user_permissions')
                    current_fields = current_fields_copy

                if obj and request.user.pk == obj.pk and request_user_role_name == UserType.APP_OWNER.value:
                    pass
                elif request_user_role_name != UserType.APP_OWNER.value and obj and obj.role and obj.role.role_name == UserType.APP_OWNER.value:
                    current_fields_copy = current_fields[:]
                    if 'is_staff' in current_fields_copy: current_fields_copy.remove('is_staff')
                    if 'is_superuser' in current_fields_copy: current_fields_copy.remove('is_superuser')
                    current_fields = current_fields_copy
            
                mutable_fieldsets[i] = (name, {'fields': tuple(current_fields)})
                break

        return [tuple(fs) for fs in mutable_fieldsets]

    def get_add_fieldsets(self, request):
        add_fieldsets_to_display = super().get_add_fieldsets(request)
        current_user = request.user
        request_user_role_name = current_user.role.role_name if hasattr(current_user, 'role') and current_user.role else None

        is_app_owner_or_superuser = current_user.is_app_owner() or current_user.is_superuser
        
        mutable_add_fieldsets = [list(fs) for fs in add_fieldsets_to_display]

        for i, (name, opts) in enumerate(mutable_add_fieldsets):
            if name == _('Role & Association'):
                current_fields = list(opts['fields'])
                mutable_add_fieldsets[i] = (name, {'fields': tuple(current_fields)})
                break
            elif name == _('Permissions'):
                current_fields = list(opts['fields'])
                if not (request.user.is_superuser or request_user_role_name == UserType.APP_OWNER.value):
                    current_fields_copy = current_fields[:]
                    if 'is_staff' in current_fields_copy: current_fields_copy.remove('is_staff')
                    if 'is_superuser' in current_fields_copy: current_fields_copy.remove('is_superuser')
                    current_fields = current_fields_copy
                mutable_add_fieldsets[i] = (name, {'fields': tuple(current_fields)})
                break

        return [tuple(fs) for fs in mutable_add_fieldsets]

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        request_user_role_name = request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else None
        
        # Determine the creator of the new user
        if not change and not obj.created_by:
            obj.created_by = request.user
            print(f"UserAccountAdmin save_model: Auto-setting created_by to {request.user.email}")

        # Handle permissions
        if not (request.user.is_superuser or request_user_role_name == UserType.APP_OWNER.value):
            if 'is_staff' in form.cleaned_data:
                del form.cleaned_data['is_staff']
            if 'is_superuser' in form.cleaned_data:
                del form.cleaned_data['is_superuser']
            if 'groups' in form.cleaned_data:
                del form.cleaned_data['groups']
            if 'user_permissions' in form.cleaned_data:
                del form.cleaned_data['user_permissions']
        elif request.user.pk == obj.pk and request_user_role_name == UserType.APP_OWNER.value:
            obj.is_staff = form.cleaned_data.get('is_staff', obj.is_staff)
            obj.is_superuser = form.cleaned_data.get('is_superuser', obj.is_superuser)

        is_new_user = not change
        captured_password = None

        if is_new_user:
            new_temp_password = form.cleaned_data.get('password')
            if not new_temp_password:
                new_temp_password = generate_temporary_password()
                obj.is_temporary_password = True
            obj.set_password(new_temp_password)
            captured_password = new_temp_password
        elif change and form.cleaned_data.get('password'):
            new_password = form.cleaned_data['password']
            obj.set_password(new_password)
            obj.is_temporary_password = False
            captured_password = new_password
            messages.info(request, _("تم تحديث كلمة مرور المستخدم في Django."))
            
        super().save_model(request, obj, form, change)
        obj.refresh_from_db()

        # Update Firebase after Django save
        if not obj.firebase_uid:
            try:
                firebase_password_to_use = captured_password if captured_password else generate_temporary_password()
                if not obj.email:
                    raise ValueError(_("Email is required to create a Firebase user."))
                firebase_user = auth.create_user(
                    email=obj.email, password=firebase_password_to_use, display_name=obj.get_full_name() or obj.username, disabled=not obj.is_active
                )
                obj.firebase_uid = firebase_user.uid
                obj.is_temporary_password = True
                obj.save(update_fields=['firebase_uid', 'is_temporary_password'])
                logger.info(f"Firebase user created: {obj.email} with UID: {obj.firebase_uid}")
            except Exception as e:
                logger.error(f"Firebase creation error for {obj.email}: {e}", exc_info=True)
                messages.error(request, format_html(_("خطأ في Firebase عند إنشاء المستخدم: {}"), str(e)))
                raise
        elif change and obj.firebase_uid:
            try:
                update_data = {'email': obj.email, 'display_name': obj.get_full_name() or obj.username, 'disabled': not obj.is_active}
                if captured_password:
                    update_data['password'] = captured_password
                auth.update_user(obj.firebase_uid, **update_data)
                logger.info(f"Firebase user updated: {obj.email} with UID: {obj.firebase_uid}")
            except Exception as e:
                logger.error(f"Firebase update error for {obj.email}: {e}", exc_info=True)
                messages.error(request, format_html(_("خطأ في Firebase عند تحديث المستخدم: {}"), str(e)))
        
        # Handle profiles (Employee/Customer)
        role = obj.role.role_name if obj.role else None
        store = form.cleaned_data.get('store')
        branch = form.cleaned_data.get('branch')
        department = form.cleaned_data.get('department')
        
        # Auto-fill store/branch for employees/customers based on the creating user's context
        current_user = request.user
        is_creating_user_staff = hasattr(current_user, 'employee_profile') and current_user.employee_profile
        is_app_owner_or_superuser = current_user.is_app_owner() or current_user.is_superuser
        
        if is_creating_user_staff and not is_app_owner_or_superuser:
            # For new users created by staff, auto-link to the staff's store/branch
            if not store:
                store = current_user.employee_profile.store
                print(f"Save Model: Auto-setting new user's store to {store.name} from creator.")
            if not branch:
                branch = current_user.employee_profile.branch
                print(f"Save Model: Auto-setting new user's branch to {branch.name} from creator.")
        
        # Create/Update Employee or Customer profile based on the user's role
        if role in [UserType.STORE_MANAGER.value, UserType.BRANCH_MANAGER.value, UserType.GENERAL_STAFF.value, UserType.CASHIER.value, UserType.SHELF_ORGANIZER.value, UserType.CUSTOMER_SERVICE.value]:
            employee_profile, created = Employee.objects.get_or_create(user_account=obj)
            employee_profile.store = store
            employee_profile.branch = branch
            employee_profile.department = department
            employee_profile.phone_number = form.cleaned_data.get('phone_number')
            employee_profile.tax_id = form.cleaned_data.get('tax_id')
            employee_profile.job_title = form.cleaned_data.get('job_title')
            employee_profile.save()
            Customer.objects.filter(user_account=obj).delete() # Ensure no customer profile exists
        elif role == UserType.PLATFORM_CUSTOMER.value:
            customer_profile, created = Customer.objects.get_or_create(user_account=obj)
            customer_profile.phone_number = form.cleaned_data.get('phone_number')
            customer_profile.store = store
            customer_profile.save()
            Employee.objects.filter(user_account=obj).delete() # Ensure no employee profile exists
        elif role == UserType.STORE_ACCOUNT.value:
            # If it's a STORE_ACCOUNT, ensure it manages the selected store
            if store:
                obj.managed_store = store
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


        # Display success messages with passwords
        if is_new_user and captured_password:
            messages.success(request, format_html(
                "<strong>تم إنشاء حساب المستخدم '{}' بنجاح.</strong><br>"
                "<strong>البريد الإلكتروني:</strong> {}<br>"
                "<strong>اسم المستخدم:</strong> {}<br>"
                "<strong>كلمة المرور المؤقتة (انسخها الآن):</strong> <code style='font-weight: bold; background-color: #e0ffe0; padding: 5px; border-radius: 3px;'>{}</code><br>"
                "يرجى تقديم هذه المعلومات للمستخدم ونصحه بتغييرها فوراً.<br>"
                "<strong>Firebase UID:</strong> {}",
                obj.get_full_name() or obj.username,
                obj.email, obj.username, captured_password, obj.firebase_uid
            ))
            logger.info(f"Success message ADDED for new user with password.")
        elif change and captured_password:
             messages.success(request, format_html(
                "<strong>تم تحديث كلمة المرور المؤقتة للمستخدم '{}' بنجاح.</strong><br>"
                "<strong>البريد الإلكتروني:</strong> {}<br>"
                "<strong>كلمة المرور المؤقتة الجديدة (انسخها الآن):</strong> <code style='font-weight: bold; background-color: #e0ffe0; padding: 5px; border-radius: 3px;'>{}</code><br>"
                "يرجى تزويد المستخدم بها ونصحه بتغييرها فوراً.",
                obj.get_full_name() or obj.username,
                obj.email, captured_password
            ))
        elif is_new_user:
            messages.info(request, _(f"تم إنشاء المستخدم '{obj.username}' بنجاح. يرجى إبلاغ المستخدم بكلمة المرور أو توجيهه لإعادة تعيينها."))
        elif change:
            messages.success(request, _(f"تم تحديث المستخدم '{obj.username}' بنجاح."))

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        print(f"\n--- get_queryset Debug for user: {request.user.email} (Is Superuser: {request.user.is_superuser}) ---")

        # Start with a base queryset that always includes the current user
        # This ensures the current user can always see their own account, preventing empty lists.
        base_qs = qs.filter(pk=request.user.pk)

        # Allow superusers and App Owners to see all user accounts
        if request.user.is_superuser or (hasattr(request.user, 'role') and request.user.role and request.user.role.role_name == UserType.APP_OWNER.value):
            print("User is Superuser or App Owner, returning all users.")
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

        # For Project Managers and App Staff, exclude App Owners
        if current_user_role_name in [UserType.PROJECT_MANAGER.value, UserType.APP_STAFF.value]:
            filtered_qs = qs.exclude(role__role_name=UserType.APP_OWNER.value)
            final_qs = (base_qs | filtered_qs).distinct()
            print(f"User is Project Manager/App Staff, excluding App Owners. Count: {final_qs.count()}")
            return final_qs

        # For all other roles (General Staff, Cashiers, etc.), only allow them to see themselves
        print(f"User is General Staff/Customer etc., only seeing themselves. Count: {base_qs.count()}")
        return base_qs # Already filtered to only include themselves

    def get_associated_store(self, obj):
        # Check if it's a STORE_ACCOUNT directly managing a store
        if hasattr(obj, 'role') and obj.role and obj.role.role_name == UserType.STORE_ACCOUNT.value and hasattr(obj, 'managed_store') and obj.managed_store:
            return obj.managed_store.name
        # Check if it's an employee linked to a store
        if hasattr(obj, 'employee_profile') and obj.employee_profile and obj.employee_profile.store:
            return obj.employee_profile.store.name
        # Check if it's a customer linked to a store
        if hasattr(obj, 'customer_profile') and obj.customer_profile and obj.customer_profile.store:
            return obj.customer_profile.store.name
        return None
    get_associated_store.short_description = _("Store")

    def get_associated_branch(self, obj):
        if hasattr(obj, 'employee_profile') and obj.employee_profile and obj.employee_profile.branch:
            return obj.employee_profile.branch.name
        return None
    get_associated_branch.short_description = _("Branch")
    
    def get_role_display(self, obj):
        return obj.role.role_name if obj.role else _("N/A")
    get_role_display.short_description = _("Role")

    def reset_password_action(self, obj):
        return format_html(
            '<a class="button" href="{}">{}</a>',
            f"/admin/users/useraccount/{obj.user_id}/reset_password/",
            _("إعادة تعيين وعرض كلمة المرور")
        )
    reset_password_action.short_description = _("إجراءات كلمة المرور")

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        my_urls = [
            path('<uuid:object_id>/reset_password/',
                 self.admin_site.admin_view(self.reset_user_password),
                 name='%s_%s_reset_password' % info),
        ]
        return my_urls + urls

    def reset_user_password(self, request, object_id):
        user_account = self.get_object(request, object_id)
        if not user_account:
            raise Http404(_("المستخدم غير موجود."))

        if not self.has_change_permission(request, user_account):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied(_("ليس لديك إذن لإعادة تعيين كلمة مرور هذا المستخدم."))

        if request.method == 'POST':
            new_password = generate_temporary_password()
            user_account.set_password(new_password)
            user_account.is_temporary_password = True
            
            if user_account.firebase_uid:
                try:
                    auth.update_user(user_account.firebase_uid, password=new_password)
                    messages.success(request, _("تم تحديث كلمة المرور في Firebase أيضًا."))
                    logger.info(f"Firebase password reset for {user_account.email}")
                except firebase_exceptions.FirebaseError as e:
                    error_message = f"فشل تحديث كلمة المرور في Firebase لـ '{user_account.email}': {e.code} - {e.message}"
                    messages.error(request, format_html(_(error_message)))
                    logger.error(f"Firebase password reset error for {user_account.email}: {e}", exc_info=True)
            else:
                messages.warning(request, _("المستخدم لا يملك Firebase UID. لم يتم تحديث كلمة المرور في Firebase."))
                logger.warning(f"Attempted password reset for user {user_account.email} but no firebase_uid found.")

            user_account.save()

            messages.success(request, format_html(
                "<strong>تم إعادة تعيين كلمة المرور المؤقتة للمستخدم '{}' ({}):</strong> <code style='font-weight: bold; background-color: #e0ffe0; padding: 5px; border-radius: 3px;'>{}</code>. يرجى تزويد المستخدم بها. ستختفي هذه الرسالة عند التحديث أو الانتقال بعيداً.",
                user_account.username, user_account.email, new_password
            ))
            return redirect('admin:%s_%s_change' % (user_account._meta.app_label, user_account._meta.model_name), user_account.user_id)

        context = dict(
            self.admin_site.each_context(request),
            opts=self.model._meta,
            has_permission=self.has_change_permission(request, user_account),
            original=user_account,
            title=_("تأكيد إعادة تعيين كلمة المرور"),
        )
        return TemplateResponse(request, "admin/reset_password_confirmation.html", context)

