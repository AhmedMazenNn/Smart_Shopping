# C:\Users\DELL\SER SQL MY APP\sales\models.py

from django.db import models
from django.conf import settings
from decimal import Decimal
from django.db.models import Sum, F
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import secrets
from django.utils.translation import gettext_lazy as _
import uuid
import qrcode
from io import BytesIO
from django.core.files import File
from PIL import Image
import os
import json
import hmac
import hashlib
import base64
from datetime import timedelta
from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver


# استيراد النماذج من أماكنها الصحيحة
from stores.models import Branch
from products.models import Product, BranchProductInventory # Import BranchProductInventory


# --- إضافة نماذج الطلب المؤقت للكاشير ---
class TempOrder(models.Model):
    """
    نموذج لتمثيل سلة المشتريات المؤقتة التي ينشئها الكاشير للعملاء غير المستخدمين للتطبيق.
    """
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='temp_orders', verbose_name=_("Branch"))
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_temp_orders',
        verbose_name=_("Cashier")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Last Updated At"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Total Amount"))


    class Meta:
        verbose_name = _("Temporary Order")
        verbose_name_plural = _("Temporary Orders")
        ordering = ['-created_at']

    def __str__(self):
        return f"{_('Temp Order')} #{self.id} {_('at')} {self.branch.name} {_('by')} {self.cashier.username if self.cashier else 'N/A'}"

    def calculate_totals(self):
        """يحسب إجمالي السعر للطلب المؤقت."""
        total = self.items.aggregate(
            sum_items=Sum(F('quantity') * F('price_at_scan'), output_field=models.DecimalField())
        )['sum_items']
        self.total_amount = total if total is not None else Decimal('0.00')


class TempOrderItem(models.Model):
    """
    عنصر في سلة المشتريات المؤقتة.
    """
    temp_order = models.ForeignKey(TempOrder, on_delete=models.CASCADE, related_name='items', verbose_name=_("Temporary Order"))
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name=_("Product"))
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name=_("Expected Quantity"))
    scanned_quantity = models.PositiveIntegerField(default=0, verbose_name=_("Scanned Quantity"))
    price_at_scan = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_("Price at Scan"),
        null=True, blank=True
    )

    class Meta:
        verbose_name = _("Temporary Order Item")
        verbose_name_plural = _("Temporary Order Items")
        unique_together = ('temp_order', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.name} {_('in Temp Order')} {self.temp_order.id}"

    def save(self, *args, **kwargs):
        if not self.price_at_scan and self.product:
            self.price_at_scan = self.product.price_after_discount()

        super().save(*args, **kwargs)

# --- نهاية نماذج الطلب المؤقت ---


