from typing import Dict, Any, Callable
from pydantic import ValidationError
from app.tools import TOOLS
from app.database import search_products, get_product
from app.cart import (
    create_cart,
    get_cart,
    add_to_cart,
    update_cart_item,
    remove_from_cart,
)
from app.order import create_order_from_cart, get_order

# Central tool registry mapping allowed tool names to their actual handlers.
# This prevents execution of arbitrary functions.
TOOL_HANDLERS: Dict[str, Callable] = {
    "search_products": search_products,
    "get_product": get_product,
    "create_cart": create_cart,
    "get_cart": get_cart,
    "add_to_cart": add_to_cart,
    "update_cart_item": update_cart_item,
    "remove_from_cart": remove_from_cart,
    "create_order": create_order_from_cart,
    "get_order": get_order,
}

def execute_tool(tool_name: str, arguments: Any) -> Dict[str, Any]:
    """
    Safely route a structured tool request to the corresponding catalog service,
    validating arguments using the established tool schemas.
    """
    if not tool_name:
        return {
            "success": False,
            "tool": "",
            "error": {
                "code": "MISSING_TOOL_NAME",
                "message": "Tool name is required."
            }
        }

    if tool_name not in TOOLS or tool_name not in TOOL_HANDLERS:
        return {
            "success": False,
            "tool": tool_name,
            "error": {
                "code": "TOOL_NOT_FOUND",
                "message": "Unknown tool"
            }
        }

    tool_def = TOOLS[tool_name]
    handler = TOOL_HANDLERS[tool_name]

    if not isinstance(arguments, dict):
        if arguments is None:
            arguments = {}
        else:
            return {
                "success": False,
                "tool": tool_name,
                "error": {
                    "code": "MALFORMED_ARGUMENTS",
                    "message": "Arguments must be a dictionary."
                }
            }

    # Validate arguments using the Pydantic schema
    try:
        validated_args = tool_def.input_schema(**arguments)
    except ValidationError as e:
        return {
            "success": False,
            "tool": tool_name,
            "error": {
                "code": "INVALID_ARGUMENTS",
                "message": str(e)
            }
        }

    # Execute the handler with validated arguments
    try:
        kwargs = validated_args.model_dump()
        result = handler(**kwargs)
        
        return {
            "success": True,
            "tool": tool_name,
            "data": result
        }
    except Exception as e:
        return {
            "success": False,
            "tool": tool_name,
            "error": {
                "code": "EXECUTION_ERROR",
                "message": str(e)
            }
        }
