import hashlib
import uuid
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Response, status
from jose import jwt
from jose.exceptions import JWTError
from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_DAYS = 30
SESSION_MAX_AGE = SESSION_DAYS * 24 * 3600
ELEVATION_MINUTES = 15
PASSWORD_REQUIRED = "password_required"  # 403 detail the frontend turns into a password prompt


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: str, session_id: str, expires_days: int = SESSION_DAYS) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=expires_days)
    payload = {"sub": user_id, "jti": session_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ---- login throttling -------------------------------------------------------

class LoginThrottle:
    """Counts failed sign-ins per key ("pin:<user_id>", "pw:<name>") with an
    escalating lockout: 5 failures -> 1 min, 10 -> 5 min, 15+ -> 15 min.
    In-memory: the API runs a single worker by design."""

    STEPS = [(15, 15 * 60), (10, 5 * 60), (5, 60)]

    def __init__(self) -> None:
        self._failures: dict[str, int] = {}
        self._locked_until: dict[str, float] = {}

    def check(self, key: str) -> None:
        until = self._locked_until.get(key, 0)
        remaining = int(until - time.monotonic())
        if remaining > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {remaining} seconds.",
                headers={"Retry-After": str(remaining)},
            )

    def fail(self, key: str) -> None:
        count = self._failures.get(key, 0) + 1
        self._failures[key] = count
        for threshold, seconds in self.STEPS:
            if count >= threshold and count % 5 == 0:
                self._locked_until[key] = time.monotonic() + seconds
                break

    def succeed(self, key: str) -> None:
        self._failures.pop(key, None)
        self._locked_until.pop(key, None)

    def reset(self) -> None:
        self._failures.clear()
        self._locked_until.clear()


login_throttle = LoginThrottle()


# ---- sessions ---------------------------------------------------------------

async def start_session(
    db: AsyncSession, response: Response, user, auth_method: str, device_hint: Optional[str] = None
):
    """Create a session row and set the login cookie for it."""
    from app.models.auth import Session

    now = datetime.now(timezone.utc)
    # Housekeeping: drop this user's expired sessions.
    await db.execute(delete(Session).where(Session.user_id == user.id, Session.expires_at < now))
    session = Session(
        user_id=user.id,
        auth_method=auth_method,
        device_hint=(device_hint or "")[:128] or None,
        expires_at=now + timedelta(days=SESSION_DAYS),
        token_hash=f"pending-{uuid.uuid4()}",  # replaced once the token exists
    )
    db.add(session)
    await db.flush()
    token = create_access_token(user.id, session.id)
    session.token_hash = _token_hash(token)
    await db.flush()
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=True,
        max_age=SESSION_MAX_AGE,
    )
    return session


async def revoke_sessions(db: AsyncSession, user_id: str, keep_session_id: Optional[str] = None) -> None:
    from app.models.auth import Session

    stmt = delete(Session).where(Session.user_id == user_id)
    if keep_session_id:
        stmt = stmt.where(Session.id != keep_session_id)
    await db.execute(stmt)


def clear_login_cookie(response: Response) -> None:
    response.set_cookie(key="access_token", value="", httponly=True, samesite="strict", secure=True, max_age=0)


@dataclass
class Auth:
    user: object
    session: object

    @property
    def admin_unlocked(self) -> bool:
        if self.session.auth_method == "password":
            return True
        until = self.session.elevated_until
        return until is not None and until > datetime.now(timezone.utc)


async def get_auth(
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> Auth:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(access_token)
    user_id, session_id = payload.get("sub"), payload.get("jti")
    if not user_id or not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    from app.models.auth import Session
    from app.models.user import User

    session = await db.get(Session, session_id)
    if (
        session is None
        or session.user_id != user_id
        or session.token_hash != _token_hash(access_token)
        or session.expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or signed out")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.is_deleted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")
    return Auth(user=user, session=session)


async def get_current_user(auth: Auth = Depends(get_auth)):
    return auth.user


def require_role(*roles: str):
    """Role gate. Admin access additionally needs a password session or a recent
    elevation, so a PIN sign-in on a shared device can't change settings."""

    async def role_dependency(auth: Auth = Depends(get_auth)):
        if auth.user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        if auth.user.role == "admin" and roles == ("admin",) and not auth.admin_unlocked:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PASSWORD_REQUIRED)
        return auth.user

    return role_dependency
