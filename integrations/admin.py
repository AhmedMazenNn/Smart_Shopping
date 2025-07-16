# integrations/admin.py

from django.contrib import admin
from .models import AccountingSystemConfig, ProductSyncLog, SaleInvoiceSyncLog
from django.utils.translation import gettext_lazy as _

@admin.register(AccountingSystemConfig)
class AccountingSystemConfigAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'api_base_url',
        'is_active',
        'last_synced_at',
        'created_at',
    )
    list_filter = ('is_active', 'created_at', 'updated_at',)
    search_fields = ('name', 'description', 'api_base_url',)
    readonly_fields = ('last_synced_at', 'created_at', 'updated_at',)
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'api_base_url', 'api_key', 'is_active')
        }),
        (_('Timestamps'), {
            'fields': ('last_synced_at', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

@admin.register(ProductSyncLog)
class ProductSyncLogAdmin(admin.ModelAdmin):
    list_display = (
        'config',
        'sync_date',
        'status',
        'products_synced',  # This field must exist in ProductSyncLog model
        'errors_count',     # This field must exist in ProductSyncLog model
    )
    list_filter = ('status', 'sync_date', 'config__name',)
    search_fields = ('message',)
    readonly_fields = ('sync_date', 'message', 'products_synced', 'errors_count')

    def message_preview(self, obj):
        return obj.message[:100] + '...' if obj.message and len(obj.message) > 100 else obj.message
    message_preview.short_description = _("Message Preview")


@admin.register(SaleInvoiceSyncLog)
class SaleInvoiceSyncLogAdmin(admin.ModelAdmin):
    list_display = (
        'config',
        'order',  # This must match the field name in SaleInvoiceSyncLog model
        'sync_date',
        'status',
        'accounting_invoice_id',
        'app_commission_rate',
        'amount_sent_to_accounting',
    )
    list_filter = (
        'status',
        'sync_date',
        'config__name',
    )
    search_fields = ('message', 'accounting_invoice_id', 'order__order_id',)
    readonly_fields = (
        'sync_date',
        'message',
        'accounting_invoice_id',
        'app_commission_rate',
        'total_amount_before_commission',
        'amount_sent_to_accounting',
    )