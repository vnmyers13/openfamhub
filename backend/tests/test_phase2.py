"""Phase 2 (v0.30): sign-in model, sessions, admin password gate, event roles."""
import pytest

SETUP = {
    "family_name": "Test Family",
    "timezone": "America/Detroit",
    "admin_display_name": "Mom",
    "admin_password": "securepassword123",
    "admin_pin": "2468",
}


def _cookie(response, name="access_token"):
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(f"{name}=") and not header.startswith(f"{name}=;") and f'{name}=""' not in header:
            return header.split(";", 1)[0]
    raise AssertionError(f"{name} cookie not set: {response.headers.get_list('set-cookie')}")


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


def _h(who):
    return {"Cookie": who["Cookie"]}


async def _member(client, admin, name="Kid", pin="1357", role="member", password=None):
    body = {"display_name": name, "pin": pin, "role": role, "avatar": "🦊"}
    if password:
        body["password"] = password
    res = await client.post("/api/users/", json=body, headers=_h(admin))
    assert res.status_code == 201, res.text
    user = res.json()
    res = await client.post("/api/auth/login/pin", json={"user_id": user["id"], "pin": pin})
    assert res.status_code == 200, res.text
    return {"Cookie": _cookie(res), "id": user["id"]}


async def _event(client, who, title="Dinner"):
    return await client.post(
        "/api/calendar/events",
        json={"title": title, "start_dt": "2026-10-10T22:00:00Z", "end_dt": "2026-10-10T23:00:00Z"},
        headers=_h(who),
    )


class TestProfilesAndPinLogin:
    async def test_profiles_expose_only_picker_fields(self, client, admin):
        await _member(client, admin)
        res = await client.get("/api/auth/profiles")
        assert res.status_code == 200
        profiles = res.json()
        assert {p["display_name"] for p in profiles} == {"Mom", "Kid"}
        for p in profiles:
            assert set(p) == {"id", "display_name", "color_hex", "avatar_type", "avatar_value", "has_pin"}
        kid = next(p for p in profiles if p["display_name"] == "Kid")
        assert kid["avatar_type"] == "emoji" and kid["avatar_value"] == "🦊" and kid["has_pin"] is True

    async def test_pin_lockout_counts_failures_and_blocks_correct_pin(self, client, admin):
        kid = await _member(client, admin)
        for _ in range(5):
            res = await client.post("/api/auth/login/pin", json={"user_id": kid["id"], "pin": "0000"})
            assert res.status_code == 401
        res = await client.post("/api/auth/login/pin", json={"user_id": kid["id"], "pin": "1357"})
        assert res.status_code == 429
        assert int(res.headers["retry-after"]) > 0

    async def test_password_login_lockout(self, client, admin):
        for _ in range(5):
            res = await client.post("/api/auth/login", json={"display_name": "Mom", "password": "wrong-password"})
            assert res.status_code == 401
        res = await client.post("/api/auth/login", json={"display_name": "Mom", "password": SETUP["admin_password"]})
        assert res.status_code == 429

    async def test_deleted_user_cannot_sign_in_and_is_signed_out(self, client, admin):
        kid = await _member(client, admin)
        assert (await client.get("/api/auth/me", headers=_h(kid))).status_code == 200
        assert (await client.delete(f"/api/users/{kid['id']}", headers=_h(admin))).status_code == 200
        assert (await client.get("/api/auth/me", headers=_h(kid))).status_code == 401
        res = await client.post("/api/auth/login/pin", json={"user_id": kid["id"], "pin": "1357"})
        assert res.status_code == 401


class TestAdminPasswordGate:
    async def _admin_pin_session(self, client, admin):
        res = await client.post("/api/auth/login/pin", json={"user_id": admin["id"], "pin": SETUP["admin_pin"]})
        assert res.status_code == 200, res.text
        return {"Cookie": _cookie(res), "id": admin["id"]}

    async def test_pin_session_needs_password_for_admin_actions(self, client, admin):
        pin_admin = await self._admin_pin_session(client, admin)
        me = (await client.get("/api/auth/me", headers=_h(pin_admin))).json()
        assert me["auth_method"] == "pin" and me["admin_unlocked"] is False

        res = await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(pin_admin))
        assert res.status_code == 403
        assert res.json()["detail"] == "password_required"

        res = await client.post("/api/auth/elevate", json={"password": "nope-nope"}, headers=_h(pin_admin))
        assert res.status_code == 401
        res = await client.post("/api/auth/elevate", json={"password": SETUP["admin_password"]}, headers=_h(pin_admin))
        assert res.status_code == 200 and res.json()["admin_unlocked"] is True

        res = await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(pin_admin))
        assert res.status_code == 201

    async def test_password_session_is_admin_capable(self, client, admin):
        me = (await client.get("/api/auth/me", headers=_h(admin))).json()
        assert me["auth_method"] == "password" and me["admin_unlocked"] is True
        res = await client.post("/api/wall/devices", json={"name": "Hall"}, headers=_h(admin))
        assert res.status_code == 201

    async def test_members_get_plain_403_on_admin_endpoints(self, client, admin):
        kid = await _member(client, admin)
        res = await client.post("/api/wall/devices", json={"name": "Hall"}, headers=_h(kid))
        assert res.status_code == 403
        assert res.json()["detail"] != "password_required"


