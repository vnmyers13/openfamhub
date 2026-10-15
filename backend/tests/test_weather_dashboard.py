"""Phase 8: weather (Open-Meteo, cached) and the dashboard summary."""
from datetime import timedelta

import httpx
import pytest

from app.services import weather as svc
from app.services.chores import family_today
from app.services.rewards import week_start
from tests.test_phase2 import SETUP, _cookie, _h, _member

TODAY = family_today(SETUP["timezone"])

# Every code Open-Meteo documents for weather_code.
OPEN_METEO_CODES = [0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99]

FORECAST = {
    "current": {"temperature_2m": 61.4, "weather_code": 2, "wind_speed_10m": 7.8},
    "daily": {"time": ["2026-10-13", "2026-10-14"], "weather_code": [2, 61],
              "temperature_2m_max": [64.2, 58.0], "temperature_2m_min": [45.9, 44.1],
              "precipitation_probability_max": [10, 80]},
}
LOCATION = {"name": "Ann Arbor, Michigan, United States", "latitude": 42.2776, "longitude": -83.7409, "units": "fahrenheit"}


@pytest.fixture(autouse=True)
def _reset():
    from app.core.security import login_throttle

    login_throttle.reset()
    svc.clear_cache()
    yield
    login_throttle.reset()
    svc.clear_cache()


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    return {"Cookie": _cookie(res), "id": res.json()["id"]}


@pytest.fixture
def open_meteo(monkeypatch):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json={"results": [
                {"name": "Ann Arbor", "admin1": "Michigan", "country": "United States", "latitude": 42.2776, "longitude": -83.7409}]})
        return httpx.Response(200, json=FORECAST)

    monkeypatch.setattr(svc, "transport", httpx.MockTransport(handler))
    return calls


class TestWeather:
    def test_every_wmo_code_has_an_emoji_and_words(self):
        assert [c for c in OPEN_METEO_CODES if c not in svc.WMO] == []
        assert svc.describe("nope") == ("🌡️", "Weather") and svc.describe(42) == ("🌡️", "Weather")

    async def test_not_set_up_yet(self, client, admin):
        assert (await client.get("/api/weather", headers=_h(admin))).json()["configured"] is False

    async def test_admin_picks_a_place_and_everyone_sees_the_forecast(self, client, admin, open_meteo):
        places = (await client.get("/api/weather/places", params={"q": "Ann Arbor"}, headers=_h(admin))).json()
        assert places == [{"name": "Ann Arbor, Michigan, United States", "latitude": 42.2776, "longitude": -83.7409}]
        assert (await client.put("/api/weather/location", json=LOCATION, headers=_h(admin))).status_code == 200
        kid = await _member(client, admin)
        assert (await client.put("/api/weather/location", json=LOCATION, headers=_h(kid))).status_code == 403
        w = (await client.get("/api/weather", headers=_h(kid))).json()
        assert (w["place"], w["temperature"], w["emoji"], w["label"], w["wind"]) == (LOCATION["name"], 61, "⛅", "Partly cloudy", 8)
        assert [(d["date"], d["emoji"], d["high"], d["low"], d["precip_chance"]) for d in w["days"]] == [
            ("2026-10-13", "⛅", 64, 46, 10), ("2026-10-14", "🌦️", 58, 44, 80)]
        forecast_call = next(c for c in open_meteo if c.url.host == "api.open-meteo.com")
        assert forecast_call.url.params["temperature_unit"] == "fahrenheit"
        assert forecast_call.url.params["timezone"] == SETUP["timezone"]

    async def test_the_forecast_is_cached(self, client, admin, open_meteo):
        await client.put("/api/weather/location", json=LOCATION, headers=_h(admin))
        for _ in range(3):
            await client.get("/api/weather", headers=_h(admin))
        assert len([c for c in open_meteo if c.url.host == "api.open-meteo.com"]) == 1

    async def test_the_cache_expires(self, client, admin, open_meteo, monkeypatch):
        await client.put("/api/weather/location", json=LOCATION, headers=_h(admin))
        clock = [1000.0]
        monkeypatch.setattr(svc.time, "monotonic", lambda: clock[0])
        await client.get("/api/weather", headers=_h(admin))
        clock[0] += svc.CACHE_SECONDS - 1
        await client.get("/api/weather", headers=_h(admin))
        clock[0] += 2
        await client.get("/api/weather", headers=_h(admin))
        assert len([c for c in open_meteo if c.url.host == "api.open-meteo.com"]) == 2

    async def test_an_outage_says_so_instead_of_failing(self, client, admin, monkeypatch):
        await client.put("/api/weather/location", json=LOCATION, headers=_h(admin))
        monkeypatch.setattr(svc, "transport", httpx.MockTransport(lambda r: httpx.Response(503)))
        w = (await client.get("/api/weather", headers=_h(admin))).json()
        assert w["configured"] is True and w["error"] == "Weather is unavailable right now"
        res = await client.get("/api/weather/places", params={"q": "Paris"}, headers=_h(admin))
        assert res.status_code == 502

    async def test_turn_it_off_and_validate(self, client, admin, open_meteo):
        await client.put("/api/weather/location", json=LOCATION, headers=_h(admin))
        assert (await client.get("/api/weather/location", headers=_h(admin))).json()["name"] == LOCATION["name"]
        assert (await client.delete("/api/weather/location", headers=_h(admin))).status_code == 200
        assert (await client.get("/api/weather", headers=_h(admin))).json()["configured"] is False
        bad = {**LOCATION, "latitude": 123}
        assert (await client.put("/api/weather/location", json=bad, headers=_h(admin))).status_code == 422


