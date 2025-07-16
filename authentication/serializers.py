# C:\Users\DELL\SER SQL MY APP\authentication\serializers.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate # استيراد دالة authenticate

# Import our new models
from stores.models import Store, StoreType # تأكد من وجود StoreType في stores/models.py
from users.models import Role # We need Role to assign for new users if applicable

User = get_user_model() # This will be our UserAccount model (from settings.AUTH_USER_MODEL)

# --- StoreRegistrationSerializer ---
class StoreRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for registering new Store instances.
    This serializer handles the creation of a Store entity and its primary login email.
    """
    # Explicitly map serializer field names to model field names using 'source'
    # This makes the API clearer while matching the model.
    store_name = serializers.CharField(source='name', max_length=255, required=True, help_text=_("The official name of the store."))
    store_address = serializers.CharField(source='address', help_text=_("The physical address of the store."), required=True)
    store_phone_number = serializers.CharField(source='phone_number', max_length=20, allow_blank=True, required=False, help_text=_("General contact phone number for the store."))
    store_contact_email = serializers.EmailField(source='email', allow_blank=True, required=False, help_text=_("General contact email for the store (not for login)."))
    store_login_email = serializers.EmailField(source='login_email', required=True, help_text=_("The primary email used for the main store account login. Must be unique."))
    store_tax_id = serializers.CharField(source='tax_id', max_length=50, allow_blank=True, required=False, help_text=_("The unique tax ID for the store (e.g., VAT number)."))

    store_type_id = serializers.PrimaryKeyRelatedField(
        queryset=StoreType.objects.all(),
        source='store_type', # Map to the foreign key field in the model
        help_text=_("The UUID of the StoreType for this new store."),
        required=True
    )

    class Meta:
        model = Store
        fields = (
            'store_name', 'store_address', 'store_phone_number', 'store_contact_email',
            'store_login_email', 'store_tax_id', 'store_type_id'
        )
        extra_kwargs = {
            # Validators are handled in the validate method below
            'store_name': {'validators': []},
            'store_login_email': {'validators': []},
        }

    def validate(self, attrs):
        # Access original validated data after source mapping
        name = attrs.get('name') # Access the mapped model field name
        login_email = attrs.get('login_email') # Access the mapped model field name

        # Validate store name uniqueness
        if Store.objects.filter(name__iexact=name).exists():
            raise serializers.ValidationError({"store_name": _("A store with this name already exists.")})
        
        # Validate store login email uniqueness
        # Check against existing Stores and UserAccounts (since a UserAccount will be created/linked)
        if Store.objects.filter(login_email__iexact=login_email).exists():
            raise serializers.ValidationError({"store_login_email": _("A store with this primary login email already exists.")})
        
        # Check if an existing UserAccount already uses this email
        if User.objects.filter(email__iexact=login_email).exists():
            raise serializers.ValidationError({"store_login_email": _("A user account with this email already exists.")})

        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            # validated_data now contains the correctly mapped model fields,
            # so we can directly create the Store instance.
            # Example: validated_data will have 'name', 'address', 'login_email', 'store_type' etc.
            store = Store.objects.create(**validated_data)
        return store


# --- CustomTokenObtainPairSerializer ---
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom serializer for obtaining JWT tokens, allowing authentication
    using email or username.
    It returns additional user information including the role.
    """
    # Use the username field as defined in the User model (which is 'email' in our CustomUserAccount)
    username_field = User.USERNAME_FIELD # This will dynamically get 'email' from UserAccount

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure 'username' and 'email' fields are explicitly available for input
        # Allowing either username or email for login
        self.fields[self.username_field] = serializers.CharField(write_only=True, required=False) # This is 'email'
        if self.username_field != 'username': # Add username if it's not the primary login field
            self.fields['username'] = serializers.CharField(write_only=True, required=False)
        self.fields['password'] = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate(self, attrs):
        email_input = attrs.get('email') # Check for email
        username_input = attrs.get('username') # Check for username

        if not (email_input or username_input):
            raise serializers.ValidationError(_("Must provide email or username to log in."))

        user = None
        # Try to authenticate using email first
        if email_input:
            user = authenticate(request=self.context.get('request'), email=email_input, password=attrs.get("password"))
        
        # If not authenticated by email, try with username
        if not user and username_input:
            user = authenticate(request=self.context.get('request'), username=username_input, password=attrs.get("password"))

        if not user:
            raise serializers.ValidationError(_("No active account found with the given credentials."))
        
        if not user.is_active:
            raise serializers.ValidationError(_("User account is inactive."))

        # This line is crucial for TokenObtainPairSerializer to work correctly internally
        # It needs the value for the 'username_field' (which is 'email' for our UserAccount)
        attrs[self.username_field] = user.email

        # Call the parent's validate method to get tokens
        data = super().validate(attrs)

        # Add custom user data to the response
        data['user_id'] = str(user.user_id) # Using user_id (UUID) from our UserAccount model
        data['email'] = user.email
        data['username'] = user.username
        # Access the role name from the related Role object
        data['role_name'] = user.role.role_name if user.role else None
        data['message'] = _('Login successful.')

        return data
