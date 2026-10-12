from .base import LLMProvider


class EchoProvider(LLMProvider):
    """Placeholder that echoes the last user message; needs no config."""

    def __init__(self, **_):
        pass

    def complete(self, messages: list[dict], max_tokens: int) -> str:
        last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"(echo, {len(messages)} msgs in context) {last}"
