# C:\Users\DELL\SER SQL MY APP\authentication\backends.py

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from firebase_admin import auth, exceptions as firebase_exceptions
from django.contrib.auth import get_user_model
import logging
from django.db import transaction # لاستخدام المعاملات لضمان سلامة البيانات

logger = logging.getLogger(__name__)

# تأكد من استيراد وتهيئة Firebase Admin SDK عند بدء تشغيل Django.
# هذا السطر سيستورد ملف firebase_app.py الذي يقوم بتهيئة Firebase.
try:
    from mysite import firebase_app
except ImportError as e:
    logger.error(f"Failed to import firebase_app: {e}. Ensure mysite/firebase_app.py exists and Firebase config is correct.")
    # إذا فشل تهيئة Firebase، فهذا خطأ فادح ويجب إيقاف الخادم.
    raise RuntimeError("Firebase Admin SDK initialization failed. Cannot start application.")

# الحصول على نموذج المستخدم المخصص الذي تم تحديده في settings.AUTH_USER_MODEL
User = get_user_model()

class FirebaseAuthentication(BaseAuthentication):
    """
    فئة مصادقة مخصصة لـ Django REST Framework للتحقق من Firebase ID Tokens.
    تقوم هذه الفئة بالتحقق من صلاحية التوكن، ثم تبحث عن المستخدم المقابل
    في قاعدة بيانات Django (عن طريق firebase_uid أو البريد الإلكتروني)،
    وتنشئ المستخدم إذا لم يكن موجودًا.
    """

    def authenticate(self, request):
        """
        تقوم بمصادقة الطلب باستخدام Firebase ID Token.
        :param request: كائن الطلب من Django.
        :return: (user, auth_token) إذا نجحت المصادقة، أو None.
        :raises AuthenticationFailed: إذا فشلت المصادقة لأي سبب.
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')

        # إذا لم يكن هناك رأس مصادقة، نعود بـ None للسماح لأذونات DRF بالتعامل.
        if not auth_header:
            return None

        # استخراج الـ ID Token من رأس Authorization (يجب أن يكون "Bearer <ID_TOKEN>").
        try:
            token_prefix, id_token = auth_header.split(' ')
            if token_prefix.lower() != 'bearer':
                raise AuthenticationFailed('Token format is invalid. Should be "Bearer <token>".')
        except ValueError:
            raise AuthenticationFailed('Token format is invalid. Should be "Bearer <token>".')

        # التحقق من صلاحية Firebase ID Token باستخدام Firebase Admin SDK
        try:
            decoded_token = auth.verify_id_token(id_token)
        except firebase_exceptions.AuthError as e:
            # خطأ في التحقق من التوكن (مثال: منتهي الصلاحية، غير صالح)
            logger.warning(f"Firebase token verification failed for token starting with '{id_token[:10]}...': {e}")
            raise AuthenticationFailed(f'Invalid Firebase ID token: {e.args[0]}')
        except Exception as e:
            # أي خطأ غير متوقع آخر أثناء التحقق
            logger.error(f"An unexpected error occurred during Firebase token verification: {e}", exc_info=True)
            raise AuthenticationFailed('An unexpected error occurred during authentication.')

        firebase_uid = decoded_token['uid']
        email = decoded_token.get('email')
        username = decoded_token.get('name', decoded_token.get('email', firebase_uid)) # يفضل الاسم المعروض من Firebase
        
        # يجب أن يكون حقل الدور موجودًا في نموذج Role لدينا
        # نفترض أن الدور الافتراضي للمستخدمين الجدد من Firebase هو 'customer'
        # يجب عليك التأكد من وجود هذا الدور في قاعدة بياناتك.
        from users.models import Role # استيراد نموذج Role
        default_role_name = 'customer'
        try:
            # استخدم get_or_create لضمان وجود الدور
            default_role, created = Role.objects.get_or_create(
                role_name=default_role_name,
                defaults={'description': f'Default role for new {default_role_name}s'}
            )
            if created:
                logger.info(f"Default role '{default_role_name}' created in database.")
        except Exception as e:
            logger.error(f"Failed to get or create default role '{default_role_name}': {e}", exc_info=True)
            raise AuthenticationFailed(f"Server configuration error: Could not find/create default role '{default_role_name}'.")

        # البحث عن المستخدم أو إنشاؤه في قاعدة بيانات Django
        try:
            # استخدام المعاملات لضمان Atomicité في عملية البحث/الإنشاء
            with transaction.atomic():
                user = None
                
                # 1. البحث عن المستخدم بواسطة firebase_uid (الطريقة المفضلة للربط)
                try:
                    user = User.objects.get(firebase_uid=firebase_uid)
                except User.DoesNotExist:
                    logger.debug(f"Django user with Firebase UID {firebase_uid} not found.")
                    
                    # 2. إذا لم يتم العثور عليه بـ UID، ابحث بواسطة البريد الإلكتروني وقم بالربط
                    if email:
                        try:
                            user = User.objects.get(email=email)
                            user.firebase_uid = firebase_uid # ربط Firebase UID بالمستخدم الموجود
                            user.save(update_fields=['firebase_uid']) # حفظ التغيير المحدد
                            logger.info(f"Linked existing Django user {email} with Firebase UID {firebase_uid}.")
                        except User.DoesNotExist:
                            logger.debug(f"Django user with email {email} not found. Creating new user.")
                            # 3. إذا لم يتم العثور عليه بالبريد الإلكتروني، قم بإنشاء مستخدم جديد
                            # هنا نقوم بإنشاء UserAccount فقط، وسيتولى منطق Register/Profile إنشاء Customer/Employee
                            user = User.objects.create_user(
                                email=email,
                                username=username,
                                firebase_uid=firebase_uid,
                                password=User.objects.make_random_password(), # لا حاجة لكلمة مرور فعلية
                                role=default_role, # تعيين الدور الافتراضي
                                is_active=True,
                            )
                            logger.info(f"Created new Django user account {email} for Firebase UID {firebase_uid}.")
                    else:
                        raise AuthenticationFailed('Firebase user email is missing, cannot create or link Django user.')
                
                # تحديث تاريخ آخر تسجيل دخول (يمكن أن يكون في مكان آخر لاحقاً في الـ View أو Middleware)
                # user.last_login_date = timezone.now()
                # user.save(update_fields=['last_login_date'])

                return (user, id_token) # إرجاع كائن المستخدم والتوكن
        
        except AuthenticationFailed:
            # تمرير أخطاء AuthenticationFailed التي تم رفعها مسبقاً
            raise
        except Exception as e:
            logger.error(f"Error finding, linking, or creating Django user: {e}", exc_info=True)
            raise AuthenticationFailed(f'Error processing user in Django: {e}')

    def authenticate_header(self, request):
        """
        يرجع سلسلة الرأس المناسبة لتحدي المصادقة.
        """
        return 'Bearer realm="api"'

