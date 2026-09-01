import razorpay
from typing import Dict, Any
from app.config import settings
from app.database import fetch_order, update_payment_details

class PaymentProviderError(Exception):
    pass


class RazorpayPaymentService:
    """
    Provider-isolated Razorpay client that creates payment orders in TEST MODE.
    """
    def __init__(self):
        # We only instantiate the client if keys are available, although they have defaults.
        # Ensure we never log the secret key.
        self.key_id = settings.razorpay_key_id
        self.key_secret = settings.razorpay_key_secret
        if not self.key_id or not self.key_secret:
            raise ValueError("Razorpay credentials are not configured.")
            
        self.client = razorpay.Client(auth=(self.key_id, self.key_secret))

    def create_payment_order(self, order_id: str) -> Dict[str, Any]:
        """
        Creates a Razorpay payment order for an existing internal order.
        """
        # Load authoritative order
        order = fetch_order(order_id)
        if not order:
            raise ValueError(f"Order '{order_id}' not found.")
            
        # Prevent duplicate Razorpay order creation
        if order.payment_status == "PENDING" and order.razorpay_order_id:
            return {
                "order_id": order.order_id,
                "razorpay_order_id": order.razorpay_order_id,
                "payment_status": order.payment_status,
                "amount_paise": int(order.total_amount * 100),
                "currency": order.currency,
                "message": "Payment order already exists."
            }
            
        # Authoritative total amount in paise
        amount_paise = int(order.total_amount * 100)
        
        # Razorpay payload
        payload = {
            "amount": amount_paise,
            "currency": order.currency,
            "receipt": order.order_id,
            "payment_capture": 1
        }
        
        try:
            razorpay_order = self.client.order.create(data=payload)
        except Exception as e:
            # Clean handling of provider errors
            raise PaymentProviderError(f"Razorpay API Error: {str(e)}") from e
            
        # Persist payment details
        update_payment_details(
            order_id=order.order_id,
            provider="razorpay",
            razorpay_order_id=razorpay_order["id"],
            payment_status="PENDING"
        )
        
        return {
            "order_id": order.order_id,
            "razorpay_order_id": razorpay_order["id"],
            "payment_status": "PENDING",
            "amount_paise": amount_paise,
            "currency": order.currency
        }


def create_payment_order(order_id: str) -> Dict[str, Any]:
    """Service function to be called by the tool executor."""
    service = RazorpayPaymentService()
    return service.create_payment_order(order_id)
