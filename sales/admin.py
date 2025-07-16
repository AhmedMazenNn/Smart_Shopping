# C:\Users\DELL\SER SQL MY APP\sales\admin.py

from django.contrib import admin
from django.contrib import messages
from django.db.models import Sum, F # F for aggregate calculation
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _ # إضافة للترجمة
from decimal import Decimal # لضمان التعامل الصحيح مع Decimal

# استيراد نماذج هذا التطبيق
from .models import Order, OrderItem, TempOrder, TempOrderItem, Payment, Return, ReturnItem # تم تحديث جميع النماذج

# استيراد النماذج من تطبيقاتها الأخرى التي يحتاجها هذا الملف
from stores.models import Branch # Order ترتبط بـ Branch
from products.models import Product, BranchProductInventory # OrderItem ترتبط بـ Product، ونحتاج BranchProductInventory للتحقق من الصلاحيات

User = get_user_model()

# --- Inline for TempOrderItem (تظهر داخل صفحة تعديل TempOrder) ---
class TempOrderItemInline(admin.TabularInline):
    model = TempOrderItem
    extra = 0
    # إضافة scanned_quantity للحقول المعروضة
    fields = ('product', 'quantity', 'scanned_quantity', 'price_at_scan',)
    readonly_fields = ('price_at_scan',) # price_at_scan للقراءة فقط، يتم حسابه تلقائياً
    raw_id_fields = ('product',) # استخدام raw_id_fields لتحسين الأداء

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        # لا توجد حقول لـ AI أو عمولة هنا لأنها طلبات مؤقتة
        return fields

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        return readonly_fields

# --- Admin for TempOrder (الطلبات المؤقتة للكاشير) ---
@admin.register(TempOrder)
class TempOrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'branch',
        'cashier',
        'total_amount', # إجمالي المبلغ المحسوب
        'created_at',
        'updated_at',
    )
    list_filter = ('branch', 'cashier', 'created_at',)
    search_fields = ('id__icontains', 'branch__name', 'cashier__username',)
    readonly_fields = ('created_at', 'updated_at', 'total_amount',) # total_amount يتم حسابه بواسطة signal
    raw_id_fields = ('branch', 'cashier',)
    inlines = [TempOrderItemInline]

    def save_model(self, request, obj, form, change):
        # تعيين الكاشير الذي أنشأ الطلب المؤقت تلقائياً
        if not obj.cashier:
            obj.cashier = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager():
            return qs
        if user.is_store_manager_user() and user.store:
            return qs.filter(branch__store=user.store)
        if user.is_branch_manager_user() and user.branch:
            return qs.filter(branch=user.branch)
        if user.is_cashier_user() and user.branch:
            return qs.filter(branch=user.branch, cashier=user)
        return qs.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        user = request.user
        if not user.is_superuser and not user.is_app_owner() and not user.is_project_manager():
            if user.is_store_manager_user() and user.store:
                form.base_fields['branch'].queryset = Branch.objects.filter(store=user.store)
            elif (user.is_branch_manager_user() or user.is_cashier_user()) and user.branch:
                form.base_fields['branch'].queryset = Branch.objects.filter(pk=user.branch.pk)
                form.base_fields['branch'].initial = user.branch
                form.base_fields['branch'].widget.attrs['disabled'] = True
            
            # Make cashier field read-only and set to current user for non-superusers/app-owners/project-managers
            form.base_fields['cashier'].queryset = User.objects.filter(pk=user.pk)
            form.base_fields['cashier'].initial = user
            form.base_fields['cashier'].widget.attrs['disabled'] = True
        return form

