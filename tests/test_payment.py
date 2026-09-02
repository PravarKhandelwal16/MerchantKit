"""
Tests for Part 7A: Razorpay Test Mode Order Creation.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.database import init_db, insert_product, get_db_connection
from app.schemas import Product
from app.cart import create_cart, add_to_cart
from app.order import create_order_from_cart
from app.payment import create_payment_order, PaymentProviderError, RazorpayPaymentService
from app.audit import AuditLogger


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    conn = get_db_connection()
    for table in ("order_items", "orders", "cart_items", "carts", "products", "audit_logs"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()
    yield


@pytest.fixture(autouse=True)
def mock_razorpay_credentials(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "razorpay_key_id", "rzp_test_mock_id")
    monkeypatch.setattr(settings, "razorpay_key_secret", "rzp_test_mock_secret")



@pytest.fixture
def audit() -> AuditLogger:
    return AuditLogger()


def setup_order(price=899.0):
    insert_product(Product(
        product_id="P1", name="Test Product", price=price,
        category="mouse", stock=10,
    ))
    cart = create_cart()
    add_to_cart(cart.cart_id, "P1", 1)
    order = create_order_from_cart(cart.cart_id)
    return order


@patch("app.payment.razorpay.Client")
def test_create_payment_order_success(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.order.create.return_value = {"id": "order_rzp123"}
    
    order = setup_order(price=899.0)
    
    result = create_payment_order(order.order_id)
    
    assert result["razorpay_order_id"] == "order_rzp123"
    assert result["payment_status"] == "PENDING"
    assert result["amount_paise"] == 89900
    
    # Check that client.order.create was called with correctly converted paise
    mock_client.order.create.assert_called_once_with(data={
        "amount": 89900,
        "currency": "INR",
        "receipt": order.order_id,
        "payment_capture": 1
    })

@patch("app.payment.razorpay.Client")
def test_payment_metadata_persisted(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.order.create.return_value = {"id": "order_rzp_persisted"}
    
    order = setup_order()
    create_payment_order(order.order_id)
    
    conn = get_db_connection()
    row = conn.execute("SELECT payment_provider, razorpay_order_id, payment_status FROM orders WHERE order_id = ?", (order.order_id,)).fetchone()
    conn.close()
    
    assert row["payment_provider"] == "razorpay"
    assert row["razorpay_order_id"] == "order_rzp_persisted"
    assert row["payment_status"] == "PENDING"


@patch("app.payment.razorpay.Client")
def test_duplicate_creation_returns_existing(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.order.create.return_value = {"id": "order_rzp_dup"}
    
    order = setup_order()
    result1 = create_payment_order(order.order_id)
    
    # Second call should not hit Razorpay client
    result2 = create_payment_order(order.order_id)
    
    assert result2["razorpay_order_id"] == "order_rzp_dup"
    assert result2["message"] == "Payment order already exists."
    mock_client.order.create.assert_called_once() # Only called once


@patch("app.payment.razorpay.Client")
def test_provider_network_failure(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_client.order.create.side_effect = Exception("Network timeout")
    
    order = setup_order()
    
    with pytest.raises(PaymentProviderError) as exc_info:
        create_payment_order(order.order_id)
        
    assert "Razorpay API Error" in str(exc_info.value)


@patch("app.payment.settings")
def test_missing_credentials_fails_cleanly(mock_settings):
    mock_settings.razorpay_key_id = None
    mock_settings.razorpay_key_secret = None
    
    order = setup_order()
    
    with pytest.raises(ValueError) as exc_info:
        create_payment_order(order.order_id)
        
    assert "Razorpay credentials are not configured" in str(exc_info.value)

def test_secret_never_returned_or_audited():
    from app.executor import execute_tool
    order = setup_order()
    
    # Use execute_tool directly so it logs to audit
    with patch("app.payment.razorpay.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.order.create.return_value = {"id": "order_rzp_audit"}
        
        # client amount cannot override internal, because we don't pass it
        result = execute_tool("create_payment_order", {"order_id": order.order_id}, actor="buyer_agent")
        
        assert result["success"] is True
        
        # Verify result contains no secrets
        result_str = str(result)
        assert "rzp_test_mock_secret" not in result_str

        # Verify audit contains no secrets
        audit = AuditLogger()
        entry = audit.get_by_action("create_payment_order")[0]
        
        audit_str = str(entry.arguments) + str(entry.result)
        assert "rzp_test_mock_secret" not in audit_str
        assert entry.success is True


def test_failed_payment_is_audited():
    from app.executor import execute_tool
    order = setup_order()
    
    with patch("app.payment.razorpay.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.order.create.side_effect = Exception("API down")
        
        result = execute_tool("create_payment_order", {"order_id": order.order_id}, actor="buyer_agent")
        
        assert result["success"] is False
        
        audit = AuditLogger()
        entry = audit.get_by_action("create_payment_order")[0]
        assert entry.success is False
        assert entry.error_code == "EXECUTION_ERROR"

def test_initiate_payment_success():
    from app.payment import RazorpayPaymentService, PAYMENT_INITIATED
    order = setup_order()
    
    with patch("app.payment.razorpay.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.order.create.return_value = {"id": "order_rzp_initiate"}
        
        service = RazorpayPaymentService()
        service.create_payment_order(order.order_id)
        
        result = service.initiate_checkout_payment(order.order_id)
        
        assert result["razorpay_order_id"] == "order_rzp_initiate"
        assert result["payment_status"] == PAYMENT_INITIATED
        assert result["amount"] == 89900
        assert result["razorpay_key_id"] == "rzp_test_mock_id"
        assert "razorpay_key_secret" not in result
        
        # Verify Audit
        audit = AuditLogger()
        entry = audit.get_by_action("initiate_payment")[0]
        assert entry.success is True
        assert entry.result["payment_status"] == PAYMENT_INITIATED


def test_initiate_payment_invalid_transition():
    from app.payment import RazorpayPaymentService, PaymentStateError
    order = setup_order()
    
    service = RazorpayPaymentService()
    # order is currently NOT_CREATED
    
    with pytest.raises(PaymentStateError) as exc_info:
        service.initiate_checkout_payment(order.order_id)
        
    assert "Invalid state transition" in str(exc_info.value)
    
    # Verify Audit
    audit = AuditLogger()
    entry = audit.get_by_action("initiate_payment")[0]
    assert entry.success is False
    assert entry.error_code == "INVALID_TRANSITION"


def test_ai_cannot_mark_paid():
    # Ensure there is no tool in TOOLS for marking paid
    from app.tools import TOOLS
    for tool_name, tool_def in TOOLS.items():
        assert "paid" not in tool_name.lower()
        # Ensure 'paid', 'payment_status', etc., are not in the tool schemas
        schema_fields = tool_def.input_schema.model_fields.keys()
        assert "paid" not in schema_fields
        assert "payment_status" not in schema_fields


def test_verify_payment_success():
    from app.payment import RazorpayPaymentService, PAYMENT_INITIATED, PAID
    from app.database import update_payment_details
    order = setup_order()
    
    # Mocking order to PAYMENT_INITIATED
    update_payment_details(order.order_id, "razorpay", "order_rzp_mock", PAYMENT_INITIATED)
    
    with patch("app.payment.razorpay.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        # Verification succeeds (does not raise)
        mock_client.utility.verify_payment_signature.return_value = True
        
        service = RazorpayPaymentService()
        result = service.verify_payment_signature(
            razorpay_payment_id="pay_mock_id",
            razorpay_order_id="order_rzp_mock",
            razorpay_signature="mock_signature"
        )
        
        assert result["success"] is True
        assert result["payment_status"] == PAID
        
        audit = AuditLogger()
        entry = audit.get_by_action("verify_payment")[0]
        assert entry.success is True
        assert entry.result["payment_status"] == PAID


def test_verify_payment_invalid_signature():
    from app.payment import RazorpayPaymentService, PAYMENT_INITIATED, PaymentProviderError
    from app.database import update_payment_details
    import razorpay
    
    order = setup_order()
    update_payment_details(order.order_id, "razorpay", "order_rzp_mock", PAYMENT_INITIATED)
    
    with patch("app.payment.razorpay.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.utility.verify_payment_signature.side_effect = razorpay.errors.SignatureVerificationError("Invalid signature")
        
        service = RazorpayPaymentService()
        
        with pytest.raises(PaymentProviderError) as exc_info:
            service.verify_payment_signature(
                razorpay_payment_id="pay_mock_id",
                razorpay_order_id="order_rzp_mock",
                razorpay_signature="invalid_signature"
            )
            
        assert "Signature verification failed" in str(exc_info.value)
        
        audit = AuditLogger()
        entry = audit.get_by_action("verify_payment")[0]
        assert entry.success is False
        assert entry.error_code == "INVALID_SIGNATURE"


def test_verify_payment_wrong_order_id():
    from app.payment import RazorpayPaymentService
    
    service = RazorpayPaymentService()
    
    with pytest.raises(ValueError) as exc_info:
        service.verify_payment_signature(
            razorpay_payment_id="pay_mock_id",
            razorpay_order_id="order_rzp_nonexistent",
            razorpay_signature="mock_signature"
        )
        
    assert "No internal order found" in str(exc_info.value)
    
    audit = AuditLogger()
    entry = audit.get_by_action("verify_payment")[0]
    assert entry.success is False
    assert entry.error_code == "ORDER_NOT_FOUND"


def test_verify_payment_from_pending_rejected():
    from app.payment import RazorpayPaymentService, PENDING, PaymentStateError
    from app.database import update_payment_details
    order = setup_order()
    
    # State is PENDING (not PAYMENT_INITIATED)
    update_payment_details(order.order_id, "razorpay", "order_rzp_mock", PENDING)
    
    service = RazorpayPaymentService()
    
    with pytest.raises(PaymentStateError) as exc_info:
        service.verify_payment_signature(
            razorpay_payment_id="pay_mock_id",
            razorpay_order_id="order_rzp_mock",
            razorpay_signature="mock_signature"
        )
        
    assert "Cannot verify payment from state PENDING" in str(exc_info.value)
    
    audit = AuditLogger()
    entry = audit.get_by_action("verify_payment")[0]
    assert entry.success is False
    assert entry.error_code == "INVALID_STATE"


def test_verify_payment_replay_attempt():
    from app.payment import RazorpayPaymentService, PAID, PaymentStateError
    from app.database import update_payment_details
    order = setup_order()
    
    # State is already PAID
    update_payment_details(order.order_id, "razorpay", "order_rzp_mock", PAID)
    
    service = RazorpayPaymentService()
    
    with pytest.raises(PaymentStateError) as exc_info:
        service.verify_payment_signature(
            razorpay_payment_id="pay_mock_id",
            razorpay_order_id="order_rzp_mock",
            razorpay_signature="mock_signature"
        )
        
    assert "Payment already verified" in str(exc_info.value)
    
    audit = AuditLogger()
    entry = audit.get_by_action("verify_payment")[0]
    assert entry.success is False
    assert entry.error_code == "REPLAY_ATTEMPT"

