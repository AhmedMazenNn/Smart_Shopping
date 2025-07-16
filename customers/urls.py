# C:\Users\DELL\SER SQL MY APP\customers\urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# استيراد جميع الـ ViewSets من views.py
from .views import CustomerViewSet, CustomerCartViewSet, CustomerCartItemViewSet, RatingViewSet

# إنشاء راوتر تلقائي لتوليد مسارات RESTful APIs
router = DefaultRouter()
router.register(r'customers', CustomerViewSet)        # تسجيل CustomerViewSet
router.register(r'carts', CustomerCartViewSet)
router.register(r'cart-items', CustomerCartItemViewSet)
router.register(r'ratings', RatingViewSet)

urlpatterns = [
    # مسارات الـ API التي تم إنشاؤها بواسطة الراوتر
    path('', include(router.urls)),
]
