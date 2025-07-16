# integrations/connectors/xero.py

from .base import BaseAccountingConnector, STANDARD_PRODUCT_FORMAT, STANDARD_SALES_ORDER_FORMAT
import requests
import json
import datetime

class XeroConnector(BaseAccountingConnector):
    def __init__(self, store, integration_settings):
        super().__init__(store, integration_settings)
        self.access_token = self.settings.get('access_token')
        self.tenant_id = self.settings.get('tenant_id') # Xero Tenant ID
        self.base_url = "https://api.xero.com/api.xro/2.0/" # Xero API Base URL

    def pull_products(self) -> List[Dict[str, Any]]:
        print(f"Pulling products for store {self.store.name} from Xero...")
        # تنفيذ سحب المنتجات من Xero API
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json',
            'Xero-Tenant-Id': self.tenant_id
        }
        try:
            response = requests.get(f"{self.base_url}Items", headers=headers)
            response.raise_for_status()
            xero_items = response.json().get('Items', [])
            
            standard_products = []
            for item in xero_items:
                standard_products.append({
                    'barcode': item.get('Code'), # Xero uses 'Code' often as unique ID
                    'name': item.get('Name'),
                    'item_number': item.get('ItemID'), # Xero internal ID
                    'price': item.get('SalesDetails', {}).get('UnitPrice', 0.0),
                    'expiry_date': None,
                    'quantity_in_stock': None, # Xero might need separate inventory calls
                })
            return standard_products
        except Exception as e:
            print(f"Error pulling products from Xero for store {self.store.name}: {e}")
            raise

    def push_sales(self, order_data: Dict[str, Any]) -> bool:
        print(f"Pushing sales for order {order_data['sales_transaction_id']} to Xero for store {self.store.name}...")
        # تنفيذ دفع بيانات المبيعات إلى Xero API (كـ invoices أو sales receipts)
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Xero-Tenant-Id': self.tenant_id
        }

        xero_invoice_lines = []
        for item in order_data['items_sold']:
            xero_invoice_lines.append({
                "LineAmount": item['quantity_sold'] * item['sale_price_per_unit'],
                "Description": item['product_name'] if 'product_name' in item else item['product_barcode'],
                "Quantity": item['quantity_sold'],
                "UnitAmount": item['sale_price_per_unit'],
                "ItemCode": item['barcode'] if item['barcode'] else item['item_number'], # استخدام الكود أو رقم الصنف
                # "AccountCode": "200" # يجب أن تعرف حساب الإيرادات في Xero
            })

        xero_invoice_payload = {
            "Type": "ACCREC", # حساب مدين (فاتورة مبيعات)
            "Contact": {
                "ContactID": self.settings.get('default_xero_contact_id', "YOUR_DEFAULT_CONTACT_ID_IN_XERO") # ربط العميل أو عميل افتراضي
            },
            "Date": str(order_data['sale_date']),
            "DueDate": str(order_data['sale_date'] + datetime.timedelta(days=7)), # مثال لتاريخ الاستحقاق
            "LineItems": xero_invoice_lines,
            "Status": "AUTHORISED", # قد يكون DRAFT أو AUTHORISED
            "Reference": f"ORDER_{order_data['sales_transaction_id']}"
        }

        try:
            response = requests.post(f"{self.base_url}Invoices", headers=headers, json=xero_invoice_payload)
            response.raise_for_status()
            print(f"Successfully pushed order {order_data['sales_transaction_id']} to Xero for store {self.store.name}.")
            return True
        except Exception as e:
            print(f"Error pushing sales for order {order_data['sales_transaction_id']} to Xero: {e}")
            raise

    def test_connection(self) -> bool:
        print(f"Testing Xero connection for store {self.store.name}...")
        try:
            # محاولة سحب شيء بسيط لاختبار الاتصال
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json',
                'Xero-Tenant-Id': self.tenant_id
            }
            response = requests.get(f"{self.base_url}Organisations", headers=headers)
            response.raise_for_status()
            print(f"Xero connection successful for store {self.store.name}.")
            return True
        except Exception as e:
            print(f"Xero connection failed for store {self.store.name}: {e}")
            return False
    
    def get_supported_features(self) -> Dict[str, Any]:
        return {
            'webhooks_supported': True, # Xero يدعم webhooks
            'polling_intervals': ['hourly', 'daily'],
            'oauth2_flow': True, # Xero يستخدم OAuth2
        }