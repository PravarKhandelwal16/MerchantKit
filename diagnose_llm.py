"""Diagnostic script to verify Ollama reachability, model availability, and a test chat call."""
from app.llm import check_ollama_health, send_message, LLMMessage
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

    print("-" * 60)
    print("CHAT PROBE")
    print("-" * 60)

    if result["reachable"] and result["model_available"]:
        probe = send_message(
            [LLMMessage(role="user", content="Reply with exactly: OK")],
            timeout=180.0,
        )
        if probe.success:
            print(f"Chat Response       : {probe.content.strip()}")
            print(f"Responding Model    : {probe.model}")
        else:
            print(f"Chat Error          : {probe.error}")
    else:
        print("Chat Probe          : Skipped (Ollama not reachable or model missing)")

    print("=" * 60)


if __name__ == "__main__":
    main()
