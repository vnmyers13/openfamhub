from typing import Optional

from pydantic import BaseModel, field_validator


def _pin(v: Optional[str]) -> Optional[str]:
    if v is not None and (not v.isdigit() or not 4 <= len(v) <= 8):
        raise ValueError("pin must be 4-8 digits")
    return v


class SetupRequest(BaseModel):
    family_name: str
    timezone: str = "UTC"
    admin_display_name: str
    admin_password: str
    admin_pin: Optional[str] = None

    @field_validator("family_name")
    @classmethod
    def family_name_length(cls, v: str) -> str:
        if len(v) < 1 or len(v) > 200:
            raise ValueError("family_name must be 1-200 characters")
        return v

    @field_validator("admin_display_name")
    @classmethod
    def display_name_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1 or len(v) > 100:
            raise ValueError("admin_display_name must be 1-100 characters")
        return v

    @field_validator("admin_password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("admin_password must be at least 8 characters")
        return v

    @field_validator("admin_pin")
    @classmethod
    def pin_format(cls, v: Optional[str]) -> Optional[str]:
        return _pin(v)


class LoginRequest(BaseModel):
    display_name: str
    password: str


class PinLoginRequest(BaseModel):
    user_id: str
    pin: str

    @field_validator("pin")
    @classmethod
    def pin_format(cls, v: str) -> str:
        return _pin(v)


class ElevateRequest(BaseModel):
    password: str


class UserResponse(BaseModel):
    id: str
    display_name: str
    role: str
    color_hex: str
    ui_mode: str
    avatar_type: Optional[str] = None
    avatar_value: Optional[str] = None
    family_id: str
    # How this session signed in, and whether it may do admin actions now.
    auth_method: Optional[str] = None
    admin_unlocked: bool = False

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    """What the sign-in picker shows. Public, so keep it to these fields."""

    id: str
    display_name: str
    color_hex: str
    avatar_type: Optional[str] = None
    avatar_value: Optional[str] = None
    has_pin: bool


class SetupStatusResponse(BaseModel):
    setup_complete: bool
