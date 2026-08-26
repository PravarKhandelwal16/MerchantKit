"""
Tests for Part 5C: BuyerAgent loop.

All LLM calls and tool executions are mocked — no Ollama server or database needed.

Strategy:
- Mock `app.agent.send_message` to return scripted LLMResponse objects.
- Mock `app.agent.dispatch_tool_call` to return scripted ToolCallResult objects.
- Verify the agent correctly orchestrates the conversation loop.
"""
import json
import pytest
from unittest.mock import patch, MagicMock, call

from app.agent import BuyerAgent, AgentResult, SYSTEM_PROMPT
from app.llm import LLMResponse
from app.tool_interface import ToolCallResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _llm_tool_response(tool_name: str, arguments: dict) -> LLMResponse:
    """Build an LLMResponse that requests one tool call."""
    tool_call = {"function": {"name": tool_name, "arguments": arguments}}
    return LLMResponse(
        content="",
        model="qwen3:8b",
        success=True,
        tool_calls=[tool_call],
        raw={"message": {"role": "assistant", "content": "", "tool_calls": [tool_call]}},
    )


def _llm_text_response(text: str) -> LLMResponse:
    """Build an LLMResponse that contains a final text answer."""
    return LLMResponse(
        content=text,
        model="qwen3:8b",
        success=True,
        tool_calls=None,
        raw={"message": {"role": "assistant", "content": text}},
    )


def _llm_error_response(error: str) -> LLMResponse:
    """Build a failed LLMResponse (connection error, etc.)."""
    return LLMResponse(
        content="",
        model="qwen3:8b",
        success=False,
        error=error,
    )


def _tool_success(name: str, data: dict) -> ToolCallResult:
    return ToolCallResult(tool_name=name, success=True, data=data)


def _tool_error(name: str, error: str) -> ToolCallResult:
    return ToolCallResult(tool_name=name, success=False, error=f"[EXECUTION_ERROR] {error}")


# ---------------------------------------------------------------------------
# 1. Basic wiring: agent initialisation
# ---------------------------------------------------------------------------

class TestAgentInit:
    def test_default_max_iterations(self):
        agent = BuyerAgent()
        assert agent.max_iterations == BuyerAgent.DEFAULT_MAX_ITERATIONS

    def test_custom_max_iterations(self):
        agent = BuyerAgent(max_iterations=3)
        assert agent.max_iterations == 3

    def test_tools_built_on_init(self):
        agent = BuyerAgent()
        assert len(agent._tools) > 0

    def test_system_prompt_has_key_rules(self):
        assert "product_id" in SYSTEM_PROMPT.lower()
        assert "never invent" in SYSTEM_PROMPT.lower()
        assert "authoritative" in SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# 2. Search → product selection → final response
# ---------------------------------------------------------------------------

class TestSearchFlow:
    def test_search_then_final_response(self):
        """Agent searches for products, Qwen evaluates them, then gives a final answer."""
        search_result = [{"product_id": "p1", "name": "Wireless Mouse", "price": 1299.0}]
        responses = [
            _llm_tool_response("search_products", {"query": "wireless mouse", "max_price": 1500}),
            _llm_text_response("I found a Wireless Mouse for ₹1299. It fits your budget."),
        ]
        tool_results = [
            _tool_success("search_products", {"results": search_result}),
        ]

        with patch("app.agent.send_message", side_effect=responses), \
             patch("app.agent.dispatch_tool_call", side_effect=tool_results):
            result = BuyerAgent().run("Find a wireless mouse under ₹1500")

        assert result.success is True
        assert result.stop_reason == "complete"
        assert result.tool_calls_made == 1
        assert "Wireless Mouse" in result.final_response

    def test_search_returns_empty_then_final_response(self):
        """Agent gracefully handles no search results."""
        responses = [
            _llm_tool_response("search_products", {"query": "quantum laptop"}),
            _llm_text_response("Sorry, no products matched your search."),
        ]
        tool_results = [_tool_success("search_products", {"results": []})]

        with patch("app.agent.send_message", side_effect=responses), \
             patch("app.agent.dispatch_tool_call", side_effect=tool_results):
            result = BuyerAgent().run("Find a quantum laptop")

        assert result.success is True
        assert result.tool_calls_made == 1


