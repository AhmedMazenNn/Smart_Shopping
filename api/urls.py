# C:\Users\DELL\SER SQL MY APP\api\urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('health-check/', views.health_check, name='health-check'),
    path('user-info/', views.user_info, name='user-info'),
    path('protected-data/', views.protected_data, name='protected-data'),
]
