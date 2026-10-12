"""PostgreSQL-backed conversation storage (psycopg 3 + connection pool)."""
import uuid

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .base import UPDATABLE_SESSION_FIELDS, Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash  TEXT PRIMARY KEY,               -- sha256 of the bearer token
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'closed', 'expired')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'
);

-- Added after the first release; IF NOT EXISTS upgrades existing databases.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS summary TEXT NOT NULL DEFAULT '';       -- running summary of trimmed history
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS summary_upto BIGINT NOT NULL DEFAULT 0; -- last message id folded into it
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS busy_until TIMESTAMPTZ;                 -- reply-in-progress lock

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id, last_active_at DESC);

CREATE INDEX IF NOT EXISTS idx_sessions_status_active
    ON sessions (status, last_active_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
    content     TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id, id);
"""


class PostgresStore(Store):
    def __init__(self, url: str, min_size: int = 1, max_size: int = 10):
        self.pool = ConnectionPool(
            url, min_size=min_size, max_size=max_size,
            kwargs={"row_factory": dict_row}, open=True,
        )
        with self.pool.connection() as c:
            c.execute(SCHEMA)

    def close(self) -> None:
        self.pool.close()

    # --- users and sign-in tokens -----------------------------------------

    def create_user(self, username: str, password_hash: str) -> dict | None:
        with self.pool.connection() as c:
            row = c.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)"
                " ON CONFLICT (username) DO NOTHING RETURNING *",
                (username, password_hash),
            ).fetchone()
        return _user(row) if row else None

    def get_user_by_username(self, username: str) -> dict | None:
        with self.pool.connection() as c:
            row = c.execute("SELECT * FROM users WHERE username = %s", (username,)).fetchone()
        return _user(row) if row else None

    def create_token(self, token_hash: str, user_id: str, ttl_seconds: int) -> None:
        with self.pool.connection() as c:
            c.execute("DELETE FROM auth_tokens WHERE expires_at < now()")
            c.execute(
                "INSERT INTO auth_tokens (token_hash, user_id, expires_at)"
                " VALUES (%s, %s, now() + make_interval(secs => %s))",
                (token_hash, user_id, ttl_seconds),
            )

    def get_user_by_token(self, token_hash: str) -> dict | None:
        with self.pool.connection() as c:
            row = c.execute(
                "SELECT u.* FROM auth_tokens t JOIN users u ON u.id = t.user_id"
                " WHERE t.token_hash = %s AND t.expires_at > now()",
                (token_hash,),
            ).fetchone()
        return _user(row) if row else None

    def delete_token(self, token_hash: str) -> None:
        with self.pool.connection() as c:
            c.execute("DELETE FROM auth_tokens WHERE token_hash = %s", (token_hash,))

    # --- sessions ---------------------------------------------------------

    def create_session(self, user_id: str, title: str, metadata: dict | None = None) -> dict:
        with self.pool.connection() as c:
            row = c.execute(
                "INSERT INTO sessions (user_id, title, metadata) VALUES (%s, %s, %s) RETURNING *",
                (user_id, title, Jsonb(metadata or {})),
            ).fetchone()
        return _session(row)

    def get_session(self, sid: str) -> dict | None:
        if not _is_uuid(sid):
            return None
        with self.pool.connection() as c:
            row = c.execute("SELECT * FROM sessions WHERE id = %s", (sid,)).fetchone()
        return _session(row) if row else None

    def list_sessions(self, user_id: str, status: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM sessions WHERE user_id = %s", (user_id,)
        if status:
            q, args = q + " AND status = %s", (*args, status)
        with self.pool.connection() as c:
            rows = c.execute(q + " ORDER BY last_active_at DESC", args).fetchall()
        return [_session(r) for r in rows]

    def update_session(self, sid: str, **fields) -> dict | None:
        if not _is_uuid(sid):
            return None
        unknown = set(fields) - UPDATABLE_SESSION_FIELDS
        if unknown:
            raise ValueError(f"Cannot update {sorted(unknown)}")
        if "metadata" in fields:
            fields["metadata"] = Jsonb(fields["metadata"])
        cols = ", ".join(f"{k} = %s" for k in fields)
        with self.pool.connection() as c:
            row = c.execute(
                f"UPDATE sessions SET {cols}, updated_at = now() WHERE id = %s RETURNING *",
                (*fields.values(), sid),
            ).fetchone()
        return _session(row) if row else None

    def reopen_session(self, sid: str) -> dict | None:
        if not _is_uuid(sid):
            return None
        with self.pool.connection() as c:
            row = c.execute(
                "UPDATE sessions SET status = 'active', last_active_at = now(), updated_at = now()"
                " WHERE id = %s RETURNING *",
                (sid,),
            ).fetchone()
        return _session(row) if row else None

    def delete_session(self, sid: str) -> bool:
        if not _is_uuid(sid):
            return False
        with self.pool.connection() as c:
            cur = c.execute("DELETE FROM sessions WHERE id = %s", (sid,))
        return cur.rowcount > 0

    def expire_idle_sessions(self, ttl_seconds: int) -> int:
        with self.pool.connection() as c:
            cur = c.execute(
                "UPDATE sessions SET status = 'expired', updated_at = now()"
                " WHERE status = 'active'"
                " AND last_active_at < now() - make_interval(secs => %s)",
                (ttl_seconds,),
            )
        return cur.rowcount

    def try_lock_session(self, sid: str, ttl_seconds: int) -> bool:
        # A conditional UPDATE is atomic across connections and server processes.
        with self.pool.connection() as c:
            cur = c.execute(
                "UPDATE sessions SET busy_until = now() + make_interval(secs => %s)"
                " WHERE id = %s AND (busy_until IS NULL OR busy_until < now())",
                (ttl_seconds, sid),
            )
        return cur.rowcount > 0

    def unlock_session(self, sid: str) -> None:
        with self.pool.connection() as c:
            c.execute("UPDATE sessions SET busy_until = NULL WHERE id = %s", (sid,))

    # --- messages ---------------------------------------------------------

    def add_message(self, sid: str, role: str, content: str, token_count: int) -> dict:
        # One transaction: the message insert and the session activity bump.
        with self.pool.connection() as c:
            row = c.execute(
                "INSERT INTO messages (session_id, role, content, token_count)"
                " VALUES (%s, %s, %s, %s) RETURNING *",
                (sid, role, content, token_count),
            ).fetchone()
            c.execute(
                "UPDATE sessions SET last_active_at = %s, updated_at = %s WHERE id = %s",
                (row["created_at"], row["created_at"], sid),
            )
        return _message(row)

    def get_messages(self, sid: str) -> list[dict]:
        if not _is_uuid(sid):
            return []
        with self.pool.connection() as c:
            rows = c.execute(
                "SELECT * FROM messages WHERE session_id = %s ORDER BY id", (sid,)
            ).fetchall()
        return [_message(r) for r in rows]


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def _user(row: dict) -> dict:
    return {**row, "id": str(row["id"]), "created_at": row["created_at"].timestamp()}


def _session(row: dict) -> dict:
    row = {k: v for k, v in row.items() if k != "busy_until"}
    return {
        **row,
        "id": str(row["id"]),
        "user_id": str(row["user_id"]) if row["user_id"] else None,
        "created_at": row["created_at"].timestamp(),
        "updated_at": row["updated_at"].timestamp(),
        "last_active_at": row["last_active_at"].timestamp(),
    }


def _message(row: dict) -> dict:
    return {**row, "session_id": str(row["session_id"]), "created_at": row["created_at"].timestamp()}
