"""Phase 3b: family settings (name, timezone, wall sleep schedule)."""
import pytest

from tests.test_phase2 import SETUP, _cookie, _h, _member


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


async def test_members_read_the_settings(client, admin):
    kid = await _member(client, admin)
    res = await client.get("/api/family", headers=_h(kid))
    assert res.status_code == 200
    assert res.json() == {
        "name": SETUP["family_name"], "timezone": SETUP["timezone"],
        "sleep": {"enabled": False, "off": "22:00", "on": "06:30"},
    }


async def test_admin_changes_name_timezone_and_sleep(client, admin):
    res = await client.patch(
        "/api/family",
        json={"name": "The Myers", "timezone": "Europe/London",
              "sleep": {"enabled": True, "off": "21:30", "on": "07:00"}},
        headers=_h(admin),
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"name": "The Myers", "timezone": "Europe/London",
                          "sleep": {"enabled": True, "off": "21:30", "on": "07:00"}}
    assert (await client.get("/api/family", headers=_h(admin))).json()["timezone"] == "Europe/London"


async def test_partial_updates_keep_the_rest(client, admin):
    await client.patch("/api/family", json={"sleep": {"enabled": True, "off": "23:00", "on": "06:00"}}, headers=_h(admin))
    res = await client.patch("/api/family", json={"name": "Renamed"}, headers=_h(admin))
    assert res.json()["sleep"] == {"enabled": True, "off": "23:00", "on": "06:00"}
    assert res.json()["timezone"] == SETUP["timezone"]


@pytest.mark.parametrize("body", [
    {"timezone": "Mars/Olympus_Mons"},
    {"timezone": ""},
    {"name": "   "},
    {"name": "x" * 129},
    {"sleep": {"enabled": True, "off": "25:00", "on": "06:00"}},
    {"sleep": {"enabled": True, "off": "10pm", "on": "06:00"}},
    {"sleep": {"enabled": True, "off": "06:00", "on": "06:00"}},
])
async def test_bad_values_are_rejected(client, admin, body):
    assert (await client.patch("/api/family", json=body, headers=_h(admin))).status_code == 422


async def test_only_admins_change_settings(client, admin):
    kid = await _member(client, admin)
    assert (await client.patch("/api/family", json={"name": "Kid's house"}, headers=_h(kid))).status_code == 403


async def test_a_pin_admin_must_unlock_first(client, admin):
    res = await client.post("/api/auth/login/pin", json={"user_id": admin["id"], "pin": SETUP["admin_pin"]})
    pin_admin = {"Cookie": _cookie(res)}
    res = await client.patch("/api/family", json={"name": "x"}, headers=pin_admin)
    assert res.status_code == 403 and res.json()["detail"] == "password_required"


async def test_the_wall_session_carries_timezone_and_sleep(client, admin):
    await client.patch("/api/family", json={"sleep": {"enabled": True, "off": "22:15", "on": "06:45"}}, headers=_h(admin))
    device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
    pair = await client.post("/api/wall/pair", json={"token": device["token"]})
    wall = {"Cookie": _cookie(pair, "wall_token")}
    session = (await client.get("/api/wall/session", headers=wall)).json()
    assert session["timezone"] == SETUP["timezone"]
    assert session["sleep"] == {"enabled": True, "off": "22:15", "on": "06:45"}


async def test_changing_settings_notifies_walls(client, admin, setup_db):
    # Queued on the session and published after commit (get_db); the test
    # client shares one session, so check the queue directly.
    setup_db.info.pop("pending_events", None)
    await client.patch("/api/family", json={"name": "Renamed"}, headers=_h(admin))
    assert ("settings_updated", {}) in setup_db.info.get("pending_events", [])