# === نموذج الطلب (Order) - سيكون هو الفاتورة الأساسية ===
class Order(models.Model):
    order_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name=_("Order ID"))
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='orders', verbose_name=_("Branch"))
    date = models.DateField(default=timezone.localdate, verbose_name=_("Order Date"))
    recorded_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Recorded At"))

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='customer_orders',
        verbose_name=_("Customer (User Account)")
    )
    non_app_customer_name = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Non-App Customer Name"))
    non_app_customer_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Non-App Customer Phone"))


    customer_tax_id = models.CharField(
        max_length=50,
        blank=True, null=True,
        verbose_name=_("Customer Tax ID (VAT/TRN)")
    )

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name=_("Total Amount"))
    total_amount_before_vat = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        verbose_name=_("Total Amount Before VAT")
    )
    total_vat_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        verbose_name=_("Total VAT Amount")
    )

    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False, verbose_name=_("Fee/Commission Amount"))

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_orders',
        verbose_name=_("Processed By Cashier")
    )

    class OrderStatus(models.TextChoices): # استخدام TextChoices لتحسين القراءة
        PENDING_PAYMENT = 'pending_payment', _('Pending Payment')
        PAID = 'paid', _('Paid')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
        RETURNED = 'returned', _('Returned')
        PARTIALLY_RETURNED = 'partially_returned', _('Partially Returned')

    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING_PAYMENT, verbose_name=_("Order Status"))

    class PaymentMethod(models.TextChoices): # استخدام TextChoices لتحسين القراءة
        CASH = 'cash', _('Cash')
        ELECTRONIC = 'electronic', _('Electronic Payment')
        CREDIT_BALANCE = 'credit_balance', _('Credit Balance')
        NOT_PAID = 'not_paid', _('Not Paid Yet')

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.NOT_PAID, verbose_name=_("Payment Method"))
    transaction_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Transaction ID (for electronic payment)"))

    paid_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Paid At"))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Completed At"))
    
    invoice_number = models.CharField(
        max_length=100,
        unique=True,
        blank=True, null=True,
        verbose_name=_("Invoice Number")
    )
    invoice_issue_date = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_("Invoice Issue Date")
    )

    # حقل جديد لربط الطلب بمعرفه في نظام المحاسبة الخارجي (Xero, QuickBooks, etc.)
    accounting_invoice_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True, # يجب أن يكون معرف الفاتورة المحاسبي فريداً
        verbose_name=_("Accounting Invoice ID")
    )


    ZATCA_SUBMISSION_STATUS_CHOICES = (
        ('PENDING', _('Pending ZATCA Submission')),
        ('SUBMITTED', _('Submitted to ZATCA')),
        ('ACCEPTED', _('ZATCA Accepted')),
        ('REJECTED', _('ZATCA Rejected')),
        ('FAILED', _('ZATCA Submission Failed')),
    )
    zatca_submission_status = models.CharField(
        max_length=20,
        choices=ZATCA_SUBMISSION_STATUS_CHOICES,
        default='PENDING',
        verbose_name=_("ZATCA Submission Status")
    )

    initial_qr_code = models.ImageField(upload_to='qr_codes/initial/', blank=True, null=True, verbose_name=_("Initial QR Code (Customer Scan)"))
    exit_qr_code = models.ImageField(upload_to='qr_codes/exit/', blank=True, null=True, verbose_name=_("Exit/Return QR Code"))
    exit_qr_code_expiry = models.DateTimeField(blank=True, null=True, verbose_name=_("Exit QR Code Expiry"))

    is_exchange = models.BooleanField(default=False, verbose_name=_("Is Exchange Order"))
    original_order_for_return = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='returned_to_orders', verbose_name=_("Original Order for Return/Exchange")
    )

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")

    def __str__(self):
        return f"{_('Order')} {self.order_id} {_('at')} {self.branch.name} - {_('Status')}: {self.get_status_display()}" + (f" - {_('Invoice')}: {self.invoice_number}" if self.invoice_number else "")

    def calculate_totals(self):
        """
        يحسب ويحدث إجماليات الطلب (المبلغ الإجمالي، الضريبة، المبلغ قبل الضريبة، عمولة الفرع).
        يجب استدعاؤها بعد إنشاء أو تعديل OrderItem.
        """
        items = self.items.all()
        total_items_price_before_vat = Decimal('0.00')
        total_items_vat = Decimal('0.00')

        for item in items:
            # استخدام price_at_purchase و vat_rate المخزنة في OrderItem
            item_total = item.quantity * item.price_at_purchase
            total_items_price_before_vat += item_total
            total_items_vat += (item_total * item.vat_rate)

        self.total_amount_before_vat = total_items_price_before_vat
        self.total_vat_amount = total_items_vat
        self.total_amount = self.total_amount_before_vat + self.total_vat_amount
        
        if self.branch and self.branch.fee_percentage is not None:
            self.fee_amount = (self.total_amount * self.branch.fee_percentage) / 100
        else:
            self.fee_amount = Decimal('0.00')


    def save(self, *args, **kwargs):
        is_new_order = not self.pk
        old_status = None
        
        if not is_new_order:
            try:
                old_instance = Order.objects.get(pk=self.pk)
                old_status = old_instance.status
            except Order.DoesNotExist:
                pass
        
        if self.customer and not self.customer_tax_id:
            self.customer_tax_id = getattr(self.customer, 'tax_id', None)
            
        if is_new_order and self.branch:
            # تحديث عدادات العمليات للفرع عند إنشاء طلب جديد
            # استخدام F لتجنب مشكلات التزامن في بيئات متعددة المستخدمين
            self.branch.daily_operations = F('daily_operations') + 1
            self.branch.monthly_operations = F('monthly_operations') + 1
            self.branch.total_yearly_operations = F('total_yearly_operations') + 1
            self.branch.save(update_fields=['daily_operations', 'monthly_operations', 'total_yearly_operations'])
            self.branch.refresh_from_db()

        # توليد رقم الفاتورة وتاريخ الإصدار إذا لم يتم تعيينهما
        if not self.invoice_number and self.branch:
            if self.branch.store:
                store_id = self.branch.store.id
                branch_id = self.branch.id
                timestamp_str = timezone.now().strftime('%Y%m%d%H%M%S')
                random_hex = secrets.token_hex(4).upper()
                self.invoice_number = f"{store_id}-{branch_id}-{timestamp_str}-{random_hex}"
                self.invoice_issue_date = timezone.now()
            else:
                print(_(f"Warning: Branch {self.branch.name} has no associated store. Invoice number might be incomplete."))
                self.invoice_number = f"NOSTORE-{self.branch.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4).upper()}"
                self.invoice_issue_date = timezone.now()

        super().save(*args, **kwargs)

        if not self.initial_qr_code:
            self._generate_qr_code(qr_type='initial')
            self.save(update_fields=['initial_qr_code'])

        if (self.status in [self.OrderStatus.PAID, self.OrderStatus.COMPLETED]) and \
           (old_status not in [self.OrderStatus.PAID, self.OrderStatus.COMPLETED] or not self.exit_qr_code):
            self.exit_qr_code_expiry = timezone.now() + timedelta(days=getattr(settings, 'RETURN_QR_CODE_VALIDITY_DAYS', 30))
            self._generate_qr_code(qr_type='exit')
            self.save(update_fields=['exit_qr_code', 'exit_qr_code_expiry'])

    def _generate_qr_code(self, qr_type='initial'):
        """
        دالة داخلية لتوليد QR Code بالبيانات المطلوبة والتوقيع.
        """
        data = {
            'order_id': str(self.order_id),
            'branch_id': str(self.branch.id) if self.branch else None,
            'customer_id': str(self.customer.id) if self.customer else None,
            'cashier_id': str(self.performed_by.id) if self.performed_by else None,
            'type': qr_type,
            'timestamp': timezone.now().isoformat(),
        }

        if qr_type == 'exit':
            data['expiry'] = (timezone.now() + timedelta(days=getattr(settings, 'RETURN_QR_CODE_VALIDITY_DAYS', 30))).isoformat()
            data['status'] = self.status
            if self.invoice_number and self.branch and self.branch.store:
                data['zatca_data'] = {
                    'seller_name': self.branch.store.name,
                    'vat_registration_number': self.branch.store.tax_id or self.branch.branch_tax_id or '',
                    'invoice_timestamp': self.invoice_issue_date.isoformat() if self.invoice_issue_date else timezone.now().isoformat(),
                    'invoice_total': str(self.total_amount),
                    'vat_total': str(self.total_vat_amount),
                }

        data_string = json.dumps(data, sort_keys=True)

        secret_key_bytes = settings.SECRET_KEY.encode('utf-8')
        signature = hmac.new(
            secret_key_bytes,
            data_string.encode('utf-8'),
            hashlib.sha256
        ).digest()
        data['signature'] = base64.urlsafe_b64encode(signature).decode('utf-8')

        final_data_to_encode = json.dumps(data)

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(final_data_to_encode)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

        try:
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'app_logo.png')
            if os.path.exists(logo_path):
                logo = Image.open(logo_path).convert("RGBA")
                logo_size = int(img.size[0] * 0.20)
                logo = logo.resize((logo_size, logo_size))

                x = (img.size[0] - logo.size[0]) // 2
                y = (img.size[1] - logo.size[1]) // 2

                img.paste(logo, (x, y), logo)
            else:
                print(f"Warning: App logo not found at {logo_path}. QR code generated without logo.")
        except Exception as e:
            print(f"Error embedding logo in QR code for order {self.order_id}: {e}")

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        file_name = f'order_{self.order_id}_{qr_type}.png'

        if qr_type == 'initial':
            self.initial_qr_code.save(file_name, File(buffer), save=False)
        elif qr_type == 'exit':
            self.exit_qr_code.save(file_name, File(buffer), save=False)


