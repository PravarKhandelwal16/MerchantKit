"""
Tests for Part 6C: Audit Logger.

All tests use the real SQLite DB (same test-db pattern as other test modules).
No mocking is needed because the logger is a simple append-to-DB service.
"""
import json
import pytest
from app.database import init_db, get_db_connection
from app.audit import (
    AuditLogger,
    AuditEntry,
    APPROVED,
    REJECTED,
    NA,
    _redact,
    _to_json,
    audit_logger,
)


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_db():
    """Ensure audit_logs is created and clean for each test."""
    init_db()
    conn = get_db_connection()
    conn.execute("DELETE FROM audit_logs")
    conn.commit()
    conn.close()
    yield


@pytest.fixture
def logger() -> AuditLogger:
    """Fresh AuditLogger instance (stateless — shares the same DB)."""
    return AuditLogger()


# ---------------------------------------------------------------------------
# 1. Successful tool call logging
# ---------------------------------------------------------------------------

class TestSuccessfulToolCallLogging:
    def test_log_successful_tool_call_returns_id(self, logger):
        row_id = logger.log_tool_call(
            actor="agent",
            action="search_products",
            arguments={"query": "mouse"},
            result=[{"product_id": "M001", "name": "Logitech M331"}],
            success=True,
        )
        assert isinstance(row_id, int)
        assert row_id > 0

    def test_successful_entry_is_retrievable(self, logger):
        logger.log_tool_call(
            actor="agent",
            action="add_to_cart",
            arguments={"cart_id": "abc", "product_id": "M001", "quantity": 1},
            result={"cart_id": "abc", "subtotal": 1299.0},
            success=True,
        )
        entries = logger.get_recent(limit=1)
        assert len(entries) == 1
        assert entries[0].action == "add_to_cart"
        assert entries[0].success is True

    def test_successful_entry_has_no_error_code(self, logger):
        logger.log_tool_call(
            actor="api",
            action="get_cart",
            arguments={"cart_id": "xyz"},
            result={"cart_id": "xyz"},
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.error_code is None

    def test_successful_entry_policy_decision_defaults_to_na(self, logger):
        logger.log_tool_call(
            actor="api",
            action="get_product",
            arguments={"product_id": "M001"},
            result={"name": "Logitech M331"},
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.policy_decision == NA

    def test_actor_field_is_stored(self, logger):
        logger.log_tool_call(
            actor="buyer_agent",
            action="create_cart",
            arguments={},
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.actor == "buyer_agent"


# ---------------------------------------------------------------------------
# 2. Failed tool call logging
# ---------------------------------------------------------------------------

class TestFailedToolCallLogging:
    def test_log_failed_tool_call(self, logger):
        logger.log_tool_call(
            actor="agent",
            action="add_to_cart",
            arguments={"cart_id": "bad-id", "product_id": "M001", "quantity": 1},
            result=None,
            success=False,
            error_code="EXECUTION_ERROR",
            reason="Cart 'bad-id' not found",
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.success is False
        assert entry.error_code == "EXECUTION_ERROR"
        assert entry.reason == "Cart 'bad-id' not found"

    def test_failed_entry_has_action_name(self, logger):
        logger.log_tool_call(
            actor="api",
            action="create_order",
            arguments={"cart_id": "x"},
            success=False,
            error_code="GUARDRAIL_VIOLATION",
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.action == "create_order"

    def test_failed_entry_result_is_none(self, logger):
        logger.log_tool_call(
            actor="agent",
            action="get_order",
            arguments={"order_id": "nonexistent"},
            result=None,
            success=False,
            error_code="EXECUTION_ERROR",
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.result is None


# ---------------------------------------------------------------------------
# 3. Guardrail decision logging
# ---------------------------------------------------------------------------

class TestGuardrailLogging:
    def test_log_guardrail_approved(self, logger):
        row_id = logger.log_guardrail(
            actor="gateway",
            action="create_order",
            policy_decision=APPROVED,
            reason="Order total ₹1299 is within the ₹5000 limit.",
            arguments={"cart_id": "cart-123"},
            details={"total_amount": 1299.0, "max_order_value": 5000.0},
        )
        assert row_id > 0

    def test_guardrail_approved_entry_is_success(self, logger):
        logger.log_guardrail(
            actor="gateway",
            action="create_order",
            policy_decision=APPROVED,
            reason="All checks passed.",
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.success is True
        assert entry.policy_decision == APPROVED

    def test_log_guardrail_rejected(self, logger):
        logger.log_guardrail(
            actor="gateway",
            action="create_order",
            policy_decision=REJECTED,
            reason="Order total ₹6000 exceeds the ₹5000 limit.",
            details={"total_amount": 6000.0, "max_order_value": 5000.0},
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.success is False
        assert entry.policy_decision == REJECTED

    def test_guardrail_rejected_has_error_code(self, logger):
        logger.log_guardrail(
            actor="gateway",
            action="create_order",
            policy_decision=REJECTED,
            reason="Quantity exceeded.",
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.error_code == "GUARDRAIL_VIOLATION"

    def test_guardrail_approved_has_no_error_code(self, logger):
        logger.log_guardrail(
            actor="gateway",
            action="add_to_cart",
            policy_decision=APPROVED,
            reason="Quantity within limit.",
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.error_code is None

    def test_guardrail_details_stored_as_structured_data(self, logger):
        details = {"total_amount": 1299.0, "max_order_value": 5000.0}
        logger.log_guardrail(
            actor="gateway",
            action="create_order",
            policy_decision=APPROVED,
            reason="Within limit.",
            details=details,
        )
        entry = logger.get_recent(limit=1)[0]
        assert isinstance(entry.result, dict)
        assert entry.result["total_amount"] == 1299.0

    def test_guardrail_reason_stored(self, logger):
        logger.log_guardrail(
            actor="gateway",
            action="create_order",
            policy_decision=REJECTED,
            reason="Category 'laptop' is not allowed.",
        )
        entry = logger.get_recent(limit=1)[0]
        assert "laptop" in entry.reason


# ---------------------------------------------------------------------------
# 4. Structured arguments and results
# ---------------------------------------------------------------------------

class TestStructuredStorage:
    def test_arguments_are_parsed_back_to_dict(self, logger):
        args = {"cart_id": "abc", "product_id": "M001", "quantity": 2}
        logger.log_tool_call(
            actor="agent",
            action="add_to_cart",
            arguments=args,
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.arguments == args

    def test_list_result_is_parsed_back(self, logger):
        result = [{"product_id": "M001"}, {"product_id": "M004"}]
        logger.log_tool_call(
            actor="agent",
            action="search_products",
            arguments={"query": "mouse"},
            result=result,
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        assert isinstance(entry.result, list)
        assert len(entry.result) == 2

    def test_nested_dict_stored_and_retrieved(self, logger):
        result = {"cart": {"cart_id": "abc", "items": [{"qty": 1}]}}
        logger.log_tool_call(
            actor="api",
            action="get_cart",
            arguments={"cart_id": "abc"},
            result=result,
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.result["cart"]["cart_id"] == "abc"

    def test_none_arguments_stored_as_null(self, logger):
        logger.log_tool_call(
            actor="agent",
            action="create_cart",
            arguments=None,
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.arguments is None


# ---------------------------------------------------------------------------
# 5. Timestamp presence
# ---------------------------------------------------------------------------

class TestTimestamp:
    def test_timestamp_is_present(self, logger):
        logger.log_tool_call(
            actor="agent",
            action="search_products",
            arguments={"query": "keyboard"},
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.timestamp is not None
        assert len(entry.timestamp) > 0

    def test_timestamp_is_iso_format(self, logger):
        """Timestamps must be parseable ISO-8601 strings."""
        from datetime import datetime
        logger.log_tool_call(
            actor="agent",
            action="get_product",
            arguments={"product_id": "M001"},
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        parsed = datetime.fromisoformat(entry.timestamp)
        assert parsed is not None

    def test_timestamps_are_utc(self, logger):
        logger.log_tool_call(
            actor="agent",
            action="get_product",
            arguments={"product_id": "M001"},
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        # UTC ISO timestamps contain '+00:00' or 'Z' or end with timezone info
        assert "+" in entry.timestamp or entry.timestamp.endswith("Z")


# ---------------------------------------------------------------------------
# 6. Retrieval
# ---------------------------------------------------------------------------

class TestRetrieval:
    def test_get_recent_returns_list(self, logger):
        entries = logger.get_recent()
        assert isinstance(entries, list)

    def test_get_recent_empty_when_no_records(self, logger):
        assert logger.get_recent() == []

    def test_get_recent_returns_newest_first(self, logger):
        for action in ["first", "second", "third"]:
            logger.log_tool_call(actor="agent", action=action, arguments={}, success=True)
        entries = logger.get_recent(limit=3)
        assert entries[0].action == "third"
        assert entries[2].action == "first"

    def test_get_recent_respects_limit(self, logger):
        for _ in range(10):
            logger.log_tool_call(actor="agent", action="ping", arguments={}, success=True)
        entries = logger.get_recent(limit=3)
        assert len(entries) == 3

    def test_get_recent_returns_all_when_fewer_than_limit(self, logger):
        for _ in range(5):
            logger.log_tool_call(actor="agent", action="ping", arguments={}, success=True)
        entries = logger.get_recent(limit=100)
        assert len(entries) == 5

    def test_get_by_action_filters_correctly(self, logger):
        logger.log_tool_call(actor="agent", action="search_products", arguments={}, success=True)
        logger.log_tool_call(actor="agent", action="create_cart", arguments={}, success=True)
        logger.log_tool_call(actor="agent", action="search_products", arguments={}, success=True)
        entries = logger.get_by_action("search_products")
        assert len(entries) == 2
        assert all(e.action == "search_products" for e in entries)

    def test_entries_have_unique_incrementing_ids(self, logger):
        for _ in range(3):
            logger.log_tool_call(actor="agent", action="ping", arguments={}, success=True)
        entries = logger.get_recent(limit=3)
        ids = [e.id for e in entries]
        assert len(set(ids)) == 3        # all unique
        assert ids == sorted(ids, reverse=True)  # newest first = highest id first

    def test_audit_entries_are_never_modified(self, logger):
        """Append-only check: write once, verify the original record is intact."""
        row_id = logger.log_tool_call(
            actor="agent",
            action="create_order",
            arguments={"cart_id": "abc"},
            success=True,
            reason="Initial log.",
        )
        # Simulate a second, separate log entry (a new append, NOT an update)
        logger.log_tool_call(
            actor="agent",
            action="create_order",
            arguments={"cart_id": "abc"},
            success=False,
            error_code="GUARDRAIL_VIOLATION",
            reason="Rejected on retry.",
        )
        # Retrieve original record by id directly
        conn = get_db_connection()
        row = conn.execute(
            "SELECT reason FROM audit_logs WHERE id = ?", (row_id,)
        ).fetchone()
        conn.close()
        assert row["reason"] == "Initial log."   # original is unchanged


# ---------------------------------------------------------------------------
# 7. Secret redaction
# ---------------------------------------------------------------------------

class TestSecretRedaction:
    def test_api_key_is_redacted(self):
        result = _redact({"api_key": "sk-super-secret", "query": "mouse"})
        assert result["api_key"] == "[REDACTED]"
        assert result["query"] == "mouse"

    def test_password_is_redacted(self):
        result = _redact({"password": "hunter2", "name": "Alice"})
        assert result["password"] == "[REDACTED]"

    def test_nested_secret_is_redacted(self):
        result = _redact({"user": {"token": "abc123", "id": 42}})
        assert result["user"]["token"] == "[REDACTED]"
        assert result["user"]["id"] == 42

    def test_list_of_dicts_redacted(self):
        result = _redact([{"secret": "s1"}, {"name": "ok"}])
        assert result[0]["secret"] == "[REDACTED]"
        assert result[1]["name"] == "ok"

    def test_razorpay_key_redacted(self):
        result = _redact({"razorpay_key": "rzp_test_xxx", "amount": 1299})
        assert result["razorpay_key"] == "[REDACTED]"
        assert result["amount"] == 1299

    def test_non_secret_fields_not_redacted(self):
        result = _redact({"product_id": "M001", "price": 1299.0, "quantity": 2})
        assert result["product_id"] == "M001"
        assert result["price"] == 1299.0

    def test_secrets_not_persisted_in_db(self, logger):
        """End-to-end: secrets passed in arguments must not survive to storage."""
        logger.log_tool_call(
            actor="test",
            action="hypothetical_payment",
            arguments={
                "cart_id": "abc",
                "api_key": "rzp_test_super_secret",
                "amount": 1299,
            },
            success=True,
        )
        entry = logger.get_recent(limit=1)[0]
        assert entry.arguments["api_key"] == "[REDACTED]"
        assert entry.arguments["amount"] == 1299

    def test_module_level_instance_works(self):
        """The module-level audit_logger singleton is usable."""
        assert isinstance(audit_logger, AuditLogger)


# ---------------------------------------------------------------------------
# 8. AuditEntry dataclass structure
# ---------------------------------------------------------------------------

class TestAuditEntryStructure:
    def test_entry_has_all_required_fields(self, logger):
        logger.log_tool_call(
            actor="agent",
            action="test_action",
            arguments={"k": "v"},
            result={"out": 1},
            success=True,
            error_code=None,
            policy_decision=APPROVED,
            reason="All good.",
        )
        entry = logger.get_recent(limit=1)[0]
        assert isinstance(entry, AuditEntry)
        for attr in ("id", "timestamp", "actor", "action", "arguments",
                     "result", "policy_decision", "reason", "success", "error_code"):
            assert hasattr(entry, attr)

    def test_success_field_is_bool(self, logger):
        logger.log_tool_call(actor="a", action="b", arguments={}, success=True)
        entry = logger.get_recent(limit=1)[0]
        assert isinstance(entry.success, bool)
