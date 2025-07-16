# C:\Users\DELL\SER SQL MY APP\customers\views.py

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import serializers
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q, F # For using F() in quantity updates
from rest_framework.exceptions import PermissionDenied, ValidationError # Added ValidationError
from django.utils.translation import gettext_lazy as _

# Import models from the customers app
from .models import Customer, CustomerCart, CustomerCartItem, Rating

# Import models from other apps
from products.models import Product, BranchProductInventory # Updated for BranchProductInventory
from sales.models import Order, OrderItem # Import Order and OrderItem
from users.models import UserAccount, Role # Updated: Import UserAccount and Role

# Import serializers from the customers app
from .serializers import (
    CustomerSerializer,
    CustomerCartSerializer,
    CustomerCartItemSerializer,
    RatingSerializer
)

# Import CustomPermission (ensure it's updated to handle UserAccount roles)
from mysite.permissions import CustomPermission


# --- API ViewSets for Customer ---
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        # request.user will be an instance of UserAccount
        user_account = self.request.user

        # Superusers, App Owners, Project Managers, App Staff see all customers
        if user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager', 'app_staff']):
            return Customer.objects.all()
        
        # Customers see their own profile
        # Assuming Customer has a OneToOneField to UserAccount called 'user_account'
        if user_account.role and user_account.role.role_name == 'customer':
            return Customer.objects.filter(user_account=user_account)
        
        # Store Manager sees customers who have placed orders in their store's branches
        if user_account.role and user_account.role.role_name == 'store_manager' and hasattr(user_account, 'employee_profile') and user_account.employee_profile.store:
            return Customer.objects.filter(customer_orders__branch__store=user_account.employee_profile.store).distinct()
        
        # Branch Manager or General Staff/Cashier sees customers who have placed orders in their branch
        if user_account.role and user_account.role.role_name in ['branch_manager', 'general_staff', 'cashier', 'shelf_organizer', 'customer_service'] and hasattr(user_account, 'employee_profile') and user_account.employee_profile.branch:
            return Customer.objects.filter(customer_orders__branch=user_account.employee_profile.branch).distinct()
            
        return Customer.objects.none()

    def perform_create(self, serializer):
        user_account = self.request.user
        # Only Superusers, App Owners, or Project Managers can create customer profiles directly via this endpoint
        # Customers register through a different endpoint (`RegisterUserAPIView` or `CustomerRegistrationSerializer`)
        if not (user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager'])):
            raise PermissionDenied(_('Only Superusers, App Owners, or Project Managers can create customer profiles directly.'))
        serializer.save()

    def perform_update(self, serializer):
        # CustomPermission handles object-level permission checks
        serializer.save()

    def perform_destroy(self, instance):
        # CustomPermission handles object-level permission checks
        instance.delete()


# --- API ViewSets for Customer Carts ---
class CustomerCartViewSet(viewsets.ModelViewSet):
    queryset = CustomerCart.objects.all()
    serializer_class = CustomerCartSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission] # Using CustomPermission

    def get_queryset(self):
        user_account = self.request.user
        # App Owner / Superuser / Project Manager / App Staff sees all carts
        if user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager', 'app_staff']):
            return CustomerCart.objects.all()
        
        # Customers see their own carts
        # Assuming CustomerCart is linked to UserAccount or Customer profile
        if user_account.role and user_account.role.role_name == 'customer':
            return CustomerCart.objects.filter(customer__user_account=user_account) # Assuming CustomerCart has a ForeignKey to Customer
        
        # Store Manager sees carts in their store's branches
        if user_account.role and user_account.role.role_name == 'store_manager' and hasattr(user_account, 'employee_profile') and user_account.employee_profile.store:
            # Assumes CustomerCart has a ForeignKey 'branch' to a Branch model
            return CustomerCart.objects.filter(branch__store=user_account.employee_profile.store).distinct()
            
        # Branch Manager or Staff sees carts in their branch
        if user_account.role and user_account.role.role_name in ['branch_manager', 'general_staff', 'cashier', 'shelf_organizer', 'customer_service'] and hasattr(user_account, 'employee_profile') and user_account.employee_profile.branch:
            # Assumes CustomerCart has a ForeignKey 'branch' to a Branch model
            return CustomerCart.objects.filter(branch=user_account.employee_profile.branch).distinct()
            
        return CustomerCart.objects.none()

    def perform_create(self, serializer):
        user_account = self.request.user
        # Define roles allowed to create carts
        allowed_roles_for_cart_creation = [
            'customer', 'general_staff', 'cashier', 'branch_manager', 'store_manager'
        ]
        
        if not (user_account.is_superuser or 
                (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager']) or
                (user_account.role and user_account.role.role_name in allowed_roles_for_cart_creation)):
            raise PermissionDenied(_('You do not have permission to create a cart.'))
            
        serializer.save(user=user_account) # Pass the UserAccount instance if the serializer needs it for customer linkage


    def perform_update(self, serializer):
        # CustomPermission handles object-level permission checks
        serializer.save()

    def perform_destroy(self, instance):
        # CustomPermission handles object-level permission checks
        instance.delete()


# --- API ViewSets for Customer Cart Items ---
class CustomerCartItemViewSet(viewsets.ModelViewSet):
    queryset = CustomerCartItem.objects.all()
    serializer_class = CustomerCartItemSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission] # Using CustomPermission

    def get_queryset(self):
        user_account = self.request.user
        if user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager', 'app_staff']):
            return CustomerCartItem.objects.all()
        
        # Customers see items in their carts only
        if user_account.role and user_account.role.role_name == 'customer':
            return CustomerCartItem.objects.filter(cart__customer__user_account=user_account)
        
        # Store Manager sees cart items in their store's branches
        if user_account.role and user_account.role.role_name == 'store_manager' and hasattr(user_account, 'employee_profile') and user_account.employee_profile.store:
            return CustomerCartItem.objects.filter(cart__branch__store=user_account.employee_profile.store).distinct()
            
        # Branch Manager or Staff sees cart items in their branch
        if user_account.role and user_account.role.role_name in ['branch_manager', 'general_staff', 'cashier', 'shelf_organizer', 'customer_service'] and hasattr(user_account, 'employee_profile') and user_account.employee_profile.branch:
            return CustomerCartItem.objects.filter(cart__branch=user_account.employee_profile.branch).distinct()
            
        return CustomerCartItem.objects.none()

    def perform_create(self, serializer):
        # Logic for permission and inventory is handled in CustomerCartItemSerializer.validate() and .create()
        serializer.save()

    def perform_update(self, serializer):
        # Logic for permission and inventory is handled in CustomerCartItemSerializer.validate() and .update()
        serializer.save()

    def perform_destroy(self, instance):
        # Revert inventory quantity if the serializer's destroy method handles it
        # Otherwise, simply delete the instance.
        # Assuming the serializer's destroy method will handle inventory adjustment.
        # The default behavior of DRF is to call instance.delete() here.
        # If your CustomerCartItemSerializer.destroy() method is meant to be called directly,
        # you might need to adjust it there. For now, we'll let DRF's default proceed.
        instance.delete() # Reverted to standard DRF destroy


