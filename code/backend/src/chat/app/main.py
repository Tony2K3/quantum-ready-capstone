from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .auth import AuthService
from .storage import get_store
from .llm import LLMError, get_provider
from .sessions import SessionError, SessionService

STATIC = Path(__file__).resolve().parent.parent / "static"

store = get_store()
service = SessionService(store, get_provider())
auth = AuthService(store)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    store.close()


app = FastAPI(title="QuantumReady Assistant", lifespan=lifespan)


class Credentials(BaseModel):
    username: str
    password: str


class CreateSession(BaseModel):
    title: str | None = None
    metadata: dict | None = None


class UpdateSession(BaseModel):
    title: str


class SendMessage(BaseModel):
    content: str


def bearer_token(authorization: str | None = Header(None)) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user(token: str | None = Depends(bearer_token)) -> str:
    """The signed-in user's id; every session route is scoped to it."""
    return auth.authenticate(token)["id"]


@app.exception_handler(SessionError)
def session_error(_: Request, exc: SessionError):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)


@app.exception_handler(LLMError)
def llm_error(_: Request, exc: LLMError):
    return JSONResponse({"detail": str(exc)}, status_code=502)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


# --- auth -------------------------------------------------------------------

@app.post("/api/auth/register", status_code=201)
def register(body: Credentials):
    return auth.register(body.username, body.password)


@app.post("/api/auth/login")
def login(body: Credentials):
    return auth.login(body.username, body.password)


@app.post("/api/auth/logout", status_code=204)
def logout(token: str | None = Depends(bearer_token)):
    if token:
        auth.logout(token)


@app.get("/api/auth/me")
def me(token: str | None = Depends(bearer_token)):
    return auth.authenticate(token)


# --- sessions ---------------------------------------------------------------

@app.post("/api/sessions", status_code=201)
def create_session(body: CreateSession, user: str = Depends(current_user)):
    return service.create(user, body.title, body.metadata)


@app.get("/api/sessions")
def list_sessions(status: str | None = None, user: str = Depends(current_user)):
    return service.list_all(user, status)


@app.get("/api/sessions/{sid}")
def get_session(sid: str, user: str = Depends(current_user)):
    return {**service.get(user, sid), "messages": service.history(user, sid)}


@app.patch("/api/sessions/{sid}")
def rename_session(sid: str, body: UpdateSession, user: str = Depends(current_user)):
    return service.rename(user, sid, body.title)


@app.post("/api/sessions/{sid}/close")
def close_session(sid: str, user: str = Depends(current_user)):
    return service.close(user, sid)


@app.post("/api/sessions/{sid}/reopen")
def reopen_session(sid: str, user: str = Depends(current_user)):
    return service.reopen(user, sid)


@app.delete("/api/sessions/{sid}", status_code=204)
def delete_session(sid: str, user: str = Depends(current_user)):
    service.delete(user, sid)


@app.post("/api/sessions/{sid}/messages")
def send_message(sid: str, body: SendMessage, user: str = Depends(current_user)):
    return service.send(user, sid, body.content)
