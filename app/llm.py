"""
LLM Provider Abstraction & Providers (Gemini Cloud & Local Ollama).

Supports:
- Gemini Provider via official google-genai SDK (Primary)
- Ollama Provider via HTTP API (Optional fallback)
- Unified normalized response format (LLMResponse)
- Multi-step tool calls with function responses
- Safe credential and error handling
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx
from app.config import settings


# ---------------------------------------------------------------------------
# Provider-independent message types
# ---------------------------------------------------------------------------

@dataclass
class LLMMessage:
    """A single turn in a conversation. role is 'system', 'user', 'assistant', or 'tool'."""
    role: str
    content: str
    # Only set for assistant turns that contain tool invocations
    tool_calls: Optional[List[Dict[str, Any]]] = None
    # Tool name for role='tool' turns
    name: Optional[str] = None


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
# Provider Base Class
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """Abstract interface for LLM backends."""

    @abstractmethod
    def send_message(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        timeout: float = 120.0,
        stream: bool = False,
    ) -> LLMResponse:
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        pass


# ---------------------------------------------------------------------------
# Ollama Provider (Local)
# ---------------------------------------------------------------------------

def _serialise_ollama_message(m: LLMMessage) -> Dict[str, Any]:
    """Serialise an LLMMessage to the Ollama wire format dict."""
    d: Dict[str, Any] = {"role": m.role, "content": m.content}
    if m.tool_calls is not None:
        d["tool_calls"] = m.tool_calls
    return d


class OllamaProvider(LLMProvider):
    """Local Ollama client."""

    def send_message(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        timeout: float = 240.0,
        stream: bool = False,
    ) -> LLMResponse:
        active_model = model or settings.ollama_model
        url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        payload: Dict[str, Any] = {
            "model": active_model,
            "messages": [_serialise_ollama_message(m) for m in messages],
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        try:
            response = httpx.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()

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

    def check_health(self) -> Dict[str, Any]:
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
            "provider": "ollama",
            "reachable": is_reachable,
            "status": "online" if (is_reachable and model_found) else "offline",
            "base_url": settings.ollama_base_url,
            "configured_model": configured_model,
            "model_available": model_found,
            "available_models": models,
            "error": data.get("error"),
        }


# ---------------------------------------------------------------------------
# Gemini Provider (Google GenAI Cloud)
# ---------------------------------------------------------------------------

class GeminiProvider(LLMProvider):
    """Cloud Gemini client using official google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        self._default_model = model or settings.gemini_model

    def _get_client(self) -> Any:
        if not self._api_key:
            raise ValueError(
                "Gemini API key is not configured. Please set GEMINI_API_KEY in .env."
            )
        from google import genai
        return genai.Client(api_key=self._api_key)

    def _convert_messages(
        self, messages: List[LLMMessage]
    ) -> Tuple[Optional[str], List[Any]]:
        """Convert LLMMessage list to (system_instruction, contents) for Gemini."""
        from google.genai import types

        system_instruction: Optional[str] = None
        contents: List[types.Content] = []
        pending_tool_names: List[str] = []

        i = 0
        while i < len(messages):
            m = messages[i]
            if m.role == "system":
                system_instruction = m.content
                i += 1
                continue

            if m.role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=m.content)],
                    )
                )
                i += 1
                continue

            if m.role == "assistant":
                parts: List[types.Part] = []
                if m.content:
                    parts.append(types.Part.from_text(text=m.content))
                if m.tool_calls:
                    pending_tool_names = []
                    for tc in m.tool_calls:
                        func = tc.get("function", {})
                        fn_name = func.get("name", "")
                        fn_args = func.get("arguments", {})
                        if isinstance(fn_args, str):
                            try:
                                fn_args = json.loads(fn_args)
                            except Exception:
                                fn_args = {}
                        call_id = tc.get("id")
                        thought_sig = tc.get("thought_signature")
                        fc = types.FunctionCall(name=fn_name, args=fn_args, id=call_id)
                        if thought_sig is not None:
                            parts.append(
                                types.Part(function_call=fc, thought_signature=thought_sig)
                            )
                        else:
                            parts.append(
                                types.Part.from_function_call(name=fn_name, args=fn_args)
                            )
                        pending_tool_names.append(fn_name)
                if not parts:
                    parts.append(types.Part.from_text(text=""))
                contents.append(types.Content(role="model", parts=parts))
                i += 1
                continue

            if m.role == "tool":
                tool_parts: List[types.Part] = []
                tool_idx = 0
                while i < len(messages) and messages[i].role == "tool":
                    tm = messages[i]
                    fn_name = tm.name
                    if not fn_name:
                        if tool_idx < len(pending_tool_names):
                            fn_name = pending_tool_names[tool_idx]
                        else:
                            fn_name = "tool_result"
                    try:
                        res_dict = (
                            json.loads(tm.content)
                            if isinstance(tm.content, str)
                            else tm.content
                        )
                        if not isinstance(res_dict, dict):
                            res_dict = {"result": res_dict}
                    except Exception:
                        res_dict = {"result": tm.content}
                    tool_parts.append(
                        types.Part.from_function_response(
                            name=fn_name, response=res_dict
                        )
                    )
                    tool_idx += 1
                    i += 1
                contents.append(types.Content(role="user", parts=tool_parts))
                continue

            i += 1

        return system_instruction, contents

    def _convert_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Any]]:
        """Convert tools definition to Gemini types.Tool."""
        if not tools:
            return None
        from google.genai import types

        declarations: List[types.FunctionDeclaration] = []
        for t in tools:
            if isinstance(t, dict) and "function" in t:
                func = t["function"]
                declarations.append(
                    types.FunctionDeclaration(
                        name=func.get("name", ""),
                        description=func.get("description", ""),
                        parameters=func.get("parameters", {}),
                    )
                )
            elif isinstance(t, types.FunctionDeclaration):
                declarations.append(t)
            elif isinstance(t, types.Tool):
                return [t]

        if not declarations:
            return None
        return [types.Tool(function_declarations=declarations)]

    def send_message(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        timeout: float = 120.0,
        stream: bool = False,
    ) -> LLMResponse:
        active_model = model or self._default_model
        try:
            client = self._get_client()
        except ValueError as exc:
            return LLMResponse(
                content="",
                model=active_model,
                success=False,
                error=str(exc),
            )

        from google.genai import types
        from google.genai.errors import APIError, ClientError

        try:
            system_instruction, contents = self._convert_messages(messages)
            gemini_tools = self._convert_tools(tools)

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=gemini_tools,
                temperature=0.0,
            )

            response = client.models.generate_content(
                model=active_model,
                contents=contents,
                config=config,
            )

            assistant_content = ""
            tool_calls: Optional[List[Dict[str, Any]]] = None

            if response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if getattr(part, "text", None):
                            assistant_content += part.text
                        if getattr(part, "function_call", None):
                            if tool_calls is None:
                                tool_calls = []
                            fc = part.function_call
                            fn_args = dict(fc.args) if fc.args else {}
                            call_id = getattr(fc, "id", None)
                            thought_sig = getattr(part, "thought_signature", None)
                            tc_dict: Dict[str, Any] = {
                                "function": {
                                    "name": fc.name,
                                    "arguments": fn_args,
                                },
                            }
                            if call_id:
                                tc_dict["id"] = call_id
                            if thought_sig is not None:
                                tc_dict["thought_signature"] = thought_sig
                            tool_calls.append(tc_dict)

            return LLMResponse(
                content=assistant_content,
                model=active_model,
                success=True,
                tool_calls=tool_calls,
                raw={"content": assistant_content, "tool_calls": tool_calls},
            )

        except ClientError as exc:
            msg = str(exc)
            if "API_KEY_INVALID" in msg or "API key not valid" in msg:
                error_desc = "Gemini API authentication failed: Invalid API key. Please check GEMINI_API_KEY in .env."
            elif "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                error_desc = "Gemini API rate limit exceeded. Please try again shortly."
            else:
                error_desc = f"Gemini client error: {exc}"
            return LLMResponse(
                content="",
                model=active_model,
                success=False,
                error=error_desc,
            )
        except APIError as exc:
            return LLMResponse(
                content="",
                model=active_model,
                success=False,
                error=f"Gemini API error: {exc}",
            )
        except Exception as exc:
            err_type = type(exc).__name__
            if "Timeout" in err_type or "deadline" in str(exc).lower():
                error_desc = f"Gemini request timed out: {exc}"
            elif "Connect" in err_type or "Network" in err_type:
                error_desc = f"Unable to connect to Gemini API: {exc}"
            else:
                error_desc = f"Unexpected error communicating with Gemini: {exc}"
            return LLMResponse(
                content="",
                model=active_model,
                success=False,
                error=error_desc,
            )

    def check_health(self) -> Dict[str, Any]:
        if not self._api_key:
            return {
                "provider": "gemini",
                "configured": False,
                "status": "offline",
                "model": self._default_model,
                "error": "GEMINI_API_KEY is not configured.",
            }
        try:
            client = self._get_client()
            client.models.get(model=self._default_model)
            return {
                "provider": "gemini",
                "configured": True,
                "status": "online",
                "model": self._default_model,
            }
        except Exception as exc:
            return {
                "provider": "gemini",
                "configured": True,
                "status": "offline",
                "model": self._default_model,
                "error": str(exc),
            }


