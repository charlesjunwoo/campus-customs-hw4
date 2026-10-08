"""Account creation, login, and sessions for Campus Customs.

Passwords
  * Hashed with PBKDF2-HMAC-SHA256, a unique 16-byte random salt per user, and
    PBKDF2_ITERATIONS rounds. Only the hash string is stored; the plain password
    is never written to disk, logged, or returned by any endpoint.
  * Stored as  pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>  so the work
    factor can be raised later without breaking existing accounts.
  * Rows seeded before this module use the older 3-part form
    pbkdf2_sha256$<salt>$<hash_hex>; those verify with LEGACY_ITERATIONS and are
    upgraded to the current format on their next successful login.
  * Comparisons use hmac.compare_digest (constant time).

Sessions
  * Login/registration issues a random 256-bit token in an HttpOnly, SameSite=Lax
    cookie. The database keeps only the SHA-256 of the token, so a leaked
    database cannot be replayed as live sessions.

Nothing here ever hands password_hash to the client or to the AI agent: every
response uses the PublicUser model.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000  # OWASP 2023+ recommendation for PBKDF2-HMAC-SHA256
LEGACY_ITERATIONS = int(os.getenv("CC_LEGACY_PBKDF2_ITERATIONS", "120000"))  # seeded users (confirmed with the test user)
SALT_BYTES = 16

SESSION_COOKIE = "cc_session"
SESSION_DAYS = 7
COOKIE_SECURE = os.getenv("CC_COOKIE_SECURE", "0") == "1"  # set to 1 behind HTTPS

MIN_PASSWORD, MAX_PASSWORD = 8, 128
MAX_FAILURES, FAILURE_WINDOW_S = 5, 15 * 60

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

router = APIRouter(prefix="/api/auth", tags=["auth"])

_db_path: Path | None = None


def init(db_path: Path) -> None:
    """Point the module at the database and create the sessions table if needed."""
    global _db_path
    _db_path = db_path
    if not db_path.is_file():
        return
    with _connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                   token_hash TEXT PRIMARY KEY,
                   user_id    INTEGER NOT NULL REFERENCES users(id),
                   created_at TEXT NOT NULL DEFAULT (datetime('now')),
                   expires_at TEXT NOT NULL
               )"""
        )
        conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")


def _connect() -> sqlite3.Connection:
    if _db_path is None or not _db_path.is_file():
        raise HTTPException(503, "Database not available")
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------- hashing


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return f"{ALGORITHM}${iterations}${salt}${digest.hex()}"


def _parse(stored: str) -> tuple[int, str, str] | None:
    parts = stored.split("$")
    if parts[0] != ALGORITHM:
        return None
    if len(parts) == 4 and parts[1].isdigit():
        return int(parts[1]), parts[2], parts[3]
    if len(parts) == 3:  # legacy seed format, no iteration count
        return LEGACY_ITERATIONS, parts[1], parts[2]
    return None


def verify_password(password: str, stored: str) -> bool:
    parsed = _parse(stored)
    if parsed is None:
        return False
    iterations, salt, expected = parsed
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return hmac.compare_digest(digest.hex(), expected)


def needs_rehash(stored: str) -> bool:
    parsed = _parse(stored)
    return parsed is None or stored.count("$") != 3 or parsed[0] < PBKDF2_ITERATIONS


# Verified against when the email is unknown, so response time does not reveal
# which emails have accounts.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


# ---------------------------------------------------------------- throttling

_failures: dict[str, deque[float]] = defaultdict(deque)


def _throttle_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "?"
    return f"{host}|{email}"


def _check_throttle(key: str) -> None:
    window = _failures[key]
    now = time.monotonic()
    while window and now - window[0] > FAILURE_WINDOW_S:
        window.popleft()
    if len(window) >= MAX_FAILURES:
        raise HTTPException(429, "Too many failed attempts. Please wait a few minutes and try again.")


# ---------------------------------------------------------------- schemas


def _clean_email(v: str) -> str:
    v = v.strip().lower()
    if not EMAIL_RE.match(v) or len(v) > 254:
        raise ValueError("Enter a valid email address.")
    return v


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: str
    password: str = Field(min_length=MIN_PASSWORD, max_length=MAX_PASSWORD)

    @field_validator("first_name", "last_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Required.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _clean_email(v)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class PublicUser(BaseModel):
    """The only user shape that ever leaves the server (no password_hash)."""

    id: int
    first_name: str
    last_name: str
    name: str
    email: str


def _public(row: sqlite3.Row) -> PublicUser:
    name = row["name"] or ""
    first = row["first_name"] or (name.split(" ", 1)[0] if name else "")
    last = row["last_name"] or (name.split(" ", 1)[1] if " " in name else "")
    return PublicUser(id=row["id"], first_name=first, last_name=last, name=name, email=row["email"])


# ---------------------------------------------------------------- sessions


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _start_session(conn: sqlite3.Connection, response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_token_hash(token), user_id, expires.strftime("%Y-%m-%d %H:%M:%S")),
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )


def current_user(token: str | None) -> PublicUser | None:
    """Resolve a session cookie to a user. Reusable by other routes (e.g. chat)."""
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute(
            """SELECT u.id, u.name, u.email, u.first_name, u.last_name
               FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > datetime('now')""",
            (_token_hash(token),),
        ).fetchone()
    return _public(row) if row else None


# ---------------------------------------------------------------- routes


@router.post("/register", response_model=PublicUser, status_code=201)
def register(req: RegisterRequest, response: Response) -> PublicUser:
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM users WHERE lower(email) = ?", (req.email,)).fetchone():
            raise HTTPException(409, "An account with that email already exists. Try logging in.")
        cur = conn.execute(
            """INSERT INTO users (name, email, password_hash, first_name, last_name)
               VALUES (?, ?, ?, ?, ?)""",
            (f"{req.first_name} {req.last_name}", req.email, hash_password(req.password),
             req.first_name, req.last_name),
        )
        user_id = cur.lastrowid
        _start_session(conn, response, user_id)
        row = conn.execute(
            "SELECT id, name, email, first_name, last_name FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return _public(row)


@router.post("/login", response_model=PublicUser)
def login(req: LoginRequest, request: Request, response: Response) -> PublicUser:
    key = _throttle_key(request, req.email)
    _check_throttle(key)
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, email, first_name, last_name, password_hash FROM users WHERE lower(email) = ?",
            (req.email,),
        ).fetchone()
        ok = verify_password(req.password, row["password_hash"] if row else _DUMMY_HASH) and row is not None
        if not ok:
            _failures[key].append(time.monotonic())
            raise HTTPException(401, "Incorrect email or password.")
        _failures.pop(key, None)
        if needs_rehash(row["password_hash"]):
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(req.password), row["id"])
            )
        _start_session(conn, response, row["id"])
    return _public(row)


@router.post("/logout", status_code=204)
def logout(response: Response, cc_session: str | None = Cookie(default=None)) -> Response:
    if cc_session:
        with _connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(cc_session),))
    response.status_code = 204
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me", response_model=PublicUser)
def me(cc_session: str | None = Cookie(default=None)) -> PublicUser:
    user = current_user(cc_session)
    if user is None:
        raise HTTPException(401, "Not signed in.")
    return user
