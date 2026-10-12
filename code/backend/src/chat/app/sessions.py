"""Session lifecycle + chat turn orchestration."""
import logging
import time

from . import config
from .context import ContextWindow, build_context
from .storage import Store
from .llm import LLMError, LLMProvider

log = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """\
You maintain a running summary of a conversation between a user and an AI assistant. \
Merge the new messages into the existing summary. Keep facts, decisions, the user's goals, \
constraints and preferences, and any open questions; drop pleasantries and repetition. \
Write concise plain prose or bullets and output only the summary."""

SUMMARY_HEADER = "Summary of the earlier part of this conversation (those messages are no longer shown):"


class SessionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class SessionService:
    def __init__(self, store: Store, llm: LLMProvider):
        self.store = store
        self.llm = llm

    def create(self, user_id: str, title: str | None = None, metadata: dict | None = None) -> dict:
        return self.store.create_session(user_id, title or "New chat", metadata)

    def get(self, user_id: str, sid: str) -> dict:
        session = self.store.get_session(sid)
        # Someone else's session is reported as missing, not forbidden, so ids can't be probed.
        if not session or session["user_id"] != user_id:
            raise SessionError("Session not found", 404)
        return self._check_expiry(session)

    def list_all(self, user_id: str, status: str | None = None) -> list[dict]:
        self.store.expire_idle_sessions(config.SESSION_TTL_SECONDS)
        return self.store.list_sessions(user_id, status)

    def close(self, user_id: str, sid: str) -> dict:
        self.get(user_id, sid)
        return self.store.update_session(sid, status="closed")

    def reopen(self, user_id: str, sid: str) -> dict:
        session = self.get(user_id, sid)
        if session["status"] == "active":
            return session
        return self.store.reopen_session(sid)

    def rename(self, user_id: str, sid: str, title: str) -> dict:
        self.get(user_id, sid)
        return self.store.update_session(sid, title=title)

    def delete(self, user_id: str, sid: str) -> None:
        self.get(user_id, sid)
        self.store.delete_session(sid)

    def history(self, user_id: str, sid: str) -> list[dict]:
        self.get(user_id, sid)
        return self.store.get_messages(sid)

    def send(self, user_id: str, sid: str, content: str) -> dict:
        session = self.get(user_id, sid)
        if session["status"] != "active":
            raise SessionError(f"Session is {session['status']}", 409)
        content = content.strip()
        if not content:
            raise SessionError("Message is empty")
        if not self.store.try_lock_session(sid, config.SESSION_LOCK_SECONDS):
            raise SessionError("A reply is already in progress in this chat", 409)

        try:
            user_msg = self.store.add_message(sid, "user", content, self.llm.count_tokens(content))
            if session["title"] == "New chat":
                self.store.update_session(sid, title=content[:40])

            ctx, summarized = self._context(sid)
            reply = self.llm.complete(ctx.messages, max_tokens=config.CONTEXT_RESERVED_FOR_REPLY)
            assistant_msg = self.store.add_message(sid, "assistant", reply, self.llm.count_tokens(reply))
        finally:
            self.store.unlock_session(sid)

        return {
            "user": user_msg,
            "assistant": assistant_msg,
            "context": {"tokens": ctx.token_count, "dropped": ctx.dropped, "summarized": summarized},
        }

    # --- context window ---------------------------------------------------

    def _context(self, sid: str) -> tuple[ContextWindow, int]:
        """Fit the chat into the budget, folding anything that doesn't fit into the summary.

        Returns the context and how many messages are now covered by the summary.
        """
        session = self.store.get_session(sid)
        summary, upto = session["summary"], session["summary_upto"]
        messages = self.store.get_messages(sid)
        history = [m for m in messages if m["id"] > upto]

        # The summary lengthens the system prompt, which can push out more
        # messages, so repeat a couple of times until everything is accounted for.
        for _ in range(3):
            ctx = self._build(summary, history)
            if not ctx.dropped:
                break
            dropped = history[:ctx.dropped]
            try:
                summary = self._summarize(summary, dropped)
            except LLMError as e:
                # Summaries are best-effort: reply without one rather than fail the turn.
                log.warning("Summarizing session %s failed: %s", sid, e)
                break
            upto = dropped[-1]["id"]
            self.store.update_session(sid, summary=summary, summary_upto=upto)
            history = history[ctx.dropped:]
        else:
            ctx = self._build(summary, history)

        return ctx, len(messages) - len(history)

    def _build(self, summary: str, history: list[dict]) -> ContextWindow:
        system = config.SYSTEM_PROMPT
        if summary:
            system += f"\n\n{SUMMARY_HEADER}\n{summary}"
        return build_context(
            system, history,
            config.CONTEXT_MAX_TOKENS, config.CONTEXT_RESERVED_FOR_REPLY,
            count_tokens=self.llm.count_tokens,
        )

    def _summarize(self, summary: str, messages: list[dict]) -> str:
        """Fold messages into the running summary, in batches that fit the model's window."""
        cap = config.SUMMARY_MAX_TOKENS
        budget = config.CONTEXT_MAX_TOKENS - cap - self.llm.count_tokens(SUMMARIZE_PROMPT) - 50
        lines = []
        for m in messages:
            line = f"{m['role'].capitalize()}: {m['content']}"
            room = budget - cap  # leave space for the existing summary in the same request
            if self.llm.count_tokens(line) > room:
                line = line[: max(room, 1) * 4] + " […]"
            lines.append(line)

        while lines:
            batch, used = [], self.llm.count_tokens(summary)
            while lines and (not batch or used + self.llm.count_tokens(lines[0]) <= budget):
                used += self.llm.count_tokens(lines[0])
                batch.append(lines.pop(0))
            prompt = f"Existing summary:\n{summary or '(none yet)'}\n\nNew messages:\n" + "\n\n".join(batch)
            summary = self.llm.complete(
                [{"role": "system", "content": SUMMARIZE_PROMPT}, {"role": "user", "content": prompt}],
                max_tokens=cap,
            ).strip()
            # Providers are asked for at most `cap` tokens; enforce it for ones that ignore that.
            if self.llm.count_tokens(summary) > cap:
                summary = summary[-cap * 4:]
        return summary

    def _check_expiry(self, session: dict) -> dict:
        idle = time.time() - session["last_active_at"]
        if session["status"] == "active" and idle > config.SESSION_TTL_SECONDS:
            return self.store.update_session(session["id"], status="expired")
        return session
