"""The isolated relay client never follows provider-controlled destinations."""
import json
import logging

import httpx
import pytest

from app.core.config import settings
from app.integrations import calendar_relay as relay

ICS = b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
FEED = {"relay_id": "feed-1", "subscription_url": "https://relay.example/c/" + "a" * 64 + ".ics"}


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    monkeypatch.setattr(settings, "calendar_relay_url", "https://relay.example")
    monkeypatch.setattr(settings, "calendar_relay_token", "private-management-token")


def transport(monkeypatch, handler):
    def streaming(request):
        response = handler(request)
        if response.is_stream_consumed:
            return httpx.Response(response.status_code, headers=response.headers,
                                  stream=httpx.ByteStream(response.content))
        return response
    monkeypatch.setattr(relay, "_transport", lambda: httpx.MockTransport(streaming))


async def test_create_replace_revoke_use_only_the_configured_endpoint(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer private-management-token"
        assert all(0 < request.extensions["timeout"][part] <= 20 for part in ("connect", "read", "write", "pool"))
        if request.method == "POST":
            return httpx.Response(201, json=FEED)
        return httpx.Response(204)

    transport(monkeypatch, handler)
    assert relay.configured()
    feed = await relay.create_feed("titles", ICS)
    assert (feed.relay_id, feed.subscription_url) == ("feed-1", FEED["subscription_url"])
    await relay.replace_feed(feed.relay_id, ICS)
    await relay.revoke_feed(feed.relay_id)
    assert [(r.method, str(r.url)) for r in requests] == [
        ("POST", "https://relay.example/v1/feeds"),
        ("PUT", "https://relay.example/v1/feeds/feed-1"),
        ("DELETE", "https://relay.example/v1/feeds/feed-1"),
    ]
    assert json.loads(requests[0].content) == {"kind": "titles", "ics": ICS.decode()}
    assert json.loads(requests[1].content) == {"ics": ICS.decode()}
    assert requests[2].content == b""
    assert "relay.example" not in caplog.text
    assert "private-management-token" not in caplog.text
    assert "BEGIN:VCALENDAR" not in caplog.text


@pytest.mark.parametrize("error,message", [
    (httpx.ReadTimeout("https://private/token BEGIN:VCALENDAR"), "calendar relay timed out"),
    (httpx.ConnectError("https://private/token BEGIN:VCALENDAR"), "calendar relay is unavailable"),
    (httpx.RemoteProtocolError("private"), "calendar relay is unavailable"),
    (httpx.InvalidURL("private"), "calendar relay is unavailable"),
    (httpx.StreamClosed(), "calendar relay is unavailable"),
])
async def test_transport_errors_are_normalized_without_sensitive_context(monkeypatch, error, message):
    def handler(request):
        raise error
    transport(monkeypatch, handler)
    with pytest.raises(relay.RelayUnavailable, match=message) as exc:
        await relay.create_feed("titles", ICS)
    assert exc.value.__cause__ is None
    assert exc.value.__suppress_context__
    assert "private" not in str(exc.value)


@pytest.mark.parametrize("status", [301, 302, 307, 308, 400, 401, 403, 404, 429, 500, 503])
async def test_provider_errors_and_redirects_never_follow_or_echo_the_provider(monkeypatch, status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "https://attacker.example/stolen"}, text="secret provider body")
    transport(monkeypatch, handler)
    for operation in (relay.create_feed("full", ICS), relay.replace_feed("feed-1", ICS), relay.revoke_feed("feed-1")):
        with pytest.raises(relay.RelayUnavailable) as exc:
            await operation
        assert "secret" not in str(exc.value) and "attacker" not in str(exc.value)
    assert len(calls) == 3


@pytest.mark.parametrize("body", [
    b"not json", b"null", b"[]", b"{}",
    json.dumps({**FEED, "relay_id": "../../evil"}).encode(),
    json.dumps({**FEED, "subscription_url": "http://relay.example/c/" + "a" * 64 + ".ics"}).encode(),
    json.dumps({**FEED, "subscription_url": "https://attacker.example/c/" + "a" * 64 + ".ics"}).encode(),
    json.dumps({**FEED, "subscription_url": FEED["subscription_url"] + "?secret=x"}).encode(),
    json.dumps({**FEED, "subscription_url": "https://user:pass@relay.example/c/" + "a" * 64 + ".ics"}).encode(),
    pytest.param(b"x" * 16385, id="oversized-response"),
    pytest.param(b"[" * 2000 + b"]" * 2000, id="deeply-nested-json"),
])
async def test_invalid_create_responses_are_rejected(monkeypatch, body):
    transport(monkeypatch, lambda r: httpx.Response(201, content=body))
    with pytest.raises(relay.RelayUnavailable):
        await relay.create_feed("titles", ICS)


async def test_response_is_bounded_while_streaming(monkeypatch):
    class Endless(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                yield b"x" * 4096
            pytest.fail("client consumed an unbounded response")
    transport(monkeypatch, lambda r: httpx.Response(201, stream=Endless()))
    with pytest.raises(relay.RelayUnavailable):
        await relay.create_feed("titles", ICS)


async def test_compressed_responses_are_rejected_before_decoding(monkeypatch):
    transport(monkeypatch, lambda r: httpx.Response(201, headers={"Content-Encoding": "gzip"}, content=b""))
    with pytest.raises(relay.RelayUnavailable):
        await relay.create_feed("titles", ICS)


@pytest.mark.parametrize("url", ["", "http://relay.example", "https://user:pw@relay.example", "https://relay.example?x=y", "https://relay.example#x", "https://relay.example:bad", "https://relay.example\\evil", "https://relay.example/path"])
async def test_invalid_environment_configuration_never_makes_a_request(monkeypatch, url):
    monkeypatch.setattr(settings, "calendar_relay_url", url)
    transport(monkeypatch, lambda r: pytest.fail("invalid configuration made a request"))
    assert not relay.configured()
    with pytest.raises(relay.RelayUnavailable):
        await relay.create_feed("titles", ICS)


async def test_absent_token_and_invalid_inputs_never_make_a_request(monkeypatch):
    transport(monkeypatch, lambda r: pytest.fail("invalid input made a request"))
    for relay_id in ("../escape", "https://other.example", "", "x?y=z", "x\nsecret"):
        with pytest.raises(relay.RelayUnavailable):
            await relay.revoke_feed(relay_id)
    for kind, ics in (("invalid", ICS), ("titles", b"\xff"), ("titles", b"x" * (1024 * 1024 + 1))):
        with pytest.raises(relay.RelayUnavailable):
            await relay.create_feed(kind, ics)
    monkeypatch.setattr(settings, "calendar_relay_token", "")
    assert not relay.configured()
    with pytest.raises(relay.RelayUnavailable):
        await relay.create_feed("titles", ICS)


@pytest.mark.parametrize("url", ["https://RELAY.EXAMPLE:443/", "https://relay.example/"])
async def test_origin_normalization_accepts_the_workers_canonical_subscription_url(monkeypatch, url):
    monkeypatch.setattr(settings, "calendar_relay_url", url)
    transport(monkeypatch, lambda r: httpx.Response(201, json=FEED))
    feed = await relay.create_feed("titles", ICS)
    assert feed.subscription_url == FEED["subscription_url"]
