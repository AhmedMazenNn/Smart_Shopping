# integrations/tasks.py

from django_q.tasks import async_task
from django.utils import timezone
import requests
import json
from decimal import Decimal
from django.conf import settings
from django.db import transaction

# استيراد النماذج من تطبيقاتك
from integrations.models import AccountingSystemConfig, SaleInvoiceSyncLog, ProductSyncLog
# استيراد النماذج الصحيحة: Order و OrderItem بدلاً من Sale و SaleItem
from sales.models import Order, OrderItem
from products.models import Product, Branch
from django.utils.translation import gettext_lazy as _
import os


# Helper function to get accounting config
def get_accounting_config():
    try:
        return AccountingSystemConfig.objects.get(is_active=True)
    except AccountingSystemConfig.DoesNotExist:
        return None

def send_sale_invoice_to_accounting_task(order_id): # تم التعديل إلى order_id
    """
    مهمة تُشغل في الخلفية لإرسال فاتورة مبيعات (طلب) إلى برنامج المحاسبة.
    """
    config = get_accounting_config()
    if not config:
        print(_("Error: Accounting system configuration not found or not active."))
        return False

    try:
        order = Order.objects.get(id=order_id) # تم التعديل إلى Order
    except Order.DoesNotExist: # تم التعديل إلى Order.DoesNotExist
        print(_(f"Error: Order with ID {order_id} not found."))
        return False

    # البحث عن سجل المزامنة الموجود أو إنشاء واحد جديد
    sync_log, created = SaleInvoiceSyncLog.objects.get_or_create(
        config=config,
        sale=order, # ربط الـ SaleInvoiceSyncLog بالـ Order هنا
        defaults={
            'status': 'PENDING',
            'message': _("Attempting to send invoice to accounting system via background task."),
            'app_commission_rate': Decimal('0.00'),
            'total_amount_before_commission': Decimal('0.00'),
            'amount_sent_to_accounting': Decimal('0.00'),
        }
    )
    if not created and sync_log.status != 'PENDING':
        sync_log.status = 'PENDING'
        sync_log.message = _("Re-attempting to send invoice to accounting system via background task.")
        sync_log.save()


    try:
        app_commission_rate = Decimal(os.environ.get('APP_COMMISSION_RATE', '0.05'))
        total_before_commission = order.total_amount # تم التعديل إلى order.total_amount
        amount_after_commission = total_before_commission * (1 - app_commission_rate)

        invoice_data = {
            'order_id': str(order.order_id),
            'sale_date': order.date.isoformat(),
            'total_amount': str(order.total_amount),
            'fee_amount': str(order.fee_amount),
            'customer_id': str(order.customer.id) if order.customer else None,
            'branch_id': str(order.branch.id) if order.branch else None,
            'app_commission_rate': str(app_commission_rate * 100),
            'total_amount_before_commission': str(total_before_commission),
            'amount_sent_to_accounting': str(amount_after_commission),
            'items': []
        }
        for item in order.items.all(): # تم التعديل إلى order.items.all()
            invoice_data['items'].append({
                'product_id': str(item.product.id),
                'product_name': item.product.name, # تم التعديل إلى product.name
                'quantity': item.quantity,
                'unit_price': str(item.price_at_purchase),
                'total_price': str(item.quantity * item.price_at_purchase)
            })

        headers = {'Content-Type': 'application/json'}
        if config.api_key:
            headers['Authorization'] = f'Bearer {config.api_key}'

        accounting_api_endpoint = f"{config.api_base_url}/invoices/"

        response = requests.post(accounting_api_endpoint, headers=headers, data=json.dumps(invoice_data))
        response.raise_for_status()

        accounting_response = response.json()
        accounting_invoice_id = accounting_response.get('invoice_id')

        sync_log.status = 'SUCCESS'
        sync_log.message = _("Invoice sent successfully via background task.")
        sync_log.accounting_invoice_id = accounting_invoice_id
        sync_log.app_commission_rate = app_commission_rate * 100
        sync_log.total_amount_before_commission = total_before_commission
        sync_log.amount_sent_to_accounting = amount_after_commission
        sync_log.save()
        return True

    except requests.exceptions.RequestException as e:
        error_message = _("Failed to send invoice to accounting system via background task: ") + str(e)
        sync_log.status = 'FAILED'
        sync_log.message = error_message
        sync_log.save()
        print(error_message)
        return False
    except Exception as e:
        error_message = _("An unexpected error occurred during invoice sync background task: ") + str(e)
        sync_log.status = 'FAILED'
        sync_log.message = error_message
        sync_log.save()
        print(error_message)
        return False


