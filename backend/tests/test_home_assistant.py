"""Phase 12: Home Assistant (services/home_assistant.py, routers/home_assistant.py).

The server talks to Home Assistant with HA_URL and HA_TOKEN from the
environment. An admin picks which entities the family sees; members and
admins can switch them, viewers and the wall only see them. A routine can
run a scene at its start time. Nothing breaks when Home Assistant is down.
"""
import json
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.core.config import settings
from tests.test_phase2 import SETUP, _cookie, _h, _member
from tests.test_todos_routines import make_routine
from tests.test_wall_panels import _pair

HA = "http://homeassistant.local:8123"
ZONE = ZoneInfo(SETUP["timezone"])

STATES = [
    {"entity_id": "light.kitchen", "state": "on", "attributes": {"friendly_name": "Kitchen light", "brightness": 128}},
    {"entity_id": "switch.coffee", "state": "off", "attributes": {"friendly_name": "Coffee maker"}},
    {"entity_id": "scene.movie_night", "state": "scening", "attributes": {"friendly_name": "Movie night"}},
    {"entity_id": "script.good_morning", "state": "off", "attributes": {"friendly_name": "Good morning"}},
    {"entity_id": "climate.hall", "state": "heat", "attributes": {
        "friendly_name": "Hall thermostat", "current_temperature": 20.5, "temperature": 21, "min_temp": 7, "max_temp": 35}},
    {"entity_id": "sensor.outside", "state": "12.3", "attributes": {"friendly_name": "Outside", "unit_of_measurement": "°C"}},
    {"entity_id": "binary_sensor.front_door", "state": "off", "attributes": {"friendly_name": "Front door", "device_class": "door"}},
    {"entity_id": "automation.lights_off", "state": "on", "attributes": {"friendly_name": "Lights off at night"}},
    {"entity_id": "person.mom", "state": "home", "attributes": {"friendly_name": "Mom"}},
]


class FakeHA:
    """Home Assistant's REST API: GET /api/, GET /api/states, POST /api/services/<domain>/<service>."""

    def __init__(self):
        self.states = {s["entity_id"]: json.loads(json.dumps(s)) for s in STATES}
        self.calls: list[tuple[str, dict, str]] = []
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("refused")
        auth = request.headers.get("Authorization")
        if auth != "Bearer ha-token":
            return httpx.Response(401, json={"message": "Invalid access token"})
        path = request.url.path
        if path == "/api/":
            return httpx.Response(200, json={"message": "API running."})
        if path == "/api/states":
            return httpx.Response(200, json=list(self.states.values()))
        if path.startswith("/api/states/"):
            entity = self.states.get(path.removeprefix("/api/states/"))
            return httpx.Response(200, json=entity) if entity else httpx.Response(404, json={"message": "Entity not found."})
        if path.startswith("/api/services/"):
            domain, service = path.removeprefix("/api/services/").split("/")
            body = json.loads(request.content or b"{}")
            self.calls.append((f"{domain}.{service}", body, str(request.url)))
            entity = self.states.get(body.get("entity_id", ""))
            if entity and service in ("toggle", "turn_on", "turn_off") and domain in ("light", "switch"):
                entity["state"] = {"toggle": "off" if entity["state"] == "on" else "on", "turn_on": "on", "turn_off": "off"}[service]
            if entity and service == "set_temperature":
                entity["attributes"]["temperature"] = body["temperature"]
            return httpx.Response(200, json=[])
        return httpx.Response(404)


@pytest.fixture(autouse=True)
def _reset_throttle():
    from app.core.security import login_throttle

    login_throttle.reset()
    yield
    login_throttle.reset()


@pytest.fixture
def ha(monkeypatch):
    from app.services import home_assistant as svc

    fake = FakeHA()
    monkeypatch.setattr(settings, "ha_url", HA + "/")
    monkeypatch.setattr(settings, "ha_token", "ha-token")
    monkeypatch.setattr(svc, "_transport", lambda: httpx.MockTransport(fake.handler))
    return fake


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    assert res.status_code == 200, res.text
    return {"Cookie": _cookie(res), "id": res.json()["id"]}


async def choose(client, admin, entities, routine_scenes=None):
    res = await client.put("/api/ha/config", json={"entities": entities, "routine_scenes": routine_scenes or {}}, headers=_h(admin))
    assert res.status_code == 200, res.text
    return res.json()


