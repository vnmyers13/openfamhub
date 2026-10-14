from pydantic import BaseModel, Field, field_validator


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(..., min_length=1, max_length=256)
    auth: str = Field(..., min_length=1, max_length=64)


class SubscriptionIn(BaseModel):
    """What the browser's PushManager.subscribe() returns (toJSON())."""

    endpoint: str = Field(..., max_length=2048)
    keys: SubscriptionKeys

    @field_validator("endpoint")
    @classmethod
    def https_only(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("push endpoints are https")
        return v


class SubscriptionRef(BaseModel):
    endpoint: str = Field(..., max_length=2048)
