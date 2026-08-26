import pytest
from app.database import init_db, insert_product, get_db_connection
from app.schemas import Product
from app.cart import create_cart, get_cart, add_to_cart

@pytest.fixture(autouse=True)
def setup_teardown_db():
    init_db()
    conn = get_db_connection()
    conn.execute("DELETE FROM cart_items")
    conn.execute("DELETE FROM carts")
    conn.execute("DELETE FROM products")
    conn.commit()
    conn.close()
    yield

def test_create_cart():
    cart = create_cart()
    assert cart.cart_id is not None
    assert cart.status == "ACTIVE"
    assert cart.created_at is not None
    assert cart.updated_at is not None
    assert cart.items == []

def test_get_cart():
    cart = create_cart()
    fetched_cart = get_cart(cart.cart_id)
    assert fetched_cart is not None
    assert fetched_cart.cart_id == cart.cart_id
    assert fetched_cart.status == cart.status

def test_add_to_cart_valid_product():
    product = Product(
        product_id="prod_1",
        name="Test Product",
        price=10.5,
        category="Test Category",
        stock=100
    )
    insert_product(product)

    cart = create_cart()

    updated_cart = add_to_cart(cart.cart_id, "prod_1", 2)
    assert len(updated_cart.items) == 1
    assert updated_cart.items[0].product_id == "prod_1"
    assert updated_cart.items[0].quantity == 2
    assert updated_cart.items[0].unit_price == 10.5

def test_add_to_cart_nonexistent_product():
    cart = create_cart()
    with pytest.raises(ValueError, match="not found"):
        add_to_cart(cart.cart_id, "invalid_prod", 1)

def test_add_to_cart_invalid_quantity():
    cart = create_cart()
    with pytest.raises(ValueError, match="Quantity must be at least 1"):
        add_to_cart(cart.cart_id, "prod_1", 0)

def test_add_to_cart_insufficient_stock():
    product = Product(
        product_id="prod_2",
        name="Test Product 2",
        price=5.0,
        category="Test",
        stock=2
    )
    insert_product(product)
    cart = create_cart()
    
    with pytest.raises(ValueError, match="Insufficient stock"):
        add_to_cart(cart.cart_id, "prod_2", 3)

def test_add_to_cart_updates_quantity():
    product = Product(
        product_id="prod_3",
        name="Test Product 3",
        price=15.0,
        category="Test",
        stock=5
    )
    insert_product(product)
    cart = create_cart()
    
    add_to_cart(cart.cart_id, "prod_3", 2)
    updated_cart = add_to_cart(cart.cart_id, "prod_3", 2)
    
    assert len(updated_cart.items) == 1
    assert updated_cart.items[0].quantity == 4

def test_get_cart_totals():
    product1 = Product(product_id="prod_5", name="P5", price=10.0, category="Test", stock=10)
    product2 = Product(product_id="prod_6", name="P6", price=20.0, category="Test", stock=10)
    insert_product(product1)
    insert_product(product2)

    cart = create_cart()
    add_to_cart(cart.cart_id, "prod_5", 2)
    updated_cart = add_to_cart(cart.cart_id, "prod_6", 1)
    
    assert updated_cart.subtotal == 40.0
    assert updated_cart.total_quantity == 3

def test_update_cart_item():
    from app.cart import update_cart_item
    product = Product(product_id="prod_7", name="P7", price=10.0, category="Test", stock=10)
    insert_product(product)

    cart = create_cart()
    add_to_cart(cart.cart_id, "prod_7", 2)
    
    updated_cart = update_cart_item(cart.cart_id, "prod_7", 5)
    
    assert updated_cart.items[0].quantity == 5
    assert updated_cart.total_quantity == 5
    assert updated_cart.subtotal == 50.0

def test_update_cart_item_invalid_quantity():
    from app.cart import update_cart_item
    product = Product(product_id="prod_8", name="P8", price=10.0, category="Test", stock=10)
    insert_product(product)
    cart = create_cart()
    add_to_cart(cart.cart_id, "prod_8", 2)
    
    with pytest.raises(ValueError, match="Quantity must be at least 1"):
        update_cart_item(cart.cart_id, "prod_8", 0)

def test_update_cart_item_insufficient_stock():
    from app.cart import update_cart_item
    product = Product(product_id="prod_9", name="P9", price=10.0, category="Test", stock=5)
    insert_product(product)
    cart = create_cart()
    add_to_cart(cart.cart_id, "prod_9", 2)
    
    with pytest.raises(ValueError, match="Insufficient stock"):
        update_cart_item(cart.cart_id, "prod_9", 10)

def test_remove_from_cart():
    from app.cart import remove_from_cart
    product = Product(product_id="prod_10", name="P10", price=10.0, category="Test", stock=10)
    insert_product(product)
    cart = create_cart()
    add_to_cart(cart.cart_id, "prod_10", 2)
    
    assert remove_from_cart(cart.cart_id, "prod_10") is True
    
    updated_cart = get_cart(cart.cart_id)
    assert len(updated_cart.items) == 0
    assert updated_cart.total_quantity == 0
    assert updated_cart.subtotal == 0.0

def test_remove_from_cart_nonexistent_item():
    cart = create_cart()
    from app.cart import remove_from_cart
    assert remove_from_cart(cart.cart_id, "invalid_prod") is False

def test_calculate_cart_total():
    from app.cart import calculate_cart_total
    product = Product(product_id="prod_11", name="P11", price=15.0, category="Test", stock=10)
    insert_product(product)
    cart = create_cart()
    
    # Empty cart
    total = calculate_cart_total(cart.cart_id)
    assert total.subtotal == 0.0
    assert total.total_quantity == 0
    assert total.currency == "USD"
    
    # After adding
    add_to_cart(cart.cart_id, "prod_11", 3)
    total = calculate_cart_total(cart.cart_id)
    assert total.subtotal == 45.0
    assert total.total_quantity == 3