class TestSessions:
    async def test_logout_revokes_the_token(self, client, admin):
        assert (await client.post("/api/auth/logout", headers=_h(admin))).status_code == 200
        assert (await client.get("/api/auth/me", headers=_h(admin))).status_code == 401

    async def test_password_change_revokes_other_sessions(self, client, admin):
        res = await client.post(
            "/api/auth/login", json={"display_name": "Mom", "password": SETUP["admin_password"]}
        )
        other = {"Cookie": _cookie(res)}
        res = await client.patch(
            f"/api/users/{admin['id']}", json={"password": "a-new-password-1"}, headers=_h(admin)
        )
        assert res.status_code == 200, res.text
        assert (await client.get("/api/auth/me", headers=other)).status_code == 401
        assert (await client.get("/api/auth/me", headers=_h(admin))).status_code == 200

    async def test_forged_token_without_session_is_rejected(self, client, admin):
        from app.core.security import create_access_token

        token = create_access_token(admin["id"], "not-a-session")
        res = await client.get("/api/auth/me", headers={"Cookie": f"access_token={token}"})
        assert res.status_code == 401

    async def test_switch_endpoint_is_gone(self, client, admin):
        res = await client.post("/api/users/switch", json={"user_id": admin["id"]}, headers=_h(admin))
        assert res.status_code in (404, 405)


class TestUniqueNames:
    async def test_display_names_are_unique_case_insensitively(self, client, admin):
        await _member(client, admin, name="Kid")
        res = await client.post("/api/users/", json={"display_name": "kid", "pin": "9999"}, headers=_h(admin))
        assert res.status_code == 409
        other = await _member(client, admin, name="Teen", pin="8642")
        res = await client.patch(f"/api/users/{other['id']}", json={"display_name": "MOM"}, headers=_h(admin))
        assert res.status_code == 409


class TestEventRoles:
    async def test_viewer_is_read_only(self, client, admin):
        viewer = await _member(client, admin, name="Grandma", pin="1111", role="viewer")
        assert (await _event(client, viewer)).status_code == 403
        res = await client.get(
            "/api/calendar/events",
            params={"start": "2026-10-01T00:00:00Z", "end": "2026-11-01T00:00:00Z"},
            headers=_h(viewer),
        )
        assert res.status_code == 200

    async def test_members_edit_only_their_own_events(self, client, admin):
        kid = await _member(client, admin)
        moms = (await _event(client, admin, "Mom's meeting")).json()
        kids = (await _event(client, kid, "Soccer")).json()

        assert (await client.patch(f"/api/calendar/events/{moms['id']}", json={"title": "x"}, headers=_h(kid))).status_code == 403
        assert (await client.delete(f"/api/calendar/events/{moms['id']}", headers=_h(kid))).status_code == 403
        res = await client.patch(f"/api/calendar/events/{kids['id']}", json={"title": "Soccer practice"}, headers=_h(kid))
        assert res.status_code == 200 and res.json()["title"] == "Soccer practice"
        # Admins can edit anyone's family events.
        assert (await client.patch(f"/api/calendar/events/{kids['id']}", json={"title": "Soccer!"}, headers=_h(admin))).status_code == 200

    async def test_synced_events_are_read_only(self, client, admin, monkeypatch):
        from datetime import datetime, timezone

        async def fake_fetch(url):
            return [{
                "external_uid": "u1", "title": "School assembly",
                "start_dt": datetime(2026, 10, 12, 13, tzinfo=timezone.utc),
                "end_dt": datetime(2026, 10, 12, 14, tzinfo=timezone.utc),
                "all_day": False, "location": None, "description": None,
            }]

        monkeypatch.setattr("app.jobs.calendar_sync.fetch_and_parse", fake_fetch)
        src = (await client.post(
            "/api/calendar/sources",
            json={"display_name": "School", "ics_url": "https://example.test/s.ics"},
            headers=_h(admin),
        )).json()
        await client.post(f"/api/calendar/sources/{src['id']}/sync", headers=_h(admin))
        events = (await client.get(
            "/api/calendar/events",
            params={"start": "2026-10-12T00:00:00Z", "end": "2026-10-13T00:00:00Z"},
            headers=_h(admin),
        )).json()
        res = await client.patch(f"/api/calendar/events/{events[0]['id']}", json={"title": "x"}, headers=_h(admin))
        assert res.status_code == 403
        assert (await client.delete(f"/api/calendar/events/{events[0]['id']}", headers=_h(admin))).status_code == 403
