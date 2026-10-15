"""Phase 11: sending one notification to a person by every channel they set up.

- **Web Push** to each device they turned on (services/push.py).
- **ntfy**: a message to their own topic on the server in `NTFY_URL`
  (with `NTFY_TOKEN` if the server needs one). Off when `NTFY_URL` is empty.
- **Email** to their own address through the SMTP account in `SMTP_*`.
  Off when `SMTP_HOST` or `SMTP_FROM` is empty.

The ntfy server and SMTP account are the server's (environment, like
SECRET_KEY), so their passwords never live in the database or the UI; each
person only picks a topic or an address (Preferences.notifications).
"""
import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.users import NotificationPrefs, Preferences
from app.services import push as push_svc

log = logging.getLogger(__name__)

TIMEOUT = 15  # seconds, per send


def notification_prefs(user: User) -> NotificationPrefs:
    try:
        return Preferences(**((user.settings_json or {}).get("prefs") or {})).notifications
    except ValueError:
        return NotificationPrefs()


def ntfy_server() -> Optional[str]:
    return (settings.ntfy_url or "").strip().rstrip("/") or None


def email_ready() -> bool:
    return bool((settings.smtp_host or "").strip() and (settings.smtp_from or "").strip())


def app_link(path: str) -> Optional[str]:
    """An absolute link into the app: the first https origin in ALLOWED_ORIGINS."""
    for origin in (settings.allowed_origins or "").split(","):
        origin = origin.strip().rstrip("/")
        if origin.startswith("https://"):
            return origin + (path if path.startswith("/") else "/")
    return None


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def _transport() -> Optional[httpx.AsyncBaseTransport]:
    return None  # tests swap in a fake ntfy server


async def send_ntfy(topic: str, payload: dict) -> bool:
    server = ntfy_server()
    if not server:
        return False
    message = {"topic": topic, "title": _one_line(payload.get("title", "OpenFamHub")),
               "message": payload.get("body") or payload.get("title") or "OpenFamHub"}
    link = app_link(payload.get("url") or "/")
    if link:
        message["click"] = link
    headers = {"Authorization": f"Bearer {settings.ntfy_token}"} if settings.ntfy_token else {}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=_transport()) as client:
            res = await client.post(server + "/", json=message, headers=headers)
    except httpx.HTTPError as exc:
        log.warning("ntfy: %s", type(exc).__name__)
        return False
    if res.status_code >= 300:
        log.warning("ntfy: HTTP %s", res.status_code)
        return False
    return True


def _deliver_email(msg: EmailMessage) -> None:
    """Blocking SMTP send; run in a thread. SMTP_SECURITY: starttls, ssl or none."""
    host, port, security = settings.smtp_host, settings.smtp_port, settings.smtp_security
    context = ssl.create_default_context()
    if security == "ssl":
        server = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=TIMEOUT)
    with server:
        if security == "starttls":
            server.starttls(context=context)
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)


async def send_email(to: str, payload: dict) -> bool:
    if not email_ready():
        return False
    text = payload.get("body") or ""
    link = app_link(payload.get("url") or "/")
    if link:
        text += f"\n\nOpen OpenFamHub: {link}"
    text += "\n\nYou can change which reminders you get in My settings › Notifications."
    try:
        msg = EmailMessage()
        msg["Subject"] = _one_line(payload.get("title", "OpenFamHub"))
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg.set_content(text.strip())
        await asyncio.to_thread(_deliver_email, msg)
    except (OSError, ValueError, smtplib.SMTPException) as exc:
        log.warning("email: %s", type(exc).__name__)
        return False
    return True


def reachable_without_device(user: User) -> bool:
    prefs = notification_prefs(user)
    return bool((prefs.ntfy_topic and ntfy_server()) or (prefs.email_to and email_ready()))


async def deliver(db: AsyncSession, user: User, payload: dict) -> int:
    """Send to every channel the person set up; how many accepted it."""
    prefs = notification_prefs(user)
    sent = 0
    if await push_svc.has_device(db, user.id):
        sent += await push_svc.send_to_users(db, [user.id], payload)
    if prefs.ntfy_topic and ntfy_server():
        sent += await send_ntfy(prefs.ntfy_topic, payload)
    if prefs.email_to and email_ready():
        sent += await send_email(prefs.email_to, payload)
    return sent