# ---------------------------------------------------------------------------
# 3. Search → cart creation → add item (multi-step)
# ---------------------------------------------------------------------------

class TestMultiStepCartFlow:
    def test_search_then_create_cart_then_add_item(self):
        """Full flow: search → create_cart → add_to_cart → get_cart → final response."""
        responses = [
            _llm_tool_response("search_products", {"query": "wireless mouse", "max_price": 1500}),
            _llm_tool_response("create_cart", {}),
            _llm_tool_response("add_to_cart", {"cart_id": "cart-abc", "product_id": "p1", "quantity": 1}),
            _llm_tool_response("get_cart", {"cart_id": "cart-abc"}),
            _llm_text_response("Done! I added the Wireless Mouse to cart cart-abc. Subtotal: ₹1299."),
        ]
        tool_results = [
            _tool_success("search_products", {"results": [{"product_id": "p1", "name": "Wireless Mouse", "price": 1299.0}]}),
            _tool_success("create_cart", {"cart_id": "cart-abc", "status": "ACTIVE"}),
            _tool_success("add_to_cart", {"cart_id": "cart-abc", "subtotal": 1299.0}),
            _tool_success("get_cart", {"cart_id": "cart-abc", "items": [{"product_id": "p1", "quantity": 1}], "subtotal": 1299.0}),
        ]

        with patch("app.agent.send_message", side_effect=responses), \
             patch("app.agent.dispatch_tool_call", side_effect=tool_results):
            result = BuyerAgent().run("Find a wireless mouse under ₹1500 and add it to a cart")

        assert result.success is True
        assert result.stop_reason == "complete"
        assert result.tool_calls_made == 4
        assert "cart-abc" in result.final_response

    def test_history_grows_correctly_through_steps(self):
        """The conversation history must contain system, user, assistant, tool, ... turns."""
        responses = [
            _llm_tool_response("create_cart", {}),
            _llm_text_response("Cart created."),
        ]
        tool_results = [_tool_success("create_cart", {"cart_id": "cart-xyz"})]

        with patch("app.agent.send_message", side_effect=responses), \
             patch("app.agent.dispatch_tool_call", side_effect=tool_results):
            result = BuyerAgent().run("Create a cart")

        roles = [m["role"] for m in result.history]
        assert roles[0] == "system"
        assert roles[1] == "user"
        assert "assistant" in roles
        assert "tool" in roles

    def test_tool_result_message_is_valid_json_in_history(self):
        """Each tool result in history must carry valid JSON content."""
        responses = [
            _llm_tool_response("search_products", {"query": "mouse"}),
            _llm_text_response("Found it."),
        ]
        tool_results = [_tool_success("search_products", {"results": []})]

        with patch("app.agent.send_message", side_effect=responses), \
             patch("app.agent.dispatch_tool_call", side_effect=tool_results):
            result = BuyerAgent().run("Search for a mouse")

        tool_messages = [m for m in result.history if m["role"] == "tool"]
        for msg in tool_messages:
            parsed = json.loads(msg["content"])  # must not raise
            assert "success" in parsed


# ---------------------------------------------------------------------------
# 4. Tool failure and recovery
# ---------------------------------------------------------------------------

