"""Wall display routes not covered by the pairing tests."""
import httpx
import pytest

from app.services import weather as weather_svc
from app.services.chores import family_today
from tests.test_phase2 import SETUP, _cookie, _event, _h, _member

TODAY = family_today(SETUP["timezone"])
LOCATION = {"name": "Ann Arbor, Michigan, United States", "latitude": 42.2776, "longitude": -83.7409, "units": "fahrenheit"}
FORECAST = {
    "current": {"temperature_2m": 61.4, "weather_code": 2, "wind_speed_10m": 7.8},
    "daily": {"time": [TODAY.isoformat()], "weather_code": [2],
              "temperature_2m_max": [64.2], "temperature_2m_min": [45.9],
              "precipitation_probability_max": [10]},
}


@pytest.fixture(autouse=True)
def _reset_throttle():
    from app.core.security import login_throttle

    login_throttle.reset()
    weather_svc.clear_cache()
    yield
    login_throttle.reset()
    weather_svc.clear_cache()


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    assert res.status_code == 200, res.text
    return {"Cookie": _cookie(res), "id": res.json()["id"]}


async def _pair(client, admin, name="Kitchen"):
    device = (await client.post("/api/wall/devices", json={"name": name}, headers=_h(admin))).json()
    res = await client.post("/api/wall/pair", json={"token": device["token"]})
    assert res.status_code == 200, res.text
    return device, {"Cookie": _cookie(res, "wall_token")}


async def test_devices_list_hides_revoked_ones(client, admin):
    kitchen, _ = await _pair(client, admin, "Kitchen")
    hall, _ = await _pair(client, admin, "Hall")
    await client.delete(f"/api/wall/devices/{hall['id']}", headers=_h(admin))
    names = [d["name"] for d in (await client.get("/api/wall/devices", headers=_h(admin))).json()]
    assert names == ["Kitchen"]


async def test_revoking_an_unknown_display_is_404(client, admin):
    assert (await client.delete("/api/wall/devices/nope", headers=_h(admin))).status_code == 404


@pytest.mark.parametrize("name", ["", "   ", "x" * 65])
async def test_display_names_are_1_to_64_characters(client, admin, name):
    res = await client.post("/api/wall/devices", json={"name": name}, headers=_h(admin))
    assert res.status_code == 422


async def test_wall_events_accept_times_without_an_offset(client, admin):
    await _event(client, admin, "Dinner")  # 22:00-23:00Z on 2026-10-10
    _, wall = await _pair(client, admin)
    res = await client.get(
        "/api/wall/events", params={"start": "2026-10-10T00:00:00", "end": "2026-10-11T00:00:00"}, headers=wall
    )
    assert res.status_code == 200
    assert [e["title"] for e in res.json()] == ["Dinner"]


async def test_a_bad_pairing_token_is_refused(client, admin):
    res = await client.post("/api/wall/pair", json={"token": "not-a-real-token"})
    assert res.status_code in (400, 401, 404)


async def test_wall_session_includes_dashboard_config(client, admin):
    kid = await _member(client, admin)
    dashboard = {"pages": [{"name": "Kitchen", "duration_seconds": 45, "widgets": [{"key": "events", "size": "wide"}]}]}
    assert (await client.put("/api/family/wall-dashboard", json=dashboard, headers=_h(kid))).status_code == 200
    _, wall = await _pair(client, admin)

    session = (await client.get("/api/wall/session", headers=wall)).json()

    assert session["dashboard"] == dashboard


@pytest.mark.parametrize("path", ["/api/wall/chores", "/api/wall/meals", "/api/wall/announcements", "/api/wall/weather"])
async def test_wall_read_only_endpoints_require_pairing(client, admin, path):
    assert (await client.get(path)).status_code == 401


async def test_wall_meals_and_announcements_are_family_scoped(client, admin):
    await client.put(f"/api/meals/plan/{TODAY.isoformat()}/dinner", json={"title": "Tacos"}, headers=_h(admin))
    await client.post("/api/announcements", json={"body": "Pizza Friday", "pinned": True}, headers=_h(admin))
    _, wall = await _pair(client, admin)

    meals = (await client.get("/api/wall/meals", headers=wall)).json()
    announcements = (await client.get("/api/wall/announcements", headers=wall)).json()

    assert TODAY.isoformat() in meals["days"]
    assert [(m["day"], m["slot"], m["title"]) for m in meals["entries"]] == [(TODAY.isoformat(), "dinner", "Tacos")]
    assert [a["body"] for a in announcements] == ["Pizza Friday"]


async def test_wall_chores_returns_todays_non_routine_chores(client, admin):
    kid = await _member(client, admin)
    await client.post("/api/chores/templates", headers=_h(admin), json={
        "title": "Feed the cat", "points": 5, "assignment": "assigned", "assigned_to": kid["id"], "repeat": None})
    await client.post("/api/routines", headers=_h(admin), json={
        "name": "Morning", "assigned_to": kid["id"], "steps": [{"title": "Brush teeth", "minutes": 2}], "repeat": None})
    _, wall = await _pair(client, admin)

    chores = (await client.get("/api/wall/chores", headers=wall)).json()

    assert [(c["title"], c["status"], c["assigned_to"]) for c in chores] == [("Feed the cat", "pending", kid["id"])]


async def test_wall_weather_uses_family_weather_settings(client, admin, monkeypatch):
    monkeypatch.setattr(weather_svc, "transport", httpx.MockTransport(lambda r: httpx.Response(200, json=FORECAST)))
    assert (await client.put("/api/weather/location", json=LOCATION, headers=_h(admin))).status_code == 200
    _, wall = await _pair(client, admin)

    weather = (await client.get("/api/wall/weather", headers=wall)).json()

    assert (weather["place"], weather["temperature"], weather["emoji"], weather["label"], weather["wind"]) == (
        LOCATION["name"], 61, "⛅", "Partly cloudy", 8)


def test_live_update_socket_refuses_unpaired_displays():
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from app.main import app

    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(app).websocket_connect("/api/wall/ws") as ws:
            ws.receive_text()
    assert exc.value.code == 4401
