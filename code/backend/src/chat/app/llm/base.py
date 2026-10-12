"""The contract every LLM adapter implements."""
from ..context import estimate_tokens


class LLMError(Exception):
    """Raised when a provider call fails (network, auth, bad response)."""


class LLMProvider:
    """Subclass this to connect a new model.

    `messages` is provider-neutral: [{"role": "system"|"user"|"assistant",
    "content": str}], system first. Adapters translate it to their API's format.
    """

    def complete(self, messages: list[dict], max_tokens: int) -> str:
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        # Override with the model's real tokenizer when one is available.
        return estimate_tokens(text)
