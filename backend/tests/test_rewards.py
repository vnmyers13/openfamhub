"""Phase 6: rewards catalog, redemptions, badges, streaks, allowance and family progress.

The points ledger is the only source of balances: every test that moves points
also checks the balance against the sum of ledger rows.
"""
from contextlib import asynccontextmanager
from datetime import date as D, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.models.chores import ChoreCompletion, PointsEntry
from app.models.rewards import AllowanceEntry, AllowancePlan, UserBadge
from app.services import rewards as svc
from app.services.chores import family_today
from tests.test_phase2 import SETUP, _cookie, _h, _member

ZONE = ZoneInfo(SETUP["timezone"])
TODAY = family_today(SETUP["timezone"])


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
    return await _member(client, admin, name="Kid", pin="1357"), await _member(client, admin, name="Sib", pin="2468")


@pytest.fixture
async def viewer(client, admin):
    return await _member(client, admin, name="Grandma", pin="9999", role="viewer")


async def family_id(setup_db):
    from app.models.family import Family

    return (await setup_db.execute(select(Family.id))).scalar_one()


async def ledger_sum(setup_db, user_id):
    return (await setup_db.execute(
        select(func.coalesce(func.sum(PointsEntry.delta), 0)).where(PointsEntry.user_id == user_id)
    )).scalar()


async def give_points(client, admin, user_id, delta, reason="Starting points"):
    res = await client.post("/api/rewards/points/adjust", json={"user_id": user_id, "delta": delta, "reason": reason},
                            headers=_h(admin))
    assert res.status_code == 201, res.text
    return res.json()


async def progress_of(client, who, user_id):
    res = await client.get("/api/rewards/progress", headers=_h(who))
    assert res.status_code == 200, res.text
    return next(r for r in res.json() if r["user_id"] == user_id)


async def make_reward(client, admin, **body):
    payload = {"name": "Movie night pick", "icon": "🎬", "point_cost": 30, "needs_approval": False}
    payload.update(body)
    res = await client.post("/api/rewards/catalog", json=payload, headers=_h(admin))
    assert res.status_code == 201, res.text
    return res.json()


async def redeem(client, who, reward_id, expect=201):
    res = await client.post(f"/api/rewards/catalog/{reward_id}/redeem", headers=_h(who))
    assert res.status_code == expect, res.text
    return res.json()


async def complete_new_chore(client, admin, kid, points=5, title="Feed the cat"):
    tpl = await client.post("/api/chores/templates", headers=_h(admin), json={
        "title": title, "points": points, "assignment": "assigned", "assigned_to": kid["id"], "repeat": None})
    assert tpl.status_code == 201, tpl.text
    insts = (await client.get("/api/chores/instances", params={"scope": "mine"}, headers=_h(kid))).json()
    inst = next(i for i in insts if i["template_id"] == tpl.json()["id"])
    res = await client.post(f"/api/chores/instances/{inst['id']}/complete", headers=_h(kid))
    assert res.status_code == 200, res.text
    return inst["id"]


def local_noon_utc(day: D) -> datetime:
    return datetime.combine(day, time(12), ZONE).astimezone(timezone.utc)


async def seed_completions(setup_db, fid, user_id, days):
    for i, day in enumerate(days):
        setup_db.add(ChoreCompletion(family_id=fid, instance_id=f"seed-{i}-{day}", completed_by=user_id,
                                     credited_to=user_id, points=0, completed_at=local_noon_utc(day)))
    await setup_db.flush()


# ---- catalog ----------------------------------------------------------------

