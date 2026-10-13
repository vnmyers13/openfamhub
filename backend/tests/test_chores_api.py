"""Phase 5: the chores API (templates, claim/complete/undo, points, admin views)."""
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.chores import ChoreInstance, PointsEntry
from app.services.chores import family_today
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


@pytest.fixture
async def kids(client, admin):
    kid = await _member(client, admin, name="Kid", pin="1357")
    sib = await _member(client, admin, name="Sib", pin="2468")
    return kid, sib


TODAY = family_today(SETUP["timezone"])


async def make_chore(client, admin, **body):
    payload = {"title": "Feed the cat", "points": 5, "assignment": "claimable", "repeat": {"every": "day"}}
    payload.update(body)
    res = await client.post("/api/chores/templates", json=payload, headers=_h(admin))
    assert res.status_code == 201, res.text
    return res.json()


async def today_instances(client, who, scope="family"):
    res = await client.get("/api/chores/instances", params={"scope": scope}, headers=_h(who))
    assert res.status_code == 200, res.text
    return res.json()


async def balance(client, who, user_id):
    res = await client.get("/api/chores/stats", params={"user_id": user_id}, headers=_h(who))
    assert res.status_code == 200, res.text
    return res.json()["points_balance"]


class TestTemplates:
    async def test_admin_creates_a_chore_and_todays_instance_exists(self, client, admin, kids):
        kid, _ = kids
        chore = await make_chore(client, admin, assignment="assigned", assigned_to=kid["id"])
        assert chore["start_date"] == TODAY.isoformat() and chore["repeat"]["every"] == "day"
        [inst] = await today_instances(client, admin)
        assert inst["template_id"] == chore["id"] and inst["title"] == "Feed the cat"
        assert inst["assigned_to"] == kid["id"] and inst["points"] == 5 and inst["due_date"] == TODAY.isoformat()

    async def test_a_week_of_instances_is_created_up_front(self, client, admin, setup_db):
        await make_chore(client, admin)
        rows = (await setup_db.execute(select(ChoreInstance))).scalars().all()
        assert sorted(r.due_date for r in rows) == [TODAY + timedelta(days=i) for i in range(7)]

    async def test_only_admins_manage_chores(self, client, admin, kids):
        kid, _ = kids
        res = await client.post("/api/chores/templates", json={"title": "Free points", "points": 999}, headers=_h(kid))
        assert res.status_code == 403
        chore = await make_chore(client, admin)
        assert (await client.patch(f"/api/chores/templates/{chore['id']}", json={"points": 99}, headers=_h(kid))).status_code == 403
        assert (await client.delete(f"/api/chores/templates/{chore['id']}", headers=_h(kid))).status_code == 403
        listed = (await client.get("/api/chores/templates", headers=_h(kid))).json()
        assert [c["id"] for c in listed] == [chore["id"]]  # members can see them

    @pytest.mark.parametrize("body", [
        {"title": ""},
        {"title": "x", "points": -1},
        {"title": "x", "points": 100001},
        {"title": "x", "assignment": "assigned"},  # no assignee
        {"title": "x", "assignment": "sometimes"},
        {"title": "x", "repeat": {"every": "fortnight"}},
        {"title": "x", "repeat": {"every": "day", "interval": 0}},
        {"title": "x", "repeat": {"every": "week", "weekdays": ["mo", "funday"]}},
        {"title": "x", "repeat": {"every": "month", "month_day": 31}},
    ])
    async def test_bad_chores_are_rejected(self, client, admin, body):
        assert (await client.post("/api/chores/templates", json=body, headers=_h(admin))).status_code == 422

    async def test_assignee_must_be_in_the_family(self, client, admin):
        res = await client.post("/api/chores/templates",
                                json={"title": "x", "assignment": "assigned", "assigned_to": "stranger"}, headers=_h(admin))
        assert res.status_code == 400

    async def test_editing_the_schedule_rebuilds_open_instances(self, client, admin, setup_db):
        chore = await make_chore(client, admin)
        tomorrow = TODAY + timedelta(days=1)
        res = await client.patch(f"/api/chores/templates/{chore['id']}",
                                 json={"repeat": {"every": "none"}, "start_date": tomorrow.isoformat(), "title": "Vet visit"},
                                 headers=_h(admin))
        assert res.status_code == 200, res.text
        rows = (await setup_db.execute(select(ChoreInstance))).scalars().all()
        assert [r.due_date for r in rows] == [tomorrow]

    async def test_retiring_a_chore_keeps_its_history(self, client, admin, kids):
        kid, _ = kids
        chore = await make_chore(client, admin, assignment="assigned", assigned_to=kid["id"])
        [inst] = await today_instances(client, kid, "mine")
        await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))
        assert (await client.delete(f"/api/chores/templates/{chore['id']}", headers=_h(admin))).status_code == 200
        assert (await client.get("/api/chores/templates", headers=_h(admin))).json() == []
        log = (await client.get("/api/chores/log", headers=_h(admin))).json()
        assert [e["title"] for e in log] == ["Feed the cat"]


