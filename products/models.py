# C:\Users\DELL\SER SQL MY APP\products\models.py

from django.db import models
from django.conf import settings
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.db.models import Q # لاستخدام UniqueConstraint مع الشروط المعقدة
from django.utils import timezone # لاستخدام الوقت والتاريخ في حسابات العروض

# استيراد نموذج Branch من تطبيق stores
# تأكد من أن مسار الاستيراد هذا صحيح بناءً على هيكلة مشروعك
from stores.models import Branch


# === نموذج القسم (Department Model) ===
# يمثل قسماً معيناً داخل فرع متجر (مثلاً: قسم الألبان، قسم الخضروات).
class Department(models.Model):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE, # إذا حذف الفرع، تحذف جميع الأقسام التابعة له
        related_name='departments',
        verbose_name=_("Branch")
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("Department Name")
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description")
    )
    created_at = models.DateTimeField(
        auto_now_add=True, # يتم تعيينه تلقائياً عند إنشاء الكائن
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True, # يتم تحديثه تلقائياً في كل مرة يتم فيها حفظ الكائن
        verbose_name=_("Last Updated At")
    )

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")
        # لضمان عدم تكرار اسم القسم ضمن نفس الفرع (مثال: لا يمكن أن يكون هناك "ألبان" مرتين في نفس الفرع)
        unique_together = ('branch', 'name')

    def __str__(self):
        # تمثيل نصي للقسم يعرض اسمه واسم الفرع التابع له
        return f"{self.name} - {self.branch.name}"


# === نموذج فئة المنتج (ProductCategory Model) ===
# يمثل فئة عامة للمنتجات (مثال: ألبان، خضروات، إلكترونيات).
# يمكن ربط المنتجات بها لتصنيفها.
class ProductCategory(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True, # يجب أن يكون اسم الفئة فريداً
        verbose_name=_("Category Name")
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Last Updated At")
    )

    class Meta:
        verbose_name = _("Product Category")
        verbose_name_plural = _("Product Categories")

    def __str__(self):
        return self.name


# === نموذج المنتج (Product Model) ===
# يمثل منتجاً معيناً متاحاً في فرع محدد، ويمكن أن ينتمي إلى قسم.
class Product(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name=_("Department")
    )
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name=_("Category")
    )

    barcode = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_("Barcode")
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_("Product Name")
    )
    item_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_("Item Number")
    )

    accounting_system_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_("Accounting System ID")
    )
    
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_("Base Price")
    )

    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name=_("Discount Percentage (%)")
    )
    fixed_offer_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_("Fixed Offer Price (if applicable)")
    )
    
    expiry_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Expiry Date")
    )
    
    offer_start_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Offer Start Date")
    )
    offer_end_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Offer End Date")
    )
    
    loyalty_points = models.IntegerField(
        default=0,
        verbose_name=_("Loyalty Points")
    )
    
    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.1500'),
        validators=[MinValueValidator(Decimal('0.0000')), MaxValueValidator(Decimal('1.0000'))],
        verbose_name=_("VAT Rate (as decimal)")
    )

    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_products',
        verbose_name=_("Last Updated By")
    )
    image = models.ImageField(
        upload_to='product_images/',
        null=True,
        blank=True,
        verbose_name=_("Product Image")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Last Updated At")
    )

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        constraints = [
            models.UniqueConstraint(
                fields=['barcode'],
                name='unique_barcode_global',
                condition=Q(barcode__isnull=False) & ~Q(barcode=''),
                violation_error_message=_("This barcode already exists for another product.")
            ),
            models.UniqueConstraint(
                fields=['item_number'],
                name='unique_item_number_global',
                condition=Q(item_number__isnull=False) & ~Q(item_number=''),
                violation_error_message=_("This item number already exists for another product.")
            ),
            models.UniqueConstraint(
                fields=['accounting_system_id'],
                name='unique_accounting_id_global',
                condition=Q(accounting_system_id__isnull=False) & ~Q(accounting_system_id=''),
                violation_error_message=_("This accounting system ID already exists for another product.")
            )
        ]

    def __str__(self):
        identifier = self.barcode if self.barcode else self.item_number or _('No ID')
        return f"{self.name} ({identifier})"

    def price_after_discount(self):
        current_date = timezone.localdate()
        is_offer_active = (self.offer_start_date and self.offer_end_date and
                           self.offer_start_date <= current_date <= self.offer_end_date)

        if is_offer_active and self.fixed_offer_price is not None:
            return self.fixed_offer_price
            
        if self.discount_percentage is not None and self.discount_percentage > Decimal('0.00'):
            return self.price * (1 - self.discount_percentage / 100)
            
        return self.price

    def discounted_amount(self):
        return self.price - self.price_after_discount()
        
    def vat_amount(self):
        return self.price_after_discount() * self.vat_rate

    def total_price_with_vat(self):
        return self.price_after_discount() + self.vat_amount()


