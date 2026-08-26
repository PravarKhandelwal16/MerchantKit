"""
Tests for POST /agent/chat API endpoint.

All LLM calls are mocked — no Ollama server or live DB writes needed.
The existing /tools/execute tests continue to work unchanged.
"""
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.agent import AgentResult
from app.tool_interface import ToolCallResult

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers — build mock AgentResult objects
# ---------------------------------------------------------------------------

def _success_result(message: str, tool_calls_made: int = 0, history: list | None = None) -> AgentResult:
    return AgentResult(
        final_response=message,
        success=True,
        tool_calls_made=tool_calls_made,
        stop_reason="complete",
        history=history or [],
    )


def _failure_result(message: str, stop_reason: str = "llm_error") -> AgentResult:
    return AgentResult(
        final_response=message,
        success=False,
        tool_calls_made=0,
        stop_reason=stop_reason,
        history=[],
    )


def _history_with_tool(tool_name: str, success: bool, data=None, error=None) -> list:
    """Build a minimal history that the tool_call_log builder can parse."""
    tool_call_entry = {
        "function": {"name": tool_name, "arguments": {}}
    }
    payload = {"success": success}
    if success:
        payload["data"] = data or {}
    else:
        payload["error"] = error or "Some error"

    return [
        {"role": "system",    "content": "..."},
        {"role": "user",      "content": "Find a mouse"},
        {"role": "assistant", "content": "", "tool_calls": [tool_call_entry]},
        {"role": "tool",      "content": json.dumps(payload)},
        {"role": "assistant", "content": "Done!", "tool_calls": None},
    ]


# ---------------------------------------------------------------------------
# 1. Request validation
# ---------------------------------------------------------------------------

class TestRequestValidation:
    def test_missing_message_field_returns_422(self):
        response = client.post("/agent/chat", json={})
        assert response.status_code == 422

    def test_empty_string_message_returns_422(self):
        response = client.post("/agent/chat", json={"message": ""})
        assert response.status_code == 422

    def test_non_string_message_returns_422(self):
        response = client.post("/agent/chat", json={"message": 12345})
        assert response.status_code == 422

    def test_extra_fields_ignored(self):
        """Pydantic should strip unknown fields without error."""
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result("OK")
            response = client.post("/agent/chat", json={"message": "hi", "price": 999})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 2. Successful agent response
# ---------------------------------------------------------------------------

class TestSuccessfulResponse:
    def test_returns_200_on_success(self):
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result("I found a wireless mouse.")
            response = client.post("/agent/chat", json={"message": "Find a wireless mouse"})
        assert response.status_code == 200

    def test_response_structure(self):
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result("Found it!", tool_calls_made=2)
            response = client.post("/agent/chat", json={"message": "Find something"})
        data = response.json()
        assert "success" in data
        assert "message" in data
        assert "stop_reason" in data
        assert "tool_calls_made" in data
        assert "tool_call_log" in data

    def test_success_true_on_complete(self):
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result("Done!")
            response = client.post("/agent/chat", json={"message": "Do something"})
        assert response.json()["success"] is True

    def test_message_content_passed_through(self):
        expected = "I added the Wireless Mouse (₹1299) to cart cart-abc."
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result(expected, tool_calls_made=3)
            response = client.post("/agent/chat", json={"message": "Add a mouse to cart"})
        assert response.json()["message"] == expected

    def test_tool_calls_made_count(self):
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result("Done", tool_calls_made=4)
            response = client.post("/agent/chat", json={"message": "Complex task"})
        assert response.json()["tool_calls_made"] == 4

    def test_stop_reason_complete(self):
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result("All done")
            response = client.post("/agent/chat", json={"message": "Simple task"})
        assert response.json()["stop_reason"] == "complete"

    def test_no_chain_of_thought_exposed(self):
        """Response must not include internal model reasoning or system prompt."""
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result("Done")
            response = client.post("/agent/chat", json={"message": "Hi"})
        data = response.json()
        assert "history" not in data
        assert "system_prompt" not in data
        assert "raw" not in data


# ---------------------------------------------------------------------------
# 3. Tool call log in response
# ---------------------------------------------------------------------------

