"""Phase 11: Web Push. Keys made by the server, subscriptions per device, and
the sender (RFC 8291 encryption + RFC 8292 VAPID), checked by decrypting what
we send with the "phone's" own key."""
import base64
import json

import http_ece
import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select

from tests.test_phase2 import SETUP, _cookie, _h, _member


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class Phone:
    """What a browser's PushManager hands the app: an endpoint and its keys."""

    def __init__(self, endpoint="https://push.example.test/send/abc"):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.auth = b"0123456789abcdef"
        self.endpoint = endpoint

    def subscription(self):
        pub = self.key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        return {"endpoint": self.endpoint, "keys": {"p256dh": b64u(pub), "auth": b64u(self.auth)}}

    def read(self, body: bytes) -> dict:
        return json.loads(http_ece.decrypt(body, private_key=self.key, auth_secret=self.auth, version="aes128gcm"))


class PushService:
    """A fake push service: records requests and answers with `status`."""

    def __init__(self, status=201):
        self.status = status
        self.requests: list[httpx.Request] = []

    def transport(self):
        def handle(request: httpx.Request):
            self.requests.append(request)
            return httpx.Response(self.status)
        return httpx.MockTransport(handle)


@pytest.fixture(autouse=True)
def _reset_throttle():
    from app.core.security import login_throttle

    login_throttle.reset()
    yield
    login_throttle.reset()


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    assert res.status_code == 200, res.text
    return {"Cookie": _cookie(res), "id": res.json()["id"]}


@pytest.fixture
def push(monkeypatch):
    """Route sends to a fake service, and treat example.test as a public host."""
    import ipaddress
    from app.services import push as push_svc

    service = PushService()
    monkeypatch.setattr(push_svc, "_transport", lambda: service.transport())
    monkeypatch.setattr(push_svc, "resolve_public_addresses", lambda url: [ipaddress.ip_address("203.0.113.7")])
    return service


async def subscriptions(setup_db):
    from app.models.push import PushSubscription
    return (await setup_db.execute(select(func.count()).select_from(PushSubscription))).scalar()


class TestKeysAndSubscriptions:
    async def test_the_public_key_is_made_once_and_kept(self, client, admin):
        assert (await client.get("/api/push/key")).status_code == 401
        first = (await client.get("/api/push/key", headers=_h(admin))).json()["public_key"]
        assert len(unb64u(first)) == 65 and unb64u(first)[0] == 4  # an uncompressed P-256 point
        assert (await client.get("/api/push/key", headers=_h(admin))).json()["public_key"] == first

    async def test_a_device_subscribes_and_unsubscribes(self, client, admin, setup_db):
        phone = Phone()
        res = await client.post("/api/push/subscriptions", json=phone.subscription(), headers=_h(admin))
        assert res.status_code == 201, res.text
        again = await client.post("/api/push/subscriptions", json=phone.subscription(), headers=_h(admin))
        assert again.status_code == 201 and await subscriptions(setup_db) == 1  # same device, one row
        res = await client.request("DELETE", "/api/push/subscriptions", json={"endpoint": phone.endpoint}, headers=_h(admin))
        assert res.status_code == 200 and await subscriptions(setup_db) == 0

    async def test_a_shared_device_belongs_to_whoever_subscribed_last(self, client, admin, setup_db):
        from app.models.push import PushSubscription
        kid = await _member(client, admin)
        phone = Phone()
        await client.post("/api/push/subscriptions", json=phone.subscription(), headers=_h(admin))
        await client.post("/api/push/subscriptions", json=phone.subscription(), headers=_h(kid))
        row = (await setup_db.execute(select(PushSubscription))).scalar_one()
        assert row.user_id == kid["id"]
        # Someone else can't remove it.
        await client.request("DELETE", "/api/push/subscriptions", json={"endpoint": phone.endpoint}, headers=_h(admin))
        assert await subscriptions(setup_db) == 1

    @pytest.mark.parametrize("bad", [
        {"endpoint": "http://push.example.test/x", "keys": {"p256dh": "AAAA", "auth": "AAAA"}},
        {"endpoint": "https://push.example.test/x", "keys": {"p256dh": "", "auth": "AAAA"}},
        {"endpoint": "https://push.example.test/x"},
        {"endpoint": "https://push.example.test/" + "x" * 2100, "keys": {"p256dh": "AAAA", "auth": "AAAA"}},
    ])
    async def test_bad_subscriptions_are_refused(self, client, admin, bad):
        assert (await client.post("/api/push/subscriptions", json=bad, headers=_h(admin))).status_code == 422


class TestSending:
    async def test_a_push_is_encrypted_for_the_phone_and_signed(self, client, admin, push):
        phone = Phone()
        await client.post("/api/push/subscriptions", json=phone.subscription(), headers=_h(admin))
        res = await client.post("/api/push/test", headers=_h(admin))
        assert res.status_code == 200 and res.json() == {"sent": 1}
        req = push.requests[0]
        assert req.method == "POST" and req.headers["content-encoding"] == "aes128gcm"
        assert req.headers["host"] == "push.example.test" and req.url.host == "203.0.113.7"  # pinned to the checked address
        assert req.headers["authorization"].startswith("vapid t=") and int(req.headers["ttl"]) > 0
        message = phone.read(req.content)
        assert message["title"] == "OpenFamHub" and "notifications are on" in message["body"].lower()

    async def test_a_gone_subscription_is_dropped(self, client, admin, push, setup_db):
        push.status = 410
        await client.post("/api/push/subscriptions", json=Phone().subscription(), headers=_h(admin))
        res = await client.post("/api/push/test", headers=_h(admin))
        assert res.json() == {"sent": 0} and await subscriptions(setup_db) == 0

    async def test_a_push_service_error_keeps_the_subscription(self, client, admin, push, setup_db):
        push.status = 503
        await client.post("/api/push/subscriptions", json=Phone().subscription(), headers=_h(admin))
        assert (await client.post("/api/push/test", headers=_h(admin))).json() == {"sent": 0}
        assert await subscriptions(setup_db) == 1

    async def test_an_endpoint_on_the_local_network_is_never_contacted(self, client, admin, monkeypatch, setup_db):
        from app.services import push as push_svc
        service = PushService()
        monkeypatch.setattr(push_svc, "_transport", lambda: service.transport())
        await client.post("/api/push/subscriptions", json=Phone("https://192.168.10.2/steal").subscription(), headers=_h(admin))
        assert (await client.post("/api/push/test", headers=_h(admin))).json() == {"sent": 0}
        assert service.requests == [] and await subscriptions(setup_db) == 0

    async def test_test_needs_a_subscribed_device(self, client, admin):
        res = await client.post("/api/push/test", headers=_h(admin))
        assert res.status_code == 409 and "turn on" in res.json()["detail"].lower()
