"""Outbound-only Worker protocol; no caller-selected destinations or raw errors.

The operator configures a trusted HTTPS origin. Subscription URLs returned by
that origin are validated but never fetched. Neither redirects nor environment
proxies can move an authenticated management request to another destination.
"""
import json
import logging
import re
from contextlib import aclosing
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

import httpx

from app.services import server_config as cfg

TIMEOUT = httpx.Timeout(connect=5, read=15, write=15, pool=5)
MAX_RESPONSE_BYTES = 16 * 1024
MAX_ICS_BYTES = 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_quiet = ContextVar("calendar_relay_quiet", default=False)


class _PrivateRequest(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not _quiet.get()


# httpx logs complete request URLs at INFO; httpcore DEBUG also includes hosts
# and headers. Suppress only this task's relay I/O, not concurrent integrations.
for _logger in ("httpx", "httpcore.connection", "httpcore.http11", "httpcore.http2", "httpcore.proxy", "httpcore.socks"):
    logging.getLogger(_logger).addFilter(_PrivateRequest())


@dataclass(frozen=True, repr=False)
class RelayFeed:
    relay_id: str
    subscription_url: str


class RelayUnavailable(Exception):
    """A safe message for the operator; never contains provider data."""


def _configuration() -> tuple[str, str]:
    try:
        values = cfg.validate({name: cfg.get(name) for name in ("calendar_relay_url", "calendar_relay_token")})
        base, token = values["calendar_relay_url"], values["calendar_relay_token"]
        if base and token:
            return base, token
    except ValueError:
        pass
    raise RelayUnavailable("calendar relay is not configured with a valid HTTPS address and token") from None


def configured() -> bool:
    try:
        _configuration()
        return True
    except RelayUnavailable:
        return False


def _transport() -> httpx.AsyncBaseTransport | None:
    return None  # tests substitute a local provider


def _document(ics: bytes) -> str:
    try:
        if not isinstance(ics, bytes) or len(ics) > MAX_ICS_BYTES:
            raise ValueError
        return ics.decode("utf-8")
    except (ValueError, UnicodeError):
        raise RelayUnavailable("calendar relay requires a UTF-8 document of at most 1 MiB") from None


def _feed_path(relay_id: str) -> str:
    if not isinstance(relay_id, str) or not _ID.fullmatch(relay_id):
        raise RelayUnavailable("calendar relay feed identifier is invalid") from None
    return "/v1/feeds/" + relay_id


async def _request(method: str, path: str, body: dict | None = None) -> tuple[bytes, str]:
    base, token = _configuration()
    quiet_token = _quiet.set(True)
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=_transport(), follow_redirects=False, trust_env=False) as client:
            async with client.stream(method, base + path, headers={
                "Authorization": "Bearer " + token, "Accept-Encoding": "identity",
            }, **({"json": body} if body is not None else {})) as response:
                if response.status_code in (401, 403):
                    raise RelayUnavailable("calendar relay refused the access token")
                expected = 201 if method == "POST" else 204
                if response.status_code != expected:
                    raise RelayUnavailable("calendar relay returned an unexpected response")
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise RelayUnavailable("calendar relay returned an unexpected response")
                content = bytearray()
                async with aclosing(response.aiter_raw()) as chunks:
                    async for chunk in chunks:
                        if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise RelayUnavailable("calendar relay response was too large")
                        content.extend(chunk)
                return bytes(content), base
    except httpx.TimeoutException:
        raise RelayUnavailable("calendar relay timed out") from None
    except (httpx.HTTPError, httpx.InvalidURL, httpx.StreamError, ValueError):
        raise RelayUnavailable("calendar relay is unavailable") from None
    finally:
        _quiet.reset(quiet_token)


async def create_feed(kind: Literal["titles", "full"], ics: bytes) -> RelayFeed:
    if kind not in ("titles", "full"):
        raise RelayUnavailable("calendar relay feed kind is invalid")
    raw, base = await _request("POST", "/v1/feeds", {"kind": kind, "ics": _document(ics)})
    try:
        data = json.loads(raw)
        relay_id, url = data["relay_id"], data["subscription_url"]
        if not isinstance(relay_id, str) or not _ID.fullmatch(relay_id) or not isinstance(url, str):
            raise ValueError
        parsed, origin = urlparse(url), urlparse(base)
        if (parsed.scheme != "https" or parsed.netloc != origin.netloc
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or not re.fullmatch(r"/c/[A-Za-z0-9_-]{32,256}\.ics", parsed.path)
                or url != base + parsed.path):
            raise ValueError
        return RelayFeed(relay_id, url)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise RelayUnavailable("calendar relay returned an invalid feed") from None


async def replace_feed(relay_id: str, ics: bytes) -> None:
    await _request("PUT", _feed_path(relay_id), {"ics": _document(ics)})


async def revoke_feed(relay_id: str) -> None:
    await _request("DELETE", _feed_path(relay_id))
