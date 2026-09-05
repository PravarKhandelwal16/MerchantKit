"""Diagnostic script to verify active LLM provider reachability, configuration, and a test chat call."""
from app.llm import check_llm_health, send_message, LLMMessage
from app.config import settings


def main():
    print("=" * 60)
    print("MERCHANTKIT — LLM PROVIDER DIAGNOSTIC")
    print("=" * 60)
    print(f"Active Provider     : {settings.llm_provider.upper()}")
    if settings.llm_provider == "gemini":
        print(f"Configured Model    : {settings.gemini_model}")
        print(f"API Key Present     : {'YES' if bool(settings.gemini_api_key) else 'NO'}")
    else:
        print(f"Target Base URL     : {settings.ollama_base_url}")
        print(f"Configured Model    : {settings.ollama_model}")
    print("-" * 60)

    result = check_llm_health()
    print(f"Health Status       : {result.get('status', 'unknown').upper()}")
    print(f"Provider Details    : {result}")
    print("-" * 60)
    print("CHAT PROBE")
    print("-" * 60)

    if result.get("status") == "online":
        probe = send_message(
            [LLMMessage(role="user", content="Reply with exactly: OK")],
            timeout=30.0,
        )
        if probe.success:
            print(f"Chat Response       : {probe.content.strip()}")
            print(f"Responding Model    : {probe.model}")
        else:
            print(f"Chat Error          : {probe.error}")
    else:
        print("Chat Probe          : Skipped (Provider not online)")

    print("=" * 60)


if __name__ == "__main__":
    main()

