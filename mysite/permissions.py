# C:\Users\DELL\SER SQL MY APP\mysite\permissions.py

from rest_framework import permissions
from django.db.models import Q
# تحديث الاستيراد لاستخدام UserAccount، Role، Customer، Employee
from users.models import UserAccount, Role, Customer, Employee

# استيراد النماذج من أماكنها الصحيحة
from stores.models import Store, Branch
from products.models import Product, Department, ProductCategory, BranchProductInventory, InventoryMovement
from sales.models import Order, OrderItem, TempOrder, TempOrderItem
# CustomerCart, CustomerCartItem, Rating are assumed to be imported from customer app models
# For simplicity, assuming they are available or will be imported from their respective apps.
# If they are in the 'customers' app, you might need:
# from customers.models import CustomerCart, CustomerCartItem, Rating


class CustomPermission(permissions.BasePermission):
    """
    صلاحيات مخصصة للمستخدمين بناءً على نوعهم والدور في المتجر/الفرع.
    تتحكم هذه الفئة في الوصول على مستوى الـ ViewSet (has_permission) وعلى مستوى الكائن (has_object_permission).
    """

    def has_permission(self, request, view):
        user_account = request.user # هذا هو كائن UserAccount

        # 1. المستخدم غير المصادق (AnonymousUser):
        if not user_account.is_authenticated:
            # السماح بقراءة بعض الموارد العامة
            safe_read_basenames = ['product', 'department', 'branch', 'store', 'productcategory']
            if view.basename in safe_read_basenames and request.method in permissions.SAFE_METHODS:
                return True
            return False # رفض الوصول بشكل افتراضي للمستخدمين غير المصادقين لغير القراءة

        # 2. مالك التطبيق / Superuser / مدير المشروع: لديهم صلاحية كاملة على كل شيء
        if user_account.is_superuser or \
           (hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'app_owner') or \
           (hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'project_manager'):
            return True

        # 3. صلاحيات العملاء (platform_customer)
        if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer':
            # العميل يمكنه الوصول إلى ViewSets الخاصة بسلاته وعناصرها وتقييماته وطلباته
            if view.basename in ['customercart', 'customercartitem', 'rating', 'order', 'orderitem', 'customer']:
                return True
            # يمكنه أيضاً عرض المنتجات والأقسام والفئات والمتاجر والفروع (للقراءة فقط)
            if view.basename in ['product', 'department', 'store', 'branch', 'productcategory']:
                return request.method in permissions.SAFE_METHODS
            return False # يمنع العميل من الوصول لأي شيء آخر

        # 4. صلاحيات مدير المتجر (store_manager)
        if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager':
            # يمكنه إدارة المنتجات (بما في ذلك المخزون), الأقسام، الطلبات، العملاء، التقييمات في نطاق متجره
            if view.basename in ['product', 'branchproductinventory', 'department', 'order', 'orderitem', 'temporder', 'temporderitem', 'customercart', 'customercartitem', 'rating', 'customer']:
                return True
            # يمكنه إدارة المستخدمين التابعين لمتجره (موظفون)
            if view.basename == 'useraccount': return True
            # إدارة متجره وفروعه
            if view.basename in ['store', 'branch']: return True
            # فئات المنتجات (للقراءة فقط، الإدارة الشاملة تكون لموظفي التطبيق)
            if view.basename == 'productcategory': return request.method in permissions.SAFE_METHODS
            # صلاحيات التقارير (افتراض وجود ViewSet للتقارير)
            if view.basename == 'report': return True
            # صلاحيات لرفع ملفات المنتجات Excel
            if view.basename == 'productexcelupload': return True # تأكد من basename الصحيح
            return False

        # 5. صلاحيات مدير الفرع (branch_manager)
        if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager':
            # يمكنه إدارة المنتجات (بما في ذلك المخزون), الأقسام، الطلبات، العملاء، التقييمات في نطاق فرعه
            if view.basename in ['product', 'branchproductinventory', 'department', 'order', 'orderitem', 'temporder', 'temporderitem', 'customercart', 'customercartitem', 'rating', 'customer']:
                return True
            # يمكنه إدارة المستخدمين التابعين لفرعه
            if view.basename == 'useraccount': return True
            # إدارة فرعه (للتعديل) ورؤية المتاجر (للقراءة)
            if view.basename == 'branch': return True
            if view.basename == 'store': return request.method in permissions.SAFE_METHODS
            # فئات المنتجات (للقراءة فقط)
            if view.basename == 'productcategory': return request.method in permissions.SAFE_METHODS
            # صلاحيات التقارير
            if view.basename == 'report': return True
            # صلاحيات لرفع ملفات المنتجات Excel
            if view.basename == 'productexcelupload': return True # تأكد من basename الصحيح
            return False

        # 6. صلاحيات موظف الكاشير (cashier)
        if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'cashier':
            # يمكنه إدارة سلات الشراء وعناصرها لإنشاء الطلبات
            if view.basename in ['customercart', 'customercartitem']: return True
            # يمكنه إنشاء وتعديل الطلبات المؤقتة والنهائية وعناصرها
            if view.basename in ['order', 'orderitem', 'temporder', 'temporderitem']: return True
            # يمكنه رؤية المنتجات والأقسام وفئات المنتجات والمخزون في فرعه (للقراءة فقط)
            if view.basename in ['product', 'department', 'productcategory', 'branchproductinventory'] and request.method in permissions.SAFE_METHODS: return True
            # يمكنه رؤية التقييمات
            if view.basename == 'rating' and request.method in permissions.SAFE_METHODS: return True
            # يمكنه رؤية ملفه الشخصي (user)
            if view.basename == 'useraccount': return request.method in permissions.SAFE_METHODS
            # يمكنه رؤية العملاء
            if view.basename == 'customer': return True
            return False
            
        # 7. صلاحيات منظم الرفوف (shelf_organizer)
        if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'shelf_organizer':
            # يمكنه رؤية المنتجات والأقسام وفئات المنتجات في نطاق فرعه
            if view.basename in ['product', 'department', 'productcategory'] and request.method in permissions.SAFE_METHODS: return True
            # يمكنه تعديل مخزون المنتجات في فرعه (BranchProductInventory)
            if view.basename == 'branchproductinventory': return True
            # يمكنه رؤية ملفه الشخصي (user)
            if view.basename == 'useraccount': return request.method in permissions.SAFE_METHODS
            return False

        # 8. صلاحيات موظف خدمة العملاء (customer_service)
        if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'customer_service':
            # يمكنه رؤية المنتجات، الأقسام، فئات المنتجات، المتاجر، الفروع
            if view.basename in ['product', 'department', 'productcategory', 'store', 'branch'] and request.method in permissions.SAFE_METHODS: return True
            # يمكنه رؤية سلات الشراء وعناصرها، الطلبات وعناصرها، والتقييمات
            if view.basename in ['customercart', 'customercartitem', 'order', 'orderitem', 'rating'] and request.method in permissions.SAFE_METHODS: return True
            # يمكنه رؤية المستخدمين (لغرض الدعم)
            if view.basename == 'useraccount': return request.method in permissions.SAFE_METHODS
            # يمكنه رؤية العملاء
            if view.basename == 'customer': return True
            return False

        # 9. صلاحيات موظف عام (general_staff)
        if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'general_staff':
            # يمكنه رؤية كل شيء في فرعه (ما عدا المستخدمين الحساسين)
            if view.basename in ['product', 'branchproductinventory', 'department', 'productcategory', 'customercart', 'customercartitem', 'order', 'orderitem', 'temporder', 'temporderitem', 'rating', 'customer'] : return True
            # يمكنه رؤية المستخدمين التابعين لفرعه
            if view.basename == 'useraccount': return True
            # يمكنه رؤية فرعه و متجره
            if view.basename in ['branch', 'store'] and request.method in permissions.SAFE_METHODS : return True
            return False

        # 10. صلاحيات فريق عمل التطبيق (app_staff)
        if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'app_staff':
            # يمكنهم إدارة المستخدمين على مستوى التطبيق (ولكن ليس مالكي التطبيق أو المشرفين)
            if view.basename == 'useraccount': return True
            # يمكنهم رؤية المتاجر والفروع والتقارير العامة
            if view.basename in ['store', 'branch', 'report']: return True
            # يمكنهم الوصول إلى سجلات المزامنة (integrations) وإدارة فئات المنتجات والأقسام والمنتجات
            if view.basename in ['accountingsystemconfig', 'productsynclog', 'saleinvoicesynclog', 'productcategory', 'department', 'product', 'branchproductinventory']: return True
            return False

        # الافتراضي: رفض الوصول لأي ViewSet لم يتم تحديده صراحةً
        return False

    def has_object_permission(self, request, view, obj):
        user_account = request.user # هذا هو كائن UserAccount

        # 1. مالك التطبيق / Superuser / مدير المشروع: لديهم صلاحية كاملة على أي كائن
        if user_account.is_superuser or \
           (hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'app_owner') or \
           (hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'project_manager'):
            return True

        # 2. الأذونات على الكائنات بناءً على نوع الكائن ودور المستخدم
        
        # صلاحيات المستخدمين (UserAccount)
        if isinstance(obj, UserAccount):
            # المستخدم يرى حسابه الخاص
            if obj == user_account:
                return True
            
            # مدراء المتجر يرى المستخدمين في متجره (مدراء الفروع، الموظفين العامين)
            if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and \
               hasattr(user_account, 'store') and user_account.store: # Store manager has direct 'store' field on UserAccount
                if hasattr(obj, 'employee_profile') and obj.employee_profile and obj.employee_profile.store == user_account.store:
                    return True
            
            # مدير الفرع يرى المستخدمين في فرعه (الموظفين العامين)
            if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and \
               hasattr(user_account, 'branch') and user_account.branch: # Branch manager has direct 'branch' field on UserAccount
                if hasattr(obj, 'employee_profile') and obj.employee_profile and obj.employee_profile.branch == user_account.branch:
                    return True
            
            # فريق عمل التطبيق يرى جميع المستخدمين (للقراءة فقط، والتعديل إذا كان لديه صلاحية عامة على ViewSet)
            if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'app_staff':
                return True # App staff can view all users, and their write access is determined by has_permission (which allows True for 'useraccount' basename)
            
            # صلاحيات التعديل (PUT, PATCH)
            if request.method in ['PUT', 'PATCH']:
                # مدير المتجر يمكنه تعديل موظفيه ضمن متجره (وليس مالكي المتاجر الآخرين، مدراء المتاجر، مدراء المشاريع، فريق عمل التطبيق)
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and \
                   hasattr(user_account, 'store') and user_account.store:
                    if hasattr(obj, 'employee_profile') and obj.employee_profile and obj.employee_profile.store == user_account.store:
                        # لا يمكنه تعديل الأدوار العليا
                        if obj.role and obj.role.role_name not in ['app_owner', 'store_account', 'project_manager', 'app_staff', 'store_manager', 'superuser']:
                            return True
                
                # مدير الفرع يمكنه تعديل موظفيه ضمن فرعه (فقط الموظفين العامين والكاشير ومنظم الرفوف وموظفي خدمة العملاء)
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and \
                   hasattr(user_account, 'branch') and user_account.branch:
                    if hasattr(obj, 'employee_profile') and obj.employee_profile and obj.employee_profile.branch == user_account.branch:
                        if obj.role and obj.role.role_name in ['general_staff', 'cashier', 'shelf_organizer', 'customer_service']:
                            return True
                
                # فريق عمل التطبيق يمكنه تعديل المستخدمين (وليس مالكي التطبيق أو المشرفين)
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'app_staff':
                    if obj.role and obj.role.role_name not in ['app_owner', 'superuser', 'project_manager']:
                        return True
                return False

            # صلاحيات الحذف (DELETE) (أكثر تقييدًا)
            if request.method == 'DELETE':
                # فريق عمل التطبيق يمكنه حذف المستخدمين (وليس مالكي التطبيق أو المشرفين)
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'app_staff':
                    if obj.role and obj.role.role_name not in ['app_owner', 'superuser', 'project_manager']:
                        return True
                return False
            return False # افتراضيًا، لا أحد آخر يمكنه التعديل/الحذف

        # صلاحيات العملاء (Customer) - ملف التعريف
        if isinstance(obj, Customer):
            if request.method in permissions.SAFE_METHODS: # Read
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer' and obj.user_account == user_account:
                    return True # Customer can view own profile
                # Staff can view customers within their scope (handled by ViewSet queryset, but also here for obj-level)
                if hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and hasattr(user_account, 'employee_profile') and user_account.employee_profile:
                    if user_account.role.role_name == 'store_manager' and user_account.employee_profile.store and \
                       obj.customer_orders.filter(branch__store=user_account.employee_profile.store).exists(): # Assuming Customer has customer_orders relation
                        return True
                    if user_account.role.role_name in ['branch_manager', 'general_staff', 'cashier', 'customer_service', 'shelf_organizer'] and \
                       user_account.employee_profile.branch and obj.customer_orders.filter(branch=user_account.employee_profile.branch).exists():
                        return True
                return False
            if request.method in ['PUT', 'PATCH']: # Update
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer' and obj.user_account == user_account:
                    return True # Customer can update own profile (e.g., phone number)
                return False # No other direct update by staff (managed via UserAccount admin or specific views)
            if request.method == 'DELETE':
                # Only app_owner/superuser/project_manager can delete customer profiles
                return False # Deletion should be highly restricted
            return False

        # صلاحيات المتاجر (Store)
        if isinstance(obj, Store):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and \
                   hasattr(user_account, 'store') and user_account.store == obj:
                    return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'app_staff': return True # فريق عمل التطبيق يمكنه رؤية جميع المتاجر
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and \
                   hasattr(user_account, 'branch') and user_account.branch and user_account.branch.store == obj:
                    return True # مدير الفرع يمكنه رؤية متجره
                # Other staff roles can see their store if they have a branch
                if hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and \
                   user_account.role.role_name not in ['store_manager', 'branch_manager'] and \
                   hasattr(user_account, 'branch') and user_account.branch and user_account.branch.store == obj:
                    return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer': return True # Platform customer can see all stores
                return False
            if request.method in ['PUT', 'PATCH']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and \
                   hasattr(user_account, 'store') and user_account.store == obj:
                    return True # مدير المتجر يمكنه تعديل متجره الخاص
                return False
            # لا أحد آخر يمكنه إنشاء/حذف المتاجر عبر API ViewSet (يتم ذلك عبر تسجيل مالك المتجر أو لوحة الإدارة)
            return False

        # صلاحيات الفروع (Branch)
        if isinstance(obj, Branch):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and \
                   hasattr(user_account, 'store') and user_account.store == obj.store:
                    return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and \
                   hasattr(user_account, 'branch') and user_account.branch == obj:
                    return True
                # Other staff roles can see their branch
                if hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and \
                   user_account.role.role_name not in ['store_manager', 'branch_manager'] and \
                   hasattr(user_account, 'branch') and user_account.branch == obj:
                    return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'app_staff': return True # فريق عمل التطبيق يمكنه رؤية جميع الفروع
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer': return True # Platform customer can see all branches
                return False
            if request.method in ['PUT', 'PATCH']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and \
                   hasattr(user_account, 'store') and user_account.store == obj.store:
                    return True # مدير المتجر يمكنه تعديل فروع متجره
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and \
                   hasattr(user_account, 'branch') and user_account.branch == obj:
                    return True # مدير الفرع يمكنه تعديل فرعه
                return False
            # لا أحد آخر يمكنه إنشاء/حذف الفروع عبر API ViewSet
            return False

        # صلاحيات الأقسام (Department)
        if isinstance(obj, Department):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and obj.branch and \
                   hasattr(user_account, 'store') and user_account.store == obj.branch.store:
                    return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and obj.branch and \
                   hasattr(user_account, 'branch') and user_account.branch == obj.branch:
                    return True
                # Other staff roles in the same branch
                if hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and \
                   user_account.role.role_name not in ['store_manager', 'branch_manager'] and obj.branch and \
                   hasattr(user_account, 'branch') and user_account.branch == obj.branch:
                    return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'shelf_organizer' and hasattr(user_account, 'employee_profile') and user_account.employee_profile and user_account.employee_profile.department == obj:
                    return True # منظم الرفوف يرى قسمه فقط
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'customer_service': return True # Customer service can see all departments
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer': return True # العملاء يمكنهم رؤية جميع الأقسام
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']: # Creation, Update, Delete
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and obj.branch and \
                   hasattr(user_account, 'store') and user_account.store == obj.branch.store:
                    return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and obj.branch and \
                   hasattr(user_account, 'branch') and user_account.branch == obj.branch:
                    return True
                # منظم الرفوف يمكنه تعديل قسمه فقط في حالة وجود إذن محدد لذلك في الـ ViewSet
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'shelf_organizer' and hasattr(user_account, 'employee_profile') and user_account.employee_profile and obj == user_account.employee_profile.department:
                    return request.method in ['PUT', 'PATCH'] # Assuming they can only update their own department
                return False

        # صلاحيات المنتجات (Product)
        if isinstance(obj, Product):
            # صلاحيات القراءة:
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and \
                   hasattr(user_account, 'store') and user_account.store and \
                   obj.branch_inventories.filter(branch__store=user_account.store).exists(): return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and \
                   hasattr(user_account, 'branch') and user_account.branch and \
                   obj.branch_inventories.filter(branch=user_account.branch).exists(): return True
                # Other staff roles in the same branch
                if hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and \
                   user_account.role.role_name not in ['store_manager', 'branch_manager'] and \
                   hasattr(user_account, 'branch') and user_account.branch and \
                   obj.branch_inventories.filter(branch=user_account.branch).exists():
                    return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'shelf_organizer' and \
                   hasattr(user_account, 'employee_profile') and user_account.employee_profile and user_account.employee_profile.department and \
                   obj.department == user_account.employee_profile.department and obj.branch_inventories.filter(branch=user_account.employee_profile.department.branch).exists(): return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'customer_service': return True # Customer service can see all products
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer': return True # العملاء يمكنهم رؤية جميع المنتجات
                return False
            # صلاحيات التعديل/الحذف:
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and \
                   hasattr(user_account, 'store') and user_account.store and \
                   obj.branch_inventories.filter(branch__store=user_account.store).exists(): return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and \
                   hasattr(user_account, 'branch') and user_account.branch and \
                   obj.branch_inventories.filter(branch=user_account.branch).exists(): return True
                # GENERAL_STAFF (and specific sub-roles like Cashier, Shelf Organizer) should manage inventory via BranchProductInventory,
                # not directly modify the Product object, unless it's very specific fields.
                if hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and \
                   user_account.role.role_name not in ['store_manager', 'branch_manager'] and \
                   hasattr(user_account, 'branch') and user_account.branch and \
                   obj.branch_inventories.filter(branch=user_account.branch).exists():
                    return request.method in ['PUT', 'PATCH'] # Allow update, but not create/delete
                return False

        # صلاحيات مخزون المنتج لكل فرع (BranchProductInventory)
        if isinstance(obj, BranchProductInventory):
            # صلاحيات القراءة:
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and obj.branch and \
                   hasattr(user_account, 'store') and user_account.store == obj.branch.store: return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and obj.branch and \
                   hasattr(user_account, 'branch') and user_account.branch == obj.branch: return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and \
                   user_account.role.role_name not in ['store_manager', 'branch_manager'] and obj.branch and \
                   hasattr(user_account, 'branch') and user_account.branch == obj.branch: return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'shelf_organizer' and obj.branch and \
                   hasattr(user_account, 'employee_profile') and user_account.employee_profile and user_account.employee_profile.department and \
                   obj.product.department == user_account.employee_profile.department and obj.branch == user_account.employee_profile.department.branch: return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'customer_service': return True # Customer service can see all inventory records
                return False
            # صلاحيات التعديل/الحذف:
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and obj.branch and \
                   hasattr(user_account, 'store') and user_account.store == obj.branch.store: return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and obj.branch and \
                   hasattr(user_account, 'branch') and user_account.branch == obj.branch: return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and \
                   user_account.role.role_name not in ['store_manager', 'branch_manager'] and obj.branch and \
                   hasattr(user_account, 'branch') and user_account.branch == obj.branch: return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'shelf_organizer' and obj.branch and \
                   hasattr(user_account, 'employee_profile') and user_account.employee_profile and user_account.employee_profile.department and \
                   obj.product.department == user_account.employee_profile.department and obj.branch == user_account.employee_profile.department.branch:
                    return request.method in ['PUT', 'PATCH']
                return False

        # صلاحيات سلة الشراء (CustomerCart)
        if isinstance(obj, CustomerCart):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer' and obj.customer and obj.customer.user_account == user_account: return True
                # Staff access via branch
                if hasattr(obj, 'branch') and obj.branch and hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager', 'customer_service', 'shelf_organizer'] and obj.branch == user_account.branch: return True
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer' and obj.customer and obj.customer.user_account == user_account: return True
                # Staff access via branch
                if hasattr(obj, 'branch') and obj.branch and hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager', 'customer_service', 'shelf_organizer'] and obj.branch == user_account.branch: return True
                return False

        # صلاحيات عناصر سلة الشراء (CustomerCartItem)
        if isinstance(obj, CustomerCartItem):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer' and obj.cart and obj.cart.customer and obj.cart.customer.user_account == user_account: return True
                # Staff access via cart's branch
                if hasattr(obj.cart, 'branch') and obj.cart.branch and hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.cart.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager', 'customer_service', 'shelf_organizer'] and obj.cart.branch == user_account.branch: return True
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer' and obj.cart and obj.cart.customer and obj.cart.customer.user_account == user_account: return True
                # Staff access via cart's branch
                if hasattr(obj.cart, 'branch') and obj.cart.branch and hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.cart.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager', 'customer_service', 'shelf_organizer'] and obj.cart.branch == user_account.branch: return True
                return False
            return False

        # صلاحيات الطلبات (Order)
        if isinstance(obj, Order):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer' and obj.customer and obj.customer.user_account == user_account: return True
                # Staff access via branch
                if hasattr(obj, 'branch') and obj.branch and hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager', 'customer_service', 'shelf_organizer'] and obj.branch == user_account.branch: return True
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                # Orders are typically created by cashiers, or finalized from temp orders.
                # Deletion is highly restricted.
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name in ['cashier', 'general_staff', 'branch_manager', 'store_manager'] and \
                   hasattr(obj, 'branch') and obj.branch and hasattr(user_account, 'branch') and user_account.branch: # Staff making/updating orders for their branch
                    if user_account.role.role_name == 'store_manager' and obj.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager'] and obj.branch == user_account.branch: return True
                return False
            return False

        # صلاحيات عناصر الطلب (OrderItem)
        if isinstance(obj, OrderItem):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer' and obj.order and obj.order.customer and obj.order.customer.user_account == user_account: return True
                # Staff access via order's branch
                if hasattr(obj.order, 'branch') and obj.order.branch and hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.order.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager', 'customer_service', 'shelf_organizer'] and obj.order.branch == user_account.branch: return True
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name in ['cashier', 'general_staff', 'branch_manager', 'store_manager'] and \
                   hasattr(obj.order, 'branch') and obj.order.branch and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.order.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager'] and obj.order.branch == user_account.branch: return True
                return False
            return False

        # صلاحيات الطلبات المؤقتة (TempOrder)
        if isinstance(obj, TempOrder):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer' and obj.customer and obj.customer.user_account == user_account: return True
                # Staff access via branch
                if hasattr(obj, 'branch') and obj.branch and hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager', 'customer_service', 'shelf_organizer'] and obj.branch == user_account.branch: return True
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name in ['cashier', 'general_staff', 'branch_manager', 'store_manager'] and \
                   hasattr(obj, 'branch') and obj.branch and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager'] and obj.branch == user_account.branch: return True
                return False
            return False

        # صلاحيات عناصر الطلب المؤقتة (TempOrderItem)
        if isinstance(obj, TempOrderItem):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'platform_customer' and obj.temp_order and obj.temp_order.customer and obj.temp_order.customer.user_account == user_account: return True
                # Staff access via temp_order's branch
                if hasattr(obj.temp_order, 'branch') and obj.temp_order.branch and hasattr(user_account, 'role') and user_account.role and user_account.role.is_staff_role and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.temp_order.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager', 'customer_service', 'shelf_organizer'] and obj.temp_order.branch == user_account.branch: return True
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name in ['cashier', 'general_staff', 'branch_manager', 'store_manager'] and \
                   hasattr(obj.temp_order, 'branch') and obj.temp_order.branch and hasattr(user_account, 'branch') and user_account.branch:
                    if user_account.role.role_name == 'store_manager' and obj.temp_order.branch.store == user_account.store: return True
                    if user_account.role.role_name in ['general_staff', 'cashier', 'branch_manager'] and obj.temp_order.branch == user_account.branch: return True
                return False
            return False

        # صلاحيات فئات المنتجات (ProductCategory)
        if isinstance(obj, ProductCategory):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name in ['store_manager', 'branch_manager', 'general_staff', 'cashier', 'shelf_organizer', 'customer_service', 'platform_customer', 'app_staff']:
                    return True # All relevant roles can view product categories
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'app_staff':
                    return True # Only app staff can manage product categories
                return False
            return False

        # صلاحيات سجلات حركة المخزون (InventoryMovement)
        if isinstance(obj, InventoryMovement):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'store_manager' and \
                   hasattr(user_account, 'store') and user_account.store and obj.branch and obj.branch.store == user_account.store: return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'branch_manager' and \
                   hasattr(user_account, 'branch') and user_account.branch == obj.branch: return True
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name == 'shelf_organizer' and \
                   hasattr(user_account, 'employee_profile') and user_account.employee_profile and user_account.employee_profile.branch == obj.branch: return True
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                # Inventory movements are usually created by staff (shelf_organizer, general_staff, branch_manager, store_manager)
                # but direct API modification might be restricted to specific views/actions.
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name in ['store_manager', 'branch_manager', 'shelf_organizer', 'general_staff'] and \
                   hasattr(user_account, 'branch') and user_account.branch == obj.branch:
                    return True # Allow staff to create/update movements within their branch
                return False
            return False

        # صلاحيات ملفات تعريف صلاحيات المتجر (StorePermissionProfile)
        if isinstance(obj, StorePermissionProfile):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name in ['app_owner', 'project_manager', 'app_staff']:
                    return True # These roles can view permission profiles
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name in ['app_owner', 'project_manager']:
                    return True # Only app owner/project manager can create/update/delete these
                return False
            return False

        # صلاحيات ملفات تعريف صلاحيات الفرع (BranchPermissionProfile)
        if isinstance(obj, BranchPermissionProfile):
            if request.method in permissions.SAFE_METHODS:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name in ['app_owner', 'project_manager', 'app_staff', 'store_manager']:
                    return True # These roles can view permission profiles
                return False
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                if hasattr(user_account, 'role') and user_account.role and user_account.role.role_name in ['app_owner', 'project_manager', 'store_manager']:
                    return True # Only app owner/project manager/store manager can create/update/delete these
                return False
            return False


        return False # رفض الوصول لأي كائن لم يتم تحديده صراحةً