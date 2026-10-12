"""The contract every storage backend implements.

Sessions, messages and users are returned as plain dicts; timestamps are Unix
epoch floats and ids are strings, whatever the backend stores internally.
"""
from abc import ABC, abstractmethod

UPDATABLE_SESSION_FIELDS = {"title", "status", "metadata", "summary", "summary_upto"}


class Store(ABC):
    # --- users and sign-in tokens -------------------------------------------

    @abstractmethod
    def create_user(self, username: str, password_hash: str) -> dict | None:
        """Returns None if the username is taken."""

    @abstractmethod
    def get_user_by_username(self, username: str) -> dict | None: ...

    @abstractmethod
    def create_token(self, token_hash: str, user_id: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    def get_user_by_token(self, token_hash: str) -> dict | None:
        """The token's user, or None if the token is unknown or expired."""

    @abstractmethod
    def delete_token(self, token_hash: str) -> None: ...

    # --- sessions -------------------------------------------------------------

    @abstractmethod
    def create_session(self, user_id: str, title: str, metadata: dict | None = None) -> dict: ...

    @abstractmethod
    def get_session(self, sid: str) -> dict | None: ...

    @abstractmethod
    def list_sessions(self, user_id: str, status: str | None = None) -> list[dict]: ...

    @abstractmethod
    def update_session(self, sid: str, **fields) -> dict | None: ...

    @abstractmethod
    def reopen_session(self, sid: str) -> dict | None:
        """Mark the session active and reset its idle clock."""

    @abstractmethod
    def delete_session(self, sid: str) -> bool: ...

    @abstractmethod
    def expire_idle_sessions(self, ttl_seconds: int) -> int: ...

    @abstractmethod
    def try_lock_session(self, sid: str, ttl_seconds: int) -> bool:
        """Atomically claim the session for one reply; False if already claimed."""

    @abstractmethod
    def unlock_session(self, sid: str) -> None: ...

    # --- messages -------------------------------------------------------------

    @abstractmethod
    def add_message(self, sid: str, role: str, content: str, token_count: int) -> dict: ...

    @abstractmethod
    def get_messages(self, sid: str) -> list[dict]: ...

    def close(self) -> None:
        pass