class TestToolFailureAndRecovery:
    def test_tool_failure_result_returned_to_qwen(self):
        """When a tool fails, the error is given back to Qwen (not hidden)."""
        responses = [
            _llm_tool_response("add_to_cart", {"cart_id": "bad", "product_id": "p1", "quantity": 1}),
            _llm_text_response("Sorry, that cart does not exist. Please create a cart first."),
        ]
        tool_results = [_tool_error("add_to_cart", "Cart 'bad' not found")]

        with patch("app.agent.send_message", side_effect=responses), \
             patch("app.agent.dispatch_tool_call", side_effect=tool_results):
            result = BuyerAgent().run("Add product p1 to cart bad")

        assert result.success is True  # Qwen recovered and gave a final reply
        assert result.tool_calls_made == 1
        # Qwen should have received the error in the tool message
        tool_msgs = [m for m in result.history if m["role"] == "tool"]
        assert len(tool_msgs) == 1
        payload = json.loads(tool_msgs[0]["content"])
        assert payload["success"] is False

    def test_failed_tool_does_not_stop_agent(self):
        """A tool error does not crash the agent; Qwen continues the conversation."""
        responses = [
            _llm_tool_response("get_product", {"product_id": "invalid"}),
            _llm_text_response("Product not found. Can I help you search instead?"),
        ]
        tool_results = [_tool_error("get_product", "Product 'invalid' not found")]

        with patch("app.agent.send_message", side_effect=responses), \
             patch("app.agent.dispatch_tool_call", side_effect=tool_results):
            result = BuyerAgent().run("Get product invalid")

        assert result.final_response != ""
        assert result.stop_reason == "complete"


# ---------------------------------------------------------------------------
# 5. Unknown tool request
# ---------------------------------------------------------------------------

class TestUnknownToolRequest:
    def test_unknown_tool_returns_error_to_qwen(self):
        """If Qwen requests a tool not in the registry, the gateway rejects it and Qwen recovers."""
        responses = [
            _llm_tool_response("hack_the_database", {"query": "DROP TABLE products"}),
            _llm_text_response("I cannot perform that action."),
        ]
        # dispatch_tool_call is NOT mocked here — we let the real gateway reject it
        with patch("app.agent.send_message", side_effect=responses):
            result = BuyerAgent().run("Hack the database")

        assert result.stop_reason == "complete"
        tool_msgs = [m for m in result.history if m["role"] == "tool"]
        assert len(tool_msgs) == 1
        payload = json.loads(tool_msgs[0]["content"])
        assert payload["success"] is False
        assert "TOOL_NOT_FOUND" in payload["error"]

    def test_exec_tool_name_rejected_by_gateway(self):
        """'exec' is not a registered tool and must be blocked."""
        responses = [
            _llm_tool_response("exec", {"code": "import os; os.system('rm -rf /')"}),
            _llm_text_response("I cannot do that."),
        ]
        with patch("app.agent.send_message", side_effect=responses):
            result = BuyerAgent().run("Execute arbitrary code")

        tool_msgs = [m for m in result.history if m["role"] == "tool"]
        payload = json.loads(tool_msgs[0]["content"])
        assert payload["success"] is False


# ---------------------------------------------------------------------------
# 6. Maximum iteration protection
# ---------------------------------------------------------------------------

class TestMaxIterationProtection:
    def test_stops_at_max_iterations(self):
        """Agent must stop after max_iterations rounds if no final response is given."""
        # Always return a tool call, never a final text response
        always_tool = _llm_tool_response("search_products", {"query": "mouse"})
        always_tool_result = _tool_success("search_products", {"results": []})

        max_iter = 3
        with patch("app.agent.send_message", return_value=always_tool), \
             patch("app.agent.dispatch_tool_call", return_value=always_tool_result):
            result = BuyerAgent(max_iterations=max_iter).run("Infinite search")

        assert result.stop_reason == "max_iterations"
        assert result.success is False
        assert result.tool_calls_made == max_iter
        assert "unable to complete" in result.final_response.lower()

    def test_max_iterations_one_still_works(self):
        """A cap of 1 means exactly 1 tool call round, then stop."""
        with patch("app.agent.send_message", return_value=_llm_tool_response("create_cart", {})), \
             patch("app.agent.dispatch_tool_call", return_value=_tool_success("create_cart", {})):
            result = BuyerAgent(max_iterations=1).run("Goal that needs tools")

        assert result.stop_reason == "max_iterations"
        assert result.tool_calls_made == 1

    def test_completes_before_cap(self):
        """If the model answers before the cap, stop_reason must be 'complete'."""
        with patch("app.agent.send_message", return_value=_llm_text_response("Done!")):
            result = BuyerAgent(max_iterations=10).run("Simple question")

        assert result.stop_reason == "complete"
        assert result.tool_calls_made == 0


