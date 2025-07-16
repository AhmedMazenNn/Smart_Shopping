# integrations/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

from sales.models import Order
from . import constants
from .utils import calculate_commission_amount


class AccountingSystemConfig(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Configuration Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    api_base_url = models.URLField(verbose_name=_("API Base URL"))
    api_key = models.CharField(max_length=255, verbose_name=_("API Key (or Token)"))
    is_active = models.BooleanField(default=False, verbose_name=_("Is Active Configuration"))

    system_type = models.CharField(
        max_length=50,
        choices=constants.SYSTEM_TYPE_CHOICES,
        default='ZATCA_EINV',
        verbose_name=_("Accounting/Integration System Type")
    )

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

    status = models.CharField(
        max_length=15,
        choices=constants.SYNC_STATUS_CHOICES,
        default='PENDING',
        verbose_name=_("Sync Status")
    )
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
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='invoice_sync_logs',
        verbose_name=_("Related Order")
    )
    status = models.CharField(
        max_length=10,
        choices=constants.SYNC_STATUS_CHOICES,
        default='PENDING',
        verbose_name=_("Sync Status")
    )
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

    def calculate_amount_sent(self):
        self.amount_sent_to_accounting = calculate_commission_amount(
            self.total_amount_before_commission, self.app_commission_rate
        )


class ZatcaInvoice(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='zatca_details',
        verbose_name=_("Related Order/Invoice")
    )
    uuid = models.UUIDField(unique=True, null=True, blank=True, verbose_name=_("ZATCA UUID"))
    invoice_hash = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Invoice Hash"))
    cryptographic_stamp = models.TextField(null=True, blank=True, verbose_name=_("Cryptographic Stamp"))
    qr_code_string = models.TextField(null=True, blank=True, verbose_name=_("QR Code Data (Base64)"))
    xml_content = models.TextField(null=True, blank=True, verbose_name=_("Fatoora XML Content"))
    zatca_response = models.JSONField(null=True, blank=True, verbose_name=_("Last ZATCA API Response"))
    last_submission_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Last ZATCA Submission Date"))

    processing_status = models.CharField(
        max_length=20,
        choices=constants.ZATCA_PROCESSING_STATUS_CHOICES,
        default='PENDING',
        verbose_name=_("ZATCA Processing Status")
    )
    error_message = models.TextField(null=True, blank=True, verbose_name=_("ZATCA Error Message"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        verbose_name = _("ZATCA E-Invoice Detail")
        verbose_name_plural = _("ZATCA E-Invoice Details")
        ordering = ['-created_at']

    def __str__(self):
        return f"ZATCA Details for Order {self.order.order_id} - Status: {self.processing_status}"