class TestClaimAndComplete:
    async def test_anyone_in_the_family_can_claim_an_open_chore(self, client, admin, kids):
        kid, sib = kids
        await make_chore(client, admin)
        [inst] = await today_instances(client, kid, "available")
        res = await client.post(f"/api/chores/instances/{inst['id']}/claim", headers=_h(kid))
        assert res.status_code == 200 and res.json()["status"] == "claimed" and res.json()["claimed_by"] == kid["id"]
        assert await today_instances(client, sib, "available") == []
        assert (await client.post(f"/api/chores/instances/{inst['id']}/claim", headers=_h(sib))).status_code == 409
        assert [i["id"] for i in await today_instances(client, kid, "mine")] == [inst["id"]]

    async def test_only_the_assignee_or_an_admin_can_claim_an_assigned_chore(self, client, admin, kids):
        # v0.29 let anyone claim a chore that was assigned to someone else.
        kid, sib = kids
        await make_chore(client, admin, assignment="assigned", assigned_to=kid["id"])
        [inst] = await today_instances(client, admin)
        assert (await client.post(f"/api/chores/instances/{inst['id']}/claim", headers=_h(sib))).status_code == 403
        assert (await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(sib))).status_code == 403
        assert (await client.post(f"/api/chores/instances/{inst['id']}/claim", headers=_h(kid))).status_code == 200

    async def test_unclaim_returns_it_to_the_pool(self, client, admin, kids):
        kid, sib = kids
        await make_chore(client, admin)
        [inst] = await today_instances(client, kid, "available")
        await client.post(f"/api/chores/instances/{inst['id']}/claim", headers=_h(kid))
        assert (await client.post(f"/api/chores/instances/{inst['id']}/unclaim", headers=_h(sib))).status_code == 403
        res = await client.post(f"/api/chores/instances/{inst['id']}/unclaim", headers=_h(kid))
        assert res.status_code == 200 and res.json()["status"] == "pending"

    async def test_viewers_cannot_claim_or_complete(self, client, admin):
        viewer = await _member(client, admin, name="Grandma", pin="1111", role="viewer")
        await make_chore(client, admin)
        [inst] = await today_instances(client, viewer)
        assert (await client.post(f"/api/chores/instances/{inst['id']}/claim", headers=_h(viewer))).status_code == 403
        assert (await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(viewer))).status_code == 403

    async def test_completing_credits_points_exactly_once(self, client, admin, kids, setup_db):
        # v0.29 never wrote to a ledger, so chores earned nothing.
        kid, _ = kids
        await make_chore(client, admin, assignment="assigned", assigned_to=kid["id"], points=7)
        [inst] = await today_instances(client, kid, "mine")
        res = await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))
        assert res.status_code == 200 and res.json()["status"] == "completed"
        assert (await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))).status_code == 409
        assert await balance(client, kid, kid["id"]) == 7
        entries = (await setup_db.execute(select(PointsEntry))).scalars().all()
        assert [(e.user_id, e.delta) for e in entries] == [(kid["id"], 7)]

    async def test_an_admin_completing_for_a_kid_credits_the_kid(self, client, admin, kids):
        kid, _ = kids
        await make_chore(client, admin, assignment="assigned", assigned_to=kid["id"], points=4)
        [inst] = await today_instances(client, admin)
        await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(admin))
        assert await balance(client, admin, kid["id"]) == 4
        assert await balance(client, admin, admin["id"]) == 0

    async def test_completing_an_unclaimed_open_chore_claims_it(self, client, admin, kids):
        kid, _ = kids
        await make_chore(client, admin, points=3)
        [inst] = await today_instances(client, kid, "available")
        res = await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))
        assert res.json()["claimed_by"] == kid["id"] and res.json()["completed_by"] == kid["id"]
        assert await balance(client, kid, kid["id"]) == 3

    async def test_undo_reverses_the_points_and_reopens(self, client, admin, kids, setup_db):
        kid, sib = kids
        await make_chore(client, admin, assignment="assigned", assigned_to=kid["id"], points=5)
        [inst] = await today_instances(client, kid, "mine")
        await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))
        assert (await client.post(f"/api/chores/instances/{inst['id']}/undo", headers=_h(sib))).status_code == 403
        res = await client.post(f"/api/chores/instances/{inst['id']}/undo", headers=_h(kid))
        assert res.status_code == 200 and res.json()["status"] == "pending"
        assert await balance(client, kid, kid["id"]) == 0
        # The ledger keeps both entries: append-only.
        assert sorted(e.delta for e in (await setup_db.execute(select(PointsEntry))).scalars()) == [-5, 5]
        # Completing again credits again (a new completion).
        await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))
        assert await balance(client, kid, kid["id"]) == 5
        assert (await client.post(f"/api/chores/instances/{inst['id']}/undo", headers=_h(admin))).status_code == 200
        assert (await client.post(f"/api/chores/instances/{inst['id']}/undo", headers=_h(admin))).status_code == 409

    async def test_the_ledger_refuses_a_second_credit_for_one_completion(self, setup_db):
        setup_db.add(PointsEntry(family_id="f", user_id="u", delta=5, source_type="chore", source_id="c1"))
        setup_db.add(PointsEntry(family_id="f", user_id="u", delta=5, source_type="chore", source_id="c1"))
        with pytest.raises(IntegrityError):
            await setup_db.flush()
        await setup_db.rollback()

    async def test_missed_chores_cannot_be_completed(self, client, admin, kids, setup_db):
        kid, _ = kids
        await make_chore(client, admin, assignment="assigned", assigned_to=kid["id"])
        [inst] = await today_instances(client, kid, "mine")
        row = await setup_db.get(ChoreInstance, inst["id"])
        row.status = "missed"
        await setup_db.flush()
        assert (await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))).status_code == 409

    async def test_unknown_or_foreign_instances_are_404(self, client, admin, setup_db):
        foreign = ChoreInstance(family_id="another-family", template_id="t", due_date=TODAY)
        setup_db.add(foreign)
        await setup_db.flush()
        for action in ("claim", "unclaim", "complete", "undo"):
            assert (await client.post(f"/api/chores/instances/{foreign.id}/{action}", headers=_h(admin))).status_code == 404
            assert (await client.post(f"/api/chores/instances/nope/{action}", headers=_h(admin))).status_code == 404
        assert all(i["id"] != foreign.id for i in await today_instances(client, admin))


