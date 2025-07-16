# C:\Users\DELL\SER SQL MY APP\sales\views.py

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import action
from rest_framework import serializers
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
from decimal import Decimal
from django.utils.translation import gettext_lazy as _

# استيراد النماذج من sales
from .models import Order, OrderItem, TempOrder, TempOrderItem, Payment, Return, ReturnItem # تم تحديث الاستيرادات
# استيراد Serializers من sales
from .serializers import ( # تم استيراد Serializers مباشرة
    TempOrderSerializer,
    TempOrderItemSerializer,
    OrderSerializer,
    OrderItemSerializer,
    PaymentSerializer,
    ReturnSerializer,
    ReturnItemSerializer,
    QRCodeScanSerializer # لوحدة مسح الباركود
)

# استيراد النماذج الأخرى
from products.models import Product, BranchProductInventory, InventoryMovement # تم تحديث الاستيرادات للمخزون
from stores.models import Branch
from users.models import UserAccount, Role
from mysite.permissions import CustomPermission


# --- API ViewSets for Temporary Orders (TempOrder) ---
class TempOrderViewSet(viewsets.ModelViewSet):
    queryset = TempOrder.objects.all()
    serializer_class = TempOrderSerializer # استخدام Serializer المستورد
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager():
            return TempOrder.objects.all()
        
        if user.is_store_manager_user() and user.store:
            return TempOrder.objects.filter(branch__store=user.store)
        
        if (user.is_branch_manager_user() or user.is_general_staff_user() or user.is_cashier_user()) and user.branch:
            if user.is_branch_manager_user():
                return TempOrder.objects.filter(branch=user.branch)
            elif user.is_general_staff_user() or user.is_cashier_user(): # الموظف العام/الكاشير يرى طلباته المؤقتة
                return TempOrder.objects.filter(branch=user.branch, cashier=user)

        return TempOrder.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        branch = serializer.validated_data.get('branch')

        if not (user.is_general_staff_user() or user.is_cashier_user()):
            raise serializers.ValidationError({'detail': _('Only General Staff or Cashiers can create temporary orders.')})
        
        if not branch:
            raise serializers.ValidationError({'branch': _('Branch must be specified for a temporary order.')})
        
        if branch != user.branch:
            raise serializers.ValidationError({'branch': _('You can only create temporary orders for your assigned branch.')})

        serializer.save(cashier=user, branch=user.branch)

    def perform_update(self, serializer):
        # CustomPermission handles object-level permission checks
        serializer.save()

    def perform_destroy(self, instance):
        # CustomPermission handles object-level permission checks
        instance.delete()


