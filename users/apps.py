from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        # Import Firebase initialization to ensure Firebase Admin SDK is initialized when Django starts
        try:
            import mysite.firebase_app
            logger.info("Firebase Admin SDK import attempt in UsersConfig.ready()")
        except ImportError as e:
            logger.error(f"Warning: Could not import mysite.firebase_app in UsersConfig.ready(): {e}")
        except Exception as e:
            logger.error(f"Error during Firebase app initialization in UsersConfig.ready(): {e}")

        # Import signals to register them and avoid circular import issues
        try:
            import users.signals
            logger.info("Users app signals loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading users app signals: {e}", exc_info=True)
