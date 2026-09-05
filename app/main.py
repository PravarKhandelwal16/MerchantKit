from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from app.config import settings
from app.database import init_db
from app.executor import execute_tool
from app.agent import BuyerAgent, AgentResult


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize minimal SQLite database configuration on startup
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Merchant-as-a-Tool Agent Gateway API",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow React dev server (localhost:5173) to call the API.
# Only this specific origin is whitelisted — no wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ToolExecutionRequest(BaseModel):
    tool: str = Field(..., description="Name of the tool to execute")
    arguments: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arguments to pass to the tool")


@app.get("/health", response_model=Dict[str, str])
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/health/llm")
def llm_health_check() -> Dict[str, Any]:
    """Health check for configured LLM provider and model."""
    from app.llm import check_llm_health
    return check_llm_health()


@app.post("/tools/execute")
def api_execute_tool(request: ToolExecutionRequest, response: Response):
    """Execute a tool dynamically."""
    result = execute_tool(request.tool, request.arguments)
    
    if not result.get("success"):
        error_code = result.get("error", {}).get("code")
        if error_code == "TOOL_NOT_FOUND":
            response.status_code = 404
        elif error_code == "INVALID_ARGUMENTS":
            response.status_code = 422
        else:
            response.status_code = 400
            
    return result


class InitiatePaymentRequest(BaseModel):
    order_id: str = Field(..., min_length=1, description="Internal order ID to initiate payment for")


@app.post("/payment/initiate")
def api_initiate_payment(request: InitiatePaymentRequest, response: Response):
    """
    Initiate checkout payment for a pending order.
    Designed for frontend checkout flow, returning safe data without secrets.
    """
    from app.payment import RazorpayPaymentService, PaymentStateError
    
    try:
        service = RazorpayPaymentService()
        result = service.initiate_checkout_payment(request.order_id)
        return result
    except PaymentStateError as e:
        response.status_code = 400
        return {"success": False, "error": str(e)}
    except ValueError as e:
        response.status_code = 404
        return {"success": False, "error": str(e)}
    except Exception as e:
        response.status_code = 500
        return {"success": False, "error": "Internal server error during payment initiation"}


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str = Field(..., description="The Razorpay payment ID")
    razorpay_order_id: str = Field(..., description="The Razorpay order ID")
    razorpay_signature: str = Field(..., description="The Razorpay signature")


@app.post("/payment/verify")
def api_verify_payment(request: VerifyPaymentRequest, response: Response):
    """
    Verify payment signature from Razorpay.
    Transitions payment to PAID if valid.
    """
    from app.payment import RazorpayPaymentService, PaymentStateError, PaymentProviderError
    
    try:
        service = RazorpayPaymentService()
        result = service.verify_payment_signature(
            razorpay_payment_id=request.razorpay_payment_id,
            razorpay_order_id=request.razorpay_order_id,
            razorpay_signature=request.razorpay_signature
        )
        return result
    except PaymentStateError as e:
        response.status_code = 400
        return {"success": False, "error": str(e)}
    except PaymentProviderError as e:
        response.status_code = 400
        return {"success": False, "error": str(e)}
    except ValueError as e:
        response.status_code = 404
        return {"success": False, "error": str(e)}
    except Exception as e:
        response.status_code = 500
        return {"success": False, "error": "Internal server error during payment verification"}


# ---------------------------------------------------------------------------
# Agent Chat endpoint
# ---------------------------------------------------------------------------

class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Natural-language shopping goal for the AI buyer agent")


class ToolCallSummary(BaseModel):
    tool_name: str
    success: bool
    error: Optional[str] = None


class SessionData(BaseModel):
    cart_id: Optional[str] = None
    order_id: Optional[str] = None


class AgentChatResponse(BaseModel):
    success: bool
    message: str
    stop_reason: str
    tool_calls_made: int
    tool_call_log: List[ToolCallSummary]
    session_data: SessionData = SessionData()


def _build_tool_call_log(history: list) -> tuple[List[ToolCallSummary], SessionData]:
    """Extract a structured tool-call summary and session data from the agent history."""
    import json
    log: List[ToolCallSummary] = []
    session = SessionData()
    # Pair each assistant turn (with tool_calls) with the following tool result messages
    i = 0
    while i < len(history):
        entry = history[i]
        if entry.get("role") == "assistant" and entry.get("tool_calls"):
            for raw_call in entry["tool_calls"]:
                tool_name = raw_call.get("function", {}).get("name", "unknown")
                # The corresponding tool result follows immediately
                i += 1
                if i < len(history) and history[i].get("role") == "tool":
                    try:
                        result = json.loads(history[i]["content"])
                        success = result.get("success", False)
                        log.append(ToolCallSummary(
                            tool_name=tool_name,
                            success=success,
                            error=result.get("error"),
                        ))
                        # Extract session identifiers from successful tool results
                        if success:
                            data = result.get("data") or {}
                            if isinstance(data, dict):
                                if tool_name in ("create_cart", "add_to_cart", "get_cart", "update_cart_item", "remove_from_cart"):
                                    cid = data.get("cart_id")
                                    if cid:
                                        session.cart_id = cid
                                elif tool_name in ("create_order", "get_order"):
                                    oid = data.get("order_id")
                                    if oid:
                                        session.order_id = oid
                    except Exception:
                        log.append(ToolCallSummary(tool_name=tool_name, success=False, error="Could not parse result"))
                else:
                    log.append(ToolCallSummary(tool_name=tool_name, success=False, error="No result received"))
                    i -= 1  # didn't consume a tool message, stay
        i += 1
    return log, session


