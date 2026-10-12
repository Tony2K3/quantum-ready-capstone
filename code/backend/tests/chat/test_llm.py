import json

import httpx
import pytest

from app import config
from app.llm import PROVIDERS, LLMError, get_provider
from app.llm.anthropic import AnthropicProvider
from app.llm.echo import EchoProvider
from app.llm.openai_compat import OpenAICompatibleProvider

MESSAGES = [
    {"role": "system", "content": "be nice"},
    {"role": "assistant", "content": "orphaned by trimming"},
    {"role": "user", "content": "hi"},
]


def mock_client(response: dict, seen: list, status: int = 200):
    def handler(request):
        seen.append(request)
        return httpx.Response(status, json=response)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_compatible_payload_and_reply():
    seen = []
    client = mock_client({"choices": [{"message": {"content": "hello!"}}]}, seen)
    p = OpenAICompatibleProvider("llama3", base_url="http://localhost:11434/v1", client=client)
    assert p.complete(MESSAGES, max_tokens=50) == "hello!"
    body = json.loads(seen[0].content)
    assert str(seen[0].url) == "http://localhost:11434/v1/chat/completions"
    assert body == {"model": "llama3", "messages": MESSAGES, "max_tokens": 50}


def test_anthropic_splits_system_and_drops_leading_assistant():
    seen = []
    client = mock_client({"content": [{"type": "text", "text": "hey"}]}, seen)
    p = AnthropicProvider("some-model", client=client)
    assert p.complete(MESSAGES, max_tokens=50) == "hey"
    body = json.loads(seen[0].content)
    assert body["system"] == "be nice"
    assert body["messages"] == [{"role": "user", "content": "hi"}]


def test_http_error_becomes_llm_error():
    client = mock_client({"error": "bad key"}, [], status=401)
    with pytest.raises(LLMError):
        OpenAICompatibleProvider("m", client=client).complete(MESSAGES, 10)


def test_get_provider_by_name_and_plugin_path(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "echo")
    assert isinstance(get_provider(), EchoProvider)
    monkeypatch.setattr(config, "LLM_PROVIDER", "app.llm.echo:EchoProvider")
    assert isinstance(get_provider(), EchoProvider)
    monkeypatch.setattr(config, "LLM_PROVIDER", "nope")
    with pytest.raises(ValueError):
        get_provider()


def test_builtin_registry():
    assert {"echo", "openai", "anthropic"} <= set(PROVIDERS)
