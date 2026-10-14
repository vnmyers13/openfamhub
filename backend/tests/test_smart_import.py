"""Phase 7 Smart Import: recipe and event drafts from JSON-LD, HTML and text."""
import json
from datetime import datetime, timezone

import httpx
import pytest

from app.integrations.smart_import import (
    NothingToImport, duration_minutes, jsonld_nodes, parse_event, parse_recipe,
)

RECIPE_LD = {
    "@context": "https://schema.org",
    "@type": "Recipe",
    "name": "Weeknight Chili &amp; Beans",
    "description": "<p>Cozy and quick.</p>",
    "recipeYield": ["6", "6 servings"],
    "prepTime": "PT15M",
    "cookTime": "PT1H5M",
    "recipeIngredient": ["1 lb ground beef", " 2 cans beans ", ""],
    "recipeInstructions": [
        {"@type": "HowToSection", "name": "Cook", "itemListElement": [
            {"@type": "HowToStep", "text": "Brown the beef."},
            {"@type": "HowToStep", "text": "Add the beans and simmer."},
        ]},
        "Serve hot.",
    ],
    "suitableForDiet": "https://schema.org/GlutenFreeDiet",
    "recipeCategory": "Dinner, Main",
    "video": {"@type": "VideoObject", "contentUrl": "https://videos.example.com/chili.mp4"},
}


def page(*blocks, extra=""):
    scripts = "".join(f'<script type="application/ld+json">{json.dumps(b)}</script>' for b in blocks)
    return f"<html><head><title>x</title>{scripts}</head><body>{extra}</body></html>"


class TestJsonLd:
    def test_a_recipe_page(self):
        draft = parse_recipe(page(RECIPE_LD), source_url="https://food.example.com/chili")
        assert draft["title"] == "Weeknight Chili & Beans"
        assert draft["description"] == "Cozy and quick."
        assert draft["servings"] == 6 and draft["prep_minutes"] == 15 and draft["cook_minutes"] == 65
        assert draft["ingredients"] == ["1 lb ground beef", "2 cans beans"]
        assert draft["steps"] == ["Brown the beef.", "Add the beans and simmer.", "Serve hot."]
        assert draft["tags"] == ["gluten-free", "dinner", "main"]
        assert draft["video_url"] == "https://videos.example.com/chili.mp4"
        assert draft["source_url"] == "https://food.example.com/chili"

    def test_a_recipe_inside_a_graph_with_a_type_list(self):
        graph = {"@context": "https://schema.org", "@graph": [
            {"@type": "WebPage", "name": "Blog"}, {**RECIPE_LD, "@type": ["Recipe", "NewsArticle"]}]}
        assert parse_recipe(page({"@type": "Organization"}, graph))["title"] == "Weeknight Chili & Beans"

    def test_pasted_json_ld(self):
        assert parse_recipe(json.dumps(RECIPE_LD))["cook_minutes"] == 65

    def test_instructions_as_one_string(self):
        node = {**RECIPE_LD, "recipeInstructions": "Mix.\nBake.\n\nCool."}
        assert parse_recipe(page(node))["steps"] == ["Mix.", "Bake.", "Cool."]

    def test_total_time_when_prep_and_cook_are_missing(self):
        node = {k: v for k, v in RECIPE_LD.items() if k not in ("prepTime", "cookTime")}
        assert parse_recipe(page({**node, "totalTime": "PT45M"}))["cook_minutes"] == 45

    def test_a_page_without_a_recipe(self):
        with pytest.raises(NothingToImport, match="No recipe found"):
            parse_recipe(page({"@type": "Article", "name": "News"}), source_url="https://x.example.com")

    def test_broken_json_is_skipped(self):
        html = '<script type="application/ld+json">{not json</script>' + page(RECIPE_LD)
        assert parse_recipe(html)["title"] == "Weeknight Chili & Beans"
        assert jsonld_nodes('<script type="application/ld+json">{nope</script>') == []

    def test_durations(self):
        assert duration_minutes("PT1H30M") == 90
        assert duration_minutes("P0DT0H20M") == 20
        assert duration_minutes("PT90S") == 2
        assert duration_minutes("soon") is None and duration_minutes(None) is None and duration_minutes("P") is None


