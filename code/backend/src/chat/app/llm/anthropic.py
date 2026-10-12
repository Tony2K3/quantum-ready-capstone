"""Adapter for Anthropic's Messages API."""
import httpx

from .base import LLMError, LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str, base_url: str = "", api_key: str = "",
                 timeout: float = 60, client: httpx.Client | None = None):
        if not model:
            raise ValueError("CHAT_LLM_MODEL is required for the anthropic provider")
        self.model = model
        self.url = (base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        self.client = client or httpx.Client(timeout=timeout, headers=headers)

    def complete(self, messages: list[dict], max_tokens: int) -> str:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        turns = [m for m in messages if m["role"] != "system"]
        # The API requires the conversation to start with a user turn; context
        # trimming can leave an assistant message first.
        while turns and turns[0]["role"] != "user":
            turns.pop(0)

        payload = {"model": self.model, "max_tokens": max_tokens, "messages": turns}
        if system:
            payload["system"] = system
        try:
            resp = self.client.post(self.url, json=payload)
            resp.raise_for_status()
            blocks = resp.json()["content"]
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise LLMError(f"Anthropic request failed: {e}") from e