# --- API ViewSets for Temporary Order Items (TempOrderItem) ---
class TempOrderItemViewSet(viewsets.ModelViewSet):
    queryset = TempOrderItem.objects.all()
    serializer_class = TempOrderItemSerializer # استخدام Serializer المستورد
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager():
            return TempOrderItem.objects.all()
        
        if user.is_store_manager_user() and user.store:
            return TempOrderItem.objects.filter(temp_order__branch__store=user.store)
        
        if (user.is_branch_manager_user() or user.is_general_staff_user() or user.is_cashier_user()) and user.branch:
            if user.is_branch_manager_user():
                return TempOrderItem.objects.filter(temp_order__branch=user.branch)
            elif user.is_general_staff_user() or user.is_cashier_user():
                return TempOrderItem.objects.filter(temp_order__branch=user.branch, temp_order__cashier=user)

        return TempOrderItem.objects.none()


    def perform_create(self, serializer):
        user = self.request.user
        temp_order = serializer.validated_data.get('temp_order')
        product = serializer.validated_data.get('product')
        quantity = serializer.validated_data.get('quantity')

        if not temp_order or not product or quantity is None:
            raise serializers.ValidationError({'detail': _('Temporary order, product, and quantity are required.')})

        if not (user.is_general_staff_user() or user.is_cashier_user()):
            raise serializers.ValidationError({'detail': _('You do not have permission to add items to this temporary order.')})
            
        if user.branch != temp_order.branch:
             raise serializers.ValidationError({'temp_order': _('Temporary order must be in your assigned branch.')})

        # التأكد من أن المنتج له مخزون في الفرع الخاص بالطلب المؤقت
        product_inventory = BranchProductInventory.objects.filter(product=product, branch=temp_order.branch).first()
        if not product_inventory:
            raise serializers.ValidationError({'product': _('Product is not available in the temporary order\'s branch.')})

        if product_inventory.quantity < quantity:
            raise serializers.ValidationError({'quantity': _(f'Not enough stock available for product {product.name} in branch {temp_order.branch.name}. Available: {product_inventory.quantity}')})

        with transaction.atomic():
            existing_item = TempOrderItem.objects.filter(temp_order=temp_order, product=product).first()
            if existing_item:
                old_item_quantity = existing_item.quantity
                existing_item.quantity = F('quantity') + quantity
                existing_item.scanned_quantity = F('scanned_quantity') + quantity # زيادة الكمية الممسوحة أيضاً
                existing_item.save(update_fields=['quantity', 'scanned_quantity'])
                existing_item.refresh_from_db()
                serializer.instance = existing_item 
            else:
                serializer.save() # price_at_scan will be set by TempOrderItem's save method
            
            # إنقاص كمية المنتج من المخزون في BranchProductInventory
            # لا نحتاج لإنشاء InventoryMovement هنا، سيتم التعامل معها عند تحويل TempOrder إلى Order
            product_inventory.quantity = F('quantity') - quantity
            product_inventory.save(update_fields=['quantity'])


    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object() 
        product = instance.product
        old_quantity = instance.quantity
        new_quantity = serializer.validated_data.get('quantity', old_quantity)

        if not (user.is_general_staff_user() or user.is_cashier_user()):
            raise serializers.ValidationError({'detail': _('You do not have permission to modify this temporary order item.')})
            
        if user.branch != instance.temp_order.branch:
             raise serializers.ValidationError({'temp_order': _('Temporary order must be in your assigned branch.')})

        if new_quantity < 0:
            raise serializers.ValidationError({'quantity': _('Quantity cannot be negative.')})

        product_inventory = BranchProductInventory.objects.filter(product=product, branch=instance.temp_order.branch).first()
        if not product_inventory:
            raise serializers.ValidationError({'product': _('Product inventory not found for this branch.')})

        with transaction.atomic():
            diff_quantity = new_quantity - old_quantity
            if diff_quantity > 0:
                if product_inventory.quantity < diff_quantity:
                    raise serializers.ValidationError({'quantity': _(f'Requested quantity ({new_quantity}) is not available. Available: {product_inventory.quantity + old_quantity}')})
            
            product_inventory.quantity = F('quantity') - diff_quantity
            product_inventory.save(update_fields=['quantity'])
            
            serializer.save()


    def perform_destroy(self, instance):
        user = self.request.user

        if not (user.is_general_staff_user() or user.is_cashier_user()):
            raise serializers.ValidationError({'detail': _('You do not have permission to delete this temporary order item.')})

        if user.branch != instance.temp_order.branch:
             raise serializers.ValidationError({'temp_order': _('Temporary order must be in your assigned branch.')})

        with transaction.atomic():
            product_inventory = BranchProductInventory.objects.filter(product=instance.product, branch=instance.temp_order.branch).first()
            if product_inventory:
                product_inventory.quantity = F('quantity') + instance.quantity
                product_inventory.save(update_fields=['quantity'])
            else:
                print(f"Warning: Inventory record for product {instance.product.name} in branch {instance.temp_order.branch.name} not found during TempOrderItem deletion. Stock was not returned.")
                # أو يمكن رفع خطأ: raise serializers.ValidationError(_("Could not find inventory to return stock."))
            
            instance.delete()


