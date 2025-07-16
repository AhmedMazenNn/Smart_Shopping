# C:\Users\DELL\SER SQL MY APP\stores\urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StoreViewSet,
    BranchViewSet,
    StorePermissionProfileViewSet,  # New: Import StorePermissionProfileViewSet
    BranchPermissionProfileViewSet, # New: Import BranchPermissionProfileViewSet
)

# Create a router to register the ViewSets
router = DefaultRouter()
router.register(r'stores', StoreViewSet)
router.register(r'branches', BranchViewSet)
router.register(r'store-permission-profiles', StorePermissionProfileViewSet) # New: Register StorePermissionProfileViewSet
router.register(r'branch-permission-profiles', BranchPermissionProfileViewSet) # New: Register BranchPermissionProfileViewSet

urlpatterns = [
    # API paths created by the router
    path('', include(router.urls)),
]

# >>>>>> تأكد من عدم وجود أي كود آخر هنا، خاصة @admin.register(Store) أو @admin.register(Branch) <<<<<<
