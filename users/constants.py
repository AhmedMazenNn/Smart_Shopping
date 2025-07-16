from enum import Enum

class UserType(Enum):
    APP_OWNER = 'app_owner'
    PROJECT_MANAGER = 'project_manager'
    APP_STAFF = 'app_staff'
    STORE_ACCOUNT = 'store_account'
    STORE_MANAGER = 'store_manager'
    BRANCH_MANAGER = 'branch_manager'
    GENERAL_STAFF = 'general_staff'
    CASHIER = 'cashier'
    SHELF_ORGANIZER = 'shelf_organizer'
    CUSTOMER_SERVICE = 'customer_service'
    PLATFORM_CUSTOMER = 'platform_customer'

    @classmethod
    def choices(cls):
        return [(key.value, key.name.replace('_', ' ').title()) for key in cls]
