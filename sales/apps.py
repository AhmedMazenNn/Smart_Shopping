# C:\Users\DELL\SER SQL MY APP\sales\apps.py

from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sales'
    verbose_name = 'المبيعات' # إضافة اسم عرض للتطبيق في لوحة الإدارة

    def ready(self):
        """
        يتم استدعاء هذه الدالة عند بدء تشغيل تطبيق Django.
        نستخدمها لاستيراد ملف signals.py لضمان تحميل الإشارات.
        """
        import sales.signals # <--- إضافة هذا السطر لاستيراد الإشارات