# C:\Users\DELL\SER SQL MY APP\stores\serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model

# استيراد النماذج من تطبيق stores
from .models import Store, Branch, StorePermissionProfile, BranchPermissionProfile # تم إضافة نماذج الصلاحيات

User = get_user_model()

# --- Serializer for StorePermissionProfile ---
class StorePermissionProfileSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = StorePermissionProfile
        fields = [
            'id', 'name', 'description', 'can_manage_products', 'can_manage_branches',
            'can_manage_staff_accounts', 'can_view_reports', 'can_manage_discounts_offers',
            'created_at', 'updated_at', 'created_by', 'created_by_username'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by_username']
        extra_kwargs = {
            'created_by': {'write_only': True, 'required': False, 'allow_null': True}
        }


# --- Serializer for BranchPermissionProfile ---
class BranchPermissionProfileSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = BranchPermissionProfile
        fields = [
            'id', 'name', 'description', 'can_manage_branch_profile', 'can_manage_local_staff',
            'can_manage_local_products', 'can_manage_local_offers', 'can_view_local_reports',
            'can_review_ratings', 'can_manage_cart', 'can_apply_discounts',
            'can_finalize_invoice', 'can_assist_customer_rating', 'can_create_promotions',
            'can_track_offer_performance', 'can_manage_daily_statuses', 'can_set_display_priority',
            'created_at', 'updated_at', 'created_by', 'created_by_username'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by_username']
        extra_kwargs = {
            'created_by': {'write_only': True, 'required': False, 'allow_null': True}
        }


# --- Serializer for Branch ---
class BranchSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True) # يمكن أن يكون user null
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    
    # Nested serializer لعرض تفاصيل ملف الصلاحيات (للقراءة)
    permission_profile_details = BranchPermissionProfileSerializer(source='permission_profile', read_only=True, allow_null=True)
    # PrimaryKeyRelatedField للكتابة (تمرير ID لملف الصلاحيات)
    permission_profile = serializers.PrimaryKeyRelatedField(
        queryset=BranchPermissionProfile.objects.all(),
        required=False,
        allow_null=True,
        write_only=True # هذا الحقل يستخدم فقط للكتابة
    )

    class Meta:
        model = Branch
        fields = [
            'id', 'name', 'address', 'phone_number', 'email', 'store', 'store_name',
            'user', 'user_username', 'branch_id_number', 'branch_tax_id', 'accounting_ref_id', # تم إضافة حقول جديدة
            'fee_percentage', 'daily_operations', 'monthly_operations', 'total_yearly_operations',
            'latitude', 'longitude', # تم إضافة حقول الموقع
            'permission_profile', 'permission_profile_details', # حقول الصلاحيات
            'created_at', 'updated_at', 'created_by', 'created_by_username'
        ]
        read_only_fields = [
            'branch_id_number', 'user', 'user_username', 'daily_operations', 'monthly_operations',
            'total_yearly_operations', 'created_at', 'updated_at', 'created_by_username',
            'permission_profile_details', # لأنه nested read_only
        ]
        extra_kwargs = {
            'store': {'write_only': True, 'required': True}, # يجب تحديد المتجر عند إنشاء فرع
            'user': {'write_only': True, 'required': False, 'allow_null': True}, # المدير يتم إنشاؤه تلقائياً أو ربطه
            'created_by': {'write_only': True, 'required': False, 'allow_null': True},
            'latitude': {'required': False, 'allow_null': True},
            'longitude': {'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        # للتأكد من أن حقل 'store' قد تم توفيره عند الإنشاء
        if self.instance is None and not attrs.get('store'):
            raise serializers.ValidationError({"store": _("Store field is required when creating a new branch.")})
        return attrs


# --- Serializer for Store ---
class StoreSerializer(serializers.ModelSerializer):
    # Nested serializer لعرض تفاصيل الفروع المرتبطة (للقراءة فقط)
    branches = BranchSerializer(many=True, read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True) # يمكن أن يكون user null
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    # Nested serializer لعرض تفاصيل ملف الصلاحيات (للقراءة)
    permission_profile_details = StorePermissionProfileSerializer(source='permission_profile', read_only=True, allow_null=True)
    # PrimaryKeyRelatedField للكتابة (تمرير ID لملف الصلاحيات)
    permission_profile = serializers.PrimaryKeyRelatedField(
        queryset=StorePermissionProfile.objects.all(),
        required=False,
        allow_null=True,
        write_only=True # هذا الحقل يستخدم فقط للكتابة
    )

    class Meta:
        model = Store
        fields = [
            'id', 'name', 'address', 'phone_number', 'email', 'tax_id', 'accounting_ref_id', # تم إضافة حقول جديدة
            'login_email', # حقل جديد
            'user', 'user_username', 'branches',
            'total_yearly_operations', 'last_yearly_update', # تم إضافة last_yearly_update
            'permission_profile', 'permission_profile_details', # حقول الصلاحيات
            'created_at', 'updated_at', 'created_by', 'created_by_username'
        ]
        read_only_fields = [
            'user', 'user_username', 'branches', 'total_yearly_operations',
            'last_yearly_update', 'created_at', 'updated_at', 'created_by_username',
            'permission_profile_details', # لأنه nested read_only
        ]
        extra_kwargs = {
            'login_email': {'required': False}, # login_email قد يكون مطلوبًا عند الإنشاء وليس دائماً
            'user': {'write_only': True, 'required': False, 'allow_null': True}, # المدير يتم إنشاؤه تلقائياً أو ربطه
            'created_by': {'write_only': True, 'required': False, 'allow_null': True}
        }
    
    def validate_name(self, value):
        # التحقق من فرادة الاسم عند الإنشاء أو التعديل
        if self.instance: # Update scenario
            if Store.objects.filter(name=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError(_("A store with this name already exists."))
        else: # Create scenario
            if Store.objects.filter(name=value).exists():
                raise serializers.ValidationError(_("A store with this name already exists."))
        return value

    def validate_login_email(self, value):
        # التحقق من فرادة login_email عند الإنشاء أو التعديل
        if self.instance: # Update scenario
            if Store.objects.filter(login_email=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError(_("A store with this login email already exists."))
            # إذا كان المستخدم يحاول تغيير login_email لمتجر موجود، وتسبب ذلك في تعارض مع مستخدم آخر
            if User.objects.filter(email=value).exclude(id=self.instance.user.id if self.instance.user else None).exists():
                 raise serializers.ValidationError(_("A user account with this email already exists."))
        else: # Create scenario
            if Store.objects.filter(login_email=value).exists():
                raise serializers.ValidationError(_("A store with this login email already exists."))
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError(_("A user account with this email already exists."))
        return value