# --- Inline for OrderItem (تظهر داخل صفحة تعديل Order) ---
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('product', 'quantity', 'price_at_purchase', 'vat_rate', 'commission_percentage', 'commission_amount', 'product_attributes_for_ai')
    readonly_fields = ('price_at_purchase', 'vat_rate', 'commission_amount',)
    raw_id_fields = ('product',)

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        # إخفاء حقول العمولة وخصائص الذكاء الاصطناعي عن غير المدراء العامين ومدراء المتاجر
        if not (request.user.is_superuser or request.user.is_app_owner() or request.user.is_project_manager() or \
                (hasattr(request.user, 'is_store_manager_user') and request.user.is_store_manager_user())):
            fields_to_remove = ['commission_percentage', 'commission_amount', 'product_attributes_for_ai']
            for field_name in fields_to_remove:
                if field_name in fields:
                    fields.remove(field_name)
        return fields

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        # السماح فقط للسوبر يوزر ومالك التطبيق ومدير المشروع ومدير المتجر بتعديل كل الحقول
        if not (request.user.is_superuser or request.user.is_app_owner() or request.user.is_project_manager() or \
                (hasattr(request.user, 'is_store_manager_user') and request.user.is_store_manager_user())):
            # باقي الأدوار يمكنها تعديل الكمية فقط (quantity)
            readonly_fields.extend([
                'product', 'price_at_purchase', 'vat_rate', 'commission_percentage',
                'commission_amount', 'product_attributes_for_ai'
            ])
            # إذا كان المستخدم مدير فرع أو كاشير، يمكنه فقط تعديل الكمية
            if (hasattr(request.user, 'is_branch_manager_user') and request.user.is_branch_manager_user()) or \
               (hasattr(request.user, 'is_cashier_user') and request.user.is_cashier_user()):
                # إذا كانت الدالة الأصلية تحظر تعديل حقول معينة، يجب احترام ذلك.
                # هنا، نحن نسمح بتعديل الكمية فقط.
                pass # quantity is not in readonly_fields, so it's editable by default.
        return readonly_fields
    
    # فلترة المنتجات المتاحة في الـ inline بناءً على الفرع المحدد في الطلب
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            if self.parent_instance and self.parent_instance.branch:
                # فلترة المنتجات التي لها مخزون في فرع الطلب
                kwargs["queryset"] = Product.objects.filter(branch_inventories__branch=self.parent_instance.branch).distinct()
            else:
                kwargs["queryset"] = Product.objects.none() # لا يوجد فرع محدد، فلا يوجد منتجات
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# --- Inline for Payment ---
class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ('amount', 'method', 'transaction_id', 'received_by', 'notes')
    readonly_fields = ('payment_date', 'received_by',) # received_by يتم تعيينه تلقائيا
    raw_id_fields = ('received_by',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager():
            return qs
        if user.is_store_manager_user() and user.store:
            return qs.filter(order__branch__store=user.store)
        if user.is_branch_manager_user() and user.branch:
            return qs.filter(order__branch=user.branch)
        if user.is_cashier_user() and user.branch:
            return qs.filter(order__branch=user.branch) # الكاشير يمكنه رؤية دفعات فرعه
        return qs.none()
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        user = request.user
        if not user.is_superuser and not user.is_app_owner() and not user.is_project_manager():
            # جعل received_by للقراءة فقط وتعيينه للمستخدم الحالي
            formset.form.base_fields['received_by'].queryset = User.objects.filter(pk=user.pk)
            formset.form.base_fields['received_by'].initial = user
            formset.form.base_fields['received_by'].widget.attrs['disabled'] = True
        return formset


# --- Inline for ReturnItem ---
class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 0
    fields = ('product', 'quantity_returned', 'price_at_return',)
    readonly_fields = ('price_at_return',)
    raw_id_fields = ('product',)

    # فلترة المنتجات المتاحة في الـ inline بناءً على المنتجات الأصلية في الطلب المرتبط بعملية الإرجاع
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            if self.parent_instance and self.parent_instance.order:
                # المنتجات التي تم شراؤها في الطلب الأصلي
                kwargs["queryset"] = Product.objects.filter(orderitem__order=self.parent_instance.order).distinct()
            else:
                kwargs["queryset"] = Product.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# --- Inline for Return (تظهر داخل صفحة تعديل Order) ---
class ReturnInline(admin.TabularInline):
    model = Return
    extra = 0
    fields = ('return_id', 'return_date', 'total_returned_amount', 'reason', 'processed_by', 'refund_method', 'refund_transaction_id')
    readonly_fields = ('return_id', 'return_date', 'total_returned_amount', 'processed_by',) # processed_by يتم تعيينه تلقائيا
    raw_id_fields = ('processed_by',)
    inlines = [ReturnItemInline] # Nested inline for ReturnItems

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager():
            return qs
        if user.is_store_manager_user() and user.store:
            return qs.filter(order__branch__store=user.store)
        if user.is_branch_manager_user() and user.branch:
            return qs.filter(order__branch=user.branch)
        if user.is_cashier_user() and user.branch:
            return qs.filter(order__branch=user.branch)
        return qs.none()

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        user = request.user
        if not user.is_superuser and not user.is_app_owner() and not user.is_project_manager():
            # جعل processed_by للقراءة فقط وتعيينه للمستخدم الحالي
            formset.form.base_fields['processed_by'].queryset = User.objects.filter(pk=user.pk)
            formset.form.base_fields['processed_by'].initial = user
            formset.form.base_fields['processed_by'].widget.attrs['disabled'] = True
        return formset


# --- Admin for Order ---
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_id',
        'branch',
        'date',
        'invoice_number',
        'accounting_invoice_id', # New field
        'invoice_issue_date',
        'total_amount',
        'total_amount_before_vat',
        'total_vat_amount',
        'zatca_submission_status',
        'status',
        'payment_method',
        'customer_display',
        'customer_tax_id',
        'performed_by',
        'initial_qr_code_display',
        'exit_qr_code_display',
        'exit_qr_code_expiry',
    )
    list_filter = ('branch', 'date', 'status', 'payment_method', 'performed_by', 'zatca_submission_status', 'is_exchange') # Added is_exchange
    search_fields = (
        'order_id__icontains',
        'invoice_number__icontains',
        'accounting_invoice_id__icontains', # New search field
        'branch__name',
        'customer__username',
        'customer__first_name',
        'non_app_customer_name',
        'customer_tax_id',
        'performed_by__username',
        'transaction_id'
    )
    readonly_fields = (
        'order_id',
        'recorded_at',
        'fee_amount',
        'transaction_id',
        'paid_at',
        'completed_at',
        'invoice_number',
        'invoice_issue_date',
        'total_amount',
        'total_amount_before_vat',
        'total_vat_amount',
        'zatca_submission_status',
        'initial_qr_code_display',
        'exit_qr_code_display',
        'exit_qr_code_expiry',
    )
    raw_id_fields = ('branch', 'customer', 'performed_by', 'original_order_for_return',)
    inlines = [OrderItemInline, PaymentInline, ReturnInline] # Add Payment and Return inlines
    fieldsets = (
        (None, {
            'fields': (
                'branch', 'date', 'customer', 'non_app_customer_name', 'non_app_customer_phone', 'customer_tax_id',
                'performed_by'
            )
        }),
        (_('Order Details'), {
            'fields': ('status', 'payment_method', 'transaction_id', 'paid_at', 'completed_at'),
        }),
        (_('Financial Details'), {
            'fields': ('total_amount_before_vat', 'total_vat_amount', 'total_amount', 'fee_amount'),
        }),
        (_('Invoice Details (ZATCA)'), {
            'fields': ('invoice_number', 'invoice_issue_date', 'accounting_invoice_id', 'zatca_submission_status'), # Added accounting_invoice_id
            'classes': ('collapse',),
        }),
        (_('QR Codes'), {
            'fields': ('initial_qr_code_display', 'exit_qr_code_display', 'exit_qr_code_expiry'),
            'classes': ('collapse',),
        }),
        (_('Return/Exchange Details'), {
            'fields': ('is_exchange', 'original_order_for_return'),
            'classes': ('collapse',),
        }),
    )

    def customer_display(self, obj):
        if obj.customer:
            return obj.customer.username
        elif obj.non_app_customer_name:
            return obj.non_app_customer_name
        return _("N/A")
    customer_display.short_description = _("Customer")

    def initial_qr_code_display(self, obj):
        if obj.initial_qr_code:
            return format_html('<img src="{}" width="100" height="100" style="border-radius: 5px;" />', obj.initial_qr_code.url)
        return _("No initial QR code")
    initial_qr_code_display.short_description = _("Initial QR Code")

    def exit_qr_code_display(self, obj):
        if obj.exit_qr_code:
            return format_html('<img src="{}" width="100" height="100" style="border-radius: 5px;" />', obj.exit_qr_code.url)
        return _("No exit QR code")
    exit_qr_code_display.short_description = _("Exit QR Code")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager():
            return qs
        if user.is_store_manager_user() and user.store:
            return qs.filter(branch__store=user.store)
        if user.is_branch_manager_user() and user.branch:
            return qs.filter(branch=user.branch)
        if user.is_cashier_user() and user.branch:
            # الكاشير يرى الطلبات التي قام بإنشائها
            return qs.filter(branch=user.branch, performed_by=user)
        return qs.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        user = request.user
        
        # صلاحيات المستخدمين على حقول الفرع (الفرع الذي يستطيع المستخدم رؤيته أو تعديله)
        if not user.is_superuser and not user.is_app_owner() and not user.is_project_manager():
            if user.is_store_manager_user() and user.store:
                form.base_fields['branch'].queryset = Branch.objects.filter(store=user.store)
            elif (user.is_branch_manager_user() or user.is_cashier_user()) and user.branch:
                form.base_fields['branch'].queryset = Branch.objects.filter(id=user.branch.id)
                form.base_fields['branch'].initial = user.branch
                form.base_fields['branch'].widget.attrs['disabled'] = True # منع التغيير بعد الاختيار الأولي
            else:
                form.base_fields['branch'].queryset = Branch.objects.none() # منع أي اختيار للفرع إذا لم يكن له صلاحية

            # جعل حقل 'performed_by' للقراءة فقط وتعيينه للمستخدم الحالي إذا لم يكن سوبر يوزر
            form.base_fields['performed_by'].widget.attrs['disabled'] = True
            form.base_fields['performed_by'].initial = user

            # حقول العميل غير المسجل: فقط الكاشير والموظف العام يمكنهم تعديلها إذا كانت هذه وظيفتهم
            if not (user.is_cashier_user() or user.is_general_staff_user()):
                form.base_fields['non_app_customer_name'].widget.attrs['readonly'] = True
                form.base_fields['non_app_customer_phone'].widget.attrs['readonly'] = True
                form.base_fields['customer_tax_id'].widget.attrs['readonly'] = True
            
            # حقل العميل المسجل: يمكن لغير المشرفين فقط تعديله إذا كانوا يؤدون دور الكاشير/الموظف العام لربط الطلب بعميل مسجل
            # ولكن لا يمكنهم تعيينه لأنفسهم كعميل
            if not (user.is_cashier_user() or user.is_general_staff_user()):
                form.base_fields['customer'].widget.attrs['disabled'] = True

        return form

    def save_model(self, request, obj, form, change):
        if not obj.performed_by:
            obj.performed_by = request.user
        
        # إذا كان الطلب له عميل مسجل، يجب مسح حقول العميل غير المسجل
        if obj.customer:
            obj.non_app_customer_name = None
            obj.non_app_customer_phone = None
        
        # عند حفظ الطلب، يتم حساب الإجماليات مرة أخرى لضمان الدقة
        obj.calculate_totals() # تأكد أن هذه الدالة تحدث total_amount, total_amount_before_vat, total_vat_amount, fee_amount
        super().save_model(request, obj, form, change)


