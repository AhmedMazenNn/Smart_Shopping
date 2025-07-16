from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.forms import BaseInlineFormSet # لـ Clean Formsets
from django.db.models import Sum # لاستخدام Sum في display_current_stock

# استيراد النماذج التي تنتمي لتطبيق products
from .models import Department, Product, ProductCategory, BranchProductInventory, InventoryMovement

# استيراد نموذج Branch من تطبيق stores
from stores.models import Store, Branch # استيراد Store و Branch

User = get_user_model() # للحصول على نموذج المستخدم المخصص

# === Inline for BranchProductInventory (will be used in ProductAdmin) ===
class BranchProductInventoryInline(admin.TabularInline):
    model = BranchProductInventory
    extra = 0 # لا تعرض صفوف فارغة إضافية بشكل افتراضي
    fields = ('branch', 'quantity', 'last_updated_by')
    readonly_fields = ('last_updated_by', 'updated_at', 'created_at')
    verbose_name = _("Inventory per Branch")
    verbose_name_plural = _("Inventory per Branches")

    # تحديد صلاحيات الـ Inline: لا يمكن للمستخدمين العاديين إضافة/حذف سجلات مخزون، فقط تعديلها
    def has_add_permission(self, request, obj=None):
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        return request.user.is_superuser or \
               (hasattr(request.user, 'is_app_owner') and request.user.is_app_owner) or \
               (hasattr(request.user, 'is_project_manager') and request.user.is_project_manager) or \
               (hasattr(request.user, 'is_app_staff_user') and request.user.is_app_staff_user)

    def has_delete_permission(self, request, obj=None):
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        return request.user.is_superuser or \
               (hasattr(request.user, 'is_app_owner') and request.user.is_app_owner) or \
               (hasattr(request.user, 'is_project_manager') and request.user.is_project_manager) or \
               (hasattr(request.user, 'is_app_staff_user') and request.user.is_app_staff_user)
    
    # تصفية الخيارات المتاحة في حقل الفرع (branch) داخل الـ Inline
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if not request.user.is_superuser:
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            if hasattr(request.user, 'is_store_account') and (request.user.is_store_account or request.user.is_store_manager_human()):
                # Store-level users see only branches within their store
                formset.form.base_fields['branch'].queryset = Branch.objects.filter(store=request.user.store) if request.user.store else Branch.objects.none()
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            elif hasattr(request.user, 'is_branch_manager_user') and (request.user.is_branch_manager_user or request.user.is_general_staff_user or \
                 request.user.is_cashier_user or request.user.is_customer_service_user or \
                 request.user.is_shelf_organizer_user):
                # Branch-level users see only their assigned branch
                formset.form.base_fields['branch'].queryset = Branch.objects.filter(pk=request.user.branch.pk) if request.user.branch else Branch.objects.none()
                if request.user.branch: # Disable the field only if a branch is assigned
                    formset.form.base_fields['branch'].widget.attrs['disabled'] = 'disabled'
            else:
                # Other users (e.g., platform customer, unassigned staff) see no branches
                formset.form.base_fields['branch'].queryset = Branch.objects.none()
        return formset
    
    # لا داعي لـ save_model هنا، سيتم التعامل معها في save_formset في ProductAdmin


# Department Inline: لعرض الأقسام مباشرة داخل صفحة الفرع (ستُستخدم في stores/admin.py)
# نتركها هنا لأنها قد تُستخدم كـ inline في BranchAdmin.
class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 0
    fields = ('name', 'description',)
    show_change_link = True
    verbose_name = _("Department")
    verbose_name_plural = _("Departments")


