# C:\Users\DELL\SER SQL MY APP\authentication\urls.py

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .views import (
    LoginAPIView,
    CustomerRegisterAPIView,
    StoreRegisterAPIView,  # تم تغيير الاسم ليعكس الغرض: تسجيل كيان المتجر
    UserProfileView,
)

urlpatterns = [
    # مسار تسجيل الدخول باستخدام البريد الإلكتروني أو اسم المستخدم (يعيد توكن JWT)
    path('login/', LoginAPIView.as_view(), name='token_obtain_pair'),

    # مسار تحديث توكن JWT
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # مسار التحقق من صلاحية التوكن
    path('verify/', TokenVerifyView.as_view(), name='token_verify'),

    # مسار تسجيل العملاء (سيعمل على إنشاء UserAccount ودور Customer)
    path('register/customer/', CustomerRegisterAPIView.as_view(), name='register_customer'),

    # مسار تسجيل المتجر (سيعمل على إنشاء كيان Store فقط، وليس حساب مستخدم للمتجر)
    # إدارة حسابات المستخدمين (مثل مديري المتاجر) ستتم بشكل منفصل كـ Employee
    path('register/store/', StoreRegisterAPIView.as_view(), name='register_store'),

    # مسار تسجيل عام للعملاء (اختياري: إذا أردت نقطة وصول عامة لـ 'register')
    # سيتم توجيهها إلى CustomerRegisterAPIView افتراضياً لتسهيل الاستخدام
    path('register/', CustomerRegisterAPIView.as_view(), name='register_default'),

    # نقطة وصول لملف تعريف المستخدم الحالي (لجلب بيانات UserAccount المرتبط)
    path('profile/', UserProfileView.as_view(), name='user_profile'),
]
