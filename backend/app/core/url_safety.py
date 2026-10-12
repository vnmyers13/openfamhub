"""Reject server-side requests to non-public addresses (SSRF guard).

Any code that fetches a user-supplied URL must validate it before connecting,
and again for each redirect target. To close the DNS-rebinding window, fetchers
should also connect to the address that was validated rather than letting the
HTTP client resolve the name a second time: use :func:`resolve_public_addresses`
and pin the connection (see ``integrations.ical_feed.fetch_ics_bytes``).
"""
import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Address blocks Python's ``is_private`` doesn't cover but that must never be
# reachable from a server-side fetch (carrier-grade NAT).
_EXTRA_BLOCKED_NETWORKS = (ipaddress.ip_network("100.64.0.0/10"),)

BLOCKED_MESSAGE = "Blocked non-public address for host"

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _is_blocked(addr) -> bool:
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def resolve_public_addresses(url: str) -> list[IPAddress]:
    """Resolve *url*'s host once and return its addresses.

    Raises ``ValueError`` unless the scheme is http(s) and **every** resolved
    address is public. Callers that open a connection should connect to one of
    the returned addresses (connect-time pinning), not re-resolve the name.
    """
    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError(f"Unsupported URL scheme: {parts.scheme or '(none)'}")

    host = parts.hostname
    if not host:
        raise ValueError("URL has no host")

    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        default_port = 443 if parts.scheme.lower() == "https" else 80
        try:
            infos = socket.getaddrinfo(host, parts.port or default_port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError(f"Could not resolve host: {host}") from exc
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    if not addresses:
        raise ValueError(f"Could not resolve host: {host}")

    checked: list[IPAddress] = []
    for addr in addresses:
        mapped = getattr(addr, "ipv4_mapped", None)
        if mapped is not None:
            addr = mapped
        if _is_blocked(addr) or any(addr in net for net in _EXTRA_BLOCKED_NETWORKS):
            raise ValueError(f"{BLOCKED_MESSAGE}: {host}")
        checked.append(addr)
    return checked


def assert_public_http_url(url: str) -> None:
    """Raise ``ValueError`` unless *url* is http(s) and every resolved IP is public."""
    resolve_public_addresses(url)
