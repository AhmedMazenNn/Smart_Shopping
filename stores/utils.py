import secrets
import string
from django.utils.text import slugify

def generate_store_username(base_name: str, prefix: str = "STORE_ACCOUNT", existing_usernames: set = None) -> str:
    """
    Generate a unique username for a store-related user.
    """
    base_slug = slugify(base_name)
    prefix = f"{prefix.upper().replace(' ', '_')}-"
    candidate = f"{prefix}{base_slug}"
    counter = 0

    existing_usernames = existing_usernames or set()

    while candidate in existing_usernames:
        counter += 1
        candidate = f"{prefix}{base_slug}-{counter}"
    
    return candidate

def generate_secure_password(length: int = 12) -> str:
    """
    Generate a secure random password for the store account.
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
