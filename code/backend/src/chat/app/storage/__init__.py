"""Storage backend selection, driven by CHAT_DATABASE_URL."""
from .. import config
from .base import Store


def get_store(url: str | None = None) -> Store:
    url = url or config.DATABASE_URL
    if url.startswith(("postgresql://", "postgres://")):
        from .postgres import PostgresStore
        return PostgresStore(url)
    if url.startswith("sqlite:///"):
        from .sqlite import SQLiteStore
        return SQLiteStore(url.removeprefix("sqlite:///"))
    raise ValueError(f"Unsupported CHAT_DATABASE_URL: {url!r}")


__all__ = ["Store", "get_store"]
