import importlib
import os
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app import config
from app.auth import AuthError, AuthService
from app.context import build_context
from app.llm import EchoProvider, LLMError, LLMProvider
from app.sessions import SUMMARIZE_PROMPT, SUMMARY_HEADER, SessionError, SessionService
from app.storage import get_store


PG_URL = os.getenv("CHAT_TEST_DATABASE_URL")


@pytest.fixture(params=["sqlite", "postgres"])
def store(request, tmp_path):
    if request.param == "sqlite":
        store = get_store(f"sqlite:///{tmp_path / 'test.db'}")
    else:
        if not PG_URL:
            pytest.skip("set CHAT_TEST_DATABASE_URL to run Postgres tests")
        store = get_store(PG_URL)
        with store.pool.connection() as c:
            c.execute("TRUNCATE users, sessions CASCADE")
    yield store
    store.close()


@pytest.fixture
def service(store):
    return SessionService(store, EchoProvider())


@pytest.fixture
def auth(store):
    return AuthService(store)


@pytest.fixture
def user(auth):
    return auth.register("alice", "correct horse")["user"]["id"]


class FakeLLM(LLMProvider):
    """Records every call; replies to summary requests with a fixed summary."""

    def __init__(self, fail_summaries: bool = False):
        self.calls = []
        self.fail_summaries = fail_summaries

    def complete(self, messages, max_tokens):
        self.calls.append(messages)
        if messages[0]["content"] == SUMMARIZE_PROMPT:
            if self.fail_summaries:
                raise LLMError("summary backend down")
            return "User is planning a PQC migration for a bank."
        return "ok"


# --- lifecycle --------------------------------------------------------------

def test_send_stores_both_messages(service, user):
    s = service.create(user)
    r = service.send(user, s["id"], "hello")
    assert r["assistant"]["content"].endswith("hello")
    assert [m["role"] for m in service.history(user, s["id"])] == ["user", "assistant"]
    assert service.get(user, s["id"])["title"] == "hello"


def test_closed_session_rejects_messages(service, user):
    s = service.create(user)
    service.close(user, s["id"])
    with pytest.raises(SessionError) as e:
        service.send(user, s["id"], "hi")
    assert e.value.status_code == 409


def test_idle_session_expires(service, user, monkeypatch):
    s = service.create(user)
    monkeypatch.setattr(config, "SESSION_TTL_SECONDS", 1)
    monkeypatch.setattr(time, "time", lambda: s["last_active_at"] + 5)
    assert service.get(user, s["id"])["status"] == "expired"


def test_reopen_closed_and_expired_sessions(service, user, store):
    s = service.create(user)
    service.close(user, s["id"])
    assert service.reopen(user, s["id"])["status"] == "active"
    service.send(user, s["id"], "back again")

    store.expire_idle_sessions(0)
    assert service.get(user, s["id"])["status"] == "expired"
    reopened = service.reopen(user, s["id"])
    assert reopened["status"] == "active"
    # The idle clock restarts, so it doesn't immediately expire again.
    assert service.get(user, s["id"])["status"] == "active"


def test_delete(service, user):
    s = service.create(user)
    service.delete(user, s["id"])
    with pytest.raises(SessionError):
        service.get(user, s["id"])


def test_list_and_bulk_expire(service, store, user):
    a, b = service.create(user), service.create(user)
    service.close(user, b["id"])
    assert store.expire_idle_sessions(0) == 1  # only the active one
    statuses = {s["id"]: s["status"] for s in service.list_all(user)}
    assert statuses == {a["id"]: "expired", b["id"]: "closed"}


def test_metadata_roundtrip_and_unknown_id(service, user):
    s = service.create(user, "t", {"tags": ["x"]})
    assert service.get(user, s["id"])["metadata"] == {"tags": ["x"]}
    with pytest.raises(SessionError):
        service.get(user, "not-a-real-id")


def test_deleting_session_deletes_messages(service, store, user):
    s = service.create(user)
    service.send(user, s["id"], "hi")
    service.delete(user, s["id"])
    assert store.get_messages(s["id"]) == []


# --- users and ownership ------------------------------------------------------

def test_register_login_logout(auth):
    token = auth.register("Bob", "hunter2hunter2")["token"]
    assert auth.authenticate(token)["username"] == "bob"
    assert auth.login("BOB", "hunter2hunter2")["user"]["username"] == "bob"
    auth.logout(token)
    with pytest.raises(AuthError):
        auth.authenticate(token)


def test_bad_registrations_and_logins(auth):
    auth.register("carol", "longenough")
    for name, pw, code in [("carol", "longenough", 409), ("x", "longenough", 400), ("dave", "short", 400)]:
        with pytest.raises(AuthError) as e:
            auth.register(name, pw)
        assert e.value.status_code == code
    for name, pw in [("carol", "wrong-password"), ("nobody", "longenough")]:
        with pytest.raises(AuthError) as e:
            auth.login(name, pw)
        assert e.value.status_code == 401


def test_expired_token_is_rejected(auth, monkeypatch):
    monkeypatch.setattr(config, "AUTH_TOKEN_TTL_SECONDS", -1)
    token = auth.register("erin", "longenough")["token"]
    with pytest.raises(AuthError):
        auth.authenticate(token)


def test_users_only_see_their_own_sessions(service, auth, user):
    other = auth.register("mallory", "longenough")["user"]["id"]
    mine = service.create(user)
    service.create(other)
    assert [s["id"] for s in service.list_all(user)] == [mine["id"]]
    for action in (service.get, service.history, service.close, service.reopen, service.delete):
        with pytest.raises(SessionError) as e:
            action(other, mine["id"])
        assert e.value.status_code == 404
    with pytest.raises(SessionError):
        service.send(other, mine["id"], "hi")
    assert service.get(user, mine["id"])["status"] == "active"


