"""
Tests for Part 5B: Tool-Calling Interface.

All external calls (httpx, database, cart, order) are mocked.
No running Ollama server or database required.
"""
import json
import pytest
import httpx
from unittest.mock import MagicMock, patch

from app.tools import TOOLS
from app.tool_interface import (
    build_ollama_tools,
    parse_tool_calls,
    dispatch_tool_call,
    format_tool_result_message,
    ToolCallRequest,
    ToolCallResult,
)
from app.llm import send_message, LLMMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _set_ollama_provider(monkeypatch):
    monkeypatch.setattr("app.config.settings.llm_provider", "ollama")

def _make_post_mock(monkeypatch, status_code: int, json_body: dict):
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = status_code
    mock_response.json.return_value = json_body
    if status_code >= 400:
        mock_response.text = str(json_body)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}", request=MagicMock(), response=mock_response
        )
    else:
        mock_response.raise_for_status.return_value = None
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: mock_response)
    return mock_response


# ===========================================================================
# 1. Tool definitions reach the LLM client (build_ollama_tools)
# ===========================================================================

class TestBuildOllamaTools:
    def test_all_tools_are_included(self):
        """Every tool in the TOOLS registry must appear in the Ollama payload."""
        ollama_tools = build_ollama_tools()
        names = {t["function"]["name"] for t in ollama_tools}
        assert names == set(TOOLS.keys())

    def test_tool_structure(self):
        """Each tool entry must have the exact Ollama-required structure."""
        for t in build_ollama_tools():
            assert t["type"] == "function"
            func = t["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            params = func["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params

    def test_no_duplication_of_definitions(self):
        """build_ollama_tools must derive from TOOLS, not hardcode anything."""
        ollama_tools = build_ollama_tools()
        for t in ollama_tools:
            name = t["function"]["name"]
            assert name in TOOLS, f"Tool '{name}' not in TOOLS registry"
            assert t["function"]["description"] == TOOLS[name].description

    def test_get_product_has_required_argument(self):
        tools = {t["function"]["name"]: t for t in build_ollama_tools()}
        gp = tools["get_product"]
        assert "product_id" in gp["function"]["parameters"]["required"]
        assert "product_id" in gp["function"]["parameters"]["properties"]

    def test_search_products_has_no_required_arguments(self):
        tools = {t["function"]["name"]: t for t in build_ollama_tools()}
        sp = tools["search_products"]
        assert sp["function"]["parameters"]["required"] == []

    def test_add_to_cart_quantity_has_minimum(self):
        tools = {t["function"]["name"]: t for t in build_ollama_tools()}
        atc = tools["add_to_cart"]
        qty = atc["function"]["parameters"]["properties"]["quantity"]
        assert qty.get("minimum") == 1

    def test_tools_sent_to_send_message(self, monkeypatch):
        """When tools are passed to send_message, they appear in the HTTP payload."""
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["payload"] = json
            mock = MagicMock(spec=httpx.Response)
            mock.raise_for_status.return_value = None
            mock.json.return_value = {
                "model": "qwen3:8b",
                "message": {"role": "assistant", "content": "", "tool_calls": []},
            }
            return mock

        monkeypatch.setattr(httpx, "post", fake_post)
        ollama_tools = build_ollama_tools()
        send_message([LLMMessage(role="user", content="hi")], tools=ollama_tools)
        assert "tools" in captured["payload"]
        assert len(captured["payload"]["tools"]) == len(TOOLS)


# ===========================================================================
# 2. Parse tool calls from Ollama response
# ===========================================================================

class TestParseToolCalls:
    def test_valid_tool_call(self):
        message = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "get_product", "arguments": {"product_id": "p1"}}}
            ],
        }
        calls = parse_tool_calls(message)
        assert len(calls) == 1
        assert calls[0].tool_name == "get_product"
        assert calls[0].arguments == {"product_id": "p1"}

    def test_multiple_tool_calls(self):
        message = {
            "tool_calls": [
                {"function": {"name": "create_cart", "arguments": {}}},
                {"function": {"name": "get_order", "arguments": {"order_id": "ord_1"}}},
            ]
        }
        calls = parse_tool_calls(message)
        assert len(calls) == 2
        assert calls[0].tool_name == "create_cart"
        assert calls[1].tool_name == "get_order"

    def test_no_tool_calls_returns_empty(self):
        message = {"role": "assistant", "content": "Hello!"}
        assert parse_tool_calls(message) == []

    def test_null_tool_calls_returns_empty(self):
        message = {"tool_calls": None}
        assert parse_tool_calls(message) == []

    def test_arguments_as_json_string(self):
        """Some Ollama versions return arguments as a JSON string."""
        message = {
            "tool_calls": [
                {"function": {"name": "get_product", "arguments": '{"product_id": "abc"}'}}
            ]
        }
        calls = parse_tool_calls(message)
        assert calls[0].arguments == {"product_id": "abc"}

    def test_malformed_tool_call_skipped(self):
        """A call with a completely broken structure should be silently skipped."""
        message = {"tool_calls": [None, 42, {"function": {"name": "get_product", "arguments": {}}}]}
        calls = parse_tool_calls(message)
        assert any(c.tool_name == "get_product" for c in calls)

    def test_empty_tool_calls_list(self):
        assert parse_tool_calls({"tool_calls": []}) == []


