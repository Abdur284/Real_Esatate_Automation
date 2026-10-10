"""
Zameen.com listings, shown on the Properties page next to our own dealers'.

The browser never talks to Zameen: it calls /api/properties/external, and
this module calls Zameen with the API key kept on the server, turns each
result into our listing shape, and caches it for a few minutes so the page is
fast and stays inside Zameen's request limits.

ZAMEEN_API_URL in .env:
    (empty)  feature off: the page shows only our own listings
    MOCK     a few clearly-labelled sample listings, for building the UI
    https:// the real API (base URL from Zameen's documentation)

Zameen's API documentation was not available when this was written. Only
`_fetch_raw` (the request) and `normalize` (the field names) depend on it;
both say where to adjust once the documentation arrives.
"""
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_RESULTS = 60
SOURCE = "zameen"


class ZameenUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Filters:
    city: str = ""
    purpose: str = ""      # for-sale | for-rent | ""
    property_type: str = ""
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    beds: Optional[int] = None
    q: str = ""
    page: int = 1


# ---- the response shape our Properties page uses -----------------------------------

def _first(raw: Dict, *keys, default=None):
    """The first present, non-empty value among several possible field names
    (dots go into nested objects: "location.name")."""
    for key in keys:
        value: Any = raw
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value not in (None, "", []):
            return value
    return default


def _number(value) -> Optional[float]:
    try:
        return float(str(value).replace(",", "")) if value not in (None, "") else None
    except ValueError:
        return None


def _purpose(value) -> str:
    v = str(value or "").lower()
    return "for-rent" if "rent" in v else "for-sale"


def normalize(raw: Dict) -> Optional[Dict]:
    """One Zameen result -> our listing. ADJUST the field names here to match
    Zameen's documentation; several common spellings are already accepted."""
    ext_id = _first(raw, "id", "externalID", "external_id", "property_id")
    if ext_id is None:
        return None
    photo = _first(raw, "coverPhoto.url", "cover_photo", "image", "image_url", "photos.0")
    if isinstance(photo, list):
        photo = photo[0] if photo else None
    beds = _number(_first(raw, "rooms", "bedrooms", "beds"))
    baths = _number(_first(raw, "baths", "bathrooms"))
    area = _first(raw, "area_label", "area", "size")
    if isinstance(area, (int, float)):
        area = f"{area:g} {_first(raw, 'area_unit', default='sq ft')}"
    return {
        "id": f"{SOURCE}-{ext_id}",
        "source": SOURCE,
        "title": str(_first(raw, "title", "name", default="Property on Zameen.com"))[:150],
        "type": str(_first(raw, "category", "property_type", "type", default="house")).lower(),
        "status": _purpose(_first(raw, "purpose", "listing_type")),
        "price": _number(_first(raw, "price", "price_pkr")) or 0,
        "location": str(_first(raw, "location_name", "location.name", "location", "address", default="Pakistan")),
        "city": str(_first(raw, "city", "city_name", "location.city", default="")),
        "beds": int(beds) if beds else 0,
        "baths": int(baths) if baths else 0,
        "area": str(area) if area else "N/A",
        "description": str(_first(raw, "description", default=""))[:2000],
        "img": photo,
        "url": _first(raw, "url", "link", "permalink"),
        "agency": _first(raw, "agency.name", "agency_name", "agent_name"),
    }


# ---- talking to Zameen ------------------------------------------------------------

def _fetch_raw(f: Filters) -> List[Dict]:
    """Calls the real API. ADJUST the path, parameter names and auth header to
    Zameen's documentation."""
    params = {
        "city": f.city or None,
        "purpose": {"for-sale": "for-sale", "for-rent": "for-rent"}.get(f.purpose),
        "property_type": f.property_type or None,
        "price_min": f.min_price,
        "price_max": f.max_price,
        "beds": f.beds,
        "q": f.q or None,
        "page": f.page,
    }
    headers = {"Accept": "application/json"}
    if settings.ZAMEEN_API_KEY:
        headers["Authorization"] = f"Bearer {settings.ZAMEEN_API_KEY}"
    url = settings.ZAMEEN_API_URL.rstrip("/") + "/listings"
    try:
        r = httpx.get(url, params={k: v for k, v in params.items() if v is not None},
                      headers=headers, timeout=settings.ZAMEEN_TIMEOUT_SECONDS)
        r.raise_for_status()
        body = r.json()
    except Exception as e:
        logger.warning("Zameen request failed: %s", e)
        raise ZameenUnavailable("Zameen.com listings are not available right now.") from e
    hits = body if isinstance(body, list) else _first(body, "hits", "results", "data", "listings", default=[])
    return [h for h in hits if isinstance(h, dict)]


def _mock_raw(f: Filters) -> List[Dict]:
    samples = [
        {"id": "sample-1", "title": "[Sample] 10 Marla House, DHA Phase 6", "purpose": "for-sale", "category": "house",
         "price": 45_000_000, "location_name": "DHA Phase 6", "city": "Lahore", "rooms": 5, "baths": 6, "area_label": "10 Marla"},
        {"id": "sample-2", "title": "[Sample] 2 Bed Apartment, Bahria Town", "purpose": "for-rent", "category": "apartment",
         "price": 85_000, "location_name": "Bahria Town Phase 7", "city": "Rawalpindi", "rooms": 2, "baths": 2, "area_label": "1,050 sq ft"},
        {"id": "sample-3", "title": "[Sample] 5 Marla House, Johar Town", "purpose": "for-sale", "category": "house",
         "price": 21_500_000, "location_name": "Johar Town", "city": "Lahore", "rooms": 3, "baths": 4, "area_label": "5 Marla"},
        {"id": "sample-4", "title": "[Sample] 1 Kanal Villa, F-7", "purpose": "for-sale", "category": "villa",
         "price": 350_000_000, "location_name": "F-7", "city": "Islamabad", "rooms": 6, "baths": 7, "area_label": "1 Kanal"},
    ]
    return samples


# ---- filters and cache ------------------------------------------------------------

def _matches(item: Dict, f: Filters) -> bool:
    """Applied to every result too, so MOCK behaves like a real search and an
    API that ignores a parameter still shows the right listings."""
    if f.purpose and item["status"] != f.purpose:
        return False
    if f.property_type and item["type"] != f.property_type.lower():
        return False
    if f.city and f.city.lower() not in (item["city"] + " " + item["location"]).lower():
        return False
    if f.min_price is not None and item["price"] < f.min_price:
        return False
    if f.max_price is not None and item["price"] > f.max_price:
        return False
    if f.beds is not None and (item["beds"] < 4 if f.beds >= 4 else item["beds"] != f.beds):
        return False
    if f.q and f.q.lower() not in (item["title"] + " " + item["location"] + " " + item["city"]).lower():
        return False
    return True


_lock = threading.Lock()
_cache: Dict[Filters, Tuple[float, List[Dict]]] = {}


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def mode() -> str:
    url = (settings.ZAMEEN_API_URL or "").strip()
    return "off" if not url else "mock" if url.upper() == "MOCK" else "live"


def search(f: Filters) -> List[Dict]:
    current = mode()
    if current == "off":
        return []
    now = time.monotonic()
    with _lock:
        hit = _cache.get(f)
        if hit and now - hit[0] < settings.ZAMEEN_CACHE_SECONDS:
            return hit[1]
    raw = _mock_raw(f) if current == "mock" else _fetch_raw(f)
    items = [n for n in (normalize(r) for r in raw) if n and _matches(n, f)][:MAX_RESULTS]
    with _lock:
        if len(_cache) > 500:
            _cache.clear()
        _cache[f] = (now, items)
    return items
