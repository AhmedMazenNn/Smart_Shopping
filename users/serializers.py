# C:\Users\DELL\SER SQL MY APP\users\serializers.py

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify

# Import the new models
from .models import UserAccount, Role, Customer, Employee, generate_temporary_password

# Import other related models
from products.models import Department
from stores.models import Store, Branch 

# --- RoleSerializer ---
class RoleSerializer(serializers.ModelSerializer):
    """
    Serializer for the Role model, used for nested representation of role details.
    """
    class Meta:
        model = Role
        fields = ['id', 'role_name', 'display_name', 'description', 'is_staff_role', 'is_employee_role']
        read_only_fields = ['id', 'role_name', 'display_name', 'description', 'is_staff_role', 'is_employee_role']


# --- RegisterSerializer ---
class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for general user registration. It requires users to provide their passwords
    and handles the creation of associated Customer or Employee profiles based on the role.
    """
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        required=True, 
        help_text=_("ID of the role for the user account.")
    )

    # Fields for Customer/Employee profiles, collected here for form input
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    tax_id = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    job_title = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    
    # Fields for Employee profile relationships
    store = serializers.PrimaryKeyRelatedField(queryset=Store.objects.all(), required=False, allow_null=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)

    class Meta:
        model = UserAccount 
        fields = (
            'username', 'email', 'password', 'password2', 'role',
            'first_name', 'last_name', 'phone_number', 'tax_id', 'job_title',
            'store', 'branch', 'department'
        )
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True},
            'username': {'required': False, 'allow_null': True, 'allow_blank': True},
        }

    def validate(self, attrs):
        email = attrs.get('email')
        if not email or not email.strip():
            raise serializers.ValidationError({"email": _("Email address is required.")})
        
        if UserAccount.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({"email": _("A user with this email address already exists.")})

        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": _("Password fields didn't match.")})
            
        try:
            validate_password(attrs['password'], user=None)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
            
        role = attrs.get('role')
        if not role:
            raise serializers.ValidationError({"role": _("Role is required.")})

        # Role-specific validation
        if role.role_name == 'customer':
            if attrs.get('store') or attrs.get('branch') or attrs.get('department') or attrs.get('job_title') or attrs.get('tax_id'):
                raise serializers.ValidationError(_("Customer role cannot be associated with store, branch, department, job title, or tax ID."))
        elif role.role_name in ['app_owner', 'project_manager', 'app_staff']:
            if attrs.get('store') or attrs.get('branch') or attrs.get('department'):
                raise serializers.ValidationError(_("App Owners, Project Managers, and App Staff should not be associated with a store, branch, or department."))
            if role.role_name in ['project_manager', 'app_staff'] and not attrs.get('job_title'):
                raise serializers.ValidationError({"job_title": _("Project Managers and App Staff must have a job title.")})
        elif role.role_name == 'store_account':
            if not attrs.get('store'):
                raise serializers.ValidationError({"store": _("A Store Account must be associated with a store.")})
            if attrs.get('branch') or attrs.get('department') or attrs.get('job_title') or attrs.get('tax_id'):
                raise serializers.ValidationError(_("A Store Account cannot be associated with a branch, department, job title, or tax ID directly."))
        elif role.role_name == 'store_manager':
            if not attrs.get('store'):
                raise serializers.ValidationError({"store": _("A Store Manager must be associated with a store.")})
            if attrs.get('branch') or attrs.get('department'):
                raise serializers.ValidationError(_("A Store Manager cannot be associated with a branch or department directly."))
            if not attrs.get('job_title'):
                raise serializers.ValidationError({"job_title": _("A Store Manager must have a job title.")})
        elif role.role_name == 'branch_manager':
            if not attrs.get('branch'):
                raise serializers.ValidationError({"branch": _("A Branch Manager must be associated with a branch.")})
            if attrs.get('department'):
                raise serializers.ValidationError({"department": _("A Branch Manager cannot be associated with a department directly.")})
            if not attrs.get('job_title'):
                raise serializers.ValidationError({"job_title": _("A Branch Manager must have a job title.")})
            # Ensure the store implicitly matches the branch's store if a store is provided
            if attrs.get('store') and attrs['store'] != attrs['branch'].store:
                raise serializers.ValidationError({"store": _("The store must match the branch's store.")})
        elif role.role_name in ['general_staff', 'cashier', 'shelf_organizer', 'customer_service']:
            if not attrs.get('branch'):
                raise serializers.ValidationError({"branch": _("This user type must be associated with a branch.")})
            if not attrs.get('job_title'):
                raise serializers.ValidationError({"job_title": _("This user type must have a job title.")})
            # Ensure the store implicitly matches the branch's store if a store is provided
            if attrs.get('store') and attrs['store'] != attrs['branch'].store:
                raise serializers.ValidationError({"store": _("The store must match the branch's store.")})
            if attrs.get('department') and attrs['department'].branch != attrs['branch']:
                raise serializers.ValidationError({"department": _("The associated department must belong to the user's assigned branch.")})

        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data.pop('password2')

        role = validated_data.pop('role')
        phone_number = validated_data.pop('phone_number', '')
        tax_id = validated_data.pop('tax_id', '')
        job_title = validated_data.pop('job_title', '')
        store = validated_data.pop('store', None)
        branch = validated_data.pop('branch', None)
        department = validated_data.pop('department', None)

        is_staff = role.is_staff_role
        is_superuser = (role.role_name == 'app_owner')

        username = validated_data.get('username')
        if not username:
            base_username = slugify(validated_data.get('first_name') or validated_data['email'].split('@')[0])
            username_candidate = f"{base_username}-{role.role_name}"
            counter = 0
            while UserAccount.objects.filter(username__iexact=username_candidate).exists():
                counter += 1
                username_candidate = f"{base_username}_{counter}"
            username = username_candidate
            validated_data['username'] = username
            
        user_account = UserAccount.objects.create_user(
            username=username,
            email=validated_data['email'],
            password=password,
            role=role,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=validated_data.get('is_active', True),
        )
        
        # Create associated Customer or Employee profile
        if role.role_name == 'customer':
            Customer.objects.create(
                user_account=user_account,
                phone_number=phone_number
            )
        elif role.is_employee_role: # All roles that are considered staff/employees
            Employee.objects.create(
                user_account=user_account,
                job_title=job_title,
                store=store,
                branch=branch,
                department=department,
                phone_number=phone_number,
                tax_id=tax_id,
            )

        return user_account


# --- LoginSerializer ---
class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login data, allowing authentication via email or username.
    """
    email = serializers.CharField(write_only=True, required=False)
    username = serializers.CharField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        extra_kwargs = {
            'email': {'required': False},
            'username': {'required': False},
        }

    def validate(self, attrs):
        email = attrs.get('email')
        username = attrs.get('username')
        password = attrs.get('password')

        if not email and not username:
            raise serializers.ValidationError(_("Must provide email or username."))

        user_account = None
        if email:
            try:
                user_account = UserAccount.objects.get(email__iexact=email)
            except UserAccount.DoesNotExist:
                pass 

        if not user_account and username:
            try:
                user_account = UserAccount.objects.get(username__iexact=username)
            except UserAccount.DoesNotExist:
                pass

        if not user_account:
            raise serializers.ValidationError(_("No user found with the provided credentials."))
            
        if not user_account.check_password(password):
            raise serializers.ValidationError(_("Incorrect password."))

        if not user_account.is_active:
            raise serializers.ValidationError(_("User account is inactive."))

        attrs['user'] = user_account
        return attrs


