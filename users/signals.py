# C:\Users\DELL\SER SQL MY APP\users\signals.py

import firebase_admin
from firebase_admin import auth, exceptions as firebase_exceptions
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import UserAccount  # تأكد من استيراد نموذج المستخدم الصحيح
import logging

logger = logging.getLogger(__name__)

@receiver(post_delete, sender=UserAccount)
def delete_firebase_user(sender, instance, **kwargs):
    """
    يحذف المستخدم المقابل في Firebase Authentication بعد حذف UserAccount في Django.
    """
    if instance.firebase_uid:  # تأكد أن لدينا firebase_uid لحذفه
        try:
            auth.delete_user(instance.firebase_uid)
            logger.info(f"Firebase user with UID {instance.firebase_uid} deleted successfully.")
        except firebase_exceptions.FirebaseError as e:
            # يمكن أن يحدث هذا إذا كان المستخدم غير موجود بالفعل في Firebase
            logger.warning(f"Failed to delete Firebase user with UID {instance.firebase_uid}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error while deleting Firebase user {instance.firebase_uid}: {e}", exc_info=True)
    else:
        logger.warning(f"UserAccount {instance.username if hasattr(instance, 'username') else instance.pk} (ID: {instance.id}) has no firebase_uid. Skipping Firebase deletion.")