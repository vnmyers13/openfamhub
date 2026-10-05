from typing import Optional

from pydantic import BaseModel, field_validator

from app.schemas import validators as v


class _UserFields(BaseModel):
    """Fields shared by create and update, with one copy of each rule."""

    email: Optional[str] = None
    password: Optional[str] = None
    pin: Optional[str] = None
    color_hex: Optional[str] = None
    ui_mode: Optional[str] = None
    role: Optional[str] = None
    avatar: Optional[str] = None  # an emoji, shown in the sign-in picker

    @field_validator("password")
    @classmethod
    def check_password(cls, x):
        return v.password(x)

    @field_validator("pin")
    @classmethod
    def check_pin(cls, x):
        return v.pin(x)

    @field_validator("color_hex")
    @classmethod
    def check_color(cls, x):
        return v.hex_color(x)

    @field_validator("role")
    @classmethod
    def check_role(cls, x):
        return v.role(x)

    @field_validator("ui_mode")
    @classmethod
    def check_ui_mode(cls, x):
        return v.ui_mode(x)

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, x):
        return v.avatar(x)


class CreateUserRequest(_UserFields):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, x):
        return v.display_name(x)


class UpdateUserRequest(_UserFields):
    display_name: Optional[str] = None

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, x):
        return v.display_name(x)


class SetPinRequest(BaseModel):
    pin: str

    @field_validator("pin")
    @classmethod
    def check_pin(cls, x):
        return v.pin(x)


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
