# C:\Users\DELL\SER SQL MY APP\customers\apps.py

from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'customers'
    verbose_name = 'العملاء'

    def ready(self):
        """
        تُستدعى هذه الدالة عند بدء تشغيل تطبيق Django.
        لا يوجد signals.py داخل Customers حاليًا، لذا لا حاجة لاستيراد إشارات هنا.
        إذا أضفت إشارات لاحقًا، فقم باستيرادها هنا.
        """
        # import customers.signals # <--- قم بإلغاء التعليق إذا كان لديك signals.py في تطبيق customers
        pass # <--- استخدم pass إذا لم يكن هناك أي شيء آخر تفعله في ready()