def test_api_requires_sign_in(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    main = importlib.reload(importlib.import_module("app.main"))
    with TestClient(main.app) as client:
        assert client.get("/api/sessions").status_code == 401
        assert client.get("/api/sessions", headers={"Authorization": "Bearer nope"}).status_code == 401
        token = client.post("/api/auth/register", json={"username": "api", "password": "longenough"}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        sid = client.post("/api/sessions", json={}, headers=h).json()["id"]
        assert client.post(f"/api/sessions/{sid}/messages", json={"content": "hi"}, headers=h).status_code == 200
        assert client.post(f"/api/sessions/{sid}/close", headers=h).json()["status"] == "closed"
        assert client.post(f"/api/sessions/{sid}/reopen", headers=h).json()["status"] == "active"
        assert client.get("/api/auth/me", headers=h).json()["username"] == "api"
        assert client.post("/api/auth/logout", headers=h).status_code == 204
        assert client.get("/api/sessions", headers=h).status_code == 401


# --- concurrent sends -----------------------------------------------------------

def test_second_send_while_replying_is_rejected(service, store, user):
    s = service.create(user)
    assert store.try_lock_session(s["id"], 60)  # a reply is in flight
    with pytest.raises(SessionError) as e:
        service.send(user, s["id"], "impatient")
    assert e.value.status_code == 409
    assert store.get_messages(s["id"]) == []  # nothing half-saved
    store.unlock_session(s["id"])
    service.send(user, s["id"], "now it works")


def test_simultaneous_sends_only_one_wins(store, user):
    started, release = threading.Event(), threading.Event()

    class Slow(LLMProvider):
        def complete(self, messages, max_tokens):
            started.set()
            release.wait(5)
            return "slow reply"

    service = SessionService(store, Slow())
    s = service.create(user)
    first = threading.Thread(target=service.send, args=(user, s["id"], "first"))
    first.start()
    assert started.wait(5)
    with pytest.raises(SessionError) as e:
        service.send(user, s["id"], "second")
    assert e.value.status_code == 409
    release.set()
    first.join(5)
    assert [m["content"] for m in store.get_messages(s["id"])] == ["first", "slow reply"]


def test_stale_lock_lapses(service, store, user):
    s = service.create(user)
    assert store.try_lock_session(s["id"], -1)  # a worker died holding an already-lapsed lock
    service.send(user, s["id"], "hi")


def test_lock_released_when_llm_fails(store, user):
    class Broken(LLMProvider):
        def complete(self, messages, max_tokens):
            raise LLMError("down")

    service = SessionService(store, Broken())
    s = service.create(user)
    with pytest.raises(LLMError):
        service.send(user, s["id"], "hi")
    assert store.try_lock_session(s["id"], 60)


# --- context window and summaries ---------------------------------------------

def test_context_keeps_most_recent_within_budget():
    history = [{"role": "user", "content": "x" * 400} for _ in range(10)]  # ~100 tokens each
    ctx = build_context("sys", history, max_tokens=350, reserved_for_reply=0)
    assert ctx.messages[0]["role"] == "system"
    assert len(ctx.messages) == 4  # system + 3 most recent
    assert ctx.dropped == 7


def test_context_truncates_oversized_latest_message():
    ctx = build_context("sys", [{"role": "user", "content": "y" * 10_000}], 100, 0)
    assert len(ctx.messages) == 2
    assert len(ctx.messages[1]["content"]) < 10_000


@pytest.fixture
def small_window(monkeypatch):
    monkeypatch.setattr(config, "SYSTEM_PROMPT", "sys")
    monkeypatch.setattr(config, "CONTEXT_MAX_TOKENS", 400)
    monkeypatch.setattr(config, "CONTEXT_RESERVED_FOR_REPLY", 50)
    monkeypatch.setattr(config, "SUMMARY_MAX_TOKENS", 60)


def test_trimmed_messages_are_summarized(store, user, small_window):
    llm = FakeLLM()
    service = SessionService(store, llm)
    s = service.create(user)
    for i in range(6):
        r = service.send(user, s["id"], f"message {i} " + "z" * 400)  # ~100 tokens each

    assert r["context"]["summarized"] > 0
    assert r["context"]["dropped"] == 0
    session = service.get(user, s["id"])
    assert session["summary"] == "User is planning a PQC migration for a bank."
    assert session["summary_upto"] > 0
    # The reply request carries the summary in its system prompt.
    last_reply_call = llm.calls[-1]
    assert SUMMARY_HEADER in last_reply_call[0]["content"]
    assert "PQC migration" in last_reply_call[0]["content"]
    # Full history is still stored and returned.
    assert len(service.history(user, s["id"])) == 12


def test_summary_failure_still_replies(store, user, small_window):
    service = SessionService(store, FakeLLM(fail_summaries=True))
    s = service.create(user)
    for i in range(6):
        r = service.send(user, s["id"], f"message {i} " + "z" * 400)
    assert r["assistant"]["content"] == "ok"
    assert r["context"]["dropped"] > 0
    assert service.get(user, s["id"])["summary"] == ""


def test_summary_is_capped_for_providers_that_ignore_max_tokens(store, user, small_window):
    service = SessionService(store, EchoProvider())  # echoes its whole prompt back
    s = service.create(user)
    for i in range(8):
        service.send(user, s["id"], f"message {i} " + "z" * 400)
    summary = service.get(user, s["id"])["summary"]
    assert summary and len(summary) <= config.SUMMARY_MAX_TOKENS * 4
