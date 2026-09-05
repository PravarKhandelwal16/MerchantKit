"""
Unit tests for GeminiProvider and LLM Provider Abstraction.
All tests use mocks — zero real external API calls are made.
"""
import pytest
from unittest.mock import MagicMock, patch
from google.genai import types
from google.genai.errors import ClientError, APIError

from app.config import settings
from app.llm import (
    LLMMessage,
    LLMResponse,
    GeminiProvider,
    OllamaProvider,
    get_llm_provider,
    send_message,
    check_llm_health,
)


# ---------------------------------------------------------------------------
# 1. Configuration tests
# ---------------------------------------------------------------------------

class TestGeminiConfig:
    def test_default_provider_is_gemini(self):
        assert settings.llm_provider == "gemini"

    def test_default_gemini_model(self):
        assert settings.gemini_model == "gemini-3.6-flash"

    def test_ollama_settings_preserved(self):
        assert settings.ollama_base_url == "http://localhost:11434"
        assert settings.ollama_model == "qwen3:8b"


# ---------------------------------------------------------------------------
# 2. Provider factory tests
# ---------------------------------------------------------------------------

class TestProviderFactory:
    def test_get_gemini_provider(self):
        provider = get_llm_provider("gemini")
        assert isinstance(provider, GeminiProvider)

    def test_get_ollama_provider(self):
        provider = get_llm_provider("ollama")
        assert isinstance(provider, OllamaProvider)

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError) as exc_info:
            get_llm_provider("unsupported_ai")
        assert "Unsupported LLM_PROVIDER" in str(exc_info.value)

    def test_send_message_invalid_provider_returns_error(self):
        res = send_message(
            [LLMMessage(role="user", content="Hi")],
            provider="invalid_model",
        )
        assert res.success is False
        assert "Unsupported LLM_PROVIDER" in res.error


# ---------------------------------------------------------------------------
# 3. Missing API key handling
# ---------------------------------------------------------------------------

class TestMissingApiKey:
    def test_missing_api_key_returns_safe_error(self):
        provider = GeminiProvider(api_key="")
        res = provider.send_message([LLMMessage(role="user", content="Hello")])
        assert res.success is False
        assert "GEMINI_API_KEY" in res.error

    def test_missing_api_key_health_status(self):
        provider = GeminiProvider(api_key="")
        health = provider.check_health()
        assert health["status"] == "offline"
        assert health["configured"] is False
        assert health["provider"] == "gemini"


# ---------------------------------------------------------------------------
# 4. Successful text response
# ---------------------------------------------------------------------------

class TestGeminiTextResponse:
    def test_text_response_normalized_correctly(self):
        provider = GeminiProvider(api_key="mock-key-12345")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.candidates = [
            types.Candidate(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_text(text="I found Logitech M331 for you.")],
                )
            )
        ]
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(provider, "_get_client", return_value=mock_client):
            res = provider.send_message([
                LLMMessage(role="system", content="You are a shopping assistant."),
                LLMMessage(role="user", content="Recommend a mouse."),
            ])

        assert res.success is True
        assert res.content == "I found Logitech M331 for you."
        assert res.tool_calls is None
        assert res.error is None
        assert res.model == "gemini-3.6-flash"


# ---------------------------------------------------------------------------
# 5. Tool call parsing
# ---------------------------------------------------------------------------

class TestGeminiToolCallParsing:
    def test_tool_call_extracted_correctly(self):
        provider = GeminiProvider(api_key="mock-key-12345")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.candidates = [
            types.Candidate(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part.from_function_call(
                            name="search_products",
                            args={"query": "mouse", "max_price": 1500},
                        )
                    ],
                )
            )
        ]
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(provider, "_get_client", return_value=mock_client):
            res = provider.send_message([
                LLMMessage(role="user", content="Find a mouse under 1500"),
            ])

        assert res.success is True
        assert res.tool_calls is not None
        assert len(res.tool_calls) == 1
        tc = res.tool_calls[0]
        assert tc["function"]["name"] == "search_products"
        assert tc["function"]["arguments"] == {"query": "mouse", "max_price": 1500}


# ---------------------------------------------------------------------------
# 6. Multi-step conversation & tool flow
# ---------------------------------------------------------------------------

