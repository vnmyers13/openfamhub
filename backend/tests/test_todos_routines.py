"""Phase 5: to-dos (one-off tasks) and routines (ordered steps on chore instances)."""
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models.chores import ChoreInstance, ChoreTemplate, PointsEntry, Todo
from app.services.chores import family_today
from tests.test_phase2 import SETUP, _cookie, _h, _member

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
async def kid(client, admin):
    return await _member(client, admin, name="Kid", pin="1357")


class TestTodos:
    async def test_create_list_complete_and_reopen(self, client, admin, kid, setup_db):
        res = await client.post("/api/todos", json={"title": "Buy a birthday card", "assigned_to": kid["id"],
                                                    "due_date": (TODAY + timedelta(days=2)).isoformat()}, headers=_h(kid))
        assert res.status_code == 201, res.text
        todo = res.json()
        assert todo["done"] is False and todo["created_by"] == kid["id"]
        assert [t["title"] for t in (await client.get("/api/todos", headers=_h(admin))).json()] == ["Buy a birthday card"]

        done = (await client.patch(f"/api/todos/{todo['id']}", json={"done": True}, headers=_h(admin))).json()
        assert done["done"] is True and done["completed_by"] == admin["id"]
        assert (await client.get("/api/todos", headers=_h(admin))).json() == []
        assert len((await client.get("/api/todos", params={"include_done": True}, headers=_h(admin))).json()) == 1
        reopened = (await client.patch(f"/api/todos/{todo['id']}", json={"done": False}, headers=_h(kid))).json()
        assert reopened["done"] is False and reopened["completed_by"] is None
        # To-dos never touch points.
        assert (await setup_db.execute(select(PointsEntry))).scalars().all() == []

    async def test_edit_fields_and_order_by_due_date(self, client, admin):
        a = (await client.post("/api/todos", json={"title": "No date"}, headers=_h(admin))).json()
        b = (await client.post("/api/todos", json={"title": "Soon", "due_date": TODAY.isoformat()}, headers=_h(admin))).json()
        res = await client.patch(f"/api/todos/{a['id']}", json={"title": "Renamed", "notes": "milk, eggs",
                                                                "due_date": None, "assigned_to": None}, headers=_h(admin))
        assert res.json()["title"] == "Renamed" and res.json()["notes"] == "milk, eggs"
        assert [t["id"] for t in (await client.get("/api/todos", headers=_h(admin))).json()] == [b["id"], a["id"]]

    async def test_family_scoped(self, client, admin, setup_db):
        foreign = Todo(family_id="another-family", title="Theirs")
        setup_db.add(foreign)
        await setup_db.flush()
        assert (await client.get("/api/todos", headers=_h(admin))).json() == []
        assert (await client.patch(f"/api/todos/{foreign.id}", json={"done": True}, headers=_h(admin))).status_code == 404
        assert (await client.delete(f"/api/todos/{foreign.id}", headers=_h(admin))).status_code == 404

    async def test_viewers_read_only_and_delete_rules(self, client, admin, kid):
        viewer = await _member(client, admin, name="Grandma", pin="1111", role="viewer")
        assert (await client.post("/api/todos", json={"title": "x"}, headers=_h(viewer))).status_code == 403
        mine = (await client.post("/api/todos", json={"title": "Mine"}, headers=_h(admin))).json()
        assert (await client.patch(f"/api/todos/{mine['id']}", json={"done": True}, headers=_h(viewer))).status_code == 403
        assert (await client.delete(f"/api/todos/{mine['id']}", headers=_h(kid))).status_code == 403
        assert (await client.delete(f"/api/todos/{mine['id']}", headers=_h(admin))).status_code == 200
        kids = (await client.post("/api/todos", json={"title": "Kid's"}, headers=_h(kid))).json()
        assert (await client.delete(f"/api/todos/{kids['id']}", headers=_h(kid))).status_code == 200

    @pytest.mark.parametrize("body", [{"title": ""}, {"title": "x" * 257}, {"title": "x", "due_date": "soon"}])
    async def test_validation(self, client, admin, body):
        assert (await client.post("/api/todos", json=body, headers=_h(admin))).status_code == 422

    async def test_assignee_must_be_in_the_family(self, client, admin):
        assert (await client.post("/api/todos", json={"title": "x", "assigned_to": "stranger"}, headers=_h(admin))).status_code == 400


MORNING = {
    "name": "Morning", "start_time": "07:00", "repeat": {"every": "day"},
    "steps": [{"title": "Get dressed", "minutes": 5, "points": 1},
              {"title": "Breakfast", "minutes": 15, "points": 1},
              {"title": "Brush teeth", "minutes": 3, "points": 2}],
}


async def make_routine(client, admin, kid, **over):
    body = {**MORNING, "assigned_to": kid["id"], **over}
    res = await client.post("/api/routines", json=body, headers=_h(admin))
    assert res.status_code == 201, res.text
    return res.json()


