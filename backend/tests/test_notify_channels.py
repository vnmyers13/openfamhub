"""Phase 11: ntfy and email, next to Web Push (services/notify.py).

The server's ntfy server and SMTP account come from the environment
(NTFY_URL, NTFY_TOKEN, SMTP_*). Each person adds their own ntfy topic or
email address in My settings; reminders go to every channel they set up."""
import json
import smtplib

import httpx
import pytest

from app.core.config import settings
from tests.test_phase2 import _h, _member
from tests.test_reminders import admin, device, local, notify, run  # noqa: F401  - fixtures

NTFY = "https://ntfy.example.test"


@pytest.fixture(autouse=True)
def _reset_throttle():
    from app.core.security import login_throttle

    login_throttle.reset()
    yield
    login_throttle.reset()


class Requests(list):
    def __init__(self):
        super().__init__()
        self.state = {"status": 200}


@pytest.fixture
def ntfy(monkeypatch):
    """A fake ntfy server; `status` sets its reply."""
    from app.services import notify as svc

    got = Requests()
    state = got.state

    def handler(request: httpx.Request) -> httpx.Response:
        got.append(request)
        return httpx.Response(state["status"], json={"id": "x"})

    monkeypatch.setattr(settings, "ntfy_url", NTFY + "/")
    monkeypatch.setattr(settings, "ntfy_token", "")
    monkeypatch.setattr(svc, "_transport", lambda: httpx.MockTransport(handler))
    return got


@pytest.fixture
def mailbox(monkeypatch):
    """Capture email instead of contacting an SMTP server."""
    from app.services import notify as svc

    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_from", "OpenFamHub <hub@example.test>")
    monkeypatch.setattr(svc, "_deliver_email", lambda msg: sent.append(msg))
    return sent


def body(request: httpx.Request) -> dict:
    return json.loads(request.content)


class TestPreferences:
    async def test_a_topic_and_an_address_are_saved_and_blank_clears_them(self, client, admin):  # noqa: F811
        await notify(client, admin, ntfy_topic="mom-reminders_7f3k", email_to="mom@example.com")
        got = (await client.get("/api/users/me/preferences", headers=_h(admin))).json()["notifications"]
        assert (got["ntfy_topic"], got["email_to"]) == ("mom-reminders_7f3k", "mom@example.com")
        await notify(client, admin, ntfy_topic="", email_to="  ")
        got = (await client.get("/api/users/me/preferences", headers=_h(admin))).json()["notifications"]
        assert (got["ntfy_topic"], got["email_to"]) == (None, None)

    async def test_bad_topics_and_addresses_are_refused(self, client, admin):  # noqa: F811
        current = (await client.get("/api/users/me/preferences", headers=_h(admin))).json()
        for bad in ({"ntfy_topic": "has space"}, {"ntfy_topic": "x" * 65}, {"ntfy_topic": "a/b"},
                    {"email_to": "not-an-address"}, {"email_to": "a@b.c\nBcc: x@y.z"}, {"email_to": "two@@example.com"}):
            res = await client.put("/api/users/me/preferences", json={**current, "notifications": bad}, headers=_h(admin))
            assert res.status_code == 422, bad


class TestChannels:
    async def test_what_the_server_offers(self, client, admin, monkeypatch):  # noqa: F811
        monkeypatch.setattr(settings, "ntfy_url", "")
        monkeypatch.setattr(settings, "smtp_host", "")
        assert (await client.get("/api/push/channels", headers=_h(admin))).json() == {"ntfy": None, "email": False}
        monkeypatch.setattr(settings, "ntfy_url", NTFY + "/")
        monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
        monkeypatch.setattr(settings, "smtp_from", "hub@example.test")
        assert (await client.get("/api/push/channels", headers=_h(admin))).json() == {"ntfy": NTFY, "email": True}

    async def test_a_test_goes_to_ntfy_and_email_without_a_device(self, client, admin, ntfy, mailbox, monkeypatch):  # noqa: F811
        monkeypatch.setattr(settings, "allowed_origins", "https://hub.example.test,http://localhost:5173")
        await notify(client, admin, ntfy_topic="mom-7f3k", email_to="mom@example.com")
        res = await client.post("/api/push/test", headers=_h(admin))
        assert res.status_code == 200 and res.json() == {"sent": 2}
        sent = body(ntfy[0])
        assert str(ntfy[0].url) == NTFY + "/" and sent["topic"] == "mom-7f3k" and sent["title"] == "OpenFamHub"
        assert sent["click"] == "https://hub.example.test/me" and "Authorization" not in ntfy[0].headers
        (mail,) = mailbox
        assert mail["To"] == "mom@example.com" and mail["Subject"] == "OpenFamHub"
        assert "https://hub.example.test/me" in mail.get_content()

    async def test_nothing_set_up_still_asks_for_a_channel(self, client, admin, ntfy):  # noqa: F811
        res = await client.post("/api/push/test", headers=_h(admin))
        assert res.status_code == 409 and "turn on" in res.json()["detail"].lower()

    async def test_a_topic_without_an_ntfy_server_is_ignored(self, client, admin, monkeypatch):  # noqa: F811
        monkeypatch.setattr(settings, "ntfy_url", "")
        monkeypatch.setattr(settings, "smtp_host", "")
        await notify(client, admin, ntfy_topic="mom-7f3k", email_to="mom@example.com")
        assert (await client.post("/api/push/test", headers=_h(admin))).status_code == 409

    async def test_the_ntfy_token_is_sent(self, client, admin, ntfy, monkeypatch):  # noqa: F811
        monkeypatch.setattr(settings, "ntfy_token", "tk_example")
        await notify(client, admin, ntfy_topic="mom-7f3k")
        await client.post("/api/push/test", headers=_h(admin))
        assert ntfy[0].headers["Authorization"] == "Bearer tk_example"


