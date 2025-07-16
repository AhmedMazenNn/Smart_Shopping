# C:\Users\DELL\SER SQL MY APP\users\views.py

from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction # For managing database transactions
from django.db.models import Q # For complex queries
from django.utils.translation import gettext_lazy as _
# from django.contrib.auth.hashers import make_password # No longer directly needed if using serializer's save

# Import the new UserAccount model directly
from .models import UserAccount, Role # Renamed from UserType
from .serializers import RegisterSerializer, UserAccountSerializer # Renamed UserSerializer to UserAccountSerializer
from mysite.permissions import IsAppOwner, IsStaffUser, IsStoreManager, IsBranchManager, IsProjectManager, IsStoreAccount


# --- Public Authentication/Registration Views ---

class RegisterView(generics.CreateAPIView):
    """
    API View for public user registration.
    Allows new users to create an account with a self-provided password.
    Uses the RegisterSerializer, which now handles Customer/Employee profile creation.
    """
    queryset = UserAccount.objects.all() # Use UserAccount
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # The create method in RegisterSerializer handles UserAccount creation
        # and password setting, as well as associated Customer/Employee profiles.
        user_account = serializer.save()

        refresh = RefreshToken.for_user(user_account)
        response_data = {
            'message': _('User registered successfully.'),
            'user': serializer.data, # Serializer data will include main UserAccount fields
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom Token Obtain Pair View to include user role details and profile info
    in the response upon successful login.
    """
    # Uses the default TokenObtainPairSerializer internally for validation,
    # but we override post to add custom data.
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            # The email/username used for login is in request.data, but the validated
            # user object is usually available from the super call context if needed.
            # For simplicity, we'll try to get the user based on the email from request data.
            try:
                user_account = UserAccount.objects.get(email__iexact=request.data.get('email'))
            except UserAccount.DoesNotExist:
                # This case should ideally be caught by the TokenObtainPairSerializer validation,
                # but it's a safeguard.
                return Response({'detail': _('No user found with the provided credentials.')}, status=status.HTTP_400_BAD_REQUEST)
            
            response.data['user_id'] = user_account.id
            response.data['username'] = user_account.username
            response.data['email'] = user_account.email
            response.data['role_name'] = user_account.role.role_name # New: role_name from Role model
            response.data['role_display'] = user_account.role.display_name # New: display_name from Role model
            response.data['is_staff'] = user_account.is_staff
            response.data['is_superuser'] = user_account.is_superuser
            response.data['is_temporary_password'] = user_account.is_temporary_password
            response.data['first_name'] = user_account.first_name
            response.data['last_name'] = user_account.last_name
            
            # Access job_title, store, branch, department from Employee profile
            if hasattr(user_account, 'employee_profile') and user_account.employee_profile:
                employee_profile = user_account.employee_profile
                response.data['job_title'] = employee_profile.job_title
                response.data['store_id'] = employee_profile.store.id if employee_profile.store else None
                response.data['branch_id'] = employee_profile.branch.id if employee_profile.branch else None
                response.data['department_id'] = employee_profile.department.id if employee_profile.department else None
                response.data['commission_percentage'] = employee_profile.commission_percentage
                response.data['tax_id'] = employee_profile.tax_id
            else: # Ensure these keys exist even if null for consistency
                response.data['job_title'] = None
                response.data['store_id'] = None
                response.data['branch_id'] = None
                response.data['department_id'] = None
                response.data['commission_percentage'] = None
                response.data['tax_id'] = None

            # Add phone_number, which could be on Customer or Employee profile
            response.data['phone_number'] = user_account.get_phone_number # Assumes get_phone_number property on UserAccount
        return response

class ChangePasswordView(generics.UpdateAPIView):
    """
    API View for changing user password.
    Requires user to be authenticated.
    Also handles changing is_temporary_password to False upon successful change.
    """
    serializer_class = UserAccountSerializer # Use the new UserAccountSerializer
    model = UserAccount # Use UserAccount
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self, queryset=None):
        obj = self.request.user # request.user will be a UserAccount instance
        return obj

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Use a dedicated serializer for password change if the main serializer has too many fields
        # For now, we'll rely on UserAccountSerializer's update method.
        # Pass data explicitly for partial update.
        
        old_password = request.data.get("old_password")
        new_password = request.data.get("password") 
        new_password2 = request.data.get("password2")

        if not self.object.check_password(old_password):
            return Response({"old_password": _("Wrong password.")}, status=status.HTTP_400_BAD_REQUEST)
            
        if not new_password or not new_password2 or new_password != new_password2:
            return Response({"password": _("New passwords didn't match or are empty.")}, status=status.HTTP_400_BAD_REQUEST)

        # The UserAccountSerializer's update method handles setting the password
        # and updating is_temporary_password.
        serializer = self.get_serializer(self.object, data={'password': new_password, 'password2': new_password2}, partial=True)
        serializer.is_valid(raise_exception=True)
        user_account = serializer.save() # This will update the password and set is_temporary_password=False

        response = {
            'status': 'success',
            'code': status.HTTP_200_OK,
            'message': _('Password updated successfully'),
            'user_id': user_account.id, # Optionally return user ID
            'is_temporary_password': user_account.is_temporary_password # Should be False
        }

        return Response(response)

# --- User Management API (for privileged users) ---

class UserManagementViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for managing users (CRUD operations).
    Accessible by App Owners, Project Managers, Store Accounts, and Store Managers
    based on the specific action and user's role.
    """
    queryset = UserAccount.objects.all().order_by('email') # Use UserAccount
    serializer_class = UserAccountSerializer # Use UserAccountSerializer
    
    def get_permissions(self):
        """
        Custom permissions based on action and user's role.
        The custom permissions (IsAppOwner, IsStaffUser, etc.)
        must be updated to check against request.user.role.role_name.
        """
        if self.action == 'list':
            # App Owners, Project Managers, Store Accounts, Store Managers, Branch Managers
            # (and other staff if IsStaffUser covers them) can list users.
            self.permission_classes = [IsAppOwner | IsProjectManager | IsStoreAccount | IsStoreManager | IsBranchManager | IsStaffUser]
        elif self.action == 'create':
            # Only specific roles can create users
            self.permission_classes = [IsAppOwner | IsProjectManager | IsStoreAccount | IsStoreManager | IsBranchManager]
        elif self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            # App Owners have full control.
            # Project Managers can see/modify most users (not App Owners).
            # Store Accounts can see/modify their own store's staff.
            # Store Managers can see/modify their own store's staff.
            # Branch Managers can see/modify their own branch's staff.
            self.permission_classes = [IsAppOwner | IsProjectManager | IsStoreAccount | IsStoreManager | IsBranchManager]
        else:
            self.permission_classes = [permissions.IsAdminUser] # Safe default

        return [permission() for permission in self.permission_classes]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            user_account = serializer.save() # UserAccountSerializer's create handles profile creation & temp password

            response_data = serializer.data
            # If a temporary password was generated by the serializer, include it in the response
            # The serializer should have set `user_account.generated_password` attribute for display
            if hasattr(user_account, 'generated_password') and user_account.is_temporary_password:
                response_data['generated_password'] = user_account.generated_password
                
        headers = self.get_success_headers(serializer.data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object() # This is the UserAccount instance
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            user_account = serializer.save() # UserAccountSerializer's update handles password, role, and profile updates

            response_data = serializer.data
            # If a temporary password was generated by the serializer during update, include it
            if hasattr(user_account, 'generated_password') and user_account.is_temporary_password:
                response_data['generated_password'] = user_account.generated_password
                
        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied, invalidate cache
            instance._prefetched_objects_cache = {}

        return Response(response_data)

    def get_queryset(self):
        """
        Filters the queryset based on the requesting user's role and associated store/branch.
        """
        user_requesting = self.request.user # This is the authenticated UserAccount
        queryset = super().get_queryset()

        if user_requesting.role.role_name == 'app_owner':
            return queryset # App Owner sees all users
        elif user_requesting.role.role_name == 'project_manager':
            # Project Managers see all users except App Owners
            return queryset.exclude(role__role_name='app_owner')
        elif user_requesting.role.role_name == 'store_account' and hasattr(user_requesting, 'employee_profile') and user_requesting.employee_profile.store:
            # Store Account sees users within their store, including themselves
            return queryset.filter(
                Q(employee_profile__store=user_requesting.employee_profile.store) |
                Q(customer_profile__isnull=False) | # Include all customers
                Q(pk=user_requesting.pk)
            ).distinct()
        elif user_requesting.role.role_name == 'store_manager' and hasattr(user_requesting, 'employee_profile') and user_requesting.employee_profile.store:
            # Store Manager sees users within their store, including themselves
            return queryset.filter(
                Q(employee_profile__store=user_requesting.employee_profile.store) |
                Q(customer_profile__isnull=False) | # Include all customers
                Q(pk=user_requesting.pk)
            ).distinct()
        elif user_requesting.role.role_name == 'branch_manager' and hasattr(user_requesting, 'employee_profile') and user_requesting.employee_profile.branch:
            # Branch Manager sees users within their branch, including themselves
            return queryset.filter(
                Q(employee_profile__branch=user_requesting.employee_profile.branch) |
                Q(customer_profile__isnull=False) | # Include all customers
                Q(pk=user_requesting.pk)
            ).distinct()
        else:
            # Default: any other staff or regular customer only sees their own profile
            return queryset.filter(pk=user_requesting.pk)

# --- User Profile View (for self-management) ---

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    API View for authenticated users to retrieve and update their own profile.
    Uses UserProfileSerializer (read-only for most fields, allowing specific updates).
    """
    queryset = UserAccount.objects.all()
    serializer_class = UserAccountSerializer # Using the comprehensive serializer for now
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user # Return the authenticated user's profile

    def get_serializer(self, *args, **kwargs):
        # Override to ensure partial update is always allowed for self-profile updates
        kwargs['partial'] = True
        return super().get_serializer(*args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # Disallow changing sensitive fields directly from user profile endpoint
        # The UserAccountSerializer's update method handles profile changes,
        # but here we can restrict what a user can *send* to update their own profile.
        # This is a security measure.
        restricted_fields = ['role', 'is_staff', 'is_superuser', 'is_active', 'is_temporary_password',
                             'store', 'branch', 'department', 'tax_id', 'commission_percentage']
        
        for field in restricted_fields:
            if field in request.data:
                return Response(
                    {"detail": _(f"You cannot change the '{field}' field from this endpoint.")},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Allow updating name, email, phone_number, job_title for self-profile
        # Note: If email is changed, it might affect login.
        # Phone number might be on customer_profile or employee_profile, serializer should handle
        # Job title should only be updatable if the user *has* an employee profile.

        with transaction.atomic():
            user_account = serializer.save()

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(self.get_serializer(user_account).data)