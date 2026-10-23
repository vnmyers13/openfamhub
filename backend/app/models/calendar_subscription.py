"""Managed feed state; bearer URLs are ciphertext, never a model property."""
import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, CheckConstraint, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


class CalendarSubscription(Base):
    __tablename__ = "calendar_subscriptions"
    __table_args__ = (
        UniqueConstraint("family_id", "kind", name="uq_calendar_subscription_family_kind"),
        CheckConstraint("kind IN ('titles', 'full')", name="ck_calendar_subscription_kind"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[Literal["titles", "full"]] = mapped_column(String(16), nullable=False)
    relay_id: Mapped[str] = mapped_column(String(128), nullable=True)
    relay_url_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    publication_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    last_published_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    # A keyed identity of the rejected configuration, never a credential. Its
    # presence pauses delivery until the operator changes relay configuration.
    auth_paused_config: Mapped[str] = mapped_column(String(64), nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CalendarSubscriptionAudit(Base):
    __tablename__ = "calendar_subscription_audits"
    __table_args__ = (
        CheckConstraint("action IN ('created', 'revealed', 'rotated', 'revoked')", name="ck_calendar_subscription_audit_action"),
        Index("ix_calendar_subscription_audits_family_created", "family_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subscription_id: Mapped[str] = mapped_column(String, nullable=False)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[Literal["created", "revealed", "rotated", "revoked"]] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