# === نموذج مخزون المنتج لكل فرع (BranchProductInventory Model) ===
# يربط منتجاً بفرع معين ويحدد الكمية المتاحة لهذا المنتج في ذلك الفرع.
class BranchProductInventory(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='branch_inventories',
        verbose_name=_("Product")
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='product_inventories',
        verbose_name=_("Branch")
    )
    quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)], # الكمية لا يمكن أن تكون سالبة
        verbose_name=_("Quantity in Stock")
    )
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_branch_inventories',
        verbose_name=_("Last Updated By")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Last Updated At")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )

    class Meta:
        verbose_name = _("Branch Product Inventory")
        verbose_name_plural = _("Branch Product Inventories")
        # ضمان أن يكون هناك سجل مخزون واحد فقط لكل منتج في كل فرع
        unique_together = ('product', 'branch')

    def __str__(self):
        return f"{self.product.name} @ {self.branch.name}: {self.quantity}"

# === نموذج سجل حركة المخزون (InventoryMovement Model) ===
# يتتبع كل حركة (إضافة، خصم، نقل) تحدث للمخزون في BranchProductInventory.
class InventoryMovement(models.Model):
    # أنواع حركة المخزون
    MOVEMENT_TYPES = (
        ('IN', _('In (Addition)')),
        ('OUT', _('Out (Deduction)')),
        ('TRANSFER_IN', _('Transfer In')),
        ('TRANSFER_OUT', _('Transfer Out')),
        ('ADJUSTMENT', _('Adjustment')),
    )

    inventory = models.ForeignKey(
        BranchProductInventory,
        on_delete=models.CASCADE, # إذا حذف سجل المخزون، تحذف سجلات حركته
        related_name='movements',
        verbose_name=_("Inventory Record")
    )
    product = models.ForeignKey( # إضافة المنتج مباشرة لتسهيل الاستعلام
        Product,
        on_delete=models.CASCADE,
        related_name='inventory_movements_by_product',
        verbose_name=_("Product")
    )
    branch = models.ForeignKey( # إضافة الفرع مباشرة لتسهيل الاستعلام
        Branch,
        on_delete=models.CASCADE,
        related_name='inventory_movements_by_branch',
        verbose_name=_("Branch")
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_TYPES,
        verbose_name=_("Movement Type")
    )
    quantity_change = models.IntegerField(
        verbose_name=_("Quantity Change (e.g., +5 or -3)")
    )
    old_quantity = models.IntegerField(
        verbose_name=_("Old Quantity")
    )
    new_quantity = models.IntegerField(
        verbose_name=_("New Quantity")
    )
    reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Reason/Notes")
    )
    moved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_movements',
        verbose_name=_("Moved By")
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Timestamp")
    )

    class Meta:
        verbose_name = _("Inventory Movement")
        verbose_name_plural = _("Inventory Movements")
        ordering = ['-timestamp'] # ترتيب الحركات من الأحدث إلى الأقدم

    def __str__(self):
        return f"{self.movement_type} {self.quantity_change} of {self.product.name} in {self.branch.name} by {self.moved_by.username if self.moved_by else 'N/A'}"
