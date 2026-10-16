"""Local-model boundary: it proposes validated drafts and never writes data."""
import json

import httpx
from pydantic import ValidationError

from app.schemas.ai import DraftResponse
from app.services import server_config as cfg


class Unavailable(Exception):
    pass


def configured() -> bool:
    return bool(cfg.get("ollama_url") and cfg.get("ollama_model"))


async def draft(request: str, context: dict, audio_base64: str | None = None) -> DraftResponse:
    if not configured():
        raise Unavailable("Local AI isn't set up yet. Ask an admin to add the Ollama address and model.")
    prompt = (
        "Return only a JSON action draft for OpenFamHub. Use only IDs supplied in context for updates or assignees; "
        "never invent IDs. Dates use YYYY-MM-DD and event datetimes are ISO-8601 UTC. "
        f"Request: {request}\nContext: {json.dumps(context, separators=(',', ':'))}"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{cfg.get('ollama_url').rstrip('/')}/api/chat",
                json={"model": cfg.get("ollama_model"), "stream": False, "format": DraftResponse.model_json_schema(),
                      "options": {"temperature": 0},
                      "messages": [{"role": "system", "content": "You create safe family-organizer drafts."},
                                   {"role": "user", "content": prompt, **({"images": [audio_base64]} if audio_base64 else {})}]},
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
        return DraftResponse.model_validate_json(content)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError) as exc:
        raise Unavailable("The local AI service is unavailable or returned an invalid draft.") from exc