# === نموذج عنصر الطلب (OrderItem) ===
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name=_("Order"))
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name=_("Product"))
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name=_("Quantity"))
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], verbose_name=_("Price at Purchase"))
    
    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.15'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('1.00'))],
        help_text=_("VAT Rate as a decimal (e.g., 0.15 for 15%)"),
        verbose_name=_("VAT Rate")
    )
    
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text=_("Commission rate for this specific item at time of sale (for AI training)"),
        verbose_name=_("Commission Percentage (%)")
    )
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), editable=False, verbose_name=_("Commission Amount"))

    product_attributes_for_ai = models.JSONField(null=True, blank=True, verbose_name=_("Product Attributes for AI"))

    class Meta:
        verbose_name = _("Order Item")
        verbose_name_plural = _("Order Items")
        unique_together = ('order', 'product')

    def save(self, *args, **kwargs):
        if not self.price_at_purchase and self.product:
            self.price_at_purchase = self.product.price_after_discount()
        
        # التأكد من استخدام vat_rate من المنتج
        if self.product and hasattr(self.product, 'vat_rate') and self.product.vat_rate is not None:
            self.vat_rate = self.product.vat_rate
        else:
            # قيمة افتراضية إذا لم يكن المنتج يحتوي على معدل ضريبة القيمة المضافة
            self.vat_rate = Decimal(getattr(settings, 'VAT_RATE', '0.15'))


        # حساب العمولة بناءً على معدل العمولة الخاص بالفرع للموظف
        if self.order and self.order.branch and self.order.branch.fee_percentage is not None:
            self.commission_percentage = self.order.branch.fee_percentage
            self.commission_amount = (self.quantity * self.price_at_purchase * self.commission_percentage) / 100
        else:
            self.commission_percentage = Decimal('0.00')
            self.commission_amount = Decimal('0.00')

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} {_('in Order')} {self.order.order_id}"


