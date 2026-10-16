"""The family Notes board is bounded before it is persisted."""
import pytest

from app.models.media import Media
from app.schemas.notes import NoteBoardUpdate
from tests.test_phase2 import SETUP, _cookie, _h, _member


@pytest.fixture
async def admin(client):
    response = await client.post("/api/auth/setup", json=SETUP)
    assert response.status_code == 200, response.text
    return {"Cookie": _cookie(response), "id": response.json()["id"]}


def note_item() -> dict:
    return {"id": "note-1", "type": "note", "x": 10, "y": 10, "width": 200, "height": 100,
            "color": "#fef08a", "text": "Pack lunches"}


class TestNoteSceneValidation:
    def test_rejects_more_than_100_items(self):
        with pytest.raises(ValueError, match="100"):
            NoteBoardUpdate(title="Family notes", items=[note_item()] * 101)

    def test_rejects_a_stroke_with_more_than_500_points(self):
        with pytest.raises(ValueError, match="500"):
            NoteBoardUpdate(title="Family notes", items=[{
                "id": "stroke-1", "type": "stroke", "color": "#000000", "points": [{"x": 1, "y": 1}] * 501,
            }])


class TestNoteBoardApi:
    async def test_get_creates_an_empty_family_board(self, client, admin):
        response = await client.get("/api/notes/board", headers=_h(admin))

        assert response.status_code == 200, response.text
        assert response.json()["title"] == "Family notes"
        assert response.json()["items"] == []

    async def test_viewer_cannot_replace_the_board(self, client, admin):
        viewer = await _member(client, admin, name="Grandma", pin="1111", role="viewer")
        response = await client.put("/api/notes/board", json={"title": "Family notes", "items": []}, headers=_h(viewer))

        assert response.status_code == 403

    async def test_rejects_an_unready_media_reference(self, client, admin, db_session):
        media = Media(family_id="test-family", uploaded_by=admin["id"], kind="photo", status="processing", original_name="draft.jpg")
        db_session.add(media)
        await db_session.commit()
        response = await client.put("/api/notes/board", json={"title": "Family notes", "items": [{
            "id": "image-1", "type": "image", "x": 0, "y": 0, "width": 100, "height": 100, "media_id": media.id,
        }]}, headers=_h(admin))

        assert response.status_code == 422