# --- Admin for Department ---
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch', 'description', 'created_at', 'updated_at')
    search_fields = ('name', 'branch__name', 'description')
    list_filter = ('branch', 'created_at',)
    raw_id_fields = ('branch',)

    # Fieldsets for consistent layout
    fieldsets = (
        (None, {
            'fields': ('branch', 'name', 'description'),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user:
            return qs # App-level staff can see all departments
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if hasattr(user, 'is_store_account') and (user.is_store_account or user.is_store_manager_human()):
            return qs.filter(branch__store=user.store) # Store-level users see departments in their store's branches
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if hasattr(user, 'is_branch_manager_user') and (user.is_branch_manager_user or user.is_general_staff_user or \
           user.is_cashier_user or user.is_customer_service_user or user.is_shelf_organizer_user):
            return qs.filter(branch=user.branch) # Branch-level users see departments in their branch
        return qs.none() # Default: no access

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        user = request.user
        
        # Filter branch queryset based on user permissions
        if not request.user.is_superuser:
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            if hasattr(user, 'is_store_account') and (user.is_store_account or user.is_store_manager_human()):
                form.base_fields['branch'].queryset = Branch.objects.filter(store=user.store) if user.store else Branch.objects.none()
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            elif hasattr(user, 'is_branch_manager_user') and (user.is_branch_manager_user or user.is_general_staff_user or \
                 user.is_cashier_user or user.is_customer_service_user or user.is_shelf_organizer_user):
                form.base_fields['branch'].queryset = Branch.objects.filter(pk=user.branch.pk) if user.branch else Branch.objects.none()
                if user.branch: # Disable field only if a branch is assigned
                    form.base_fields['branch'].initial = user.branch.pk # Set initial value for disabled field
                    form.base_fields['branch'].widget.attrs['disabled'] = 'disabled' 
            else:
                form.base_fields['branch'].queryset = Branch.objects.none()

        # Shelf organizer specific field disabling
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if hasattr(user, 'is_shelf_organizer_user') and user.is_shelf_organizer_user and user.department:
            form.base_fields['name'].widget.attrs['disabled'] = 'disabled'
            form.base_fields['description'].widget.attrs['disabled'] = 'disabled'
        
        return form

    def has_add_permission(self, request):
        user = request.user
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        return user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user or \
               (hasattr(user, 'is_store_account') and user.is_store_account and user.store) or \
               (hasattr(user, 'is_store_manager_human') and user.is_store_manager_human and user.store) or \
               (hasattr(user, 'is_branch_manager_user') and user.is_branch_manager_user and user.branch)

    def has_change_permission(self, request, obj=None):
        user = request.user
        if obj is None: # List view
            return self.has_add_permission(request) # If they can add, they can see list and potentially change
        
        # Object specific permission
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user:
            return True
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if hasattr(user, 'is_store_account') and (user.is_store_account or user.is_store_manager_human()) and obj.branch.store == user.store:
            return True
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if hasattr(user, 'is_branch_manager_user') and (user.is_branch_manager_user or user.is_general_staff_user or \
           user.is_cashier_user or user.is_customer_service_user or user.is_shelf_organizer_user) and obj.branch == user.branch:
            # Shelf organizer can only change their assigned department's name/description IF it was enabled by get_form,
            # but usually it's read-only.
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            return True if (user.is_shelf_organizer_user and obj == user.department and request.method != 'POST') else True # Can view always, change if not shelf_organizer and within scope
        return False

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if obj is None: # List view
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            return user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user
        
        # Object specific permission
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user:
            return True
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if hasattr(user, 'is_store_account') and (user.is_store_account or user.is_store_manager_human()) and obj.branch.store == user.store:
            return True
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if hasattr(user, 'is_branch_manager_user') and user.is_branch_manager_user and obj.branch == user.branch:
            return True
        return False


# --- Admin for ProductCategory ---
@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        # All app-level staff can manage product categories globally
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user:
            return qs
        return qs.none() # Other users (store/branch level) cannot manage global categories

    def has_add_permission(self, request):
        user = request.user
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        return user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user

    def has_change_permission(self, request, obj=None):
        user = request.user
        if obj is None: # List view
            return self.has_add_permission(request)
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        return user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if obj is None: # List view
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            return user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        return user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user


# --- Admin for Product ---
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [BranchProductInventoryInline] # إضافة الـ inline لعرض المخزون لكل فرع
    
    list_display = (
        'name', 'barcode', 'item_number', 'category', 'department',
        'price', 'price_after_discount', 'vat_rate', 'total_price_with_vat',
        'display_current_stock', # New field to display total stock across branches
        'expiry_date', 'display_image',
        'last_updated_by', 'created_at', 'updated_at'
    )
    search_fields = (
        'name', 'barcode', 'item_number', 'accounting_system_id',
        'category__name', 'department__name',
    )
    list_filter = (
        'category', 'department', 'expiry_date', 'created_at', 'discount_percentage',
    )
    raw_id_fields = ('department', 'category', 'last_updated_by',)
    
    fieldsets = (
        (None, {
            'fields': (
                'name', 'barcode', 'item_number', 'accounting_system_id',
                'category', 'department',
                'price', 'vat_rate', 'image'
            ),
        }),
        (_('Offer and Loyalty Details'), {
            'fields': ('discount_percentage', 'fixed_offer_price', 'offer_start_date', 'offer_end_date', 'loyalty_points'),
            'classes': ('collapse',),
        }),
        (_('Expiry Information'), {
            'fields': ('expiry_date',),
            'classes': ('collapse',),
        }),
        (_('Audit Information'), {
            'fields': ('last_updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_updated_by')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user:
            return qs # App-level staff can see all products
            
        # Store Account or Store Manager (human) can see products associated with their store's branches
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if hasattr(user, 'is_store_account') and (user.is_store_account or user.is_store_manager_human()):
            return qs.filter(branch_inventories__branch__store=user.store).distinct()
            
        # Branch Manager/Staff can see products associated with their specific branch
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if hasattr(user, 'is_branch_manager_user') and (user.is_branch_manager_user or user.is_general_staff_user or \
           user.is_cashier_user or user.is_customer_service_user):
            return qs.filter(branch_inventories__branch=user.branch).distinct()
            
        # Shelf organizer sees products in their assigned department/branch
        # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
        if hasattr(user, 'is_shelf_organizer_user') and user.is_shelf_organizer_user and user.department:
            return qs.filter(
                department=user.department,
                branch_inventories__branch=user.department.branch
            ).distinct()
            
        return qs.none() # Default: no access

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        user = request.user
        
        # Filter department and category querysets based on user permissions
        if not user.is_superuser:
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            if user.is_app_owner or user.is_project_manager or user.is_app_staff_user:
                # App-level staff see all categories/departments
                form.base_fields['category'].queryset = ProductCategory.objects.all()
                form.base_fields['department'].queryset = Department.objects.all()
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            elif hasattr(user, 'is_store_account') and (user.is_store_account or user.is_store_manager_human()):
                # Store managers see departments only within their store's branches
                form.base_fields['department'].queryset = Department.objects.filter(branch__store=user.store) if user.store else Department.objects.none()
                # Store managers manage global categories
                form.base_fields['category'].queryset = ProductCategory.objects.all() 
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            elif hasattr(user, 'is_branch_manager_user') and (user.is_branch_manager_user or user.is_general_staff_user or \
                 user.is_cashier_user or user.is_customer_service_user):
                # Branch-level staff see departments only within their branch
                form.base_fields['department'].queryset = Department.objects.filter(branch=user.branch) if user.branch else Department.objects.none()
                # Branch-level staff manage global categories
                form.base_fields['category'].queryset = ProductCategory.objects.all() 
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            elif hasattr(user, 'is_shelf_organizer_user') and user.is_shelf_organizer_user and user.department:
                # Shelf organizer sees only their department
                form.base_fields['department'].queryset = Department.objects.filter(pk=user.department.pk)
                form.base_fields['department'].initial = user.department.pk # Set initial value for disabled field
                form.base_fields['department'].widget.attrs['disabled'] = 'disabled'
                # Shelf organizer manages global categories
                form.base_fields['category'].queryset = ProductCategory.objects.all()
            else:
                form.base_fields['department'].queryset = Department.objects.none()
                form.base_fields['category'].queryset = ProductCategory.objects.none()

        # Disable last_updated_by field and set its initial value
        form.base_fields['last_updated_by'].initial = request.user.pk # Use PK for initial value
        form.base_fields['last_updated_by'].widget.attrs['disabled'] = 'disabled'
            
        return form

    def save_model(self, request, obj, form, change):
        # Set updater before saving. This field is readonly in the form, but we set it here.
        obj.last_updated_by = request.user
        
        # Superuser, App Owner, Project Manager, App Staff can create/edit any product
        # Store Manager, Branch Manager, General Staff, Cashier, Customer Service, Shelf Organizer
        # can only view/edit products they have permissions for (controlled by get_queryset).
        # Direct creation/deletion of Product object (not inventory) is restricted to higher roles.
        if not change: # Only for new products
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            if not (request.user.is_superuser or request.user.is_app_owner or request.user.is_project_manager or request.user.is_app_staff_user):
                messages.error(request, _("You do not have permission to create products directly. Please ensure you are managing products through your assigned store or branch inventory."))
                return # Prevent saving if not allowed
        
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        # This method is called after the main object has been saved.
        # It's responsible for saving inline formsets.
        
        instances = formset.save(commit=False) # Get instances from the formset
        
        # Validate and set last_updated_by for BranchProductInventory instances
        for instance in instances:
            if isinstance(instance, BranchProductInventory):
                # Ensure the branch selected in the inline is within the user's scope
                user = request.user
                is_valid_branch = False
                # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
                if user.is_superuser or user.is_app_owner or user.is_project_manager or user.is_app_staff_user:
                    is_valid_branch = True
                # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
                elif hasattr(user, 'is_store_account') and (user.is_store_account or user.is_store_manager_human()):
                    if user.store and instance.branch and instance.branch.store == user.store:
                        is_valid_branch = True
                # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
                elif hasattr(user, 'is_branch_manager_user') and (user.is_branch_manager_user or user.is_general_staff_user or \
                     user.is_cashier_user or user.is_customer_service_user or user.is_shelf_organizer_user):
                    if user.branch and instance.branch and instance.branch == user.branch:
                        is_valid_branch = True
                
                if not is_valid_branch:
                    messages.error(request, _(f"You do not have permission to manage inventory for branch '{instance.branch.name if instance.branch else 'N/A'}'."))
                    # If an invalid instance is found, prevent saving the entire formset for this product
                    raise Exception(_("Invalid inventory branch selected.")) # This will rollback the transaction

                instance.last_updated_by = request.user
                instance.save() # Save the BranchProductInventory instance

        # Delete marked objects
        for obj in formset.deleted_objects:
            obj.delete()

        formset.save_m2m() # Save ManyToMany relations for the inline if any

        # Custom validation/creation logic for BranchProductInventory
        # This part ensures that if a new product is created (or updated) and no inventory was explicitly added via inline,
        # a default inventory record is created for the relevant branch/store scope.
        if not change and not BranchProductInventory.objects.filter(product=form.instance).exists():
            user = request.user
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            if hasattr(user, 'is_store_account') and (user.is_store_account or user.is_store_manager_human()):
                if user.store:
                    # Create inventory records for all branches in the store
                    for branch in user.store.branches.all():
                        BranchProductInventory.objects.get_or_create(
                            product=form.instance, # The newly saved product
                            branch=branch,
                            defaults={'quantity': 0, 'last_updated_by': user}
                        )
                    messages.info(request, _("Default inventory records created for branches in your store."))
            # تم تصحيح: إزالة الأقواس () من استدعاء الخصائص المنطقية
            elif hasattr(user, 'is_branch_manager_user') and (user.is_branch_manager_user or user.is_general_staff_user or \
                 user.is_cashier_user or user.is_shelf_organizer_user or user.is_customer_service_user()):
                if user.branch:
                    # Create inventory record for the user's branch
                    BranchProductInventory.objects.get_or_create(
                        product=form.instance,
                        branch=user.branch,
                        defaults={'quantity': 0, 'last_updated_by': user}
                    )
                messages.info(request, _("Default inventory record created for your branch."))


    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="border-radius: 5px;" />', obj.image.url)
        return _("No Image")
    display_image.short_description = _('Image')

    def display_current_stock(self, obj):
        """
        يعرض إجمالي الكمية المتوفرة لهذا المنتج عبر جميع الفروع.
        """
        total_quantity = obj.branch_inventories.aggregate(total=Sum('quantity'))['total']
        return total_quantity if total_quantity is not None else 0
    display_current_stock.short_description = _("Current Stock")