# main/payment_utils.py
from django.core.mail import send_mail
from django.conf import settings

def send_order_email(order, payment_method):
    subject = f"Order #{order.id} Confirmation ({payment_method})"
    message = f"""
    Thank you for your order!
    Payment Method: {payment_method}
    Total: Rs. {order.total_price}
    """
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.user.email],
        fail_silently=False,
    )