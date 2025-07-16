# integrations/views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import AccountingSystemConfig, ProductSyncLog, SaleInvoiceSyncLog
from .serializers import (
    AccountingSystemConfigSerializer,
    ProductSyncLogSerializer,
    SaleInvoiceSyncLogSerializer,
    SaleInvoiceIntegrationSerializer,
    ProductIntegrationSerializer
)
# استيراد النماذج الصحيحة: Order بدلاً من Sale
from sales.models import Order
from products.models import Product
from django.conf import settings
from django.db import transaction
import requests
import json
from decimal import Decimal
import os # لاستخدام os.environ.get

# Helper function to get accounting config
def get_accounting_config():
    try:
        return AccountingSystemConfig.objects.get(is_active=True)
    except AccountingSystemConfig.DoesNotExist:
        return None

# --- ViewSets للـ CRUD على سجلات وإعدادات التكامل (للاستخدام الداخلي أو Admin API) ---

class AccountingSystemConfigViewSet(viewsets.ModelViewSet):
    queryset = AccountingSystemConfig.objects.all()
    serializer_class = AccountingSystemConfigSerializer
    permission_classes = [IsAuthenticated] # يجب أن يكون المستخدم مصادقًا لإدارة الإعدادات

class ProductSyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductSyncLog.objects.all()
    serializer_class = ProductSyncLogSerializer
    permission_classes = [IsAuthenticated]

class SaleInvoiceSyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SaleInvoiceSyncLog.objects.all()
    serializer_class = SaleInvoiceSyncLogSerializer
    permission_classes = [IsAuthenticated]

# --- API Endpoints لمهام التكامل الفعلية (المنتجات والمبيعات) ---

@api_view(['POST'])
@permission_classes([IsAuthenticated]) # يتطلب مصادقة
def send_sale_invoice_to_accounting(request, order_id): # تم التعديل إلى order_id
    """
    نقطة نهاية لإرسال فاتورة مبيعات (طلب) محددة إلى برنامج المحاسبة.
    يجب أن يتم تشغيل هذه الدالة بواسطة Task Queue (django-q) للعمليات الخلفية.
    """
    try:
        order = Order.objects.get(id=order_id) # تم التعديل إلى Order
    except Order.DoesNotExist: # تم التعديل إلى Order.DoesNotExist
        return Response({'detail': _("Order not found.")}, status=status.HTTP_404_NOT_FOUND)

    config = get_accounting_config()
    if not config:
        return Response({'detail': _("Accounting system configuration not found or not active.")}, status=status.HTTP_400_BAD_REQUEST)

    # إنشاء سجل مزامنة جديد (في البداية يكون معلقاً)
    # ملاحظة: SaleInvoiceSyncLog لا يرتبط بـ Sale بل بـ Order الآن
    sync_log = SaleInvoiceSyncLog.objects.create(
        config=config,
        sale=order, # ربط الـ SaleInvoiceSyncLog بالـ Order هنا
        status='PENDING',
        message=_("Attempting to send invoice to accounting system.")
    )

    try:
        # حساب نسبة التطبيق والمبلغ الصافي
        app_commission_rate = Decimal(os.environ.get('APP_COMMISSION_RATE', '0.05')) # احصل عليها من متغير بيئة أو قاعدة البيانات
        
        # المبلغ بعد الخصومات والضرائب هو total_amount في نموذج Order
        total_before_commission = order.total_amount # تم التعديل إلى order.total_amount
        amount_after_commission = total_before_commission * (1 - app_commission_rate)

        # تجهيز بيانات الفاتورة للإرسال
        invoice_data = {
            'order_id': str(order.order_id), # استخدام order_id كمعرف فريد للطلب
            'sale_date': order.date.isoformat(), # تاريخ الطلب
            'total_amount': str(order.total_amount), # إجمالي المبلغ من الطلب
            'fee_amount': str(order.fee_amount), # رسوم التطبيق من الطلب
            # 'tax_amount': str(order.tax_amount), # إذا كان لديك حقل للضريبة في Order
            # 'final_amount': str(order.final_amount), # إذا كان لديك حقل للمبلغ النهائي بعد كل شيء
            'customer_id': str(order.customer.id) if order.customer else None,
            'branch_id': str(order.branch.id) if order.branch else None,
            'app_commission_rate': str(app_commission_rate * 100), # إرسال كنسبة مئوية
            'total_amount_before_commission': str(total_before_commission),
            'amount_sent_to_accounting': str(amount_after_commission),
            'items': []
        }
        for item in order.items.all(): # استخدام related_name 'items' في Order
            invoice_data['items'].append({
                'product_id': str(item.product.id),
                'product_name': item.product.name, # تم التعديل إلى product.name
                'quantity': item.quantity,
                'unit_price': str(item.price_at_purchase),
                'total_price': str(item.quantity * item.price_at_purchase) # حساب الإجمالي لكل عنصر
            })

        # إرسال البيانات إلى برنامج المحاسبة
        headers = {'Content-Type': 'application/json'}
        if config.api_key:
            headers['Authorization'] = f'Bearer {config.api_key}'

        accounting_api_endpoint = f"{config.api_base_url}/invoices/" # نقطة نهاية افتراضية لإرسال الفواتير

        response = requests.post(accounting_api_endpoint, headers=headers, data=json.dumps(invoice_data))
        response.raise_for_status() # ألقِ استثناء إذا كان الرد 4xx/5xx

        # معالجة الرد من برنامج المحاسبة
        accounting_response = response.json()
        accounting_invoice_id = accounting_response.get('invoice_id') # افترض أن برنامج المحاسبة يرجع ID

        # تحديث سجل المزامنة
        sync_log.status = 'SUCCESS'
        sync_log.message = _("Invoice sent successfully.")
        sync_log.accounting_invoice_id = accounting_invoice_id
        sync_log.app_commission_rate = app_commission_rate * 100 # حفظ النسبة المئوية
        sync_log.total_amount_before_commission = total_before_commission
        sync_log.amount_sent_to_accounting = amount_after_commission
        sync_log.save()

        # (اختياري) يمكنك تحديث نموذج Order نفسه بمعرف الفاتورة في برنامج المحاسبة
        # if hasattr(order, 'accounting_invoice_id'):
        #     order.accounting_invoice_id = accounting_invoice_id
        #     order.save(update_fields=['accounting_invoice_id'])

        return Response({'detail': _("Invoice sent to accounting system successfully."), 'accounting_invoice_id': accounting_invoice_id}, status=status.HTTP_200_OK)

    except requests.exceptions.RequestException as e:
        error_message = _("Failed to send invoice to accounting system: ") + str(e)
        sync_log.status = 'FAILED'
        sync_log.message = error_message
        sync_log.save()
        return Response({'detail': error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        error_message = _("An unexpected error occurred during invoice sync: ") + str(e)
        sync_log.status = 'FAILED'
        sync_log.message = error_message
        sync_log.save()
        return Response({'detail': error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ... (بقية views.py مثل sync_products_from_accounting إذا كانت مفعلة) ...