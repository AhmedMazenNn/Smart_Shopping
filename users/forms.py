# C:\Users\DELL\SER SQL MY APP\users\forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
import uuid

# استيراد النماذج الجديدة: UserAccount و Role
from .models import UserAccount, Role, generate_temporary_password, Customer, Employee

try:
    from stores.models import Store, Branch, StoreType # قد نحتاج StoreType لاحقًا
except ImportError:
    Store = None
    Branch = None
    StoreType = None
try:
    from products.models import Department
except ImportError:
    Department = None


# CustomUserCreationForm لإنشاء حساب UserAccount جديد (غالباً يستخدم في Django Admin)
class CustomUserCreationForm(forms.ModelForm):
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={'placeholder': _('Enter password for new user')}),
        required=False,
        help_text=_("Will be auto-generated for staff/store accounts if left blank.")
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput(attrs={'placeholder': _('Confirm password')}),
        required=False,
        help_text=_("Enter the same password as above. Not required if password is auto-generated.")
    )

    # تغيير user_type إلى Role
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(), # يجب أن تتوفر الأدوار في قاعدة البيانات
        label=_("Role"),
        help_text=_("Select the role for this user account.")
    )

    # الحقول التي أصبحت تنتمي إلى Customer أو Employee
    # تم إزالة blank=True و null=True من هنا، مع الحفاظ على required=False لجعلها اختيارية في الفورم
    phone_number = forms.CharField(max_length=20, required=False,
                                   label=_('Phone Number'),
                                   widget=forms.TextInput(attrs={'placeholder': _('+9665XXXXXXXX')}))
    tax_id = forms.CharField(max_length=50, required=False,
                             label=_('Tax ID (VAT/TRN/SSN)'),
                             widget=forms.TextInput(attrs={'placeholder': _('VAT ID or SSN')}))
    job_title = forms.CharField(max_length=100, required=False,
                                label=_('Job Title'),
                                widget=forms.TextInput(attrs={'placeholder': _('e.g., Cashier, Manager')}))
    
    # حقول العلاقات التي ستكون في Employee
    store = forms.ModelChoiceField(
        queryset=Store.objects.all() if Store else None,
        label=_('Associated Store'),
        required=False,
        empty_label=_("No Store")
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all() if Branch else None,
        label=_('Associated Branch'),
        required=False,
        empty_label=_("No Branch")
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all() if Department else None,
        label=_('Associated Department'),
        required=False,
        empty_label=_("No Department")
    )

    class Meta:
        model = UserAccount # استخدام UserAccount الجديد
        fields = (
            'email',
            'username',
            'first_name',
            'last_name',
            'role', # استخدام role بدلاً من user_type
            'phone_number',
            'tax_id',
            'job_title',
            'store',
            'branch',
            'department',
            'password',
            'password2'
        )
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': _('user@example.com')}),
            'username': forms.TextInput(attrs={'placeholder': _('Enter username')}),
            'first_name': forms.TextInput(attrs={'placeholder': _('First Name')}),
            'last_name': forms.TextInput(attrs={'placeholder': _('Last Name')}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        if 'username' in self.fields:
            self.fields['username'].required = False
            self.fields['username'].help_text = _("Optional. Will be auto-generated based on role and email if left blank.")
        
        # تصفية الأدوار بناءً على صلاحيات المستخدم الذي يقوم بإنشاء الحساب
        if self.request and self.request.user.is_authenticated and 'role' in self.fields:
            # افتراض أن request.user هو UserAccount
            current_user_role_name = self.request.user.role.role_name if self.request.user.role else None

            if not (self.request.user.is_superuser or current_user_role_name == 'app_owner'):
                # للمستخدمين غير السوبر يوزر وغير أصحاب التطبيق، تقييد خيارات الأدوار
                if current_user_role_name == 'store_manager' and self.request.user.employee_profile and self.request.user.employee_profile.store: # أو 'store_account'
                    self.fields['role'].queryset = Role.objects.filter(
                        role_name__in=['branch_manager', 'general_staff', 'cashier', 'shelf_organizer', 'customer_service', 'customer']
                    )
                elif current_user_role_name == 'branch_manager' and self.request.user.employee_profile and self.request.user.employee_profile.branch:
                    self.fields['role'].queryset = Role.objects.filter(
                        role_name__in=['general_staff', 'cashier', 'shelf_organizer', 'customer_service', 'customer']
                    )
                else: # أي دور آخر، يمكنه فقط إنشاء عملاء عاديين
                    self.fields['role'].queryset = Role.objects.filter(role_name='customer')
            
            # تعيين الدور الافتراضي حسب الأذونات
            if 'role' in self.fields and not self.initial.get('role'):
                if self.fields['role'].queryset.filter(role_name='customer').exists():
                    self.fields['role'].initial = Role.objects.get(role_name='customer')
                else:
                    self.fields['role'].initial = self.fields['role'].queryset.first() # تعيين الأول المتاح كافتراضي

        # تصفية الـ querysets للحقول المرتبطة (store, branch, department) بناءً على المستخدم
        if self.request and self.request.user.is_authenticated and hasattr(self.request.user, 'employee_profile') and self.request.user.employee_profile:
            employee_profile = self.request.user.employee_profile
            current_user_role_name = self.request.user.role.role_name if self.request.user.role else None

            if current_user_role_name in ['store_manager', 'store_account'] and employee_profile.store:
                if 'store' in self.fields and Store:
                    self.fields['store'].queryset = Store.objects.filter(pk=employee_profile.store.pk)
                    self.fields['store'].initial = employee_profile.store
                    self.fields['store'].widget.attrs['disabled'] = 'disabled'
                if 'branch' in self.fields and Branch:
                    self.fields['branch'].queryset = Branch.objects.filter(store=employee_profile.store)
                if 'department' in self.fields and Department:
                    self.fields['department'].queryset = Department.objects.filter(branch__store=employee_profile.store)
            elif current_user_role_name == 'branch_manager' and employee_profile.branch:
                if 'store' in self.fields and Store:
                    self.fields['store'].queryset = Store.objects.filter(pk=employee_profile.branch.store.pk) if employee_profile.branch.store else Store.objects.none()
                    self.fields['store'].initial = employee_profile.branch.store
                    self.fields['store'].widget.attrs['disabled'] = 'disabled'
                if 'branch' in self.fields and Branch:
                    self.fields['branch'].queryset = Branch.objects.filter(pk=employee_profile.branch.pk)
                    self.fields['branch'].initial = employee_profile.branch
                    self.fields['branch'].widget.attrs['disabled'] = 'disabled'
                if 'department' in self.fields and Department:
                    self.fields['department'].queryset = Department.objects.filter(branch=employee_profile.branch)
        else: # للضيوف أو المستخدمين الذين لا يملكون employee_profile
            # إذا لم يكن سوبر يوزر أو صاحب تطبيق، أخفي هذه الحقول
            if not (self.request and self.request.user.is_authenticated and (self.request.user.is_superuser or (self.request.user.role and self.request.user.role.role_name == 'app_owner'))):
                for field_name in ['store', 'branch', 'department', 'phone_number', 'tax_id', 'job_title']:
                    if field_name in self.fields:
                        self.fields[field_name].widget.attrs['style'] = 'display: none;'
                        self.fields[field_name].required = False # اجعلها غير مطلوبة إذا كانت مخفية


    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            if UserAccount.objects.filter(email__iexact=email).exists(): # استخدام UserAccount
                raise forms.ValidationError(_("A user with that email already exists."))
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            if UserAccount.objects.filter(username__iexact=username).exists(): # استخدام UserAccount
                raise forms.ValidationError(_("A user with that username already exists. Please choose a unique username."))
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password2 = cleaned_data.get("password2")
        role = cleaned_data.get('role') # أصبحنا نستخدم role مباشرة
        store = cleaned_data.get('store')
        branch = cleaned_data.get('branch')
        department = cleaned_data.get('department')
        job_title = cleaned_data.get('job_title')

        # منطق التحقق من كلمة المرور (خاص بـ CustomUserCreationForm فقط)
        # نتحقق من أننا في صفحة "إضافة" مستخدم جديد قبل تطبيق هذا التحقق.
        if self.request and self.request.resolver_match and self.request.resolver_match.url_name == 'users_useraccount_add': # تحديث اسم المسار
            if password and password2:
                if password != password2:
                    self.add_error('password2', _("Passwords don't match."))
            elif password and not password2:
                self.add_error('password2', _("Please confirm the new password."))
            elif not password and password2:
                self.add_error('password', _("Please enter the new password."))
            
            # بالنسبة لبعض الأدوار، كلمة المرور مطلوبة دائمًا
            if role and role.role_name in ['app_owner', 'project_manager', 'store_account'] and not password:
                self.add_error('password', _("A password is required for this role."))

        # التحقق من الاتساق بين الدور والحقول الإضافية
        # هذا التحقق هو على مستوى الفورم، والتحقق النهائي سيتم في save() أو في Model.clean()
        if role:
            if role.role_name == 'customer':
                # العميل يجب ألا يرتبط بـ store/branch/department/job_title/tax_id
                if store or branch or department or job_title or cleaned_data.get('tax_id'):
                    self.add_error(None, _("A customer cannot be associated with a store, branch, department, job title, or tax ID."))
            elif role.role_name in ['app_owner', 'project_manager', 'app_staff']:
                # أدوار التطبيق لا ترتبط بـ store/branch/department
                if store or branch or department:
                    self.add_error(None, _("App Owners, Project Managers, and App Staff should not be associated with a store, branch, or department."))
                if role.role_name in ['project_manager', 'app_staff'] and not job_title:
                    self.add_error('job_title', _("Project Managers and App Staff must have a job title."))
            elif role.role_name == 'store_account':
                # حساب المتجر لا يرتبط بـ branch/department/job_title/phone_number/tax_id
                if branch or department or job_title or cleaned_data.get('phone_number') or cleaned_data.get('tax_id'):
                    self.add_error(None, _("A Store Account cannot be associated with a branch, department, job title, phone number, or tax ID directly."))
                if not store:
                    self.add_error('store', _("A Store Account must be associated with a store."))
                # التحقق من صلاحيات المستخدم الذي يقوم بإنشاء الحساب
                if self.request and self.request.user.is_authenticated and self.request.user.role:
                    if self.request.user.role.role_name in ['store_manager', 'store_account'] and store:
                        if self.request.user.employee_profile and store.pk != self.request.user.employee_profile.store.pk:
                            self.add_error('store', _("You can only create accounts for your own store."))

            elif role.role_name == 'store_manager':
                # مدير المتجر يجب أن يكون مرتبطاً بمتجر، ولا يرتبط بفرع/قسم
                if not store:
                    self.add_error('store', _("A Store Manager must be associated with a store."))
                if branch or department:
                    self.add_error(None, _("A Store Manager cannot be associated with a branch or department."))
                if not job_title:
                    self.add_error('job_title', _("A Store Manager must have a job title."))
                if self.request and self.request.user.is_authenticated and self.request.user.role:
                    if self.request.user.role.role_name in ['store_manager', 'store_account'] and store:
                        if self.request.user.employee_profile and store.pk != self.request.user.employee_profile.store.pk:
                            self.add_error('store', _("You can only assign managers to your own store."))

            elif role.role_name == 'branch_manager':
                # مدير الفرع يجب أن يكون مرتبطاً بفرع، ويمكن لـ store أن يُعين تلقائيًا
                if not branch:
                    self.add_error('branch', _("A Branch Manager must be associated with a branch."))
                if department:
                    self.add_error('department', _("A Branch Manager cannot be associated with a department directly."))
                if not job_title:
                    self.add_error('job_title', _("A Branch Manager must have a job title."))
                
                if branch and not store:
                    cleaned_data['store'] = branch.store # تعيين المتجر تلقائياً بناءً على الفرع
                elif branch and store and store != branch.store:
                    self.add_error('store', _("The store must match the branch's store."))
                
                if self.request and self.request.user.is_authenticated and self.request.user.role:
                    if self.request.user.role.role_name in ['store_manager', 'store_account'] and branch:
                        if self.request.user.employee_profile and branch.store.pk != self.request.user.employee_profile.store.pk:
                            self.add_error('branch', _("You can only create branch managers for branches within your store."))
                    elif self.request.user.role.role_name == 'branch_manager' and self.instance and self.instance.pk != self.request.user.pk: # Allow editing self
                        self.add_error('role', _("You cannot create other branch managers.")) # لا يمكن لمدير الفرع إنشاء مديري فروع آخرين
            
            elif role.role_name in ['general_staff', 'cashier', 'shelf_organizer', 'customer_service']:
                # الموظفون الآخرون يجب أن يرتبطوا بفرع
                if not branch:
                    self.add_error('branch', _("This user type must be associated with a branch."))
                if not job_title:
                    self.add_error('job_title', _("This user type must have a job title."))
                
                if branch and not store:
                    cleaned_data['store'] = branch.store
                elif branch and store and store != branch.store:
                    self.add_error('store', _("The store must match the branch's store."))

                if department:
                    if not department.branch:
                        self.add_error('department', _("The associated department must be linked to a branch."))
                    elif department.branch != branch:
                        self.add_error('department', _("The associated department must belong to the user's assigned branch."))
                    elif department.branch.store != store:
                        self.add_error('department', _("The associated department's store must match the user's assigned store."))
                
                if self.request and self.request.user.is_authenticated and self.request.user.role:
                    if self.request.user.role.role_name in ['store_manager', 'store_account'] and branch:
                        if self.request.user.employee_profile and branch.store.pk != self.request.user.employee_profile.store.pk:
                            self.add_error('branch', _("You can only create staff for branches within your store."))
                    elif self.request.user.role.role_name == 'branch_manager' and branch:
                        if self.request.user.employee_profile and branch.pk != self.request.user.employee_profile.branch.pk:
                            self.add_error('branch', _("You can only create staff for your own branch."))

        return cleaned_data

    def save(self, commit=True):
        # حفظ UserAccount أولاً
        user_account = super().save(commit=False)
        password = self.cleaned_data.get("password")
        
        role = self.cleaned_data.get('role')
        if role:
            # تعيين is_staff و is_superuser بناءً على الدور
            user_account.is_staff = role.is_staff_role
            # تحديد is_superuser فقط لدور 'app_owner'
            user_account.is_superuser = (role.role_name == 'app_owner')

        if not password: # إذا لم يتم توفير كلمة مرور، يتم إنشاء كلمة مرور مؤقتة
            temp_password = generate_temporary_password()
            user_account.set_password(temp_password)
            user_account.is_temporary_password = True
            user_account._temporary_password = temp_password
        else: # إذا تم توفير كلمة مرور
            user_account.set_password(password)
            user_account.is_temporary_password = False
        
        if commit:
            user_account.save() # حفظ UserAccount في قاعدة البيانات

            # الآن، إنشاء أو تحديث كائن Customer أو Employee المرتبط
            role_name = role.role_name if role else None
            
            if role_name == 'customer':
                # إنشاء أو تحديث Customer
                customer, created = Customer.objects.get_or_create(
                    user_account=user_account,
                    defaults={
                        'phone_number': self.cleaned_data.get('phone_number', '') # يمكن أن يكون فارغًا
                    }
                )
                if not created: # إذا كان موجودًا، قم بالتحديث
                    customer.phone_number = self.cleaned_data.get('phone_number', customer.phone_number)
                    customer.save(update_fields=['phone_number'])
                # إزالة أي Employee مرتبط إذا كان موجودًا
                Employee.objects.filter(user_account=user_account).delete()

            elif role_name in ['app_owner', 'project_manager', 'app_staff', 'store_account']:
                # هؤلاء المستخدمون قد لا يكون لديهم ملف Employee (خاصة app_owner/project_manager)
                # حساب المتجر 'store_account' هو كيان منطقي، وليس بالضرورة موظف بشري
                # يمكن حذف أي Customer أو Employee مرتبط إذا كان موجودًا
                Customer.objects.filter(user_account=user_account).delete()
                Employee.objects.filter(user_account=user_account).delete()
            else: # أدوار الموظفين الأخرى (store_manager, branch_manager, general_staff, cashier, etc.)
                # إنشاء أو تحديث Employee
                employee, created = Employee.objects.get_or_create(
                    user_account=user_account,
                    defaults={
                        'job_title': self.cleaned_data.get('job_title', ''),
                        'store': self.cleaned_data.get('store'),
                        'branch': self.cleaned_data.get('branch'),
                        'department': self.cleaned_data.get('department'),
                        'phone_number': self.cleaned_data.get('phone_number', ''),
                        'tax_id': self.cleaned_data.get('tax_id', ''),
                        # 'commission_percentage' يمكن إدارتها بشكل منفصل أو هنا
                    }
                )
                if not created: # إذا كان موجودًا، قم بالتحديث
                    employee.job_title = self.cleaned_data.get('job_title', employee.job_title)
                    employee.store = self.cleaned_data.get('store', employee.store)
                    employee.branch = self.cleaned_data.get('branch', employee.branch)
                    employee.department = self.cleaned_data.get('department', employee.department)
                    employee.phone_number = self.cleaned_data.get('phone_number', employee.phone_number)
                    employee.tax_id = self.cleaned_data.get('tax_id', employee.tax_id)
                    employee.save(update_fields=['job_title', 'store', 'branch', 'department', 'phone_number', 'tax_id'])
                
                # إزالة أي Customer مرتبط إذا كان موجودًا
                Customer.objects.filter(user_account=user_account).delete()
        
        return user_account # نُعيد كائن UserAccount الذي تم حفظه


# CustomUserChangeForm لتعديل حساب UserAccount موجود
class CustomUserChangeForm(UserChangeForm):
    # تغيير user_type إلى Role
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(), # يجب أن تتوفر الأدوار في قاعدة البيانات
        label=_("Role"),
        help_text=_("Select the role for this user account.")
    )

    # الحقول التي أصبحت تنتمي إلى Customer أو Employee
    # تم إزالة blank=True و null=True من هنا، مع الحفاظ على required=False لجعلها اختيارية في الفورم
    phone_number = forms.CharField(max_length=20, required=False,
                                   label=_('Phone Number'),
                                   widget=forms.TextInput(attrs={'placeholder': _('+9665XXXXXXXX')}))
    tax_id = forms.CharField(max_length=50, required=False,
                             label=_('Tax ID (VAT/TRN/SSN)'),
                             widget=forms.TextInput(attrs={'placeholder': _('VAT ID or SSN')}))
    job_title = forms.CharField(max_length=100, required=False,
                                label=_('Job Title'),
                                widget=forms.TextInput(attrs={'placeholder': _('e.g., Cashier, Manager')}))
    
    # حقول العلاقات التي ستكون في Employee
    store = forms.ModelChoiceField(
        queryset=Store.objects.all() if Store else None,
        label=_('Associated Store'),
        required=False,
        empty_label=_("No Store")
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all() if Branch else None,
        label=_('Associated Branch'),
        required=False,
        empty_label=_("No Branch")
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all() if Department else None,
        label=_('Associated Department'),
        required=False,
        empty_label=_("No Department")
    )

    class Meta:
        model = UserAccount # استخدام UserAccount الجديد
        fields = (
            'email',
            'username',
            'first_name',
            'last_name',
            'role', # استخدام role
            'phone_number',
            'tax_id',
            'job_title',
            'store',
            'branch',
            'department',
            'is_active',
            'is_staff',
            'is_superuser',
            'groups',
            'user_permissions',
            'is_temporary_password'
        )
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': _('user@example.com')}),
            'first_name': forms.TextInput(attrs={'placeholder': _('First Name')}),
            'last_name': forms.TextInput(attrs={'placeholder': _('Last Name')}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # حذف حقول كلمة المرور لأنها لا تستخدم في نموذج التعديل
        if 'password' in self.fields:
            del self.fields['password']
        if 'password2' in self.fields:
            del self.fields['password2']

        if 'username' in self.fields and self.instance and self.instance.pk:
            self.fields['username'].disabled = True
            self.fields['username'].help_text = _("Username cannot be changed.")

        # تعيين القيمة الأولية للحقول المرتبطة من كائن العميل/الموظف الحالي
        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'customer_profile') and self.instance.customer_profile:
                customer_profile = self.instance.customer_profile
                self.fields['phone_number'].initial = customer_profile.phone_number
            elif hasattr(self.instance, 'employee_profile') and self.instance.employee_profile:
                employee_profile = self.instance.employee_profile
                self.fields['phone_number'].initial = employee_profile.phone_number
                self.fields['tax_id'].initial = employee_profile.tax_id
                self.fields['job_title'].initial = employee_profile.job_title
                self.fields['store'].initial = employee_profile.store
                self.fields['branch'].initial = employee_profile.branch
                self.fields['department'].initial = employee_profile.department
        
        # تعيين الدور الأولي من كائن UserAccount الحالي
        if self.instance and self.instance.role:
            self.fields['role'].initial = self.instance.role
            # في نموذج التعديل، قد نُعطل تغيير الدور لغير السوبر يوزر
            if self.request and self.request.user.is_authenticated:
                if not (self.request.user.is_superuser or (self.request.user.role and self.request.user.role.role_name == 'app_owner')):
                    # إذا لم يكن سوبر يوزر أو صاحب تطبيق، لا يمكنه تغيير الدور
                    self.fields['role'].widget.attrs['disabled'] = 'disabled'
                    self.fields['role'].help_text = _("You do not have permission to change the role for this user.")


        # تصفية الـ querysets للحقول المرتبطة (store, branch, department) بناءً على المستخدم
        if self.request and self.request.user.is_authenticated and hasattr(self.request.user, 'employee_profile') and self.request.user.employee_profile:
            employee_profile = self.request.user.employee_profile
            current_user_role_name = self.request.user.role.role_name if self.request.user.role else None

            if current_user_role_name in ['store_manager', 'store_account'] and employee_profile.store:
                if 'store' in self.fields and Store:
                    self.fields['store'].queryset = Store.objects.filter(pk=employee_profile.store.pk)
                    self.fields['store'].initial = employee_profile.store
                    self.fields['store'].widget.attrs['disabled'] = 'disabled'
                if 'branch' in self.fields and Branch:
                    self.fields['branch'].queryset = Branch.objects.filter(store=employee_profile.store)
                if 'department' in self.fields and Department:
                    self.fields['department'].queryset = Department.objects.filter(branch__store=employee_profile.store)
            elif current_user_role_name == 'branch_manager' and employee_profile.branch:
                if 'store' in self.fields and Store:
                    self.fields['store'].queryset = Store.objects.filter(pk=employee_profile.branch.store.pk) if employee_profile.branch.store else Store.objects.none()
                    self.fields['store'].initial = employee_profile.branch.store
                    self.fields['store'].widget.attrs['disabled'] = 'disabled'
                if 'branch' in self.fields and Branch:
                    self.fields['branch'].queryset = Branch.objects.filter(pk=employee_profile.branch.pk)
                    self.fields['branch'].initial = employee_profile.branch
                    self.fields['branch'].widget.attrs['disabled'] = 'disabled'
                if 'department' in self.fields and Department:
                    self.fields['department'].queryset = Department.objects.filter(branch=employee_profile.branch)
        else: # للضيوف أو المستخدمين الذين لا يملكون employee_profile
            # يمكن للمسؤولين الكبار رؤية هذه الحقول وتعديلها
            if not (self.request and self.request.user.is_authenticated and (self.request.user.is_superuser or (self.request.user.role and self.request.user.role.role_name == 'app_owner'))):
                for field_name in ['store', 'branch', 'department', 'phone_number', 'tax_id', 'job_title']:
                    if field_name in self.fields:
                        self.fields[field_name].widget.attrs['style'] = 'display: none;'
                        self.fields[field_name].required = False # اجعلها غير مطلوبة إذا كانت مخفية

        # إخفاء حقول is_staff, is_superuser, groups, user_permissions إذا لم يكن المستخدم سوبر يوزر أو صاحب تطبيق
        if self.request and self.request.user.is_authenticated:
            if not (self.request.user.is_superuser or (self.request.user.role and self.request.user.role.role_name == 'app_owner')):
                for field_name in ['is_staff', 'is_superuser', 'groups', 'user_permissions']:
                    if field_name in self.fields:
                        self.fields[field_name].widget.attrs['disabled'] = 'disabled'
                        self.fields[field_name].help_text = _("You do not have permission to modify this field.")
            
            # إذا كان المستخدم يقوم بتعديل نفسه وكان دوره هو 'app_owner'، يمكنه تعديل هذه الحقول
            if self.request.user.pk == self.instance.pk and self.request.user.role and self.request.user.role.role_name == 'app_owner':
                for field_name in ['is_staff', 'is_superuser', 'groups', 'user_permissions']:
                    if field_name in self.fields:
                        if 'disabled' in self.fields[field_name].widget.attrs:
                            del self.fields[field_name].widget.attrs['disabled'] # إزالة التعطيل
                        self.fields[field_name].help_text = _("As an App Owner, you can modify this field.")


        if 'is_temporary_password' in self.fields:
            if not self.instance.is_temporary_password:
                self.fields['is_temporary_password'].widget.attrs['disabled'] = False
                self.fields['is_temporary_password'].help_text = _("Check this box to generate a new temporary password for the user.")
            else:
                self.fields['is_temporary_password'].widget.attrs['disabled'] = True # عادة لا تسمح بتعطيله إذا كان مؤقتاً
                self.fields['is_temporary_password'].help_text = _("This user currently has a temporary password.")


    def clean_email(self):
        email = self.cleaned_data.get('email')
        if self.instance and self.instance.pk and email and email.lower() == self.instance.email.lower():
            return email
        if email:
            if UserAccount.objects.filter(email__iexact=email).exists():
                raise forms.ValidationError(_("A user with that email already exists."))
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if self.instance and self.instance.pk and username and username.lower() == self.instance.username.lower():
            return username
        if username:
            if UserAccount.objects.filter(username__iexact=username).exists():
                raise forms.ValidationError(_("A user with that username already exists. Please choose a unique username."))
        return username

    def clean(self):
        cleaned_data = super().clean()
        
        # --- إصلاح مهم: إعادة إضافة الحقول المعطلة إلى cleaned_data لتناسق التحقق ---
        # عندما تكون الحقول معطلة في دالة __init__، غالبًا لا يتم إرسال قيمها من قبل المتصفح.
        # يؤدي هذا إلى فقدانها من cleaned_data، مما يسبب أخطاء التحقق.
        # نقوم بإعادة إدخال قيم النموذج الأصلية لهذه الحقول إذا كانت معطلة.
        if self.instance and self.instance.pk: # فقط للكائنات الموجودة (نموذج التعديل)
            current_employee_profile = getattr(self.instance, 'employee_profile', None)
            current_customer_profile = getattr(self.instance, 'customer_profile', None)

            # استرجاع القيم الأصلية للحقول من Employee/Customer profile
            if current_employee_profile:
                # استخدام get لاحتمال عدم وجود الحقل في البيانات المرسلة (إذا كان معطلاً)
                cleaned_data['phone_number'] = cleaned_data.get('phone_number', current_employee_profile.phone_number)
                cleaned_data['tax_id'] = cleaned_data.get('tax_id', current_employee_profile.tax_id)
                cleaned_data['job_title'] = cleaned_data.get('job_title', current_employee_profile.job_title)
                cleaned_data['store'] = cleaned_data.get('store', current_employee_profile.store)
                cleaned_data['branch'] = cleaned_data.get('branch', current_employee_profile.branch)
                cleaned_data['department'] = cleaned_data.get('department', current_employee_profile.department)
            elif current_customer_profile:
                cleaned_data['phone_number'] = cleaned_data.get('phone_number', current_customer_profile.phone_number)

        # هذه الحقول لم تعد على UserAccount مباشرة،
        # ولكننا نحتاجها للتحقق من الصحة في الفورم قبل حفظها في Employee/Customer
        role = cleaned_data.get('role')
        store = cleaned_data.get('store')
        branch = cleaned_data.get('branch')
        department = cleaned_data.get('department')
        job_title = cleaned_data.get('job_title')
        phone_number = cleaned_data.get('phone_number')
        tax_id = cleaned_data.get('tax_id') # هذا يجب أن يكون موجوداً بالفعل في cleaned_data بعد التعديل أعلاه

        # منطق التحقق بناءً على الدور (Role)
        if role:
            role_name = role.role_name
            # Customer role validation
            if role_name == 'customer':
                # يجب ألا تكون هذه الحقول موجودة أو أن تكون فارغة
                if store or branch or department or job_title or tax_id:
                    self.add_error(None, _("A customer cannot be associated with a store, branch, department, job title, or tax ID."))
            # App roles validation
            elif role_name in ['app_owner', 'project_manager', 'app_staff']:
                if store or branch or department:
                    self.add_error(None, _("App Owners, Project Managers, and App Staff should not be associated with a store, branch, or department."))
                if role_name in ['project_manager', 'app_staff'] and not job_title:
                    self.add_error('job_title', _("Project Managers and App Staff must have a job title."))
            # Store Account role validation
            elif role_name == 'store_account':
                if not store:
                    self.add_error('store', _("A Store Account must be associated with a store."))
                if branch or department or job_title or phone_number or tax_id:
                    self.add_error(None, _("A Store Account cannot be associated with a branch, department, job title, phone number, or tax ID directly."))
                
                # Check permissions of the user performing the action
                if self.request and self.request.user.is_authenticated and self.request.user.role:
                    if self.request.user.role.role_name in ['store_manager', 'store_account'] and store:
                        # التأكد من أن المستخدم الذي يُجري التعديل يمكنه فقط إدارة متجره الخاص
                        if self.request.user.employee_profile and store.pk != self.request.user.employee_profile.store.pk:
                            self.add_error('store', _("You can only manage accounts for your own store."))

            # Employee roles (store_manager, branch_manager, general_staff, cashier, shelf_organizer, customer_service)
            elif role_name in ['store_manager', 'branch_manager', 'general_staff', 'cashier', 'shelf_organizer', 'customer_service']:
                if not store:
                    self.add_error('store', _("This employee role must be associated with a store."))
                if not job_title:
                    self.add_error('job_title', _("This employee role must have a job title."))
                
                # Branch Manager specific validation
                if role_name == 'branch_manager':
                    if not branch:
                        self.add_error('branch', _("A Branch Manager must be associated with a branch."))
                    if department:
                        self.add_error('department', _("A Branch Manager cannot be associated with a department directly."))
                    
                    if branch and store and store.pk != branch.store.pk: # استخدام pk للمقارنة
                        self.add_error('store', _("The store must match the branch's store."))
                    elif branch and not store: # Auto-assign store if branch is selected and store is not
                        cleaned_data['store'] = branch.store
                    
                    # Check permissions
                    if self.request and self.request.user.is_authenticated and self.request.user.role:
                        if self.request.user.role.role_name in ['store_manager', 'store_account'] and branch:
                            if self.request.user.employee_profile and branch.store.pk != self.request.user.employee_profile.store.pk:
                                self.add_error('branch', _("You can only assign branch managers for branches within your store."))
                        elif self.request.user.role.role_name == 'branch_manager' and self.instance and self.instance.pk != self.request.user.pk: # Allow editing self, but not other branch managers
                            self.add_error('role', _("You cannot manage other branch managers.")) # Cannot change other branch managers' roles
                            if self.instance.role.role_name == 'branch_manager' and self.instance.employee_profile.branch.pk != branch.pk: # Use pk for comparison
                                self.add_error('branch', _("You can only assign yourself as a branch manager for your own branch."))


                # Other Staff (General Staff, Cashier, Shelf Organizer, Customer Service) specific validation
                elif role_name in ['general_staff', 'cashier', 'shelf_organizer', 'customer_service']:
                    if not branch:
                        self.add_error('branch', _("This user type must be associated with a branch."))
                    
                    if branch and store and store.pk != branch.store.pk: # استخدام pk للمقارنة
                        self.add_error('store', _("The store must match the branch's store."))
                    elif branch and not store: # Auto-assign store
                        cleaned_data['store'] = branch.store

                    if department:
                        if not department.branch:
                            self.add_error('department', _("The associated department must be linked to a branch."))
                        elif department.branch != branch:
                            self.add_error('department', _("The associated department must belong to the user's assigned branch."))
                        elif department.branch.store != store:
                            self.add_error('department', _("The associated department's store must match the user's assigned store."))
                    
                    if self.request and self.request.user.is_authenticated and self.request.user.role:
                        if self.request.user.role.role_name in ['store_manager', 'store_account'] and branch:
                            if self.request.user.employee_profile and branch.store.pk != self.request.user.employee_profile.store.pk:
                                self.add_error('branch', _("You can only create staff for branches within your store."))
                        elif self.request.user.role.role_name == 'branch_manager' and branch:
                            if self.request.user.employee_profile and branch.pk != self.request.user.employee_profile.branch.pk:
                                self.add_error('branch', _("You can only create staff for your own branch."))

        return cleaned_data

    def save(self, commit=True):
        # حفظ UserAccount أولاً
        user_account = super().save(commit=False)
        
        # إذا تم تحديد is_temporary_password في الفورم، فهذا يعني طلب إعادة تعيين
        if 'is_temporary_password' in self.cleaned_data and self.cleaned_data['is_temporary_password']:
            temp_password = generate_temporary_password()
            user_account.set_password(temp_password)
            user_account.is_temporary_password = True
            # تخزين كلمة المرور المولّدة مؤقتًا على كائن user_account للعرض
            user_account._temporary_password = temp_password
        else:
            # إذا لم يتم تحديد is_temporary_password (أو كان False)، ولم يتم تغيير كلمة المرور يدوياً
            # نحتاج إلى الحفاظ على كلمة المرور القديمة ما لم يتم تقديم كلمة مرور جديدة يدوياً
            pass # كلمة المرور يتم التعامل معها في Django admin's change_form.html بشكل منفصل.
                 # هنا نحن فقط نُعالج حالة إعادة تعيين كلمة المرور.

        # تحديث is_staff و is_superuser بناءً على الدور الجديد
        role = self.cleaned_data.get('role')
        if role:
            user_account.is_staff = role.is_staff_role
            user_account.is_superuser = (role.role_name == 'app_owner')

        if commit:
            user_account.save() # حفظ UserAccount في قاعدة البيانات

            # الآن، إنشاء أو تحديث كائن Customer أو Employee المرتبط
            role_name = role.role_name if role else None
            
            # حقول ملفات التعريف
            phone_number = self.cleaned_data.get('phone_number', '')
            tax_id = self.cleaned_data.get('tax_id', '')
            job_title = self.cleaned_data.get('job_title', '')
            store = self.cleaned_data.get('store', None)
            branch = self.cleaned_data.get('branch', None)
            department = self.cleaned_data.get('department', None)

            if role_name == 'customer':
                # إنشاء أو تحديث Customer
                customer, created = Customer.objects.get_or_create(
                    user_account=user_account
                )
                customer.phone_number = phone_number
                customer.save(update_fields=['phone_number'])
                # إزالة أي Employee مرتبط إذا كان موجودًا
                Employee.objects.filter(user_account=user_account).delete()

            elif role_name in ['app_owner', 'project_manager', 'app_staff', 'store_account']:
                # هؤلاء المستخدمون قد لا يكون لديهم ملف Employee (خاصة app_owner/project_manager)
                # حساب المتجر 'store_account' هو كيان منطقي، وليس بالضرورة موظف بشري
                # يمكن حذف أي Customer أو Employee مرتبط إذا كان موجودًا
                Customer.objects.filter(user_account=user_account).delete()
                Employee.objects.filter(user_account=user_account).delete()
            else: # أدوار الموظفين الأخرى (store_manager, branch_manager, general_staff, cashier, etc.)
                # إنشاء أو تحديث Employee
                employee, created = Employee.objects.get_or_create(
                    user_account=user_account,
                    defaults={
                        'job_title': job_title,
                        'store': store,
                        'branch': branch,
                        'department': department,
                        'phone_number': phone_number,
                        'tax_id': tax_id,
                    }
                )
                if not created: # إذا كان موجودًا، قم بالتحديث
                    employee.job_title = job_title
                    employee.store = store
                    employee.branch = branch
                    employee.department = department
                    employee.phone_number = phone_number
                    employee.tax_id = tax_id
                    employee.save(update_fields=['job_title', 'store', 'branch', 'department', 'phone_number', 'tax_id'])
                
                # إزالة أي Customer مرتبط إذا كان موجودًا
                Customer.objects.filter(user_account=user_account).delete()
        
        return user_account # نُعيد كائن UserAccount الذي تم حفظه