class TestSetup:
    async def test_off_until_the_server_is_given_a_url_and_token(self, client, admin, monkeypatch):
        monkeypatch.setattr(settings, "ha_url", "")
        monkeypatch.setattr(settings, "ha_token", "")
        assert (await client.get("/api/ha/status", headers=_h(admin))).json() == {"configured": False, "reachable": False, "error": None}
        states = (await client.get("/api/ha/states", headers=_h(admin))).json()
        assert states == {"configured": False, "available": False, "error": None, "entities": []}

    async def test_status_says_whether_it_answers(self, client, admin, ha):
        assert (await client.get("/api/ha/status", headers=_h(admin))).json() == {"configured": True, "reachable": True, "error": None}
        ha.down = True
        got = (await client.get("/api/ha/status", headers=_h(admin))).json()
        assert got["reachable"] is False and "reach" in got["error"]

    async def test_a_bad_token_is_reported(self, client, admin, ha, monkeypatch):
        monkeypatch.setattr(settings, "ha_token", "wrong")
        got = (await client.get("/api/ha/status", headers=_h(admin))).json()
        assert got["reachable"] is False and "token" in got["error"].lower()

    async def test_admins_list_the_entities_they_can_choose(self, client, admin, ha):
        got = (await client.get("/api/ha/entities", headers=_h(admin))).json()
        ids = [e["entity_id"] for e in got]
        assert "light.kitchen" in ids and "climate.hall" in ids and "sensor.outside" in ids
        assert "automation.lights_off" not in ids and "person.mom" not in ids  # not supported
        kitchen = next(e for e in got if e["entity_id"] == "light.kitchen")
        assert kitchen == {"entity_id": "light.kitchen", "name": "Kitchen light", "domain": "light", "state": "on"}

    async def test_only_admins_choose(self, client, admin, ha):
        kid = await _member(client, admin)
        assert (await client.get("/api/ha/entities", headers=_h(kid))).status_code == 403
        assert (await client.put("/api/ha/config", json={"entities": []}, headers=_h(kid))).status_code == 403
        assert (await client.get("/api/ha/config", headers=_h(kid))).status_code == 403

    @pytest.mark.parametrize("bad", [
        {"entities": ["automation.lights_off"]},  # not a supported kind
        {"entities": ["not an id"]},
        {"entities": ["light.kitchen", "light.kitchen"]},
        {"entities": [f"light.l{i}" for i in range(25)]},
        {"entities": [], "routine_scenes": {"r1": "light.kitchen"}},  # must be a scene or script
    ])
    async def test_bad_choices_are_refused(self, client, admin, ha, bad):
        assert (await client.put("/api/ha/config", json=bad, headers=_h(admin))).status_code == 422

    async def test_a_routine_scene_needs_one_of_our_routines(self, client, admin, ha):
        res = await client.put("/api/ha/config", json={"entities": [], "routine_scenes": {"someone-elses": "scene.movie_night"}},
                               headers=_h(admin))
        assert res.status_code == 400


