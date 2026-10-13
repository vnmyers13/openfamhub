from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MediaResponse(BaseModel):
    id: str
    kind: str
    status: str
    error: Optional[str] = None
    original_name: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_s: Optional[float] = None
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime] = None
    wall_url: str
    thumb_url: str


class WallMediaResponse(BaseModel):
    id: str
    kind: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_s: Optional[float] = None
    wall_url: str
    thumb_url: str
