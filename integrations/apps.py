# C:\Users\DELL\SER SQL MY APP\integrations\APPS
from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integrations'

    def ready(self):
        import integrations.signals
