"""Smart Import: turn a pasted page, JSON-LD or plain text into a recipe or
event draft. Nothing here touches the network or the database; the routers
fetch pages (core.safe_fetch) and the user reviews a draft before saving it.

Most recipe and event sites embed schema.org JSON-LD
(<script type="application/ld+json">), so that's tried first. Plain recipe
text falls back to a heuristic: a title line, then "Ingredients" and
"Instructions"/"Method" sections (or quantity-looking lines as ingredients).
"""
import html
import json
import re
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_LINES = 200
MAX_TAGS = 8


class NothingToImport(ValueError):
    """Nothing usable was found (shown to the user as-is)."""


# ---- JSON-LD extraction -------------------------------------------------------

class _LdScripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._in = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and (dict(attrs).get("type") or "").lower().strip() == "application/ld+json":
            self._in, self._buf = True, []

    def handle_endtag(self, tag):
        if tag == "script" and self._in:
            self.blocks.append("".join(self._buf))
            self._in = False

    def handle_data(self, data):
        if self._in:
            self._buf.append(data)


def _loads(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        # Some sites leave trailing semicolons or HTML comments around the JSON.
        cleaned = text.strip().strip(";").replace("<!--", "").replace("-->", "")
        try:
            return json.loads(cleaned)
        except ValueError:
            return None


def jsonld_nodes(content: str) -> list[dict]:
    """Every JSON-LD object in a page (or in pasted JSON), flattened."""
    stripped = content.lstrip()
    blocks = [content] if stripped[:1] in ("{", "[") else []
    if not blocks:
        parser = _LdScripts()
        try:
            parser.feed(content)
        except Exception:  # noqa: BLE001  - a malformed page shouldn't crash the import
            pass
        blocks = parser.blocks
    out: list[dict] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            out.append(node)
            for key in ("@graph", "mainEntity", "itemListElement", "subEvent"):
                if key in node:
                    walk(node[key])
    for block in blocks:
        walk(_loads(block))
    return out


def _types(node: dict) -> list[str]:
    t = node.get("@type", [])
    return [str(x) for x in (t if isinstance(t, list) else [t])]


def _first_of_type(nodes: Iterable[dict], match) -> Optional[dict]:
    for n in nodes:
        if any(match(t) for t in _types(n)):
            return n
    return None


# ---- small helpers --------------------------------------------------------------

def clean(value: Any) -> str:
    """Text without tags, entities or runs of whitespace."""
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("text") or value.get("name") or ""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value)))
    return re.sub(r"\s+", " ", text).strip()


def duration_minutes(value: Any) -> Optional[int]:
    """ISO-8601 durations ("PT1H30M", "P0DT0H20M") as whole minutes."""
    if not isinstance(value, str):
        return None
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?", value.strip().upper())
    if not m or not any(m.groups()):
        return None
    d, h, mins, s = (float(x) if x else 0 for x in m.groups())
    total = round(d * 1440 + h * 60 + mins + s / 60)
    return total or None


def _servings(value: Any) -> Optional[int]:
    for v in value if isinstance(value, list) else [value]:
        m = re.search(r"\d+", str(v)) if v is not None else None
        if m and 0 < int(m.group()) <= 100:
            return int(m.group())
    return None


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _steps(value: Any) -> list[str]:
    out: list[str] = []
    for item in _as_list(value):
        if isinstance(item, dict) and "HowToSection" in _types(item):
            out.extend(_steps(item.get("itemListElement")))
        elif isinstance(item, str) and "\n" in item:
            out.extend(clean(line) for line in item.splitlines())
        else:
            out.append(clean(item))
    return [s for s in out if s][:MAX_LINES]


_DIETS = {
    "VegetarianDiet": "vegetarian", "VeganDiet": "vegan", "GlutenFreeDiet": "gluten-free",
    "DiabeticDiet": "diabetic", "HalalDiet": "halal", "KosherDiet": "kosher", "LowCalorieDiet": "low-calorie",
    "LowFatDiet": "low-fat", "LowLactoseDiet": "low-lactose", "LowSaltDiet": "low-salt",
}


def _tags(node: dict) -> list[str]:
    tags: list[str] = []
    for diet in _as_list(node.get("suitableForDiet")):
        name = str(diet).rsplit("/", 1)[-1]
        if name in _DIETS:
            tags.append(_DIETS[name])
    for cat in _as_list(node.get("recipeCategory")) + _as_list(node.get("recipeCuisine")):
        for part in str(cat).split(","):
            if clean(part):
                tags.append(clean(part).lower())
    seen: list[str] = []
    for t in tags:
        if t not in seen and len(t) <= 32:
            seen.append(t)
    return seen[:MAX_TAGS]


def _video(value: Any) -> Optional[str]:
    for v in _as_list(value):
        if isinstance(v, dict):
            url = v.get("contentUrl") or v.get("embedUrl") or v.get("url")
        else:
            url = v
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return url
    return None


# ---- recipes --------------------------------------------------------------------

def recipe_from_jsonld(node: dict, source_url: Optional[str] = None) -> dict:
    title = clean(node.get("name")) or "Untitled recipe"
    prep = duration_minutes(node.get("prepTime"))
    cook = duration_minutes(node.get("cookTime"))
    if prep is None and cook is None:
        cook = duration_minutes(node.get("totalTime"))
    return {
        "title": title[:128],
        "description": clean(node.get("description"))[:1000] or None,
        "servings": _servings(node.get("recipeYield")),
        "prep_minutes": prep,
        "cook_minutes": cook,
        "ingredients": [clean(i) for i in _as_list(node.get("recipeIngredient") or node.get("ingredients")) if clean(i)][:MAX_LINES],
        "steps": _steps(node.get("recipeInstructions")),
        "tags": _tags(node),
        "video_url": _video(node.get("video")),
        "source_url": source_url,
    }