class TestToolCallLog:
    def test_successful_tool_call_in_log(self):
        history = _history_with_tool("search_products", success=True, data={"results": []})
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = AgentResult(
                final_response="Done", success=True, tool_calls_made=1,
                stop_reason="complete", history=history,
            )
            response = client.post("/agent/chat", json={"message": "Search"})
        data = response.json()
        assert len(data["tool_call_log"]) == 1
        assert data["tool_call_log"][0]["tool_name"] == "search_products"
        assert data["tool_call_log"][0]["success"] is True
        assert data["tool_call_log"][0]["error"] is None

    def test_failed_tool_call_in_log(self):
        history = _history_with_tool("add_to_cart", success=False, error="[EXECUTION_ERROR] Cart not found")
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = AgentResult(
                final_response="Could not add item", success=True, tool_calls_made=1,
                stop_reason="complete", history=history,
            )
            response = client.post("/agent/chat", json={"message": "Add to cart"})
        data = response.json()
        log = data["tool_call_log"]
        assert len(log) == 1
        assert log[0]["success"] is False
        assert log[0]["error"] is not None

    def test_empty_log_when_no_tool_calls(self):
        """If the agent answered without tools, log should be empty."""
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result("Simple answer", history=[
                {"role": "system", "content": "..."},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ])
            response = client.post("/agent/chat", json={"message": "Hi"})
        assert response.json()["tool_call_log"] == []

    def test_multiple_tool_calls_in_log(self):
        """Two tool calls produce two entries in the log."""
        call1 = {"function": {"name": "search_products", "arguments": {}}}
        call2 = {"function": {"name": "create_cart", "arguments": {}}}
        history = [
            {"role": "system",    "content": "..."},
            {"role": "user",      "content": "Find and cart"},
            {"role": "assistant", "content": "", "tool_calls": [call1, call2]},
            {"role": "tool",      "content": json.dumps({"success": True, "data": []})},
            {"role": "tool",      "content": json.dumps({"success": True, "data": {"cart_id": "c1"}})},
            {"role": "assistant", "content": "Done!"},
        ]
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = AgentResult(
                final_response="Done", success=True, tool_calls_made=2,
                stop_reason="complete", history=history,
            )
            response = client.post("/agent/chat", json={"message": "Search and cart"})
        log = response.json()["tool_call_log"]
        assert len(log) == 2
        names = {e["tool_name"] for e in log}
        assert "search_products" in names
        assert "create_cart" in names


# ---------------------------------------------------------------------------
# 4. Failure / error responses
# ---------------------------------------------------------------------------

class TestErrorResponses:
    def test_llm_error_returns_success_false(self):
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _failure_result("AI error occurred")
            response = client.post("/agent/chat", json={"message": "Do something"})
        data = response.json()
        assert data["success"] is False

    def test_max_iterations_stop_reason(self):
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = AgentResult(
                final_response="Could not complete in time",
                success=False, tool_calls_made=10,
                stop_reason="max_iterations", history=[],
            )
            response = client.post("/agent/chat", json={"message": "Infinite task"})
        data = response.json()
        assert data["stop_reason"] == "max_iterations"
        assert data["success"] is False

    def test_internal_exception_does_not_expose_stack_trace(self):
        """If BuyerAgent raises unexpectedly, the API must return a safe error, not a 500."""
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.side_effect = RuntimeError("Something went very wrong internally")
            response = client.post("/agent/chat", json={"message": "Trigger crash"})
        # Must not be a 500 — the outer try/except in the route catches it
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "stack" not in data["message"].lower()
        assert "traceback" not in data["message"].lower()
        assert "RuntimeError" not in data["message"]

    def test_error_message_is_user_friendly(self):
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.side_effect = Exception("DB locked")
            response = client.post("/agent/chat", json={"message": "Buy stuff"})
        data = response.json()
        assert len(data["message"]) > 0
        # Should be the generic safe message
        assert "internal error" in data["message"].lower()


# ---------------------------------------------------------------------------
# 5. Agent is not instantiated with logic inside the route
# ---------------------------------------------------------------------------

class TestRouteDelegation:
    def test_buyer_agent_run_is_called_with_user_message(self):
        """The route must pass the user's exact message to agent.run()."""
        user_msg = "Find me a wireless mouse under ₹1500"
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result("Done")
            client.post("/agent/chat", json={"message": user_msg})
        MockAgent.return_value.run.assert_called_once_with(user_msg)

    def test_new_agent_created_per_request(self):
        """Each request must get a fresh BuyerAgent instance."""
        with patch("app.main.BuyerAgent") as MockAgent:
            MockAgent.return_value.run.return_value = _success_result("Done")
            client.post("/agent/chat", json={"message": "First"})
            client.post("/agent/chat", json={"message": "Second"})
        assert MockAgent.call_count == 2