# --- API ViewSets for Orders ---
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer # استخدام Serializer المستورد
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager() or user.is_app_staff_user():
            return Order.objects.all()
        
        if user.is_platform_customer():
            return Order.objects.filter(customer=user)
        
        if user.is_store_manager_user() and user.store:
            return Order.objects.filter(branch__store=user.store)
        
        if (user.is_branch_manager_user() or user.is_general_staff_user() or user.is_cashier_user()) and user.branch:
            return Order.objects.filter(branch=user.branch)
            
        return Order.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        branch = serializer.validated_data.get('branch')
        customer = serializer.validated_data.get('customer')

        if not (user.is_superuser or user.is_app_owner() or user.is_project_manager() or user.is_general_staff_user() or user.is_cashier_user() or user.is_platform_customer()):
            raise serializers.ValidationError({'detail': _('You do not have permission to create an order.')})

        if user.is_general_staff_user() or user.is_cashier_user():
            if not branch or branch != user.branch:
                raise serializers.ValidationError({'branch': _('General Staff/Cashier must create orders for their assigned branch.')})
            serializer.validated_data['performed_by'] = user
        elif user.is_platform_customer():
            if customer and customer != user:
                raise serializers.ValidationError({'customer': _('Customers can only create orders for themselves.')})
            serializer.validated_data['customer'] = user
        elif user.is_store_manager_user() or user.is_branch_manager_user(): # يمكنهم إنشاء طلبات ولكن لا نحدد performed_by هنا
            pass
        
        order = serializer.save()

        # إذا تم إنشاء طلب بواسطة كاشير/موظف عام، قد يحتاج إلى نقل العناصر من TempOrder
        # هذه الخطوة تعتمد على workflow الخاص بك، هل يتم التحويل يدوياً أم آلياً
        # إذا كنت تخطط لتحويل TempOrder إلى Order، فهذا سيكون جزءًا من view منفصل.
        # حاليا، هذا الـ perform_create يتعامل مع إنشاء Order جديد فارغ أو مع بيانات أولية.

    def perform_update(self, serializer):
        instance = self.get_object()
        old_status = instance.status
        new_status = serializer.validated_data.get('status', old_status)

        # التحديثات التلقائية لـ paid_at و completed_at تتم في دالة save بالنموذج
        
        serializer.save()

        # منطق استعادة المخزون أو خصمه عند تغيير حالة الطلب
        # هذا يتم معالجته الآن بواسطة Signals في `sales.models.py`
        # تحديداً، post_save على Order (لخصم المخزون عند COMPLETED)
        # و post_save/post_delete على ReturnItem (لإعادة/خصم المخزون عند الإرجاع)
        # لذلك، يمكن إزالة المنطق اليدوي لاستعادة المخزون هنا لتجنب التكرار.

    def perform_destroy(self, instance):
        # عند حذف الطلب، يتم التعامل مع استعادة المخزون بواسطة Signal
        # في `sales.models.py` (post_delete على OrderItem)
        # لذلك، يمكن إزالة المنطق اليدوي لاستعادة المخزون هنا لتجنب التكرار.
        instance.delete()