# ---------------------------------------------------------------------------
# Factory & Dispatcher
# ---------------------------------------------------------------------------

def get_llm_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """
    Factory function returning the configured or requested LLM provider.
    Raises ValueError for unsupported providers (never silently fall back).
    """
    name = (provider_name or settings.llm_provider).lower().strip()
    if name == "gemini":
        return GeminiProvider()
    elif name == "ollama":
        return OllamaProvider()
    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{name}'. Allowed values are 'gemini' or 'ollama'."
        )


def send_message(
    messages: List[LLMMessage],
    *,
    model: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    timeout: float = 120.0,
    stream: bool = False,
    provider: Optional[str] = None,
) -> LLMResponse:
    """
    Unified entry point to send a message turn to the active LLM provider.
    """
    try:
        client = get_llm_provider(provider)
        return client.send_message(
            messages,
            model=model,
            tools=tools,
            timeout=timeout,
            stream=stream,
        )
    except ValueError as exc:
        return LLMResponse(
            content="",
            model=model or "",
            success=False,
            error=str(exc),
        )


def check_llm_health(provider_name: Optional[str] = None) -> Dict[str, Any]:
    """Check health of the configured or specified LLM provider."""
    try:
        client = get_llm_provider(provider_name)
        return client.check_health()
    except ValueError as exc:
        return {
            "provider": provider_name or settings.llm_provider,
            "status": "offline",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Health / diagnostic helpers (retained for backwards compatibility)
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
    """Check Ollama service connectivity and model availability (backwards compatibility)."""
    return OllamaProvider().check_health()