# === نموذج الدفعة (Payment) ===
# لربط الدفعات بـ Order. يمكن أن يكون للطلب الواحد أكثر من دفعة.
class Payment(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name=_("Order")
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))], # لا يمكن أن تكون الدفعة صفر أو سالبة
        verbose_name=_("Payment Amount")
    )
    payment_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Payment Date")
    )
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', _('Cash')
        ELECTRONIC = 'electronic', _('Electronic Payment')
        CREDIT_BALANCE = 'credit_balance', _('Credit Balance')
        CHEQUE = 'cheque', _('Cheque')
        OTHER = 'other', _('Other')
    method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name=_("Payment Method")
    )
    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Transaction ID")
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_payments',
        verbose_name=_("Received By")
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes")
    )

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ['-payment_date']

    def __str__(self):
        return f"{_('Payment')} {self.amount} {_('for Order')} {self.order.order_id} {_('by')} {self.get_method_display()}"


# === نموذج الإرجاع (Return) ===
# لربط المرتجعات بـ Order. يمكن أن يكون للطلب الواحد أكثر من عملية إرجاع.
class Return(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='returns',
        verbose_name=_("Original Order")
    )
    return_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name=_("Return ID"))
    return_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Return Date")
    )
    total_returned_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Total Returned Amount")
    )
    reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Reason for Return")
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_returns',
        verbose_name=_("Processed By")
    )
    # يمكن أن يكون هناك حقل للإرجاع النقدي أو رصيد المتجر
    refund_method = models.CharField(
        max_length=20,
        choices=[
            ('CASH', _('Cash Refund')),
            ('STORE_CREDIT', _('Store Credit')),
            ('ELECTRONIC_REFUND', _('Electronic Refund')),
            ('EXCHANGE', _('Exchange'))
        ],
        default='CASH',
        verbose_name=_("Refund Method")
    )
    refund_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Refund Transaction ID")
    )
    
    class Meta:
        verbose_name = _("Return")
        verbose_name_plural = _("Returns")
        ordering = ['-return_date']

    def __str__(self):
        return f"{_('Return')} {self.return_id} {_('for Order')} {self.order.order_id}"

    def calculate_total_returned_amount(self):
        """يحسب إجمالي المبلغ المرتجع لهذا الإرجاع."""
        total = self.returned_items.aggregate(
            sum_items=Sum(F('quantity_returned') * F('price_at_return'), output_field=models.DecimalField())
        )['sum_items']
        self.total_returned_amount = total if total is not None else Decimal('0.00')

    def save(self, *args, **kwargs):
        is_new_return = not self.pk
        super().save(*args, **kwargs)
        if is_new_return: # للتأكد من حساب الإجمالي للتو
            self.calculate_total_returned_amount()
            # حفظ بدون تحديث في حلقة مفرغة إذا كانت calculate_total_returned_amount هي من تسبب في حفظ آخر
            # إذا كنت تستدعيها في مكان آخر (مثل إشارة)، فلا داعي للحفظ هنا.
            # للحفاظ على البساطة الآن، سنتجنب الحفظ المتكرر داخل save()
            # إذا أردت حسابها فوراً، قم باستدعائها في إشارة post_save لـ ReturnItem

