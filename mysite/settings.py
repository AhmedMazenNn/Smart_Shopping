# C:\Users\DELL\SER SQL MY APP\mysite\settings.py

"""
Django settings for mysite project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
import subprocess
import platform
import firebase_admin
from firebase_admin import credentials, exceptions as firebase_exceptions
import logging

# Initialize logger for settings file
logger = logging.getLogger(__name__)


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-nox)nz_q@g!ki9g7y0yw8g@9_nbjeg-71k3ptxzq-susi&(6^p')


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# --- UPDATE THIS LINE ---
# Add your local machine's IP address if accessing from a different network (like Replit).
# AND add your Ngrok domain.
# For production, this list should contain your actual domain names, not just '*'.
ALLOWED_HOSTS = [
    '192.168.250.222',
    'localhost',
    '127.0.0.1',
    # أضف نطاق Ngrok هنا. في الإنتاج، استبدل هذا بالنطاق الفعلي.
    'ad04-2a02-9b0-4016-84dd-a98b-146b-584e-d02e.ngrok-free.app',
    # أضف النطاقات الفرعية لـ Replit إذا كنت تستخدمها
    '.replit.dev', # يسمح بجميع النطاقات الفرعية لـ replit.dev
]


# Application definition

INSTALLED_APPS = [
    # Django CORS Headers should be listed here only once
    'corsheaders',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Django REST Framework and JWT apps
    'rest_framework',
    'rest_framework_simplejwt', # Keep this installed even if Firebase is primary,
                                 # as CustomTokenObtainPairSerializer might extend from it.

    # Your custom apps
    'users',
    'stores',
    'products',
    'sales',
    'reports',
    'customers',
    'authentication', # This app will contain the FirebaseAuthentication Backend
    'api',

    # New app for integrations
    'integrations',

    # Background task queue for async operations and scheduled tasks
    'django_q',
]

MIDDLEWARE = [
    # CORS middleware must be at the very top
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware', # For i18n/l10n
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mysite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # This path is crucial for new HTML templates
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mysite.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'RetailChainDB', # تأكد أن هذا مطابق لاسم قاعدة البيانات التي أنشأتها
        'USER': 'postgres', # اسم مستخدم PostgreSQL الخاص بك
        'PASSWORD': '1234', # كلمة مرور PostgreSQL الخاصة بك
        'HOST': 'localhost',
        'PORT': '5432',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/databases/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'ar-sa' # Default language for the application

# It's better to set this to a more specific timezone if your application is for a specific country
TIME_ZONE = 'Asia/Riyadh'

USE_I18N = True # Enable internationalization support
USE_L10N = True # Enable localization support (important for formats)

USE_TZ = True # Ensure this is True if you use `timezone.now()` in models or views

# List of supported languages in the application
LANGUAGES = [
    ('ar', _('Arabic')),
    ('en', _('English')),
    ('ur', _('Urdu')),
    ('fr', _('French')),
    ('tr', _('Turkish')),
]

# Path to the directory for translation files (.po files)
LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# Media files (user uploaded content, like product images, QR code images)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework Settings - IMPORTANT for Firebase Authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # Use our custom authentication class to verify Firebase ID Tokens
        'authentication.backends.FirebaseAuthentication', # <--- UPDATED PATH to backends.FirebaseAuthentication
        # 'rest_framework_simplejwt.authentication.JWTAuthentication', # يمكنك إبقاء هذا إذا كنت تستخدم JWT بخلاف Firebase
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated', # Default to requiring authentication
    )
}

# IMPORTANT: Specify your custom user model
AUTH_USER_MODEL = 'users.UserAccount' # <--- تم تعديل هذا السطر: يشير إلى UserAccount الآن

# JWT settings are not directly used if Firebase handles authentication,
# but can be kept if you have other JWT-based services.
# إذا كنت لا تستخدم JWT لتوليد التوكنات (أي تعتمد فقط على Firebase)، يمكن حذف rest_framework_simplejwt من INSTALLED_APPS
# ولكن إذا كنت تستخدم CustomTokenObtainPairSerializer لإنشاء توكنات JWT يدوياً (حتى لو كانت المصادقة من Firebase)، يجب إبقاءها.
# بما أننا نستخدمها في CustomTokenObtainPairSerializer، فمن الأفضل إبقاؤها.
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60), # توكنات الوصول صالحة لمدة 60 دقيقة
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1), # توكنات التحديث صالحة لمدة يوم واحد
    'ROTATE_REFRESH_TOKENS': True, # تدوير توكنات التحديث في كل مرة يتم فيها تحديث التوكن
    'BLACKLIST_AFTER_ROTATION': True, # وضع توكنات التحديث القديمة في القائمة السوداء بعد التدوير
    'UPDATE_LAST_LOGIN': True, # تحديث حقل last_login في نموذج المستخدم
    
    'ALGORITHM': 'HS256', # خوارزمية التوقيع
    # ** التحديث هنا لاستخدام JWT_SIGNING_KEY **
    'SIGNING_KEY': os.environ.get('JWT_SIGNING_KEY', SECRET_KEY), # استخدم JWT_SIGNING_KEY من المتغيرات البيئية
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'user_id', # <--- هام: يشير إلى حقل الـ UUID في UserAccount
    'USER_ID_CLAIM': 'user_id', # <--- هام: يشير إلى الـ claim في التوكن
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}


# --- CORS SETTINGS ---
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5000",  # أضف هذا لدعم VITE_API_URL إذا كان frontend يعمل عليه
    "http://127.0.0.1:5000",  # أضف هذا لدعم VITE_API_URL إذا كان frontend يعمل عليه
    # If your frontend is accessed directly via IP on the network:
    # "http://192.168.250.222:5000", # أضف هذا إذا كان الـ frontend يعمل على هذا الـ IP والمنفذ
    # أضف نطاق Ngrok هنا إذا كان مختلفًا عن ما في ALLOWED_HOSTS
    f"https://{os.environ.get('NGROK_DOMAIN', 'ad04-2a02-9b0-4016-84dd-a98b-146b-584e-d02e.ngrok-free.app')}",
]
# في بيئة الإنتاج، يجب استخدام CORS_ALLOWED_ORIGIN_REGEXES أو CORS_ALLOWED_ORIGINS فقط
# وتجنب CORS_ALLOW_ALL_ORIGINS = True لأسباب أمنية.
# إذا كنت تستخدم CORS_ALLOWED_ORIGINS، فتأكد أن CORS_ALLOW_ALL_ORIGINS غير مفعل أو False.
# يمكن أن يكون هذا مفيدًا للسماح بالنطاقات الفرعية الديناميكية مثل Replit:
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https:\/\/.*\.replit\.dev$",
]
# ** تأكد من أن CORS_ALLOW_ALL_ORIGINS ليس True إذا كنت تستخدم CORS_ALLOWED_ORIGINS أو REGEXES **
# CORS_ALLOW_ALL_ORIGINS = False # قم بإلغاء التعليق إذا كنت لا تستخدمه في التطوير

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]


# >>> Google Maps API Settings <<<
Maps_API_KEY = os.environ.get('Maps_API_KEY')

# === QR Code Settings ===
RETURN_QR_CODE_VALIDITY_DAYS = 30

# >>> Barcode Scan Settings <<<
MAX_BARCODE_SCAN_DISTANCE_KM = Decimal('0.01')

# --- Django-Q Settings ---
Q_CLUSTER = {
    'name': 'DjangORM',
    'workers': 4,
    'timeout': 90,
    'retry': 120,
    'queue_limit': 50,
    'bulk': 10,
    'orm': 'default',
}
Q_SCHEDULE = [
    {
        'func': 'integrations.tasks.sync_products_with_accounting_software', # Full path to the function
        'schedule_type': 'hourly', # Schedule type: 'hourly', 'daily', 'weekly', 'monthly', 'once'
        'name': 'Pull Products from Accounting Software Hourly', # Descriptive name for the task
        'hook': 'integrations.tasks.sync_products_callback', # Optional function to execute after task completion (for reports, notifications)
        'cluster': 'DjangORM', # The cluster that will execute the task
    },
]

# >>> VAT Rate Setting <<<
VAT_RATE = Decimal('15.00')

# >>> GNU Gettext Tools Path for Windows (Required for makemessages) <<<
if platform.system() == "Windows":
    GETTEXT_TOOLS_PATH = r"C:\Program1\gettext0.25-iconv1.17-static-64\bin"
    os.environ["PATH"] += os.pathsep + GETTEXT_TOOLS_PATH
    logger.info(f"Added {GETTEXT_TOOLS_PATH} to PATH for Django operations.")
else:
    GETTEXT_TOOLS_PATH = None


# --- Email settings for password reset ---
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# --- Firebase Admin SDK Settings ---
# This is the path to your downloaded service account key file
# Make sure to replace 'mys-f-s111p-firebase-adminsdk-fbsvc-30f59b06c0.json' with your actual file name
FIREBASE_ADMIN_SDK_CONFIG = BASE_DIR / 'firebase_keys' / 'mys-f-s111p-firebase-adminsdk-fbsvc-30f59b06c0.json'

# Your Firebase project ID (found in Firebase Console -> Project settings)
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'mys-f-s111p')


# --- Firebase Admin SDK Initialization ---
# This ensures Firebase Admin SDK is initialized only once when Django starts
if not firebase_admin._apps:
    try:
        if not FIREBASE_ADMIN_SDK_CONFIG.exists():
            logger.error(f"Firebase service account key file not found at: {FIREBASE_ADMIN_SDK_CONFIG}")
            # Consider raising an exception here if Firebase is critical for your app to run
            # raise FileNotFoundError(f"Firebase service account key file not found at: {FIREBASE_ADMIN_SDK_CONFIG}")

        cred = credentials.Certificate(str(FIREBASE_ADMIN_SDK_CONFIG))
        firebase_admin.initialize_app(cred, {
            'projectId': FIREBASE_PROJECT_ID,
        })
        logger.info("Firebase Admin SDK initialized successfully.")
    except FileNotFoundError:
        logger.error(f"FATAL ERROR: Firebase service account key not found at {FIREBASE_ADMIN_SDK_CONFIG}. Please check the path and file existence.")
        # Decide if you want to raise the exception to stop server startup if Firebase is essential
        # raise
    except firebase_exceptions.FirebaseError as e:
        logger.error(f"Firebase initialization error: {e.code} - {e.message}", exc_info=True)
        # Decide if you want to raise the exception to stop server startup
        # raise
    except Exception as e:
        logger.error(f"General error during Firebase Admin SDK initialization: {e}", exc_info=True)
        # Decide if you want to raise the exception to stop server startup
        # raise


# --- LOGGING CONFIGURATION ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',  # Changed from DEBUG to INFO to reduce verbosity in console
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'django_debug.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO', # Changed from DEBUG to INFO
            'propagate': False,
        },
        'authentication': { # Specific logger for our authentication app
            'handlers': ['console', 'file'],
            'level': 'INFO', # Changed from DEBUG to INFO
            'propagate': False,
        },
        'users': { # Add a logger for the users app
            'handlers': ['console', 'file'],
            'level': 'INFO', # Changed from DEBUG to INFO
            'propagate': False,
        },
        'stores': { # Add a logger for the stores app
            'handlers': ['console', 'file'],
            'level': 'INFO', # Changed from DEBUG to INFO
            'propagate': False,
        },
        'products': { # Add a logger for the products app
            'handlers': ['console', 'file'],
            'level': 'INFO', # Changed from DEBUG to INFO
            'propagate': False,
        },
        'sales': { # Add a logger for the sales app
            'handlers': ['console', 'file'],
            'level': 'INFO', # Changed from DEBUG to INFO
            'propagate': False,
        },
        'customers': { # Add a logger for the customers app
            'handlers': ['console', 'file'],
            'level': 'INFO', # Changed from DEBUG to INFO
            'propagate': False,
        },
        'reports': { # Add a logger for the reports app
            'handlers': ['console', 'file'],
            'level': 'INFO', # Changed from DEBUG to INFO
            'propagate': False,
        },
        'integrations': { # Add a logger for the integrations app
            'handlers': ['console', 'file'],
            'level': 'INFO', # Changed from DEBUG to INFO
            'propagate': False,
        },
        'api': { # Add a logger for the api app
            'handlers': ['console', 'file'],
            'level': 'INFO', # Changed from DEBUG to INFO
            'propagate': False,
        },
        '': { # Root logger
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}