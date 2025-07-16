from rest_framework import serializers
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.db.models import F # For using F() expressions
import secrets # For generating session keys if needed
from django.utils import timezone # For timezone.now()

# Import models from the customers app
from .models import Customer, CustomerCart, CustomerCartItem, Rating

# Import models from other apps
from products.models import Product, BranchProductInventory
# التأكد من استيراد Order (كان Invoice)
from sales.models import Order
# تحديث الاستيراد لاستخدام UserAccount والوصول إلى Role
from users.models import UserAccount, Role, Employee # Customer is imported from .models


class CustomerSerializer(serializers.ModelSerializer):
    # Customer model is now linked to UserAccount via user_account OneToOneField
    user_account_username = serializers.CharField(source='user_account.username', read_only=True)
    user_account_email = serializers.EmailField(source='user_account.email', read_only=True)
    user_account_first_name = serializers.CharField(source='user_account.first_name', read_only=True)
    user_account_last_name = serializers.CharField(source='user_account.last_name', read_only=True)
    
    # Assuming 'phone_number' is now on the Customer model itself, not UserAccount directly
    # If phone_number is on UserAccount, you might need to adjust Customer model
    # based on the last forms.py, phone_number is on Customer/Employee profiles
    
    class Meta:
        model = Customer
        # fields should reflect what's on the Customer model and what we want to display from UserAccount
        fields = [
            'id', 'user_account', 'user_account_username', 'user_account_email',
            'user_account_first_name', 'user_account_last_name',
            'phone_number', 'credit_balance' # phone_number is assumed to be on Customer model
        ]
        read_only_fields = [
            'user_account', 'user_account_username', 'user_account_email',
            'user_account_first_name', 'user_account_last_name', 'credit_balance'
        ]
        extra_kwargs = {
            # user_account will be set automatically during user registration or by admin
            'user_account': {'read_only': True} 
        }

    # No specific create/update methods needed here if Customer objects are created/updated
    # primarily via the UserAccountSerializer (e.g., in Admin or user registration).
    # If this serializer is used for direct Customer creation/update, permissions would be key.
    def validate(self, attrs):
        request = self.context.get('request')
        user_account = request.user if request else None

        if not user_account or not user_account.is_authenticated:
            raise serializers.ValidationError(_("Authentication required."))
        
        # Prevent non-admin/non-privileged users from manually linking a customer to a user_account
        if self.instance is None and 'user_account' in attrs and attrs['user_account'] != user_account and \
           not (user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager'])):
            raise serializers.ValidationError({'user_account': _("You do not have permission to assign a customer to a different user account.")})
        
        # If updating, ensure a customer can only update their own profile's phone number
        if self.instance:
            if user_account.role and user_account.role.role_name == 'customer':
                if self.instance.user_account != user_account:
                     raise serializers.ValidationError(_("You can only modify your own customer profile."))
                # Allow customer to update their own phone number
                if 'phone_number' in attrs and attrs['phone_number'] != self.instance.phone_number:
                    self.instance.phone_number = attrs['phone_number'] # Directly update phone_number on instance for simplicity
                    attrs.pop('phone_number') # Remove it from validated_data to prevent super().update trying to set it on UserAccount
            elif not (user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager'])):
                # Staff users can modify customer profiles within their scope, handled by ViewSet permissions
                pass

        return attrs

    def create(self, validated_data):
        # Customer creation is usually tied to UserAccount registration
        # This serializer typically handles retrieving existing customers or is used by admin
        # If direct creation is allowed, ensure 'user_account' is handled correctly.
        # For simplicity, if this is called, assume user_account is implicitly current user or set by admin
        if 'user_account' not in validated_data:
            request = self.context.get('request')
            user_account = request.user
            if user_account and user_account.role.role_name == 'customer':
                validated_data['user_account'] = user_account
            else:
                raise serializers.ValidationError({"user_account": _("User account must be linked to a customer profile for creation.")})
        return super().create(validated_data)


class CustomerCartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(source='product.price_after_discount', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CustomerCartItem
        fields = ['id', 'cart', 'product', 'product_name', 'product_price', 'quantity', 'added_at']
        read_only_fields = ['product_name', 'product_price', 'added_at']
        extra_kwargs = {
            'cart': {'write_only': True},
            'product': {'write_only': True}
        }

    def validate(self, data):
        request = self.context.get('request')
        user_account = request.user if request else None

        if not user_account or not user_account.is_authenticated:
            raise serializers.ValidationError(_("Authentication required."))

        cart = data.get('cart')
        product = data.get('product')
        quantity = data.get('quantity')

        if not cart or not product or quantity is None:
            raise serializers.ValidationError(_("Cart, product, and quantity must be specified."))

        if quantity <= 0:
            raise serializers.ValidationError({'quantity': _('Quantity must be a positive number.')})

        # Check cart ownership/permission based on UserAccount role
        if user_account.role.role_name == 'customer' and cart.customer.user_account != user_account:
            raise serializers.ValidationError({'cart': _('You can only add items to your own cart.')})
        # Check if the user is a staff member and the cart's branch matches their assigned branch/store scope
        elif user_account.role.is_staff_role and hasattr(user_account, 'employee_profile') and user_account.employee_profile:
            employee_profile = user_account.employee_profile
            
            if user_account.role.role_name == 'store_manager':
                if not employee_profile.store or (cart.branch and cart.branch.store != employee_profile.store):
                    raise serializers.ValidationError({'cart': _('You can only modify cart items in your store\'s branches.')})
            elif user_account.role.role_name in ['branch_manager', 'general_staff', 'cashier', 'shelf_organizer', 'customer_service']:
                if not employee_profile.branch or (cart.branch and cart.branch != employee_profile.branch):
                    raise serializers.ValidationError({'cart': _('You can only modify cart items in your assigned branch.')})
        
        # Superuser/AppOwner/ProjectManager has full access, no specific checks here.

        # Ensure product is available in the cart's branch
        if not cart.branch:
            raise serializers.ValidationError({'branch': _('Cart must be associated with a branch to add products.')})

        product_inventory = BranchProductInventory.objects.filter(product=product, branch=cart.branch).first()
        if not product_inventory:
            raise serializers.ValidationError({'product': _('Product is not available in the specified cart branch.')})

        # For updates, get the old quantity to calculate the difference
        instance = self.instance # The existing cart item instance if this is an update
        old_quantity = instance.quantity if instance else 0
        
        needed_quantity_change = quantity - old_quantity # Quantity difference (positive for add, negative for remove)
        
        if needed_quantity_change > 0: # Only check stock if quantity is increasing
            if product_inventory.quantity < needed_quantity_change:
                raise serializers.ValidationError({'quantity': _(f'Requested quantity ({quantity}) is not available in stock. Available: {product_inventory.quantity + old_quantity}')})
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        cart = validated_data['cart']
        product = validated_data['product']
        quantity = validated_data['quantity']

        existing_item = CustomerCartItem.objects.filter(cart=cart, product=product).first()
        # Use select_for_update to lock the inventory row for the duration of the transaction
        product_inventory = BranchProductInventory.objects.select_for_update().get(product=product, branch=cart.branch)

        if existing_item:
            # If item exists, update its quantity and adjust stock
            old_item_quantity = existing_item.quantity
            new_item_quantity = old_item_quantity + quantity
            
            # Stock check for the *total new quantity* compared to *current available + old item quantity*
            # This logic should mostly be covered by validate() if it calculates needed_quantity_change correctly
            # and checks against available inventory before the update.
            
            existing_item.quantity = new_item_quantity
            existing_item.save(update_fields=['quantity'])

            product_inventory.quantity = F('quantity') - quantity # Deduct the *added* quantity
            product_inventory.save(update_fields=['quantity'])
            
            return existing_item
        else:
            # Create new item and deduct stock
            product_inventory.quantity = F('quantity') - quantity
            product_inventory.save(update_fields=['quantity'])
            return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        old_quantity = instance.quantity
        new_quantity = validated_data.get('quantity', old_quantity) # Get new quantity or keep old
        product = instance.product
        cart = instance.cart 

        # Use select_for_update to lock the inventory row
        product_inventory = BranchProductInventory.objects.select_for_update().get(product=product, branch=cart.branch)

        if new_quantity <= 0: # If new quantity is 0 or less, this means removal
            # Return stock and delete the item
            product_inventory.quantity = F('quantity') + old_quantity # Return the full old quantity
            product_inventory.save(update_fields=['quantity'])
            instance.delete()
            return instance # Return the deleted instance (DRF will return 204 No Content for DELETE)

        if new_quantity != old_quantity:
            diff_quantity = new_quantity - old_quantity # Positive if increasing, negative if decreasing
            
            # If increasing, check stock. Validation should have already done this, but a redundant check in atomic transaction is safe.
            if diff_quantity > 0:
                if product_inventory.quantity < diff_quantity: # If current stock is less than what we need to add
                    raise serializers.ValidationError({'quantity': _(f'Not enough stock to increase quantity by {diff_quantity}. Available: {product_inventory.quantity}.')})
            
            # Adjust inventory
            product_inventory.quantity = F('quantity') - diff_quantity
            product_inventory.save(update_fields=['quantity'])
            
        return super().update(instance, validated_data)

    @transaction.atomic
    def destroy(self, instance): # Renamed to 'destroy' for consistency with DRF ViewSet actions
        # When deleting a cart item, return the quantity to stock
        product_inventory = BranchProductInventory.objects.select_for_update().get(product=instance.product, branch=instance.cart.branch)
        product_inventory.quantity = F('quantity') + instance.quantity # Return the quantity of the item being deleted
        product_inventory.save(update_fields=['quantity'])
        instance.delete()


class CustomerCartSerializer(serializers.ModelSerializer):
    # This should be the main Cart Serializer, so it needs to properly handle items and total price.
    items = CustomerCartItemSerializer(many=True, read_only=True) # Nested serializer for cart items
    
    # Access customer's username and branch name via related objects
    customer_username = serializers.CharField(source='customer.user_account.username', read_only=True, allow_null=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True, allow_null=True)
    
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, source='get_total_price') # Use model's method

    class Meta:
        model = CustomerCart
        fields = [
            'id', 'customer', 'customer_username', 'session_key', 'branch', 'branch_name',
            'created_at', 'updated_at', 'is_active', 'total_price', 'items'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'total_price', 'customer_username', 'branch_name', 'items'
        ]
        extra_kwargs = {
            # customer is optional for guest carts initially
            'customer': {'required': False, 'allow_null': True}, 
            # session_key is optional and generated for guest carts
            'session_key': {'required': False, 'allow_blank': True, 'allow_null': True},
            # branch is optional initially but important for items
            'branch': {'required': False, 'allow_null': True}
        }

    def validate(self, data):
        request = self.context.get('request')
        user_account = request.user if request else None
        
        if not user_account or not user_account.is_authenticated:
            raise serializers.ValidationError(_("Authentication required to create or modify a cart."))

        # On create (POST)
        if request.method == 'POST':
            # Customers creating their own cart
            if user_account.role.role_name == 'customer':
                customer_profile = getattr(user_account, 'customer_profile', None)
                if not customer_profile:
                    raise serializers.ValidationError(_("User account is not linked to a customer profile."))

                # Check for an *active* cart for the customer (per branch if applicable)
                if 'branch' in data and data['branch']: # If a branch is specified for customer cart
                    if CustomerCart.objects.filter(customer=customer_profile, branch=data['branch'], is_active=True).exists():
                         raise serializers.ValidationError({'detail': _(f'You already have an active cart for branch {data["branch"].name}. Please use the existing cart or clear it.')})
                else: # Customer creating a cart without a specific branch (e.g., for general app use)
                     if CustomerCart.objects.filter(customer=customer_profile, branch__isnull=True, is_active=True).exists():
                         raise serializers.ValidationError({'detail': _('You already have an active general cart. Please use the existing cart or clear it.')})
                
                # Ensure customer is not trying to set 'customer' field to someone else
                if 'customer' in data and data['customer'] != customer_profile:
                    raise serializers.ValidationError({'customer': _('You can only create a cart for your own customer profile.')})
                data['customer'] = customer_profile # Set customer to current user's profile
                data['session_key'] = None # Registered customers don't use session_key directly

            # Staff creating a cart for a guest
            elif user_account.role.is_staff_role and hasattr(user_account, 'employee_profile') and user_account.employee_profile:
                # Staff *must* specify a branch for carts they create
                if 'branch' not in data or not data['branch']:
                    raise serializers.ValidationError({'branch': _('Branch must be specified when creating a cart as staff.')})
                
                # Check if the staff member has permission to create a cart for the given branch
                employee_profile = user_account.employee_profile
                if user_account.role.role_name == 'store_manager' and employee_profile.store and data['branch'].store != employee_profile.store:
                    raise serializers.ValidationError({'branch': _('You can only create carts for branches within your store.')})
                elif user_account.role.role_name in ['branch_manager', 'general_staff', 'cashier', 'shelf_organizer', 'customer_service'] and data['branch'] != employee_profile.branch:
                    raise serializers.ValidationError({'branch': _('You can only create carts for your assigned branch.')})

                if 'customer' in data and data['customer'] is not None:
                     raise serializers.ValidationError({'customer': _('Staff cannot create a cart for a registered customer directly. Please use a guest cart or manage the registered customer\'s cart via their account.')})
                
                data['customer'] = None # Explicitly set customer to None for staff-created guest carts
                if 'session_key' not in data or not data['session_key']:
                    data['session_key'] = f"guest-{timezone.now().timestamp()}-{secrets.token_hex(4)}" # Generate unique session key

            # Superusers/App Owners/Project Managers can create any cart
            elif not (user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager'])):
                 raise serializers.ValidationError(_("You do not have permission to create carts."))

        # On update (PUT/PATCH)
        if request.method in ['PUT', 'PATCH']:
            instance = self.instance # The existing cart instance
            if not instance:
                return data # Should not happen if instance exists

            # Prevent branch change for existing carts by anyone other than superuser/app_owner/project_manager
            if 'branch' in data and data['branch'] != instance.branch and \
               not (user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager'])):
                raise serializers.ValidationError({'branch': _('You cannot change the branch of an existing cart.')})

            # Ensure 'customer' is not changed unless it's a superuser/app_owner/project_manager
            if 'customer' in data and data['customer'] != instance.customer and \
               not (user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager'])):
                raise serializers.ValidationError({'customer': _('You cannot change the customer of an existing cart.')})
                
            # Ensure 'session_key' is not changed unless it's a superuser/app_owner/project_manager
            if 'session_key' in data and data['session_key'] != instance.session_key and \
               not (user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager'])):
                raise serializers.ValidationError({'session_key': _('You cannot change the session key of an existing cart.')})

            # If user is a customer, ensure they are trying to modify their own cart
            if user_account.role.role_name == 'customer' and instance.customer.user_account != user_account:
                raise serializers.ValidationError({'detail': _('You can only modify your own cart.')})
                
            # If user is staff, ensure they are modifying a cart in their branch/store scope
            if user_account.role.is_staff_role and hasattr(user_account, 'employee_profile') and user_account.employee_profile:
                employee_profile = user_account.employee_profile
                if user_account.role.role_name in ['general_staff', 'cashier', 'shelf_organizer', 'branch_manager', 'customer_service']:
                    if instance.branch and instance.branch != employee_profile.branch:
                        raise serializers.ValidationError({'detail': _('You can only modify carts in your assigned branch.')})
                elif user_account.role.role_name == 'store_manager':
                    if instance.branch and instance.branch.store != employee_profile.store:
                        raise serializers.ValidationError({'detail': _('You can only modify carts in your store\'s branches.')})

        return data

    def create(self, validated_data):
        # 'customer', 'session_key', and 'branch' are handled in validate based on user role/type
        return super().create(validated_data)


class RatingSerializer(serializers.ModelSerializer):
    # Access customer's username from the linked UserAccount
    customer_username = serializers.CharField(source='customer.user_account.username', read_only=True)
    # Access order details
    order_id = serializers.UUIDField(source='order.order_id', read_only=True)
    order_invoice_number = serializers.CharField(source='order.invoice_number', read_only=True)

    class Meta:
        model = Rating
        fields = [
            'id', 'customer', 'customer_username', 'order', 'order_id', 'order_invoice_number',
            'cashier_rating', 'branch_rating', 'app_rating', 'comments', 'submitted_at'
        ]
        read_only_fields = [
            'customer', 'submitted_at', 'customer_username', 'order', 'order_id', 'order_invoice_number'
        ]
        extra_kwargs = {
            'customer': {'read_only': True}, # Customer should be set by signal/logic, not directly by user input
            'order': {'read_only': True}     # Order should be set by signal/logic, not directly by user input
        }

    def validate(self, data):
        request = self.context.get('request')
        user_account = request.user if request else None

        if not user_account or not user_account.is_authenticated:
            raise serializers.ValidationError(_("Authentication required to create or modify a rating."))

        if self.instance: # This is an update operation
            # Only the customer who owns the rating can update it, or superuser/app owner/project manager
            if user_account.role.role_name == 'customer':
                # Check if the customer profile linked to the user account is the owner of the rating
                if not hasattr(user_account, 'customer_profile') or self.instance.customer != user_account.customer_profile:
                    raise serializers.ValidationError(_("You can only update your own ratings."))
            elif not (user_account.is_superuser or (user_account.role and user_account.role.role_name in ['app_owner', 'project_manager'])):
                raise serializers.ValidationError(_("You do not have permission to update this rating."))
        else: # This is a create operation
            # Direct creation of ratings is not allowed via API. They are created by signals after purchase.
            # Customers should update existing ratings that are linked to their orders.
            raise serializers.ValidationError(_("Direct creation of ratings is not allowed. Ratings are created automatically for purchases. Please update an existing rating."))
        
        # Ensure rating values are within valid range (1-5 for example, if applicable)
        for field_name in ['cashier_rating', 'branch_rating', 'app_rating']:
            if field_name in data and not (1 <= data[field_name] <= 5):
                raise serializers.ValidationError({field_name: _("Rating must be between 1 and 5.")})
            
        return data

    @transaction.atomic # Ensure atomicity for updates that might involve other logic later
    def update(self, instance, validated_data):
        # Allow updating specific rating fields and comments
        instance.cashier_rating = validated_data.get('cashier_rating', instance.cashier_rating)
        instance.branch_rating = validated_data.get('branch_rating', instance.branch_rating)
        instance.app_rating = validated_data.get('app_rating', instance.app_rating)
        instance.comments = validated_data.get('comments', instance.comments)
        instance.submitted_at = timezone.now() # Update timestamp on modification
        instance.save()
        return instance
