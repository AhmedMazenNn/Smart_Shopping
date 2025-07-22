# sales/utils.py
import json
import secrets
import hmac
import hashlib
import base64
import os
from io import BytesIO
from decimal import Decimal
from PIL import Image
from django.utils import timezone
from django.core.files import File
from django.db import models
from django.conf import settings
from django.db.models import Sum, F
import qrcode

def calculate_order_totals(order):
    """
    Calculates and returns total amounts for the given order:
    - total_before_vat
    - total_vat
    - total_amount (final)
    """
    items = order.items.all()

    total_before_vat = items.aggregate(
        total=Sum(F('quantity') * F('unit_price'), output_field=models.DecimalField())
    )['total'] or Decimal('0.00')

    total_vat = items.aggregate(
        vat=Sum(F('quantity') * F('vat_amount'), output_field=models.DecimalField())
    )['vat'] or Decimal('0.00')

    fee_amount = order.fee_amount or Decimal('0.00')
    total_amount = total_before_vat + total_vat + fee_amount

    return {
        'total_before_vat': total_before_vat,
        'total_vat': total_vat,
        'total_amount': total_amount,
        'fee_amount': fee_amount,
    }


def calculate_return_total(return_obj):
    """
    Calculates the total returned amount from all ReturnItems under this return_obj.
    """
    returned_items = return_obj.returned_items.all()
    total = returned_items.aggregate(
        total=Sum(F('quantity_returned') * F('price_at_return'), output_field=models.DecimalField())
    )['total'] or Decimal('0.00')
    return total

def generate_invoice_number(branch):
    timestamp_str = timezone.now().strftime('%Y%m%d%H%M%S')
    random_hex = secrets.token_hex(4).upper()
    if not branch.store:
        return f"NOSTORE-{branch.id}-{timestamp_str}-{random_hex}"
    return f"{branch.store.id}-{branch.id}-{timestamp_str}-{random_hex}"

def generate_signed_qr_data(order, qr_type='initial'):
    data = {
        'order_id': str(order.order_id),
        'branch_id': str(order.branch.id) if order.branch else None,
        'customer_id': str(order.customer.id) if order.customer else None,
        'cashier_id': str(order.performed_by.id) if order.performed_by else None,
        'type': qr_type,
        'timestamp': timezone.now().isoformat(),
    }

    if qr_type == 'exit':
        expiry = timezone.now() + timezone.timedelta(days=getattr(settings, 'RETURN_QR_CODE_VALIDITY_DAYS', 30))
        data['expiry'] = expiry.isoformat()
        data['status'] = order.status
        if order.invoice_number and order.branch and order.branch.store:
            data['zatca_data'] = {
                'seller_name': order.branch.store.name,
                'vat_registration_number': order.branch.store.tax_id or order.branch.branch_tax_id or '',
                'invoice_timestamp': order.invoice_issue_date.isoformat() if order.invoice_issue_date else timezone.now().isoformat(),
                'invoice_total': str(order.total_amount),
                'vat_total': str(order.total_vat_amount),
            }

    data_string = json.dumps(data, sort_keys=True)
    signature = hmac.new(settings.SECRET_KEY.encode(), data_string.encode(), hashlib.sha256).digest()
    data['signature'] = base64.urlsafe_b64encode(signature).decode()
    return json.dumps(data)

def generate_qr_image(qr_data: str, filename: str) -> File:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'app_logo.png')
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo_size = int(img.size[0] * 0.20)
        logo = logo.resize((logo_size, logo_size))
        x = (img.size[0] - logo.size[0]) // 2
        y = (img.size[1] - logo.size[1]) // 2
        img.paste(logo, (x, y), logo)

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return File(buffer, name=filename)
