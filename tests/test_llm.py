from app.config import settings
from app.llm import check_ollama_health


def test_llm_configuration():
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "qwen3:8b"


def test_check_ollama_health_structure():
    # Verify that check_ollama_health returns expected schema even if server is offline
    result = check_ollama_health()
    assert "reachable" in result
    assert "configured_model" in result
    assert "model_available" in result
    assert "available_models" in result
    assert result["configured_model"] == "qwen3:8b"
