# C:\Users\DELL\SER SQL MY APP\sales\serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.utils.translation import gettext_lazy as _
from django.conf import settings # لاستخدام الإعدادات مثل VAT_RATE

# استيراد النماذج من تطبيق sales
from .models import Order, OrderItem, TempOrder, TempOrderItem, Payment, Return, ReturnItem # تم تحديث الاستيرادات

# استيراد النماذج من تطبيقات أخرى (النماذج المتعلقة بالمنتجات)
from products.models import Product, BranchProductInventory # للتأكد من وجودها للعرض في Serializers

User = get_user_model()


# --- Serializer for TempOrderItem ---
class TempOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True) # تم تغيير product_name إلى name
    product_barcode = serializers.CharField(source='product.barcode', read_only=True)

    class Meta:
        model = TempOrderItem
        fields = [
            'id', 'temp_order', 'product', 'product_name', 'product_barcode',
            'quantity', 'scanned_quantity', 'price_at_scan'
        ]
        read_only_fields = ('price_at_scan',) # price_at_scan يتم حسابه في save()
        extra_kwargs = {
            'product': {'write_only': True},
            'temp_order': {'write_only': True}
        }

# --- Serializer for TempOrder ---
class TempOrderSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    cashier_username = serializers.CharField(source='cashier.username', read_only=True)
    items = TempOrderItemSerializer(many=True, read_only=True) # Nested serializer لعناصر الطلب المؤقت

    class Meta:
        model = TempOrder
        fields = [
            'id', 'branch', 'branch_name', 'cashier', 'cashier_username',
            'created_at', 'updated_at', 'total_amount', 'items'
        ]
        read_only_fields = ('created_at', 'updated_at', 'total_amount', 'branch_name', 'cashier_username', 'items')
        extra_kwargs = {
            'branch': {'write_only': True},
            'cashier': {'write_only': True, 'required': False, 'allow_null': True}
        }


# --- Serializer for OrderItem ---
class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True) # تم تغيير product_name إلى name
    product_barcode = serializers.CharField(source='product.barcode', read_only=True)
    
    # إضافة حقول ضريبة القيمة المضافة والعمولة من النموذج
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=4, read_only=True)
    commission_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    commission_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'product', 'product_name', 'product_barcode',
            'quantity', 'price_at_purchase', 
            'vat_rate', 'commission_percentage', 'commission_amount', # حقول جديدة/معدلة
            'product_attributes_for_ai'
        ]
        read_only_fields = ('price_at_purchase', 'vat_rate', 'commission_percentage', 'commission_amount',)
        extra_kwargs = {
            'product': {'write_only': True},
            'order': {'write_only': True}
        }


# --- Serializer for Payment ---
class PaymentSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(source='order.order_id', read_only=True)
    received_by_username = serializers.CharField(source='received_by.username', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'order_id', 'amount', 'payment_date', 'method',
            'transaction_id', 'received_by', 'received_by_username', 'notes'
        ]
        read_only_fields = ('payment_date', 'order_id', 'received_by_username')
        extra_kwargs = {
            'order': {'write_only': True},
            'received_by': {'write_only': True, 'required': False, 'allow_null': True}
        }

# --- Serializer for ReturnItem ---
class ReturnItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_barcode = serializers.CharField(source='product.barcode', read_only=True)

    class Meta:
        model = ReturnItem
        fields = [
            'id', 'return_obj', 'product', 'product_name', 'product_barcode',
            'quantity_returned', 'price_at_return'
        ]
        read_only_fields = ('price_at_return',)
        extra_kwargs = {
            'return_obj': {'write_only': True},
            'product': {'write_only': True}
        }

# --- Serializer for Return ---
class ReturnSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(source='order.order_id', read_only=True)
    processed_by_username = serializers.CharField(source='processed_by.username', read_only=True)
    returned_items = ReturnItemSerializer(many=True, read_only=True) # Nested serializer لعناصر الإرجاع

    class Meta:
        model = Return
        fields = [
            'id', 'return_id', 'order', 'order_id', 'return_date',
            'total_returned_amount', 'reason', 'processed_by',
            'processed_by_username', 'refund_method', 'refund_transaction_id',
            'returned_items'
        ]
        read_only_fields = ('return_id', 'return_date', 'total_returned_amount', 'processed_by_username', 'returned_items')
        extra_kwargs = {
            'order': {'write_only': True},
            'processed_by': {'write_only': True, 'required': False, 'allow_null': True}
        }


