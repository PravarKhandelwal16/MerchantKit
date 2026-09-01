"""
Tests for Part 6B: Guardrail integration with the order service.

Principle: The guardrail checks run server-side inside create_order_from_cart()
BEFORE any database write. A rejected order must not appear in the DB and must
not change the cart status.

All authoritative values (price, category) are fetched from the DB — the client
cannot supply them and cannot bypass the policy.
"""
import pytest
from app.database import init_db, insert_product, get_db_connection
from app.schemas import Product
from app.cart import create_cart, add_to_cart, get_cart
from app.order import create_order_from_cart, get_order, GuardrailViolation
from app.guardrails import GuardrailPolicy


# ---------------------------------------------------------------------------
# Fixed policy matching the Part-6 specification
# ---------------------------------------------------------------------------
POLICY = GuardrailPolicy(
    max_order_value=5000.0,
    max_quantity_per_item=3,
    require_payment_confirmation=False,   # not tested here — no payment yet
    allowed_categories=["mouse", "keyboard", "headset"],
)

# Permissive policy used only when the test intentionally needs to bypass limits
PERMISSIVE = GuardrailPolicy(
    max_order_value=999_999.0,
    max_quantity_per_item=999,
    require_payment_confirmation=False,
    allowed_categories=["mouse", "keyboard", "headset", "test"],
)


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    conn = get_db_connection()
    for table in ("order_items", "orders", "cart_items", "carts", "products"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()
    yield


def _make_product(product_id: str, price: float, category: str = "mouse", stock: int = 20) -> Product:
    p = Product(product_id=product_id, name=f"Product {product_id}", price=price, category=category, stock=stock)
    insert_product(p)
    return p


def _cart_with(*items: tuple) -> str:
    """Create a cart and add (product_id, qty) pairs. Returns cart_id."""
    cart = create_cart()
    for product_id, qty in items:
        add_to_cart(cart.cart_id, product_id, qty)
    return cart.cart_id


# ---------------------------------------------------------------------------
# 1. Happy path — valid orders pass all guardrails
# ---------------------------------------------------------------------------

class TestValidOrdersPassGuardrails:
    def test_valid_order_under_limit(self):
        _make_product("p1", price=1000.0)      # 1 × ₹1000 = ₹1000
        cart_id = _cart_with(("p1", 1))
        order = create_order_from_cart(cart_id, policy=POLICY)
        assert order.order_id is not None
        assert order.total_amount == 1000.0
        assert order.status == "CREATED"

    def test_order_exactly_at_max_value_passes(self):
        """Boundary: ₹5000.00 exactly must be allowed."""
        _make_product("p2", price=2500.0)      # 2 × ₹2500 = ₹5000
        cart_id = _cart_with(("p2", 2))
        order = create_order_from_cart(cart_id, policy=POLICY)
        assert order.total_amount == 5000.0

    def test_valid_order_marks_cart_as_checkout(self):
        _make_product("p3", price=100.0)
        cart_id = _cart_with(("p3", 1))
        create_order_from_cart(cart_id, policy=POLICY)
        cart = get_cart(cart_id)
        assert cart.status == "CHECKOUT"

    def test_valid_order_has_correct_items(self):
        _make_product("p4", price=500.0)
        cart_id = _cart_with(("p4", 2))
        order = create_order_from_cart(cart_id, policy=POLICY)
        assert len(order.items) == 1
        assert order.items[0].quantity == 2
        assert order.items[0].unit_price == 500.0

    def test_valid_order_persisted_in_db(self):
        _make_product("p5", price=300.0)
        cart_id = _cart_with(("p5", 1))
        order = create_order_from_cart(cart_id, policy=POLICY)
        fetched = get_order(order.order_id)
        assert fetched is not None
        assert fetched.order_id == order.order_id


# ---------------------------------------------------------------------------
# 2. Order value guardrail
# ---------------------------------------------------------------------------

class TestOrderValueGuardrail:
    def test_order_above_limit_raises_violation(self):
        _make_product("pv1", price=2000.0)     # 3 × ₹2000 = ₹6000 > ₹5000
        cart_id = _cart_with(("pv1", 3))
        with pytest.raises(GuardrailViolation) as exc_info:
            create_order_from_cart(cart_id, policy=POLICY)
        assert exc_info.value.result.code == "ORDER_VALUE_EXCEEDED"

    def test_order_above_limit_by_one_rupee_is_rejected(self):
        _make_product("pv2", price=5000.01)    # 1 × ₹5000.01 > ₹5000
        cart_id = _cart_with(("pv2", 1))
        with pytest.raises(GuardrailViolation) as exc_info:
            create_order_from_cart(cart_id, policy=POLICY)
        assert exc_info.value.result.code == "ORDER_VALUE_EXCEEDED"

    def test_rejected_order_does_not_exist_in_db(self):
        """A rejected order must leave zero trace in the orders table."""
        _make_product("pv3", price=6000.0)
        cart_id = _cart_with(("pv3", 1))
        try:
            order = create_order_from_cart(cart_id, policy=POLICY)
            order_id = order.order_id
        except GuardrailViolation as e:
            # The violation gives no order_id; verify nothing was written
            conn = get_db_connection()
            count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            conn.close()
            assert count == 0
        else:
            pytest.fail("Expected GuardrailViolation was not raised")

    def test_rejected_cart_remains_active_and_reusable(self):
        """Cart must NOT be marked CHECKOUT after a rejected order."""
        _make_product("pv4", price=6000.0)
        cart_id = _cart_with(("pv4", 1))
        with pytest.raises(GuardrailViolation):
            create_order_from_cart(cart_id, policy=POLICY)
        cart = get_cart(cart_id)
        assert cart.status == "ACTIVE"   # still usable — can update and retry

    def test_client_supplied_total_cannot_bypass_policy(self):
        """
        There is no 'total' argument to create_order_from_cart — the backend
        always recalculates from DB data. This test demonstrates that even if a
        product's actual DB price yields ₹6000, the order is rejected regardless
        of what value the caller could theoretically claim.
        """
        # Attempt to sneak a high-price order through: price is set in DB, NOT
        # accepted from the tool caller. The guardrail checks the DB price.
        _make_product("pv5", price=6000.0)
        cart_id = _cart_with(("pv5", 1))
        # Calling with no total argument (there is none) — policy still fires
        with pytest.raises(GuardrailViolation) as exc_info:
            create_order_from_cart(cart_id, policy=POLICY)
        assert exc_info.value.result.code == "ORDER_VALUE_EXCEEDED"


# ---------------------------------------------------------------------------
# 3. Quantity guardrail
# ---------------------------------------------------------------------------

class TestQuantityGuardrail:
    def test_quantity_at_limit_is_allowed(self):
        _make_product("pq1", price=100.0, stock=10)   # 3 × ₹100 = ₹300 < ₹5000
        cart_id = _cart_with(("pq1", 3))
        order = create_order_from_cart(cart_id, policy=POLICY)
        assert order.total_amount == 300.0

    def test_quantity_above_limit_raises_violation(self):
        _make_product("pq2", price=100.0, stock=20)
        cart_id = _cart_with(("pq2", 4))           # 4 > max_quantity_per_item=3
        with pytest.raises(GuardrailViolation) as exc_info:
            create_order_from_cart(cart_id, policy=POLICY)
        assert exc_info.value.result.code == "QUANTITY_EXCEEDED"

    def test_excessive_quantity_cart_remains_active(self):
        _make_product("pq3", price=50.0, stock=20)
        cart_id = _cart_with(("pq3", 4))
        with pytest.raises(GuardrailViolation):
            create_order_from_cart(cart_id, policy=POLICY)
        assert get_cart(cart_id).status == "ACTIVE"


# ---------------------------------------------------------------------------
# 4. Category guardrail
# ---------------------------------------------------------------------------

class TestCategoryGuardrail:
    def test_allowed_category_passes(self):
        _make_product("pc1", price=500.0, category="keyboard")
        cart_id = _cart_with(("pc1", 1))
        order = create_order_from_cart(cart_id, policy=POLICY)
        assert order.order_id is not None

    def test_disallowed_category_raises_violation(self):
        insert_product(Product(
            product_id="pc2", name="Laptop", price=40000.0,
            category="laptop", stock=5
        ))
        # Use permissive policy for value/qty so only category triggers
        loose_policy = GuardrailPolicy(
            max_order_value=999_999.0,
            max_quantity_per_item=999,
            require_payment_confirmation=False,
            allowed_categories=["mouse", "keyboard", "headset"],
        )
        cart_id = _cart_with(("pc2", 1))
        with pytest.raises(GuardrailViolation) as exc_info:
            create_order_from_cart(cart_id, policy=loose_policy)
        assert exc_info.value.result.code == "CATEGORY_NOT_ALLOWED"

    def test_disallowed_category_cart_remains_active(self):
        insert_product(Product(
            product_id="pc3", name="Tablet", price=100.0,
            category="tablet", stock=5
        ))
        loose_policy = GuardrailPolicy(
            max_order_value=999_999.0,
            max_quantity_per_item=999,
            require_payment_confirmation=False,
            allowed_categories=["mouse", "keyboard", "headset"],
        )
        cart_id = _cart_with(("pc3", 1))
        with pytest.raises(GuardrailViolation):
            create_order_from_cart(cart_id, policy=loose_policy)
        assert get_cart(cart_id).status == "ACTIVE"

    def test_category_check_uses_authoritative_db_value(self):
        """
        The category is fetched from the DB product record, NOT from any
        argument the caller provides. The tool schema has no 'category' field.
        """
        _make_product("pc4", price=500.0, category="mouse")
        cart_id = _cart_with(("pc4", 1))
        # No way to pass a fake category — it always comes from the DB
        order = create_order_from_cart(cart_id, policy=POLICY)
        assert order.order_id is not None


# ---------------------------------------------------------------------------
# 5. GuardrailViolation surfaces correctly through the executor gateway
# ---------------------------------------------------------------------------

class TestGuardrailViolationThroughGateway:
    def test_create_order_tool_returns_guardrail_violation_code(self):
        """
        Via execute_tool, a policy rejection must return GUARDRAIL_VIOLATION —
        not EXECUTION_ERROR — so the agent can distinguish policy from bugs.
        """
        from app.executor import execute_tool

        # Product with disallowed category
        insert_product(Product(
            product_id="gw1", name="Smartphone", price=999.0,
            category="smartphone", stock=5
        ))
        cart = create_cart()
        add_to_cart(cart.cart_id, "gw1", 1)

        res = execute_tool("create_order", {"cart_id": cart.cart_id})
        assert res["success"] is False
        assert res["error"]["code"] == "GUARDRAIL_VIOLATION"
        assert "guardrail_code" in res["error"]
        assert res["error"]["guardrail_code"] == "CATEGORY_NOT_ALLOWED"

    def test_create_order_tool_value_exceeded_returns_violation(self):
        from app.executor import execute_tool

        _make_product("gw2", price=9999.0, category="mouse")
        cart = create_cart()
        add_to_cart(cart.cart_id, "gw2", 1)

        res = execute_tool("create_order", {"cart_id": cart.cart_id})
        assert res["success"] is False
        assert res["error"]["code"] == "GUARDRAIL_VIOLATION"
        assert res["error"]["guardrail_code"] == "ORDER_VALUE_EXCEEDED"