# --- API ViewSets for Order Items ---
class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer # استخدام Serializer المستورد
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager():
            return OrderItem.objects.all()
        
        if user.is_platform_customer():
            return OrderItem.objects.filter(order__customer=user)
        
        if user.is_store_manager_user() and user.store:
            return OrderItem.objects.filter(order__branch__store=user.store)
        
        if (user.is_branch_manager_user() or user.is_general_staff_user() or user.is_cashier_user()) and user.branch:
            return OrderItem.objects.filter(order__branch=user.branch)
            
        return OrderItem.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        order = serializer.validated_data.get('order')
        product = serializer.validated_data.get('product')
        quantity = serializer.validated_data.get('quantity')

        if not order or not product or quantity is None:
            raise serializers.ValidationError({'detail': _('Order, product, and quantity are required.')})

        # تحقق من صلاحية المستخدم على الطلب والمنتج
        if not (user.is_superuser or user.is_app_owner() or user.is_project_manager()):
            if user.is_platform_customer() and order.customer != user:
                raise serializers.ValidationError({'order': _('You can only add items to your own orders.')})
            elif (user.is_branch_manager_user() or user.is_general_staff_user() or user.is_cashier_user()) and order.branch != user.branch:
                raise serializers.ValidationError({'order': _('You can only add items to orders in your branch.')})
            elif user.is_store_manager_user() and order.branch.store != user.store:
                raise serializers.ValidationError({'order': _('You can only add items to orders in your store.')})
            else:
                raise serializers.ValidationError({'detail': _('You do not have permission to add items to this order.')})

        # التأكد من أن حالة الطلب تسمح بالإضافة (مثلاً: pending_payment)
        if order.status not in [Order.OrderStatus.PENDING_PAYMENT, Order.OrderStatus.PAID]:
            raise serializers.ValidationError({'order': _('Cannot add items to an order with status: ') + order.get_status_display()})

        # التحقق من المخزون
        product_inventory = BranchProductInventory.objects.filter(product=product, branch=order.branch).first()
        if not product_inventory:
            raise serializers.ValidationError({'product': _('Product is not available in the order\'s branch.')})

        if product_inventory.quantity < quantity:
            raise serializers.ValidationError({'quantity': _(f'Not enough stock available for product {product.name} in branch {order.branch.name}. Available: {product_inventory.quantity}')})

        with transaction.atomic():
            # إذا كان العنصر موجوداً بالفعل، قم بتحديث الكمية
            existing_item = OrderItem.objects.filter(order=order, product=product).first()
            if existing_item:
                old_item_quantity = existing_item.quantity
                existing_item.quantity = F('quantity') + quantity
                existing_item.save(update_fields=['quantity'])
                existing_item.refresh_from_db()
                serializer.instance = existing_item
            else:
                serializer.save() # price_at_purchase and vat_rate will be set by OrderItem's save method

            # خصم الكمية من المخزون
            # InventoryMovement يتم تسجيلها عن طريق Signal بعد اكتمال الطلب، وليس هنا.
            product_inventory.quantity = F('quantity') - quantity
            product_inventory.save(update_fields=['quantity'])


    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object() 
        order = instance.order
        product = instance.product
        old_quantity = instance.quantity
        new_quantity = serializer.validated_data.get('quantity', old_quantity)

        # صلاحية التعديل
        if not (user.is_superuser or user.is_app_owner() or user.is_project_manager()):
            if (user.is_branch_manager_user() or user.is_general_staff_user() or user.is_cashier_user()) and order.branch != user.branch:
                raise serializers.ValidationError({'order': _('You can only modify items in orders in your branch.')})
            elif user.is_store_manager_user() and order.branch.store != user.store:
                raise serializers.ValidationError({'order': _('You can only modify items in orders in your store.')})
            else:
                raise serializers.ValidationError({'detail': _('You do not have permission to modify this order item.')})

        # التأكد من أن حالة الطلب تسمح بالتعديل
        if order.status not in [Order.OrderStatus.PENDING_PAYMENT, Order.OrderStatus.PAID]:
            raise serializers.ValidationError({'order': _('Cannot modify items in an order with status: ') + order.get_status_display()})
            
        if new_quantity < 0:
            raise serializers.ValidationError({'quantity': _('Quantity cannot be negative.')})

        product_inventory = BranchProductInventory.objects.filter(product=product, branch=order.branch).first()
        if not product_inventory:
            raise serializers.ValidationError({'product': _('Product inventory not found for this branch.')})

        with transaction.atomic():
            diff_quantity = new_quantity - old_quantity
            if diff_quantity > 0:
                if product_inventory.quantity < diff_quantity:
                    raise serializers.ValidationError({'quantity': _(f'Requested quantity ({new_quantity}) is not available. Available: {product_inventory.quantity + old_quantity}')})
            
            product_inventory.quantity = F('quantity') - diff_quantity
            product_inventory.save(update_fields=['quantity'])
            
            serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        order = instance.order

        # صلاحية الحذف
        if not (user.is_superuser or user.is_app_owner() or user.is_project_manager()):
            if (user.is_branch_manager_user() or user.is_general_staff_user() or user.is_cashier_user()) and order.branch != user.branch:
                raise serializers.ValidationError({'order': _('You can only delete items from orders in your branch.')})
            elif user.is_store_manager_user() and order.branch.store != user.store:
                raise serializers.ValidationError({'order': _('You can only delete items from orders in your store.')})
            else:
                raise serializers.ValidationError({'detail': _('You do not have permission to delete this order item.')})
        
        # التأكد من أن حالة الطلب تسمح بالحذف
        if order.status not in [Order.OrderStatus.PENDING_PAYMENT, Order.OrderStatus.PAID]:
            raise serializers.ValidationError({'order': _('Cannot delete items from an order with status: ') + order.get_status_display()})

        with transaction.atomic():
            # استعادة الكمية للمخزون
            # InventoryMovement يتم تسجيلها عن طريق Signal بعد حذف OrderItem
            product_inventory = BranchProductInventory.objects.filter(product=instance.product, branch=order.branch).first()
            if product_inventory:
                product_inventory.quantity = F('quantity') + instance.quantity
                product_inventory.save(update_fields=['quantity'])
            else:
                print(f"Warning: Inventory record for product {instance.product.name} in branch {order.branch.name} not found during OrderItem deletion. Stock was not returned.")
            
            instance.delete()


