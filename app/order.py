import uuid
from datetime import datetime, timezone
from typing import Optional

from app.schemas import Order, OrderItem
from app.cart import get_cart
from app.database import get_product, create_order_transaction, fetch_order


def _get_utc_now() -> str:
    """Helper to get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def create_order_from_cart(cart_id: str) -> Order:
    """
    Creates an order from an active cart.
    """
    cart = get_cart(cart_id)
    if not cart:
        raise ValueError(f"Cart '{cart_id}' not found")
        
    if cart.status != "ACTIVE":
        raise ValueError(f"Cart '{cart_id}' is not ACTIVE")
        
    if not cart.items:
        raise ValueError(f"Cart '{cart_id}' is empty")

    order_id = str(uuid.uuid4())
    now = _get_utc_now()
    
    order_items = []
    total_amount = 0.0
    
    for item in cart.items:
        product = get_product(item.product_id)
        if not product:
            raise ValueError(f"Product '{item.product_id}' not found")
            
        order_item = OrderItem(
            order_id=order_id,
            product_id=product.product_id,
            product_name=product.name,
            quantity=item.quantity,
            unit_price=product.price
        )
        order_items.append(order_item)
        total_amount += item.quantity * product.price
        
    order = Order(
        order_id=order_id,
        cart_id=cart_id,
        total_amount=total_amount,
        currency="USD",
        status="CREATED",
        created_at=now,
        items=[]
    )
    
    create_order_transaction(order, order_items)
    
    # Return the full order
    order.items = order_items
    return order


def get_order(order_id: str) -> Optional[Order]:
    """
    Retrieves an order by its ID.
    """
    return fetch_order(order_id)