# --- Admin for Payment ---
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'amount', 'method', 'payment_date', 'received_by',)
    list_filter = ('method', 'payment_date', 'received_by',)
    search_fields = ('order__order_id__icontains', 'transaction_id',)
    raw_id_fields = ('order', 'received_by',)
    readonly_fields = ('payment_date',)

    def save_model(self, request, obj, form, change):
        if not obj.received_by:
            obj.received_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager():
            return qs
        if user.is_store_manager_user() and user.store:
            return qs.filter(order__branch__store=user.store)
        if user.is_branch_manager_user() and user.branch:
            return qs.filter(order__branch=user.branch)
        if user.is_cashier_user() and user.branch:
            return qs.filter(order__branch=user.branch)
        return qs.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        user = request.user
        if not user.is_superuser and not user.is_app_owner() and not user.is_project_manager():
            form.base_fields['received_by'].queryset = User.objects.filter(pk=user.pk)
            form.base_fields['received_by'].initial = user
            form.base_fields['received_by'].widget.attrs['disabled'] = True
            
            # Restrict order selection based on user's branch/store
            if user.is_store_manager_user() and user.store:
                form.base_fields['order'].queryset = Order.objects.filter(branch__store=user.store)
            elif (user.is_branch_manager_user() or user.is_cashier_user()) and user.branch:
                form.base_fields['order'].queryset = Order.objects.filter(branch=user.branch)
            else:
                form.base_fields['order'].queryset = Order.objects.none()
        return form


