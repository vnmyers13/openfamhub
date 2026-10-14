"""Fetch a user-supplied URL without letting it reach the server's own network.

- Every hop (the URL and each redirect target) is validated by the SSRF guard
  before connecting; redirects are followed here, not by httpx.
- The connection goes to the address the guard approved (the URL's host is
  replaced by that IP, with the original name kept in the Host header and,
  for https, as the TLS SNI/certificate name). httpx never re-resolves the
  name, which closes the DNS-rebinding window between check and connect.
- The body is capped at `max_bytes`, and the whole fetch at `timeout` seconds.

Used for calendar feeds, recipe pages and event pages.
"""
import httpx

from app.core.url_safety import resolve_public_addresses

MAX_REDIRECTS = 5


async def fetch_public(
    url: str,
    *,
    max_bytes: int,
    fetch_label: str = "Fetch",
    size_label: str = "Response",
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bytes:
    target = url
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        for _ in range(MAX_REDIRECTS + 1):
            addresses = resolve_public_addresses(target)
            original = httpx.URL(target)
            ip = addresses[0]
            pinned = original.copy_with(host=f"[{ip}]" if ip.version == 6 else str(ip))
            request_headers = {**(headers or {}), "Host": original.netloc.decode("ascii")}
            extensions = {"sni_hostname": original.host} if original.scheme == "https" else {}

            async with client.stream(
                "GET", pinned, headers=request_headers, extensions=extensions, follow_redirects=False
            ) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise ValueError(f"{fetch_label} returned a redirect without a Location header")
                    target = str(original.join(location))
                    continue
                if resp.status_code != 200:
                    raise ValueError(f"{fetch_label} returned HTTP {resp.status_code}")
                chunks, size = [], 0
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(f"{size_label} is larger than {max_bytes // 1_000_000 or 1} MB")
                    chunks.append(chunk)
                return b"".join(chunks)
    raise ValueError(f"{fetch_label} exceeded {MAX_REDIRECTS} redirects")
