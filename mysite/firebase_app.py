# C:\Users\DELL\SER SQL MY APP\mysite\firebase_app.py
import firebase_admin
from firebase_admin import credentials
from django.conf import settings
import os
import logging

logger = logging.getLogger(__name__)

# Check if the app has already been initialized
if not firebase_admin._apps:
    cred_path = settings.FIREBASE_ADMIN_SDK_CONFIG
    
    # Ensure the service account key file exists
    if not os.path.exists(cred_path):
        logger.error(f"Firebase service account key file not found at: {cred_path}")
        raise FileNotFoundError(f"ملف مفتاح حساب خدمة Firebase غير موجود. يرجى التحقق من مسار {cred_path} وتأكيد إعداد FIREBASE_ADMIN_SDK_CONFIG في settings.py.")

    try:
        # Initialize Firebase Admin SDK
        cred = credentials.Certificate(str(cred_path)) # Convert Path object to string
        firebase_admin.initialize_app(cred, {
            'projectId': settings.FIREBASE_PROJECT_ID,
        })
        logger.info("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        raise # Re-raise the exception to prevent the server from starting if initialization fails
else:
    logger.info("Firebase Admin SDK already initialized.")

# You can import this file anywhere you need to interact with the Firebase Admin SDK
# Example: from your Authentication class or in Views to manage users
