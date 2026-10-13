"""Family member management: listing, editing, deleting, PINs and field rules."""
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


async def test_list_and_get_members(client, admin):
    kid = await _member(client, admin, name="Kid")
    names = [u["display_name"] for u in (await client.get("/api/users/", headers=_h(admin))).json()]
    assert names == ["Kid", "Mom"]
    assert (await client.get(f"/api/users/{kid['id']}", headers=_h(admin))).json()["display_name"] == "Kid"
    assert (await client.get(f"/api/users/{kid['id']}", headers=_h(kid))).status_code == 200  # self
    assert (await client.get(f"/api/users/{admin['id']}", headers=_h(kid))).status_code == 403
    assert (await client.get("/api/users/nope", headers=_h(admin))).status_code == 404


async def test_admin_edits_a_members_profile(client, admin):
    kid = await _member(client, admin)
    res = await client.patch(
        f"/api/users/{kid['id']}",
        json={"display_name": "Sam", "email": "sam@example.test", "color_hex": "#F59E0B",
              "ui_mode": "simple", "avatar": "🐢", "role": "viewer"},
        headers=_h(admin),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["display_name"], body["color_hex"], body["ui_mode"], body["role"]) == ("Sam", "#F59E0B", "simple", "viewer")


async def test_renaming_to_a_taken_name_is_409(client, admin):
    kid = await _member(client, admin)
    res = await client.patch(f"/api/users/{kid['id']}", json={"display_name": " mom "}, headers=_h(admin))
    assert res.status_code == 409


async def test_members_cannot_change_their_role_or_others(client, admin):
    kid = await _member(client, admin)
    assert (await client.patch(f"/api/users/{kid['id']}", json={"role": "admin"}, headers=_h(kid))).status_code == 403
    assert (await client.patch(f"/api/users/{admin['id']}", json={"color_hex": "#000000"}, headers=_h(kid))).status_code == 403


async def test_unknown_member_is_404(client, admin):
    assert (await client.patch("/api/users/nope", json={"color_hex": "#000000"}, headers=_h(admin))).status_code == 404
    assert (await client.delete("/api/users/nope", headers=_h(admin))).status_code == 404
    assert (await client.post("/api/users/nope/pin", json={"pin": "1234"}, headers=_h(admin))).status_code == 404


async def test_admins_cannot_delete_themselves(client, admin):
    assert (await client.delete(f"/api/users/{admin['id']}", headers=_h(admin))).status_code == 400


async def test_set_pin_then_sign_in_with_it(client, admin):
    kid = await _member(client, admin, pin="1357")
    res = await client.post(f"/api/users/{kid['id']}/pin", json={"pin": "8642"}, headers=_h(admin))
    assert res.status_code == 200 and res.json()["has_pin"] is True
    assert (await client.post("/api/auth/login/pin", json={"user_id": kid["id"], "pin": "8642"})).status_code == 200
    assert (await client.post("/api/auth/login/pin", json={"user_id": kid["id"], "pin": "1357"})).status_code == 401


@pytest.mark.parametrize("body", [
    {"display_name": "   ", "pin": "1234"},
    {"display_name": "x" * 101, "pin": "1234"},
    {"display_name": "Ok", "color_hex": "#12345"},
    {"display_name": "Ok", "color_hex": "#GGGGGG"},
    {"display_name": "Ok", "password": "short"},
    {"display_name": "Ok", "pin": "12ab"},
    {"display_name": "Ok", "pin": "123"},
    {"display_name": "Ok", "role": "owner"},
    {"display_name": "Ok", "ui_mode": "fancy"},
    {"display_name": "Ok", "avatar": "x" * 17},
])
async def test_field_rules(client, admin, body):
    res = await client.post("/api/users/", json=body, headers=_h(admin))
    assert res.status_code == 422, (body, res.text)


async def test_new_member_defaults(client, admin):
    res = await client.post("/api/users/", json={"display_name": "Grandpa"}, headers=_h(admin))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["role"] == "member" and body["ui_mode"] == "standard" and body["has_pin"] is False
