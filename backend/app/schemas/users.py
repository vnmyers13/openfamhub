from typing import Optional

from pydantic import BaseModel, field_validator


class CreateUserRequest(BaseModel):
    display_name: str
    email: Optional[str] = None
    password: Optional[str] = None
    pin: Optional[str] = None
    color_hex: Optional[str] = None
    ui_mode: Optional[str] = None
    role: Optional[str] = None

    @field_validator("display_name")
    @classmethod
    def display_name_length(cls, v: str) -> str:
        if len(v) < 1 or len(v) > 100:
            raise ValueError("display_name must be 1-100 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v

    @field_validator("pin")
    @classmethod
    def pin_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (len(v) < 4 or len(v) > 8):
            raise ValueError("pin must be 4-8 characters")
        return v

    @field_validator("color_hex")
    @classmethod
    def valid_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.startswith("#") or len(v) != 7:
                raise ValueError("color_hex must be #RRGGBB")
            int(v[1:], 16)
        return v

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("admin", "member", "viewer"):
            raise ValueError('role must be admin, member, or viewer')
        return v

    @field_validator("ui_mode")
    @classmethod
    def valid_ui_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("standard", "simple", "kiosk"):
            raise ValueError('ui_mode must be standard, simple, or kiosk')
        return v


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    pin: Optional[str] = None
    color_hex: Optional[str] = None
    ui_mode: Optional[str] = None
    role: Optional[str] = None

    @field_validator("display_name")
    @classmethod
    def display_name_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (len(v) < 1 or len(v) > 100):
            raise ValueError("display_name must be 1-100 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v

    @field_validator("pin")
    @classmethod
    def pin_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (len(v) < 4 or len(v) > 8):
            raise ValueError("pin must be 4-8 characters")
        return v

    @field_validator("color_hex")
    @classmethod
    def valid_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.startswith("#") or len(v) != 7:
                raise ValueError("color_hex must be #RRGGBB")
            int(v[1:], 16)
        return v

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("admin", "member", "viewer"):
            raise ValueError('role must be admin, member, or viewer')
        return v

    @field_validator("ui_mode")
    @classmethod
    def valid_ui_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("standard", "simple", "kiosk"):
            raise ValueError('ui_mode must be standard, simple, or kiosk')
        return v


class SetPinRequest(BaseModel):
    pin: str

    @field_validator("pin")
    @classmethod
    def pin_length(cls, v: str) -> str:
        if len(v) < 4 or len(v) > 8:
            raise ValueError("pin must be 4-8 characters")
        return v


class SwitchUserRequest(BaseModel):
    user_id: str


class UserResponse(BaseModel):
    id: str
    display_name: str
    email: Optional[str] = None
    role: str
    color_hex: str
    ui_mode: str
    avatar_type: Optional[str] = None
    avatar_value: Optional[str] = None
    family_id: str
    has_password: bool = False
    has_pin: bool = False
    last_login_at: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}
