"""
Tests for read-only dashboard commerce endpoints:
- GET /dashboard/products
- GET /dashboard/carts
- GET /dashboard/orders
- Cart items product name join and authoritative subtotal/total_quantity
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import (
    init_db,
    insert_product,
    get_db_connection,
)
from app.schemas import Product
from app.cart import create_cart, add_to_cart
from app.order import create_order_from_cart

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
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


def test_dashboard_get_products_empty():
    res = client.get("/dashboard/products")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["data"] == []


def test_dashboard_get_products_populated():
    p = Product(
        product_id="prod_m1",
        name="Logitech Mouse",
        description="Wireless mouse",
        price=1299.0,
        category="mouse",
        stock=15,
    )
    insert_product(p)

    res = client.get("/dashboard/products")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    prod = data["data"][0]
    assert prod["product_id"] == "prod_m1"
    assert prod["name"] == "Logitech Mouse"
    assert prod["price"] == 1299.0
    assert prod["stock"] == 15


def test_dashboard_get_carts():
    p = Product(
        product_id="prod_k1",
        name="Mechanical Keyboard",
        description="Gaming keyboard",
        price=2499.0,
        category="keyboard",
        stock=10,
    )
    insert_product(p)

    cart = create_cart()
    add_to_cart(cart.cart_id, "prod_k1", 2)

    res = client.get("/dashboard/carts")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["data"]) == 1

    c = data["data"][0]
    assert c["cart_id"] == cart.cart_id
    assert c["status"] == "ACTIVE"
    assert c["subtotal"] == 4998.0
    assert c["total_quantity"] == 2
    assert len(c["items"]) == 1
    item = c["items"][0]
    assert item["product_id"] == "prod_k1"
    assert item["product_name"] == "Mechanical Keyboard"
    assert item["quantity"] == 2
    assert item["unit_price"] == 2499.0


def test_dashboard_get_orders():
    p = Product(
        product_id="prod_h1",
        name="Gaming Headset",
        description="Headset with mic",
        price=1999.0,
        category="headset",
        stock=5,
    )
    insert_product(p)

    cart = create_cart()
    add_to_cart(cart.cart_id, "prod_h1", 1)
    order = create_order_from_cart(cart.cart_id)

    res = client.get("/dashboard/orders")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["data"]) == 1

    o = data["data"][0]
    assert o["order_id"] == order.order_id
    assert o["cart_id"] == cart.cart_id
    assert o["total_amount"] == 1999.0
    assert o["currency"] == "INR"
    assert o["status"] == "CREATED"
    assert len(o["items"]) == 1
    assert o["items"][0]["product_name"] == "Gaming Headset"
    assert o["items"][0]["quantity"] == 1
    assert o["items"][0]["unit_price"] == 1999.0