class TestText:
    def test_sections(self):
        draft = parse_recipe("""# Pancakes
Serves 4

Ingredients:
- 1 cup flour
- 1 egg
* 1 cup milk

Method
1. Whisk everything.
2) Cook in a hot pan.
""")
        assert draft["title"] == "Pancakes" and draft["servings"] == 4
        assert draft["ingredients"] == ["1 cup flour", "1 egg", "1 cup milk"]
        assert draft["steps"] == ["Whisk everything.", "Cook in a hot pan."]

    def test_without_headers_quantities_are_ingredients(self):
        draft = parse_recipe("Toast\n2 slices bread\n1 tbsp butter\nToast the bread and butter it while hot.")
        assert draft["ingredients"] == ["2 slices bread", "1 tbsp butter"]
        assert draft["steps"] == ["Toast the bread and butter it while hot."]

    def test_empty_text(self):
        with pytest.raises(NothingToImport):
            parse_recipe("   \n  ")


EVENT_LD = {
    "@context": "https://schema.org", "@type": "MusicEvent", "name": "School Concert",
    "startDate": "2026-11-05T18:30", "endDate": "2026-11-05T20:00",
    "location": {"@type": "Place", "name": "Lincoln Elementary",
                 "address": {"@type": "PostalAddress", "streetAddress": "1 Main St", "addressLocality": "Ann Arbor"}},
    "description": "Bring a chair.",
}


class TestEvents:
    def test_a_timed_event_in_the_familys_timezone(self):
        draft = parse_event(page(EVENT_LD), "America/Detroit", source_url="https://school.example.com/concert")
        assert draft["title"] == "School Concert" and draft["all_day"] is False
        assert draft["start_dt"] == datetime(2026, 11, 5, 23, 30, tzinfo=timezone.utc)  # 18:30 EST
        assert draft["end_dt"] == datetime(2026, 11, 6, 1, 0, tzinfo=timezone.utc)
        assert draft["location"] == "Lincoln Elementary, 1 Main St, Ann Arbor"
        assert draft["description"] == "Bring a chair.\n\nhttps://school.example.com/concert"

    def test_an_offset_is_respected(self):
        draft = parse_event(json.dumps({**EVENT_LD, "startDate": "2026-11-05T18:30:00-08:00", "endDate": None}), "America/Detroit")
        assert draft["start_dt"] == datetime(2026, 11, 6, 2, 30, tzinfo=timezone.utc)
        assert draft["end_dt"] == datetime(2026, 11, 6, 3, 30, tzinfo=timezone.utc)  # 1 hour by default

    def test_a_multi_day_all_day_event_gets_an_exclusive_end(self):
        draft = parse_event(page({"@type": "Event", "name": "Book fair", "startDate": "2026-11-09", "endDate": "2026-11-11",
                                  "location": "Library"}))
        assert draft["all_day"] is True and draft["location"] == "Library"
        assert draft["start_dt"] == datetime(2026, 11, 9, tzinfo=timezone.utc)
        assert draft["end_dt"] == datetime(2026, 11, 12, tzinfo=timezone.utc)

    def test_online_events_and_missing_dates(self):
        online = {"@type": "Event", "name": "Webinar", "startDate": "2026-11-09T10:00:00Z",
                  "location": {"@type": "VirtualLocation", "url": "https://meet.example.com/x"}}
        assert parse_event(page(online))["location"] == "https://meet.example.com/x"
        with pytest.raises(NothingToImport, match="no start date"):
            parse_event(page({"@type": "Event", "name": "Someday"}))
        with pytest.raises(NothingToImport, match="No event"):
            parse_event(page(RECIPE_LD))


# ---- the import API (pages fetched through the SSRF-safe fetcher) -------------

from tests.test_phase2 import SETUP, _cookie, _h, _member  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_throttle():
    from app.core.security import login_throttle

    login_throttle.reset()
    yield
    login_throttle.reset()


@pytest.fixture
async def admin(client):
    res = await client.post("/api/auth/setup", json=SETUP)
    return {"Cookie": _cookie(res), "id": res.json()["id"]}


