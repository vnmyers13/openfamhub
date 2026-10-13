"""One family per install (review backlog #5).

Sign-in is public (the avatar picker runs before anyone is signed in), so its
queries can't take a family from a session. Instead an install holds exactly
one family: setup refuses a second one, the database rejects a second
`families` row, and the sign-in queries filter by the install's family so a
stray row from anywhere else can never sign in.
"""
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.family import Family
from app.models.user import User
from tests.test_phase2 import SETUP, _cookie


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


async def _family_count(db) -> int:
    return (await db.execute(select(func.count(Family.id)))).scalar()


class TestSetup:
    async def test_second_setup_is_refused(self, client, admin, setup_db):
        res = await client.post("/api/auth/setup", json={**SETUP, "family_name": "Another"})
        assert res.status_code == 400
        assert await _family_count(setup_db) == 1

    async def test_database_rejects_a_second_family(self, admin, setup_db):
        # Two setup requests can race past the count check; the trigger is the backstop.
        setup_db.add(Family(name="Racing setup", timezone="UTC"))
        with pytest.raises(IntegrityError):
            await setup_db.flush()
        await setup_db.rollback()

    async def test_setup_turns_a_lost_race_into_400(self, client, setup_db, monkeypatch):
        # Simulate the race: the count check sees no family, but one already exists.
        setup_db.add(Family(name="Won the race", timezone="UTC"))
        await setup_db.flush()

        import app.routers.auth as auth_router

        async def no_family_yet(db):
            return 0

        monkeypatch.setattr(auth_router, "_family_count", no_family_yet)
        res = await client.post("/api/auth/setup", json=SETUP)
        assert res.status_code == 400
        assert res.json()["detail"] == "Setup already completed"


class TestSignInScope:
    async def _plant_stray_user(self, setup_db) -> User:
        """A user row whose family isn't this install's (e.g. left behind by
        hand edits or an old import). It must never be offered or signed in."""
        stray = User(
            family_id="not-this-install",
            display_name="Stranger",
            email="stranger@example.test",
            hashed_password=hash_password("strangerpassword"),
            pin_hash=hash_password("9999"),
            role="admin",
        )
        setup_db.add(stray)
        await setup_db.flush()
        return stray

    async def test_picker_lists_only_this_familys_members(self, client, admin, setup_db):
        await self._plant_stray_user(setup_db)
        names = [p["display_name"] for p in (await client.get("/api/auth/profiles")).json()]
        assert names == [SETUP["admin_display_name"]]

    async def test_password_login_ignores_other_families(self, client, admin, setup_db):
        await self._plant_stray_user(setup_db)
        res = await client.post(
            "/api/auth/login", json={"display_name": "Stranger", "password": "strangerpassword"}
        )
        assert res.status_code == 401

    async def test_pin_login_ignores_other_families(self, client, admin, setup_db):
        stray = await self._plant_stray_user(setup_db)
        res = await client.post("/api/auth/login/pin", json={"user_id": stray.id, "pin": "9999"})
        assert res.status_code == 401

    async def test_members_still_sign_in(self, client, admin):
        res = await client.post(
            "/api/auth/login",
            json={"display_name": SETUP["admin_display_name"], "password": SETUP["admin_password"]},
        )
        assert res.status_code == 200, res.text

    async def test_sign_in_before_setup_finds_nobody(self, client):
        assert (await client.get("/api/auth/profiles")).json() == []
        res = await client.post("/api/auth/login", json={"display_name": "Mom", "password": "x" * 12})
        assert res.status_code == 401
