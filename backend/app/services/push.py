"""Web Push sending (Phase 11), RFC 8291 + RFC 8292.

- Keys: the install's VAPID key pair is made on first use and kept in
  `push_keys`; browsers subscribe with its public half.
- Payloads are encrypted for each device with `http_ece` (aes128gcm) and
  signed with a VAPID JWT (`py_vapid`), then POSTed with httpx.
- The endpoint URL comes from a browser, so it's treated like any
  user-supplied URL: https only, its host must resolve to public addresses
  (`resolve_public_addresses`), and the connection is pinned to the checked
  address (no DNS rebinding). An endpoint that fails the check is dropped.
- 404/410 from the push service mean the device unsubscribed: drop it.
  Other failures (5xx, timeouts) keep it for the next try.
"""
import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlsplit

import http_ece
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid02
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.url_safety import resolve_public_addresses
from app.models.push import PushKeys, PushSubscription

log = logging.getLogger(__name__)

TTL_SECONDS = 4 * 3600  # a reminder older than this isn't worth delivering
TIMEOUT_SECONDS = 15


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _transport() -> httpx.AsyncBaseTransport | None:
    """Tests swap in a fake push service."""
    return None


async def vapid_keys(db: AsyncSession) -> PushKeys:
    keys = await db.get(PushKeys, 1)
    if keys is None:
        vapid = Vapid02()
        vapid.generate_keys()
        public = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        keys = PushKeys(id=1, private_pem=vapid.private_pem().decode(), public_key=_b64u(public))
        db.add(keys)
        await db.flush()
    return keys


def _subject() -> str:
    origin = (settings.allowed_origins or "").split(",")[0].strip()
    return origin if origin.startswith("https://") else "mailto:openfamhub@localhost"


def _encrypt(sub: PushSubscription, payload: dict) -> bytes:
    sender = ec.generate_private_key(ec.SECP256R1())  # a fresh key per message (RFC 8291)
    return http_ece.encrypt(json.dumps(payload).encode(), private_key=sender, dh=_unb64u(sub.p256dh),
                            auth_secret=_unb64u(sub.auth), version="aes128gcm")


async def _send_one(client: httpx.AsyncClient, keys: PushKeys, sub: PushSubscription, payload: dict) -> str:
    """'sent', 'gone' (drop the subscription) or 'failed' (keep it)."""
    try:
        parts = urlsplit(sub.endpoint)
        if parts.scheme != "https" or not parts.hostname:
            return "gone"
        ip = resolve_public_addresses(sub.endpoint)[0]
    except Exception:  # noqa: BLE001  - a private, unresolvable or malformed endpoint is never contacted
        log.warning("push: refusing endpoint on %s", urlsplit(sub.endpoint).hostname)
        return "gone"
    try:
        body = _encrypt(sub, payload)
    except Exception:  # noqa: BLE001  - bad keys from the browser
        return "gone"
    vapid = Vapid02.from_pem(keys.private_pem.encode())
    audience = f"{parts.scheme}://{parts.netloc}"
    auth = vapid.sign({"sub": _subject(), "aud": audience, "exp": int(time.time()) + 12 * 3600})["Authorization"]
    original = httpx.URL(sub.endpoint)
    pinned = original.copy_with(host=f"[{ip}]" if ip.version == 6 else str(ip))
    headers = {"Host": original.netloc.decode("ascii"), "Authorization": auth, "Content-Encoding": "aes128gcm",
               "Content-Type": "application/octet-stream", "TTL": str(TTL_SECONDS), "Urgency": "normal"}
    try:
        resp = await client.post(pinned, content=body, headers=headers, extensions={"sni_hostname": original.host})
    except httpx.HTTPError:
        return "failed"
    if resp.status_code in (404, 410):
        return "gone"
    if 200 <= resp.status_code < 300:
        return "sent"
    log.warning("push: service answered %s", resp.status_code)
    return "failed"


async def send_to_users(db: AsyncSession, user_ids: Iterable[str], payload: dict) -> int:
    """Send `payload` ({title, body, url?, tag?}) to every device of these people.
    Returns how many devices accepted it."""
    ids = list(set(user_ids))
    if not ids:
        return 0
    subs = (await db.execute(select(PushSubscription).where(PushSubscription.user_id.in_(ids)))).scalars().all()
    if not subs:
        return 0
    keys = await vapid_keys(db)
    sent = 0
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=_transport()) as client:
        for sub in subs:
            outcome = await _send_one(client, keys, sub, payload)
            if outcome == "sent":
                sent += 1
                sub.last_success_at = datetime.now(timezone.utc)
            elif outcome == "gone":
                await db.delete(sub)
    await db.flush()
    return sent


async def has_device(db: AsyncSession, user_id: str) -> bool:
    return (await db.execute(select(PushSubscription.id).where(PushSubscription.user_id == user_id).limit(1))).first() is not None
