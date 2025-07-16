# C:\Users\DELL\SER SQL MY APP\users\urls.py

from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from .views import RegisterUserAPIView # <<< تم استيراد RegisterUserAPIView


urlpatterns = [
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('register/', RegisterUserAPIView.as_view(), name='register_user'), # <<< تم إضافة مسار التسجيل
]