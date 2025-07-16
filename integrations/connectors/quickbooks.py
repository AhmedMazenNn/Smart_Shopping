# integrations/connectors/quickbooks.py

from .base import BaseAccountingConnector, STANDARD_PRODUCT_FORMAT, STANDARD_SALES_ORDER_FORMAT
import requests
import json
import datetime

# قد تحتاج إلى مكتبة SDK لـ QuickBooks إذا كانت متوفرة ومعقدة
# pip install python-quickbooks (أو المكتبة الرسمية إذا كانت موجودة)

class QuickBooksConnector(BaseAccountingConnector):
    def __init__(self, store, integration_settings):
        super().__init__(store, integration_settings)
        # استخلاص الإعدادات الخاصة بـ QuickBooks من settings_json
        # تذكر فك التشفير هنا إذا لزم الأمر
        self.access_token = self.settings.get('access_token')
        self.refresh_token = self.settings.get('refresh_token')
        self.realm_id = self.settings.get('realm_id') # معرف الشركة في QuickBooks Online
        self.client_id = self.settings.get('client_id')
        self.client_secret = self.settings.get('client_secret')
        self.base_url = "https://sandbox-quickbooks.api.intuit.com/v3/company/" # غيرها إلى Production URL
        
        # مثال بسيط لعنوان URL لتجديد التوكن (قد تحتاج إلى دالة مخصصة)
        self.oauth_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

    def _refresh_access_token(self):
        """
        دالة مساعدة لتجديد access token إذا انتهت صلاحيته.
        هذا مثال بسيط وقد يتطلب منطقًا أكثر تعقيدًا وإدارة للحالة.
        """
        print(f"Refreshing QuickBooks token for store {self.store.name}...")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": "Basic " + self.settings.get('basic_auth_header') # Client ID:Client Secret base64 encoded
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        try:
            response = requests.post(self.oauth_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token', self.refresh_token) # Refresh token might change
            
            # تحديث الإعدادات في قاعدة البيانات (مهم جداً!)
            self.settings['access_token'] = self.access_token
            self.settings['refresh_token'] = self.refresh_token
            
            # احفظ التغييرات على نموذج StoreAccountingIntegration
            # يمكنك تحديث النموذج مباشرةً هنا أو إرجاع الإعدادات المحدثة.
            # الأسهل هو أن تقوم مهمة المزامنة بحفظ الإعدادات المحدثة بعد كل عملية.
            
            print(f"QuickBooks token refreshed successfully for store {self.store.name}.")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Failed to refresh QuickBooks token for store {self.store.name}: {e}")
            return False

    def _make_quickbooks_request(self, method, endpoint, headers=None, json_data=None, params=None):
        """
        دالة مساعدة لإنشاء طلبات لـ QuickBooks API مع معالجة التوكن.
        """
        if not self.access_token:
            if not self._refresh_access_token():
                raise ConnectionError("Failed to get QuickBooks access token.")
        
        url = f"{self.base_url}{self.realm_id}/{endpoint}"
        
        default_headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json' if json_data else 'application/x-www-form-urlencoded'
        }
        if headers:
            default_headers.update(headers)

        try:
            response = requests.request(method, url, headers=default_headers, json=json_data, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401 and self._refresh_access_token():
                # حاول مرة أخرى بعد تجديد التوكن
                response = requests.request(method, url, headers=default_headers, json=json_data, params=params)
                response.raise_for_status()
                return response.json()
            raise # أعد إلقاء الاستثناء إذا لم ينجح التجديد أو كان الخطأ ليس 401
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"QuickBooks API request failed: {e}")

    def pull_products(self) -> List[Dict[str, Any]]:
        print(f"Pulling products for store {self.store.name} from QuickBooks...")
        try:
            # مثال على استعلام لسحب المنتجات من QuickBooks
            # قد تحتاج إلى التعامل مع pagination إذا كان هناك عدد كبير من المنتجات
            response_data = self._make_quickbooks_request(
                'GET',
                'query',
                params={'query': "SELECT * FROM Item MAXRESULTS 1000"}
            )
            
            quickbooks_items = response_data.get('QueryResponse', {}).get('Item', [])
            
            standard_products = []
            for qb_item in quickbooks_items:
                # تحويل حقول QuickBooks إلى تنسيق STANDARD_PRODUCT_FORMAT
                product_barcode = qb_item.get('Sku')
                product_name = qb_item.get('Name')
                # السعر قد يكون في حقول مختلفة حسب نوع المنتج (service/inventory)
                sale_price = qb_item.get('UnitPrice', qb_item.get('SalesTaxRate', 0.0)) # مثال
                
                # يمكنك إضافة المزيد من المنطق هنا للتحقق من أنواع المنتجات
                # أو التعامل مع الحقول التي لا تتوفر دائمًا
                
                standard_products.append({
                    'barcode': product_barcode,
                    'name': product_name,
                    'item_number': qb_item.get('Id'), # QuickBooks ID كـ item_number
                    'price': float(sale_price),
                    'expiry_date': None, # QuickBooks لا يدعم تاريخ الانتهاء للمنتجات عادةً
                    'quantity_in_stock': int(qb_item.get('QtyOnHand', 0)) if qb_item.get('Type') == 'Inventory' else None,
                })
            return standard_products
        except Exception as e:
            print(f"Error pulling products from QuickBooks for store {self.store.name}: {e}")
            # من المهم إعادة إلقاء الاستثناء هنا ليتم التعامل معه بواسطة المهمة الخلفية
            raise

    def push_sales(self, order_data: Dict[str, Any]) -> bool:
        print(f"Pushing sales for order {order_data['sales_transaction_id']} to QuickBooks for store {self.store.name}...")
        try:
            # بناء حمولة (payload) طلب المبيعات لـ QuickBooks
            # يجب أن يتوافق هذا مع بنية بيانات QuickBooks SaleReceipts أو Invoices
            qb_line_items = []
            for item in order_data['items_sold']:
                qb_line_items.append({
                    "DetailType": "SalesItemLineDetail",
                    "SalesItemLineDetail": {
                        "ItemRef": {
                            "value": item['item_number'], # استخدم item_number لربط المنتج بـ QuickBooks ID
                            "name": item['product_name'] if 'product_name' in item else ""
                        },
                        "UnitPrice": item['sale_price_per_unit'],
                        "Qty": item['quantity_sold']
                    },
                    "Amount": item['quantity_sold'] * item['sale_price_per_unit'],
                    "Description": item['product_name']
                })
            
            qb_sales_receipt_payload = {
                "Line": qb_line_items,
                "CustomerRef": {
                    "value": self.settings.get('default_customer_id', "YOUR_DEFAULT_CUSTOMER_ID_IN_QB") # قد تحتاج لربط العملاء أو استخدام عميل افتراضي
                },
                "SalesReceiptExemption": { # قد تحتاج إلى ضبط الإعفاء الضريبي
                    "name": "NonTaxable",
                    "value": "NonTaxable"
                },
                "TxnDate": str(order_data['sale_date']),
                # يمكنك إضافة حقول أخرى مثل Memo, SalesTermRef, BillEmail, إلخ.
            }

            self._make_quickbooks_request('POST', 'salesreceipt', json_data=qb_sales_receipt_payload)
            print(f"Successfully pushed order {order_data['sales_transaction_id']} to QuickBooks for store {self.store.name}.")
            return True
        except Exception as e:
            print(f"Error pushing sales for order {order_data['sales_transaction_id']} to QuickBooks: {e}")
            raise

    def test_connection(self) -> bool:
        print(f"Testing QuickBooks connection for store {self.store.name}...")
        try:
            # مثال على اختبار الاتصال بسحب بيانات شركة بسيطة
            self._make_quickbooks_request('GET', 'companyinfo/{self.realm_id}')
            print(f"QuickBooks connection successful for store {self.store.name}.")
            return True
        except Exception as e:
            print(f"QuickBooks connection failed for store {self.store.name}: {e}")
            return False

    def get_supported_features(self) -> Dict[str, Any]:
        return {
            'webhooks_supported': False, # QuickBooks يدعم webhooks لكن يتطلب إعدادات إضافية
            'polling_intervals': ['hourly', 'daily', 'twice_daily'],
            'oauth2_flow': True, # QuickBooks يستخدم OAuth2
        }