# --- Admin for Return ---
@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ('return_id', 'order', 'total_returned_amount', 'return_date', 'processed_by', 'refund_method',)
    list_filter = ('return_date', 'processed_by', 'refund_method',)
    search_fields = ('return_id__icontains', 'order__order_id__icontains',)
    raw_id_fields = ('order', 'processed_by',)
    readonly_fields = ('return_id', 'return_date', 'total_returned_amount',)
    inlines = [ReturnItemInline]

    def save_model(self, request, obj, form, change):
        if not obj.processed_by:
            obj.processed_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager():
            return qs
        if user.is_store_manager_user() and user.store:
            return qs.filter(order__branch__store=user.store)
        if user.is_branch_manager_user() and user.branch:
            return qs.filter(order__branch=user.branch)
        if user.is_cashier_user() and user.branch:
            return qs.filter(order__branch=user.branch)
        return qs.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        user = request.user
        if not user.is_superuser and not user.is_app_owner() and not user.is_project_manager():
            form.base_fields['processed_by'].queryset = User.objects.filter(pk=user.pk)
            form.base_fields['processed_by'].initial = user
            form.base_fields['processed_by'].widget.attrs['disabled'] = True

            # Restrict order selection based on user's branch/store
            if user.is_store_manager_user() and user.store:
                form.base_fields['order'].queryset = Order.objects.filter(branch__store=user.store)
            elif (user.is_branch_manager_user() or user.is_cashier_user()) and user.branch:
                form.base_fields['order'].queryset = Order.objects.filter(branch=user.branch)
            else:
                form.base_fields['order'].queryset = Order.objects.none()
        return form