# --- API ViewSets for Ratings ---
class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.all() # Queryset will be filtered by get_queryset
    serializer_class = RatingSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission] # Using CustomPermission

    def get_queryset(self):
        user_account = self.request.user
        if user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager', 'app_staff']):
            return Rating.objects.all()
        
        # Customers see their own ratings
        # Assuming Rating has a ForeignKey to Customer, and Customer has OneToOne to UserAccount
        if user_account.role and user_account.role.role_name == 'customer':
            return Rating.objects.filter(customer__user_account=user_account)
        
        # Store Manager sees ratings for orders in their store's branches
        if user_account.role and user_account.role.role_name == 'store_manager' and hasattr(user_account, 'employee_profile') and user_account.employee_profile.store:
            return Rating.objects.filter(order__branch__store=user_account.employee_profile.store).distinct()
            
        # Branch Manager or Staff sees ratings for orders in their branch
        if user_account.role and user_account.role.role_name in ['branch_manager', 'general_staff', 'cashier', 'shelf_organizer', 'customer_service'] and hasattr(user_account, 'employee_profile') and user_account.employee_profile.branch:
            return Rating.objects.filter(order__branch=user_account.employee_profile.branch).distinct()

        return Rating.objects.none()

    def perform_create(self, serializer):
        # As per RatingSerializer.validate(), direct creation of ratings via API is generally not allowed.
        # Ratings are typically created automatically (e.g., via Signals after an order is completed)
        # and then updated by customers.
        raise PermissionDenied(_("Direct creation of ratings is not allowed. Ratings are created automatically for purchases."))

    def perform_update(self, serializer):
        # CustomPermission handles object-level permission checks
        # Update permissions are also handled in RatingSerializer.validate()
        serializer.save()

    def perform_destroy(self, instance):
        # CustomPermission handles object-level permission checks
        # Delete permissions are also handled in RatingSerializer.validate()
        instance.delete()