class TestDashboard:
    async def test_one_call_has_everything(self, client, admin):
        kid = await _member(client, admin)
        await client.post("/api/chores/templates", headers=_h(admin), json={
            "title": "Feed the cat", "points": 5, "assignment": "assigned", "assigned_to": kid["id"], "repeat": None})
        await client.post("/api/chores/templates", headers=_h(admin), json={"title": "Bins", "points": 2, "repeat": None})
        [inst] = (await client.get("/api/chores/instances", params={"scope": "mine"}, headers=_h(kid))).json()
        await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))
        await client.post("/api/calendar/events", headers=_h(kid), json={
            "title": "Soccer", "start_dt": f"{TODAY.isoformat()}T00:00:00Z",
            "end_dt": f"{(TODAY + timedelta(days=1)).isoformat()}T00:00:00Z", "all_day": True})
        await client.put(f"/api/meals/plan/{TODAY.isoformat()}/dinner", json={"title": "Tacos"}, headers=_h(kid))
        await client.post("/api/announcements", json={"body": "Pizza Friday", "pinned": True}, headers=_h(admin))
        await client.patch(f"/api/users/{kid['id']}", headers=_h(kid),
                           json={"birthday": (TODAY + timedelta(days=2)).replace(year=TODAY.year - 9).isoformat()})

        s = (await client.get("/api/dashboard/summary", headers=_h(kid))).json()
        assert s["today"] == TODAY.isoformat()
        assert [e["title"] for e in s["events_today"]] == ["Soccer"]
        assert s["chores"] == {"mine_open": 0, "mine_done": 1, "family_open": 1, "family_done": 1}
        assert s["points_balance"] == 5 and s["allowance_cents"] == 0
        assert [m["title"] for m in s["meals_today"]] == ["Tacos"]
        assert all(week_start(TODAY).isoformat() <= m["day"] for m in s["meals_week"])
        assert [(b["display_name"], b["days_away"], b["turns"]) for b in s["birthdays"]] == [("Kid", 2, 9)]
        assert [a["body"] for a in s["announcements"]] == ["Pizza Friday"]
        assert (await client.get("/api/dashboard/summary")).status_code == 401


class TestPreferences:
    async def test_defaults_then_saved_and_read_back(self, client, admin):
        kid = await _member(client, admin)
        res = await client.get("/api/users/me/preferences", headers=_h(kid))
        default_notifications = {"events": "off", "event_minutes": 15, "daily": True, "daily_time": "07:00", "rewards": True,
                                 "birthdays": True, "pantry": True, "allowance": True}
        assert res.json() == {"nav": "side", "calendar_scope": "family", "wallpaper": "none", "wallpaper_media_id": None, "pages": [],
                              "notifications": default_notifications}
        prefs = {"nav": "top", "calendar_scope": "mine", "wallpaper": "ocean", "wallpaper_media_id": None,
                 "pages": [{"name": "Home", "widgets": [{"key": "events", "size": "wide"}, {"key": "stars", "size": "normal"}]},
                           {"name": "Food", "widgets": [{"key": "meals", "size": "normal"}]}]}
        assert (await client.put("/api/users/me/preferences", json=prefs, headers=_h(kid))).status_code == 200
        assert (await client.get("/api/users/me/preferences", headers=_h(kid))).json() == {**prefs, "notifications": default_notifications}
        # Each person has their own.
        assert (await client.get("/api/users/me/preferences", headers=_h(admin))).json()["nav"] == "side"

    async def test_bad_preferences_are_refused(self, client, admin):
        bad = [
            {"nav": "bottom"},
            {"pages": [{"name": "x", "widgets": [{"key": "nope"}]}]},
            {"pages": [{"name": "x", "widgets": [{"key": "events"}, {"key": "events"}]}]},
            {"pages": [{"name": "", "widgets": []}]},
            {"pages": [{"name": str(i), "widgets": []} for i in range(7)]},
        ]
        for body in bad:
            assert (await client.put("/api/users/me/preferences", json=body, headers=_h(admin))).status_code == 422, body
        assert (await client.get("/api/users/me/preferences")).status_code == 401


class TestJustMe:
    async def test_the_calendar_and_dashboard_can_show_just_my_events(self, client, admin):
        kid = await _member(client, admin)
        day = TODAY.isoformat()
        nxt = (TODAY + timedelta(days=1)).isoformat()
        for who, title in ((kid, "Soccer"), (admin, "Book club")):
            await client.post("/api/calendar/events", headers=_h(who), json={
                "title": title, "start_dt": f"{day}T00:00:00Z", "end_dt": f"{nxt}T00:00:00Z", "all_day": True})
        params = {"start": f"{day}T00:00:00Z", "end": f"{nxt}T00:00:00Z"}
        everyone = (await client.get("/api/calendar/events", params=params, headers=_h(kid))).json()
        mine = (await client.get("/api/calendar/events", params={**params, "scope": "mine"}, headers=_h(kid))).json()
        assert sorted(e["title"] for e in everyone) == ["Book club", "Soccer"]
        assert [e["title"] for e in mine] == ["Soccer"]
        s = (await client.get("/api/dashboard/summary", params={"scope": "mine"}, headers=_h(kid))).json()
        assert [e["title"] for e in s["events_today"]] == ["Soccer"]
