# C:\Users\DELL\SER SQL MY APP\mysite\urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from django.contrib.auth import views as auth_views

# Import custom admin sites (تأكد من وجود هذا الملف)
from .custom_admin_site import app_owner_admin_site, store_manager_panel

# Import ViewSets for the integrations app (تأكد من وجود هذه الـ ViewSets والتطبيق)
from integrations.views import AccountingSystemConfigViewSet, ProductSyncLogViewSet, SaleInvoiceSyncLogViewSet

# Import ViewSets for the customers app (تأكد من وجود هذه الـ ViewSets والتطبيق)
# تم إضافة CustomerViewSet هنا للاستيراد
from customers.views import CustomerViewSet, CustomerCartViewSet, CustomerCartItemViewSet, RatingViewSet

# Import ViewSets for the sales app (تأكد من وجود هذه الـ ViewSets والتطبيق)
from sales.views import OrderViewSet, OrderItemViewSet, TempOrderViewSet, TempOrderItemViewSet

# تم نقل health_check و user_info إلى تطبيق 'api' الجديد، لذا لا حاجة لاستيرادهما هنا بعد الآن.
# from .views import health_check, user_info


# --- Set up a main router for all ViewSets that use ModelViewSet ---
router = DefaultRouter()

# Register ViewSets for the integrations app
router.register(r'integrations/config', AccountingSystemConfigViewSet, basename='accountingsystemconfig')
router.register(r'integrations/product-sync-logs', ProductSyncLogViewSet, basename='productsynclog')
router.register(r'integrations/sale-invoice-sync-logs', SaleInvoiceSyncLogViewSet, basename='saleinvoicesynclog')

# Register ViewSets for the customers app
# تم إضافة CustomerViewSet هنا
router.register(r'customers', CustomerViewSet, basename='customer') # تسجيل CustomerViewSet
router.register(r'carts', CustomerCartViewSet, basename='customercart')
router.register(r'cart-items', CustomerCartItemViewSet, basename='customercartitem')
router.register(r'ratings', RatingViewSet, basename='rating')

# Register ViewSets for the sales app
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='orderitem')
router.register(r'temp-orders', TempOrderViewSet, basename='temporder')
router.register(r'temp-order-items', TempOrderItemViewSet, basename='temporderitem')


urlpatterns = [
    # Default Django admin panel
    path('admin/', admin.site.urls),
    
    # New custom admin panels
    path('app-owner-admin/', app_owner_admin_site.urls),
    path('store-manager-panel/', store_manager_panel.urls),

    # API paths for authentication (Firebase)
    path('api/auth/', include('authentication.urls')), 

    # Include all paths created by the main router (for non-products)
    path('api/', include(router.urls)),

    # --- Include paths for the stores app modularly ---
    path('api/stores/', include('stores.urls')),

    # --- Include paths for the products app modularly ---
    path('api/products/', include('products.urls')),

    # تضمين مسارات تطبيق 'api' الجديد الذي يحتوي الآن على health-check, user-info, و protected-data
    path('api/', include('api.urls')), # <--- هذا السطر الجديد يضمن تضمين مسارات api/views.py

    # URL paths for password reset
    path('password_reset/',
          auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'),
          name='password_reset'),
    path('password_reset/done/',
          auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
          name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
          auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
          name='password_reset_confirm'),
    path('reset/done/',
          auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
          name='password_reset_complete'),
]

# For serving static files and media files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
