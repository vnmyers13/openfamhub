"""Reject server-side requests to non-public addresses (SSRF guard).

Any code that fetches a user-supplied URL must call
:func:`assert_public_http_url` before connecting, and again for each
redirect target.
"""
import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Address blocks Python's ``is_private`` doesn't cover but that must never be
# reachable from a server-side fetch (carrier-grade NAT).
_EXTRA_BLOCKED_NETWORKS = (ipaddress.ip_network("100.64.0.0/10"),)

BLOCKED_MESSAGE = "Blocked non-public address for host"


def _is_blocked(addr) -> bool:
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def assert_public_http_url(url: str) -> None:
    """Raise ``ValueError`` unless *url* is http(s) and every resolved IP is public."""
    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError(f"Unsupported URL scheme: {parts.scheme or '(none)'}")

    host = parts.hostname
    if not host:
        raise ValueError("URL has no host")

    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parts.port or 80, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError(f"Could not resolve host: {host}") from exc
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]

    for addr in addresses:
        mapped = getattr(addr, "ipv4_mapped", None)
        if mapped is not None:
            addr = mapped
        if _is_blocked(addr) or any(addr in net for net in _EXTRA_BLOCKED_NETWORKS):
            raise ValueError(f"{BLOCKED_MESSAGE}: {host}")
