import uuid
from datetime import datetime, timezone
from typing import Optional

from app.schemas import Order, OrderItem
from app.cart import get_cart
from app.database import get_product, create_order_transaction, fetch_order
from app.guardrails import (
    GuardrailPolicy,
    GuardrailResult,
    check_order_value,
    check_item_quantity,
    check_product_category,
    default_policy,
)


class GuardrailViolation(Exception):
    """
    Raised when a commerce action is blocked by the guardrail policy engine.

    Attributes
    ----------
    result : GuardrailResult
        The structured rejection reason from the policy check.
    """
    def __init__(self, result: GuardrailResult) -> None:
        self.result = result
        super().__init__(result.reason)


def _get_utc_now() -> str:
    """Helper to get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def create_order_from_cart(
    cart_id: str,
    policy: Optional[GuardrailPolicy] = None,
) -> Order:
    """
    Creates an order from an active cart after passing all guardrail checks.

    Parameters
    ----------
    cart_id:
        The cart to convert into an order.
    policy:
        Guardrail policy to enforce. Defaults to the module-level default_policy.
        Tests may inject a permissive policy; production always uses the default.

    Raises
    ------
    ValueError
        For structural problems (cart not found, empty, not ACTIVE, missing product).
    GuardrailViolation
        When a policy check rejects the order — no order is written and the cart
        status is never changed.
    """
    _policy = policy or default_policy

    cart = get_cart(cart_id)
    if not cart:
        raise ValueError(f"Cart '{cart_id}' not found")

    if cart.status != "ACTIVE":
        raise ValueError(f"Cart '{cart_id}' is not ACTIVE")

    if not cart.items:
        raise ValueError(f"Cart '{cart_id}' is empty")

    # -----------------------------------------------------------------------
    # Build order items and recalculate total from authoritative backend data.
    # Run all guardrail checks BEFORE touching the database.
    # -----------------------------------------------------------------------
    order_id = str(uuid.uuid4())
    now = _get_utc_now()

    order_items = []
    total_amount = 0.0

    for item in cart.items:
        product = get_product(item.product_id)
        if not product:
            raise ValueError(f"Product '{item.product_id}' not found")

        # --- Per-item guardrail: quantity ---
        qty_result = check_item_quantity(item.quantity, _policy)
        if not qty_result.allowed:
            raise GuardrailViolation(qty_result)

        # --- Per-item guardrail: category (authoritative from DB product) ---
        cat_result = check_product_category(product.category, _policy)
        if not cat_result.allowed:
            raise GuardrailViolation(cat_result)

        order_item = OrderItem(
            order_id=order_id,
            product_id=product.product_id,
            product_name=product.name,
            quantity=item.quantity,
            unit_price=product.price,  # authoritative price, never from client
        )
        order_items.append(order_item)
        total_amount += item.quantity * product.price  # recalculated server-side

    # --- Order-level guardrail: total value (recalculated above, never trusted from caller) ---
    value_result = check_order_value(total_amount, _policy)
    if not value_result.allowed:
        raise GuardrailViolation(value_result)

    # -----------------------------------------------------------------------
    # All checks passed — write the order in a single transaction.
    # -----------------------------------------------------------------------
    order = Order(
        order_id=order_id,
        cart_id=cart_id,
        total_amount=total_amount,
        currency="INR",
        status="CREATED",
        created_at=now,
        items=[],
    )

    create_order_transaction(order, order_items)

    order.items = order_items
    return order


def get_order(order_id: str) -> Optional[Order]:
    """
    Retrieves an order by its ID.
    """
    return fetch_order(order_id)