# === نموذج عنصر الإرجاع (ReturnItem) ===
# لربط المنتجات المرتجعة بعملية الإرجاع.
class ReturnItem(models.Model):
    return_obj = models.ForeignKey( # تم تغيير الاسم لتجنب تضارب مع كلمة 'return' المحجوزة
        Return,
        on_delete=models.CASCADE,
        related_name='returned_items',
        verbose_name=_("Return Record")
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name=_("Returned Product")
    )
    quantity_returned = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name=_("Quantity Returned")
    )
    price_at_return = models.DecimalField( # سعر المنتج عند الإرجاع
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_("Price at Return")
    )
    # يمكن إضافة حقول أخرى مثل سبب إرجاع هذا العنصر بالتحديد

    class Meta:
        verbose_name = _("Returned Item")
        verbose_name_plural = _("Returned Items")
        unique_together = ('return_obj', 'product')

    def __str__(self):
        return f"{self.quantity_returned} x {self.product.name} {_('returned in')} {self.return_obj.return_id}"

    def save(self, *args, **kwargs):
        if not self.price_at_return and self.product:
            self.price_at_return = self.product.price_after_discount() # أو السعر من OrderItem الأصلي
        super().save(*args, **kwargs)

# === Signal لتحديث إجماليات الطلب بعد حفظ أو حذف عنصر طلب ===
@receiver(post_save, sender=OrderItem)
def update_order_totals_on_item_change(sender, instance, **kwargs):
    """
    تحديث إجماليات الطلب عندما يتم حفظ (إنشاء/تعديل) عنصر في الطلب.
    """
    if kwargs.get('raw'):
        return
    order = instance.order
    # استدعاء calculate_totals للحصول على القيم المحدثة
    order.calculate_totals()
    # حفظ الطلب مع تحديث الحقول المحددة فقط لتجنب الحلقات المفرغة
    order.save(update_fields=['total_amount', 'total_amount_before_vat', 'total_vat_amount', 'fee_amount'])


@receiver(post_delete, sender=OrderItem)
def update_order_totals_on_item_actual_delete(sender, instance, **kwargs):
    """
    تحديث إجماليات الطلب عندما يتم حذف عنصر من الطلب فعلياً.
    """
    order = instance.order
    order.refresh_from_db()
    order.calculate_totals()
    order.save(update_fields=['total_amount', 'total_amount_before_vat', 'total_vat_amount', 'fee_amount'])


# --- Signal لتحديث `total_amount` في `TempOrder` عند تعديل `TempOrderItem` ---
@receiver(post_save, sender=TempOrderItem)
def update_temp_order_totals_on_item_save(sender, instance, **kwargs):
    """
    تحديث إجماليات TempOrder عندما يتم حفظ (إنشاء/تعديل) عنصر في TempOrderItem.
    """
    if kwargs.get('raw'):
        return
    temp_order = instance.temp_order
    temp_order.calculate_totals()
    temp_order.save(update_fields=['total_amount'])


