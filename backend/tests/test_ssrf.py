"""SSRF guards for server-side ICS fetching (review backlog #1)."""
import socket

import httpx
import pytest

from app.core.url_safety import assert_public_http_url
from app.integrations.ical_feed import fetch_and_parse

PUBLIC_IP = "93.184.216.34"

VALID_ICS = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//OpenFamHub test//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:abc\r\n"
    "DTSTART:20261007T130000Z\r\n"
    "DTEND:20261007T150000Z\r\n"
    "SUMMARY:Field trip\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
).encode()


def _fake_getaddrinfo(*ips):
    def fake(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))
            for ip in ips
        ]
    return fake


class TestAssertPublicHttpUrl:
    def test_rejects_non_http_schemes(self):
        for url in ("ftp://example.com/cal.ics", "file:///etc/passwd", "//example.com/cal.ics"):
            with pytest.raises(ValueError):
                assert_public_http_url(url)

    def test_rejects_url_without_a_host(self):
        with pytest.raises(ValueError):
            assert_public_http_url("http:///cal.ics")

    def test_rejects_ipv4_loopback_and_localhost(self):
        for url in ("http://127.0.0.1/cal.ics", "http://localhost/cal.ics", "http://127.1.2.3/"):
            with pytest.raises(ValueError):
                assert_public_http_url(url)

    def test_rejects_private_ranges(self):
        for ip in ("10.0.0.5", "172.16.3.4", "192.168.1.10", "100.64.0.1"):
            with pytest.raises(ValueError):
                assert_public_http_url(f"http://{ip}/cal.ics")

    def test_rejects_link_local_and_metadata(self):
        with pytest.raises(ValueError):
            assert_public_http_url("http://169.254.169.254/latest/meta-data")

    def test_rejects_multicast_and_unspecified(self):
        for ip in ("224.0.0.1", "0.0.0.0", "240.0.0.1"):
            with pytest.raises(ValueError):
                assert_public_http_url(f"http://{ip}/cal.ics")

    def test_rejects_ipv6_loopback_private_and_link_local(self):
        for host in ("[::1]", "[fd00::1]", "[fe80::1]"):
            with pytest.raises(ValueError):
                assert_public_http_url(f"http://{host}/cal.ics")

    def test_rejects_ipv4_mapped_ipv6_loopback(self):
        with pytest.raises(ValueError):
            assert_public_http_url("http://[::ffff:127.0.0.1]/cal.ics")

    def test_rejects_hostname_resolving_to_private(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("192.168.1.5"))
        with pytest.raises(ValueError):
            assert_public_http_url("http://calendar.example.com/cal.ics")

    def test_rejects_hostname_with_mixed_public_and_private(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(PUBLIC_IP, "10.0.0.1"))
        with pytest.raises(ValueError):
            assert_public_http_url("http://calendar.example.com/cal.ics")

    def test_allows_public_ip(self):
        assert_public_http_url(f"http://{PUBLIC_IP}/cal.ics")

    def test_allows_hostname_resolving_to_public(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(PUBLIC_IP))
        assert_public_http_url("https://calendar.example.com/cal.ics")