class TestReminders:
    async def make_chore(self, client, admin, kid):  # noqa: F811
        res = await client.post("/api/chores/templates", headers=_h(admin), json={
            "title": "Feed the cat", "points": 5, "assignment": "assigned", "assigned_to": kid["id"], "repeat": None})
        assert res.status_code == 201, res.text

    async def test_reminders_reach_people_with_only_ntfy_or_email_once(self, client, admin, ntfy, mailbox, run):  # noqa: F811
        kid = await _member(client, admin)
        await notify(client, kid, ntfy_topic="kid-9q2w", email_to="kid@example.com")
        await self.make_chore(client, admin, kid)
        await run(now=local(7, 1))
        assert [body(r)["topic"] for r in ntfy] == ["kid-9q2w"]
        assert body(ntfy[0])["title"] == "Today: 1 chore" and body(ntfy[0])["message"] == "Feed the cat"
        assert [m["To"] for m in mailbox] == ["kid@example.com"]
        await run(now=local(7, 2))
        assert len(ntfy) == 1 and len(mailbox) == 1

    async def test_a_failed_ntfy_send_is_tried_again(self, client, admin, ntfy, run):  # noqa: F811
        kid = await _member(client, admin)
        await notify(client, kid, ntfy_topic="kid-9q2w")
        await self.make_chore(client, admin, kid)
        ntfy.state["status"] = 500
        await run(now=local(7, 1))
        ntfy.state["status"] = 200
        await run(now=local(7, 2))
        await run(now=local(7, 3))
        assert len(ntfy) == 2  # failed, then sent once

    async def test_an_unreachable_ntfy_server_counts_as_not_sent(self, client, admin, monkeypatch, run):  # noqa: F811
        from app.services import notify as svc

        def down(request):
            raise httpx.ConnectError("refused")

        monkeypatch.setattr(settings, "ntfy_url", NTFY)
        monkeypatch.setattr(svc, "_transport", lambda: httpx.MockTransport(down))
        kid = await _member(client, admin)
        await notify(client, kid, ntfy_topic="kid-9q2w")
        await self.make_chore(client, admin, kid)
        assert await run(now=local(7, 1)) == 0

    async def test_wellness_reminders_skip_email(self, client, admin, ntfy, mailbox, run):  # noqa: F811
        kid = await _member(client, admin)
        await notify(client, kid, ntfy_topic="kid-9q2w", email_to="kid@example.com", daily=False,
                     water=True, water_every=60, water_from="09:00", water_until="18:00")
        await run(now=local(10, 0))
        assert [body(r)["topic"] for r in ntfy] == ["kid-9q2w"] and mailbox == []

    async def test_email_only_people_get_no_wellness_reminders(self, client, admin, mailbox, run):  # noqa: F811
        kid = await _member(client, admin)
        await notify(client, kid, email_to="kid@example.com", daily=False, mindful=True, mindful_time="10:00")
        assert await run(now=local(10, 0)) == 0 and mailbox == []

    async def test_device_and_ntfy_both_get_it(self, client, admin, ntfy, run, monkeypatch):  # noqa: F811
        from app.services import push as push_svc

        pushed = []

        async def fake_send(db, user_ids, payload):
            pushed.append(payload)
            return 1

        monkeypatch.setattr(push_svc, "send_to_users", fake_send)
        kid = await _member(client, admin)
        await device(client, kid)
        await notify(client, kid, ntfy_topic="kid-9q2w")
        await self.make_chore(client, admin, kid)
        await run(now=local(7, 1))
        assert len(pushed) == 1 and len(ntfy) == 1


class FakeSMTP:
    log: list = []

    def __init__(self, host, port, timeout=None, context=None):
        FakeSMTP.log.append(("connect", type(self).__name__, host, port))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        FakeSMTP.log.append(("starttls",))

    def login(self, user, password):
        FakeSMTP.log.append(("login", user))

    def send_message(self, msg):
        FakeSMTP.log.append(("send", msg["To"]))


class FakeSMTP_SSL(FakeSMTP):
    pass


@pytest.mark.parametrize("security,expected", [
    ("starttls", [("connect", "FakeSMTP", "smtp.example.test", 587), ("starttls",), ("login", "hub"), ("send", "a@example.com")]),
    ("ssl", [("connect", "FakeSMTP_SSL", "smtp.example.test", 587), ("login", "hub"), ("send", "a@example.com")]),
    ("none", [("connect", "FakeSMTP", "smtp.example.test", 587), ("login", "hub"), ("send", "a@example.com")]),
])
def test_smtp_security_modes(monkeypatch, security, expected):
    from email.message import EmailMessage

    from app.services import notify as svc

    FakeSMTP.log = []
    monkeypatch.setattr(svc.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(svc.smtplib, "SMTP_SSL", FakeSMTP_SSL)
    for key, value in {"smtp_host": "smtp.example.test", "smtp_port": 587, "smtp_security": security,
                       "smtp_username": "hub", "smtp_password": "pw"}.items():
        monkeypatch.setattr(settings, key, value)
    msg = EmailMessage()
    msg["To"] = "a@example.com"
    svc._deliver_email(msg)
    assert FakeSMTP.log == expected


async def test_an_smtp_failure_counts_as_not_sent(monkeypatch):
    from app.services import notify as svc

    def broken(msg):
        raise smtplib.SMTPAuthenticationError(535, b"bad login")

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_from", "hub@example.test")
    monkeypatch.setattr(svc, "_deliver_email", broken)
    assert await svc.send_email("a@example.com", {"title": "Hi\nthere", "body": "x", "url": "/"}) is False
