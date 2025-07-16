# C:\Users\DELL\SER SQL MY APP\integrations\models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal # Needed for DecimalField

# Import the correct model from the sales app
from sales.models import Order # الآن Order هو نموذج الفاتورة الأساسي


class AccountingSystemConfig(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Configuration Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    api_base_url = models.URLField(verbose_name=_("API Base URL"))
    api_key = models.CharField(max_length=255, verbose_name=_("API Key (or Token)"))
    is_active = models.BooleanField(default=False, verbose_name=_("Is Active Configuration"))
    
    # حقل جديد: نوع نظام المحاسبة (مثلاً Rewaa, QuickBooks, ZATCA)
    SYSTEM_TYPE_CHOICES = (
        ('REWAA', 'Rewaa'),
        ('QUICKBOOKS', 'QuickBooks Online'),
        ('XERO', 'Xero'),
        ('ZATCA_EINV', 'ZATCA E-Invoicing'), # أضف هذا الخيار لـ ZATCA
        # أضف المزيد هنا حسب الحاجة
    )
    system_type = models.CharField(
        max_length=50,
        choices=SYSTEM_TYPE_CHOICES,
        default='ZATCA_EINV', # يمكن تعيين قيمة افتراضية مناسبة
        verbose_name=_("Accounting/Integration System Type")
    )
    
    # Timestamps
    last_synced_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Synced At"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        verbose_name = _("Accounting System Configuration")
        verbose_name_plural = _("Accounting System Configurations")

    def __str__(self):
        return self.name

class ProductSyncLog(models.Model):
    config = models.ForeignKey(
        AccountingSystemConfig,
        on_delete=models.CASCADE,
        related_name='product_sync_logs',
        verbose_name=_("Accounting System Configuration")
    )
    sync_date = models.DateTimeField(auto_now_add=True, verbose_name=_("Sync Date"))
    
    status_choices = (
        ('PENDING', _('Pending')),
        ('SUCCESS', _('Success')),
        ('FAILED', _('Failed')),
        ('IN_PROGRESS', _('In Progress')),
    )
    status = models.CharField(max_length=15, choices=status_choices, default='PENDING', verbose_name=_("Sync Status"))
    message = models.TextField(blank=True, null=True, verbose_name=_("Sync Message"))
    
    products_synced = models.PositiveIntegerField(default=0, verbose_name=_("Products Synced"))
    errors_count = models.PositiveIntegerField(default=0, verbose_name=_("Errors Count"))

    class Meta:
        verbose_name = _("Product Sync Log")
        verbose_name_plural = _("Product Sync Logs")
        ordering = ['-sync_date']

    def __str__(self):
        return f"{self.config.name} - {self.sync_date.strftime('%Y-%m-%d')} - {self.status}"

class SaleInvoiceSyncLog(models.Model):
    config = models.ForeignKey(
        AccountingSystemConfig,
        on_delete=models.CASCADE,
        related_name='sale_invoice_sync_logs',
        verbose_name=_("Accounting System Configuration")
    )
    order = models.ForeignKey( # هذا الآن يشير إلى Order مباشرة
        Order,
        on_delete=models.CASCADE,
        related_name='invoice_sync_logs',
        verbose_name=_("Related Order")
    )
    status_choices = (
        ('PENDING', _('Pending')),
        ('SUCCESS', _('Success')),
        ('FAILED', _('Failed')),
        ('RETRIED', _('Retried')),
    )
    status = models.CharField(max_length=10, choices=status_choices, default='PENDING', verbose_name=_("Sync Status"))
    message = models.TextField(blank=True, null=True, verbose_name=_("Sync Message"))
    sync_date = models.DateTimeField(auto_now_add=True, verbose_name=_("Sync Date"))
    accounting_invoice_id = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Accounting System Invoice ID"))
    
    app_commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("App Commission Rate (%)")
    )
    total_amount_before_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Total Amount Before Commission")
    )
    amount_sent_to_accounting = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Amount Sent to Accounting")
    )

    class Meta:
        verbose_name = _("Sale Invoice Sync Log")
        verbose_name_plural = _("Sale Invoice Sync Logs")
        ordering = ['-sync_date']

    def __str__(self):
        return f"{self.order.order_id} - {self.status} on {self.sync_date.strftime('%Y-%m-%d %H:%M')}"

# === نموذج ZatcaInvoice - لتفاصيل الفاتورة الإلكترونية الفنية ===
class ZatcaInvoice(models.Model):
    # ربط الفاتورة الإلكترونية بـ Order
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='zatca_details',
        verbose_name=_("Related Order/Invoice")
    )

    uuid = models.UUIDField(
        unique=True,
        null=True, blank=True,
        verbose_name=_("ZATCA UUID")
    )

    invoice_hash = models.CharField(
        max_length=255,
        null=True, blank=True,
        verbose_name=_("Invoice Hash")
    )

    cryptographic_stamp = models.TextField(
        null=True, blank=True,
        verbose_name=_("Cryptographic Stamp")
    )

    qr_code_string = models.TextField(
        null=True, blank=True,
        verbose_name=_("QR Code Data (Base64)")
    )

    xml_content = models.TextField(
        null=True, blank=True,
        verbose_name=_("Fatoora XML Content")
    )

    zatca_response = models.JSONField(
        null=True, blank=True,
        verbose_name=_("Last ZATCA API Response")
    )

    last_submission_date = models.DateTimeField(
        null=True, blank=True,
        verbose_name=_("Last ZATCA Submission Date")
    )

    ZATCA_PROCESSING_STATUS_CHOICES = (
        ('PENDING', _('Pending Processing')),
        ('ACCEPTED', _('Accepted by ZATCA')),
        ('REJECTED', _('Rejected by ZATCA')),
        ('REPORTED', _('Reported (Phase 1)')),
        ('CLEARED', _('Cleared (Phase 2)')),
        ('FAILED_VALIDATION', _('Failed ZATCA Validation')),
        ('UNKNOWN', _('Unknown Status')),
    )
    processing_status = models.CharField(
        max_length=20,
        choices=ZATCA_PROCESSING_STATUS_CHOICES,
        default='PENDING',
        verbose_name=_("ZATCA Processing Status")
    )

    error_message = models.TextField(
        null=True, blank=True,
        verbose_name=_("ZATCA Error Message")
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))


    class Meta:
        verbose_name = _("ZATCA E-Invoice Detail")
        verbose_name_plural = _("ZATCA E-Invoice Details")
        ordering = ['-created_at']

    def __str__(self):
        return f"ZATCA Details for Order {self.order.order_id} - Status: {self.processing_status}"