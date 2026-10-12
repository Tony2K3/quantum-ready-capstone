"""Context-window handling: fit conversation history into a token budget."""
from dataclasses import dataclass
from typing import Callable


def estimate_tokens(text: str) -> int:
    # Rough heuristic (~4 chars/token); providers can override count_tokens.
    return max(1, len(text) // 4)


@dataclass
class ContextWindow:
    messages: list[dict]      # [{"role", "content"}] ready to send to the LLM
    token_count: int
    dropped: int              # number of history messages that didn't fit


def build_context(
    system_prompt: str,
    history: list[dict],
    max_tokens: int,
    reserved_for_reply: int,
    count_tokens: Callable[[str], int] = estimate_tokens,
) -> ContextWindow:
    """Keep the system prompt plus the most recent messages that fit the budget.

    `history` is oldest-first and must include the latest user message, which is
    always kept (truncated from the front if it alone exceeds the budget).
    """
    budget = max_tokens - reserved_for_reply
    system = {"role": "system", "content": system_prompt}
    used = count_tokens(system_prompt)

    kept: list[dict] = []
    for i, msg in enumerate(reversed(history)):
        cost = msg.get("token_count") or count_tokens(msg["content"])
        if used + cost > budget:
            if i == 0:
                # Latest message is too big on its own: keep its tail.
                room = max(0, budget - used) * 4
                tail = msg["content"][-room:] if room else ""
                kept.append({"role": msg["role"], "content": tail})
                used = budget
            break
        kept.append({"role": msg["role"], "content": msg["content"]})
        used += cost

    kept.reverse()
    return ContextWindow(
        messages=[system, *kept],
        token_count=used,
        dropped=len(history) - len(kept),
    )