class TestCatalog:
    async def test_admin_manages_the_catalog_and_members_see_active_rewards(self, client, admin, kids):
        kid, _ = kids
        reward = await make_reward(client, admin)
        assert reward["point_cost"] == 30 and reward["icon"] == "🎬" and reward["is_active"] is True
        listed = (await client.get("/api/rewards/catalog", headers=_h(kid))).json()
        assert [r["id"] for r in listed] == [reward["id"]]

        res = await client.patch(f"/api/rewards/catalog/{reward['id']}", json={"point_cost": 40}, headers=_h(admin))
        assert res.status_code == 200 and res.json()["point_cost"] == 40
        assert (await client.delete(f"/api/rewards/catalog/{reward['id']}", headers=_h(admin))).status_code == 200
        assert (await client.get("/api/rewards/catalog", headers=_h(kid))).json() == []
        everything = (await client.get("/api/rewards/catalog", params={"include_inactive": True}, headers=_h(admin))).json()
        assert [r["is_active"] for r in everything] == [False]

    async def test_only_admins_change_the_catalog(self, client, admin, kids):
        kid, _ = kids
        res = await client.post("/api/rewards/catalog", json={"name": "Free stuff", "point_cost": 1}, headers=_h(kid))
        assert res.status_code == 403
        reward = await make_reward(client, admin)
        assert (await client.patch(f"/api/rewards/catalog/{reward['id']}", json={"point_cost": 1}, headers=_h(kid))).status_code == 403
        assert (await client.delete(f"/api/rewards/catalog/{reward['id']}", headers=_h(kid))).status_code == 403

    async def test_costs_must_be_positive(self, client, admin):
        res = await client.post("/api/rewards/catalog", json={"name": "Odd", "point_cost": 0}, headers=_h(admin))
        assert res.status_code == 422


# ---- redemptions --------------------------------------------------------------