def sync_products_with_accounting_software():
    """
    مهمة مجدولة لجلب/مزامنة المنتجات من برنامج المحاسبة.
    """
    config = get_accounting_config()
    if not config:
        print(_("Error: Accounting system configuration not found or not active."))
        return False

    sync_log = ProductSyncLog.objects.create(
        config=config,
        status='IN_PROGRESS',
        message=_("Starting scheduled product sync from accounting system.")
    )

    try:
        headers = {}
        if config.api_key:
            headers['Authorization'] = f'Bearer {config.api_key}'

        accounting_api_endpoint = f"{config.api_base_url}/products/"
        response = requests.get(accounting_api_endpoint, headers=headers)
        response.raise_for_status()
        products_data = response.json()

        synced_count = 0
        errors_count = 0
        
        default_branch = Branch.objects.first()

        if not default_branch:
            raise Exception(_("No default branch found to assign products."))

        for item_data in products_data:
            try:
                product_accounting_id = item_data.get('id')
                
                with transaction.atomic():
                    product, created = Product.objects.update_or_create(
                        # بما أنك أضفت unique_accounting_id_per_branch، يمكننا استخدامها
                        # يجب أن يكون accounting_system_id موجودًا في بيانات برنامج المحاسبة
                        accounting_system_id=product_accounting_id,
                        branch=default_branch, # ربط المنتج بالفرع الافتراضي
                        
                        defaults={
                            'name': item_data.get('name', _("Unnamed Product")),
                            'item_number': item_data.get('item_number', None),
                            'barcode': item_data.get('barcode', None), # تأكد من أن الباركود يمكن أن يأتي من الـ API
                            'price': Decimal(item_data.get('price', '0.00')),
                            'quantity_in_stock': int(item_data.get('quantity', 0)),
                            # أضف أي حقول أخرى تحتاج لمزامنتها
                        }
                    )
                synced_count += 1
            except Exception as item_e:
                errors_count += 1
                sync_log.message += _(f"\nError processing product {item_data.get('id', 'N/A')}: {str(item_e)}")
                
        sync_log.status = 'SUCCESS' if errors_count == 0 else 'FAILED'
        sync_log.message = _(f"Product sync completed. Synced: {synced_count}, Errors: {errors_count}.")
        sync_log.products_synced = synced_count
        sync_log.errors_count = errors_count
        sync_log.save()
        config.last_synced_at = timezone.now()
        config.save()
        return True

    except requests.exceptions.RequestException as e:
        error_message = _("Failed to sync products from accounting system: ") + str(e)
        sync_log.status = 'FAILED'
        sync_log.message = error_message
        sync_log.save()
        print(error_message)
        return False
    except Exception as e:
        error_message = _("An unexpected error occurred during product sync: ") + str(e)
        sync_log.status = 'FAILED'
        sync_log.message = error_message
        sync_log.save()
        print(error_message)
        return False


def sync_products_callback(task):
    """
    دالة رد الاتصال بعد انتهاء مهمة مزامنة المنتجات.
    يمكن استخدامها لإرسال إشعارات أو تحديث واجهة المستخدم.
    """
    if task.success:
        print(f"Product sync task {task.id} completed successfully.")
    else:
        print(f"Product sync task {task.id} failed: {task.result}")