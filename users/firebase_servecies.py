import firebase_admin
from firebase_admin import auth, exceptions as firebase_exceptions
import logging
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

def create_firebase_user(email, password, display_name, is_active=True):
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
            disabled=not is_active
        )
        return user.uid
    except firebase_exceptions.FirebaseError as e:
        raise ValidationError(_(f"Firebase error: {e.message}"))

def update_firebase_user(uid, email, password=None, display_name=None, is_active=True):
    try:
        data = {
            'email': email,
            'display_name': display_name,
            'disabled': not is_active,
        }
        if password:
            data['password'] = password
        auth.update_user(uid, **data)
    except firebase_exceptions.FirebaseError as e:
        raise ValidationError(_(f"Firebase update error: {e.message}"))

def get_existing_firebase_user_uid(email):
    try:
        return auth.get_user_by_email(email).uid
    except firebase_exceptions.FirebaseError as e:
        raise ValidationError(_(f"Could not fetch Firebase user: {e.message}"))