class TestRedeem:
    async def test_buying_an_instant_reward_takes_the_points_once(self, client, admin, kids, setup_db):
        kid, _ = kids
        await give_points(client, admin, kid["id"], 50)
        reward = await make_reward(client, admin)
        red = await redeem(client, kid, reward["id"])
        assert red["status"] == "approved" and red["point_cost"] == 30 and red["reward_name"] == "Movie night pick"
        assert (await progress_of(client, kid, kid["id"]))["points_balance"] == 20
        assert await ledger_sum(setup_db, kid["id"]) == 20

    async def test_not_enough_points_is_refused_and_nothing_is_written(self, client, admin, kids, setup_db):
        kid, _ = kids
        await give_points(client, admin, kid["id"], 10)
        reward = await make_reward(client, admin)
        res = await client.post(f"/api/rewards/catalog/{reward['id']}/redeem", headers=_h(kid))
        assert res.status_code == 409 and "points" in res.json()["detail"]
        assert await ledger_sum(setup_db, kid["id"]) == 10
        assert (await client.get("/api/rewards/redemptions", headers=_h(kid))).json() == []

    async def test_a_request_holds_the_points_until_approved(self, client, admin, kids, setup_db):
        kid, _ = kids
        await give_points(client, admin, kid["id"], 50)
        reward = await make_reward(client, admin, name="Trip to the zoo", point_cost=40, needs_approval=True)
        red = await redeem(client, kid, reward["id"])
        assert red["status"] == "pending"
        assert (await progress_of(client, kid, kid["id"]))["points_balance"] == 10  # held
        res = await client.post(f"/api/rewards/redemptions/{red['id']}/approve", headers=_h(admin))
        assert res.status_code == 200 and res.json()["status"] == "approved"
        assert res.json()["decided_by"] == admin["id"]
        assert await ledger_sum(setup_db, kid["id"]) == 10
        # A second decision is refused and moves no points.
        assert (await client.post(f"/api/rewards/redemptions/{red['id']}/approve", headers=_h(admin))).status_code == 409
        assert (await client.post(f"/api/rewards/redemptions/{red['id']}/reject", json={}, headers=_h(admin))).status_code == 409
        assert await ledger_sum(setup_db, kid["id"]) == 10

    async def test_rejecting_refunds_exactly_once(self, client, admin, kids, setup_db):
        kid, _ = kids
        await give_points(client, admin, kid["id"], 50)
        reward = await make_reward(client, admin, point_cost=40, needs_approval=True)
        red = await redeem(client, kid, reward["id"])
        res = await client.post(f"/api/rewards/redemptions/{red['id']}/reject", json={"note": "Not this week"}, headers=_h(admin))
        assert res.status_code == 200 and res.json()["status"] == "rejected" and res.json()["note"] == "Not this week"
        assert await ledger_sum(setup_db, kid["id"]) == 50
        assert (await client.post(f"/api/rewards/redemptions/{red['id']}/reject", json={}, headers=_h(admin))).status_code == 409
        assert (await client.post(f"/api/rewards/redemptions/{red['id']}/approve", headers=_h(admin))).status_code == 409
        assert await ledger_sum(setup_db, kid["id"]) == 50
        refunds = (await setup_db.execute(select(PointsEntry).where(PointsEntry.source_type == "reward_refund"))).scalars().all()
        assert [r.delta for r in refunds] == [40]

    async def test_the_requester_can_cancel_a_pending_request(self, client, admin, kids, setup_db):
        kid, sib = kids
        await give_points(client, admin, kid["id"], 50)
        reward = await make_reward(client, admin, point_cost=40, needs_approval=True)
        red = await redeem(client, kid, reward["id"])
        assert (await client.post(f"/api/rewards/redemptions/{red['id']}/cancel", headers=_h(sib))).status_code == 404
        res = await client.post(f"/api/rewards/redemptions/{red['id']}/cancel", headers=_h(kid))
        assert res.status_code == 200 and res.json()["status"] == "cancelled"
        assert await ledger_sum(setup_db, kid["id"]) == 50
        assert (await client.post(f"/api/rewards/redemptions/{red['id']}/cancel", headers=_h(kid))).status_code == 409

    async def test_members_approve_nothing_and_viewers_redeem_nothing(self, client, admin, kids, viewer):
        kid, _ = kids
        await give_points(client, admin, kid["id"], 50)
        reward = await make_reward(client, admin, needs_approval=True)
        red = await redeem(client, kid, reward["id"])
        assert (await client.post(f"/api/rewards/redemptions/{red['id']}/approve", headers=_h(kid))).status_code == 403
        assert (await client.post(f"/api/rewards/catalog/{reward['id']}/redeem", headers=_h(viewer))).status_code == 403

    async def test_inactive_rewards_cant_be_redeemed(self, client, admin, kids):
        kid, _ = kids
        await give_points(client, admin, kid["id"], 50)
        reward = await make_reward(client, admin)
        await client.delete(f"/api/rewards/catalog/{reward['id']}", headers=_h(admin))
        assert (await client.post(f"/api/rewards/catalog/{reward['id']}/redeem", headers=_h(kid))).status_code == 404

    async def test_members_see_their_own_requests_and_admins_see_everyones(self, client, admin, kids):
        kid, sib = kids
        for who in (kid, sib):
            await give_points(client, admin, who["id"], 50)
        reward = await make_reward(client, admin, point_cost=10, needs_approval=True)
        await redeem(client, kid, reward["id"])
        await redeem(client, sib, reward["id"])
        mine = (await client.get("/api/rewards/redemptions", headers=_h(kid))).json()
        assert [r["user_id"] for r in mine] == [kid["id"]]
        everyone = (await client.get("/api/rewards/redemptions", params={"status": "pending"}, headers=_h(admin))).json()
        assert sorted(r["user_id"] for r in everyone) == sorted([kid["id"], sib["id"]])


# ---- points -------------------------------------------------------------------