# --- Admin for ReturnItem ---
@admin.register(ReturnItem)
class ReturnItemAdmin(admin.ModelAdmin):
    list_display = ('return_obj', 'product', 'quantity_returned', 'price_at_return',)
    list_filter = ('return_obj__return_date', 'product__name',)
    search_fields = ('return_obj__return_id__icontains', 'product__name__icontains',)
    raw_id_fields = ('return_obj', 'product',)
    readonly_fields = ('price_at_return',)

    def save_model(self, request, obj, form, change):
        # Ensure price_at_return is set
        if not obj.price_at_return and obj.product:
            obj.price_at_return = obj.product.price_after_discount() # Or fetch from original order item
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager():
            return qs
        if user.is_store_manager_user() and user.store:
            return qs.filter(return_obj__order__branch__store=user.store)
        if user.is_branch_manager_user() and user.branch:
            return qs.filter(return_obj__order__branch=user.branch)
        if user.is_cashier_user() and user.branch:
            return qs.filter(return_obj__order__branch=user.branch)
        return qs.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        user = request.user
        if not user.is_superuser and not user.is_app_owner() and not user.is_project_manager():
            # Restrict return_obj selection based on user's branch/store
            if user.is_store_manager_user() and user.store:
                form.base_fields['return_obj'].queryset = Return.objects.filter(order__branch__store=user.store)
            elif (user.is_branch_manager_user() or user.is_cashier_user()) and user.branch:
                form.base_fields['return_obj'].queryset = Return.objects.filter(order__branch=user.branch)
            else:
                form.base_fields['return_obj'].queryset = Return.objects.none()
            
            # Restrict product selection to products in the associated branch's inventory
            if 'return_obj' in form.base_fields and form.base_fields['return_obj'].initial:
                # If a return object is already selected, filter by products in its order's branch
                initial_return = Return.objects.get(pk=form.base_fields['return_obj'].initial)
                if initial_return.order and initial_return.order.branch:
                    form.base_fields['product'].queryset = Product.objects.filter(
                        branch_inventories__branch=initial_return.order.branch
                    ).distinct()
                else:
                    form.base_fields['product'].queryset = Product.objects.none()
            elif (user.is_store_manager_user() and user.store) or \
                 ((user.is_branch_manager_user() or user.is_cashier_user()) and user.branch):
                # If creating a new ReturnItem and user has a store/branch, filter products from there
                if user.is_store_manager_user() and user.store:
                    form.base_fields['product'].queryset = Product.objects.filter(
                        branch_inventories__branch__store=user.store
                    ).distinct()
                elif (user.is_branch_manager_user() or user.is_cashier_user()) and user.branch:
                    form.base_fields['product'].queryset = Product.objects.filter(
                        branch_inventories__branch=user.branch
                    ).distinct()
            else:
                form.base_fields['product'].queryset = Product.objects.none()
        return form

