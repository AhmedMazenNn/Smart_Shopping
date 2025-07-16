# integrations/connectors/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import datetime

# تعريف تنسيق المنتج القياسي الذي سيتعامل معه تطبيقك
# كل موصل سيحول بيانات برنامجه المحاسبي إلى هذا التنسيق
STANDARD_PRODUCT_FORMAT = {
    "barcode": str,
    "name": str,
    "item_number": Optional[str], # رقم الصنف في برنامج المحاسبة
    "price": float,
    "expiry_date": Optional[datetime.date],
    "quantity_in_stock": Optional[int], # للكميات الأولية عند السحب
    # أضف هنا أي حقول منتج أخرى تحتاجها من برنامج المحاسبة
}

# تعريف تنسيق بيانات المبيعات القياسي الذي سيرسله تطبيقك
# كل موصل سيحول بيانات المبيعات من هذا التنسيق إلى تنسيق برنامجه المحاسبي
STANDARD_SALES_ORDER_FORMAT = {
    "sales_transaction_id": int, # معرف الطلب في نظامك
    "sale_date": datetime.date,
    "branch_id_in_your_app": int, # معرف الفرع في نظامك
    "store_accounting_ref_id": Optional[str], # معرف المتجر في نظام المحاسبة الخارجي
    "total_amount": float,
    "customer_info": Optional[Dict[str, Any]], # بيانات العميل (اختياري)
    "items_sold": List[Dict[str, Any]] # قائمة بالمنتجات المباعة
    # كل عنصر في items_sold سيكون:
    # {
    #   "product_barcode": str,
    #   "item_number": Optional[str],
    #   "quantity_sold": int,
    #   "sale_price_per_unit": float
    # }
}


class BaseAccountingConnector(ABC):
    """
    واجهة مجردة يجب على جميع موصلات برامج المحاسبة تنفيذها.
    """
    def __init__(self, store: 'Store', integration_settings: Dict[str, Any]):
        self.store = store
        # الإعدادات تحتوي على API keys, URLs, tokens الخ.
        # يجب فك تشفير البيانات الحساسة هنا إذا تم تشفيرها عند التخزين.
        self.settings = integration_settings

    @abstractmethod
    def pull_products(self) -> List[Dict[str, Any]]:
        """
        يسحب بيانات المنتجات من برنامج المحاسبة.
        يجب أن يعيد قائمة من القواميس، كل قاموس يمثل منتجًا بتنسيق STANDARD_PRODUCT_FORMAT.
        """
        pass

    @abstractmethod
    def push_sales(self, order_data: Dict[str, Any]) -> bool:
        """
        يرسل بيانات المبيعات (من طلب مكتمل) إلى برنامج المحاسبة.
        order_data سيكون قاموسًا بتنسيق STANDARD_SALES_ORDER_FORMAT.
        يعيد True عند النجاح، False عند الفشل.
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        يختبر الاتصال بـ API لبرنامج المحاسبة باستخدام الإعدادات الحالية.
        يعيد True إذا كان الاتصال ناجحًا، False بخلاف ذلك.
        """
        pass

    def get_supported_features(self) -> Dict[str, Any]:
        """
        يعيد قاموسًا بالميزات المدعومة بواسطة هذا الموصل.
        مثال: {'webhooks_supported': False, 'polling_intervals': ['hourly', 'daily']}
        """
        return {
            'webhooks_supported': False,
            'polling_intervals': ['hourly', 'daily']
        }