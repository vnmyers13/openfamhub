"""The family Notes board is bounded before it is persisted."""
import pytest

from app.schemas.notes import NoteBoardUpdate


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
