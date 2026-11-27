import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from threading import BoundedSemaphore, Lock
from time import monotonic
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, Response, Security
from fastapi.security import APIKeyCookie
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import LoginSession, User

SESSION_COOKIE = "lifeflow_session"
SESSION_AGE = timedelta(hours=12)
# Keep password verification memory bounded even under concurrent requests.
password_workers = BoundedSemaphore(4)
session_cookie = APIKeyCookie(name=SESSION_COOKIE, auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_session)]
SessionToken = Annotated[str | None, Security(session_cookie)]


class AuthAttemptLimit:
    def __init__(self) -> None:
        self.lock = Lock()
        self.window = 0
        self.clients: dict[str, int] = {}

    def check(self, source: str) -> None:
        with self.lock:
            window = int(monotonic() // 60)
            if window != self.window:
                self.window = window
                self.clients.clear()

            attempts = self.clients.get(source, 0)
            if attempts >= 30 or (attempts == 0 and len(self.clients) >= 4096):
                raise HTTPException(
                    status_code=429,
                    detail="Слишком много попыток. Повторите через минуту.",
                    headers={"Retry-After": "60"},
                )
            self.clients[source] = attempts + 1


def limit_auth_attempts(request: Request) -> None:
    source = request.client.host if request.client is not None else "unknown"
    request.app.state.auth_attempts.check(source)


def derive_password(password: str, salt: bytes) -> bytes:
    if not password_workers.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="Сервис входа занят. Повторите через несколько секунд.",
            headers={"Retry-After": "3"},
        )
    try:
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**15,
            r=8,
            p=3,
            maxmem=64 * 1024**2,
            dklen=32,
        )
    finally:
        password_workers.release()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"{salt.hex()}:{derive_password(password, salt).hex()}"


def verify_password(password: str, password_hash: str | None) -> bool:
    salt = bytes(16)
    expected = bytes(32)
    if password_hash is not None:
        salt_hex, expected_hex = password_hash.split(":", maxsplit=1)
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(expected_hex)

    # Derive a hash for unknown accounts as well, to keep the login flow comparable.
    matches = hmac.compare_digest(derive_password(password, salt), expected)
    return password_hash is not None and matches


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def start_session(
    db: Session,
    user_id: int,
    previous_token: str | None,
    response: Response,
    secure: bool,
) -> None:
    now = datetime.now(UTC)
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
    revoke_session(db, previous_token)
    token = secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            token_hash=token_hash(token), user_id=user_id, expires_at=now + SESSION_AGE
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_AGE.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="lax",
    )


def revoke_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(
            delete(LoginSession).where(LoginSession.token_hash == token_hash(token))
        )


def current_user(db: DatabaseSession, token: SessionToken) -> User:
    if token:
        user = db.scalar(
            select(User)
            .join(LoginSession, LoginSession.user_id == User.id)
            .where(
                LoginSession.token_hash == token_hash(token),
                LoginSession.expires_at > datetime.now(UTC),
            )
        )
        if user is not None:
            return user

    raise HTTPException(status_code=401, detail="Войдите в аккаунт")


CurrentUser = Annotated[User, Depends(current_user)]


def require_request_header(
    request: Request,
    marker: Annotated[str | None, Header(alias="X-LifeFlow-Request")] = None,
) -> None:
    # Cross-site HTML forms cannot set this header. The app allows no CORS origins.
    if request.method not in {"GET", "HEAD", "OPTIONS"} and marker != "1":
        raise HTTPException(
            status_code=403, detail="Запрос требует заголовок X-LifeFlow-Request"
        )
