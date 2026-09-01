"""
Tests for Part 6A: Guardrail Policy Engine.

All checks are deterministic — no database, no LLM, no network.
The tests verify exact policy boundaries using controlled GuardrailPolicy
instances so environment variables never affect test outcomes.
"""
import pytest
from app.guardrails import (
    GuardrailPolicy,
    GuardrailResult,
    check_order_value,
    check_item_quantity,
    check_product_category,
    check_payment_confirmation,
    default_policy,
)


# ---------------------------------------------------------------------------
# Shared policy fixture — fixed values regardless of env vars
# ---------------------------------------------------------------------------

@pytest.fixture
def policy() -> GuardrailPolicy:
    """A fixed policy instance with canonical Part-6 values."""
    return GuardrailPolicy(
        max_order_value=5000.0,
        max_quantity_per_item=3,
        require_payment_confirmation=True,
        allowed_categories=["mouse", "keyboard", "headset"],
    )


# ---------------------------------------------------------------------------
# 1. GuardrailPolicy model
# ---------------------------------------------------------------------------

class TestGuardrailPolicy:
    def test_default_policy_values(self):
        """Module-level default policy must have the required canonical values."""
        assert default_policy.max_order_value == 5000.0
        assert default_policy.max_quantity_per_item == 3
        assert default_policy.require_payment_confirmation is True
        assert "mouse" in default_policy.allowed_categories
        assert "keyboard" in default_policy.allowed_categories
        assert "headset" in default_policy.allowed_categories

    def test_custom_policy_construction(self, policy):
        assert policy.max_order_value == 5000.0
        assert policy.max_quantity_per_item == 3

    def test_policy_is_pydantic_model(self, policy):
        assert isinstance(policy, GuardrailPolicy)

    def test_policy_serialisable(self, policy):
        d = policy.model_dump()
        assert "max_order_value" in d
        assert "allowed_categories" in d


# ---------------------------------------------------------------------------
# 2. GuardrailResult structure
# ---------------------------------------------------------------------------

class TestGuardrailResult:
    def test_result_has_required_fields(self):
        r = GuardrailResult(allowed=True, code="ALLOWED", reason="OK")
        assert hasattr(r, "allowed")
        assert hasattr(r, "code")
        assert hasattr(r, "reason")
        assert hasattr(r, "details")

    def test_details_defaults_to_empty_dict(self):
        r = GuardrailResult(allowed=False, code="REJECTED", reason="No")
        assert r.details == {}

    def test_details_can_carry_metadata(self):
        r = GuardrailResult(allowed=False, code="X", reason="Y", details={"k": 1})
        assert r.details["k"] == 1


# ---------------------------------------------------------------------------
# 3. check_order_value
# ---------------------------------------------------------------------------

class TestCheckOrderValue:
    def test_order_under_limit_is_allowed(self, policy):
        result = check_order_value(4999.0, policy)
        assert result.allowed is True
        assert result.code == "ALLOWED"

    def test_order_exactly_at_limit_is_allowed(self, policy):
        """Boundary: exactly ₹5000 must be allowed."""
        result = check_order_value(5000.0, policy)
        assert result.allowed is True
        assert result.code == "ALLOWED"

    def test_order_above_limit_is_rejected(self, policy):
        result = check_order_value(5000.01, policy)
        assert result.allowed is False
        assert result.code == "ORDER_VALUE_EXCEEDED"

    def test_order_well_above_limit_is_rejected(self, policy):
        result = check_order_value(9999.0, policy)
        assert result.allowed is False
        assert result.code == "ORDER_VALUE_EXCEEDED"

    def test_rejection_reason_mentions_limit(self, policy):
        result = check_order_value(6000.0, policy)
        assert "5000" in result.reason

    def test_details_contain_amounts(self, policy):
        result = check_order_value(1234.0, policy)
        assert result.details["total_amount"] == 1234.0
        assert result.details["max_order_value"] == 5000.0

    def test_uses_default_policy_when_none_given(self):
        """Calling without a policy argument must not raise."""
        result = check_order_value(1000.0)
        assert isinstance(result, GuardrailResult)

    def test_zero_order_value_is_allowed(self, policy):
        """Edge: ₹0 total (empty cart edge case) is within limit."""
        result = check_order_value(0.0, policy)
        assert result.allowed is True

    def test_custom_limit_respected(self):
        strict = GuardrailPolicy(
            max_order_value=1000.0,
            max_quantity_per_item=3,
            require_payment_confirmation=True,
            allowed_categories=["mouse"],
        )
        assert check_order_value(1000.0, strict).allowed is True
        assert check_order_value(1000.01, strict).allowed is False


# ---------------------------------------------------------------------------
# 4. check_item_quantity
# ---------------------------------------------------------------------------