class TestPoints:
    async def test_admins_adjust_points_with_a_reason_and_history_shows_it(self, client, admin, kids, setup_db):
        kid, _ = kids
        await give_points(client, admin, kid["id"], 25, reason="Helped with groceries")
        await give_points(client, admin, kid["id"], -5, reason="Correction")
        history = (await client.get("/api/rewards/points/history", headers=_h(kid))).json()
        assert [(h["delta"], h["reason"]) for h in history] == [(-5, "Correction"), (25, "Helped with groceries")]
        assert (await progress_of(client, kid, kid["id"]))["points_balance"] == 20 == await ledger_sum(setup_db, kid["id"])

    async def test_members_cant_adjust_or_read_other_peoples_history(self, client, admin, kids):
        kid, sib = kids
        res = await client.post("/api/rewards/points/adjust", json={"user_id": kid["id"], "delta": 99, "reason": "x"}, headers=_h(kid))
        assert res.status_code == 403
        assert (await client.get("/api/rewards/points/history", params={"user_id": sib["id"]}, headers=_h(kid))).status_code == 403
        assert (await client.get("/api/rewards/points/history", params={"user_id": sib["id"]}, headers=_h(admin))).status_code == 200

    async def test_a_zero_adjustment_is_refused(self, client, admin, kids):
        kid, _ = kids
        res = await client.post("/api/rewards/points/adjust", json={"user_id": kid["id"], "delta": 0, "reason": "x"}, headers=_h(admin))
        assert res.status_code == 422


# ---- streaks and badges -------------------------------------------------------

class TestStreaks:
    async def test_a_streak_carries_across_the_week_boundary(self, setup_db, client, admin, kids):
        kid, _ = kids
        fid = await family_id(setup_db)
        monday = D(2026, 10, 19)
        await seed_completions(setup_db, fid, kid["id"], [monday - timedelta(days=2), monday - timedelta(days=1), monday])
        assert await svc.streak_days(setup_db, fid, kid["id"], ZONE, today=monday) == 3

    async def test_a_streak_survives_until_the_end_of_today(self, setup_db, client, admin, kids):
        kid, _ = kids
        fid = await family_id(setup_db)
        tue = D(2026, 10, 20)
        await seed_completions(setup_db, fid, kid["id"], [tue - timedelta(days=2), tue - timedelta(days=1)])
        assert await svc.streak_days(setup_db, fid, kid["id"], ZONE, today=tue) == 2  # nothing yet today
        assert await svc.streak_days(setup_db, fid, kid["id"], ZONE, today=tue + timedelta(days=1)) == 0

    async def test_completions_count_on_the_familys_local_day(self, setup_db, client, admin, kids):
        kid, _ = kids
        fid = await family_id(setup_db)
        # 23:30 local on Sunday is already Monday in UTC; it still counts for Sunday.
        sunday_late = datetime.combine(D(2026, 10, 18), time(23, 30), ZONE).astimezone(timezone.utc)
        setup_db.add(ChoreCompletion(family_id=fid, instance_id="late", completed_by=kid["id"], credited_to=kid["id"],
                                     points=0, completed_at=sunday_late))
        await seed_completions(setup_db, fid, kid["id"], [D(2026, 10, 17)])
        assert await svc.streak_days(setup_db, fid, kid["id"], ZONE, today=D(2026, 10, 18)) == 2

    async def test_points_this_week_restart_on_monday(self, setup_db, client, admin, kids):
        kid, _ = kids
        fid = await family_id(setup_db)
        monday = D(2026, 10, 19)
        sunday = datetime.combine(monday - timedelta(days=1), time(20), ZONE).astimezone(timezone.utc)
        tuesday = datetime.combine(monday + timedelta(days=1), time(8), ZONE).astimezone(timezone.utc)
        setup_db.add(PointsEntry(family_id=fid, user_id=kid["id"], delta=7, reason="old", source_type="chore",
                                 source_id="c1", created_at=sunday))
        setup_db.add(PointsEntry(family_id=fid, user_id=kid["id"], delta=5, reason="new", source_type="chore",
                                 source_id="c2", created_at=tuesday))
        setup_db.add(PointsEntry(family_id=fid, user_id=kid["id"], delta=-3, reason="spent", source_type="reward",
                                 source_id="r1", created_at=tuesday))
        await setup_db.flush()
        rows = await svc.progress(setup_db, fid, today=monday + timedelta(days=1))
        row = next(r for r in rows if r.user_id == kid["id"])
        assert row.points_this_week == 5  # earned since Monday; spending doesn't count
        assert row.points_balance == 9


