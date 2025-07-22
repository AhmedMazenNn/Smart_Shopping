from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from users.models import UserAccount, Role
from .models import Store, Branch
from .utils import generate_store_username, generate_secure_password

@receiver(post_save, sender=Store)
def create_store_primary_user(sender, instance, created, **kwargs):
    """
    Automatically creates a primary user for the store after creation.
    """
    if created and instance.login_email and not instance.user:
        try:
            with transaction.atomic():
                store_account_role = Role.objects.get(role_name='store_account')

                existing_usernames = set(
                    UserAccount.objects.values_list('username', flat=True)
                )
                username = generate_store_username(instance.name, prefix=store_account_role.role_name, existing_usernames=existing_usernames)
                password = generate_secure_password()

                user = UserAccount.objects.create_user(
                    email=instance.login_email,
                    password=password,
                    username=username,
                    role=store_account_role,
                    is_active=True,
                    first_name=instance.name,
                    last_name=_("Account")
                )

                instance.user = user
                instance.save(update_fields=['user'])

                print(f"\n--- STORE PRIMARY ACCOUNT CREATED ---")
                print(f"Username: {user.username}")
                print(f"Email: {user.email}")
                print(f"Temporary Password: {password}")
                print(_("Please change this password after the first login."))
                print("--------------------------------------\n")

        except Role.DoesNotExist:
            raise ValidationError(_("The 'store_account' role does not exist. Please create it first."))
        except Exception as e:
            print(f"Error creating primary store user: {e}")
            if instance.pk:
                instance.delete()
            raise ValidationError(_(f"Failed to create primary store account: {e}"))

@receiver(post_save, sender=Branch)
def link_branch_manager_to_branch(sender, instance, created, **kwargs):
    """
    Ensure the branch manager is linked to the branch/store correctly.
    """
    if instance.manager_employee:
        if instance.manager_employee.branch != instance:
            instance.manager_employee.branch = instance
            instance.manager_employee.save(update_fields=['branch'])
        if instance.manager_employee.store != instance.store:
            instance.manager_employee.store = instance.store
            instance.manager_employee.save(update_fields=['store'])
