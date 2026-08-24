from typing import Any, Dict, List
import httpx
from app.config import settings


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
