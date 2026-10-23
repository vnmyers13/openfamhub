"""Schemas for the calendar subscription lifecycle API.

End-points live under /api/calendar/subscriptions/{kind} where kind is
"titles" or "full".  All write operations are password-gated admin.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CalendarSubscriptionListResponse(BaseModel):
    """A subscription entry returned by the list endpoint.

    Only stable metadata and the chosen kind; the relay URL is never
    included so that a leaked response cannot be used to access feeds.
    """

    id: str
    family_id: str
    kind: str
    active: bool
    last_published_at: Optional[datetime] = None
    last_error: Optional[str] = None

    model_config = {"from_attributes": True}


class CalendarSubscriptionDetailResponse(BaseModel):
    """A subscription entry that also carries the revealed URL.

    Used by create, reveal, and rotate responses.  The URL is encrypted
    at rest and decrypted only for the requesting admin.
    """

    id: str
    family_id: str
    kind: str
    active: bool
    last_published_at: Optional[datetime] = None
    last_error: Optional[str] = None
    subscription_url: str

    model_config = {"from_attributes": True}


class CalendarSubscriptionAuditLogEntry(BaseModel):
    """An audit entry for a subscription lifecycle action."""

    id: str
    subscription_id: str
    family_id: str
    action: str
    actor_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}
