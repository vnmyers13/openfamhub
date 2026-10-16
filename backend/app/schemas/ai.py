from typing import Any, Literal

from pydantic import BaseModel, Field


class DraftRequest(BaseModel):
    request: str = Field(min_length=1, max_length=2000)


class DraftAction(BaseModel):
    kind: Literal["event", "chore", "todo"]
    operation: Literal["create", "update"]
    fields: dict[str, Any]
    target_id: str | None = None


class DraftResponse(BaseModel):
    action: DraftAction
    summary: str = Field(min_length=1, max_length=500)
