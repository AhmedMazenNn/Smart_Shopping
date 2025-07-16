# integrations/serializers.py

from rest_framework import serializers
from .models import AccountingSystemConfig, SaleInvoiceSyncLog, ProductSyncLog
from products.models import Product # سنحتاج إلى Product Serializer
# استيراد النماذج الصحيحة: Order و OrderItem بدلاً من Sale و SaleItem
from sales.models import Order, OrderItem
from decimal import Decimal
from django.utils.translation import gettext_lazy as _

class AccountingSystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingSystemConfig
        fields = '__all__'
        read_only_fields = ('last_synced_at', 'created_at', 'updated_at')
        extra_kwargs = {
            'api_key': {'write_only': True} # لا ترسل مفتاح الـ API في الاستجابات
        }

class ProductIntegrationSerializer(serializers.ModelSerializer):
    # هذا الـ serializer لتمثيل المنتج عند إرساله/استقباله من برنامج المحاسبة
    # قد تختلف الحقول هنا عن ProductSerializer العادي
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'barcode', 'item_number', 'price',
            'discount', 'offer_price', 'offer_quantity', 'expiry_date',
            'quantity_in_stock',
            'accounting_system_id', # يجب أن يكون هذا الحقل موجودًا الآن في نموذج Product
        ]
        read_only_fields = ['id']


class OrderItemIntegrationSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True) # تم التعديل إلى product.name
    product_barcode = serializers.CharField(source='product.barcode', read_only=True)
    
    class Meta:
        model = OrderItem # تم التعديل إلى OrderItem
        fields = [
            'product', 'product_name', 'product_barcode',
            'quantity', 'price_at_purchase', 'commission_percentage', 'commission_amount',
        ]
        read_only_fields = ['product_name', 'product_barcode', 'commission_amount']


class SaleInvoiceIntegrationSerializer(serializers.ModelSerializer):
    # هذا الـ serializer لتمثيل الفاتورة/الطلب عند إرسالها إلى برنامج المحاسبة
    items = OrderItemIntegrationSerializer(many=True, read_only=True, source='items') # تم التعديل إلى items (related_name في Order)

    # ملاحظة: يجب أن يأتي app_commission_rate من إعدادات تطبيقك
    # أو يتم حسابها في View أو Task
    # هنا تم وضعها كـ read_only_field لتمثيل ما سيتم إرساله
    app_commission_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True,
        help_text=_("Application commission rate applied to this sale.")
    )
    total_amount_before_commission = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True,
        help_text=_("Total amount of sale before applying application commission.")
    )
    amount_sent_to_accounting = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True,
        help_text=_("Final amount sent to accounting system after commission.")
    )

    class Meta:
        model = Order # تم التعديل إلى Order (لأن الفاتورة مبنية على الطلب)
        # اختر الحقول التي تريد إرسالها إلى برنامج المحاسبة
        fields = [
            'order_id', 'date', 'total_amount', 'fee_amount', # total_amount هنا هو ما كان final_amount في السابق
            'payment_method', 'transaction_id', 'customer', 'branch', 'items',
            'app_commission_rate', 'total_amount_before_commission', 'amount_sent_to_accounting',
            # 'accounting_system_invoice_id', # إذا أضفت هذا الحقل إلى نموذج Order أو Invoice
        ]
        read_only_fields = [
            'order_id', 'date', 'total_amount', 'fee_amount',
            'payment_method', 'transaction_id', 'customer', 'branch', 'items',
            'app_commission_rate', 'total_amount_before_commission', 'amount_sent_to_accounting',
        ]


class ProductSyncLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSyncLog
        fields = '__all__'
        read_only_fields = ('sync_date',)

class SaleInvoiceSyncLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleInvoiceSyncLog
        fields = '__all__'
        read_only_fields = ('sync_date',)