@receiver(post_delete, sender=TempOrderItem)
def update_temp_order_totals_on_item_delete(sender, instance, **kwargs):
    """
    تحديث إجماليات TempOrder عندما يتم حذف عنصر من TempOrderItem.
    """
    temp_order = instance.temp_order
    temp_order.refresh_from_db()
    temp_order.calculate_totals()
    temp_order.save(update_fields=['total_amount'])


# --- Signals for Return and ReturnItem ---
@receiver(post_save, sender=ReturnItem)
def update_return_totals_on_item_save(sender, instance, **kwargs):
    """
    تحديث إجماليات Return عندما يتم حفظ (إنشاء/تعديل) عنصر في ReturnItem.
    """
    if kwargs.get('raw'):
        return
    return_obj = instance.return_obj
    return_obj.calculate_total_returned_amount()
    return_obj.save(update_fields=['total_returned_amount'])


@receiver(post_delete, sender=ReturnItem)
def update_return_totals_on_item_delete(sender, instance, **kwargs):
    """
    تحديث إجماليات Return عندما يتم حذف عنصر من ReturnItem.
    """
    return_obj = instance.return_obj
    return_obj.refresh_from_db()
    return_obj.calculate_total_returned_amount()
    return_obj.save(update_fields=['total_returned_amount'])


# Signal to update BranchProductInventory and create InventoryMovement when Order status changes to COMPLETED or RETURNED
@receiver(post_save, sender=Order)
def manage_inventory_and_movements_on_order_status_change(sender, instance, created, **kwargs):
    # لا تقم بأي شيء إذا كان الحفظ خامًا (مثل الهجرات) أو إذا كان status_changed غير صحيح (يعني لم يتغير)
    if kwargs.get('raw'):
        return

    # جلب النسخة القديمة من الطلب للتحقق من تغيير الحالة
    try:
        old_instance = sender.objects.get(pk=instance.pk)
        status_changed = (old_instance.status != instance.status)
    except sender.DoesNotExist:
        # إذا كان الطلب جديدًا تمامًا، اعتبر أن الحالة قد تغيرت (من لا شيء إلى الحالة الحالية)
        old_instance = None
        status_changed = True if created else False # If created, status definitely changed from non-existent

    # إذا تم إنشاء الطلب حديثًا وانتقل مباشرة إلى PAID/COMPLETED
    # أو إذا تغيرت الحالة إلى COMPLETED (من أي حالة سابقة غير COMPLETED)
    if created or (status_changed and instance.status == instance.OrderStatus.COMPLETED):
        if instance.status == instance.OrderStatus.COMPLETED:
            # خصم الكميات من المخزون وإنشاء حركة مخزون 'OUT'
            with transaction.atomic():
                for item in instance.items.all():
                    product_inventory = BranchProductInventory.objects.select_for_update().get(
                        product=item.product,
                        branch=instance.branch
                    )
                    old_quantity = product_inventory.quantity
                    new_quantity = old_quantity - item.quantity

                    if new_quantity < 0:
                        # هذا يجب أن يتم التحقق منه قبل الوصول إلى هنا (مثلاً عند إضافة العنصر للسلة)
                        # ولكن كتحقق إضافي:
                        raise ValidationError(_(f"Insufficient stock for product {item.product.name} in branch {instance.branch.name} during order completion."))
                    
                    product_inventory.quantity = new_quantity
                    product_inventory.save(update_fields=['quantity'])

                    InventoryMovement.objects.create(
                        inventory=product_inventory,
                        product=item.product,
                        branch=instance.branch,
                        movement_type='OUT',
                        quantity_change=-item.quantity, # الكمية سالبة لتعبر عن الخصم
                        old_quantity=old_quantity,
                        new_quantity=new_quantity,
                        reason=f"Sale (Order {instance.order_id})",
                        moved_by=instance.performed_by
                    )
                    print(f"Stock deducted for product {item.product.name} in branch {instance.branch.name}. New quantity: {new_quantity}")


    # إذا تغيرت الحالة إلى RETURNED أو PARTIALLY_RETURNED
    # هذا السيجنال قد لا يكون هو الأنسب لإعادة المخزون عند الإرجاع الفعلي.
    # إعادة المخزون يجب أن تحدث عند إنشاء كائن `ReturnItem` (عنصر المرتجع).
    # هذا المنطق هنا يمكن استخدامه لتغيير حالة الطلب في قاعدة البيانات.
    # سأضع هذا كتعليق حالياً وأقترح معالجته عند إنشاء ReturnItem.
    # elif status_changed and instance.status in [instance.OrderStatus.RETURNED, instance.OrderStatus.PARTIALLY_RETURNED]:
    #     # هنا يجب أن يتم إعادة الكميات إلى المخزون بناءً على عناصر الإرجاع الفعلية
    #     # وليس فقط تغيير حالة الطلب.
    #     # هذا المنطق سيكون أفضل في سيجنال `post_save` لـ `ReturnItem`
    #     pass

