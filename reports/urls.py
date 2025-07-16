# C:\Users\DELL\SER SQL MY APP\reports\urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
# من المفترض أن يكون لديك ViewSets هنا لتطبيق reports
# على سبيل المثال:
# from .views import ReportViewSet

router = DefaultRouter()
# router.register(r'reports', ReportViewSet) # قم بإلغاء التعليق عند إنشاء ViewSet الخاص بالتقارير

urlpatterns = [
    path('', include(router.urls)),
    # يمكنك إضافة مسارات يدوية هنا إذا لم تستخدم ViewSets
    # path('some-report/', SomeReportView.as_view(), name='some_report'),
]