# ===========================================================================
# 3. A valid tool call reaches the gateway
# ===========================================================================

class TestDispatchToolCall:
    def test_valid_tool_call_routes_through_gateway(self):
        """dispatch_tool_call must use execute_tool, not call DB directly."""
        with patch("app.tool_interface.execute_tool") as mock_exec:
            mock_exec.return_value = {"success": True, "tool": "get_product", "data": {"product_id": "p1"}}
            req = ToolCallRequest(tool_name="get_product", arguments={"product_id": "p1"})
            result = dispatch_tool_call(req)
            mock_exec.assert_called_once_with("get_product", {"product_id": "p1"}, actor="api")
            assert result.success is True
            assert result.data == {"product_id": "p1"}

    def test_successful_dispatch_result(self):
        with patch("app.tool_interface.execute_tool") as mock_exec:
            mock_exec.return_value = {"success": True, "tool": "create_cart", "data": "cart_data"}
            req = ToolCallRequest(tool_name="create_cart", arguments={})
            result = dispatch_tool_call(req)
            assert result.success is True
            assert result.tool_name == "create_cart"
            assert result.error is None


# ===========================================================================
# 4. Unknown tools are rejected
# ===========================================================================

class TestUnknownToolRejection:
    def test_unknown_tool_name_rejected(self):
        req = ToolCallRequest(tool_name="drop_table", arguments={})
        result = dispatch_tool_call(req)
        assert result.success is False
        assert result.error is not None
        assert "TOOL_NOT_FOUND" in result.error

    def test_empty_tool_name_rejected(self):
        req = ToolCallRequest(tool_name="", arguments={})
        result = dispatch_tool_call(req)
        assert result.success is False

    def test_sql_injection_tool_name_rejected(self):
        req = ToolCallRequest(tool_name="'; DROP TABLE products; --", arguments={})
        result = dispatch_tool_call(req)
        assert result.success is False
        assert result.error is not None

    def test_exec_tool_name_rejected(self):
        req = ToolCallRequest(tool_name="exec", arguments={"code": "import os"})
        result = dispatch_tool_call(req)
        assert result.success is False


# ===========================================================================
# 5. Malformed arguments are rejected
# ===========================================================================

class TestMalformedArgumentsRejection:
    def test_missing_required_argument(self):
        """get_product requires product_id — omitting it must fail validation."""
        req = ToolCallRequest(tool_name="get_product", arguments={})
        result = dispatch_tool_call(req)
        assert result.success is False
        assert "INVALID_ARGUMENTS" in result.error

    def test_wrong_type_for_quantity(self):
        req = ToolCallRequest(
            tool_name="add_to_cart",
            arguments={"cart_id": "c1", "product_id": "p1", "quantity": "not-a-number"},
        )
        result = dispatch_tool_call(req)
        assert result.success is False

    def test_non_dict_arguments_rejected(self):
        req = ToolCallRequest(tool_name="get_product", arguments="not-a-dict")  # type: ignore
        result = dispatch_tool_call(req)
        assert result.success is False


# ===========================================================================
# 6. Tool results can be returned to the model
# ===========================================================================

class TestFormatToolResultMessage:
    def test_success_result_formatted(self):
        result = ToolCallResult(tool_name="get_product", success=True, data={"product_id": "p1", "name": "Widget"})
        msg = format_tool_result_message(result)
        assert msg["role"] == "tool"
        payload = json.loads(msg["content"])
        assert payload["success"] is True
        assert payload["data"]["product_id"] == "p1"

    def test_error_result_formatted(self):
        result = ToolCallResult(tool_name="get_product", success=False, error="[TOOL_NOT_FOUND] Unknown tool")
        msg = format_tool_result_message(result)
        assert msg["role"] == "tool"
        payload = json.loads(msg["content"])
        assert payload["success"] is False
        assert "TOOL_NOT_FOUND" in payload["error"]

    def test_none_data_formatted_safely(self):
        result = ToolCallResult(tool_name="get_cart", success=True, data=None)
        msg = format_tool_result_message(result)
        assert msg["role"] == "tool"
        payload = json.loads(msg["content"])
        assert payload["success"] is True

    def test_list_data_formatted(self):
        result = ToolCallResult(tool_name="search_products", success=True, data=[{"product_id": "p1"}, {"product_id": "p2"}])
        msg = format_tool_result_message(result)
        payload = json.loads(msg["content"])
        assert isinstance(payload["data"], list)
        assert len(payload["data"]) == 2

    def test_content_is_always_valid_json(self):
        """format_tool_result_message must never produce invalid JSON."""
        result = ToolCallResult(tool_name="bad", success=True, data=object())  # unserializable
        msg = format_tool_result_message(result)
        # Should not raise
        payload = json.loads(msg["content"])
        assert "success" in payload

    def test_tool_calls_in_llm_response(self, monkeypatch):
        """LLMResponse.tool_calls is populated when Ollama includes tool_calls."""
        _make_post_mock(monkeypatch, 200, {
            "model": "qwen3:8b",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "get_product", "arguments": {"product_id": "p1"}}}],
            },
        })
        response = send_message(
            [LLMMessage(role="user", content="Tell me about product p1")],
            tools=build_ollama_tools(),
        )
        assert response.success is True
        assert response.tool_calls is not None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "get_product"