# --- CustomerRegistrationSerializer ---
class CustomerRegistrationSerializer(RegisterSerializer):
    """
    Specialized serializer for platform customer registration.
    Automatically sets the role to 'customer' and excludes employee-specific fields.
    """
    class Meta(RegisterSerializer.Meta):
        fields = (
            'username', 'email', 'password', 'password2',
            'first_name', 'last_name', 'phone_number', 
        )
        extra_kwargs = {
            'role': {'read_only': True, 'default': None}, # Will be set in validate/create
            'tax_id': {'read_only': True, 'allow_null': True, 'required': False},
            'job_title': {'read_only': True, 'allow_null': True, 'required': False},
            'store': {'read_only': True, 'allow_null': True, 'required': False},
            'branch': {'read_only': True, 'allow_null': True, 'required': False},
            'department': {'read_only': True, 'allow_null': True, 'required': False},
            **RegisterSerializer.Meta.extra_kwargs 
        }

    def validate(self, attrs):
        try:
            customer_role = Role.objects.get(role_name='customer')
            attrs['role'] = customer_role
        except Role.DoesNotExist:
            raise serializers.ValidationError({"role": _("The 'customer' role does not exist in the database.")})
            
        # Remove employee-specific fields if they somehow sneaked in
        attrs.pop('tax_id', None)
        attrs.pop('job_title', None)
        attrs.pop('store', None)
        attrs.pop('branch', None)
        attrs.pop('department', None)

        return super().validate(attrs)

    def create(self, validated_data):
        try:
            customer_role = Role.objects.get(role_name='customer')
            validated_data['role'] = customer_role
        except Role.DoesNotExist:
            raise serializers.ValidationError({"role": _("The 'customer' role does not exist in the database.")})
            
        return super().create(validated_data)