# --- API ViewSets for Payments ---
class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager() or user.is_app_staff_user():
            return Payment.objects.all()
        
        if user.is_store_manager_user() and user.store:
            return Payment.objects.filter(order__branch__store=user.store)
        
        if (user.is_branch_manager_user() or user.is_general_staff_user() or user.is_cashier_user()) and user.branch:
            return Payment.objects.filter(order__branch=user.branch)
            
        return Payment.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        order = serializer.validated_data.get('order')

        # يجب أن يكون لدى المستخدم صلاحية إنشاء دفعة لهذا الطلب
        if not (user.is_superuser or user.is_app_owner() or user.is_project_manager()):
            if not (user.is_store_manager_user() and order.branch.store == user.store) and \
               not ((user.is_branch_manager_user() or user.is_cashier_user()) and order.branch == user.branch):
                raise serializers.ValidationError({'detail': _('You do not have permission to add payments to this order.')})

        # تعيين مستلم الدفعة
        if not serializer.validated_data.get('received_by') and user.is_authenticated:
            serializer.validated_data['received_by'] = user

        serializer.save()

    def perform_update(self, serializer):
        # CustomPermission handles object-level permission checks
        serializer.save()

    def perform_destroy(self, instance):
        # CustomPermission handles object-level permission checks
        instance.delete()


# --- API ViewSets for Returns ---
class ReturnViewSet(viewsets.ModelViewSet):
    queryset = Return.objects.all()
    serializer_class = ReturnSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager() or user.is_app_staff_user():
            return Return.objects.all()
        
        if user.is_platform_customer():
            return Return.objects.filter(order__customer=user) # العملاء يرون إرجاعات طلباتهم
        
        if user.is_store_manager_user() and user.store:
            return Return.objects.filter(order__branch__store=user.store)
        
        if (user.is_branch_manager_user() or user.is_general_staff_user() or user.is_cashier_user()) and user.branch:
            return Return.objects.filter(order__branch=user.branch)
            
        return Return.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        order = serializer.validated_data.get('order')

        # يجب أن يكون لدى المستخدم صلاحية إنشاء إرجاع لهذا الطلب
        if not (user.is_superuser or user.is_app_owner() or user.is_project_manager()):
            if not (user.is_store_manager_user() and order.branch.store == user.store) and \
               not ((user.is_branch_manager_user() or user.is_cashier_user()) and order.branch == user.branch):
                raise serializers.ValidationError({'detail': _('You do not have permission to create returns for this order.')})

        # تعيين معالج الإرجاع
        if not serializer.validated_data.get('processed_by') and user.is_authenticated:
            serializer.validated_data['processed_by'] = user

        serializer.save()

    def perform_update(self, serializer):
        # CustomPermission handles object-level permission checks
        serializer.save()

    def perform_destroy(self, instance):
        # CustomPermission handles object-level permission checks
        instance.delete()


