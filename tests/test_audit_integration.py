"""
Tests for Part 6D: Audit Integration.

These tests verify that the audit trail is written correctly for every
tool call that flows through the gateway — success, failure, guardrail
approval, and guardrail rejection.

No real LLM is used. Qwen is stubbed so tests are fast and deterministic.
The real executor, guardrails, cart, and order services run against the
test SQLite database.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from app.database import init_db, insert_product, get_db_connection
from app.schemas import Product
from app.cart import create_cart, add_to_cart
from app.audit import AuditLogger, APPROVED, REJECTED, NA
from app.executor import execute_tool


# ---------------------------------------------------------------------------
# DB and audit fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    conn = get_db_connection()
    for table in ("order_items", "orders", "cart_items", "carts", "products", "audit_logs"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()
    yield


@pytest.fixture
def audit() -> AuditLogger:
    return AuditLogger()


# ---------------------------------------------------------------------------
# Shared product helpers
# ---------------------------------------------------------------------------

def _mouse(product_id: str = "M001", price: float = 999.0, stock: int = 10) -> str:
    insert_product(Product(
        product_id=product_id, name="Test Mouse", price=price,
        category="mouse", stock=stock,
    ))
    return product_id


def _expensive_mouse(product_id: str = "MBIG", price: float = 6000.0, stock: int = 5) -> str:
    """A mouse-category product whose price alone exceeds the ₹5000 order limit."""
    insert_product(Product(
        product_id=product_id, name="Expensive Mouse", price=price,
        category="mouse", stock=stock,
    ))
    return product_id


# ---------------------------------------------------------------------------
# 1. Successful tool call creates an audit record
# ---------------------------------------------------------------------------

class TestSuccessfulToolAudit:
    def test_search_products_is_audited(self, audit):
        _mouse()
        execute_tool("search_products", {"query": "mouse"}, actor="buyer_agent")
        entries = audit.get_by_action("search_products")
        assert len(entries) == 1
        assert entries[0].actor == "buyer_agent"
        assert entries[0].success is True

    def test_get_product_is_audited(self, audit):
        _mouse()
        execute_tool("get_product", {"product_id": "M001"}, actor="buyer_agent")
        entries = audit.get_by_action("get_product")
        assert len(entries) == 1
        assert entries[0].success is True

    def test_create_cart_is_audited(self, audit):
        execute_tool("create_cart", {}, actor="buyer_agent")
        entries = audit.get_by_action("create_cart")
        assert len(entries) == 1
        assert entries[0].actor == "buyer_agent"

    def test_add_to_cart_is_audited(self, audit):
        _mouse()
        cart = create_cart()
        execute_tool(
            "add_to_cart",
            {"cart_id": cart.cart_id, "product_id": "M001", "quantity": 1},
            actor="buyer_agent",
        )
        entries = audit.get_by_action("add_to_cart")
        assert len(entries) == 1
        assert entries[0].success is True

    def test_audit_record_has_timestamp(self, audit):
        execute_tool("create_cart", {}, actor="buyer_agent")
        entry = audit.get_recent(limit=1)[0]
        assert entry.timestamp is not None

    def test_audit_record_has_arguments(self, audit):
        _mouse()
        execute_tool("search_products", {"query": "wireless mouse"}, actor="buyer_agent")
        entry = audit.get_by_action("search_products")[0]
        # Logged arguments are the validated kwargs (Pydantic model_dump) which
        # include optional fields like category=None alongside the caller's input.
        assert entry.arguments["query"] == "wireless mouse"

    def test_audit_actor_is_recorded(self, audit):
        execute_tool("create_cart", {}, actor="buyer_agent")
        entry = audit.get_recent(limit=1)[0]
        assert entry.actor == "buyer_agent"

    def test_audit_result_is_structured(self, audit):
        _mouse()
        cart = create_cart()
        execute_tool(
            "add_to_cart",
            {"cart_id": cart.cart_id, "product_id": "M001", "quantity": 1},
            actor="buyer_agent",
        )
        entry = audit.get_by_action("add_to_cart")[0]
        # Result is deserialised JSON — should be a dict (cart dump)
        assert isinstance(entry.result, dict)


# ---------------------------------------------------------------------------
# 2. Failed tool call creates an audit record
# ---------------------------------------------------------------------------

class TestFailedToolAudit:
    def test_nonexistent_cart_is_audited(self, audit):
        _mouse()
        execute_tool(
            "add_to_cart",
            {"cart_id": "ghost-cart", "product_id": "M001", "quantity": 1},
            actor="buyer_agent",
        )
        entries = audit.get_by_action("add_to_cart")
        assert len(entries) == 1
        assert entries[0].success is False
        assert entries[0].error_code == "EXECUTION_ERROR"

    def test_failed_record_has_reason(self, audit):
        _mouse()
        execute_tool(
            "add_to_cart",
            {"cart_id": "ghost", "product_id": "M001", "quantity": 1},
            actor="buyer_agent",
        )
        entry = audit.get_by_action("add_to_cart")[0]
        assert entry.reason is not None
        assert "ghost" in entry.reason.lower() or "not found" in entry.reason.lower()

    def test_failed_record_has_correct_actor(self, audit):
        execute_tool("get_cart", {"cart_id": "bad"}, actor="buyer_agent")
        entry = audit.get_by_action("get_cart")[0]
        assert entry.actor == "buyer_agent"


# ---------------------------------------------------------------------------
# 3. Guardrail approval audit
# ---------------------------------------------------------------------------

class TestGuardrailApprovalAudit:
    def test_successful_order_creates_approved_audit(self, audit):
        _mouse(price=999.0)
        cart = create_cart()
        add_to_cart(cart.cart_id, "M001", 1)
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")
        entries = audit.get_by_action("create_order")
        assert len(entries) == 1
        assert entries[0].success is True
        assert entries[0].policy_decision == APPROVED

    def test_approved_order_audit_has_cart_id_in_arguments(self, audit):
        _mouse(price=999.0)
        cart = create_cart()
        add_to_cart(cart.cart_id, "M001", 1)
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")
        entry = audit.get_by_action("create_order")[0]
        assert entry.arguments["cart_id"] == cart.cart_id

    def test_approved_order_audit_has_result_with_amount(self, audit):
        _mouse(price=999.0)
        cart = create_cart()
        add_to_cart(cart.cart_id, "M001", 1)
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")
        entry = audit.get_by_action("create_order")[0]
        # Result should include total_amount from the Order model dump
        assert entry.result is not None
        assert entry.result.get("total_amount") == 999.0

    def test_approved_order_audit_no_error_code(self, audit):
        _mouse(price=999.0)
        cart = create_cart()
        add_to_cart(cart.cart_id, "M001", 1)
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")
        entry = audit.get_by_action("create_order")[0]
        assert entry.error_code is None


# ---------------------------------------------------------------------------
# 4. Guardrail rejection audit — ₹5000 limit
# ---------------------------------------------------------------------------

class TestGuardrailRejectionAudit:
    def test_order_above_5000_is_rejected_and_audited(self, audit):
        """Core scenario: ₹6000 order exceeds limit; rejection must appear in audit."""
        _expensive_mouse(price=6000.0)
        cart = create_cart()
        add_to_cart(cart.cart_id, "MBIG", 1)
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")

        entries = audit.get_by_action("create_order")
        assert len(entries) == 1
        assert entries[0].success is False
        assert entries[0].policy_decision == REJECTED

    def test_rejected_order_audit_has_guardrail_violation_code(self, audit):
        _expensive_mouse()
        cart = create_cart()
        add_to_cart(cart.cart_id, "MBIG", 1)
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")

        entry = audit.get_by_action("create_order")[0]
        assert entry.error_code == "GUARDRAIL_VIOLATION"

    def test_rejected_audit_record_has_reason(self, audit):
        _expensive_mouse()
        cart = create_cart()
        add_to_cart(cart.cart_id, "MBIG", 1)
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")

        entry = audit.get_by_action("create_order")[0]
        assert entry.reason is not None
        assert "5000" in entry.reason or "exceed" in entry.reason.lower()

    def test_rejected_audit_has_details_with_amounts(self, audit):
        _expensive_mouse(price=6000.0)
        cart = create_cart()
        add_to_cart(cart.cart_id, "MBIG", 1)
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")

        entry = audit.get_by_action("create_order")[0]
        # Details stored in result field by log_guardrail
        assert entry.result is not None
        assert entry.result.get("total_amount") == 6000.0
        assert entry.result.get("max_order_value") == 5000.0

    def test_rejected_audit_has_cart_id_in_arguments(self, audit):
        _expensive_mouse()
        cart = create_cart()
        add_to_cart(cart.cart_id, "MBIG", 1)
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")

        entry = audit.get_by_action("create_order")[0]
        assert entry.arguments["cart_id"] == cart.cart_id

    def test_category_violation_is_audited_as_rejected(self, audit):
        """Disallowed category also produces a REJECTED audit record."""
        insert_product(Product(
            product_id="LAPTOP1", name="Gaming Laptop", price=50.0,
            category="laptop", stock=5,
        ))
        cart = create_cart()
        add_to_cart(cart.cart_id, "LAPTOP1", 1)
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")

        entry = audit.get_by_action("create_order")[0]
        assert entry.success is False
        assert entry.policy_decision == REJECTED

    def test_quantity_violation_is_audited_as_rejected(self, audit):
        """Excessive quantity also produces a REJECTED audit record."""
        insert_product(Product(
            product_id="M_QTY", name="Cheap Mouse", price=10.0,
            category="mouse", stock=50,
        ))
        cart = create_cart()
        add_to_cart(cart.cart_id, "M_QTY", 3)  # at limit
        # Directly add 1 more bypassing add_to_cart guardrail to get qty=4 in DB
        conn = get_db_connection()
        conn.execute(
            "UPDATE cart_items SET quantity = 4 WHERE cart_id = ? AND product_id = ?",
            (cart.cart_id, "M_QTY"),
        )
        conn.commit()
        conn.close()
        execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")

        entry = audit.get_by_action("create_order")[0]
        assert entry.success is False
        assert entry.policy_decision == REJECTED


# ---------------------------------------------------------------------------
# 5. Full multi-step flow audit (agent-like sequence)
# ---------------------------------------------------------------------------

class TestMultiStepFlowAudit:
    def test_full_shopping_flow_creates_multiple_audit_records(self, audit):
        """
        Simulate the buyer agent's typical flow:
        search → get_product → create_cart → add_to_cart → create_order
        All steps must be audited.
        """
        _mouse(price=1000.0)

        execute_tool("search_products", {"query": "mouse"}, actor="buyer_agent")
        execute_tool("get_product", {"product_id": "M001"}, actor="buyer_agent")
        cart_res = execute_tool("create_cart", {}, actor="buyer_agent")
        cart_id = cart_res["data"].cart_id
        execute_tool(
            "add_to_cart",
            {"cart_id": cart_id, "product_id": "M001", "quantity": 1},
            actor="buyer_agent",
        )
        execute_tool("create_order", {"cart_id": cart_id}, actor="buyer_agent")

        all_entries = audit.get_recent(limit=20)
        actions = [e.action for e in all_entries]

        assert "search_products" in actions
        assert "get_product" in actions
        assert "create_cart" in actions
        assert "add_to_cart" in actions
        assert "create_order" in actions

    def test_all_audit_records_have_buyer_agent_actor(self, audit):
        _mouse(price=500.0)
        execute_tool("create_cart", {}, actor="buyer_agent")
        execute_tool("search_products", {"query": "mouse"}, actor="buyer_agent")

        entries = audit.get_recent(limit=10)
        for e in entries:
            assert e.actor == "buyer_agent"

    def test_audit_records_are_in_chronological_order(self, audit):
        _mouse()
        execute_tool("search_products", {"query": "mouse"}, actor="buyer_agent")
        execute_tool("create_cart", {}, actor="buyer_agent")

        entries = audit.get_recent(limit=10)
        # get_recent returns newest-first; ids must be decreasing
        ids = [e.id for e in entries]
        assert ids == sorted(ids, reverse=True)

    def test_successful_and_rejected_in_same_session(self, audit):
        """
        Happy order followed by an over-limit order — both audited correctly.
        """
        _mouse(product_id="M001", price=999.0)
        _expensive_mouse(product_id="MBIG", price=6000.0)

        # Successful order
        cart1 = create_cart()
        add_to_cart(cart1.cart_id, "M001", 1)
        execute_tool("create_order", {"cart_id": cart1.cart_id}, actor="buyer_agent")

        # Rejected order
        cart2 = create_cart()
        add_to_cart(cart2.cart_id, "MBIG", 1)
        execute_tool("create_order", {"cart_id": cart2.cart_id}, actor="buyer_agent")

        order_entries = audit.get_by_action("create_order")
        assert len(order_entries) == 2

        decisions = {e.policy_decision for e in order_entries}
        assert APPROVED in decisions
        assert REJECTED in decisions


# ---------------------------------------------------------------------------
# 6. Audit does not bypass guardrails or affect tool responses
# ---------------------------------------------------------------------------

class TestAuditDoesNotAffectBehavior:
    def test_guardrail_still_blocks_after_audit(self, audit):
        """A logged guardrail rejection must also return the correct error response."""
        _expensive_mouse(price=6000.0)
        cart = create_cart()
        add_to_cart(cart.cart_id, "MBIG", 1)
        res = execute_tool("create_order", {"cart_id": cart.cart_id}, actor="buyer_agent")

        assert res["success"] is False
        assert res["error"]["code"] == "GUARDRAIL_VIOLATION"

    def test_successful_tool_response_unchanged(self, audit):
        """Audit integration must not change the return value of successful tools."""
        res = execute_tool("create_cart", {}, actor="buyer_agent")
        assert res["success"] is True
        assert "data" in res
        assert res["data"].cart_id is not None

    def test_default_actor_is_api_for_direct_calls(self, audit):
        """Calls without actor= default to 'api' (not 'buyer_agent')."""
        execute_tool("create_cart", {})
        entry = audit.get_recent(limit=1)[0]
        assert entry.actor == "api"


# ---------------------------------------------------------------------------
# 7. Secrets never appear in audit log
# ---------------------------------------------------------------------------

class TestSecretsNotInAuditLog:
    def test_api_key_in_search_never_logged(self, audit):
        """
        Extra keys not in the tool schema are stripped by Pydantic validation
        before execution — they never reach the audit write at all.
        Secret fields that *do* reach the logger are redacted by _redact().
        Either way no secret value is stored.
        """
        _mouse()
        execute_tool(
            "search_products",
            {"query": "mouse", "api_key": "sk-super-secret"},
            actor="buyer_agent",
        )
        entry = audit.get_by_action("search_products")[0]
        # Pydantic strips unknown keys — api_key simply absent (not stored at all)
        logged_args_str = str(entry.arguments)
        assert "sk-super-secret" not in logged_args_str
        # The legitimate query field is still present
        assert entry.arguments["query"] == "mouse"