# --- UserAccountSerializer (replaces UserSerializer) ---
class UserAccountSerializer(serializers.ModelSerializer):
    """
    Serializer for UserAccount management by administrators or privileged roles.
    Handles auto-generation of passwords, updates, and related Customer/Employee profiles.
    """
    role_info = RoleSerializer(source='role', read_only=True) # Nested serializer for full role details
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), write_only=True, required=False) # For setting role by ID

    password = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'},
        help_text=_("Leave blank to auto-generate a temporary password. Required for superusers when changing password.")
    )
    password2 = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'},
        help_text=_("Confirm password. Not required if password is auto-generated.")
    )

    generated_password = serializers.CharField(read_only=True, required=False)

    # Fields that come from related Customer/Employee profiles.
    # 'get_phone_number' is a method on UserAccount to retrieve phone from either profile.
    phone_number = serializers.CharField(source='get_phone_number', required=False, allow_blank=True, allow_null=True)
    
    # Direct fields from Employee profile, allowing writing (updates)
    tax_id = serializers.CharField(source='employee_profile.tax_id', required=False, allow_blank=True, allow_null=True)
    job_title = serializers.CharField(source='employee_profile.job_title', required=False, allow_blank=True, allow_null=True)
    commission_percentage = serializers.DecimalField(source='employee_profile.commission_percentage', max_digits=5, decimal_places=2, required=False, allow_null=True)
    
    store = serializers.PrimaryKeyRelatedField(source='employee_profile.store', queryset=Store.objects.all(), required=False, allow_null=True)
    store_name = serializers.CharField(source='employee_profile.store.name', read_only=True, allow_null=True)
    
    branch = serializers.PrimaryKeyRelatedField(source='employee_profile.branch', queryset=Branch.objects.all(), required=False, allow_null=True)
    branch_name = serializers.CharField(source='employee_profile.branch.name', read_only=True, allow_null=True)
    
    department = serializers.PrimaryKeyRelatedField(source='employee_profile.department', queryset=Department.objects.all(), required=False, allow_null=True)
    department_name = serializers.CharField(source='employee_profile.department.name', read_only=True, allow_null=True)


    class Meta:
        model = UserAccount 
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'role_info', 
            'phone_number', 'tax_id', 'job_title', 'commission_percentage',
            'store', 'store_name', 'branch', 'branch_name', 'department', 'department_name',
            'is_staff', 'is_active', 'is_superuser', 'is_temporary_password',
            'password', 'password2', 'generated_password',
            'last_login', 'date_joined', 
        )
        read_only_fields = (
            'id', 'role_info', 'last_login', 'date_joined', 'generated_password',
            'store_name', 'branch_name', 'department_name',
        )
        extra_kwargs = {
            'is_temporary_password': {'required': False}, # Allow updating this flag
            'username': {'required': False, 'allow_null': True, 'allow_blank': True},
            'email': {'required': True}, 
        }

    def validate(self, attrs):
        # Password validation
        if attrs.get('password'):
            if attrs.get('password2') and attrs['password'] != attrs['password2']:
                raise serializers.ValidationError({"password": _("Password fields didn't match.")})
            
            if self.instance and not attrs.get('password2'):
                raise serializers.ValidationError({"password2": _("Confirm password is required if changing password.")})
                
            try:
                validate_password(attrs['password'], user=self.instance)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"password": list(e.messages)})
        elif self.instance and attrs.get('password2'): 
            raise serializers.ValidationError({"password": _("Password is required if confirm password is provided.")})


        # Email validation
        email = attrs.get('email')
        if not email or not email.strip():
            raise serializers.ValidationError({"email": _("Email address is required.")})
            
        # Check for duplicate email, excluding the current instance if it's an update
        if self.instance:
            if UserAccount.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError({"email": _("A user with this email address already exists.")})
        else: # For create operation
            if UserAccount.objects.filter(email__iexact=email).exists():
                raise serializers.ValidationError({"email": _("A user with this email address already exists.")})
            
        # Get the role for validation - prioritize new role, then existing instance's role
        role = attrs.get('role', self.instance.role if self.instance else None)
        if not role:
            raise serializers.ValidationError({"role": _("Role is required.")})
            
        # Collect profile-related fields for role-specific validation, using current instance's values if not provided in attrs
        # These fields need to be handled carefully, as their values might come from the existing instance's profile
        # if they are not explicitly provided in the request body (during a partial update, for example).
        current_phone_number = self.instance.get_phone_number() if self.instance else None
        current_tax_id = self.instance.employee_profile.tax_id if self.instance and hasattr(self.instance, 'employee_profile') else None
        current_job_title = self.instance.employee_profile.job_title if self.instance and hasattr(self.instance, 'employee_profile') else None
        current_store = self.instance.employee_profile.store if self.instance and hasattr(self.instance, 'employee_profile') else None
        current_branch = self.instance.employee_profile.branch if self.instance and hasattr(self.instance, 'employee_profile') else None
        current_department = self.instance.employee_profile.department if self.instance and hasattr(self.instance, 'employee_profile') else None

        # For validation, use the new value if provided, otherwise the current value
        phone_number = attrs.get('phone_number', current_phone_number)
        tax_id = attrs.get('tax_id', current_tax_id)
        job_title = attrs.get('job_title', current_job_title)
        store = attrs.get('store', current_store)
        branch = attrs.get('branch', current_branch)
        department = attrs.get('department', current_department)

        # Apply role-specific validation
        if role.role_name == 'customer':
            if store or branch or department or job_title or tax_id:
                raise serializers.ValidationError(_("Customer role cannot be associated with store, branch, department, job title, or tax ID."))
        elif role.role_name in ['app_owner', 'project_manager', 'app_staff']:
            if store or branch or department:
                raise serializers.ValidationError(_("App Owners, Project Managers, and App Staff should not be associated with a store, branch, or department."))
            if role.role_name in ['project_manager', 'app_staff'] and not job_title:
                raise serializers.ValidationError({"job_title": _("Project Managers and App Staff must have a job title.")})
        elif role.role_name == 'store_account':
            if not store:
                raise serializers.ValidationError({"store": _("A Store Account must be associated with a store.")})
            if branch or department or job_title or tax_id:
                raise serializers.ValidationError(_("A Store Account cannot be associated with a branch, department, job title, or tax ID directly."))
        elif role.role_name == 'store_manager':
            if not store:
                raise serializers.ValidationError({"store": _("A Store Manager must be associated with a store.")})
            if branch or department:
                raise serializers.ValidationError(_("A Store Manager cannot be associated with a branch or department directly."))
            if not job_title:
                raise serializers.ValidationError({"job_title": _("A Store Manager must have a job title.")})
        elif role.role_name == 'branch_manager':
            if not branch:
                raise serializers.ValidationError({"branch": _("A Branch Manager must be associated with a branch.")})
            if department:
                raise serializers.ValidationError({"department": _("A Branch Manager cannot be associated with a department directly.")})
            if not job_title:
                raise serializers.ValidationError({"job_title": _("A Branch Manager must have a job title.")})
            if store and branch and store != branch.store:
                raise serializers.ValidationError({"store": _("The store must match the branch's store.")})
        elif role.role_name in ['general_staff', 'cashier', 'shelf_organizer', 'customer_service']:
            if not branch:
                raise serializers.ValidationError({"branch": _("This user type must be associated with a branch.")})
            if not job_title:
                raise serializers.ValidationError({"job_title": _("This user type must have a job title.")})
            if store and branch and store != branch.store:
                raise serializers.ValidationError({"store": _("The store must match the branch's store.")})
            if department and branch and department.branch != branch:
                raise serializers.ValidationError({"department": _("The associated department must belong to the user's assigned branch.")})

        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        validated_data.pop('password2', None)
        
        # Pop all fields that will be used for profiles
        role = validated_data.pop('role')
        phone_number = validated_data.pop('phone_number', '')
        tax_id = validated_data.pop('tax_id', '')
        job_title = validated_data.pop('job_title', '')
        store = validated_data.pop('store', None)
        branch = validated_data.pop('branch', None)
        department = validated_data.pop('department', None)
        commission_percentage = validated_data.pop('commission_percentage', None)

        is_staff = role.is_staff_role
        is_superuser = (role.role_name == 'app_owner')

        username = validated_data.get('username')
        if not username:
            base_username = slugify(validated_data.get('first_name') or validated_data['email'].split('@')[0])
            username_candidate = f"{base_username}-{role.role_name}"
            counter = 0
            while UserAccount.objects.filter(username__iexact=username_candidate).exists():
                counter += 1
                username_candidate = f"{base_username}_{counter}"
            username = username_candidate
            validated_data['username'] = username
            
        user_account = UserAccount.objects.create_user(
            username=username,
            email=validated_data['email'],
            password=password, 
            role=role,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=validated_data.get('is_active', True),
        )
        
        # Handle temporary password generation if no password was provided
        if not password:
            user_account.is_temporary_password = True
            user_account.save(update_fields=['is_temporary_password'])
            # Store the generated password on the instance for serialization, not in DB
            user_account.generated_password = user_account._temporary_password 

        # Create associated Customer or Employee profile based on role
        if role.role_name == 'customer':
            Customer.objects.create(
                user_account=user_account,
                phone_number=phone_number
            )
        elif role.is_employee_role: 
            Employee.objects.create(
                user_account=user_account,
                job_title=job_title,
                store=store,
                branch=branch,
                department=department,
                phone_number=phone_number,
                tax_id=tax_id,
                commission_percentage=commission_percentage
            )

        return user_account

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        validated_data.pop('password2', None)
        
        # Pop fields that might update profile data
        role = validated_data.pop('role', None) 
        phone_number = validated_data.pop('phone_number', None)
        tax_id = validated_data.pop('tax_id', None)
        job_title = validated_data.pop('job_title', None)
        store = validated_data.pop('store', None)
        branch = validated_data.pop('branch', None)
        department = validated_data.pop('department', None)
        commission_percentage = validated_data.pop('commission_percentage', None)

        # Handle password update and temporary password status
        if password:
            instance.set_password(password)
            instance.is_temporary_password = False
        elif validated_data.get('is_temporary_password') is True: 
            temp_password = generate_temporary_password()
            instance.set_password(temp_password)
            instance.is_temporary_password = True
            instance.generated_password = temp_password # For displaying in response
        elif validated_data.get('is_temporary_password') is False: 
            instance.is_temporary_password = False
        
        # Update UserAccount fields (directly on the instance)
        for attr, value in validated_data.items():
            if hasattr(instance, attr): 
                setattr(instance, attr, value)
            
        # Update role and its derived fields if a new role is provided
        if role:
            instance.role = role
            instance.is_staff = role.is_staff_role
            instance.is_superuser = (role.role_name == 'app_owner')

        # Update or create associated Customer or Employee profile
        # This logic handles transitions between roles requiring different profiles.
        
        # If the new/current role is 'customer'
        if instance.role and instance.role.role_name == 'customer':
            # Delete employee profile if it exists (transition from employee to customer)
            if hasattr(instance, 'employee_profile') and instance.employee_profile:
                instance.employee_profile.delete()
            # Get or create customer profile and update its phone number
            customer_profile, created = Customer.objects.get_or_create(user_account=instance)
            if phone_number is not None: # Only update if phone_number was provided in the request
                customer_profile.phone_number = phone_number
            customer_profile.save() 
        # If the new/current role is an 'employee' role
        elif instance.role and instance.role.is_employee_role: 
            # Delete customer profile if it exists (transition from customer to employee)
            if hasattr(instance, 'customer_profile') and instance.customer_profile:
                instance.customer_profile.delete()
            # Get or create employee profile and update its fields
            employee_profile, created = Employee.objects.get_or_create(user_account=instance)
            
            # Update fields only if they were explicitly provided in validated_data (for partial updates)
            if job_title is not None: employee_profile.job_title = job_title
            if store is not None: employee_profile.store = store
            if branch is not None: employee_profile.branch = branch
            if department is not None: employee_profile.department = department
            if phone_number is not None: employee_profile.phone_number = phone_number
            if tax_id is not None: employee_profile.tax_id = tax_id
            if commission_percentage is not None: employee_profile.commission_percentage = commission_percentage

            employee_profile.save() 
        else: # For app_owner, project_manager, app_staff, store_account roles (no explicit profile needed)
            # Delete any existing customer or employee profiles if the role doesn't require one
            if hasattr(instance, 'customer_profile') and instance.customer_profile:
                instance.customer_profile.delete()
            if hasattr(instance, 'employee_profile') and instance.employee_profile:
                instance.employee_profile.delete()
                
        instance.save() # Save UserAccount changes
        return instance