# --- API ViewSets for Return Items ---
class ReturnItemViewSet(viewsets.ModelViewSet):
    queryset = ReturnItem.objects.all()
    serializer_class = ReturnItemSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_app_owner() or user.is_project_manager() or user.is_app_staff_user():
            return ReturnItem.objects.all()
        
        if user.is_platform_customer():
            return ReturnItem.objects.filter(return_obj__order__customer=user)
        
        if user.is_store_manager_user() and user.store:
            return ReturnItem.objects.filter(return_obj__order__branch__store=user.store)
        
        if (user.is_branch_manager_user() or user.is_general_staff_user() or user.is_cashier_user()) and user.branch:
            return ReturnItem.objects.filter(return_obj__order__branch=user.branch)
            
        return ReturnItem.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        return_obj = serializer.validated_data.get('return_obj')
        product = serializer.validated_data.get('product')
        quantity_returned = serializer.validated_data.get('quantity_returned')

        if not return_obj or not product or quantity_returned is None:
            raise serializers.ValidationError({'detail': _('Return object, product, and quantity are required.')})

        # تحقق من صلاحية المستخدم على عملية الإرجاع والمنتج
        if not (user.is_superuser or user.is_app_owner() or user.is_project_manager()):
            if not (user.is_store_manager_user() and return_obj.order.branch.store == user.store) and \
               not ((user.is_branch_manager_user() or user.is_cashier_user()) and return_obj.order.branch == user.branch):
                raise serializers.ValidationError({'detail': _('You do not have permission to add return items to this return record.')})
        
        # التأكد من أن المنتج الذي يتم إرجاعه كان جزءاً من الطلب الأصلي
        if not OrderItem.objects.filter(order=return_obj.order, product=product).exists():
            raise serializers.ValidationError({'product': _('Product was not part of the original order.')})

        serializer.save() # المخزون سيتم تعديله عبر Signal في sales.models.py

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object() 
        return_obj = instance.return_obj

        # صلاحية التعديل
        if not (user.is_superuser or user.is_app_owner() or user.is_project_manager()):
            if not (user.is_store_manager_user() and return_obj.order.branch.store == user.store) and \
               not ((user.is_branch_manager_user() or user.is_cashier_user()) and return_obj.order.branch == user.branch):
                raise serializers.ValidationError({'detail': _('You do not have permission to modify this return item.')})

        serializer.save() # المخزون سيتم تعديله عبر Signal في sales.models.py

    def perform_destroy(self, instance):
        user = self.request.user
        return_obj = instance.return_obj

        # صلاحية الحذف
        if not (user.is_superuser or user.is_app_owner() or user.is_project_manager()):
            if not (user.is_store_manager_user() and return_obj.order.branch.store == user.store) and \
               not ((user.is_branch_manager_user() or user.is_cashier_user()) and return_obj.order.branch == user.branch):
                raise serializers.ValidationError({'detail': _('You do not have permission to delete this return item.')})
        
        instance.delete() # المخزون سيتم تعديله عبر Signal في sales.models.py


