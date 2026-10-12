"""Adapter for any OpenAI-compatible /chat/completions endpoint.

Covers OpenAI, Azure OpenAI (via base_url), Ollama, vLLM, LM Studio, llama.cpp
server, Groq, Together, Mistral, DeepSeek, OpenRouter, Gemini's OpenAI-compatible
endpoint, etc. — just point base_url at the service.
"""
import httpx

from .base import LLMError, LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, model: str, base_url: str = "", api_key: str = "",
                 timeout: float = 60, client: httpx.Client | None = None):
        if not model:
            raise ValueError("CHAT_LLM_MODEL is required for the openai provider")
        self.model = model
        self.url = (base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.client = client or httpx.Client(timeout=timeout, headers=headers)

    def complete(self, messages: list[dict], max_tokens: int) -> str:
        payload = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        try:
            resp = self.client.post(self.url, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise LLMError(f"OpenAI-compatible request failed: {e}") from e
