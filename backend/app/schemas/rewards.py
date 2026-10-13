from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

BadgeKind = Literal["streak_days", "chores_completed", "points_earned"]


def _name(v: Optional[str], limit: int) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    if not 1 <= len(v) <= limit:
        raise ValueError(f"name must be 1-{limit} characters")
    return v


# ---- catalog ----------------------------------------------------------------

class _RewardFields(BaseModel):
    description: Optional[str] = Field(None, max_length=1000)
    icon: Optional[str] = Field(None, max_length=16)
    needs_approval: Optional[bool] = None


class RewardCreate(_RewardFields):
    name: str
    point_cost: int = Field(..., ge=1, le=100000)
    needs_approval: bool = False

    @field_validator("name")
    @classmethod
    def name_length(cls, v):
        return _name(v, 128)


class RewardUpdate(_RewardFields):
    name: Optional[str] = None
    point_cost: Optional[int] = Field(None, ge=1, le=100000)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_length(cls, v):
        return _name(v, 128)


class RewardResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    icon: Optional[str]
    point_cost: int
    needs_approval: bool
    is_active: bool


# ---- redemptions --------------------------------------------------------------

class DecisionRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=256)


class RedemptionResponse(BaseModel):
    id: str
    reward_id: str
    user_id: str
    reward_name: str
    point_cost: int
    status: str
    note: Optional[str]
    requested_at: datetime
    decided_at: Optional[datetime]
    decided_by: Optional[str]


# ---- points -------------------------------------------------------------------

class PointsAdjust(BaseModel):
    user_id: str
    delta: int = Field(..., ge=-100000, le=100000)
    reason: str = Field(..., min_length=1, max_length=256)

    @field_validator("delta")
    @classmethod
    def not_zero(cls, v):
        if v == 0:
            raise ValueError("delta can't be 0")
        return v


class LedgerEntry(BaseModel):
    id: str
    delta: int
    reason: str
    source_type: str
    created_at: datetime


# ---- badges -------------------------------------------------------------------

class BadgeCreate(BaseModel):
    name: str
    description: Optional[str] = Field(None, max_length=256)
    icon: Optional[str] = Field(None, max_length=16)
    kind: BadgeKind
    threshold: int = Field(..., ge=1, le=100000)
    bonus_points: int = Field(0, ge=0, le=100000)

    @field_validator("name")
    @classmethod
    def name_length(cls, v):
        return _name(v, 64)


class BadgeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = Field(None, max_length=256)
    icon: Optional[str] = Field(None, max_length=16)
    kind: Optional[BadgeKind] = None
    threshold: Optional[int] = Field(None, ge=1, le=100000)
    bonus_points: Optional[int] = Field(None, ge=0, le=100000)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_length(cls, v):
        return _name(v, 64)


class BadgeResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    icon: Optional[str]
    kind: str
    threshold: int
    bonus_points: int
    is_active: bool


class EarnedBadge(BaseModel):
    id: str
    name: str
    icon: Optional[str]


class ProgressRow(BaseModel):
    user_id: str
    display_name: str
    color_hex: str
    avatar_value: Optional[str]
    points_balance: int
    points_this_week: int
    streak_days: int
    badges: List[EarnedBadge]


# ---- allowance ----------------------------------------------------------------

class AllowanceSet(BaseModel):
    weekly_cents: int = Field(..., ge=0, le=100000)


class AllowanceAdjust(BaseModel):
    delta_cents: int = Field(..., ge=-1000000, le=1000000)
    reason: str = Field(..., min_length=1, max_length=256)

    @field_validator("delta_cents")
    @classmethod
    def not_zero(cls, v):
        if v == 0:
            raise ValueError("delta_cents can't be 0")
        return v


class AllowanceRow(BaseModel):
    user_id: str
    display_name: str
    weekly_cents: int
    balance_cents: int
    next_payout: Optional[date]


class AllowanceEntryResponse(BaseModel):
    id: str
    delta_cents: int
    reason: str
    source_type: str
    week_start: Optional[date]
    created_at: datetime
