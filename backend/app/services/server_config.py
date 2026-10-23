"""Server settings an admin can change in the app (Admin › Settings).

`get(name)` is what the rest of the code reads:
   1. except for Home Assistant, a value from the environment / `.env` wins: a non-empty string, or a
   number or choice different from its default. The field is then "locked"
   in the app;
   2. Home Assistant values are written to `.env` by an unlocked admin;
   3. otherwise the value saved in the app (`server_settings`, loaded into
   memory at startup and after each save);
   4. otherwise the default.

Database secrets (tokens, the email password) are stored encrypted with a key
derived from SECRET_KEY. Home Assistant's token stays in `.env`. Secrets are
never returned by the API or logged.
"""
import base64
import json
import ipaddress
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import _PROJECT_ROOT, settings
from app.models.server_setting import ServerSetting

log = logging.getLogger(__name__)


def _web_url(v: Any) -> str:
    v = str(v).strip()
    if v and (not re.match(r"^https?://[^\s/]+", v, re.I) or len(v) > 2048):
        raise ValueError("use an http:// or https:// address")
    return v.rstrip("/")


def _local_web_url(v: Any) -> str:
    """Ollama must stay on the LAN; accept a private IP or mDNS hostname."""
    url = _web_url(v)
    if not url:
        return url
    host = urlparse(url).hostname or ""
    try:
        if not ipaddress.ip_address(host).is_private:
            raise ValueError("use a private LAN address or .local hostname")
    except ValueError:
        if not host.lower().endswith(".local"):
            raise ValueError("use a private LAN address or .local hostname")
    return url


def _relay_url(v: Any) -> str:
    """A Worker HTTPS origin, never credentials, query parameters or a path."""
    value = str(v).strip()
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        valid = (parsed.scheme == "https" and parsed.hostname and parsed.port != 0
                 and not parsed.username and not parsed.password
                 and parsed.path in ("", "/") and not parsed.params
                 and not parsed.query and not parsed.fragment
                 and not re.search(r"[\x00-\x20\x7f\\?#@]", value) and len(value) <= 2048)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("use an https:// origin without credentials, a path, query or fragment")
    # Match URL.origin in the Worker (case-folded host, no default HTTPS port).
    try:
        host = parsed.hostname.lower()
        if ":" in host:
            host = "[" + ipaddress.IPv6Address(host).compressed + "]"
        else:
            host = host.encode("idna").decode("ascii")
    except ValueError:
        raise ValueError("use a valid HTTPS hostname") from None
    port = f":{parsed.port}" if parsed.port not in (None, 443) else ""
    return "https://" + host + port


def _relay_token(v: Any) -> str:
    value = str(v).strip()
    if value and (len(value) > 4096 or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", value)):
        raise ValueError("use a bearer token, up to 4096 characters")
    return value


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
    "ollama_url": Field(_local_web_url),
    "ollama_model": Field(_text(256)),
    "calendar_relay_url": Field(_relay_url, secret=True),
    "calendar_relay_token": Field(_relay_token, secret=True),
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
HA_FIELDS = {"ha_url", "ha_token"}
ENV_FILE = _PROJECT_ROOT / ".env"

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
    if name in HA_FIELDS:
        return False
    return _env_value(name) is not None


def get(name: str) -> Any:
    if name in HA_FIELDS:
        return getattr(settings, name)
    env = _env_value(name)
    if env is not None:
        return env
    if name in _stored:
        return _stored[name]
    return _default(name)


def save_home_assistant_to_env(changes: dict[str, Any]) -> None:
    """Persist Home Assistant connection settings in .env and use them now."""
    values = {name: changes[name] for name in HA_FIELDS & changes.keys()}
    if not values:
        return
    existing = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = existing.splitlines(keepends=True)
    replaced: set[str] = set()
    rendered: list[str] = []
    for line in lines:
        for name, value in values.items():
            env_name = name.upper()
            if re.match(rf"^\s*(?:export\s+)?{re.escape(env_name)}\s*=", line):
                rendered.append(f"{env_name}={value}\n")
                replaced.add(name)
                break
        else:
            rendered.append(line)
    if rendered and not rendered[-1].endswith(("\n", "\r")):
        rendered[-1] += "\n"
    for name, value in values.items():
        if name not in replaced:
            rendered.append(f"{name.upper()}={value}\n")
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    mode = ENV_FILE.stat().st_mode if ENV_FILE.exists() else 0o600
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=ENV_FILE.parent, delete=False) as tmp:
        tmp.writelines(rendered)
        tmp_path = Path(tmp.name)
    os.chmod(tmp_path, mode)
    os.replace(tmp_path, ENV_FILE)
    for name, value in values.items():
        setattr(settings, name, value)


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