class TestViews:
    async def test_by_user_counts(self, client, admin, kids):
        kid, sib = kids
        await make_chore(client, admin, title="Dishes", assignment="assigned", assigned_to=kid["id"])
        await make_chore(client, admin, title="Bins", assignment="assigned", assigned_to=kid["id"])
        await make_chore(client, admin, title="Laundry", assignment="assigned", assigned_to=sib["id"])
        await make_chore(client, admin, title="Anyone", assignment="claimable")
        mine = await today_instances(client, kid, "mine")
        await client.post(f"/api/chores/instances/{mine[0]['id']}/complete", headers=_h(kid))

        res = await client.get("/api/chores/by-user", headers=_h(admin))
        assert res.status_code == 200
        rows = {r["display_name"]: (r["pending"], r["completed"]) for r in res.json()}
        assert rows == {"Kid": (1, 1), "Sib": (1, 0), "Unassigned": (1, 0)}

    async def test_by_user_is_admin_only(self, client, admin, kids):
        kid, _ = kids
        assert (await client.get("/api/chores/by-user", headers=_h(kid))).status_code == 403

    async def test_stats_streak_and_privacy(self, client, admin, kids):
        kid, sib = kids
        await make_chore(client, admin, assignment="assigned", assigned_to=kid["id"], points=2)
        [inst] = await today_instances(client, kid, "mine")
        await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))
        stats = (await client.get("/api/chores/stats", headers=_h(kid))).json()
        assert stats == {"user_id": kid["id"], "completed_total": 1, "completed_this_week": 1,
                         "points_balance": 2, "streak_days": 1}
        assert (await client.get("/api/chores/stats", params={"user_id": kid["id"]}, headers=_h(sib))).status_code == 403

    async def test_family_points_and_log(self, client, admin, kids):
        kid, sib = kids
        await make_chore(client, admin, assignment="assigned", assigned_to=kid["id"], points=6)
        [inst] = await today_instances(client, kid, "mine")
        await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))
        points = {p["display_name"]: p["points"] for p in (await client.get("/api/chores/points", headers=_h(sib))).json()}
        assert points == {"Kid": 6, "Mom": 0, "Sib": 0}
        assert len((await client.get("/api/chores/log", headers=_h(kid))).json()) == 1
        assert (await client.get("/api/chores/log", headers=_h(sib))).json() == []  # others see only their own
        assert len((await client.get("/api/chores/log", headers=_h(admin))).json()) == 1

    async def test_date_range_query(self, client, admin):
        await make_chore(client, admin)
        end = (TODAY + timedelta(days=6)).isoformat()
        res = await client.get("/api/chores/instances", params={"start": TODAY.isoformat(), "end": end}, headers=_h(admin))
        assert len(res.json()) == 7
        bad = await client.get("/api/chores/instances", params={"start": end, "end": TODAY.isoformat()}, headers=_h(admin))
        assert bad.status_code == 400