class TestFetchAndParse:
    async def test_blocks_private_url_before_connecting(self):
        with pytest.raises(ValueError):
            await fetch_and_parse("http://127.0.0.1/cal.ics")

    async def test_follows_redirects_to_public_hosts(self):
        def handler(request):
            if request.url.path == "/real.ics":
                return httpx.Response(200, content=VALID_ICS)
            return httpx.Response(302, headers={"location": f"http://{PUBLIC_IP}/real.ics"})

        events = await fetch_and_parse(
            f"http://{PUBLIC_IP}/start.ics", transport=httpx.MockTransport(handler)
        )
        assert [e["external_uid"] for e in events] == ["abc"]

    async def test_resolves_relative_redirects(self):
        def handler(request):
            if request.url.path == "/real.ics":
                return httpx.Response(200, content=VALID_ICS)
            return httpx.Response(302, headers={"location": "/real.ics"})

        events = await fetch_and_parse(
            f"http://{PUBLIC_IP}/start.ics", transport=httpx.MockTransport(handler)
        )
        assert len(events) == 1

    async def test_blocks_redirect_to_private_host(self):
        def handler(request):
            return httpx.Response(
                302, headers={"location": "http://169.254.169.254/latest/meta-data"}
            )

        with pytest.raises(ValueError):
            await fetch_and_parse(
                f"http://{PUBLIC_IP}/start.ics", transport=httpx.MockTransport(handler)
            )

    async def test_stops_after_too_many_redirects(self):
        def handler(request):
            return httpx.Response(302, headers={"location": f"http://{PUBLIC_IP}/loop.ics"})

        with pytest.raises(ValueError):
            await fetch_and_parse(
                f"http://{PUBLIC_IP}/start.ics", transport=httpx.MockTransport(handler)
            )

    async def test_reports_non_200(self):
        def handler(request):
            return httpx.Response(404)

        with pytest.raises(ValueError):
            await fetch_and_parse(
                f"http://{PUBLIC_IP}/missing.ics", transport=httpx.MockTransport(handler)
            )


class TestDnsRebinding:
    """The connection must go to the address the guard approved."""

    async def test_connects_to_the_validated_address_not_a_second_lookup(self, monkeypatch):
        calls = []

        def rebinding_getaddrinfo(host, port, *args, **kwargs):
            # First answer public (what the guard checks); any later lookup
            # answers loopback, as a rebinding attacker's DNS would.
            calls.append(host)
            ip = PUBLIC_IP if len(calls) == 1 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]

        monkeypatch.setattr(socket, "getaddrinfo", rebinding_getaddrinfo)
        seen = []

        def handler(request):
            seen.append((request.url.host, request.headers["host"]))
            return httpx.Response(200, content=VALID_ICS)

        events = await fetch_and_parse(
            "http://calendar.example.com/cal.ics", transport=httpx.MockTransport(handler)
        )
        assert [e["external_uid"] for e in events] == ["abc"]
        # Pinned to the approved IP, original name kept for virtual hosting.
        assert seen == [(PUBLIC_IP, "calendar.example.com")]
        assert calls == ["calendar.example.com"]  # resolved exactly once

    async def test_https_keeps_the_name_for_tls(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo(PUBLIC_IP))
        seen = []

        def handler(request):
            seen.append((request.url.scheme, request.url.host, request.extensions.get("sni_hostname")))
            return httpx.Response(200, content=VALID_ICS)

        await fetch_and_parse(
            "https://calendar.example.com/cal.ics", transport=httpx.MockTransport(handler)
        )
        assert seen == [("https", PUBLIC_IP, "calendar.example.com")]

    async def test_each_redirect_hop_is_pinned(self, monkeypatch):
        other_public = "93.184.216.35"
        table = {"a.example.com": PUBLIC_IP, "b.example.com": other_public}
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda host, port, *a, **k: [
                (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (table[host], port))
            ],
        )
        seen = []

        def handler(request):
            seen.append((request.url.host, request.headers["host"]))
            if request.headers["host"] == "a.example.com":
                return httpx.Response(302, headers={"location": "http://b.example.com/real.ics"})
            return httpx.Response(200, content=VALID_ICS)

        await fetch_and_parse("http://a.example.com/start.ics", transport=httpx.MockTransport(handler))
        assert seen == [(PUBLIC_IP, "a.example.com"), (other_public, "b.example.com")]


class TestResponseLimits:
    async def test_rejects_oversized_feeds(self, monkeypatch):
        monkeypatch.setattr("app.integrations.ical_feed.MAX_ICS_BYTES", 100)

        def handler(request):
            return httpx.Response(200, content=b"X" * 500)

        with pytest.raises(ValueError, match="larger than"):
            await fetch_and_parse(f"http://{PUBLIC_IP}/big.ics", transport=httpx.MockTransport(handler))
