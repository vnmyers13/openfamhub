"""Server settings an admin can change in the app (Admin › Settings), with
`.env` still in charge where it says something.

`get(name)` is what the rest of the code reads:
  1. a value from the environment / `.env` wins: a non-empty string, or a
     number or choice different from its default. The field is then "locked"
     in the app;
  2. otherwise the value saved in the app (`server_settings`, loaded into
     memory at startup and after each save);
  3. otherwise the default.

Secrets (tokens, the email password) are stored encrypted with a key derived
from SECRET_KEY, never returned by the API, and never logged. If SECRET_KEY
changes they can't be read any more and have to be entered again.
"""
import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.server_setting import ServerSetting

log = logging.getLogger(__name__)


def _web_url(v: Any) -> str:
    v = str(v).strip()
    if v and (not re.match(r"^https?://[^\s/]+", v, re.I) or len(v) > 2048):
        raise ValueError("use an http:// or https:// address")
    return v.rstrip("/")


def _text(limit: int, spaces: bool = False) -> Callable[[Any], str]:
    def check(v: Any) -> str:
        v = str(v).strip()
        if len(v) > limit or (not spaces and re.search(r"\s", v)):
            raise ValueError(f"up to {limit} characters" + ("" if spaces else ", no spaces"))
        return v
    return check


def _int(low: int, high: int) -> Callable[[Any], int]:
    def check(v: Any) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or not low <= v <= high:
            raise ValueError(f"a whole number from {low} to {high}")
        return v
    return check


def _choice(*options: str) -> Callable[[Any], str]:
    def check(v: Any) -> str:
        if v not in options:
            raise ValueError("one of " + ", ".join(options))
        return v
    return check


def _hhmm(v: Any) -> str:
    if not isinstance(v, str) or not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", v):
        raise ValueError("a time as HH:MM, 24-hour")
    return v


@dataclass(frozen=True)
class Field:
    check: Callable[[Any], Any]
    secret: bool = False


FIELDS: dict[str, Field] = {
    "ha_url": Field(_web_url),
    "ha_token": Field(_text(4096), secret=True),
    "ntfy_url": Field(_web_url),
    "ntfy_token": Field(_text(1024), secret=True),
    "smtp_host": Field(_text(253)),
    "smtp_port": Field(_int(1, 65535)),
    "smtp_security": Field(_choice("starttls", "ssl", "none")),
    "smtp_username": Field(_text(254)),
    "smtp_password": Field(_text(1024, spaces=True), secret=True),
    "smtp_from": Field(_text(254, spaces=True)),
    "backup_time": Field(_hhmm),
    "backup_retention_days": Field(_int(1, 3650)),
    "wall_idle_timeout_seconds": Field(_int(30, 86400)),
}

_stored: dict[str, Any] = {}  # what the app saved, secrets decrypted
_unreadable: set[str] = set()  # secrets that wouldn't decrypt (SECRET_KEY changed)


def _default(name: str) -> Any:
    return type(settings).model_fields[name].default


def _env_value(name: str) -> Any:
    """The environment's value when it says something, else None."""
    value = getattr(settings, name)
    if value == _default(name):
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def locked(name: str) -> bool:
    return _env_value(name) is not None


def get(name: str) -> Any:
    env = _env_value(name)
    if env is not None:
        return env
    if name in _stored:
        return _stored[name]
    return _default(name)


def _fernet() -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=b"openfamhub server settings").derive(settings.secret_key.encode())
    return Fernet(base64.urlsafe_b64encode(key))


async def load(db: AsyncSession) -> None:
    """Read what the app saved (startup, and after each save)."""
    rows = (await db.execute(select(ServerSetting))).scalars().all()
    fresh: dict[str, Any] = {}
    unreadable: set[str] = set()
    fernet = _fernet()
    for row in rows:
        if row.key not in FIELDS:
            continue
        try:
            raw = fernet.decrypt(row.value.encode()).decode() if row.secret else row.value
            fresh[row.key] = json.loads(raw)
        except (InvalidToken, ValueError):
            unreadable.add(row.key)
            log.warning("Server setting %s couldn't be read (was SECRET_KEY changed?); enter it again", row.key)
    _stored.clear()
    _stored.update(fresh)
    _unreadable.clear()
    _unreadable.update(unreadable)


def clear() -> None:
    """Forget what was loaded (tests; a restart without a database)."""
    _stored.clear()
    _unreadable.clear()


def validate(changes: dict[str, Any]) -> dict[str, Any]:
    """Check each change; raises ValueError naming the setting."""
    clean = {}
    for name, value in changes.items():
        field = FIELDS.get(name)
        if field is None:
            raise ValueError(f"{name}: not a setting that can be changed here")
        try:
            clean[name] = "" if field.secret and value in ("", None) else field.check(value)
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from None
    return clean


async def save(db: AsyncSession, changes: dict[str, Any]) -> None:
    """Store validated changes. A secret set to "" is removed."""
    fernet = _fernet()
    for name, value in changes.items():
        field = FIELDS[name]
        row = await db.get(ServerSetting, name)
        if field.secret and value == "":
            if row is not None:
                await db.delete(row)
            continue
        raw = json.dumps(value)
        stored = fernet.encrypt(raw.encode()).decode() if field.secret else raw
        if row is None:
            db.add(ServerSetting(key=name, value=stored, secret=field.secret))
        else:
            row.value, row.secret = stored, field.secret
    await db.flush()
    await load(db)


def describe() -> dict[str, dict]:
    """For Admin › Settings: values, but for secrets only whether one is set."""
    out: dict[str, dict] = {}
    for name, field in FIELDS.items():
        if field.secret:
            entry: dict[str, Any] = {"is_set": bool(get(name)), "locked": locked(name)}
            if name in _unreadable and not locked(name):
                entry["unreadable"] = True
        else:
            entry = {"value": get(name), "locked": locked(name)}
        out[name] = entry
    return out
