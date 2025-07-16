# C:\Users\DELL\SER SQL MY APP\api\views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model() # الحصول على نموذج المستخدم المخصص

@api_view(['GET'])
@permission_classes([AllowAny]) # لا تتطلب مصادقة
def health_check(request):
    """
    نقطة نهاية بسيطة لفحص حالة صحة الـ API.
    يمكن استخدامها بواسطة أدوات مراقبة للتأكد من أن الخادم يعمل.
    """
    return Response({"status": "healthy", "message": _("API is running smoothly.")}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated]) # تتطلب مصادقة
def user_info(request):
    """
    تعرض معلومات المستخدم الحالي المصادق عليه.
    تتطلب مصادقة JWT.
    """
    user = request.user
    user_data = {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "user_type": user.get_user_type_display(),
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "date_joined": user.date_joined.isoformat(),
        "firebase_uid": user.firebase_uid if user.firebase_uid else None,
        "is_temporary_password": user.is_temporary_password,
        "job_title": user.job_title if user.job_title else None,
        "store_id": user.store.pk if user.store else None,
        "store_name": user.store.name if user.store else None,
        "branch_id": user.branch.pk if user.branch else None,
        "branch_name": user.branch.name if user.branch else None,
        "department_id": user.department.pk if user.department else None,
        "department_name": user.department.name if user.department else None,
        "phone_number": user.phone_number if user.phone_number else None,
        "tax_id": user.tax_id if user.tax_id else None,
        "commission_percentage": str(user.commission_percentage), # تحويل Decimal إلى سلسلة نصية
    }
    return Response(user_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated]) # تتطلب مصادقة
def protected_data(request):
    """
    نقطة نهاية مثال لبيانات محمية.
    يمكن للمستخدمين المصادق عليهم فقط الوصول إليها.
    """
    return Response(
        {"message": _("This is protected data. You are authenticated!"), "user_id": request.user.id},
        status=status.HTTP_200_OK
    )
