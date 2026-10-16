import json
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator


Coordinate = Annotated[int, Field(ge=0, le=1000)]


class Point(BaseModel):
    x: Coordinate
    y: Coordinate


class NoteItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: Literal["note"]
    x: Coordinate
    y: Coordinate
    width: Annotated[int, Field(ge=40, le=1000)]
    height: Annotated[int, Field(ge=40, le=1000)]
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    text: str = Field(min_length=1, max_length=1000)


class StickerItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: Literal["sticker"]
    x: Coordinate
    y: Coordinate
    size: Annotated[int, Field(ge=20, le=300)]
    emoji: str = Field(min_length=1, max_length=16)


class ImageItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: Literal["image"]
    x: Coordinate
    y: Coordinate
    width: Annotated[int, Field(ge=40, le=1000)]
    height: Annotated[int, Field(ge=40, le=1000)]
    media_id: str = Field(min_length=1, max_length=64)


class StrokeItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: Literal["stroke"]
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    points: list[Point] = Field(min_length=2, max_length=500)


BoardItem = Annotated[Union[NoteItem, StickerItem, ImageItem, StrokeItem], Field(discriminator="type")]


class NoteBoardUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    items: list[BoardItem] = Field(max_length=100)

    @field_validator("title")
    @classmethod
    def title_is_trimmed(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @model_validator(mode="after")
    def scene_is_bounded(self):
        if len(json.dumps(self.model_dump(mode="json"), separators=(",", ":"))) > 250_000:
            raise ValueError("scene must be no larger than 250 KB")
        return self


class NoteBoardResponse(NoteBoardUpdate):
    id: str
    updated_by: str | None = None
