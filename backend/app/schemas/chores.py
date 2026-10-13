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


# ---- to-dos -----------------------------------------------------------------

class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    notes: Optional[str] = Field(None, max_length=4000)
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None

    @field_validator("title")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("title can't be blank")
        return v.strip()


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=256)
    notes: Optional[str] = Field(None, max_length=4000)
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None
    done: Optional[bool] = None


class TodoResponse(BaseModel):
    id: str
    title: str
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None
    done: bool
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


# ---- routines ---------------------------------------------------------------

class RoutineStepIn(BaseModel):
    id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=128)
    minutes: int = Field(5, ge=1, le=180)
    points: int = Field(0, ge=0, le=100000)


class _RoutineFields(BaseModel):
    assigned_to: Optional[str] = None
    start_time: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    repeat: Optional[Repeat] = None
    start_date: Optional[date] = None


class RoutineCreate(_RoutineFields):
    name: str = Field(..., min_length=1, max_length=128)
    steps: List[RoutineStepIn] = Field(..., min_length=1, max_length=20)


class RoutineUpdate(_RoutineFields):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    steps: Optional[List[RoutineStepIn]] = Field(None, min_length=1, max_length=20)


class RoutineStep(BaseModel):
    id: str
    title: str
    minutes: int
    points: int


class RoutineResponse(BaseModel):
    id: str
    name: str
    assigned_to: Optional[str] = None
    start_time: Optional[str] = None
    repeat: Optional[dict] = None
    start_date: date
    steps: List[RoutineStep]


class RoutineRunStep(BaseModel):
    instance_id: str
    template_id: str
    title: str
    minutes: int
    points: int
    status: str


class RoutineRun(BaseModel):
    """A routine as it runs today, for the app and the wall."""
    id: str
    name: str
    assigned_to: Optional[str] = None
    assigned_name: Optional[str] = None
    assigned_color: Optional[str] = None
    start_time: Optional[str] = None
    steps: List[RoutineRunStep]
