import pytest
from app.database import init_db, insert_product, get_db_connection
from app.schemas import Product
from app.executor import execute_tool

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
    
    product = Product(product_id="prod_tool_1", name="Tool Product", price=15.0, category="mouse", stock=10)
    insert_product(product)
    yield

def test_commerce_tools_flow():
    # 1. Create cart
    res = execute_tool("create_cart", {})
    assert res["success"] is True
    cart_id = res["data"].cart_id
    assert cart_id is not None
    
    # 2. Get cart
    res = execute_tool("get_cart", {"cart_id": cart_id})
    assert res["success"] is True
    assert res["data"].cart_id == cart_id
    
    # 3. Add to cart
    res = execute_tool("add_to_cart", {"cart_id": cart_id, "product_id": "prod_tool_1", "quantity": 2})
    assert res["success"] is True
    assert res["data"].total_quantity == 2
    assert res["data"].subtotal == 30.0
    
    # 4. Update cart item
    res = execute_tool("update_cart_item", {"cart_id": cart_id, "product_id": "prod_tool_1", "quantity": 3})
    assert res["success"] is True
    assert res["data"].total_quantity == 3
    assert res["data"].subtotal == 45.0
    
    # 5. Create order
    res = execute_tool("create_order", {"cart_id": cart_id})
    assert res["success"] is True
    order_id = res["data"].order_id
    assert order_id is not None
    assert res["data"].total_amount == 45.0
    assert res["data"].status == "CREATED"
    
    # 6. Get order
    res = execute_tool("get_order", {"order_id": order_id})
    assert res["success"] is True
    assert res["data"].order_id == order_id
    assert len(res["data"].items) == 1

def test_commerce_tools_validation_errors():
    # Missing args
    res = execute_tool("get_cart", {})
    assert res["success"] is False
    assert res["error"]["code"] == "INVALID_ARGUMENTS"
    
    # Invalid quantity type
    res = execute_tool("add_to_cart", {"cart_id": "123", "product_id": "abc", "quantity": "invalid"})
    assert res["success"] is False
    assert res["error"]["code"] == "INVALID_ARGUMENTS"

def test_commerce_tools_business_errors():
    # Attempt to add to nonexistent cart
    res = execute_tool("add_to_cart", {"cart_id": "does_not_exist", "product_id": "prod_tool_1", "quantity": 1})
    assert res["success"] is False
    assert res["error"]["code"] == "EXECUTION_ERROR"
    assert "not found" in res["error"]["message"].lower()

def test_remove_from_cart_tool():
    # Setup
    res = execute_tool("create_cart", {})
    cart_id = res["data"].cart_id
    execute_tool("add_to_cart", {"cart_id": cart_id, "product_id": "prod_tool_1", "quantity": 1})
    
    # Remove
    res = execute_tool("remove_from_cart", {"cart_id": cart_id, "product_id": "prod_tool_1"})
    assert res["success"] is True
    assert res["data"] is True
    
    # Verify
    res = execute_tool("get_cart", {"cart_id": cart_id})
    assert res["data"].total_quantity == 0
