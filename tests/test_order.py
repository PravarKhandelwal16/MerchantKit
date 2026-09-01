import pytest
from app.database import init_db, insert_product, get_db_connection
from app.schemas import Product
from app.cart import create_cart, add_to_cart, get_cart
from app.order import create_order_from_cart, get_order
from app.guardrails import GuardrailPolicy

# ---------------------------------------------------------------------------
# Permissive policy used by Part-4 structural tests.
# These tests verify order creation mechanics, not guardrail policy — so we
# inject a policy that allows the "Test" category they use.
# ---------------------------------------------------------------------------
PERMISSIVE_POLICY = GuardrailPolicy(
    max_order_value=999_999.0,
    max_quantity_per_item=999,
    require_payment_confirmation=False,
    allowed_categories=["test", "mouse", "keyboard", "headset"],
)

@pytest.fixture(autouse=True)
def setup_teardown_db():
    init_db()
    conn = get_db_connection()
    conn.execute("DELETE FROM order_items")
    conn.execute("DELETE FROM orders")
    conn.execute("DELETE FROM cart_items")
    conn.execute("DELETE FROM carts")
    conn.execute("DELETE FROM products")
    conn.commit()
    conn.close()
    yield

def test_create_order_success():
    product = Product(product_id="prod_1", name="Product 1", price=10.0, category="Test", stock=10)
    insert_product(product)

    cart = create_cart()
    add_to_cart(cart.cart_id, "prod_1", 2)

    order = create_order_from_cart(cart.cart_id, policy=PERMISSIVE_POLICY)

    assert order.order_id is not None
    assert order.cart_id == cart.cart_id
    assert order.total_amount == 20.0
    assert order.status == "CREATED"
    assert len(order.items) == 1
    assert order.items[0].product_name == "Product 1"

    updated_cart = get_cart(cart.cart_id)
    assert updated_cart.status == "CHECKOUT"

def test_create_order_empty_cart():
    cart = create_cart()
    with pytest.raises(ValueError, match="is empty"):
        create_order_from_cart(cart.cart_id, policy=PERMISSIVE_POLICY)

def test_create_order_nonexistent_cart():
    with pytest.raises(ValueError, match="not found"):
        create_order_from_cart("invalid_cart", policy=PERMISSIVE_POLICY)

def test_create_order_duplicate_prevention():
    product = Product(product_id="prod_2", name="Product 2", price=10.0, category="Test", stock=10)
    insert_product(product)

    cart = create_cart()
    add_to_cart(cart.cart_id, "prod_2", 2)

    create_order_from_cart(cart.cart_id, policy=PERMISSIVE_POLICY)

    with pytest.raises(ValueError, match="is not ACTIVE"):
        create_order_from_cart(cart.cart_id, policy=PERMISSIVE_POLICY)

def test_get_order():
    product = Product(product_id="prod_3", name="Product 3", price=15.0, category="Test", stock=10)
    insert_product(product)

    cart = create_cart()
    add_to_cart(cart.cart_id, "prod_3", 1)

    order = create_order_from_cart(cart.cart_id, policy=PERMISSIVE_POLICY)

    fetched = get_order(order.order_id)
    assert fetched is not None
    assert fetched.order_id == order.order_id
    assert len(fetched.items) == 1
