from typing import Dict, Any, Callable, Optional
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
from app.order import create_order_from_cart, get_order, GuardrailViolation
from app.audit import audit_logger, APPROVED, REJECTED, NA

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


def _serialise_result(result: Any) -> Any:
    """
    Convert a handler return value to a plain dict/list so it can be stored
    in the audit log as JSON. Pydantic models → model_dump(); lists of models
    are handled too; everything else passes through unchanged.
    """
    if result is None:
        return None
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, list):
        return [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in result
        ]
    return result


def execute_tool(
    tool_name: str,
    arguments: Any,
    actor: str = "api",
) -> Dict[str, Any]:
    """
    Safely route a structured tool request to the corresponding service,
    validate arguments using the established tool schemas, and audit every
    execution attempt — successful or not.

    Parameters
    ----------
    tool_name : str
        Name of the registered tool to call.
    arguments : Any
        Arguments dict (or None) for the tool.
    actor : str
        Identifier for who is making the call.  Pass "buyer_agent" when
        called from the autonomous agent loop so the audit trail tracks the
        actor accurately.  Defaults to "api" for direct gateway calls.
    """
    # -----------------------------------------------------------------------
    # Gate: tool_name must be non-empty
    # -----------------------------------------------------------------------
    if not tool_name:
        return {
            "success": False,
            "tool": "",
            "error": {
                "code": "MISSING_TOOL_NAME",
                "message": "Tool name is required.",
            },
        }

    # -----------------------------------------------------------------------
    # Gate: tool must be registered
    # -----------------------------------------------------------------------
    if tool_name not in TOOLS or tool_name not in TOOL_HANDLERS:
        return {
            "success": False,
            "tool": tool_name,
            "error": {
                "code": "TOOL_NOT_FOUND",
                "message": "Unknown tool",
            },
        }

    tool_def = TOOLS[tool_name]
    handler = TOOL_HANDLERS[tool_name]

    # -----------------------------------------------------------------------
    # Normalise arguments
    # -----------------------------------------------------------------------
    if not isinstance(arguments, dict):
        if arguments is None:
            arguments = {}
        else:
            return {
                "success": False,
                "tool": tool_name,
                "error": {
                    "code": "MALFORMED_ARGUMENTS",
                    "message": "Arguments must be a dictionary.",
                },
            }

    # -----------------------------------------------------------------------
    # Validate arguments with Pydantic schema
    # -----------------------------------------------------------------------
    try:
        validated_args = tool_def.input_schema(**arguments)
    except ValidationError as e:
        # Validation failures are not audited — the call never reached the
        # service layer and carries no commerce significance.
        return {
            "success": False,
            "tool": tool_name,
            "error": {
                "code": "INVALID_ARGUMENTS",
                "message": str(e),
            },
        }

    # -----------------------------------------------------------------------
    # Execute handler and audit the outcome
    # Audit writes are wrapped in try/except so a logging failure NEVER
    # silently promotes a bad operation — if the audit write itself fails we
    # log to stderr but still return the correct response to the caller.
    # -----------------------------------------------------------------------
    kwargs = validated_args.model_dump()

    try:
        result = handler(**kwargs)

        response = {
            "success": True,
            "tool": tool_name,
            "data": result,
        }

        # --- Audit: successful tool execution ---
        try:
            audit_logger.log_tool_call(
                actor=actor,
                action=tool_name,
                arguments=kwargs,
                result=_serialise_result(result),
                success=True,
                policy_decision=APPROVED if tool_name == "create_order" else NA,
                reason="Tool executed successfully.",
            )
        except Exception as audit_err:  # noqa: BLE001
            import sys
            print(f"[audit] WARNING: failed to write audit log: {audit_err}", file=sys.stderr)

        return response

    except GuardrailViolation as e:
        response = {
            "success": False,
            "tool": tool_name,
            "error": {
                "code": "GUARDRAIL_VIOLATION",
                "guardrail_code": e.result.code,
                "message": e.result.reason,
                "details": e.result.details,
            },
        }

        # --- Audit: guardrail rejection ---
        try:
            audit_logger.log_guardrail(
                actor=actor,
                action=tool_name,
                policy_decision=REJECTED,
                reason=e.result.reason,
                arguments=kwargs,
                details=e.result.details,
            )
        except Exception as audit_err:  # noqa: BLE001
            import sys
            print(f"[audit] WARNING: failed to write audit log: {audit_err}", file=sys.stderr)

        return response

    except Exception as e:
        response = {
            "success": False,
            "tool": tool_name,
            "error": {
                "code": "EXECUTION_ERROR",
                "message": str(e),
            },
        }

        # --- Audit: unexpected runtime error ---
        try:
            audit_logger.log_tool_call(
                actor=actor,
                action=tool_name,
                arguments=kwargs,
                result=None,
                success=False,
                error_code="EXECUTION_ERROR",
                reason=str(e),
            )
        except Exception as audit_err:  # noqa: BLE001
            import sys
            print(f"[audit] WARNING: failed to write audit log: {audit_err}", file=sys.stderr)

        return response
