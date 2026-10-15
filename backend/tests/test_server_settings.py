"""Server settings in Admin › Settings (2026-10-15): Home Assistant, ntfy,
email, backups and the wall's idle timeout can be set in the app.

Secrets are stored encrypted with a key derived from SECRET_KEY, are
write-only through the API, and never appear in logs. A value set in `.env`
still wins and locks the field, so installs configured there keep working.
"""
import logging

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.services import server_config as cfg
from tests.test_phase2 import SETUP, _cookie, _h, _member
from tests.test_reminders import notify

URL = "/api/admin/server-settings"


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


@pytest.fixture(autouse=True)
def _no_env(monkeypatch):
    """As if nothing were set in .env (CI only sets SECRET_KEY)."""
    for name in ("ha_url", "ha_token", "ntfy_url", "ntfy_token", "smtp_host", "smtp_username", "smtp_password", "smtp_from"):
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_security", "starttls")
    monkeypatch.setattr(settings, "backup_time", "03:00")
    monkeypatch.setattr(settings, "backup_retention_days", 30)
    monkeypatch.setattr(settings, "wall_idle_timeout_seconds", 300)


async def put(client, who, body, status=200):
    res = await client.put(URL, json=body, headers=_h(who))
    assert res.status_code == status, res.text
    return res.json()


class TestReadingAndSaving:
    async def test_defaults_until_changed(self, client, admin):
        got = (await client.get(URL, headers=_h(admin))).json()
        assert got["ha_url"] == {"value": "", "locked": False}
        assert got["ha_token"] == {"is_set": False, "locked": False}
        assert got["smtp_port"] == {"value": 587, "locked": False}
        assert got["smtp_security"] == {"value": "starttls", "locked": False}
        assert got["backup_time"] == {"value": "03:00", "locked": False}
        assert got["wall_idle_timeout_seconds"] == {"value": 300, "locked": False}

    async def test_values_are_saved_and_used(self, client, admin):
        await put(client, admin, {"ha_url": "http://192.168.1.20:8123", "ha_token": "tok-123", "smtp_port": 465,
                                  "smtp_security": "ssl", "wall_idle_timeout_seconds": 120})
        got = (await client.get(URL, headers=_h(admin))).json()
        assert got["ha_url"]["value"] == "http://192.168.1.20:8123" and got["ha_token"] == {"is_set": True, "locked": False}
        assert (got["smtp_port"]["value"], got["smtp_security"]["value"]) == (465, "ssl")
        assert cfg.get("ha_token") == "tok-123" and cfg.get("smtp_port") == 465
        from app.services import home_assistant
        assert home_assistant.configured()

    async def test_absent_keeps_and_empty_clears(self, client, admin):
        await put(client, admin, {"ntfy_url": "https://ntfy.sh", "ntfy_token": "tk"})
        await put(client, admin, {"ntfy_url": "https://ntfy.example"})
        assert cfg.get("ntfy_token") == "tk"
        await put(client, admin, {"ntfy_token": ""})
        assert cfg.get("ntfy_token") == "" and (await client.get(URL, headers=_h(admin))).json()["ntfy_token"]["is_set"] is False

    async def test_values_survive_a_restart(self, client, admin, setup_db):
        await put(client, admin, {"smtp_host": "smtp.example.com", "smtp_password": "pw-secret"})
        cfg.clear()
        assert cfg.get("smtp_host") == ""
        await cfg.load(setup_db)
        assert (cfg.get("smtp_host"), cfg.get("smtp_password")) == ("smtp.example.com", "pw-secret")

    @pytest.mark.parametrize("bad", [
        {"ha_url": "ftp://x"}, {"ha_url": "homeassistant.local"}, {"ntfy_url": "javascript:alert(1)"},
        {"smtp_port": 0}, {"smtp_port": 70000}, {"smtp_security": "tls"}, {"smtp_host": "a b"},
        {"backup_time": "25:00"}, {"backup_retention_days": 0}, {"wall_idle_timeout_seconds": 5},
        {"secret_key": "x"}, {"database_url": "sqlite://"}, {"ha_token": "x" * 5000},
    ])
    async def test_bad_values_and_unknown_settings_are_refused(self, client, admin, bad):
        await put(client, admin, bad, status=422)


class TestSecrets:
    async def test_secrets_never_come_back_and_are_stored_encrypted(self, client, admin, setup_db, caplog):
        caplog.set_level(logging.DEBUG)
        await put(client, admin, {"ha_token": "super-secret-token", "smtp_password": "hunter2-password", "ntfy_token": "tk_secret_ntfy"})
        res = await client.get(URL, headers=_h(admin))
        assert "super-secret-token" not in res.text and "hunter2-password" not in res.text and "tk_secret_ntfy" not in res.text
        from app.models.server_setting import ServerSetting
        rows = {r.key: r for r in (await setup_db.execute(select(ServerSetting))).scalars().all()}
        assert rows["ha_token"].secret and "super-secret-token" not in rows["ha_token"].value
        assert "hunter2-password" not in rows["smtp_password"].value
        for record in caplog.records:
            text = record.getMessage()
            assert "super-secret-token" not in text and "hunter2-password" not in text and "tk_secret_ntfy" not in text

    async def test_a_changed_secret_key_means_re_entering_them(self, client, admin, setup_db, monkeypatch):
        await put(client, admin, {"ha_url": "http://ha.local:8123", "ha_token": "tok-123"})
        original = settings.secret_key
        monkeypatch.setattr(settings, "secret_key", "a-different-secret-key-0123456789abcdef")
        cfg.clear()
        await cfg.load(setup_db)
        assert cfg.get("ha_token") == "" and cfg.get("ha_url") == "http://ha.local:8123"
        monkeypatch.setattr(settings, "secret_key", original)  # sign-ins use it too; keep the admin signed in
        got = (await client.get(URL, headers=_h(admin))).json()
        assert got["ha_token"] == {"is_set": False, "locked": False, "unreadable": True}