class TestBadges:
    async def make_badge(self, client, admin, **body):
        payload = {"name": "Helper", "icon": "🏅", "kind": "chores_completed", "threshold": 2, "bonus_points": 10}
        payload.update(body)
        res = await client.post("/api/rewards/badges", json=payload, headers=_h(admin))
        assert res.status_code == 201, res.text
        return res.json()

    async def test_a_badge_is_awarded_once_with_its_bonus(self, client, admin, kids, setup_db):
        kid, _ = kids
        badge = await self.make_badge(client, admin)
        await complete_new_chore(client, admin, kid, title="One")
        assert (await progress_of(client, kid, kid["id"]))["badges"] == []
        await complete_new_chore(client, admin, kid, title="Two")
        await complete_new_chore(client, admin, kid, title="Three")
        row = await progress_of(client, kid, kid["id"])
        assert [b["id"] for b in row["badges"]] == [badge["id"]]
        assert row["points_balance"] == 3 * 5 + 10 == await ledger_sum(setup_db, kid["id"])
        earned = (await setup_db.execute(select(UserBadge))).scalars().all()
        assert len(earned) == 1

    async def test_undo_and_redo_doesnt_award_twice(self, client, admin, kids, setup_db):
        kid, _ = kids
        await self.make_badge(client, admin, threshold=1, bonus_points=4)
        inst = await complete_new_chore(client, admin, kid)
        assert (await client.post(f"/api/chores/instances/{inst}/undo", headers=_h(kid))).status_code == 200
        assert (await client.post(f"/api/chores/instances/{inst}/complete", headers=_h(kid))).status_code == 200
        assert await ledger_sum(setup_db, kid["id"]) == 5 + 4
        assert len((await setup_db.execute(select(UserBadge))).scalars().all()) == 1

    async def test_a_new_badge_goes_to_people_who_already_qualify(self, client, admin, kids):
        kid, sib = kids
        await complete_new_chore(client, admin, kid, points=30)
        await self.make_badge(client, admin, kind="points_earned", threshold=25, bonus_points=0)
        assert len((await progress_of(client, kid, kid["id"]))["badges"]) == 1
        assert (await progress_of(client, kid, sib["id"]))["badges"] == []

    async def test_streak_badges_use_the_family_day(self, client, admin, kids, setup_db):
        kid, _ = kids
        fid = await family_id(setup_db)
        await seed_completions(setup_db, fid, kid["id"], [TODAY - timedelta(days=2), TODAY - timedelta(days=1)])
        await self.make_badge(client, admin, name="On a roll", kind="streak_days", threshold=3, bonus_points=0)
        assert (await progress_of(client, kid, kid["id"]))["badges"] == []
        await complete_new_chore(client, admin, kid)
        row = await progress_of(client, kid, kid["id"])
        assert row["streak_days"] == 3 and [b["name"] for b in row["badges"]] == ["On a roll"]

    async def test_only_admins_define_badges_and_retiring_one_keeps_what_was_earned(self, client, admin, kids):
        kid, _ = kids
        res = await client.post("/api/rewards/badges", json={"name": "x", "kind": "chores_completed", "threshold": 1}, headers=_h(kid))
        assert res.status_code == 403
        badge = await self.make_badge(client, admin, threshold=1, bonus_points=0)
        await complete_new_chore(client, admin, kid)
        assert (await client.delete(f"/api/rewards/badges/{badge['id']}", headers=_h(admin))).status_code == 200
        assert (await client.get("/api/rewards/badges", headers=_h(kid))).json() == []
        assert len((await progress_of(client, kid, kid["id"]))["badges"]) == 1

    async def test_unknown_badge_kinds_are_refused(self, client, admin):
        res = await client.post("/api/rewards/badges", json={"name": "x", "kind": "vibes", "threshold": 1}, headers=_h(admin))
        assert res.status_code == 422


