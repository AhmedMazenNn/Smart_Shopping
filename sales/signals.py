# C:\Users\DELL\SER SQL MY APP\sales\signals.py
# هذا التعليق هو أول سطر في الملف، يليه مباشرة الكود البرمجي

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order # استيراد نموذج Order بدلاً من Invoice
from customers.models import Rating # استيراد نموذج التقييم من تطبيق customers
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Order) # <--- تم تغيير 'Invoice' إلى 'Order' هنا
def create_or_update_rating_for_order(sender, instance, created, **kwargs):
    """
    عند إنشاء طلب (Order) جديد، يتم إنشاء سجل تقييم فارغ تلقائيًا وربطه به.
    """
    if created: # هذا الشرط يعني أن الطلب تم إنشاؤه (ليست تحديثًا)
        try:
            # التحقق مما إذا كان هناك تقييم موجود بالفعل لهذا الطلب
            # (نستخدم related_name 'rating' من Rating.order)
            # ملاحظة: if not hasattr(instance, 'rating') قد لا يكون دقيقًا دائمًا لـ OneToOneField.
            # الأفضل هو استخدام if not Rating.objects.filter(order=instance).exists():
            if not Rating.objects.filter(order=instance).exists(): # <-- تعديل مقترح هنا
                # إنشاء سجل تقييم جديد وربطه بالطلب والعميل.
                # العميل قد يكون None إذا كان الطلب لعميل غير مسجل.
                # في هذه الحالة، حقل العميل في Rating مسموح بـ null (تم تعديله في customers/models.py).
                customer_obj = instance.customer # إذا كان العميل موجودًا في الطلب
                
                Rating.objects.create(
                    order=instance, # <--- تم تغيير 'invoice' إلى 'order' هنا
                    customer=customer_obj # ربط التقييم بالعميل المرتبط بالطلب
                )
                logger.info(f"Rating record created for Order: {instance.order_id or instance.id}")
            else:
                logger.info(f"Rating record already exists for Order: {instance.order_id or instance.id}. Skipping creation.")
        except Exception as e:
            logger.error(f"Error creating rating for order {instance.order_id or instance.id}: {e}")

