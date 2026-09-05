"""
Tests for the LLM client (app/llm.py).
All HTTP calls are intercepted with pytest-httpx mocks — no running Ollama needed.
"""
import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.llm import LLMMessage, LLMResponse, send_message, check_ollama_health


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _set_ollama_provider(monkeypatch):
    monkeypatch.setattr("app.config.settings.llm_provider", "ollama")

def _mock_post(monkeypatch, status_code: int, json_body: dict):
    """Patch httpx.post to return a controlled Response."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = status_code
    mock_response.json.return_value = json_body
    if status_code >= 400:
        mock_response.text = str(json_body)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=mock_response,
        )
    else:
        mock_response.raise_for_status.return_value = None
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: mock_response)
    return mock_response


# ---------------------------------------------------------------------------
# LLMMessage tests
# ---------------------------------------------------------------------------

class TestLLMMessage:
    def test_create_user_message(self):
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_create_system_message(self):
        msg = LLMMessage(role="system", content="You are a helpful assistant.")
        assert msg.role == "system"

    def test_create_assistant_message(self):
        msg = LLMMessage(role="assistant", content="I can help you.")
        assert msg.role == "assistant"


# ---------------------------------------------------------------------------
# LLMResponse tests
# ---------------------------------------------------------------------------

class TestLLMResponse:
    def test_success_response(self):
        r = LLMResponse(content="Hello!", model="qwen3:8b", success=True)
        assert r.success is True
        assert r.error is None
        assert r.content == "Hello!"

    def test_error_response(self):
        r = LLMResponse(content="", model="qwen3:8b", success=False, error="Connection refused")
        assert r.success is False
        assert r.error == "Connection refused"
        assert r.content == ""


# ---------------------------------------------------------------------------
# send_message — success path
# ---------------------------------------------------------------------------

class TestSendMessageSuccess:
    def test_returns_assistant_content(self, monkeypatch):
        _mock_post(monkeypatch, 200, {
            "model": "qwen3:8b",
            "message": {"role": "assistant", "content": "Hello from Qwen!"},
        })
        result = send_message([LLMMessage(role="user", content="Hi")])
        assert result.success is True
        assert result.content == "Hello from Qwen!"
        assert result.model == "qwen3:8b"
        assert result.error is None

    def test_raw_payload_stored(self, monkeypatch):
        payload = {"model": "qwen3:8b", "message": {"role": "assistant", "content": "raw"}}
        _mock_post(monkeypatch, 200, payload)
        result = send_message([LLMMessage(role="user", content="test")])
        assert result.raw == payload

    def test_multi_turn_conversation(self, monkeypatch):
        _mock_post(monkeypatch, 200, {
            "model": "qwen3:8b",
            "message": {"role": "assistant", "content": "3"},
        })
        messages = [
            LLMMessage(role="system", content="You are a calculator."),
            LLMMessage(role="user", content="1 + 2?"),
        ]
        result = send_message(messages)
        assert result.success is True
        assert result.content == "3"

    def test_model_override(self, monkeypatch):
        _mock_post(monkeypatch, 200, {
            "model": "other-model",
            "message": {"role": "assistant", "content": "ok"},
        })
        result = send_message(
            [LLMMessage(role="user", content="hi")],
            model="other-model",
        )
        assert result.model == "other-model"

    def test_empty_content_in_response(self, monkeypatch):
        """Gracefully handle an empty assistant message."""
        _mock_post(monkeypatch, 200, {
            "model": "qwen3:8b",
            "message": {"role": "assistant", "content": ""},
        })
        result = send_message([LLMMessage(role="user", content="?")])
        assert result.success is True
        assert result.content == ""

    def test_missing_message_key_in_response(self, monkeypatch):
        """Handle a response that omits the 'message' key."""
        _mock_post(monkeypatch, 200, {"model": "qwen3:8b"})
        result = send_message([LLMMessage(role="user", content="?")])
        assert result.success is True
        assert result.content == ""


# ---------------------------------------------------------------------------
# send_message — error paths
# ---------------------------------------------------------------------------

class TestSendMessageErrors:
    def test_connect_error_returns_failure(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **kw: (_ for _ in ()).throw(httpx.ConnectError("refused"))
        )
        result = send_message([LLMMessage(role="user", content="hi")])
        assert result.success is False
        assert result.error is not None
        assert "connect" in result.error.lower()

    def test_timeout_returns_failure(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **kw: (_ for _ in ()).throw(httpx.TimeoutException("timed out"))
        )
        result = send_message([LLMMessage(role="user", content="hi")])
        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_http_4xx_returns_failure(self, monkeypatch):
        _mock_post(monkeypatch, 400, {"error": "bad request"})
        result = send_message([LLMMessage(role="user", content="hi")])
        assert result.success is False
        assert "400" in result.error

    def test_unexpected_exception_returns_failure(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        result = send_message([LLMMessage(role="user", content="hi")])
        assert result.success is False
        assert result.error is not None

    def test_error_does_not_raise(self, monkeypatch):
        """send_message must never raise; all errors come back as LLMResponse."""
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **kw: (_ for _ in ()).throw(Exception("unexpected"))
        )
        try:
            result = send_message([LLMMessage(role="user", content="hi")])
            assert result.success is False
        except Exception:
            pytest.fail("send_message raised an exception instead of returning LLMResponse")


# ---------------------------------------------------------------------------
# check_ollama_health — existing tests still work
# ---------------------------------------------------------------------------

class TestCheckOllamaHealth:
    def test_structure_offline(self, monkeypatch):
        """Health check returns the required keys even when Ollama is offline."""
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: (_ for _ in ()).throw(Exception("offline")))
        result = check_ollama_health()
        assert "reachable" in result
        assert "configured_model" in result
        assert "model_available" in result
        assert "available_models" in result
        assert result["configured_model"] == "qwen3:8b"
        assert result["reachable"] is False

    def test_structure_online_with_model(self, monkeypatch):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "qwen3:8b"}]
        }
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: mock_response)
        result = check_ollama_health()
        assert result["reachable"] is True
        assert result["model_available"] is True
        assert "qwen3:8b" in result["available_models"]