class TestEnvWins:
    async def test_a_value_in_env_overrides_and_locks_the_field(self, client, admin, monkeypatch):
        await put(client, admin, {"ha_url": "http://from-app:8123", "smtp_port": 2525})
        monkeypatch.setattr(settings, "ha_url", "http://from-env:8123")
        monkeypatch.setattr(settings, "ha_token", "env-token")
        monkeypatch.setattr(settings, "smtp_port", 465)
        got = (await client.get(URL, headers=_h(admin))).json()
        assert got["ha_url"] == {"value": "http://from-env:8123", "locked": True}
        assert got["ha_token"] == {"is_set": True, "locked": True}
        assert got["smtp_port"] == {"value": 465, "locked": True}
        assert cfg.get("ha_url") == "http://from-env:8123" and cfg.get("smtp_port") == 465
        res = await client.put(URL, json={"ha_url": "http://other:8123"}, headers=_h(admin))
        assert res.status_code == 409 and "ha_url" in res.json()["detail"]


class TestWhoMayChange:
    async def test_only_an_unlocked_admin(self, client, admin):
        kid = await _member(client, admin)
        viewer = await _member(client, admin, name="Grandma", pin="1111", role="viewer")
        for who in (kid, viewer):
            assert (await client.get(URL, headers=_h(who))).status_code == 403
            assert (await client.put(URL, json={"ha_url": "http://x:1"}, headers=_h(who))).status_code == 403
        res = await client.post("/api/auth/login/pin", json={"user_id": admin["id"], "pin": SETUP["admin_pin"]})
        pin_admin = {"Cookie": _cookie(res)}
        res = await client.get(URL, headers=pin_admin)
        assert res.status_code == 403 and res.json()["detail"] == "password_required"


class TestWiring:
    async def test_the_wall_gets_the_idle_timeout(self, client, admin):
        await put(client, admin, {"wall_idle_timeout_seconds": 90})
        device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
        pair = await client.post("/api/wall/pair", json={"token": device["token"]})
        session = (await client.get("/api/wall/session", headers={"Cookie": _cookie(pair, "wall_token")})).json()
        assert session["idle_timeout_seconds"] == 90

    async def test_the_backup_runs_at_the_new_time_in_the_family_timezone(self, client, admin):
        from app.jobs.scheduler import scheduler

        await put(client, admin, {"backup_time": "02:30", "backup_retention_days": 14})
        job = scheduler.get_job("daily_backup")
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert (fields["hour"], fields["minute"]) == ("2", "30")
        assert str(job.trigger.timezone) == SETUP["timezone"]
        assert cfg.get("backup_retention_days") == 14
        res = await client.patch("/api/family", json={"timezone": "Europe/London"}, headers=_h(admin))
        assert res.status_code == 200, res.text
        assert str(scheduler.get_job("daily_backup").trigger.timezone) == "Europe/London"


class TestTryingThemOut:
    async def test_home_assistant(self, client, admin, monkeypatch):
        from app.services import home_assistant

        monkeypatch.setattr(home_assistant, "_transport", lambda: httpx.MockTransport(
            lambda r: httpx.Response(200 if r.headers.get("Authorization") == "Bearer tok" else 401, json={})))
        await put(client, admin, {"ha_url": "http://ha.local:8123", "ha_token": "wrong"})
        got = (await client.post(f"{URL}/test/home-assistant", headers=_h(admin))).json()
        assert got["ok"] is False and "token" in got["message"].lower()
        await put(client, admin, {"ha_token": "tok"})
        assert (await client.post(f"{URL}/test/home-assistant", headers=_h(admin))).json() == {"ok": True, "message": "Connected."}

    async def test_ntfy_goes_to_the_admins_own_topic(self, client, admin, monkeypatch):
        from app.services import notify as svc

        sent = []

        def handler(request):
            sent.append(request)
            return httpx.Response(200, json={})

        monkeypatch.setattr(svc, "_transport", lambda: httpx.MockTransport(handler))
        await put(client, admin, {"ntfy_url": "https://ntfy.example"})
        got = (await client.post(f"{URL}/test/ntfy", headers=_h(admin))).json()
        assert got["ok"] is False and "topic" in got["message"]
        await notify(client, admin, ntfy_topic="mom-7f3k")
        assert (await client.post(f"{URL}/test/ntfy", headers=_h(admin))).json()["ok"] is True
        assert len(sent) == 1 and b"mom-7f3k" in sent[0].content

    async def test_email_goes_to_the_admins_own_address(self, client, admin, monkeypatch):
        from app.services import notify as svc

        mails = []
        monkeypatch.setattr(svc, "_deliver_email", lambda msg: mails.append(msg))
        got = (await client.post(f"{URL}/test/email", headers=_h(admin))).json()
        assert got["ok"] is False and "not set up" in got["message"]
        await put(client, admin, {"smtp_host": "smtp.example.com", "smtp_from": "hub@example.com"})
        got = (await client.post(f"{URL}/test/email", headers=_h(admin))).json()
        assert got["ok"] is False and "address" in got["message"]
        await notify(client, admin, email_to="mom@example.com")
        assert (await client.post(f"{URL}/test/email", headers=_h(admin))).json()["ok"] is True
        assert mails[0]["To"] == "mom@example.com"

    async def test_unknown_test(self, client, admin):
        assert (await client.post(f"{URL}/test/fax", headers=_h(admin))).status_code == 404
