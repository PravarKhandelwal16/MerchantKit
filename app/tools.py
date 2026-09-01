from pydantic import BaseModel, Field
from typing import Type, Optional

class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Type[BaseModel]
    output_structure: str

class SearchProductsInput(BaseModel):
    query: Optional[str] = Field(default=None, description="Text query to search in product name and description")
    category: Optional[str] = Field(default=None, description="Optional category to filter by")
    min_price: Optional[float] = Field(default=None, description="Optional minimum price filter")
    max_price: Optional[float] = Field(default=None, description="Optional maximum price filter")

class GetProductInput(BaseModel):
    product_id: str = Field(..., description="The exact product_id to look up")

search_products_tool = ToolDefinition(
    name="search_products",
    description="Search for products in the catalog based on text, category, and price limits. Defaults to returning only in-stock items.",
    input_schema=SearchProductsInput,
    output_structure="List of structured Product objects. Empty list if none found."
)

get_product_tool = ToolDefinition(
    name="get_product",
    description="Fetch a single product's exact details using its product_id.",
    input_schema=GetProductInput,
    output_structure="A structured Product object if found, or None/null if the product does not exist."
)

class CreateCartInput(BaseModel):
    pass

class GetCartInput(BaseModel):
    cart_id: str = Field(..., description="The ID of the cart to fetch")

class AddToCartInput(BaseModel):
    cart_id: str = Field(..., description="The ID of the cart")
    product_id: str = Field(..., description="The ID of the product to add")
    quantity: int = Field(..., ge=1, description="Quantity to add")

class UpdateCartItemInput(BaseModel):
    cart_id: str = Field(..., description="The ID of the cart")
    product_id: str = Field(..., description="The ID of the product to update")
    quantity: int = Field(..., ge=1, description="New quantity for the item")

class RemoveFromCartInput(BaseModel):
    cart_id: str = Field(..., description="The ID of the cart")
    product_id: str = Field(..., description="The ID of the product to remove")

class CreateOrderInput(BaseModel):
    cart_id: str = Field(..., description="The ID of the cart to checkout and convert to an order")

class GetOrderInput(BaseModel):
    order_id: str = Field(..., description="The ID of the order to fetch")


class CreatePaymentOrderInput(BaseModel):
    order_id: str = Field(..., description="The ID of the confirmed internal order to create a payment for")


create_cart_tool = ToolDefinition(
    name="create_cart",
    description="Create a new empty shopping cart.",
    input_schema=CreateCartInput,
    output_structure="A structured Cart object with a unique cart_id."
)

get_cart_tool = ToolDefinition(
    name="get_cart",
    description="Fetch a cart and its items by cart_id.",
    input_schema=GetCartInput,
    output_structure="A structured Cart object if found, or None if not found."
)

add_to_cart_tool = ToolDefinition(
    name="add_to_cart",
    description="Add a product to an existing cart.",
    input_schema=AddToCartInput,
    output_structure="The updated Cart object."
)

update_cart_item_tool = ToolDefinition(
    name="update_cart_item",
    description="Update the quantity of an item already in the cart.",
    input_schema=UpdateCartItemInput,
    output_structure="The updated Cart object."
)

remove_from_cart_tool = ToolDefinition(
    name="remove_from_cart",
    description="Remove a product entirely from the cart.",
    input_schema=RemoveFromCartInput,
    output_structure="A boolean indicating whether the item was removed."
)

create_order_tool = ToolDefinition(
    name="create_order",
    description="Convert an active cart into a confirmed order.",
    input_schema=CreateOrderInput,
    output_structure="The confirmed Order object."
)

get_order_tool = ToolDefinition(
    name="get_order",
    description="Fetch an order by its order_id.",
    input_schema=GetOrderInput,
    output_structure="A structured Order object if found, or None if not found."
)

create_payment_order_tool = ToolDefinition(
    name="create_payment_order",
    description="Creates a Razorpay payment order for an existing internal order.",
    input_schema=CreatePaymentOrderInput,
    output_structure="A dictionary containing payment order details including razorpay_order_id."
)

# Registry of available tools
TOOLS = {
    search_products_tool.name: search_products_tool,
    get_product_tool.name: get_product_tool,
    create_cart_tool.name: create_cart_tool,
    get_cart_tool.name: get_cart_tool,
    add_to_cart_tool.name: add_to_cart_tool,
    update_cart_item_tool.name: update_cart_item_tool,
    remove_from_cart_tool.name: remove_from_cart_tool,
    create_order_tool.name: create_order_tool,
    get_order_tool.name: get_order_tool,
    create_payment_order_tool.name: create_payment_order_tool,
}