# ---- allowance ------------------------------------------------------------------

def at_local(day: D, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), ZONE).astimezone(timezone.utc)


class TestAllowanceWeeks:
    def test_the_first_payout_is_the_next_monday_morning(self):
        wed = datetime.combine(D(2026, 10, 14), time(9), ZONE)
        assert svc.first_payout_week(wed) == D(2026, 10, 19)
        early_monday = datetime.combine(D(2026, 10, 19), time(6, 59), ZONE)
        assert svc.first_payout_week(early_monday) == D(2026, 10, 19)
        monday_after = datetime.combine(D(2026, 10, 19), time(7), ZONE)
        assert svc.first_payout_week(monday_after) == D(2026, 10, 26)

    def test_the_due_week_follows_monday_at_seven_local(self):
        assert svc.payout_week_due(datetime.combine(D(2026, 10, 19), time(6, 59), ZONE)) == D(2026, 10, 12)
        assert svc.payout_week_due(datetime.combine(D(2026, 10, 19), time(7), ZONE)) == D(2026, 10, 19)
        assert svc.payout_week_due(datetime.combine(D(2026, 10, 25), time(23), ZONE)) == D(2026, 10, 19)


class TestAllowance:
    @pytest.fixture
    def job(self, setup_db, monkeypatch):
        from app.jobs import allowance

        @asynccontextmanager
        async def shared_session():
            yield setup_db

        monkeypatch.setattr(allowance, "session_factory", shared_session)
        return allowance.run_allowance

    async def plan(self, client, admin, setup_db, user_id, cents, start=D(2026, 10, 19)):
        res = await client.put(f"/api/rewards/allowance/{user_id}", json={"weekly_cents": cents}, headers=_h(admin))
        assert res.status_code == 200, res.text
        row = (await setup_db.execute(select(AllowancePlan).where(AllowancePlan.user_id == user_id))).scalar_one()
        row.start_week = start  # pin the first payout week so the test doesn't depend on today
        await setup_db.flush()
        return res.json()

    async def entries(self, setup_db, user_id):
        rows = (await setup_db.execute(
            select(AllowanceEntry).where(AllowanceEntry.user_id == user_id).order_by(AllowanceEntry.week_start)
        )).scalars().all()
        return [(r.week_start, r.delta_cents) for r in rows]

    async def test_pays_once_per_week_from_monday_seven(self, client, admin, kids, setup_db, job):
        kid, _ = kids
        await self.plan(client, admin, setup_db, kid["id"], 500)
        assert await job(now=at_local(D(2026, 10, 19), 6, 59)) == 0
        assert await job(now=at_local(D(2026, 10, 19), 7, 5)) == 1
        assert await job(now=at_local(D(2026, 10, 19), 8)) == 0
        assert await job(now=at_local(D(2026, 10, 22), 12)) == 0
        assert await self.entries(setup_db, kid["id"]) == [(D(2026, 10, 19), 500)]

    async def test_missed_mondays_are_caught_up_on_the_next_run(self, client, admin, kids, setup_db, job):
        kid, _ = kids
        await self.plan(client, admin, setup_db, kid["id"], 250)
        # The server was off for two Mondays; Wednesday's run pays all three weeks once.
        assert await job(now=at_local(D(2026, 11, 4), 10)) == 3
        assert await self.entries(setup_db, kid["id"]) == [
            (D(2026, 10, 19), 250), (D(2026, 10, 26), 250), (D(2026, 11, 2), 250)]
        assert await job(now=at_local(D(2026, 11, 4), 11)) == 0

    async def test_catch_up_is_capped(self, client, admin, kids, setup_db, job):
        kid, _ = kids
        await self.plan(client, admin, setup_db, kid["id"], 100, start=D(2026, 1, 5))
        assert await job(now=at_local(D(2026, 10, 19), 8)) == svc.CATCH_UP_WEEKS

    async def test_monday_seven_is_local_time_across_dst(self, client, admin, kids, setup_db, job):
        kid, _ = kids
        await self.plan(client, admin, setup_db, kid["id"], 100, start=D(2026, 11, 2))
        # DST ended on Sunday 1 Nov: 11:30 UTC is 06:30 EST, still too early.
        assert await job(now=datetime(2026, 11, 2, 11, 30, tzinfo=timezone.utc)) == 0
        assert await job(now=datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)) == 1

    async def test_no_plan_or_zero_pays_nothing(self, client, admin, kids, setup_db, job):
        kid, sib = kids
        await self.plan(client, admin, setup_db, kid["id"], 0)
        assert await job(now=at_local(D(2026, 10, 26), 8)) == 0

    async def test_payouts_and_balances_are_whole_cents(self, client, admin, kids, setup_db, job):
        kid, _ = kids
        await self.plan(client, admin, setup_db, kid["id"], 375)
        await job(now=at_local(D(2026, 10, 26), 8))
        res = await client.post(f"/api/rewards/allowance/{kid['id']}/adjust",
                                json={"delta_cents": -500, "reason": "Paid in cash"}, headers=_h(admin))
        assert res.status_code == 201, res.text
        mine = (await client.get("/api/rewards/allowance", headers=_h(kid))).json()
        assert mine == [{"user_id": kid["id"], "display_name": "Kid", "weekly_cents": 375, "balance_cents": 250,
                         "next_payout": mine[0]["next_payout"]}]
        history = (await client.get(f"/api/rewards/allowance/{kid['id']}/history", headers=_h(kid))).json()
        assert [h["delta_cents"] for h in history] == [-500, 375, 375]

    async def test_only_admins_set_or_adjust_allowance(self, client, admin, kids):
        kid, sib = kids
        assert (await client.put(f"/api/rewards/allowance/{kid['id']}", json={"weekly_cents": 9999}, headers=_h(kid))).status_code == 403
        res = await client.post(f"/api/rewards/allowance/{kid['id']}/adjust", json={"delta_cents": 100, "reason": "x"}, headers=_h(kid))
        assert res.status_code == 403
        assert (await client.get(f"/api/rewards/allowance/{sib['id']}/history", headers=_h(kid))).status_code == 403
        everyone = (await client.get("/api/rewards/allowance", headers=_h(admin))).json()
        assert {r["display_name"] for r in everyone} >= {"Kid", "Sib"}

    async def test_a_new_plan_starts_at_the_next_payout(self, client, admin, kids, setup_db):
        kid, _ = kids
        res = await client.put(f"/api/rewards/allowance/{kid['id']}", json={"weekly_cents": 300}, headers=_h(admin))
        expected = svc.first_payout_week(datetime.now(ZONE))
        assert res.json()["next_payout"] == expected.isoformat()

    async def test_negative_amounts_are_refused(self, client, admin, kids):
        kid, _ = kids
        assert (await client.put(f"/api/rewards/allowance/{kid['id']}", json={"weekly_cents": -1}, headers=_h(admin))).status_code == 422

    def test_registered_hourly_and_at_startup(self):
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        from app.jobs.allowance import register_allowance_job

        scheduler = AsyncIOScheduler(timezone="UTC")
        register_allowance_job(scheduler)
        job = scheduler.get_job("allowance")
        assert job is not None and job.next_run_time is not None


