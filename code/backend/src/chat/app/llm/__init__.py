"""Provider registry.

Pick a provider with CHAT_LLM_PROVIDER:
  - a built-in name below, or
  - "some.module:ClassName" to load your own LLMProvider subclass without
    touching this package.
"""
import importlib

from .. import config
from .anthropic import AnthropicProvider
from .base import LLMError, LLMProvider
from .echo import EchoProvider
from .openai_compat import OpenAICompatibleProvider

PROVIDERS: dict[str, type[LLMProvider]] = {
    "echo": EchoProvider,
    "openai": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
}


def register(name: str, cls: type[LLMProvider]) -> None:
    PROVIDERS[name] = cls


def _resolve(name: str) -> type[LLMProvider]:
    if ":" in name:
        module, _, attr = name.partition(":")
        return getattr(importlib.import_module(module), attr)
    try:
        return PROVIDERS[name]
    except KeyError:
        raise ValueError(f"Unknown LLM provider {name!r}; choose from {sorted(PROVIDERS)}") from None


def get_provider() -> LLMProvider:
    cls = _resolve(config.LLM_PROVIDER)
    return cls(
        model=config.LLM_MODEL,
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
        timeout=config.LLM_TIMEOUT_SECONDS,
    )


__all__ = ["LLMError", "LLMProvider", "PROVIDERS", "get_provider", "register"]
