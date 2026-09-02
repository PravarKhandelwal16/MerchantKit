import razorpay
from typing import Dict, Any
from app.config import settings
from app.database import fetch_order, update_payment_details
from app.audit import audit_logger

class PaymentProviderError(Exception):
    pass

class PaymentStateError(Exception):
    pass

# Payment States
NOT_CREATED = "NOT_CREATED"
PENDING = "PENDING"
PAYMENT_INITIATED = "PAYMENT_INITIATED"
PAID = "PAID"
FAILED = "FAILED"

class RazorpayPaymentService:
    """
    Provider-isolated Razorpay client that creates payment orders in TEST MODE.
    """
    def __init__(self):
        self.key_id = settings.razorpay_key_id
        self.key_secret = settings.razorpay_key_secret
        if not self.key_id or not self.key_secret:
            raise ValueError("Razorpay credentials are not configured.")
            
        self.client = razorpay.Client(auth=(self.key_id, self.key_secret))

    def create_payment_order(self, order_id: str) -> Dict[str, Any]:
        """
        Creates a Razorpay payment order for an existing internal order.
        """
        order = fetch_order(order_id)
        if not order:
            raise ValueError(f"Order '{order_id}' not found.")
            
        current_status = order.payment_status or NOT_CREATED
        
        # Enforce valid state transition (None/NOT_CREATED -> PENDING)
        if current_status in [PAYMENT_INITIATED, PAID, FAILED]:
            raise PaymentStateError(f"Invalid state transition: Cannot create payment order from {current_status}")
            
        # Prevent duplicate Razorpay order creation
        if current_status == PENDING and order.razorpay_order_id:
            return {
                "order_id": order.order_id,
                "razorpay_order_id": order.razorpay_order_id,
                "payment_status": order.payment_status,
                "amount_paise": int(order.total_amount * 100),
                "currency": order.currency,
                "message": "Payment order already exists."
            }
            
        amount_paise = int(order.total_amount * 100)
        
        payload = {
            "amount": amount_paise,
            "currency": order.currency,
            "receipt": order.order_id,
            "payment_capture": 1
        }
        
        try:
            razorpay_order = self.client.order.create(data=payload)
        except Exception as e:
            raise PaymentProviderError(f"Razorpay API Error: {str(e)}") from e
            
        update_payment_details(
            order_id=order.order_id,
            provider="razorpay",
            razorpay_order_id=razorpay_order["id"],
            payment_status=PENDING
        )
        
        return {
            "order_id": order.order_id,
            "razorpay_order_id": razorpay_order["id"],
            "payment_status": PENDING,
            "amount_paise": amount_paise,
            "currency": order.currency
        }

    def initiate_checkout_payment(self, order_id: str) -> Dict[str, Any]:
        """
        Backend operation suitable for a frontend/checkout flow to request payment initiation.
        Transitions PENDING -> PAYMENT_INITIATED.
        Returns safe checkout data. NEVER exposes the secret.
        """
        order = fetch_order(order_id)
        if not order:
            raise ValueError(f"Order '{order_id}' not found.")
            
        current_status = order.payment_status or NOT_CREATED
        
        if current_status != PENDING:
            audit_logger.log_tool_call(
                actor="checkout_flow",
                action="initiate_payment",
                arguments={"order_id": order_id},
                success=False,
                error_code="INVALID_TRANSITION",
                reason=f"Invalid state transition: Cannot initiate payment from {current_status}"
            )
            raise PaymentStateError(f"Invalid state transition: Cannot initiate payment from {current_status}")
            
        update_payment_details(
            order_id=order.order_id,
            provider="razorpay",
            razorpay_order_id=order.razorpay_order_id,
            payment_status=PAYMENT_INITIATED
        )
        
        # Return ONLY safe data suitable for frontend consumption
        safe_response = {
            "razorpay_key_id": self.key_id,
            "razorpay_order_id": order.razorpay_order_id,
            "amount": int(order.total_amount * 100),
            "currency": order.currency,
            "internal_order_reference": order.order_id,
            "payment_status": PAYMENT_INITIATED
        }
        
        audit_logger.log_tool_call(
            actor="checkout_flow",
            action="initiate_payment",
            arguments={"order_id": order_id},
            result={"payment_status": PAYMENT_INITIATED, "razorpay_order_id": order.razorpay_order_id},
            success=True
        )
        
        return safe_response


    def verify_payment_signature(self, razorpay_payment_id: str, razorpay_order_id: str, razorpay_signature: str) -> Dict[str, Any]:
        """
        Verifies the Razorpay payment signature cryptographically.
        Transitions PAYMENT_INITIATED -> PAID if valid.
        """
        from app.database import fetch_order_by_razorpay_order_id
        
        order = fetch_order_by_razorpay_order_id(razorpay_order_id)
        if not order:
            audit_logger.log_tool_call(
                actor="payment_verification",
                action="verify_payment",
                arguments={"razorpay_payment_id": razorpay_payment_id, "razorpay_order_id": razorpay_order_id},
                success=False,
                error_code="ORDER_NOT_FOUND",
                reason=f"No internal order found for Razorpay order {razorpay_order_id}"
            )
            raise ValueError(f"No internal order found for Razorpay order '{razorpay_order_id}'")
            
        current_status = order.payment_status or NOT_CREATED
        
        if current_status == PAID:
            audit_logger.log_tool_call(
                actor="payment_verification",
                action="verify_payment",
                arguments={"razorpay_payment_id": razorpay_payment_id, "razorpay_order_id": razorpay_order_id},
                success=False,
                error_code="REPLAY_ATTEMPT",
                reason=f"Payment already verified for order {order.order_id}"
            )
            raise PaymentStateError(f"Payment already verified for order '{order.order_id}'")
            
        if current_status != PAYMENT_INITIATED:
            audit_logger.log_tool_call(
                actor="payment_verification",
                action="verify_payment",
                arguments={"razorpay_payment_id": razorpay_payment_id, "razorpay_order_id": razorpay_order_id},
                success=False,
                error_code="INVALID_STATE",
                reason=f"Cannot verify payment from state {current_status}"
            )
            raise PaymentStateError(f"Cannot verify payment from state {current_status}")
            
        # Perform signature verification
        try:
            self.client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
        except razorpay.errors.SignatureVerificationError as e:
            # Audit failure but do not automatically transition to FAILED to avoid abuse,
            # though instructions say "transition to FAILED only when appropriate". Let's not transition.
            audit_logger.log_tool_call(
                actor="payment_verification",
                action="verify_payment",
                arguments={"razorpay_payment_id": razorpay_payment_id, "razorpay_order_id": razorpay_order_id},
                success=False,
                error_code="INVALID_SIGNATURE",
                reason=f"Razorpay signature verification failed"
            )
            raise PaymentProviderError(f"Signature verification failed")
            
        # Signature is valid. Transition to PAID.
        update_payment_details(
            order_id=order.order_id,
            provider="razorpay",
            razorpay_order_id=razorpay_order_id,
            payment_status=PAID
        )
        
        audit_logger.log_tool_call(
            actor="payment_verification",
            action="verify_payment",
            arguments={"razorpay_payment_id": razorpay_payment_id, "razorpay_order_id": razorpay_order_id},
            result={"payment_status": PAID, "internal_order_id": order.order_id},
            success=True
        )
        
        return {
            "success": True,
            "order_id": order.order_id,
            "payment_status": PAID,
            "message": "Payment verified successfully"
        }

def create_payment_order(order_id: str) -> Dict[str, Any]:
    """Service function to be called by the tool executor."""
    service = RazorpayPaymentService()
    return service.create_payment_order(order_id)
