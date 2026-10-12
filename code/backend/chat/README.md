# QuantumReady Assistant

Chat assistant for QuantumReady. Chat backend: user accounts, per-user session lifecycle, conversation storage (PostgreSQL), and context-window handling with running summaries. The LLM layer is provider-agnostic; by default `echo` stands in for a real model.

## Run

Code lives in `code/backend/src/chat`, tests in `code/backend/tests/chat`; this folder holds the docs and config. Run everything from here (`code/backend/chat`):

```
docker compose up -d --wait          # Postgres 16 on localhost:5432 (user/pass/db: chat)
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --app-dir ../src/chat --reload
```

Open http://localhost:8000 and create an account. The schema is created (and upgraded) automatically on startup. To skip Postgres for a quick local run, set `CHAT_DATABASE_URL=sqlite:///chat.db`.

Tests run against SQLite by default. To also run them against Postgres, point them at a separate database (the tests wipe it):

```
docker compose exec postgres psql -U chat -d chat -c "CREATE DATABASE chat_test"
set CHAT_TEST_DATABASE_URL=postgresql://chat:chat@localhost:5432/chat_test
.venv\Scripts\pytest
```

## Layout

Paths are relative to `code/backend/src/chat`.

| File | Purpose |
|---|---|
| `app/storage/` | Storage backends behind one `Store` interface: `postgres.py` (default), `sqlite.py` (fallback) |
| `app/auth.py` | Accounts (scrypt-hashed passwords) and bearer tokens (stored as SHA-256 hashes) |
| `app/sessions.py` | Lifecycle (create / close / reopen / expire / delete), ownership checks, the chat turn, and summarizing trimmed history |
| `app/context.py` | Fits history into a token budget (system prompt plus the newest messages) |
| `app/llm/` | Provider-agnostic LLM layer: `base.py` interface, one adapter per API style, registry in `__init__.py` |
| `app/main.py` | REST API; also serves `static/index.html` |

## API

Every `/api/sessions` route needs `Authorization: Bearer <token>` and only sees the signed-in user's sessions; another user's session id returns 404.

- `POST /api/auth/register` / `POST /api/auth/login` take `{"username", "password"}` and return `{"token", "user"}`
- `POST /api/auth/logout` revokes the token; `GET /api/auth/me` returns the signed-in user
- `POST /api/sessions` creates a session
- `GET /api/sessions?status=active` lists sessions
- `GET /api/sessions/{id}` returns a session with its messages
- `PATCH /api/sessions/{id}` renames (`{"title": ...}`)
- `POST /api/sessions/{id}/close` closes a session
- `POST /api/sessions/{id}/reopen` makes a closed or expired session active again and restarts its idle clock
- `DELETE /api/sessions/{id}` deletes a session
- `POST /api/sessions/{id}/messages` sends `{"content": ...}` and returns the user message, the reply, and context stats (`tokens`, `summarized`, `dropped`). While a reply is being generated the session is locked: a second send returns 409 until the first finishes. The lock lives in the database, so it holds across server processes, and it lapses on its own if a worker dies mid-reply.

## Context window

Each request carries the system prompt plus the newest messages that fit `CHAT_CONTEXT_MAX_TOKENS` (minus the reply reserve). Messages that no longer fit are folded by the model into a running summary that's stored on the session and appended to the system prompt, so long chats keep their earlier facts and decisions. The full history is always kept in the database. If the summary call fails the reply still goes ahead, just without the newest summary.

## Config (env vars)

`CHAT_DATABASE_URL` (default `postgresql://chat:chat@localhost:5432/chat`), `CHAT_SESSION_TTL_SECONDS` (default 24h idle, then expired), `CHAT_CONTEXT_MAX_TOKENS`, `CHAT_CONTEXT_RESERVED_FOR_REPLY` (also used as the reply's `max_tokens`), `CHAT_SUMMARY_MAX_TOKENS` (default 512), `CHAT_AUTH_TOKEN_TTL_SECONDS` (default 30 days), `CHAT_SESSION_LOCK_SECONDS` (how long a reply lock can be held; default 4× the LLM timeout + 30s), `CHAT_SYSTEM_PROMPT` (defaults to the QuantumReady assistant prompt in `app/config.py`).

## Connecting an LLM

Set `CHAT_LLM_PROVIDER`, `CHAT_LLM_MODEL`, and, where needed, `CHAT_LLM_BASE_URL` / `CHAT_LLM_API_KEY` (plus `CHAT_LLM_TIMEOUT_SECONDS`).

| `CHAT_LLM_PROVIDER` | Works with |
|---|---|
| `echo` (default) | Nothing; echoes input for testing |
| `openai` | Any OpenAI-compatible `/chat/completions` API: OpenAI, Azure OpenAI, Ollama, vLLM, LM Studio, llama.cpp, Groq, Together, Mistral, DeepSeek, OpenRouter, Gemini (OpenAI-compatible endpoint) |
| `anthropic` | Anthropic Messages API |
| `my.module:MyClass` | Your own adapter, loaded by import path |

Examples:

```
# Local Ollama
set CHAT_LLM_PROVIDER=openai
set CHAT_LLM_BASE_URL=http://localhost:11434/v1
set CHAT_LLM_MODEL=llama3.1

# Gemini
set CHAT_LLM_PROVIDER=openai
set CHAT_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
set CHAT_LLM_MODEL=<gemini model id>
set CHAT_LLM_API_KEY=...
```

### Adding a provider

Subclass `LLMProvider` (`app/llm/base.py`) and implement `complete(messages, max_tokens) -> str`. `messages` is always the neutral `[{"role": "system"|"user"|"assistant", "content": ...}]` list, system first; the adapter converts it to its API's format. Optionally override `count_tokens` with the model's real tokenizer so context trimming is accurate. Then either add it to `PROVIDERS` in `app/llm/__init__.py` or point `CHAT_LLM_PROVIDER` at it (`mypkg.bedrock:BedrockProvider`). The constructor receives `model`, `base_url`, `api_key` and `timeout` keyword args.

Also set `CHAT_CONTEXT_MAX_TOKENS` to the model's context window. A failed LLM call returns HTTP 502; the user's message stays saved.

Not done yet: streaming replies, accurate token counts (adapters use a ~4 chars/token estimate unless they override `count_tokens`), password reset, and rate limiting on sign-in.
