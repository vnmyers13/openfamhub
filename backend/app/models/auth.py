import uuid
from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


class Session(Base):
    """A signed-in browser. The JWT's `jti` is this row's id, so deleting the row
    revokes the token (logout, password change, user removal)."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    # sha256 of the issued JWT (never the token itself).
    token_hash: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    device_hint: Mapped[str] = mapped_column(String(128), nullable=True)
    # "password" or "pin". Admin actions need a password session or an elevation.
    auth_method: Mapped[str] = mapped_column(String(16), nullable=False, default="password")
    # Set by POST /auth/elevate: a PIN session may do admin actions until then.
    elevated_until: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
