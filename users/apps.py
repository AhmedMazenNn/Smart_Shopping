# C:\Users\DELL\SER SQL MY APP\users\apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        # استيراد ملف تهيئة Firebase لضمان تشغيله عند بدء تشغيل التطبيق
        # هذا يضمن تهيئة Firebase Admin SDK بمجرد أن تكون تطبيقات Django جاهزة
        try:
            import mysite.firebase_app
            logger.info("Firebase Admin SDK import attempt in UsersConfig.ready()")
        except ImportError as e:
            logger.error(f"Warning: Could not import mysite.firebase_app in UsersConfig.ready(): {e}")
        except Exception as e:
            logger.error(f"Error during Firebase app initialization in UsersConfig.ready(): {e}")

        # استيراد signals هنا لتجنب مشاكل الاستيراد الدائري وضمان تفعيل الإشارات
        try:
            import users.signals
            logger.info("Users app signals loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading users app signals: {e}", exc_info=True)