# Signal to update BranchProductInventory and create InventoryMovement when ReturnItem is saved
@receiver(post_save, sender=ReturnItem)
def manage_inventory_and_movements_on_return_item_save(sender, instance, created, **kwargs):
    if kwargs.get('raw'):
        return

    return_obj = instance.return_obj
    product = instance.product
    quantity_returned = instance.quantity_returned
    branch = return_obj.order.branch # الفرع الذي تمت فيه العملية الأصلية

    with transaction.atomic():
        # البحث عن سجل المخزون وتأمين الصف
        product_inventory = BranchProductInventory.objects.select_for_update().get(
            product=product,
            branch=branch
        )
        
        old_quantity = product_inventory.quantity
        new_quantity = old_quantity + quantity_returned # إعادة الكمية للمخزون

        product_inventory.quantity = new_quantity
        product_inventory.save(update_fields=['quantity'])

        InventoryMovement.objects.create(
            inventory=product_inventory,
            product=product,
            branch=branch,
            movement_type='IN', # يمكن أن يكون 'RETURN_IN'
            quantity_change=quantity_returned, # الكمية موجبة لتعبر عن الإضافة
            old_quantity=old_quantity,
            new_quantity=new_quantity,
            reason=f"Return (Return ID: {return_obj.return_id})",
            moved_by=return_obj.processed_by # المستخدم الذي قام بعملية الإرجاع
        )
        print(f"Stock returned for product {product.name} in branch {branch.name}. New quantity: {new_quantity}")

        # تحديث حالة الطلب الأصلي إذا تم إرجاع جميع المنتجات
        # هذا منطق معقد بعض الشيء، وقد يحتاج لمراجعة عدد المنتجات في الطلب وعدد المرتجعات.
        # للحفاظ على البساطة، لن نغير حالة الطلب هنا، بل نتركها للـ Viewsets أو منطق مخصص آخر.

@receiver(post_delete, sender=ReturnItem)
def manage_inventory_and_movements_on_return_item_delete(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    
    # عند حذف عنصر مرتجع، يجب خصم الكمية من المخزون
    return_obj = instance.return_obj
    product = instance.product
    quantity_returned = instance.quantity_returned
    branch = return_obj.order.branch

    with transaction.atomic():
        product_inventory = BranchProductInventory.objects.select_for_update().get(
            product=product,
            branch=branch
        )

        old_quantity = product_inventory.quantity
        new_quantity = old_quantity - quantity_returned # خصم الكمية التي تم إضافتها سابقاً

        if new_quantity < 0:
            print(f"Warning: Deleting ReturnItem caused negative stock for {product.name} in {branch.name}. Manual adjustment needed.")
            new_quantity = 0 # منع الكمية السالبة
            
        product_inventory.quantity = new_quantity
        product_inventory.save(update_fields=['quantity'])

        InventoryMovement.objects.create(
            inventory=product_inventory,
            product=product,
            branch=branch,
            movement_type='ADJUSTMENT', # أو 'RETURN_OUT_ADJUSTMENT'
            quantity_change=-quantity_returned,
            old_quantity=old_quantity,
            new_quantity=new_quantity,
            reason=f"Return Item Deleted (Return ID: {return_obj.return_id}) - Quantity removed from stock.",
            moved_by=return_obj.processed_by # أو المستخدم الحالي إذا كان الحذف يدوياً في لوحة الإدارة
        )
        print(f"Stock adjusted down for product {product.name} in branch {branch.name} due to ReturnItem deletion. New quantity: {new_quantity}")

