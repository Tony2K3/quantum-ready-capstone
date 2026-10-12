"""User accounts and sign-in tokens.

Passwords are hashed with scrypt. Sign-in returns a random bearer token; only
its SHA-256 is stored, so a leaked database doesn't leak usable tokens.
"""
import hashlib
import hmac
import re
import secrets

from . import config
from .sessions import SessionError
from .storage import Store

USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")
MIN_PASSWORD_LENGTH = 8
SCRYPT = {"n": 2**14, "r": 8, "p": 1}


class AuthError(SessionError):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message, status_code)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, salt, digest = stored.split("$")
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), dklen=32, **SCRYPT)
    return hmac.compare_digest(candidate.hex(), digest)


# Checked against when the username doesn't exist, so a failed sign-in takes
# the same time either way and doesn't reveal which usernames are registered.
_DUMMY_HASH = hash_password(secrets.token_hex(8))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_user(user: dict) -> dict:
    return {"id": user["id"], "username": user["username"]}


class AuthService:
    def __init__(self, store: Store):
        self.store = store

    def register(self, username: str, password: str) -> dict:
        username = username.strip().lower()
        if not USERNAME_RE.match(username):
            raise AuthError("Username must be 3-32 characters: letters, numbers, . _ or -", 400)
        if len(password) < MIN_PASSWORD_LENGTH:
            raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters", 400)
        user = self.store.create_user(username, hash_password(password))
        if not user:
            raise AuthError("That username is taken", 409)
        return self._issue_token(user)

    def login(self, username: str, password: str) -> dict:
        user = self.store.get_user_by_username(username.strip().lower())
        if not verify_password(password, user["password_hash"] if user else _DUMMY_HASH) or not user:
            raise AuthError("Wrong username or password")
        return self._issue_token(user)

    def logout(self, token: str) -> None:
        self.store.delete_token(_token_hash(token))

    def authenticate(self, token: str | None) -> dict:
        user = self.store.get_user_by_token(_token_hash(token)) if token else None
        if not user:
            raise AuthError("Not signed in")
        return public_user(user)

    def _issue_token(self, user: dict) -> dict:
        token = secrets.token_urlsafe(32)
        self.store.create_token(_token_hash(token), user["id"], config.AUTH_TOKEN_TTL_SECONDS)
        return {"token": token, "user": public_user(user)}
