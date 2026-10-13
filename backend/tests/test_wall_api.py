"""Wall display routes not covered by the pairing tests."""
import pytest

from tests.test_phase2 import SETUP, _cookie, _event, _h


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


def test_live_update_socket_refuses_unpaired_displays():
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from app.main import app

    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(app).websocket_connect("/api/wall/ws") as ws:
            ws.receive_text()
    assert exc.value.code == 4401
