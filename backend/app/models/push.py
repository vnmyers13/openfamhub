"""Phase 11: Web Push.

- `push_keys`: the install's VAPID key pair (one row, made on first use).
- `push_subscriptions`: one per device that turned notifications on; the
  endpoint is unique, so a shared device belongs to whoever subscribed last.
- `notifications_sent`: what each person has been sent, so the reminder job
  sends each reminder once (unique per user, kind and reference).
"""
import uuid
from datetime import datetime

from sqlalchemy import Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


def _id() -> str:
    return str(uuid.uuid4())


class PushKeys(Base):
    __tablename__ = "push_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # always 1
    private_pem: Mapped[str] = mapped_column(Text, nullable=False)
    public_key: Mapped[str] = mapped_column(String(128), nullable=False)  # base64url, uncompressed P-256
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, server_default=func.now())


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (Index("ix_push_subscriptions_user", "user_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(256), nullable=False)
    auth: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, server_default=func.now())
    last_success_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=True)


class NotificationSent(Base):
    __tablename__ = "notifications_sent"
    __table_args__ = (UniqueConstraint("user_id", "kind", "ref", name="uq_notifications_sent"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # event | daily | reward
    ref: Mapped[str] = mapped_column(String(160), nullable=False)  # what it was about (event id + start, a date, a request id)
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, server_default=func.now())
