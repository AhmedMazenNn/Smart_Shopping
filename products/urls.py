# C:\Users\DELL\SER SQL MY APP\products\urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# استيراد جميع الـ ViewSets والـ APIView من views.py
from .views import (
    DepartmentViewSet,
    ProductViewSet,
    ProductCategoryViewSet,
    BranchProductInventoryViewSet,
    ProductUploadExcelView,
    ScanBarcodeAPIView
)

# إنشاء راوتر تلقائي لتوليد مسارات RESTful APIs
router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'products', ProductViewSet)
router.register(r'product-categories', ProductCategoryViewSet)
router.register(r'branch-product-inventories', BranchProductInventoryViewSet)
router.register(r'product-excel-upload', ProductUploadExcelView, basename='product-excel-upload')

urlpatterns = [
    # مسارات الـ API التي تم إنشاؤها بواسطة الراوتر
    path('', include(router.urls)),

    # مسار خاص لـ API مسح الباركود (يبقى كما هو لأنه APIView)
    path('scan_barcode/', ScanBarcodeAPIView.as_view(), name='scan-barcode'),
]
