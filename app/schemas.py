from typing import Optional, List
from pydantic import BaseModel, Field


class Product(BaseModel):
    product_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    price: float = Field(..., gt=0)
    category: str = Field(..., min_length=1)
    stock: int = Field(..., ge=0)
    image_url: Optional[str] = None


class CartItem(BaseModel):
    product_id: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)
    product_name: Optional[str] = None


class Cart(BaseModel):
    cart_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    updated_at: str = Field(..., min_length=1)
    items: List[CartItem] = Field(default_factory=list)
    subtotal: float = 0.0
    total_quantity: int = 0


class CartTotal(BaseModel):
    subtotal: float
    total_quantity: int
    currency: str = "USD"


class OrderItem(BaseModel):
    order_id: str = Field(..., min_length=1)
    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1)
    unit_price: float = Field(..., ge=0)


class Order(BaseModel):
    order_id: str = Field(..., min_length=1)
    cart_id: str = Field(..., min_length=1)
    total_amount: float = Field(..., ge=0)
    currency: str = Field(default="USD", min_length=1)
    status: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    payment_provider: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    payment_status: Optional[str] = None
    items: List[OrderItem] = Field(default_factory=list)
