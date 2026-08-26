import uuid
from datetime import datetime, timezone
from typing import Optional

from app.schemas import Cart, CartItem, CartTotal
from app.database import (
    insert_cart,
    fetch_cart,
    get_product,
    upsert_cart_item,
    update_cart_timestamp,
    upsert_cart_item_transaction,
    delete_cart_item_transaction,
)


def _get_utc_now() -> str:
    """Helper to get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def create_cart() -> Cart:
    """
    Creates a new shopping cart.
    """
    now = _get_utc_now()
    cart = Cart(
        cart_id=str(uuid.uuid4()),
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        items=[],
    )
    insert_cart(cart)
    return cart


def get_cart(cart_id: str) -> Optional[Cart]:
    """
    Retrieves a cart by its ID.
    """
    cart = fetch_cart(cart_id)
    if cart:
        cart.subtotal = sum(item.quantity * item.unit_price for item in cart.items)
        cart.total_quantity = sum(item.quantity for item in cart.items)
    return cart


def add_to_cart(cart_id: str, product_id: str, quantity: int) -> Cart:
    """
    Adds a product to the cart or updates its quantity.
    """
    if quantity < 1:
        raise ValueError("Quantity must be at least 1")

    # Fetch cart to ensure it exists
    cart = get_cart(cart_id)
    if not cart:
        raise ValueError(f"Cart '{cart_id}' not found")

    # Verify product exists
    product = get_product(product_id)
    if not product:
        raise ValueError(f"Product '{product_id}' not found")

    # Calculate new quantity if item already in cart
    existing_item = next((item for item in cart.items if item.product_id == product_id), None)
    new_quantity = quantity
    if existing_item:
        new_quantity = existing_item.quantity + quantity

    # Verify stock is sufficient
    if product.stock < new_quantity:
        raise ValueError(f"Insufficient stock for product '{product_id}'")

    # Create/update CartItem with the authoritative price
    item = CartItem(
        product_id=product_id,
        quantity=new_quantity,
        unit_price=product.price
    )
    now = _get_utc_now()
    upsert_cart_item_transaction(cart_id, item, now)

    # Return updated cart
    return get_cart(cart_id)


def update_cart_item(cart_id: str, product_id: str, quantity: int) -> Cart:
    """
    Updates the quantity of an existing cart item.
    """
    if quantity < 1:
        raise ValueError("Quantity must be at least 1")

    cart = fetch_cart(cart_id)
    if not cart:
        raise ValueError(f"Cart '{cart_id}' not found")
        
    existing_item = next((item for item in cart.items if item.product_id == product_id), None)
    if not existing_item:
        raise ValueError(f"Product '{product_id}' not in cart")

    product = get_product(product_id)
    if not product:
        raise ValueError(f"Product '{product_id}' not found")

    if product.stock < quantity:
        raise ValueError(f"Insufficient stock for product '{product_id}'")

    item = CartItem(
        product_id=product_id,
        quantity=quantity,
        unit_price=product.price
    )
    now = _get_utc_now()
    upsert_cart_item_transaction(cart_id, item, now)

    return get_cart(cart_id)


def remove_from_cart(cart_id: str, product_id: str) -> bool:
    """
    Removes a product from the cart. Returns True if removed, False otherwise.
    """
    cart = fetch_cart(cart_id)
    if not cart:
        return False
        
    now = _get_utc_now()
    deleted_count = delete_cart_item_transaction(cart_id, product_id, now)
    return deleted_count > 0


def calculate_cart_total(cart_id: str) -> CartTotal:
    """
    Calculates the cart total based on authoritative stored prices.
    """
    cart = get_cart(cart_id)
    if not cart:
        raise ValueError(f"Cart '{cart_id}' not found")
        
    return CartTotal(
        subtotal=cart.subtotal,
        total_quantity=cart.total_quantity,
        currency="USD"
    )
