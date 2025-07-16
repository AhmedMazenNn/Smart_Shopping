# C:\Users\DELL\SER SQL MY APP\mysite\views.py

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    نقطة نهاية بسيطة للتحقق من أن الواجهة الخلفية لـ Django تعمل.
    """
    return JsonResponse({'status': 'ok', 'message': 'Django backend is running successfully!'})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_info(request):
    """
    نقطة نهاية لجلب معلومات المستخدم الحالي المصادق عليه.
    """
    if request.user.is_authenticated:
        return JsonResponse({
            'id': request.user.id,
            'email': request.user.email,
            'username': request.user.username,
            'is_authenticated': True,
        })
    else:
        return JsonResponse({'message': 'Unauthorized - User not authenticated'}, status=401)
