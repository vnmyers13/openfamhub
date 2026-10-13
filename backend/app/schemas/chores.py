from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Weekday = Literal["mo", "tu", "we", "th", "fr", "sa", "su"]


class Repeat(BaseModel):
    """How a chore repeats: every `interval` days, weeks (on `weekdays`, default
    the start date's weekday) or months (on `month_day`, 1-28, or -1 for the
    last day). "none" is a one-off on the start date."""

    every: Literal["none", "day", "week", "month"] = "none"
    interval: int = Field(1, ge=1, le=52)
    weekdays: Optional[List[Weekday]] = None
    month_day: Optional[int] = None

    @field_validator("month_day")
    @classmethod
    def valid_month_day(cls, v):
        if v is not None and not (1 <= v <= 28 or v == -1):
            raise ValueError("month_day is 1-28, or -1 for the last day of the month")
        return v


class _ChoreFields(BaseModel):
    description: Optional[str] = Field(None, max_length=2000)
    points: Optional[int] = Field(None, ge=0, le=100000)
    assignment: Optional[Literal["assigned", "claimable"]] = None
    assigned_to: Optional[str] = None
    repeat: Optional[Repeat] = None
    start_date: Optional[date] = None

    @field_validator("title", check_fields=False)
    @classmethod
    def title_length(cls, v):
        if v is not None and not 1 <= len(v.strip()) <= 128:
            raise ValueError("title must be 1-128 characters")
        return v.strip() if v is not None else v


class ChoreCreate(_ChoreFields):
    title: str
    points: int = Field(0, ge=0, le=100000)
    assignment: Literal["assigned", "claimable"] = "claimable"

    @model_validator(mode="after")
    def assignee_matches_mode(self):
        if self.assignment == "assigned" and not self.assigned_to:
            raise ValueError("an assigned chore needs assigned_to")
        if self.assignment == "claimable" and self.assigned_to:
            raise ValueError("a claimable chore has no assigned_to")
        return self


class ChoreUpdate(_ChoreFields):
    title: Optional[str] = None
    is_active: Optional[bool] = None


class ChoreTemplateResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    points: int
    assignment: str
    assigned_to: Optional[str] = None
    repeat: Optional[dict] = None
    start_date: date
    is_active: bool

    model_config = {"from_attributes": True}


class ChoreInstanceResponse(BaseModel):
    id: str
    template_id: str
    title: str
    points: int
    due_date: date
    status: str
    assigned_to: Optional[str] = None
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    completed_at: Optional[datetime] = None
    routine_id: Optional[str] = None


class ByUserRow(BaseModel):
    user_id: Optional[str] = None
    display_name: str
    pending: int
    completed: int
    missed: int


class ChoreStats(BaseModel):
    user_id: str
    completed_total: int
    completed_this_week: int
    points_balance: int
    streak_days: int


class PointsRow(BaseModel):
    user_id: str
    display_name: str
    points: int


class CompletionLogEntry(BaseModel):
    id: str
    instance_id: str
    title: str
    completed_by: str
    credited_to: Optional[str] = None
    points: int
    completed_at: datetime
    undone_at: Optional[datetime] = None
