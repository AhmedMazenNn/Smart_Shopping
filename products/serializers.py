# C:\Users\DELL\SER SQL MY APP\products\serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Sum

# استيراد النماذج الصحيحة لتطبيق products
from .models import Product, Department, ProductCategory, BranchProductInventory
# لا نحتاج لاستيراد Branch هنا مباشرة، لأننا سنتعامل معها عبر ProductInventory

User = get_user_model() # إذا كنت تستخدم User في سيرياليزرات المنتجات أو الأقسام

# --- Serializer for ProductCategory ---
class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

# --- Serializer for Department ---
class DepartmentSerializer(serializers.ModelSerializer):
    # branch_name لم يعد مطلوباً هنا إذا لم تكن بحاجته مباشرة في تمثيل القسم
    # ولكن إذا أردت تضمين اسم الفرع، يجب أن يكون الفرع نفسه متاحاً
    # للحفاظ على التوافق مع الكود القديم:
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'branch', 'branch_name', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'branch_name']
        extra_kwargs = {
            'branch': {'write_only': True} # عادةً لا تريد أن يقوم العميل الأمامي بتمرير كائن الفرع بالكامل
        }

# --- Serializer for BranchProductInventory ---
class BranchProductInventorySerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    # يمكن إضافة المزيد من تفاصيل الفرع إذا لزم الأمر، مثل Store Name
    store_name = serializers.CharField(source='branch.store.name', read_only=True)

    class Meta:
        model = BranchProductInventory
        fields = ['id', 'branch', 'branch_name', 'store_name', 'quantity', 'last_updated_by', 'updated_at', 'created_at']
        read_only_fields = ['last_updated_by', 'updated_at', 'created_at', 'branch_name', 'store_name']
        extra_kwargs = {
            'branch': {'write_only': True} # الفرع يجب أن يكون موجوداً عند الإنشاء/التعديل
        }


# --- Serializer for Product ---
class ProductSerializer(serializers.ModelSerializer):
    # إزالة branch_name و store_name لأن Product لم يعد مرتبطاً مباشرة بـ Branch

    department_name = serializers.CharField(source='department.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True) # حقل جديد لاسم الفئة
    last_updated_by_username = serializers.CharField(source='last_updated_by.username', read_only=True)

    image = serializers.ImageField(required=False, allow_null=True)

    # حقول للقراءة فقط تعتمد على الدوال المحسوبة في نموذج Product
    price_after_discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discounted_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    vat_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_price_with_vat = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    # Nested serializer لعرض تفاصيل المخزون لكل فرع
    # read_only=True يعني أنك لن تستخدمه لإنشاء/تعديل BranchProductInventory من خلال ProductSerializer
    # بل فقط لعرض البيانات. لإنشاء/تعديل المخزون، استخدم BranchProductInventorySerializer مباشرة.
    branch_inventories = BranchProductInventorySerializer(many=True, read_only=True)

    # حقل محسوب يعرض إجمالي الكمية في المخزون عبر جميع الفروع
    total_quantity_in_all_branches = serializers.SerializerMethodField()


    class Meta:
        model = Product
        fields = [
            'id', 
            'category', 'category_name', # حقول الفئة الجديدة
            'department', 'department_name',
            'barcode', 'name', 'item_number', 'accounting_system_id', # تم إضافة accounting_system_id
            'price', 'vat_rate', # تم إضافة vat_rate
            
            # حقول العروض الجديدة
            'discount_percentage', 'fixed_offer_price',
            'offer_start_date', 'offer_end_date',
            
            'expiry_date', 'loyalty_points',
            
            # حقول المخزون (الآن من branch_inventories)
            'branch_inventories', # Nested serializer للمخزون لكل فرع
            'total_quantity_in_all_branches', # حقل محسوب لإجمالي الكمية

            'image',
            'last_updated_by', 'last_updated_by_username',
            'created_at', 'updated_at',
            
            # حقول محسوبة للقراءة فقط
            'price_after_discount', 'discounted_amount', 'vat_amount', 'total_price_with_vat',
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'department_name', 'category_name', 'last_updated_by_username',
            'price_after_discount', 'discounted_amount', 'vat_amount', 'total_price_with_vat',
            'branch_inventories', # بما أنه nested read_only
            'total_quantity_in_all_branches',
        ]
        extra_kwargs = {
            'department': {'write_only': True, 'required': False, 'allow_null': True},
            'category': {'write_only': True, 'required': False, 'allow_null': True}, # category يمكن أن تكون write_only
            'last_updated_by': {'write_only': True, 'required': False, 'allow_null': True}
        }
        # تم إزالة depth = 1

    def get_total_quantity_in_all_branches(self, obj):
        """
        يحسب إجمالي الكمية المتوفرة لهذا المنتج عبر جميع الفروع من سجلات المخزون.
        """
        # استخدام .aggregate() للحصول على مجموع الكميات من جميع BranchProductInventory المرتبطة بالمنتج
        total_quantity = obj.branch_inventories.aggregate(total=Sum('quantity'))['total']
        return total_quantity if total_quantity is not None else 0

    def create(self, validated_data):
        # DRF لا يتعامل مع Inlines تلقائياً عند الإنشاء/التعديل بشكل مباشر عبر Serializer الرئيسي
        # لذلك يجب التأكد من حفظ last_updated_by هنا
        if not validated_data.get('last_updated_by') and 'request' in self.context and self.context['request'].user.is_authenticated:
            validated_data['last_updated_by'] = self.context['request'].user
        
        # إذا كان هناك بيانات for BranchProductInventory في payload (وهو غير متوقع مع read_only=True)
        # يجب معالجتها بشكل منفصل أو منعها
        # For this setup, BranchProductInventory records will be managed through their own API endpoint
        # or via Django Admin inline.

        product = Product.objects.create(**validated_data)
        return product

    def update(self, instance, validated_data):
        if not validated_data.get('last_updated_by') and 'request' in self.context and self.context['request'].user.is_authenticated:
            validated_data['last_updated_by'] = self.context['request'].user
        
        # تأكد أنك لا تحاول حفظ حقول read_only (مثل branch_inventories)
        # DRF سيتجاهل الحقول read_only تلقائياً عند التحديث، لكن من الجيد التأكد
        
        return super().update(instance, validated_data)