# --- API for converting TempOrder to Order ---
class ConvertTempOrderToOrderAPIView(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    @action(detail=False, methods=['post'], url_path='convert')
    def convert(self, request):
        user = request.user
        temp_order_id = request.data.get('temp_order_id')
        customer_id = request.data.get('customer_id') # اختياري: لربط الطلب بعميل مسجل
        non_app_customer_name = request.data.get('non_app_customer_name', None) # اختياري: لعميل غير مسجل
        non_app_customer_phone = request.data.get('non_app_customer_phone', None) # اختياري: لعميل غير مسجل
        payment_method = request.data.get('payment_method') # CASH, ELECTRONIC, CREDIT_BALANCE
        transaction_id = request.data.get('transaction_id', None) # مطلوب للدفع الإلكتروني

        if not temp_order_id:
            return Response({'detail': _('Temporary order ID is required.')}, status=status.HTTP_400_BAD_REQUEST)
        if not payment_method:
            return Response({'detail': _('Payment method is required.')}, status=status.HTTP_400_BAD_REQUEST)
        if payment_method == Order.PaymentMethod.ELECTRONIC and not transaction_id:
            return Response({'detail': _('Transaction ID is required for electronic payment.')}, status=status.HTTP_400_BAD_REQUEST)

        try:
            temp_order = get_object_or_404(TempOrder, id=temp_order_id)

            # التحقق من صلاحية المستخدم
            if not (user.is_superuser or user.is_app_owner() or user.is_project_manager()):
                if not ((user.is_general_staff_user() or user.is_cashier_user()) and temp_order.cashier == user and temp_order.branch == user.branch):
                    return Response({'detail': _('You do not have permission to convert this temporary order.')}, status=status.HTTP_403_FORBIDDEN)

            if not temp_order.items.exists():
                return Response({'detail': _('Temporary order has no items to convert.'), 'total_amount': temp_order.total_amount}, status=status.HTTP_400_BAD_REQUEST)

            customer_obj = None
            if customer_id:
                try:
                    customer_obj = User.objects.get(id=customer_id)
                    if not customer_obj.is_platform_customer():
                        return Response({'detail': _('Provided customer ID does not belong to a platform customer.')}, status=status.HTTP_400_BAD_REQUEST)
                except User.DoesNotExist:
                    return Response({'detail': _('Customer not found.')}, status=status.HTTP_404_NOT_FOUND)
            
            # البدء في المعاملة الذرية لتحويل الطلب المؤقت إلى طلب نهائي ودفع
            with transaction.atomic():
                # 1. إنشاء الطلب النهائي (Order)
                order_data = {
                    'branch': temp_order.branch,
                    'total_amount': temp_order.total_amount,
                    'vat_amount': temp_order.vat_amount,
                    'total_with_vat': temp_order.total_with_vat,
                    'discount_amount': temp_order.discount_amount,
                    'performed_by': user, # من قام بإنشاء الطلب النهائي (الكاشير/الموظف العام)
                    'status': Order.OrderStatus.PENDING_PAYMENT, # الحالة الأولية قبل الدفع
                }
                if customer_obj:
                    order_data['customer'] = customer_obj
                if non_app_customer_name:
                    order_data['non_app_customer_name'] = non_app_customer_name
                if non_app_customer_phone:
                    order_data['non_app_customer_phone'] = non_app_customer_phone
                
                order = Order.objects.create(**order_data)

                # 2. نقل عناصر الطلب المؤقت إلى عناصر الطلب النهائي
                for temp_item in temp_order.items.all():
                    # تأكد من أن المخزون تم خصمه بالفعل عند إنشاء TempOrderItem.
                    # هنا ننشئ OrderItem فقط.
                    OrderItem.objects.create(
                        order=order,
                        product=temp_item.product,
                        quantity=temp_item.quantity,
                        price_at_purchase=temp_item.price_at_scan,
                        vat_rate_at_purchase=temp_item.vat_rate_at_scan,
                    )
                    # حذف العنصر المؤقت بعد نقله بنجاح
                    temp_item.delete()

                # 3. إنشاء الدفعة
                payment_data = {
                    'order': order,
                    'amount': order.total_with_vat, # المبلغ المدفوع هو إجمالي الطلب
                    'method': payment_method,
                    'received_by': user,
                }
                if transaction_id:
                    payment_data['transaction_id'] = transaction_id

                payment = Payment.objects.create(**payment_data)

                # 4. تحديث حالة الطلب إلى PAID بعد الدفع
                # ملاحظة: دالة save في نموذج Order ستتولى تعيين paid_at
                order.status = Order.OrderStatus.PAID
                order.save()

                # 5. حذف الطلب المؤقت بعد تحويله بنجاح
                temp_order.delete()

            # إعادة استجابة بالطلب الجديد
            order_serializer = OrderSerializer(order)
            return Response(order_serializer.data, status=status.HTTP_201_CREATED)

        except TempOrder.DoesNotExist:
            return Response({'detail': _('Temporary order not found.')}, status=status.HTTP_404_NOT_FOUND)
        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # يجب أن تكون المعاملات الذرية قد ألغت أي تغييرات في حالة حدوث خطأ
            return Response({'detail': _(f'An unexpected error occurred: {str(e)}')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# --- API for QR Code Scanning ---
class QRCodeScanView(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, CustomPermission]

    @action(detail=False, methods=['post'], url_path='scan')
    def scan_qr_code(self, request):
        serializer = QRCodeScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        qr_code_data = serializer.validated_data['qr_code_data']
        temp_order_id = serializer.validated_data.get('temp_order_id')
        user = request.user

        if not (user.is_general_staff_user() or user.is_cashier_user()):
            return Response({'detail': _('Only General Staff or Cashiers can scan QR codes for temporary orders.')}, status=status.HTTP_403_FORBIDDEN)
        
        if not user.branch:
            return Response({'detail': _('User must be assigned to a branch to scan QR codes.')}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(qr_code=qr_code_data)
        except Product.DoesNotExist:
            return Response({'detail': _('Product with this QR code not found.')}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            temp_order = None
            if temp_order_id:
                try:
                    temp_order = TempOrder.objects.get(id=temp_order_id, cashier=user, branch=user.branch)
                except TempOrder.DoesNotExist:
                    return Response({'detail': _('Temporary order not found or you do not have access to it.')}, status=status.HTTP_404_NOT_FOUND)
            else:
                # إذا لم يتم توفير temp_order_id، أنشئ طلبًا مؤقتًا جديدًا
                temp_order = TempOrder.objects.create(cashier=user, branch=user.branch)
            
            # تحقق من المخزون
            product_inventory = BranchProductInventory.objects.filter(product=product, branch=temp_order.branch).first()
            if not product_inventory or product_inventory.quantity < 1: # التحقق من توفر 1 قطعة على الأقل
                return Response({'detail': _(f'Not enough stock available for product {product.name} in branch {temp_order.branch.name}. Available: {product_inventory.quantity if product_inventory else 0}')}, status=status.HTTP_400_BAD_REQUEST)

            # إضافة أو تحديث TempOrderItem
            temp_order_item, created = TempOrderItem.objects.get_or_create(
                temp_order=temp_order,
                product=product,
                defaults={
                    'quantity': 1,
                    'scanned_quantity': 1,
                    'price_at_scan': product.current_price,
                    'vat_rate_at_scan': product.vat_rate,
                }
            )
            if not created:
                temp_order_item.quantity = F('quantity') + 1
                temp_order_item.scanned_quantity = F('scanned_quantity') + 1
                temp_order_item.save(update_fields=['quantity', 'scanned_quantity'])
                temp_order_item.refresh_from_db() # لتحديث الكائن بالقيم الجديدة

            # إنقاص المخزون
            product_inventory.quantity = F('quantity') - 1
            product_inventory.save(update_fields=['quantity'])

            # إعادة بيانات الطلب المؤقت وعناصره
            temp_order_serializer = TempOrderSerializer(temp_order)
            return Response(temp_order_serializer.data, status=status.HTTP_200_OK)