@app.post("/agent/chat", response_model=AgentChatResponse)
def agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    """
    Send a natural-language shopping goal to the AI buyer agent.

    The agent autonomously uses registered tools (search, cart, order) to
    fulfil the request. All tool calls go through the secure gateway —
    the model cannot access the database directly.
    """
    try:
        agent = BuyerAgent()
        result: AgentResult = agent.run(request.message)
        tool_log, session = _build_tool_call_log(result.history)
        return AgentChatResponse(
            success=result.success,
            message=result.final_response,
            stop_reason=result.stop_reason,
            tool_calls_made=result.tool_calls_made,
            tool_call_log=tool_log,
            session_data=session,
        )
    except Exception:
        # Never expose stack traces to the client
        return AgentChatResponse(
            success=False,
            message="An internal error occurred. Please try again.",
            stop_reason="error",
            tool_calls_made=0,
            tool_call_log=[],
            session_data=SessionData(),
        )


# ---------------------------------------------------------------------------
# Dashboard read-only endpoints
# ---------------------------------------------------------------------------

@app.get("/dashboard/products")
def dashboard_get_products():
    """Read-only product catalog retrieval for dashboard."""
    from app.database import list_products
    products = list_products()
    return {
        "success": True,
        "data": [p.model_dump() for p in products]
    }


@app.get("/dashboard/carts")
def dashboard_get_carts(limit: int = 50):
    """Read-only carts retrieval for dashboard."""
    from app.database import list_carts
    carts = list_carts(limit=limit)
    return {
        "success": True,
        "data": [c.model_dump() for c in carts]
    }


@app.get("/dashboard/orders")
def dashboard_get_orders(limit: int = 50):
    """Read-only orders retrieval for dashboard."""
    from app.database import list_orders
    orders = list_orders(limit=limit)
    return {
        "success": True,
        "data": [o.model_dump() for o in orders]
    }


@app.get("/dashboard/cart/{cart_id}")
def dashboard_get_cart(cart_id: str, response: Response):
    """Read-only cart retrieval for dashboard."""
    from app.database import fetch_cart
    cart = fetch_cart(cart_id)
    if not cart:
        response.status_code = 404
        return {"success": False, "error": "Cart not found"}
    return {"success": True, "data": cart.model_dump()}


@app.get("/dashboard/order/{order_id}")
def dashboard_get_order(order_id: str, response: Response):
    """Read-only order retrieval for dashboard."""
    from app.database import fetch_order
    order = fetch_order(order_id)
    if not order:
        response.status_code = 404
        return {"success": False, "error": "Order not found"}
    return {"success": True, "data": order.model_dump()}


@app.get("/dashboard/audit")
def dashboard_get_audit(limit: int = 50):
    """Read-only audit trail for dashboard."""
    from app.audit import AuditLogger
    logger = AuditLogger()
    entries = logger.get_recent(limit=limit)
    return {
        "success": True,
        "data": [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "actor": e.actor,
                "action": e.action,
                "policy_decision": e.policy_decision,
                "reason": e.reason,
                "success": e.success,
                "error_code": e.error_code,
                "arguments": e.arguments,
                "result": e.result,
            }
            for e in entries
        ]
    }


@app.get("/dashboard/tools")
def dashboard_get_tools():
    """Read-only list of registered and allowed tools for dashboard."""
    from app.tools import TOOLS
    return {
        "success": True,
        "data": [
            {
                "name": tool.name,
                "description": tool.description,
            }
            for tool in TOOLS.values()
        ]
    }


@app.get("/dashboard/guardrails")
def dashboard_get_guardrails():
    """Read-only guardrail policy configuration for dashboard."""
    from app.guardrails import default_policy
    return {
        "success": True,
        "data": {
            "max_order_value": default_policy.max_order_value,
            "max_item_quantity": default_policy.max_quantity_per_item,
            "allowed_categories": default_policy.allowed_categories,
            "require_payment_confirmation": default_policy.require_payment_confirmation,
        }
    }


@app.get("/dashboard/session")
def dashboard_get_session():
    """
    Read-only endpoint returning the most recently created cart and order IDs.
    Used by the dashboard to auto-populate Commerce/Payment sections after an
    agent interaction without requiring the user to manually type IDs.
    """
    from app.database import get_db_connection
    conn = get_db_connection()
    try:
        cart_row = conn.execute(
            "SELECT cart_id FROM carts ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        order_row = conn.execute(
            "SELECT order_id FROM orders ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return {
            "success": True,
            "data": {
                "cart_id": cart_row["cart_id"] if cart_row else None,
                "order_id": order_row["order_id"] if order_row else None,
            }
        }
    finally:
        conn.close()