class TestGeminiMultiStepFlow:
    def test_converts_multi_turn_history_including_tool_response(self):
        provider = GeminiProvider(api_key="mock-key-12345")
        messages = [
            LLMMessage(role="system", content="You are an AI shopping assistant."),
            LLMMessage(role="user", content="Find a mouse under ₹1500"),
            LLMMessage(
                role="assistant",
                content="",
                tool_calls=[{"function": {"name": "search_products", "arguments": {"query": "mouse"}}}],
            ),
            LLMMessage(
                role="tool",
                name="search_products",
                content='{"success": true, "data": [{"product_id": "M001", "name": "Logitech M331"}]}',
            ),
        ]

        system_instruction, contents = provider._convert_messages(messages)
        assert system_instruction == "You are an AI shopping assistant."
        assert len(contents) == 3

        # Turn 0: User message
        assert contents[0].role == "user"
        assert contents[0].parts[0].text == "Find a mouse under ₹1500"

        # Turn 1: Model function call
        assert contents[1].role == "model"
        assert contents[1].parts[0].function_call.name == "search_products"
        assert contents[1].parts[0].function_call.args == {"query": "mouse"}

        # Turn 2: User function response
        assert contents[2].role == "user"
        assert contents[2].parts[0].function_response.name == "search_products"
        assert contents[2].parts[0].function_response.response["success"] is True

    def test_preserves_thought_signature_in_multi_turn_history(self):
        provider = GeminiProvider(api_key="mock-key-12345")
        mock_signature = b"secret_thought_state_bytes"
        messages = [
            LLMMessage(role="user", content="Find a mouse"),
            LLMMessage(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": "call_123",
                    "function": {"name": "search_products", "arguments": {"query": "mouse"}},
                    "thought_signature": mock_signature,
                }],
            ),
            LLMMessage(
                role="tool",
                name="search_products",
                content='{"success": true}',
            ),
        ]
        _, contents = provider._convert_messages(messages)
        model_part = contents[1].parts[0]
        assert model_part.thought_signature == mock_signature
        assert model_part.function_call.id == "call_123"


# ---------------------------------------------------------------------------
# 7. Safe error handling
# ---------------------------------------------------------------------------

class TestGeminiErrorHandling:
    def test_invalid_api_key_client_error(self):
        provider = GeminiProvider(api_key="invalid-key")
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = ClientError(
            400,
            {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}},
        )

        with patch.object(provider, "_get_client", return_value=mock_client):
            res = provider.send_message([LLMMessage(role="user", content="Hi")])

        assert res.success is False
        assert "Invalid API key" in res.error
        # Must never leak raw key
        assert "invalid-key" not in res.error

    def test_rate_limit_error(self):
        provider = GeminiProvider(api_key="mock-key")
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = ClientError(
            429,
            {"error": {"code": 429, "message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}},
        )

        with patch.object(provider, "_get_client", return_value=mock_client):
            res = provider.send_message([LLMMessage(role="user", content="Hi")])

        assert res.success is False
        assert "rate limit exceeded" in res.error.lower()

    def test_network_timeout_error(self):
        provider = GeminiProvider(api_key="mock-key")
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = TimeoutError("Deadline exceeded")

        with patch.object(provider, "_get_client", return_value=mock_client):
            res = provider.send_message([LLMMessage(role="user", content="Hi")])

        assert res.success is False
        assert "timed out" in res.error.lower()


# ---------------------------------------------------------------------------
# 8. Health check
# ---------------------------------------------------------------------------

class TestGeminiHealthCheck:
    def test_online_when_model_verified(self):
        provider = GeminiProvider(api_key="mock-key")
        mock_client = MagicMock()
        mock_client.models.get.return_value = MagicMock()

        with patch.object(provider, "_get_client", return_value=mock_client):
            health = provider.check_health()

        assert health["status"] == "online"
        assert health["provider"] == "gemini"
        assert health["configured"] is True
        assert health["model"] == "gemini-3.6-flash"

    def test_offline_when_models_get_fails(self):
        provider = GeminiProvider(api_key="mock-key")
        mock_client = MagicMock()
        mock_client.models.get.side_effect = Exception("Model unreachable")

        with patch.object(provider, "_get_client", return_value=mock_client):
            health = provider.check_health()

        assert health["status"] == "offline"
        assert health["provider"] == "gemini"
        assert health["configured"] is True
