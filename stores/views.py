# C:\Users\DELL\SER SQL MY APP\stores\views.py

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import serializers # For showing ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone

# Import models from the stores app
from .models import Store, Branch, StorePermissionProfile, BranchPermissionProfile # Added permission models

# Import CustomUser for new helper functions
from django.contrib.auth import get_user_model
User = get_user_model()


# Import serializers from the stores app
from .serializers import (
    StoreSerializer,
    BranchSerializer,
    StorePermissionProfileSerializer, # Added permission profile serializer
    BranchPermissionProfileSerializer, # Added permission profile serializer
)

# Import CustomPermission from its new shared file
from mysite.permissions import CustomPermission


# --- API ViewSets for Store Permission Profiles ---
class StorePermissionProfileViewSet(viewsets.ModelViewSet):
    queryset = StorePermissionProfile.objects.all()
    serializer_class = StorePermissionProfileSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        # Only superuser or app owner can view all permission profiles
        if user.is_superuser or user.is_app_owner():
            return StorePermissionProfile.objects.all()
        # Other roles cannot view permission profiles here
        return StorePermissionProfile.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        # Only superuser or app owner can create new permission profiles
        if user.is_superuser or user.is_app_owner():
            serializer.save(created_by=user)
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لإنشاء ملف صلاحيات المتجر.'})

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object() # The profile being updated
        # Only superuser or app owner can update any permission profile
        if user.is_superuser or user.is_app_owner():
            serializer.save()
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لتعديل ملف صلاحيات المتجر هذا.'})

    def perform_destroy(self, instance):
        user = self.request.user
        # Only superuser or app owner can delete permission profiles
        if user.is_superuser or user.is_app_owner():
            instance.delete()
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لحذف ملف صلاحيات المتجر هذا.'})


# --- API ViewSets for Branch Permission Profiles ---
class BranchPermissionProfileViewSet(viewsets.ModelViewSet):
    queryset = BranchPermissionProfile.objects.all()
    serializer_class = BranchPermissionProfileSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        # Only superuser or app owner can view all permission profiles
        if user.is_superuser or user.is_app_owner():
            return BranchPermissionProfile.objects.all()
        # Other roles cannot view permission profiles here
        return BranchPermissionProfile.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        # Only superuser or app owner can create new permission profiles
        if user.is_superuser or user.is_app_owner():
            serializer.save(created_by=user)
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لإنشاء ملف صلاحيات الفرع.'})

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object() # The profile being updated
        # Only superuser or app owner can update any permission profile
        if user.is_superuser or user.is_app_owner():
            serializer.save()
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لتعديل ملف صلاحيات الفرع هذا.'})

    def perform_destroy(self, instance):
        user = self.request.user
        # Only superuser or app owner can delete permission profiles
        if user.is_superuser or user.is_app_owner():
            instance.delete()
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لحذف ملف صلاحيات الفرع هذا.'})


# --- API ViewSets for Stores ---
class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        # Application owner/Superuser sees all stores
        if user.is_superuser or user.is_app_owner():
            return Store.objects.all()
        # Store manager sees only their store
        # Ensure user.store exists before attempting to access id
        if user.is_store_manager_user() and hasattr(user, 'store') and user.store:
            return Store.objects.filter(id=user.store.id)
        # Other roles do not see stores here by default
        return Store.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        # Only app owner/superuser can create new stores
        if user.is_superuser or user.is_app_owner():
            serializer.save(created_by=user)
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لإنشاء متجر.'})

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object() # The store being updated

        # App owner/Superuser can update any store
        if user.is_superuser or user.is_app_owner():
            pass
        # Store manager can only update their own store
        elif user.is_store_manager_user() and hasattr(user, 'store') and user.store == instance:
            pass
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لتعديل هذا المتجر.'})
        
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        # Only app owner/superuser can delete stores
        if user.is_superuser or user.is_app_owner():
            instance.delete()
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لحذف هذا المتجر.'})


# --- API ViewSets for Branches ---
class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_app_owner():
            return Branch.objects.all()
        # Store manager sees only branches of their store
        if user.is_store_manager_user() and hasattr(user, 'store') and user.store:
            return Branch.objects.filter(store=user.store)
        # Branch manager sees only their branch
        # NOTE: The 'user.department' attribute is assumed to exist and link to a branch
        if user.is_branch_manager_user() and hasattr(user, 'department') and user.department and user.department.branch:
            return Branch.objects.filter(id=user.department.branch.id)
        # Cashiers and other staff see only their branch
        # NOTE: The 'user.department' attribute is assumed to exist and link to a branch
        if user.user_type in ['cashier', 'shelf_organizer', 'staff'] and hasattr(user, 'department') and user.department and user.department.branch:
            return Branch.objects.filter(id=user.department.branch.id)
        
        return Branch.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        store = serializer.validated_data.get('store')

        if not store:
            raise serializers.ValidationError({'store': 'يجب تحديد المتجر للفرع.'})

        # App owner/Superuser can create branches for any store
        if user.is_superuser or user.is_app_owner():
            pass
        # Store manager can create branches only for their own store
        elif user.is_store_manager_user() and hasattr(user, 'store') and user.store == store:
            pass
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لإنشاء فروع لهذا المتجر.'})

        serializer.save(created_by=user)

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object() # The branch being updated
        new_store = serializer.validated_data.get('store', instance.store)

        # App owner/Superuser can update any branch
        if user.is_superuser or user.is_app_owner():
            pass
        # Store manager can only update branches within their own store, and cannot move the branch to another store
        elif user.is_store_manager_user() and hasattr(user, 'store') and user.store == instance.store:
            if new_store != instance.store:
                raise serializers.ValidationError({'error': 'لا يمكنك نقل فرع إلى متجر آخر.'})
        # Branch manager can only update their own branch, and cannot change its store
        elif user.is_branch_manager_user() and hasattr(user, 'department') and user.department and user.department.branch == instance:
            if new_store != instance.store:
                raise serializers.ValidationError({'error': 'لا يمكنك نقل فرعك إلى متجر آخر.'})
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لتعديل هذا الفرع.'})
        
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        # Only app owner/Superuser can delete branches
        if user.is_superuser or user.is_app_owner():
            instance.delete()
        # Store manager can delete branches within their own store only
        elif user.is_store_manager_user() and hasattr(user, 'store') and user.store == instance.store:
            instance.delete()
        else:
            raise serializers.ValidationError({'error': 'ليس لديك الصلاحية لحذف هذا الفرع.'})