# --- Serializer for Order ---
class OrderSerializer(serializers.ModelSerializer):
    # لا يوجد 'invoice' كـ ForeignKey منفصل بعد الآن، المعلومات مدمجة في Order
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    performed_by_username = serializers.CharField(source='performed_by.username', read_only=True)
    
    # بيانات العميل غير مستخدمي التطبيق
    non_app_customer_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    non_app_customer_phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    # حقول إجمالي المبلغ وتفاصيله
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_amount_before_vat = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_vat_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    fee_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    items = OrderItemSerializer(many=True, read_only=True) # Nested serializer لعناصر الطلب
    payments = PaymentSerializer(many=True, read_only=True) # Nested serializer للدفعات
    returns = ReturnSerializer(many=True, read_only=True) # Nested serializer للمرتجعات

    # حقول لعرض مسارات صور QR Code
    initial_qr_code_url = serializers.SerializerMethodField()
    exit_qr_code_url = serializers.SerializerMethodField()
    
    # حقل لعرض تاريخ انتهاء صلاحية QR الخروج
    exit_qr_code_expiry = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'order_id', 'branch', 'branch_name', 'date', 'recorded_at', 
            'customer', 'non_app_customer_name', 'non_app_customer_phone', 'customer_tax_id', # حقول العميل الجديدة
            'total_amount', 'total_amount_before_vat', 'total_vat_amount', 'fee_amount', # حقول الإجماليات
            'performed_by', 'performed_by_username',
            'status', 'payment_method', 'transaction_id',
            'paid_at', 'completed_at',
            'invoice_number', 'invoice_issue_date', 'accounting_invoice_id', # حقول الفاتورة الجديدة
            'zatca_submission_status', # حقل حالة إرسال الزكاة
            'initial_qr_code', 'initial_qr_code_url', 
            'exit_qr_code', 'exit_qr_code_url', 'exit_qr_code_expiry', 
            'is_exchange', 'original_order_for_return', # حقول الإرجاع/التبادل
            'items', 'payments', 'returns' # إضافة Nested serializers
        ]
        read_only_fields = (
            'order_id', 'recorded_at', 'fee_amount', 'performed_by_username',
            'paid_at', 'completed_at', 'initial_qr_code', 'exit_qr_code',
            'initial_qr_code_url', 'exit_qr_code_url', 'exit_qr_code_expiry', 
            'invoice_number', 'invoice_issue_date', # هذه الحقول للقراءة فقط لأنها تتولد تلقائياً في النموذج
            'total_amount', 'total_amount_before_vat', 'total_vat_amount', # للقراءة فقط لأنها تحسب تلقائياً
            'transaction_id', 'items', 'payments', 'returns' # Nested serializers للقراءة فقط
        )
        extra_kwargs = {
            'branch': {'write_only': True},
            'customer': {'required': False, 'allow_null': True}, # Customer can be null for non-app customers
            'performed_by': {'write_only': True, 'required': False, 'allow_null': True},
            'original_order_for_return': {'write_only': True, 'required': False, 'allow_null': True},
        }

    def get_initial_qr_code_url(self, obj):
        if obj.initial_qr_code:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.initial_qr_code.url)
        return None

    def get_exit_qr_code_url(self, obj):
        if obj.exit_qr_code:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.exit_qr_code.url)
        return None

    def validate(self, data):
        """
        يقوم بالتحقق من صحة البيانات لضمان توفير تفاصيل العميل بشكل صحيح.
        يجب أن يتم توفير إما عميل مسجل في التطبيق أو تفاصيل عميل غير مسجل،
        وليس كلاهما في نفس الوقت.
        """
        customer = data.get('customer')
        non_app_customer_name = data.get('non_app_customer_name')
        non_app_customer_phone = data.get('non_app_customer_phone')

        has_app_customer = customer is not None
        has_non_app_customer_details = bool(non_app_customer_name or non_app_customer_phone)

        if has_app_customer and has_non_app_customer_details:
            raise serializers.ValidationError(
                _("لا يمكن أن يحتوي الطلب على كل من عميل مسجل في التطبيق وتفاصيل عميل غير مسجل في نفس الوقت.")
            )
        
        if not has_app_customer and not has_non_app_customer_details:
            raise serializers.ValidationError(
                _("يجب توفير إما عميل مسجل في التطبيق أو تفاصيل عميل غير مسجل.")
            )
            
        return data

    def create(self, validated_data):
        if not validated_data.get('performed_by') and self.context['request'].user.is_authenticated:
            validated_data['performed_by'] = self.context['request'].user
        
        # إذا كان هناك customer و non_app_customer_name/phone في نفس الوقت، يتم التعامل مع ذلك الآن في دالة validate()
        order = Order.objects.create(**validated_data)
        return order


# Serializer جديد لبيانات QR Code الواردة (للمسح والتحقق)
class QRCodeScanSerializer(serializers.Serializer):
    qr_data = serializers.CharField(help_text=_("QR Code data string (JSON format)"))
