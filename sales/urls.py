# C:\Users\DELL\SER SQL MY APP\sales\urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# استيراد جميع الـ ViewSets والـ APIView من views.py
from .views import (
    OrderViewSet,
    OrderItemViewSet,
    TempOrderViewSet,       # New ViewSet
    TempOrderItemViewSet,   # New ViewSet
    PaymentViewSet,         # New ViewSet
    ReturnViewSet,          # New ViewSet
    ReturnItemViewSet,      # New ViewSet
    ConvertTempOrderToOrderAPIView # New ViewSet for custom action
)

# إنشاء راوتر تلقائي لتوليد مسارات RESTful APIs
router = DefaultRouter()
router.register(r'orders', OrderViewSet)
router.register(r'order-items', OrderItemViewSet)
router.register(r'temp-orders', TempOrderViewSet)             # Register TempOrderViewSet
router.register(r'temp-order-items', TempOrderItemViewSet)   # Register TempOrderItemViewSet
router.register(r'payments', PaymentViewSet)                 # Register PaymentViewSet
router.register(r'returns', ReturnViewSet)                   # Register ReturnViewSet
router.register(r'return-items', ReturnItemViewSet)         # Register ReturnItemViewSet
router.register(r'convert-temp-order', ConvertTempOrderToOrderAPIView, basename='convert-temp-order') # Register custom action ViewSet

urlpatterns = [
    # مسارات الـ API التي تم إنشاؤها بواسطة الراوتر
    path('', include(router.urls)),
]
