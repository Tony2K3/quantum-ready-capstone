"""SQLite store — zero-setup fallback for local dev and tests."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

from .base import UPDATABLE_SESSION_FIELDS, Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash  TEXT PRIMARY KEY,                     -- sha256 of the bearer token
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  REAL NOT NULL,
    expires_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',   -- active | closed | expired
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    last_active_at  REAL NOT NULL,
    metadata        TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,                        -- system | user | assistant
    content     TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
"""

# Columns added after the first release; applied to existing databases on startup.
SESSION_COLUMNS = {
    "user_id": "TEXT REFERENCES users(id) ON DELETE CASCADE",
    "summary": "TEXT NOT NULL DEFAULT ''",       # running summary of trimmed history
    "summary_upto": "INTEGER NOT NULL DEFAULT 0",  # last message id folded into it
    "busy_until": "REAL",                          # reply-in-progress lock
}


class SQLiteStore(Store):
    def __init__(self, db_path: str):
        self.db_path = db_path
        with self._conn() as c:
            c.executescript(SCHEMA)
            existing = {r["name"] for r in c.execute("PRAGMA table_info(sessions)")}
            for name, ddl in SESSION_COLUMNS.items():
                if name not in existing:
                    c.execute(f"ALTER TABLE sessions ADD COLUMN {name} {ddl}")
            c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, last_active_at)")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- users and sign-in tokens -----------------------------------------

    def create_user(self, username: str, password_hash: str) -> dict | None:
        uid = uuid.uuid4().hex
        try:
            with self._conn() as c:
                c.execute(
                    "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (uid, username, password_hash, time.time()),
                )
        except sqlite3.IntegrityError:
            return None
        return self.get_user_by_username(username)

    def get_user_by_username(self, username: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    def create_token(self, token_hash: str, user_id: str, ttl_seconds: int) -> None:
        now = time.time()
        with self._conn() as c:
            c.execute("DELETE FROM auth_tokens WHERE expires_at < ?", (now,))
            c.execute(
                "INSERT INTO auth_tokens (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token_hash, user_id, now, now + ttl_seconds),
            )

    def get_user_by_token(self, token_hash: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT u.* FROM auth_tokens t JOIN users u ON u.id = t.user_id"
                " WHERE t.token_hash = ? AND t.expires_at > ?",
                (token_hash, time.time()),
            ).fetchone()
        return dict(row) if row else None

    def delete_token(self, token_hash: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (token_hash,))

    # --- sessions ---------------------------------------------------------

    def create_session(self, user_id: str, title: str, metadata: dict | None = None) -> dict:
        now = time.time()
        sid = uuid.uuid4().hex
        with self._conn() as c:
            c.execute(
                "INSERT INTO sessions (id, user_id, title, status, created_at, updated_at, last_active_at, metadata)"
                " VALUES (?, ?, ?, 'active', ?, ?, ?, ?)",
                (sid, user_id, title, now, now, now, json.dumps(metadata or {})),
            )
        return self.get_session(sid)

    def get_session(self, sid: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        return _session(row) if row else None

    def list_sessions(self, user_id: str, status: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM sessions WHERE user_id = ?", (user_id,)
        if status:
            q, args = q + " AND status = ?", (*args, status)
        with self._conn() as c:
            rows = c.execute(q + " ORDER BY last_active_at DESC", args).fetchall()
        return [_session(r) for r in rows]

    def update_session(self, sid: str, **fields) -> dict | None:
        unknown = set(fields) - UPDATABLE_SESSION_FIELDS
        if unknown:
            raise ValueError(f"Cannot update {sorted(unknown)}")
        if "metadata" in fields:
            fields["metadata"] = json.dumps(fields["metadata"])
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._conn() as c:
            c.execute(f"UPDATE sessions SET {cols} WHERE id = ?", (*fields.values(), sid))
        return self.get_session(sid)

    def reopen_session(self, sid: str) -> dict | None:
        now = time.time()
        with self._conn() as c:
            c.execute(
                "UPDATE sessions SET status = 'active', last_active_at = ?, updated_at = ? WHERE id = ?",
                (now, now, sid),
            )
        return self.get_session(sid)

    def delete_session(self, sid: str) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM sessions WHERE id = ?", (sid,))
        return cur.rowcount > 0

    def expire_idle_sessions(self, ttl_seconds: int) -> int:
        cutoff = time.time() - ttl_seconds
        with self._conn() as c:
            cur = c.execute(
                "UPDATE sessions SET status = 'expired', updated_at = ?"
                " WHERE status = 'active' AND last_active_at < ?",
                (time.time(), cutoff),
            )
        return cur.rowcount

    def try_lock_session(self, sid: str, ttl_seconds: int) -> bool:
        # SQLite serializes writers, so this conditional UPDATE is atomic.
        now = time.time()
        with self._conn() as c:
            cur = c.execute(
                "UPDATE sessions SET busy_until = ?"
                " WHERE id = ? AND (busy_until IS NULL OR busy_until < ?)",
                (now + ttl_seconds, sid, now),
            )
        return cur.rowcount > 0

    def unlock_session(self, sid: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE sessions SET busy_until = NULL WHERE id = ?", (sid,))

    # --- messages ---------------------------------------------------------

    def add_message(self, sid: str, role: str, content: str, token_count: int) -> dict:
        now = time.time()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO messages (session_id, role, content, token_count, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (sid, role, content, token_count, now),
            )
            c.execute(
                "UPDATE sessions SET last_active_at = ?, updated_at = ? WHERE id = ?",
                (now, now, sid),
            )
            row = c.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)

    def get_messages(self, sid: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id", (sid,)
            ).fetchall()
        return [dict(r) for r in rows]


def _session(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["metadata"] = json.loads(d["metadata"])
    d.pop("busy_until", None)
    return d