class TestStatesAndControl:
    async def test_everyone_sees_the_chosen_entities_in_order(self, client, admin, ha):
        await choose(client, admin, ["climate.hall", "light.kitchen", "sensor.outside", "binary_sensor.front_door"])
        viewer = await _member(client, admin, name="Grandma", pin="1111", role="viewer")
        got = (await client.get("/api/ha/states", headers=_h(viewer))).json()
        assert got["configured"] and got["available"] and got["error"] is None
        assert [e["entity_id"] for e in got["entities"]] == ["climate.hall", "light.kitchen", "sensor.outside", "binary_sensor.front_door"]
        hall, kitchen, outside, door = got["entities"]
        assert (hall["current_temperature"], hall["target_temperature"], hall["min_temp"], hall["max_temp"]) == (20.5, 21, 7, 35)
        assert kitchen["state"] == "on" and kitchen["brightness"] == 50
        assert outside["state"] == "12.3" and outside["unit"] == "°C"
        assert door["device_class"] == "door"

    async def test_an_entity_gone_from_home_assistant_shows_as_unavailable(self, client, admin, ha):
        await choose(client, admin, ["light.kitchen", "light.gone"])
        got = (await client.get("/api/ha/states", headers=_h(admin))).json()
        assert got["entities"][1] == {"entity_id": "light.gone", "name": "light.gone", "domain": "light", "state": "unavailable"}

    async def test_when_home_assistant_is_down_the_card_says_so(self, client, admin, ha):
        await choose(client, admin, ["light.kitchen"])
        ha.down = True
        got = (await client.get("/api/ha/states", headers=_h(admin))).json()
        assert got["available"] is False and got["entities"] == [] and "reach" in got["error"]

    async def test_members_switch_lights_and_run_scenes(self, client, admin, ha):
        await choose(client, admin, ["light.kitchen", "switch.coffee", "scene.movie_night", "script.good_morning"])
        kid = await _member(client, admin)
        res = await client.post("/api/ha/action", json={"entity_id": "switch.coffee", "action": "toggle"}, headers=_h(kid))
        assert res.status_code == 200, res.text
        assert res.json()["state"] == "on"
        await client.post("/api/ha/action", json={"entity_id": "light.kitchen", "action": "turn_off"}, headers=_h(kid))
        await client.post("/api/ha/action", json={"entity_id": "scene.movie_night", "action": "turn_on"}, headers=_h(kid))
        await client.post("/api/ha/action", json={"entity_id": "script.good_morning", "action": "turn_on"}, headers=_h(kid))
        assert [c[0] for c in ha.calls] == ["switch.toggle", "light.turn_off", "scene.turn_on", "script.turn_on"]
        assert ha.calls[0][1] == {"entity_id": "switch.coffee"}
        assert ha.calls[0][2] == HA + "/api/services/switch/toggle"

    async def test_the_thermostat_is_set_within_its_range(self, client, admin, ha):
        await choose(client, admin, ["climate.hall"])
        res = await client.post("/api/ha/action", json={"entity_id": "climate.hall", "action": "set_temperature", "temperature": 22},
                                headers=_h(admin))
        assert res.status_code == 200 and res.json()["target_temperature"] == 22
        assert ha.calls == [("climate.set_temperature", {"entity_id": "climate.hall", "temperature": 22}, HA + "/api/services/climate/set_temperature")]
        for bad in (6, 36, None):
            res = await client.post("/api/ha/action", json={"entity_id": "climate.hall", "action": "set_temperature", "temperature": bad},
                                    headers=_h(admin))
            assert res.status_code in (400, 422), bad

    async def test_viewers_cannot_control_and_nothing_unchosen_can_be_touched(self, client, admin, ha):
        await choose(client, admin, ["light.kitchen", "sensor.outside"])
        viewer = await _member(client, admin, name="Grandma", pin="1111", role="viewer")
        assert (await client.post("/api/ha/action", json={"entity_id": "light.kitchen", "action": "toggle"}, headers=_h(viewer))).status_code == 403
        assert (await client.post("/api/ha/action", json={"entity_id": "switch.coffee", "action": "toggle"}, headers=_h(admin))).status_code == 404
        assert (await client.post("/api/ha/action", json={"entity_id": "sensor.outside", "action": "toggle"}, headers=_h(admin))).status_code == 400
        assert (await client.post("/api/ha/action", json={"entity_id": "light.kitchen", "action": "set_temperature", "temperature": 20},
                                  headers=_h(admin))).status_code == 400
        assert ha.calls == []

    async def test_an_action_while_home_assistant_is_down_explains(self, client, admin, ha):
        await choose(client, admin, ["light.kitchen"])
        ha.down = True
        res = await client.post("/api/ha/action", json={"entity_id": "light.kitchen", "action": "toggle"}, headers=_h(admin))
        assert res.status_code == 502 and "reach" in res.json()["detail"]

    async def test_the_wall_sees_but_cannot_change(self, client, admin, ha):
        await choose(client, admin, ["light.kitchen"])
        _, wall = await _pair(client, admin)
        got = (await client.get("/api/wall/home-assistant", headers=wall)).json()
        assert got["available"] and got["entities"][0]["entity_id"] == "light.kitchen"
        assert (await client.post("/api/ha/action", json={"entity_id": "light.kitchen", "action": "toggle"}, headers=wall)).status_code == 401
        assert (await client.get("/api/wall/home-assistant", headers={"Cookie": "wall_token=nope"})).status_code == 401


class TestRoutineScenes:
    @pytest.fixture
    def job(self, setup_db, monkeypatch):
        from app.jobs import home_assistant as job

        @asynccontextmanager
        async def shared_session():
            yield setup_db

        monkeypatch.setattr(job, "session_factory", shared_session)
        return job.run_routine_scenes

    def at(self, hh, mm, days=0):
        today = datetime.now(timezone.utc).astimezone(ZONE).date() + timedelta(days=days)
        return datetime.combine(today, time(hh, mm), ZONE).astimezone(timezone.utc)

    async def test_a_routine_runs_its_scene_at_its_start_once(self, client, admin, ha, job):
        kid = await _member(client, admin)
        routine = await make_routine(client, admin, kid, start_time="07:00")
        await choose(client, admin, [], {routine["id"]: "script.good_morning"})
        assert await job(now=self.at(6, 59)) == 0
        assert await job(now=self.at(7, 0)) == 1
        assert await job(now=self.at(7, 1)) == 0
        assert [c[0] for c in ha.calls] == ["script.turn_on"]
        assert ha.calls[0][1] == {"entity_id": "script.good_morning"}

    async def test_a_late_start_is_skipped_and_a_failure_is_retried(self, client, admin, ha, job):
        kid = await _member(client, admin)
        routine = await make_routine(client, admin, kid, start_time="07:00")
        await choose(client, admin, [], {routine["id"]: "scene.movie_night"})
        ha.down = True
        assert await job(now=self.at(7, 0)) == 0
        ha.down = False
        assert await job(now=self.at(7, 2)) == 1  # still within a few minutes: tried again
        assert await job(now=self.at(9, 0)) == 0
        assert len(ha.calls) == 1

    async def test_nothing_without_home_assistant_or_a_scene(self, client, admin, ha, job, monkeypatch):
        kid = await _member(client, admin)
        await make_routine(client, admin, kid, start_time="07:00")
        assert await job(now=self.at(7, 0)) == 0
        monkeypatch.setattr(settings, "ha_url", "")
        assert await job(now=self.at(7, 0)) == 0
        assert ha.calls == []
