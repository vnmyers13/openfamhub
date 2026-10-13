"""Phase 6: rewards, badges and allowance.

Points live only in the Phase 5 `points_ledger`; nothing here stores a points
balance. Allowance is money, so it has its own append-only ledger in whole
cents (v0.29 stored it as strings).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


def _id() -> str:
    return str(uuid.uuid4())


class Reward(Base):
    """Something a member can spend points on. Rewards are retired, never deleted,
    so past redemptions keep making sense."""

    __tablename__ = "rewards"
    __table_args__ = (Index("ix_rewards_family", "family_id", "is_active"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(16), nullable=True)
    point_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    needs_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


class Redemption(Base):
    """One purchase or request. Points are taken when it's made (so a pending
    request can't be spent twice) and refunded if it's rejected or cancelled.
    Name and cost are copied so later catalog edits don't rewrite history."""

    __tablename__ = "reward_redemptions"
    __table_args__ = (Index("ix_redemptions_family", "family_id", "status"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    reward_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    reward_name: Mapped[str] = mapped_column(String(128), nullable=False)
    point_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # pending|approved|rejected|cancelled
    note: Mapped[str] = mapped_column(String(256), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    decided_by: Mapped[str] = mapped_column(String, nullable=True)


class BadgeDefinition(Base):
    """A badge and what earns it: a streak of days, a number of chores, or
    lifetime chore points. Retired (not deleted) so earned badges keep their name."""

    __tablename__ = "badge_definitions"
    __table_args__ = (Index("ix_badges_family", "family_id", "is_active"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=True)
    icon: Mapped[str] = mapped_column(String(16), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # streak_days|chores_completed|points_earned
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    bonus_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


class UserBadge(Base):
    """A badge someone earned. Unique per person and badge: earned once, kept."""

    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),
        Index("ix_user_badges_family", "family_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    badge_id: Mapped[str] = mapped_column(String, nullable=False)
    earned_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class AllowancePlan(Base):
    """A member's weekly allowance. start_week is the Monday of the first payout."""

    __tablename__ = "allowance_plans"
    __table_args__ = (UniqueConstraint("user_id", name="uq_allowance_plan_user"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    weekly_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_week: Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


class AllowanceEntry(Base):
    """Append-only allowance ledger in whole cents. Weekly payouts carry their
    week, and (user_id, week_start) is unique, so a week can't be paid twice;
    adjustments and cash payouts have no week."""

    __tablename__ = "allowance_ledger"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_allowance_week"),
        UniqueConstraint("source_type", "source_id", name="uq_allowance_source"),
        Index("ix_allowance_family_user", "family_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    delta_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # weekly|adjustment
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
