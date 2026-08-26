from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings


# ---------------------------------------------------------------------------
# Provider-independent message types
# ---------------------------------------------------------------------------

@dataclass
class LLMMessage:
    """A single turn in a conversation. role is 'system', 'user', or 'assistant'."""
    role: str
    content: str
    # Only set for assistant turns that contain tool invocations (round-tripped to Ollama)
    tool_calls: Optional[List[Dict[str, Any]]] = None


@dataclass
class LLMResponse:
    """Structured result returned by the LLM client."""
    content: str                        # The assistant reply text
    model: str                          # Which model produced the response
    success: bool                       # False when an error occurred
    error: Optional[str] = None         # Error description when success=False
    tool_calls: Optional[List[Dict[str, Any]]] = None  # Raw tool_calls list if model requested tools
    raw: Optional[Dict[str, Any]] = field(default=None, repr=False)  # Full raw payload


# ---------------------------------------------------------------------------
# Core chat function
# ---------------------------------------------------------------------------

def _serialise_message(m: LLMMessage) -> Dict[str, Any]:
    """Serialise an LLMMessage to the Ollama wire format dict."""
    d: Dict[str, Any] = {"role": m.role, "content": m.content}
    if m.tool_calls is not None:
        d["tool_calls"] = m.tool_calls
    return d


def send_message(
    messages: List[LLMMessage],
    *,
    model: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    timeout: float = 180.0,
    stream: bool = False,
) -> LLMResponse:
    """
    Send a conversation to the configured Ollama model and return an LLMResponse.

    Parameters
    ----------
    messages:
        Ordered list of LLMMessage objects representing the conversation so far.
    model:
        Override the model from settings (useful for testing).
    timeout:
        HTTP request timeout in seconds.
    stream:
        If True, requests streaming from Ollama. Currently not consumed here
        (kept provider-independent — callers can inspect raw bytes if needed).

    Returns
    -------
    LLMResponse with success=True on success, success=False with an error
    message on any connection or API problem.
    """
    active_model = model or settings.ollama_model
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload: Dict[str, Any] = {
        "model": active_model,
        "messages": [_serialise_message(m) for m in messages],
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        # Ollama /api/chat non-streaming response:
        # { "message": { "role": "assistant", "content": "...", "tool_calls": [...] }, "model": "..." }
        msg = data.get("message", {})
        assistant_content = msg.get("content", "")
        returned_model = data.get("model", active_model)
        raw_tool_calls = msg.get("tool_calls") or None

        return LLMResponse(
            content=assistant_content,
            model=returned_model,
            success=True,
            tool_calls=raw_tool_calls,
            raw=data,
        )

    except httpx.ConnectError as exc:
        return LLMResponse(
            content="",
            model=active_model,
            success=False,
            error=f"Could not connect to Ollama at {settings.ollama_base_url}: {exc}",
        )
    except httpx.TimeoutException as exc:
        return LLMResponse(
            content="",
            model=active_model,
            success=False,
            error=f"Request to Ollama timed out: {exc}",
        )
    except httpx.HTTPStatusError as exc:
        return LLMResponse(
            content="",
            model=active_model,
            success=False,
            error=f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}",
        )
    except Exception as exc:
        return LLMResponse(
            content="",
            model=active_model,
            success=False,
            error=f"Unexpected error communicating with Ollama: {exc}",
        )


# ---------------------------------------------------------------------------
# Health / diagnostic helpers (retained from Part 1)
# ---------------------------------------------------------------------------

def get_ollama_tags(timeout: float = 3.0) -> Dict[str, Any]:
    """Query Ollama /api/tags to list installed local models."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        response = httpx.get(url, timeout=timeout)
        if response.status_code == 200:
            return response.json()
        return {"error": f"HTTP {response.status_code}: {response.text}", "models": []}
    except Exception as exc:
        return {"error": str(exc), "models": []}


def check_ollama_health() -> Dict[str, Any]:
    """Check Ollama service connectivity and model availability."""
    data = get_ollama_tags()
    is_reachable = "error" not in data or not data["error"]
    models: List[str] = [
        m.get("name", "") for m in data.get("models", []) if isinstance(m, dict)
    ]
    configured_model = settings.ollama_model
    model_found = any(
        m == configured_model or m.startswith(f"{configured_model}:") or configured_model.startswith(m)
        for m in models
    )
    return {
        "reachable": is_reachable,
        "base_url": settings.ollama_base_url,
        "configured_model": configured_model,
        "model_available": model_found,
        "available_models": models,
        "error": data.get("error"),
    }

