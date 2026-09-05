"""
Buyer Agent — autonomous shopping loop.

The agent drives Qwen3 through a structured tool-calling loop:
  1. Send the user's goal + conversation history to Qwen with all registered tools.
  2. If Qwen requests tool calls → route every call through the secure execute_tool
     gateway, append results to history, and repeat.
  3. If Qwen produces a natural-language reply (no tool calls) → return it as the
     final answer.
  4. If the iteration cap is hit → stop cleanly with an explanation.

Qwen never touches the database, cart, or order layer directly.
The execute_tool gateway (and its Pydantic validators) remain the sole entry point.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.llm import LLMMessage, LLMResponse, send_message
from app.tool_interface import (
    build_ollama_tools,
    parse_tool_calls,
    dispatch_tool_call,
    format_tool_result_message,
)


# ---------------------------------------------------------------------------
# System prompt — explicit instructions that constrain Qwen's behaviour
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an autonomous AI shopping assistant.

Your job is to help the user achieve their shopping goal by using the provided tools.

STRICT RULES — follow these exactly:
1. Use tools for ALL product information. Never invent product names, IDs, prices, or stock levels.
2. Use the EXACT product_id values returned by search_products or get_product. Never guess or construct a product_id.
3. Do not claim an action succeeded unless the tool result explicitly shows "success": true.
4. If a tool returns an error, report it honestly and try an alternative approach if possible.
5. Every tool response is the authoritative source of truth — never override it with assumptions.
6. Never invent or assume cart totals, subtotals, or order totals — always use values returned by tools.
7. When the user's goal is achieved, or you cannot proceed further, provide a clear, concise final response summarising what was accomplished and the key details (product name, quantity, price, cart ID, etc.).

WORKFLOW GUIDANCE:
- Use search_products to discover products matching the user's criteria.
- Use get_product to confirm a product's details before adding it to a cart.
- Use create_cart before calling add_to_cart.
- Use get_cart to confirm cart contents after adding items.
- Use create_order only when the user explicitly asks to place/confirm an order.
- Do NOT use create_order unless the user has explicitly requested it."""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    """The final outcome of a BuyerAgent.run() call."""
    final_response: str           # Model's last natural-language message
    success: bool                 # True when the agent stopped normally (complete)
    tool_calls_made: int          # Total number of tool dispatches during the run
    stop_reason: str              # "complete" | "max_iterations" | "llm_error"
    history: List[Dict[str, Any]] = field(default_factory=list, repr=False)


# ---------------------------------------------------------------------------
# BuyerAgent
# ---------------------------------------------------------------------------

class BuyerAgent:
    """
    Autonomous shopping agent that iterates Qwen3 through tool calls until
    it produces a final natural-language response.

    Parameters
    ----------
    max_iterations : int
        Hard cap on the number of tool-call rounds. Prevents infinite loops.
        Each round may contain one or more individual tool invocations.
    """

    DEFAULT_MAX_ITERATIONS = 10

    def __init__(self, max_iterations: int = DEFAULT_MAX_ITERATIONS) -> None:
        self.max_iterations = max_iterations
        self._tools = build_ollama_tools()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, user_goal: str) -> AgentResult:
        """
        Run the agent loop for a given user shopping goal.

        The conversation starts with a system prompt followed by the user's
        goal. The loop then calls the LLM, dispatches any requested tools,
        and repeats until the LLM gives a final text reply or the cap is hit.
        """
        history: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_goal},
        ]
        tool_calls_made = 0

        for _iteration in range(self.max_iterations):
            messages = _history_to_messages(history)
            response: LLMResponse = send_message(messages, tools=self._tools)

            # --- LLM-level error (network, HTTP, etc.) ---
            if not response.success:
                return AgentResult(
                    final_response=(
                        f"I encountered an error communicating with the AI: {response.error}"
                    ),
                    success=False,
                    tool_calls_made=tool_calls_made,
                    stop_reason="llm_error",
                    history=history,
                )

            # Append the assistant turn to history (may carry tool_calls)
            assistant_entry: Dict[str, Any] = {
                "role": "assistant",
                "content": response.content or "",
            }
            if response.tool_calls:
                assistant_entry["tool_calls"] = response.tool_calls
            history.append(assistant_entry)

            # --- No tool calls → Qwen has given a final answer ---
            if not response.tool_calls:
                return AgentResult(
                    final_response=response.content or "(No response text)",
                    success=True,
                    tool_calls_made=tool_calls_made,
                    stop_reason="complete",
                    history=history,
                )

            # --- Parse and dispatch all tool calls in this round ---
            parsed_calls = parse_tool_calls({"tool_calls": response.tool_calls})

            for call_request in parsed_calls:
                tool_result = dispatch_tool_call(call_request, actor="buyer_agent")
                tool_msg = format_tool_result_message(tool_result)
                history.append(tool_msg)
                tool_calls_made += 1

        # --- Iteration cap reached without a final answer ---
        return AgentResult(
            final_response=(
                "I was unable to complete your request within the allowed number of steps. "
                "Please try a more specific query or break the task into smaller parts."
            ),
            success=False,
            tool_calls_made=tool_calls_made,
            stop_reason="max_iterations",
            history=history,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _history_to_messages(history: List[Dict[str, Any]]) -> List[LLMMessage]:
    """
    Convert raw history dicts to LLMMessage objects for send_message.

    Assistant messages that include tool_calls are preserved by attaching
    the tool_calls list to the LLMMessage, so the serialiser can include them.
    """
    return [
        LLMMessage(
            role=entry.get("role", "user"),
            content=entry.get("content", ""),
            tool_calls=entry.get("tool_calls"),
            name=entry.get("name"),
        )
        for entry in history
    ]
