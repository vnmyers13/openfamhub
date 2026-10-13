import uuid
from datetime import datetime

from sqlalchemy import DDL, Boolean, String, event, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


class Family(Base):
    __tablename__ = "families"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    settings_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )




# One family per install (review backlog #5). Sign-in runs before anyone is
# signed in, so it can't scope by a session's family; the install's single
# family is the scope. Setup checks first; this trigger is the backstop for two
# setup requests racing. Migration 006 creates the same trigger on existing
# databases, and this listener creates it wherever create_all builds the table.
SINGLE_FAMILY_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS families_single_row
BEFORE INSERT ON families
WHEN (SELECT COUNT(*) FROM families) > 0
BEGIN
    SELECT RAISE(ABORT, 'single_family: this install already has a family');
END
"""

event.listen(
    Family.__table__,
    "after_create",
    DDL(SINGLE_FAMILY_TRIGGER).execute_if(dialect="sqlite"),
)
