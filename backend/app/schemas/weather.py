from pydantic import BaseModel, Field
from typing import Optional


class WeatherSettingsUpdate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    location_name: Optional[str] = Field(None, max_length=200)


class WeatherSettingsResponse(BaseModel):
    lat: float
    lon: float
    location_name: Optional[str] = None


class WeatherResponse(BaseModel):
    temperature: float
    condition_code: int
    condition_description: str
    condition_icon: str
    high: float
    low: float
    location_name: Optional[str] = None
    error: Optional[str] = None
    settings: Optional[WeatherSettingsResponse] = None
