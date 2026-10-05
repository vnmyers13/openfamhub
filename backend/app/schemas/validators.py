"""Field rules shared by request schemas (one copy of each rule)."""
from typing import Optional

ROLES = ("admin", "member", "viewer")
UI_MODES = ("standard", "simple", "kiosk")


def hex_color(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if not v.startswith("#") or len(v) != 7:
        raise ValueError("color_hex must be #RRGGBB")
    try:
        int(v[1:], 16)
    except ValueError:
        raise ValueError("color_hex must be #RRGGBB")
    return v


def display_name(v: Optional[str]) -> Optional[str]:
    if v is not None and not 1 <= len(v.strip()) <= 100:
        raise ValueError("display_name must be 1-100 characters")
    return v


def password(v: Optional[str]) -> Optional[str]:
    if v is not None and len(v) < 8:
        raise ValueError("password must be at least 8 characters")
    return v


def pin(v: Optional[str]) -> Optional[str]:
    if v is not None and (not v.isdigit() or not 4 <= len(v) <= 8):
        raise ValueError("pin must be 4-8 digits")
    return v


def role(v: Optional[str]) -> Optional[str]:
    if v is not None and v not in ROLES:
        raise ValueError("role must be admin, member, or viewer")
    return v


def ui_mode(v: Optional[str]) -> Optional[str]:
    if v is not None and v not in UI_MODES:
        raise ValueError("ui_mode must be standard, simple, or kiosk")
    return v


def avatar(v: Optional[str]) -> Optional[str]:
    if v is not None and not 1 <= len(v) <= 16:
        raise ValueError("avatar must be 1-16 characters (an emoji)")
    return v