# ---- progress -------------------------------------------------------------------

class TestProgress:
    async def test_everyone_but_viewers_appears_with_ledger_totals(self, client, admin, kids, viewer, setup_db):
        kid, sib = kids
        await give_points(client, admin, kid["id"], 12)
        await complete_new_chore(client, admin, sib, points=3)
        rows = (await client.get("/api/rewards/progress", headers=_h(viewer))).json()
        names = [r["display_name"] for r in rows]
        assert "Grandma" not in names and {"Mom", "Kid", "Sib"} <= set(names)
        for r in rows:
            assert r["points_balance"] == await ledger_sum(setup_db, r["user_id"])
        sib_row = next(r for r in rows if r["user_id"] == sib["id"])
        assert sib_row["points_this_week"] == 3 and sib_row["streak_days"] == 1

    async def test_the_wall_reads_progress_only_when_paired(self, client, admin, kids):
        kid, _ = kids
        await give_points(client, admin, kid["id"], 8)
        assert (await client.get("/api/wall/progress")).status_code == 401
        device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
        pair = await client.post("/api/wall/pair", json={"token": device["token"]})
        wall = {"Cookie": _cookie(pair, "wall_token")}
        rows = (await client.get("/api/wall/progress", headers=wall)).json()
        assert next(r for r in rows if r["user_id"] == kid["id"])["points_balance"] == 8


