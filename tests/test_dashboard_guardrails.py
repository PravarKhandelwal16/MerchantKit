"""
Tests for read-only dashboard guardrails and policy endpoints:
- GET /dashboard/guardrails
- GET /dashboard/tools
- GET /dashboard/audit (with arguments and result/details)
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, get_db_connection
from app.audit import AuditLogger, REJECTED

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    conn = get_db_connection()
    conn.execute("DELETE FROM audit_logs")
    conn.commit()
    conn.close()
    yield


def test_dashboard_get_guardrails():
    res = client.get("/dashboard/guardrails")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    policy = data["data"]
    assert "max_order_value" in policy
    assert "max_item_quantity" in policy
    assert "allowed_categories" in policy
    assert "require_payment_confirmation" in policy
    assert isinstance(policy["allowed_categories"], list)
    assert policy["max_order_value"] > 0


def test_dashboard_get_tools():
    res = client.get("/dashboard/tools")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    tools = data["data"]
    assert len(tools) >= 5
    tool_names = [t["name"] for t in tools]
    assert "search_products" in tool_names
    assert "get_product" in tool_names
    assert "create_cart" in tool_names
    assert "add_to_cart" in tool_names
    assert "create_order" in tool_names
    assert "create_payment_order" in tool_names
    for t in tools:
        assert "name" in t
        assert "description" in t
        assert len(t["description"]) > 0


def test_dashboard_get_audit_includes_arguments_and_result():
    logger = AuditLogger()
    logger.log_guardrail(
        actor="buyer_agent",
        action="create_order",
        policy_decision=REJECTED,
        reason="Order total ₹6000.00 exceeds the maximum allowed ₹5000.00 per transaction.",
        arguments={"cart_id": "cart-audit-test"},
        details={"total_amount": 6000.0, "max_order_value": 5000.0},
    )

    res = client.get("/dashboard/audit")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    entry = data["data"][0]
    assert entry["action"] == "create_order"
    assert entry["policy_decision"] == REJECTED
    assert entry["arguments"] == {"cart_id": "cart-audit-test"}
    assert entry["result"] == {"total_amount": 6000.0, "max_order_value": 5000.0}