class TestCheckItemQuantity:
    def test_quantity_within_limit_is_allowed(self, policy):
        result = check_item_quantity(1, policy)
        assert result.allowed is True
        assert result.code == "ALLOWED"

    def test_quantity_exactly_at_limit_is_allowed(self, policy):
        """Boundary: exactly max_quantity_per_item must be allowed."""
        result = check_item_quantity(3, policy)
        assert result.allowed is True

    def test_quantity_above_limit_is_rejected(self, policy):
        result = check_item_quantity(4, policy)
        assert result.allowed is False
        assert result.code == "QUANTITY_EXCEEDED"

    def test_quantity_well_above_limit_is_rejected(self, policy):
        result = check_item_quantity(100, policy)
        assert result.allowed is False

    def test_rejection_reason_mentions_limit(self, policy):
        result = check_item_quantity(10, policy)
        assert "3" in result.reason

    def test_details_contain_quantity_info(self, policy):
        result = check_item_quantity(2, policy)
        assert result.details["quantity"] == 2
        assert result.details["max_quantity_per_item"] == 3

    def test_uses_default_policy_when_none_given(self):
        result = check_item_quantity(1)
        assert isinstance(result, GuardrailResult)

    def test_custom_limit_respected(self):
        strict = GuardrailPolicy(
            max_order_value=5000.0,
            max_quantity_per_item=1,
            require_payment_confirmation=True,
            allowed_categories=["mouse"],
        )
        assert check_item_quantity(1, strict).allowed is True
        assert check_item_quantity(2, strict).allowed is False


# ---------------------------------------------------------------------------
# 5. check_product_category
# ---------------------------------------------------------------------------

class TestCheckProductCategory:
    def test_allowed_category_mouse(self, policy):
        result = check_product_category("mouse", policy)
        assert result.allowed is True
        assert result.code == "ALLOWED"

    def test_allowed_category_keyboard(self, policy):
        result = check_product_category("keyboard", policy)
        assert result.allowed is True

    def test_allowed_category_headset(self, policy):
        result = check_product_category("headset", policy)
        assert result.allowed is True

    def test_disallowed_category_laptop(self, policy):
        result = check_product_category("laptop", policy)
        assert result.allowed is False
        assert result.code == "CATEGORY_NOT_ALLOWED"

    def test_disallowed_category_smartphone(self, policy):
        result = check_product_category("smartphone", policy)
        assert result.allowed is False

    def test_rejection_reason_lists_allowed_categories(self, policy):
        result = check_product_category("tablet", policy)
        assert "mouse" in result.reason or "mouse" in str(result.details)

    def test_category_check_is_case_insensitive(self, policy):
        """Catalog may store 'Mouse' or 'MOUSE' — must still match."""
        assert check_product_category("Mouse", policy).allowed is True
        assert check_product_category("KEYBOARD", policy).allowed is True
        assert check_product_category("Headset", policy).allowed is True

    def test_details_contain_category_info(self, policy):
        result = check_product_category("mouse", policy)
        assert result.details["category"] == "mouse"
        assert "mouse" in result.details["allowed_categories"]

    def test_uses_default_policy_when_none_given(self):
        result = check_product_category("mouse")
        assert isinstance(result, GuardrailResult)

    def test_empty_category_is_rejected(self, policy):
        result = check_product_category("", policy)
        assert result.allowed is False


# ---------------------------------------------------------------------------
# 6. check_payment_confirmation
# ---------------------------------------------------------------------------

class TestCheckPaymentConfirmation:
    def test_confirmed_true_is_allowed(self, policy):
        result = check_payment_confirmation(True, policy)
        assert result.allowed is True
        assert result.code == "ALLOWED"

    def test_confirmed_false_is_rejected_when_required(self, policy):
        result = check_payment_confirmation(False, policy)
        assert result.allowed is False
        assert result.code == "PAYMENT_CONFIRMATION_REQUIRED"

    def test_rejection_reason_is_descriptive(self, policy):
        result = check_payment_confirmation(False, policy)
        assert "confirmation" in result.reason.lower()

    def test_details_contain_confirmation_info(self, policy):
        result = check_payment_confirmation(False, policy)
        assert result.details["confirmed"] is False
        assert result.details["require_payment_confirmation"] is True

    def test_confirmation_not_required_allows_unconfirmed(self):
        """When policy does not require confirmation, False is still allowed."""
        open_policy = GuardrailPolicy(
            max_order_value=5000.0,
            max_quantity_per_item=3,
            require_payment_confirmation=False,
            allowed_categories=["mouse"],
        )
        result = check_payment_confirmation(False, open_policy)
        assert result.allowed is True

    def test_confirmation_not_required_also_allows_confirmed(self):
        open_policy = GuardrailPolicy(
            max_order_value=5000.0,
            max_quantity_per_item=3,
            require_payment_confirmation=False,
            allowed_categories=["mouse"],
        )
        result = check_payment_confirmation(True, open_policy)
        assert result.allowed is True

    def test_uses_default_policy_when_none_given(self):
        result = check_payment_confirmation(True)
        assert isinstance(result, GuardrailResult)


# ---------------------------------------------------------------------------
# 7. Policy independence — each check is self-contained
# ---------------------------------------------------------------------------

class TestPolicyIndependence:
    def test_each_check_returns_guardrail_result(self, policy):
        for result in [
            check_order_value(100.0, policy),
            check_item_quantity(1, policy),
            check_product_category("mouse", policy),
            check_payment_confirmation(True, policy),
        ]:
            assert isinstance(result, GuardrailResult)

    def test_allowed_check_always_has_allowed_code(self, policy):
        """All passing checks use code='ALLOWED'."""
        for result in [
            check_order_value(1000.0, policy),
            check_item_quantity(2, policy),
            check_product_category("keyboard", policy),
            check_payment_confirmation(True, policy),
        ]:
            assert result.code == "ALLOWED"

    def test_rejected_checks_have_distinct_codes(self, policy):
        codes = {
            check_order_value(9999.0, policy).code,
            check_item_quantity(99, policy).code,
            check_product_category("smartphone", policy).code,
            check_payment_confirmation(False, policy).code,
        }
        # Each rejection must have a unique code
        assert len(codes) == 4