class TestEdgeCases:
    async def test_lowering_a_badge_threshold_awards_it_to_people_who_now_qualify(self, client, admin, kids):
        kid, _ = kids
        await complete_new_chore(client, admin, kid)
        res = await client.post("/api/rewards/badges", headers=_h(admin),
                                json={"name": "Starter", "kind": "chores_completed", "threshold": 5})
        badge = res.json()
        assert (await progress_of(client, kid, kid["id"]))["badges"] == []
        res = await client.patch(f"/api/rewards/badges/{badge['id']}", json={"threshold": 1, "icon": "⭐"}, headers=_h(admin))
        assert res.status_code == 200 and res.json()["threshold"] == 1 and res.json()["icon"] == "⭐"
        assert [b["icon"] for b in (await progress_of(client, kid, kid["id"]))["badges"]] == ["⭐"]

    async def test_unknown_ids_are_not_found(self, client, admin, kids):
        kid, _ = kids
        assert (await client.patch("/api/rewards/catalog/nope", json={"point_cost": 5}, headers=_h(admin))).status_code == 404
        assert (await client.post("/api/rewards/catalog/nope/redeem", headers=_h(kid))).status_code == 404
        assert (await client.post("/api/rewards/redemptions/nope/approve", headers=_h(admin))).status_code == 404
        assert (await client.patch("/api/rewards/badges/nope", json={"threshold": 2}, headers=_h(admin))).status_code == 404
        res = await client.post("/api/rewards/points/adjust", json={"user_id": "nope", "delta": 5, "reason": "x"}, headers=_h(admin))
        assert res.status_code == 400

    async def test_editing_a_reward_keeps_fields_that_werent_sent(self, client, admin):
        reward = await make_reward(client, admin, needs_approval=True)
        res = await client.patch(f"/api/rewards/catalog/{reward['id']}", json={"name": "Pick the movie", "needs_approval": None},
                                 headers=_h(admin))
        assert res.json()["name"] == "Pick the movie" and res.json()["needs_approval"] is True and res.json()["point_cost"] == 30

    async def test_restarting_a_stopped_allowance_doesnt_back_pay(self, client, admin, kids, setup_db):
        kid, _ = kids
        await client.put(f"/api/rewards/allowance/{kid['id']}", json={"weekly_cents": 200}, headers=_h(admin))
        plan = (await setup_db.execute(select(AllowancePlan))).scalar_one()
        plan.start_week = D(2026, 1, 5)
        await setup_db.flush()
        await client.put(f"/api/rewards/allowance/{kid['id']}", json={"weekly_cents": 0}, headers=_h(admin))
        res = await client.put(f"/api/rewards/allowance/{kid['id']}", json={"weekly_cents": 300}, headers=_h(admin))
        assert res.json()["next_payout"] == svc.first_payout_week(datetime.now(ZONE)).isoformat()
        assert plan.start_week == svc.first_payout_week(datetime.now(ZONE))
