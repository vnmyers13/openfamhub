"""Calendar source and event scoping (review backlog #6, #7)."""
import pytest

from tests.test_phase2 import SETUP, _cookie, _h


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


WINDOW = {"start": "2026-10-10T00:00:00Z", "end": "2026-10-11T00:00:00Z"}


class TestInternalSourceCreation:
    async def test_admin_cannot_create_an_internal_source(self, client, admin):
        res = await client.post(
            "/api/calendar/sources",
            json={"display_name": "Sneaky", "provider": "internal"},
            headers=_h(admin),
        )
        assert res.status_code == 422

        sources = (await client.get("/api/calendar/sources", headers=_h(admin))).json()
        assert all(s["display_name"] != "Sneaky" for s in sources)

    async def test_ical_is_still_the_default_provider(self, client, admin):
        res = await client.post(
            "/api/calendar/sources",
            json={"display_name": "School", "ics_url": "https://example.test/s.ics"},
            headers=_h(admin),
        )
        assert res.status_code == 201, res.text
        assert res.json()["provider"] == "ical"
