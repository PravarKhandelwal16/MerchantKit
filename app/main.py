from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
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


class ToolExecutionRequest(BaseModel):
    tool: str = Field(..., description="Name of the tool to execute")
    arguments: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arguments to pass to the tool")


@app.get("/health", response_model=Dict[str, str])
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


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


class AgentChatResponse(BaseModel):
    success: bool
    message: str
    stop_reason: str
    tool_calls_made: int
    tool_call_log: List[ToolCallSummary]


def _build_tool_call_log(history: list) -> List[ToolCallSummary]:
    """Extract a structured tool-call summary from the agent history."""
    import json
    log: List[ToolCallSummary] = []
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
                        log.append(ToolCallSummary(
                            tool_name=tool_name,
                            success=result.get("success", False),
                            error=result.get("error"),
                        ))
                    except Exception:
                        log.append(ToolCallSummary(tool_name=tool_name, success=False, error="Could not parse result"))
                else:
                    log.append(ToolCallSummary(tool_name=tool_name, success=False, error="No result received"))
                    i -= 1  # didn't consume a tool message, stay
        i += 1
    return log


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
        tool_log = _build_tool_call_log(result.history)
        return AgentChatResponse(
            success=result.success,
            message=result.final_response,
            stop_reason=result.stop_reason,
            tool_calls_made=result.tool_calls_made,
            tool_call_log=tool_log,
        )
    except Exception:
        # Never expose stack traces to the client
        return AgentChatResponse(
            success=False,
            message="An internal error occurred. Please try again.",
            stop_reason="error",
            tool_calls_made=0,
            tool_call_log=[],
        )
