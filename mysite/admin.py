# C:\Users\DELL\SER SQL MY APP\mysite\admin.py

from django.contrib import admin
from django.db.models import Sum
from products.models import Store, Branch # استيراد النماذج التي نحتاجها لحساب الإحصائيات

# >>>>>> هذا هو السطر الجديد الذي يحل مشكلة RecursionError <<<<<<
# نحفظ مرجعًا للدالة الأصلية لـ admin.site.index قبل أن نقوم بتغييرها.
_original_admin_site_index = admin.site.index

# دالة لتخصيص الصفحة الرئيسية لـ Django Admin
def mysite_admin_site_index(request, extra_context=None):
    if extra_context is None:
        extra_context = {}

    # حساب إجمالي العمليات السنوية لجميع المتاجر
    # يجمع حقل 'total_yearly_operations' من كل كائن Store
    total_ops_across_all_stores = Store.objects.aggregate(total=Sum('total_yearly_operations'))['total'] or 0
    extra_context['total_ops_across_all_stores'] = total_ops_across_all_stores

    # حساب إجمالي العمليات اليومية لجميع الفروع
    # يجمع حقل 'daily_operations' من كل كائن Branch
    total_daily_ops_across_all_branches = Branch.objects.aggregate(total=Sum('daily_operations'))['total'] or 0
    extra_context['total_daily_ops_across_all_branches'] = total_daily_ops_across_all_branches

    # يمكنك إضافة المزيد من الإحصائيات هنا حسب الحاجة
    # مثال: إجمالي عدد المنتجات
    # total_products = Product.objects.count()
    # extra_context['total_products'] = total_products

    # استدعاء الدالة الأصلية للصفحة الرئيسية لـ Admin
    # >>>>>> استخدمنا المرجع الذي حفظناه: _original_admin_site_index بدلاً من admin.site.index <<<<<<
    return _original_admin_site_index(request, extra_context=extra_context)

# استبدال الدالة الافتراضية للصفحة الرئيسية لـ Admin بالدالة المخصصة
admin.site.index = mysite_admin_site_index

# ملاحظة: لا تحتاج إلى تسجيل النماذج هنا (Store, Branch, Product)
# لأنها مسجلة بالفعل في products/admin.py