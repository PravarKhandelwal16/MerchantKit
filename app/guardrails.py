"""
Guardrail Policy Engine — Part 6A.

Principle: "The LLM asks. The gateway decides."

This module provides a deterministic, Python-executable policy layer that
validates commerce actions independently of anything the LLM might request.
All authoritative data (price, category, stock) is fetched from the backend,
never trusted from the caller.

No prompt instructions are used — every check is deterministic code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Policy configuration
# ---------------------------------------------------------------------------

class GuardrailPolicy(BaseModel):
    """
    Commerce policy that governs what the AI buyer is permitted to do.

    All values are configurable via environment variables so they can be
    adjusted per-deployment without touching code.
    """
    max_order_value: float = Field(
        default=float(os.getenv("GUARDRAIL_MAX_ORDER_VALUE", "5000")),
        gt=0,
        description="Maximum total order value in INR.",
    )
    max_quantity_per_item: int = Field(
        default=int(os.getenv("GUARDRAIL_MAX_QUANTITY_PER_ITEM", "3")),
        ge=1,
        description="Maximum quantity for any single line item.",
    )
    require_payment_confirmation: bool = Field(
        default=os.getenv("GUARDRAIL_REQUIRE_PAYMENT_CONFIRMATION", "true").lower() == "true",
        description="Whether explicit payment confirmation is required before money moves.",
    )
    allowed_categories: List[str] = Field(
        default_factory=lambda: [
            c.strip()
            for c in os.getenv(
                "GUARDRAIL_ALLOWED_CATEGORIES", "mouse,keyboard,headset"
            ).split(",")
            if c.strip()
        ],
        description="Product categories the AI buyer is permitted to purchase.",
    )


# Module-level default policy instance — mirrors settings pattern from config.py.
# Tests or specialised endpoints can construct their own GuardrailPolicy.
default_policy = GuardrailPolicy()


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

@dataclass
class GuardrailResult:
    """
    Outcome of a single policy check.

    Attributes
    ----------
    allowed : bool
        True if the action is permitted by policy.
    code : str
        Machine-readable result code, e.g. "ALLOWED", "ORDER_VALUE_EXCEEDED".
    reason : str
        Human-readable explanation suitable for returning to the caller / LLM.
    details : dict
        Optional structured metadata (checked value, limit, etc.).
    """
    allowed: bool
    code: str
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation functions
# Each function accepts *authoritative* values obtained from the backend.
# Callers must resolve data from the DB before calling these functions.
# ---------------------------------------------------------------------------

def check_order_value(
    total_amount: float,
    policy: Optional[GuardrailPolicy] = None,
) -> GuardrailResult:
    """
    Verify that the order total does not exceed the configured maximum.

    Parameters
    ----------
    total_amount:
        The authoritative total calculated by the backend (never from the LLM).
    policy:
        Policy to apply. Defaults to the module-level default_policy.
    """
    p = policy or default_policy
    if total_amount <= p.max_order_value:
        return GuardrailResult(
            allowed=True,
            code="ALLOWED",
            reason=f"Order total ₹{total_amount:.2f} is within the ₹{p.max_order_value:.2f} limit.",
            details={"total_amount": total_amount, "max_order_value": p.max_order_value},
        )
    return GuardrailResult(
        allowed=False,
        code="ORDER_VALUE_EXCEEDED",
        reason=(
            f"Order total ₹{total_amount:.2f} exceeds the maximum allowed "
            f"₹{p.max_order_value:.2f} per transaction."
        ),
        details={"total_amount": total_amount, "max_order_value": p.max_order_value},
    )


def check_item_quantity(
    quantity: int,
    policy: Optional[GuardrailPolicy] = None,
) -> GuardrailResult:
    """
    Verify that the requested quantity for a single line item is within policy.

    Parameters
    ----------
    quantity:
        The quantity the buyer is requesting (validated by the caller from the
        incoming tool arguments — never an LLM-claimed total).
    policy:
        Policy to apply. Defaults to the module-level default_policy.
    """
    p = policy or default_policy
    if quantity <= p.max_quantity_per_item:
        return GuardrailResult(
            allowed=True,
            code="ALLOWED",
            reason=f"Quantity {quantity} is within the per-item limit of {p.max_quantity_per_item}.",
            details={"quantity": quantity, "max_quantity_per_item": p.max_quantity_per_item},
        )
    return GuardrailResult(
        allowed=False,
        code="QUANTITY_EXCEEDED",
        reason=(
            f"Requested quantity {quantity} exceeds the maximum of "
            f"{p.max_quantity_per_item} per item."
        ),
        details={"quantity": quantity, "max_quantity_per_item": p.max_quantity_per_item},
    )


def check_product_category(
    category: str,
    policy: Optional[GuardrailPolicy] = None,
) -> GuardrailResult:
    """
    Verify that a product's category is in the allowed list.

    Parameters
    ----------
    category:
        The category fetched from the backend — never accepted from the LLM.
        Callers must call get_product() (or equivalent) and pass product.category.
    policy:
        Policy to apply. Defaults to the module-level default_policy.
    """
    p = policy or default_policy
    # Case-insensitive comparison so catalog data and policy are both forgiving
    allowed_lower = {c.lower() for c in p.allowed_categories}
    if category.lower() in allowed_lower:
        return GuardrailResult(
            allowed=True,
            code="ALLOWED",
            reason=f"Category '{category}' is permitted by policy.",
            details={"category": category, "allowed_categories": p.allowed_categories},
        )
    return GuardrailResult(
        allowed=False,
        code="CATEGORY_NOT_ALLOWED",
        reason=(
            f"Category '{category}' is not in the list of permitted categories: "
            f"{p.allowed_categories}."
        ),
        details={"category": category, "allowed_categories": p.allowed_categories},
    )


def check_payment_confirmation(
    confirmed: bool,
    policy: Optional[GuardrailPolicy] = None,
) -> GuardrailResult:
    """
    Verify that explicit payment confirmation is present when required.

    Parameters
    ----------
    confirmed:
        Whether the buyer (or the calling agent) has explicitly confirmed
        payment intent. Must be derived from a structured field — not inferred
        from LLM prose.
    policy:
        Policy to apply. Defaults to the module-level default_policy.
    """
    p = policy or default_policy
    if not p.require_payment_confirmation or confirmed:
        return GuardrailResult(
            allowed=True,
            code="ALLOWED",
            reason="Payment confirmation requirement satisfied.",
            details={
                "confirmed": confirmed,
                "require_payment_confirmation": p.require_payment_confirmation,
            },
        )
    return GuardrailResult(
        allowed=False,
        code="PAYMENT_CONFIRMATION_REQUIRED",
        reason=(
            "Explicit payment confirmation is required before this action can proceed. "
            "The buyer must confirm intent before any money movement is initiated."
        ),
        details={
            "confirmed": confirmed,
            "require_payment_confirmation": p.require_payment_confirmation,
        },
    )
