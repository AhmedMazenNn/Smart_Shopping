# integrations/urls.py

from django.urls import path
from . import views

app_name = 'integrations' # اسم التطبيق (مهم لعمل reverse lookup)

urlpatterns = [
    # مسار إرسال الفاتورة إلى نظام المحاسبة
    # ملاحظة: <int:order_id> هنا يطابق ما هو متوقع في send_sale_invoice_to_accounting في views.py
    # تم تغيير sale_id إلى order_id ليتوافق مع نماذجك
    path('<int:order_id>/send_invoice/', views.send_sale_invoice_to_accounting, name='send_invoice'),

    # يمكنك إضافة مسارات أخرى هنا إذا أردت استدعاء مهام أخرى من views
    # مثال:
    # path('products/sync_from_accounting/', views.sync_products_from_accounting, name='sync_products'),
]