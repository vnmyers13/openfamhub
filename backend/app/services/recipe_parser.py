"""Recipe text parsing and URL import service."""

import json
import re
import httpx
from typing import Any


def parse_recipe_text(text: str) -> dict[str, Any]:
    """
    Heuristic parsing of pasted recipe text.
    Returns: {title, ingredients_raw, steps_raw, prep_time_min, cook_time_min, servings}
    """
    lines = text.strip().split('\n')
    title = lines[0].strip() if lines else "Untitled Recipe"
    
    ingredients: list[str] = []
    steps: list[str] = []
    current_section: str | None = None  # "ingredients" or "steps"
    
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        
        # Detect section transitions
        lower = line.lower()
        if lower in ('ingredients:', 'ingredients', "what you'll need:", 'for the recipe:'):
            current_section = "ingredients"
            continue
        elif lower in ('instructions:', 'directions:', 'steps:', 'method:', 'how to make:', 'directions:'):
            current_section = "steps"
            continue
        
        # Parse based on section
        if current_section == "ingredients":
            if line and re.match(r'^[\d\w]', line):  # Starts with number/word
                ingredients.append(line)
        elif current_section == "steps":
            if re.match(r'^\d+[\.\)]\s', line) or re.match(r'^[-*•]\s', line):
                steps.append(re.sub(r'^\d+[\.\)]\s|^[*-•]\s', '', line))
        else:
            # Heuristic: lines with quantities are ingredients
            if re.search(r'\d+\s*(cups?|tbsp|tsp|oz|lb|g|kg|ml|L|pinch|slice|piece|can|bunch|bag|box|package|medium|large|small)', line, re.IGNORECASE):
                ingredients.append(line)
            # Numbered lines are steps
            elif re.match(r'^\d+[\.\)]\s', line):
                steps.append(re.sub(r'^\d+[\.\)]\s', '', line))
    
    return {
        "title": title,
        "ingredients_raw": '\n'.join(ingredients) if ingredients else None,
        "steps_raw": '\n'.join(steps) if steps else None,
        "prep_time_min": None,
        "cook_time_min": None,
        "servings": None,
    }


async def import_recipe_from_url(url: str) -> dict[str, Any]:
    """
    Fetch a URL and try to extract recipe data from schema.org/Recipe JSON-LD.
    Falls back to storing raw HTML.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
    
    # Try to find JSON-LD with schema.org/Recipe
    json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    scripts = re.findall(json_ld_pattern, html, re.DOTALL)
    
    for script in scripts:
        try:
            data = json.loads(script)
            recipe = extract_recipe_from_jsonld(data)
            if recipe:
                recipe["imported_from"] = "website"
                recipe["content_text"] = html  # Store raw for reference
                return recipe
        except json.JSONDecodeError:
            continue
    
    # Fallback: store raw HTML
    return {
        "title": "Imported Recipe",
        "content_text": html,
        "ingredients_raw": None,
        "steps_raw": None,
        "imported_from": "website_fallback",
    }


def extract_recipe_from_jsonld(data: Any) -> dict[str, Any] | None:
    """Recursively search JSON-LD data for schema.org/Recipe."""
    if isinstance(data, dict):
        if data.get("@type") in ("Recipe", ["Recipe"]):
            return {
                "title": data.get("name", "Untitled"),
                "ingredients_raw": "\n".join(data.get("recipeIngredient", [])) if data.get("recipeIngredient") else None,
                "steps_raw": _format_steps(data.get("recipeInstructions")),
                "prep_time_min": _parse_duration(data.get("prepTime")),
                "cook_time_min": _parse_duration(data.get("cookTime")),
                "total_time_min": _parse_duration(data.get("totalTime")),
                "servings": data.get("recipeYield"),
            }
        for value in data.values():
            result = extract_recipe_from_jsonld(value)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = extract_recipe_from_jsonld(item)
            if result:
                return result
    return None


def _format_steps(recipe_instructions: Any) -> str | None:
    """Format recipe instructions from JSON-LD into a plain text string."""
    if not recipe_instructions:
        return None
    
    if isinstance(recipe_instructions, str):
        return recipe_instructions
    
    if isinstance(recipe_instructions, list):
        steps = []
        for item in recipe_instructions:
            if isinstance(item, str):
                steps.append(item)
            elif isinstance(item, dict):
                # Could be TextObject or HowToStep
                text = item.get("text", "") or item.get("@value", "")
                if text:
                    steps.append(text)
        return "\n".join(steps) if steps else None
    
    return None


def _parse_duration(iso_duration: str | None) -> int | None:
    """Parse ISO 8601 duration (PT30M, PT1H30M, P1D) to minutes."""
    if not iso_duration:
        return None
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_duration)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes
