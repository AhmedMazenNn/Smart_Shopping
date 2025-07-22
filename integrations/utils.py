from datetime import timezone


def calculate_commission_amount(total_amount, commission_rate):
    return round(total_amount * (commission_rate / 100), 2)

def format_sync_message(order, status):
    return f"Order {order.order_id} sync {status} at {timezone.now().isoformat()}"