class TestImportApi:
    async def test_import_a_recipe_from_a_link(self, client, admin, monkeypatch):
        seen = {}

        async def fake_fetch(url, **kw):
            seen.update(url=url, **kw)
            return page(RECIPE_LD).encode()

        monkeypatch.setattr("app.routers.imports.fetch_public", fake_fetch)
        res = await client.post("/api/import/recipe", json={"url": "https://food.example.com/chili"}, headers=_h(admin))
        assert res.status_code == 200, res.text
        assert res.json()["title"] == "Weeknight Chili & Beans" and res.json()["source_url"] == "https://food.example.com/chili"
        assert seen["max_bytes"] == 3_000_000 and seen["timeout"] == 20.0

    async def test_import_recipe_text_and_an_event(self, client, admin):
        res = await client.post("/api/import/recipe", json={"text": "Toast\n2 slices bread\nToast it."}, headers=_h(admin))
        assert res.status_code == 200 and res.json()["ingredients"] == ["2 slices bread"]
        res = await client.post("/api/import/event", json={"text": json.dumps(EVENT_LD)}, headers=_h(admin))
        assert res.status_code == 200, res.text
        assert res.json()["start_dt"].startswith("2026-11-05T23:30")  # SETUP's family is in America/Detroit

    async def test_blocked_and_failing_links_explain_themselves(self, client, admin):
        res = await client.post("/api/import/recipe", json={"url": "http://127.0.0.1/admin"}, headers=_h(admin))
        assert res.status_code == 400 and "Blocked non-public address" in res.json()["detail"]
        res = await client.post("/api/import/recipe", json={"url": "javascript:alert(1)"}, headers=_h(admin))
        assert res.status_code == 422

    async def test_the_real_fetcher_is_used_with_its_guards(self, client, admin, monkeypatch):
        import socket

        monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))])

        def handler(request):
            return httpx.Response(404)

        real = httpx.AsyncClient

        def client_with_mock(*a, **k):
            k["transport"] = httpx.MockTransport(handler)
            return real(*a, **k)

        monkeypatch.setattr("app.core.safe_fetch.httpx.AsyncClient", client_with_mock)
        res = await client.post("/api/import/event", json={"url": "https://events.example.com/x"}, headers=_h(admin))
        assert res.status_code == 400 and res.json()["detail"] == "Couldn't read that link: That page returned HTTP 404"

    async def test_one_source_and_no_viewers(self, client, admin):
        res = await client.post("/api/import/recipe", json={"url": "https://a.example.com", "text": "x"}, headers=_h(admin))
        assert res.status_code == 422
        viewer = await _member(client, admin, name="Grandma", pin="9999", role="viewer")
        assert (await client.post("/api/import/recipe", json={"text": "x\n1 egg"}, headers=_h(viewer))).status_code == 403
        res = await client.post("/api/import/recipe", json={"text": "<html><body>no recipe</body></html>"}, headers=_h(admin))
        assert res.status_code == 400 and "No recipe found" in res.json()["detail"]


def test_a_recipe_read_from_a_photo_parses_like_pasted_text():
    """Phase 10 photo → recipe: the app OCRs the photo, joins wrapped steps
    (frontend lib/ocrRecipe.ts) and sends the text here. This is that text as
    the real OCR test (frontend lib/ocr.real.test.ts) produces it."""
    from app.integrations.smart_import import recipe_from_text

    text = "\n".join([
        "Banana Bread", "Serves 8", "Ingredients", "3 ripe bananas", "1/3 cup melted butter", "1 cup sugar", "Method",
        "1. Heat the oven to 350F and butter a loaf pan.", "2. Mash the bananas, then stir in the butter and sugar.",
        "3. Bake for 60 minutes.",
    ])
    r = recipe_from_text(text)
    assert (r["title"], r["servings"]) == ("Banana Bread", 8)
    assert r["ingredients"] == ["3 ripe bananas", "1/3 cup melted butter", "1 cup sugar"]
    assert r["steps"] == ["Heat the oven to 350F and butter a loaf pan.",
                          "Mash the bananas, then stir in the butter and sugar.", "Bake for 60 minutes."]
