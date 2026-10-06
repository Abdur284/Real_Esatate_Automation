"""
Shared Gemini access for the design modules.

One client, one retry/fallback policy: an overloaded model (503) is retried
with a short backoff, a model whose quota is used up (429) or that no longer
exists (404) is skipped in favour of the next one in the list, and anything
else is a real error. Free-tier quotas are counted per model, which is why a
list of fallbacks is useful at all.
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from google import genai

from app.core.config import settings

logger = logging.getLogger(__name__)

TRANSIENT_RETRIES = 2

client: Optional[genai.Client] = None
if settings.GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Gemini client init failed: {e}")


class GeminiUnavailable(Exception):
    """No configured model could answer (no key, quota used up, overloaded)."""


def model_list(configured: str, *fallbacks: str) -> List[str]:
    """Comma-separated setting, or GEMINI_MODEL followed by the fallbacks."""
    names = configured or ",".join((settings.GEMINI_MODEL,) + fallbacks)
    out: List[str] = []
    for name in (n.strip() for n in names.split(",")):
        if name and name not in out:
            out.append(name)
    return out


def _is_overloaded(err: Exception) -> bool:
    text = str(err).upper()
    return any(s in text for s in ("503", "UNAVAILABLE", "OVERLOADED"))


def _is_skippable(err: Exception) -> bool:
    text = str(err).upper()
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "NOT_FOUND" in text


async def generate(contents: Any, models: List[str], config: Dict[str, Any],
                   feature: str = "Gemini") -> Tuple[Any, str]:
    """Returns (response, model used) from the first model that answers."""
    if client is None:
        raise GeminiUnavailable("GEMINI_API_KEY is not configured.")
    last_error: Optional[Exception] = None
    for model in models:
        for attempt in range(TRANSIENT_RETRIES + 1):
            try:
                response = await client.aio.models.generate_content(
                    model=model, contents=contents, config=config)
                return response, model
            except Exception as e:
                last_error = e
                if _is_skippable(e):
                    logger.warning(f"{feature}: {model} unavailable (quota or not found), trying next model")
                    break
                if not _is_overloaded(e):
                    raise GeminiUnavailable(f"Gemini request failed: {e}")
                logger.warning(f"{feature}: {model} busy (attempt {attempt + 1})")
                if attempt < TRANSIENT_RETRIES:
                    await asyncio.sleep(2 * (attempt + 1))
    if last_error is not None and _is_skippable(last_error):
        raise GeminiUnavailable("The Gemini API quota is used up for every configured model. "
                                "Please try again later.")
    raise GeminiUnavailable("The AI model is busy right now, please try again in a minute.")


def parse_json(text: str) -> Dict[str, Any]:
    """Parses a JSON object, tolerating markdown fences around it."""
    text = (text or "").strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value is not an object")
    return data
