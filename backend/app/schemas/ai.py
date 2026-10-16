from typing import Any, Literal

import base64

from pydantic import BaseModel, Field, model_validator


class DraftRequest(BaseModel):
    request: str = Field("", max_length=2000)
    # WAV/MP3 bytes, sent to Ollama's media field. Limited before decoding.
    audio_base64: str | None = Field(None, max_length=14_000_000)

    @model_validator(mode="after")
    def has_text_or_audio(self):
        if not self.request.strip() and not self.audio_base64:
            raise ValueError("provide a request or audio")
        if self.audio_base64:
            try:
                raw = base64.b64decode(self.audio_base64, validate=True)
            except ValueError:
                raise ValueError("audio must be base64") from None
            if len(raw) > 10_000_000 or not (raw.startswith(b"RIFF") or raw.startswith(b"ID3") or raw[:2] == b"\xff\xfb"):
                raise ValueError("audio must be WAV or MP3 and no larger than 10 MB")
        return self


class DraftAction(BaseModel):
    kind: Literal["event", "chore", "todo"]
    operation: Literal["create", "update"]
    fields: dict[str, Any]
    target_id: str | None = None


class DraftResponse(BaseModel):
    action: DraftAction
    summary: str = Field(min_length=1, max_length=500)
