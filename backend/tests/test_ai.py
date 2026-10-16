"""Local-only AI draft endpoint: it must be safe before it is helpful."""
import json
import base64

import httpx
import pytest

from tests.test_phase2 import SETUP, _cookie, _h


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    assert res.status_code == 200, res.text
    return {"Cookie": _cookie(res), "id": res.json()["id"]}


class TestDrafts:
    async def _configure(self, client, admin):
        res = await client.put("/api/admin/server-settings", json={"ollama_url": "http://192.168.10.91:11434", "ollama_model": "llama3.1:8b"}, headers=_h(admin))
        assert res.status_code == 200, res.text

    async def test_draft_is_unavailable_until_an_admin_configures_a_local_model(self, client, admin):
        res = await client.post("/api/ai/draft", json={"request": "Add soccer practice tomorrow"}, headers=_h(admin))

        assert res.status_code == 503
        assert res.json()["detail"] == "Local AI isn't set up yet. Ask an admin to add the Ollama address and model."

    async def test_invalid_model_json_becomes_a_safe_draft_error(self, client, admin, monkeypatch):
        await self._configure(client, admin)

        class BadModel:
            async def __aenter__(self): return self
            async def __aexit__(self, *_): pass
            async def post(self, *_args, **_kwargs): return type("Response", (), {"raise_for_status": lambda self: None, "json": lambda self: {"message": {"content": "not json"}}})()

        monkeypatch.setattr(httpx, "AsyncClient", lambda **_: BadModel())
        res = await client.post("/api/ai/draft", json={"request": "Add soccer practice tomorrow"}, headers=_h(admin))

        assert res.status_code == 503
        assert res.json()["detail"] == "The local AI service is unavailable or returned an invalid draft."

    async def test_returns_a_valid_family_scoped_event_draft(self, client, admin, monkeypatch):
        await self._configure(client, admin)
        reply = {"action": {"kind": "event", "operation": "create", "fields": {
            "title": "Soccer practice", "start_dt": "2026-10-17T18:00:00+00:00", "end_dt": "2026-10-17T19:00:00+00:00", "all_day": False}},
            "summary": "Add Soccer practice on October 17 at 6:00 PM."}
        sent = {}

        class Model:
            async def __aenter__(self): return self
            async def __aexit__(self, *_): pass
            async def post(self, url, **kwargs):
                sent.update(url=url, **kwargs)
                return type("Response", (), {"raise_for_status": lambda self: None, "json": lambda self: {"message": {"content": json.dumps(reply)}}})()

        monkeypatch.setattr(httpx, "AsyncClient", lambda **_: Model())
        res = await client.post("/api/ai/draft", json={"request": "Add soccer practice tomorrow"}, headers=_h(admin))

        assert res.status_code == 200, res.text
        assert res.json() == reply
        assert sent["url"] == "http://192.168.10.91:11434/api/chat"
        assert sent["json"]["stream"] is False and sent["json"]["options"] == {"temperature": 0}
        prompt = sent["json"]["messages"][1]["content"]
        assert "Add soccer practice tomorrow" in prompt and "family_id" in prompt

    async def test_admin_cannot_configure_a_hosted_model_endpoint(self, client, admin):
        res = await client.put("/api/admin/server-settings", json={"ollama_url": "https://ollama.com", "ollama_model": "qwen"}, headers=_h(admin))

        assert res.status_code == 422
        assert "private LAN" in res.json()["detail"]

    async def test_audio_draft_passes_wav_bytes_to_the_local_model(self, client, admin, monkeypatch):
        await self._configure(client, admin)
        sent = {}
        reply = {"action": {"kind": "todo", "operation": "create", "fields": {"title": "Buy milk"}}, "summary": "Add Buy milk."}

        class Model:
            async def __aenter__(self): return self
            async def __aexit__(self, *_): pass
            async def post(self, _url, **kwargs):
                sent.update(kwargs)
                return type("Response", (), {"raise_for_status": lambda self: None, "json": lambda self: {"message": {"content": json.dumps(reply)}}})()

        monkeypatch.setattr(httpx, "AsyncClient", lambda **_: Model())
        audio = base64.b64encode(b"RIFF\x00\x00\x00\x00WAVE").decode()
        res = await client.post("/api/ai/draft", json={"request": "", "audio_base64": audio}, headers=_h(admin))

        assert res.status_code == 200, res.text
        assert sent["json"]["messages"][1]["images"] == [audio]
