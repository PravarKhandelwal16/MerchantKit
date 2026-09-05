"""
Tool-calling interface between Qwen3/Ollama and the existing tool gateway.

Responsibilities:
  1. Convert provider-independent ToolDefinitions → Ollama wire format (no duplication).
  2. Parse Ollama tool-call responses.
  3. Route tool requests through execute_tool() — the only authorised entry point.
  4. Return tool results formatted as Ollama "tool" role messages.

Nothing in here talks directly to the database, cart, or order logic.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.tools import TOOLS, ToolDefinition
from app.executor import execute_tool


# ---------------------------------------------------------------------------
# JSON-Schema helpers
# ---------------------------------------------------------------------------

_PYTHON_TYPE_MAP: Dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
}


def _pydantic_to_json_schema(model: type[BaseModel]) -> Dict[str, Any]:
    """
    Convert a Pydantic model's fields into a minimal JSON Schema object
    suitable for Ollama's tools[].function.parameters format.

    Only the top-level fields are introspected — nested structures
    are serialised as 'object' type. This is sufficient for all
    current tool schemas (flat argument bags).
    """
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for name, field_info in model.model_fields.items():
        annotation = field_info.annotation

        # Unwrap Optional[X] → X
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", ())
        if origin is type(None):
            continue
        if origin is not None and type(None) in args:
            # Optional[X] — pick the non-None arg
            inner = next((a for a in args if a is not type(None)), str)
            annotation = inner

        type_name = getattr(annotation, "__name__", str(annotation))
        json_type = _PYTHON_TYPE_MAP.get(type_name, "string")

        prop: Dict[str, Any] = {"type": json_type}
        if field_info.description:
            prop["description"] = field_info.description

        # Numeric constraints
        if field_info.metadata:
            for meta in field_info.metadata:
                ge = getattr(meta, "ge", None)
                if ge is not None:
                    prop["minimum"] = ge

        properties[name] = prop

        # A field is required when it has no default
        if field_info.is_required():
            required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


# ---------------------------------------------------------------------------
# Public: build the tools list sent to Ollama
# ---------------------------------------------------------------------------

def build_ollama_tools() -> List[Dict[str, Any]]:
    """
    Convert all registered ToolDefinitions into Ollama's tool wire format.

    The existing TOOLS registry remains the single source of truth —
    nothing is duplicated here.
    """
    result: List[Dict[str, Any]] = []
    for tool_def in TOOLS.values():
        schema = _pydantic_to_json_schema(tool_def.input_schema)
        result.append({
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": schema,
            },
        })
    return result


def build_gemini_tools() -> List[Any]:
    """
    Convert all registered ToolDefinitions into Google GenAI Tool format.

    The existing TOOLS registry remains the single source of truth.
    """
    from google.genai import types
    declarations = []
    for tool_def in TOOLS.values():
        schema = _pydantic_to_json_schema(tool_def.input_schema)
        declarations.append(
            types.FunctionDeclaration(
                name=tool_def.name,
                description=tool_def.description,
                parameters=schema,
            )
        )
    return [types.Tool(function_declarations=declarations)]


# ---------------------------------------------------------------------------
# Dataclasses for tool-call parsing
# ---------------------------------------------------------------------------

@dataclass
class ToolCallRequest:
    """A single tool call extracted from an Ollama response."""
    tool_name: str
    arguments: Dict[str, Any]


@dataclass
class ToolCallResult:
    """The structured result after routing a ToolCallRequest through the gateway."""
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Public: parse tool calls out of an Ollama message payload
# ---------------------------------------------------------------------------

def parse_tool_calls(message: Dict[str, Any]) -> List[ToolCallRequest]:
    """
    Extract tool call requests from an Ollama /api/chat response message.

    Ollama format:
        {
          "role": "assistant",
          "content": "",
          "tool_calls": [
            {"function": {"name": "...", "arguments": {...}}}
          ]
        }

    Returns an empty list if the message contains no tool calls or if
    the format is malformed (never raises).
    """
    raw_calls = message.get("tool_calls") or []
    requests: List[ToolCallRequest] = []

    for raw in raw_calls:
        try:
            func = raw.get("function", {})
            name = func.get("name", "")
            args = func.get("arguments", {})

            # Ollama may return arguments as a JSON string in some versions
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    args = {}

            if not isinstance(args, dict):
                args = {}

            if name:
                requests.append(ToolCallRequest(tool_name=name, arguments=args))
        except Exception:
            # Silently skip malformed individual calls — caller sees an empty list
            continue

    return requests


# ---------------------------------------------------------------------------
# Public: dispatch a tool call through the secure gateway
# ---------------------------------------------------------------------------

def dispatch_tool_call(
    request: ToolCallRequest,
    actor: str = "api",
) -> ToolCallResult:
    """
    Route a ToolCallRequest through execute_tool() and return a ToolCallResult.

    All security checks (unknown tool, malformed arguments, execution errors)
    are delegated to execute_tool — this function never bypasses the gateway.

    Parameters
    ----------
    actor:
        Identifier recorded in the audit log for this call.
        Pass "buyer_agent" when called from the autonomous agent loop.
    """
    result = execute_tool(request.tool_name, request.arguments, actor=actor)

    if result.get("success"):
        return ToolCallResult(
            tool_name=request.tool_name,
            success=True,
            data=result.get("data"),
        )

    error_block = result.get("error", {})
    code = error_block.get("code", "UNKNOWN_ERROR")
    message = error_block.get("message", "An unknown error occurred.")
    return ToolCallResult(
        tool_name=request.tool_name,
        success=False,
        error=f"[{code}] {message}",
    )


# ---------------------------------------------------------------------------
# Public: format a tool result as an Ollama "tool" role message
# ---------------------------------------------------------------------------

def format_tool_result_message(result: ToolCallResult) -> Dict[str, Any]:
    """
    Package a ToolCallResult as an Ollama message dict with role="tool".

    The content is always a JSON string so the model can parse it reliably.
    Pydantic models are serialised via model_dump(); everything else falls
    back to str() so the function never raises.
    """
    if result.success:
        data = result.data
        # Serialise Pydantic models
        if hasattr(data, "model_dump"):
            payload = {"success": True, "data": data.model_dump()}
        elif isinstance(data, list):
            items = []
            for item in data:
                items.append(item.model_dump() if hasattr(item, "model_dump") else item)
            payload = {"success": True, "data": items}
        else:
            payload = {"success": True, "data": data}
    else:
        payload = {"success": False, "error": result.error}

    try:
        content = json.dumps(payload, default=str)
    except Exception:
        content = json.dumps({"success": False, "error": "Could not serialise tool result."})

    return {"role": "tool", "name": result.tool_name, "content": content}
