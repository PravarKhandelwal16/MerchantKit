"""Diagnostic script to verify Ollama reachability and configured model availability."""
from app.llm import check_ollama_health
from app.config import settings


def main():
    print("=" * 60)
    print("OLLAMA & LOCAL LLM DIAGNOSTIC")
    print("=" * 60)
    print(f"Target Base URL     : {settings.ollama_base_url}")
    print(f"Configured Model    : {settings.ollama_model}")
    print("-" * 60)

    result = check_ollama_health()

    print(f"Ollama Reachable    : {'YES' if result['reachable'] else 'NO'}")
    print(f"Model Available     : {'YES' if result['model_available'] else 'NO'}")

    if result["available_models"]:
        print(f"Installed Models    : {', '.join(result['available_models'])}")
    else:
        print("Installed Models    : None detected")

    if result["error"]:
        print(f"Details / Error     : {result['error']}")

    print("=" * 60)


if __name__ == "__main__":
    main()