# --- UserProfileSerializer (Used for self-profile view) ---
class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying a user's own profile information. All fields are read-only.
    """
    # These fields might come from either Customer or Employee profile
    # 'get_phone_number' is a method on UserAccount to retrieve phone from either profile.
    phone_number = serializers.CharField(source='get_phone_number', read_only=True, allow_null=True)
    tax_id = serializers.CharField(source='employee_profile.tax_id', read_only=True, allow_null=True)
    job_title = serializers.CharField(source='employee_profile.job_title', read_only=True, allow_null=True)
    commission_percentage = serializers.DecimalField(source='employee_profile.commission_percentage', max_digits=5, decimal_places=2, read_only=True, allow_null=True)

    # Directly map role display name
    role_display = serializers.CharField(source='role.display_name', read_only=True, allow_null=True)

    # Store, Branch, Department names from employee_profile
    store_name = serializers.CharField(source='employee_profile.store.name', read_only=True, allow_null=True)
    branch_name = serializers.CharField(source='employee_profile.branch.name', read_only=True, allow_null=True)
    department_name = serializers.CharField(source='employee_profile.department.name', read_only=True, allow_null=True)

    class Meta:
        model = UserAccount 
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'tax_id', 'role', 'role_display', 'job_title',
            'commission_percentage', 'is_active', 'is_staff', 'is_superuser',
            'store_name', 'branch_name', 'department_name',
            'date_joined', 'last_login', 
        )
        read_only_fields = fields # All fields are read-only for a profile view (updates should use UserAccountSerializer)