_BULLET = re.compile(r"^\s*(?:[-*•▢◦·]|\d+[.)]|step\s*\d+[.:)]?)\s*", re.IGNORECASE)
_INGREDIENTS = re.compile(r"^#*\s*ingredients?\s*:?\s*$", re.IGNORECASE)
_STEPS = re.compile(r"^#*\s*(instructions|directions|method|steps|preparation)\s*:?\s*$", re.IGNORECASE)
_SERVES = re.compile(r"^\s*(?:serves|servings|makes|yield)\s*:?\s*(\d+)", re.IGNORECASE)
_QUANTITY = re.compile(r"^(?:\d|[½¼¾⅓⅔⅛]|a |an |one |two |pinch|dash|handful|salt|pepper)", re.IGNORECASE)


def recipe_from_text(text: str) -> dict:
    lines = [ln.rstrip() for ln in text.replace("\r", "").split("\n")]
    lines = [ln for ln in lines if ln.strip()]
    if not lines:
        raise NothingToImport("There's no recipe text to read")
    title = re.sub(r"^#+\s*", "", lines[0]).strip()[:128]
    servings = None
    ingredients: list[str] = []
    steps: list[str] = []
    section: Optional[str] = None
    has_headers = any(_INGREDIENTS.match(ln) or _STEPS.match(ln) for ln in lines[1:])
    for line in lines[1:]:
        if _INGREDIENTS.match(line):
            section = "ingredients"
            continue
        if _STEPS.match(line):
            section = "steps"
            continue
        m = _SERVES.match(line)
        if m and servings is None:
            servings = int(m.group(1))
            continue
        item = _BULLET.sub("", line).strip()
        if not item:
            continue
        if has_headers:
            if section == "ingredients":
                ingredients.append(item)
            elif section == "steps":
                steps.append(item)
        elif _QUANTITY.match(item) and len(item) <= 80 and not steps:
            ingredients.append(item)
        else:
            steps.append(item)
    return {
        "title": title or "Untitled recipe", "description": None, "servings": servings,
        "prep_minutes": None, "cook_minutes": None, "ingredients": ingredients[:MAX_LINES],
        "steps": steps[:MAX_LINES], "tags": [], "video_url": None, "source_url": None,
    }


def looks_like_html(content: str) -> bool:
    return bool(re.search(r"<(html|head|body|script|div|meta)\b", content[:5000], re.IGNORECASE))


def parse_recipe(content: str, source_url: Optional[str] = None) -> dict:
    node = _first_of_type(jsonld_nodes(content), lambda t: t == "Recipe" or t.endswith("/Recipe"))
    if node is not None:
        return recipe_from_jsonld(node, source_url)
    if source_url or looks_like_html(content):
        raise NothingToImport("No recipe found on that page. Paste the recipe text instead.")
    return recipe_from_text(content)


# ---- events ---------------------------------------------------------------------

def _zone(name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _when(value: Any, zone: ZoneInfo) -> tuple[Optional[datetime], bool]:
    """A schema.org date/time as (UTC datetime, is_all_day)."""
    if not isinstance(value, str) or not value.strip():
        return None, False
    v = value.strip().replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        d = date.fromisoformat(v)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc), True
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None, False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=zone)  # local time where the event is: assume the family's
    return dt.astimezone(timezone.utc), False


def _location(value: Any) -> Optional[str]:
    for loc in _as_list(value):
        if isinstance(loc, str):
            return clean(loc) or None
        if isinstance(loc, dict):
            if "VirtualLocation" in _types(loc):
                return clean(loc.get("url")) or "Online"
            parts = [clean(loc.get("name"))]
            addr = loc.get("address")
            if isinstance(addr, dict):
                parts += [clean(addr.get(k)) for k in ("streetAddress", "addressLocality", "addressRegion")]
            elif addr:
                parts.append(clean(addr))
            text = ", ".join(p for p in parts if p)
            if text:
                return text[:256]
    return None


def event_from_jsonld(node: dict, family_tz: Optional[str] = "UTC", source_url: Optional[str] = None) -> dict:
    zone = _zone(family_tz)
    start, all_day = _when(node.get("startDate"), zone)
    if start is None:
        raise NothingToImport("That event has no start date")
    end, end_all_day = _when(node.get("endDate"), zone)
    if all_day:
        # All-day: dates with an exclusive end (an inclusive endDate gets +1 day).
        end = (end + timedelta(days=1)) if (end is not None and end_all_day and end >= start) else start + timedelta(days=1)
    elif end is None or end <= start:
        end = start + timedelta(hours=1)
    description = clean(node.get("description"))
    if source_url:
        description = (description + "\n\n" if description else "") + source_url
    return {
        "title": (clean(node.get("name")) or "Event")[:256],
        "start_dt": start, "end_dt": end, "all_day": all_day,
        "location": _location(node.get("location")),
        "description": description[:2000] or None,
    }


def parse_event(content: str, family_tz: Optional[str] = "UTC", source_url: Optional[str] = None) -> dict:
    node = _first_of_type(jsonld_nodes(content), lambda t: t.endswith("Event"))
    if node is None:
        raise NothingToImport("No event found on that page")
    return event_from_jsonld(node, family_tz, source_url)
