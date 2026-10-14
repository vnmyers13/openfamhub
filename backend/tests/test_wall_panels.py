"""Phase 10: the wall's read-only panels. A paired display reads today's chores,
the week's meals, announcements and the weather with its wall_token cookie,
the same data the app shows a family member, and can't change any of it."""
import pytest

from tests.test_phase2 import SETUP, _cookie, _h, _member

PANELS = ["/api/wall/chores", "/api/wall/meals", "/api/wall/announcements", "/api/wall/weather"]


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


async def _pair(client, admin):
    device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
    res = await client.post("/api/wall/pair", json={"token": device["token"]})
    assert res.status_code == 200, res.text
    return device, {"Cookie": _cookie(res, "wall_token")}


async def test_an_unpaired_or_revoked_display_reads_nothing(client, admin):
    for path in PANELS:
        assert (await client.get(path)).status_code == 401, path
        assert (await client.get(path, headers={"Cookie": "wall_token=not-a-token"})).status_code == 401, path
    device, wall = await _pair(client, admin)
    await client.delete(f"/api/wall/devices/{device['id']}", headers=_h(admin))
    for path in PANELS:
        assert (await client.get(path, headers=wall)).status_code == 401, path


async def test_a_signed_in_member_is_not_a_display(client, admin):
    for path in PANELS:
        assert (await client.get(path, headers=_h(admin))).status_code == 401, path


async def test_the_panels_are_read_only(client, admin):
    _, wall = await _pair(client, admin)
    for path in PANELS:
        for method in ("post", "put", "patch", "delete"):
            res = await getattr(client, method)(path, headers=wall)
            assert res.status_code == 405, (method, path, res.status_code)


async def test_todays_chores_without_routine_steps(client, admin):
    kid = await _member(client, admin, name="Kid")
    await client.post("/api/chores/templates", headers=_h(admin), json={
        "title": "Feed the cat", "points": 5, "assignment": "assigned", "assigned_to": kid["id"], "repeat": None})
    routine = await client.post("/api/routines", headers=_h(admin), json={
        "name": "Morning", "start_time": "07:00", "assigned_to": kid["id"], "steps": [{"title": "Teeth", "minutes": 5}]})
    assert routine.status_code == 201, routine.text
    steps = (await client.get("/api/chores/instances", params={"include_routines": True}, headers=_h(admin))).json()
    assert "Teeth" in [c["title"] for c in steps]  # the routine's step is a chore today...
    _, wall = await _pair(client, admin)
    res = await client.get("/api/wall/chores", headers=wall)
    assert res.status_code == 200, res.text
    chores = res.json()
    assert [c["title"] for c in chores] == ["Feed the cat"]  # ...but not on the chores panel
    assert chores[0]["assigned_to"] == kid["id"] and chores[0]["status"] == "pending"


async def test_the_weeks_meals(client, admin):
    await client.put("/api/meals/plan/2026-10-20/dinner", json={"title": "Tacos"}, headers=_h(admin))
    _, wall = await _pair(client, admin)
    week = (await client.get("/api/wall/meals", params={"start": "2026-10-19"}, headers=wall)).json()
    assert week["week_start"] == "2026-10-19" and len(week["days"]) == 7
    assert [(e["day"], e["slot"], e["title"]) for e in week["entries"]] == [("2026-10-20", "dinner", "Tacos")]
    this_week = await client.get("/api/wall/meals", headers=wall)
    assert this_week.status_code == 200 and len(this_week.json()["days"]) == 7


async def test_announcements_pinned_first_and_capped(client, admin):
    for i in range(12):
        await client.post("/api/announcements", json={"body": f"Note {i}"}, headers=_h(admin))
    first = (await client.get("/api/announcements", headers=_h(admin))).json()[-1]
    await client.patch(f"/api/announcements/{first['id']}", json={"pinned": True}, headers=_h(admin))
    _, wall = await _pair(client, admin)
    notes = (await client.get("/api/wall/announcements", headers=wall)).json()
    assert len(notes) == 10
    assert notes[0]["body"] == first["body"] and notes[0]["pinned"] is True


async def test_weather_says_when_it_is_not_set_up(client, admin):
    _, wall = await _pair(client, admin)
    res = await client.get("/api/wall/weather", headers=wall)
    assert res.status_code == 200 and res.json()["configured"] is False


async def test_weather_uses_the_family_location(client, admin, monkeypatch):
    async def fake_forecast(lat, lon, units, tz):
        return {"current": {"temperature": 12.5, "code": 3, "emoji": "☁️", "label": "Cloudy"}, "days": []}

    monkeypatch.setattr("app.services.weather.forecast", fake_forecast)
    await client.put("/api/weather/location", headers=_h(admin),
                     json={"name": "Detroit", "latitude": 42.33, "longitude": -83.05, "units": "fahrenheit"})
    _, wall = await _pair(client, admin)
    body = (await client.get("/api/wall/weather", headers=wall)).json()
    assert body["configured"] is True and body["place"] == "Detroit"


async def test_a_display_cant_change_the_family_timezone(client, admin):
    """The wall timezone is the family's, set by an admin (Admin › Settings); a display only reads it."""
    _, wall = await _pair(client, admin)
    res = await client.patch("/api/family", json={"timezone": "Asia/Tokyo"}, headers=wall)
    assert res.status_code == 401
    session = (await client.get("/api/wall/session", headers=wall)).json()
    assert session["timezone"] == SETUP.get("timezone", session["timezone"]) and session["timezone"] != "Asia/Tokyo"
    await client.patch("/api/family", json={"timezone": "Asia/Tokyo"}, headers=_h(admin))
    assert (await client.get("/api/wall/session", headers=wall)).json()["timezone"] == "Asia/Tokyo"