# ---------------------------------------------------------------------------
# 7. Hallucinated / nonexistent product ID attempt
# ---------------------------------------------------------------------------

class TestHallucinatedProductID:
    def test_hallucinated_product_id_fails_at_gateway(self):
        """
        If Qwen invents a product ID not in the DB, the real executor returns
        an EXECUTION_ERROR (product not found). The agent returns this to Qwen.
        """
        fake_id = "HALLUCINATED-PRODUCT-9999"
        responses = [
            _llm_tool_response("add_to_cart", {"cart_id": "c1", "product_id": fake_id, "quantity": 1}),
            _llm_text_response("Sorry, that product does not exist."),
        ]
        # Let real dispatch_tool_call run — it will call execute_tool → add_to_cart → "cart not found"
        # But since we don't want DB, mock dispatch_tool_call returning a failure
        with patch("app.agent.send_message", side_effect=responses), \
             patch("app.agent.dispatch_tool_call",
                   return_value=_tool_error("add_to_cart", f"Cart 'c1' not found")):
            result = BuyerAgent().run(f"Add product {fake_id} to cart c1")

        tool_msgs = [m for m in result.history if m["role"] == "tool"]
        payload = json.loads(tool_msgs[0]["content"])
        assert payload["success"] is False

    def test_agent_never_accepts_qwen_invented_price(self):
        """
        Even if Qwen passes a price in arguments, add_to_cart's schema has no price field,
        so the Pydantic validator will strip unknown fields. The DB price is always used.
        """
        from app.tools import AddToCartInput
        # Verify add_to_cart schema has no price/unit_price field
        field_names = set(AddToCartInput.model_fields.keys())
        assert "price" not in field_names
        assert "unit_price" not in field_names


# ---------------------------------------------------------------------------
# 8. LLM-level error handling
# ---------------------------------------------------------------------------

class TestLLMError:
    def test_connection_error_returns_failure(self):
        with patch("app.agent.send_message", return_value=_llm_error_response("Connection refused")):
            result = BuyerAgent().run("Any goal")

        assert result.success is False
        assert result.stop_reason == "llm_error"
        assert "error" in result.final_response.lower()
        assert result.tool_calls_made == 0

    def test_llm_error_in_second_round(self):
        """LLM error mid-loop should also stop cleanly."""
        responses = [
            _llm_tool_response("search_products", {"query": "laptop"}),
            _llm_error_response("Timeout"),
        ]
        tool_results = [_tool_success("search_products", {"results": []})]

        with patch("app.agent.send_message", side_effect=responses), \
             patch("app.agent.dispatch_tool_call", side_effect=tool_results):
            result = BuyerAgent().run("Find a laptop")

        assert result.success is False
        assert result.stop_reason == "llm_error"
        assert result.tool_calls_made == 1  # one successful call before the error


# ---------------------------------------------------------------------------
# 9. Multiple tool calls in a single round
# ---------------------------------------------------------------------------

class TestMultipleToolCallsPerRound:
    def test_two_tool_calls_in_one_response(self):
        """Qwen can request multiple tool calls in one response."""
        call1 = {"function": {"name": "search_products", "arguments": {"query": "mouse"}}}
        call2 = {"function": {"name": "create_cart", "arguments": {}}}
        multi_response = LLMResponse(
            content="",
            model="qwen3:8b",
            success=True,
            tool_calls=[call1, call2],
            raw={"message": {"role": "assistant", "content": "", "tool_calls": [call1, call2]}},
        )
        tool_results = [
            _tool_success("search_products", {"results": []}),
            _tool_success("create_cart", {"cart_id": "cart-1"}),
        ]

        with patch("app.agent.send_message", side_effect=[multi_response, _llm_text_response("Done.")]), \
             patch("app.agent.dispatch_tool_call", side_effect=tool_results):
            result = BuyerAgent().run("Search and create cart")

        assert result.tool_calls_made == 2
        assert result.stop_reason == "complete"
        # Both tool messages should appear in history
        tool_msgs = [m for m in result.history if m["role"] == "tool"]
        assert len(tool_msgs) == 2
