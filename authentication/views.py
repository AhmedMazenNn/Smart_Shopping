# C:\Users\DELL\SER SQL MY APP\authentication\views.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils.translation import gettext_lazy as _
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

# استيراد الـ serializers من مواقعها الصحيحة
# CustomerRegistrationSerializer و UserProfileSerializer يجب أن يكونا في users/serializers.py
# CustomTokenObtainPairSerializer و StoreRegistrationSerializer في authentication/serializers.py
from users.serializers import CustomerRegistrationSerializer, UserProfileSerializer
from authentication.serializers import CustomTokenObtainPairSerializer, StoreRegistrationSerializer # تم تغيير الاسم هنا


# === LoginAPIView ===
class LoginAPIView(TokenObtainPairView):
    """
    نقطة نهاية لتسجيل دخول المستخدم باستخدام البريد الإلكتروني أو اسم المستخدم وكلمة المرور.
    تستخدم CustomTokenObtainPairSerializer للتحقق من الصحة وتوليد التوكن.
    """
    serializer_class = CustomTokenObtainPairSerializer


# === CustomerRegisterAPIView ===
class CustomerRegisterAPIView(GenericAPIView):
    """
    نقطة نهاية لتسجيل العملاء الأفراد.
    تقوم بإنشاء UserAccount جديد مع ربطه بدور 'customer' وإنشاء كيان Customer مرتبط.
    """
    serializer_class = CustomerRegistrationSerializer
    permission_classes = [AllowAny] # السماح لأي شخص بالتسجيل

    def post(self, request, *args, **kwargs):
        """
        معالجة طلب POST لتسجيل عميل جديد.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True) # التحقق من صحة البيانات
        
        # serializer.save() يجب أن يقوم بإنشاء UserAccount و Customer في معاملة واحدة
        try:
            # هنا نفترض أن serializer.save() سيعيد كائن UserAccount الذي تم إنشاؤه
            user_account, customer = serializer.save() 
            return Response({
                'user_id': str(user_account.user_id), # استخدام user_id (UUID)
                'email': user_account.email,
                'username': user_account.username,
                'customer_id': str(customer.customer_id), # معرف العميل (UUID)
                'message': _('Customer registered successfully.'),
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error during customer registration: {e}", exc_info=True)
            return Response({'detail': _(f"Registration failed: {e}")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# === StoreRegisterAPIView ===
class StoreRegisterAPIView(GenericAPIView):
    """
    نقطة نهاية لتسجيل كيان متجر جديد (وليس حساب مستخدم للمتجر).
    تقوم هذه العملية بإنشاء كيان Store فقط.
    إنشاء حسابات المستخدمين (مثل مديري المتاجر) التي ترتبط بهذا المتجر
    يجب أن تتم عبر نقاط نهاية تسجيل الموظفين (Employee registration) بشكل منفصل.
    """
    serializer_class = StoreRegistrationSerializer # تم تغيير اسم Serializer هنا
    permission_classes = [AllowAny] # يمكن لأي شخص (أو المشرف) تسجيل متجر

    def post(self, request, *args, **kwargs):
        """
        معالجة طلب POST لتسجيل متجر جديد.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True) # التحقق من صحة البيانات

        try:
            # serializer.save() ستقوم فقط بإنشاء كيان Store
            store = serializer.save()
            return Response({
                'store_id': str(store.store_id), # استخدام store_id (UUID)
                'store_name': store.store_name,
                'message': _('Store registered successfully. You can now create employee accounts and branches for this store.'),
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error during store registration: {e}", exc_info=True)
            return Response({'detail': _(f"Store registration failed: {e}")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# === UserProfileView ===
class UserProfileView(APIView):
    """
    نقطة نهاية لعرض وتعديل ملف تعريف المستخدم الحالي.
    تتطلب مصادقة المستخدم.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer # serializer يجب أن يتعامل مع UserAccount

    def get(self, request, *args, **kwargs):
        """
        جلب بيانات ملف تعريف المستخدم الحالي.
        """
        user_account = request.user # request.user هو كائن UserAccount بعد المصادقة
        serializer = self.serializer_class(user_account)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        """
        تحديث بيانات ملف تعريف المستخدم الحالي.
        """
        user_account = request.user
        # partial=True يسمح بالتحديث الجزئي (ليس كل الحقول مطلوبة)
        serializer = self.serializer_class(user_account, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True) # التحقق من صحة البيانات
        
        updated_user_account = serializer.save() # حفظ التغييرات

        response_data = serializer.data
        # تم إزالة منطق 'generated_password' لأنه عادة ما يتم التعامل معه في عملية منفصلة لتغيير كلمة المرور
        response_data['message'] = _("Profile updated successfully.")

        return Response(response_data, status=status.HTTP_200_OK)

