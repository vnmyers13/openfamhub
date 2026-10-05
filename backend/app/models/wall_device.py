import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


class WallDevice(Base):
    """A paired wall display (kiosk). Read-only access to its family's calendar."""

    __tablename__ = "wall_devices"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # sha256 of the pairing token; the token itself is shown to the admin once.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
