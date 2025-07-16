# C:\Users\DELL\SER SQL MY APP\customers\apps.py

from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'customers'
    verbose_name = 'العملاء'

    def ready(self):
        import customers.signals