class TestRoutines:
    async def test_create_keeps_step_order(self, client, admin, kid):
        r = await make_routine(client, admin, kid)
        assert [s["title"] for s in r["steps"]] == ["Get dressed", "Breakfast", "Brush teeth"]
        assert [s["minutes"] for s in r["steps"]] == [5, 15, 3]
        listed = (await client.get("/api/routines", headers=_h(kid))).json()
        assert [x["id"] for x in listed] == [r["id"]]

    async def test_todays_run_lists_step_instances_in_order(self, client, admin, kid):
        await make_routine(client, admin, kid)
        [today] = (await client.get("/api/routines/today", headers=_h(kid))).json()
        assert today["name"] == "Morning" and today["start_time"] == "07:00" and today["assigned_to"] == kid["id"]
        assert [s["title"] for s in today["steps"]] == ["Get dressed", "Breakfast", "Brush teeth"]
        assert all(s["status"] == "pending" for s in today["steps"])

    async def test_steps_are_completed_as_chores_and_credit_the_assignee(self, client, admin, kid):
        await make_routine(client, admin, kid)
        [today] = (await client.get("/api/routines/today", headers=_h(kid))).json()
        step = today["steps"][2]
        res = await client.post(f"/api/chores/instances/{step['instance_id']}/complete", headers=_h(kid))
        assert res.status_code == 200
        stats = (await client.get("/api/chores/stats", headers=_h(kid))).json()
        assert stats["points_balance"] == 2
        [today] = (await client.get("/api/routines/today", headers=_h(kid))).json()
        assert [s["status"] for s in today["steps"]] == ["pending", "pending", "completed"]
        # Routine steps stay out of the plain chore lists.
        assert (await client.get("/api/chores/instances", headers=_h(kid))).json() == []
        assert (await client.get("/api/chores/templates", headers=_h(admin))).json() == []

    async def test_step_order_survives_edits(self, client, admin, kid):
        r = await make_routine(client, admin, kid)
        dressed, breakfast, teeth = r["steps"]
        [today] = (await client.get("/api/routines/today", headers=_h(kid))).json()
        await client.post(f"/api/chores/instances/{today['steps'][0]['instance_id']}/complete", headers=_h(kid))

        # Move teeth first, rename breakfast, drop "get dressed", add a new last step.
        res = await client.patch(f"/api/routines/{r['id']}", json={"steps": [
            {"id": teeth["id"], "title": "Brush teeth", "minutes": 3, "points": 2},
            {"id": breakfast["id"], "title": "Eat breakfast", "minutes": 20, "points": 1},
            {"title": "Pack bag", "minutes": 5, "points": 1},
        ]}, headers=_h(admin))
        assert res.status_code == 200, res.text
        edited = res.json()
        assert [s["title"] for s in edited["steps"]] == ["Brush teeth", "Eat breakfast", "Pack bag"]
        assert edited["steps"][0]["id"] == teeth["id"] and edited["steps"][1]["id"] == breakfast["id"]

        again = (await client.get("/api/routines", headers=_h(admin))).json()[0]
        assert [s["title"] for s in again["steps"]] == ["Brush teeth", "Eat breakfast", "Pack bag"]
        [today] = (await client.get("/api/routines/today", headers=_h(kid))).json()
        assert [s["title"] for s in today["steps"]] == ["Brush teeth", "Eat breakfast", "Pack bag"]
        # The step that was already done today keeps its history.
        log = (await client.get("/api/chores/log", headers=_h(admin))).json()
        assert [e["title"] for e in log] == ["Get dressed"]

    async def test_rename_and_reassign_without_touching_steps(self, client, admin, kid):
        r = await make_routine(client, admin, kid)
        res = await client.patch(f"/api/routines/{r['id']}", json={"name": "School mornings", "start_time": "06:45"},
                                 headers=_h(admin))
        assert res.json()["name"] == "School mornings" and len(res.json()["steps"]) == 3

    async def test_retire_a_routine(self, client, admin, kid):
        r = await make_routine(client, admin, kid)
        assert (await client.delete(f"/api/routines/{r['id']}", headers=_h(admin))).status_code == 200
        assert (await client.get("/api/routines", headers=_h(admin))).json() == []
        assert (await client.get("/api/routines/today", headers=_h(kid))).json() == []

    async def test_only_admins_manage_routines(self, client, admin, kid):
        assert (await client.post("/api/routines", json={**MORNING}, headers=_h(kid))).status_code == 403
        r = await make_routine(client, admin, kid)
        assert (await client.patch(f"/api/routines/{r['id']}", json={"name": "x"}, headers=_h(kid))).status_code == 403
        assert (await client.delete(f"/api/routines/{r['id']}", headers=_h(kid))).status_code == 403
        assert (await client.patch("/api/routines/nope", json={"name": "x"}, headers=_h(admin))).status_code == 404

    @pytest.mark.parametrize("over", [
        {"steps": []},
        {"steps": [{"title": f"s{i}", "minutes": 1} for i in range(21)]},
        {"start_time": "7am"},
        {"name": ""},
        {"steps": [{"title": "x", "minutes": 0}]},
        {"steps": [{"title": "x", "minutes": 181}]},
    ])
    async def test_validation(self, client, admin, kid, over):
        res = await client.post("/api/routines", json={**MORNING, "assigned_to": kid["id"], **over}, headers=_h(admin))
        assert res.status_code == 422

    async def test_a_step_id_from_another_routine_is_refused(self, client, admin, kid):
        a = await make_routine(client, admin, kid)
        b = await make_routine(client, admin, kid, name="Bedtime")
        res = await client.patch(f"/api/routines/{a['id']}", json={"steps": [
            {"id": b["steps"][0]["id"], "title": "Stolen", "minutes": 1}]}, headers=_h(admin))
        assert res.status_code == 400

    async def test_the_wall_reads_todays_routines_only_when_paired(self, client, admin, kid):
        await make_routine(client, admin, kid)
        assert (await client.get("/api/wall/routines")).status_code == 401
        device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
        pair = await client.post("/api/wall/pair", json={"token": device["token"]})
        wall = {"Cookie": _cookie(pair, "wall_token")}
        [routine] = (await client.get("/api/wall/routines", headers=wall)).json()
        assert routine["name"] == "Morning" and routine["assigned_name"] == "Kid"
        assert [s["title"] for s in routine["steps"]] == ["Get dressed", "Breakfast", "Brush teeth"]

    async def test_the_wall_completes_an_assigned_routine_step_and_credits_the_child(self, client, admin, kid):
        await make_routine(client, admin, kid)
        device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
        pair = await client.post("/api/wall/pair", json={"token": device["token"]})
        wall = {"Cookie": _cookie(pair, "wall_token")}
        [routine] = (await client.get("/api/wall/routines", headers=wall)).json()

        res = await client.post(f"/api/wall/routines/steps/{routine['steps'][0]['instance_id']}/complete", headers=wall)

        assert res.status_code == 200, res.text
        assert res.json()["status"] == "completed"
        assert res.json()["completed_by"] == kid["id"]
        stats = (await client.get("/api/chores/stats", headers=_h(kid))).json()
        assert stats["points_balance"] == 1
        [routine] = (await client.get("/api/wall/routines", headers=wall)).json()
        assert routine["steps"][0]["status"] == "completed"

    async def test_wall_routine_completion_is_idempotent(self, client, admin, kid, setup_db):
        await make_routine(client, admin, kid)
        device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
        pair = await client.post("/api/wall/pair", json={"token": device["token"]})
        wall = {"Cookie": _cookie(pair, "wall_token")}
        [routine] = (await client.get("/api/wall/routines", headers=wall)).json()
        step_id = routine["steps"][0]["instance_id"]

        assert (await client.post(f"/api/wall/routines/steps/{step_id}/complete", headers=wall)).status_code == 200
        second = await client.post(f"/api/wall/routines/steps/{step_id}/complete", headers=wall)

        assert second.status_code == 200, second.text
        assert second.json()["status"] == "completed"
        points = (await setup_db.execute(select(PointsEntry))).scalars().all()
        assert [(p.user_id, p.delta) for p in points] == [(kid["id"], 1)]

    async def test_wall_cannot_complete_plain_chores_or_foreign_steps(self, client, admin, kid, setup_db):
        plain = (await client.post("/api/chores/templates", json={
            "title": "Feed the cat", "points": 2, "assignment": "assigned", "assigned_to": kid["id"],
        }, headers=_h(admin))).json()
        [plain_inst] = (await client.get("/api/chores/instances", headers=_h(admin))).json()
        foreign_template = ChoreTemplate(
            family_id="another-family", title="Foreign step", points=1, assignment="assigned", assigned_to=kid["id"],
            repeat={"every": "day"}, start_date=TODAY, routine_id="foreign-routine", position=0, minutes=5,
        )
        setup_db.add(foreign_template)
        await setup_db.flush()
        foreign_inst = ChoreInstance(
            family_id="another-family", template_id=foreign_template.id, due_date=TODAY, assigned_to=kid["id"],
        )
        setup_db.add(foreign_inst)
        await setup_db.flush()
        device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
        pair = await client.post("/api/wall/pair", json={"token": device["token"]})
        wall = {"Cookie": _cookie(pair, "wall_token")}

        assert plain["title"] == "Feed the cat"
        assert (await client.post(f"/api/wall/routines/steps/{plain_inst['id']}/complete", headers=wall)).status_code == 404
        assert (await client.post(f"/api/wall/routines/steps/{foreign_inst.id}/complete", headers=wall)).status_code == 404

    async def test_wall_refuses_unassigned_routine_steps(self, client, admin, kid):
        await make_routine(client, admin, kid, assigned_to=None)
        device = (await client.post("/api/wall/devices", json={"name": "Kitchen"}, headers=_h(admin))).json()
        pair = await client.post("/api/wall/pair", json={"token": device["token"]})
        wall = {"Cookie": _cookie(pair, "wall_token")}
        [routine] = (await client.get("/api/wall/routines", headers=wall)).json()

        res = await client.post(f"/api/wall/routines/steps/{routine['steps'][0]['instance_id']}/complete", headers=wall)

        assert res.status_code == 403
        stats = (await client.get("/api/chores/stats", headers=_h(kid))).json()
        assert stats["points_balance"] == 0
