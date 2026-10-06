"""
Requirement extraction for the 3D Design module.

Deliberately regex/keyword based rather than LLM based: rules.md 5.3 requires
that anything calculable deterministically is calculated by application logic,
not guessed by a model. Every number that drives the generated geometry
(plot size, room counts, storeys) originates here, so it must be reproducible
and testable without any AI service being reachable.
"""
import re
from typing import Any, Dict, Optional

# Minimum practical room sizes in feet (width x depth). These are conventional
# planning sizes for small/mid residential construction, not a legal standard.
ROOM_SPECS = {
    "bedroom":     (10.0, 12.0),
    "bathroom":    (5.0, 8.0),
    "kitchen":     (8.0, 10.0),
    "drawing_room": (12.0, 14.0),
    "tv_lounge":   (12.0, 14.0),
    "store_room":  (5.0, 6.0),
    "stairs":      (4.0, 10.0),
    "parking":     (10.0, 18.0),
}

ROOM_LABELS = {
    "bedroom": "Bedroom",
    "bathroom": "Bathroom",
    "kitchen": "Kitchen",
    "drawing_room": "Drawing Room",
    "tv_lounge": "TV Lounge",
    "store_room": "Store Room",
    "stairs": "Staircase",
    "parking": "Car Parking",
}

# Typical dimensions for standard plot sizes. These vary by society and city,
# so they are only used when the user gives a marla/kanal figure without
# explicit dimensions, and the result is flagged as estimated.
MARLA_TYPICAL_DIMS_FT = {
    3: (22.5, 30.0),
    5: (25.0, 45.0),
    8: (30.0, 60.0),
    10: (35.0, 65.0),
    20: (50.0, 90.0),
}


def _closest_marla_dims(marla: float):
    keys = sorted(MARLA_TYPICAL_DIMS_FT)
    closest = min(keys, key=lambda k: abs(k - marla))
    w, l = MARLA_TYPICAL_DIMS_FT[closest]
    if marla > 0 and closest != marla:
        scale = (marla / closest) ** 0.5
        w, l = round(w * scale, 1), round(l * scale, 1)
    return w, l


def _parse_plot(text: str) -> Dict[str, Any]:
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:x|X|×|by)\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot)?', text)
    if m:
        return {"width_ft": float(m.group(1)), "length_ft": float(m.group(2)),
                "estimated": False, "source": "explicit_dimensions"}

    m = re.search(r'(\d+(?:\.\d+)?)\s*marla', text, re.IGNORECASE)
    if m:
        marla = float(m.group(1))
        w, l = _closest_marla_dims(marla)
        return {"width_ft": w, "length_ft": l, "estimated": True, "source": f"{marla}_marla_typical"}

    m = re.search(r'(\d+(?:\.\d+)?)\s*kanal', text, re.IGNORECASE)
    if m:
        kanal = float(m.group(1))
        w, l = _closest_marla_dims(kanal * 20)
        return {"width_ft": w, "length_ft": l, "estimated": True, "source": f"{kanal}_kanal_typical"}

    return {"width_ft": None, "length_ft": None, "estimated": False, "source": None}


def _parse_storeys(text: str) -> Optional[int]:
    t = text.lower()
    # Capped at 2 everywhere: this module never models a third storey.
    if re.search(r'\b(triple|three)[\s-]?stor(e?y|ies)\b', t):
        return 2
    if re.search(r'\b(double|two|2)[\s-]?stor(e?y|ies)\b', t):
        return 2
    if re.search(r'\b(single|one|1)[\s-]?stor(e?y|ies)\b', t):
        return 1
    m = re.search(r'\b(\d+)\s*stor(e?y|ies)\b', t)
    if m:
        return min(int(m.group(1)), 2)
    if 'ground floor' in t and ('first floor' in t or 'upper floor' in t):
        return 2
    return None


def _count_before(text: str, patterns: list) -> Optional[int]:
    for pattern in patterns:
        m = re.search(r'(\d+)\s*[- ]?' + pattern, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def extract_requirements(prompt: str) -> Dict[str, Any]:
    """Free text -> structured requirements. Never raises; missing values come
    back as None/0/False so the caller decides how to handle ambiguity."""
    text = prompt or ""
    plot = _parse_plot(text)

    bedrooms = _count_before(text, [r'bed\s*rooms?', r'bhk'])
    if bedrooms is None:
        bedrooms = 1 if re.search(r'\bbed\s*room\b', text, re.IGNORECASE) else 0

    bathrooms = _count_before(text, [r'bath\s*rooms?', r'wash\s*rooms?', r'toilets?'])
    if bathrooms is None:
        bathrooms = 1 if re.search(r'\b(bath\s*room|wash\s*room|toilet)\b', text, re.IGNORECASE) else 0

    kitchens = _count_before(text, [r'kitchens?'])
    if kitchens is None:
        kitchens = 1 if re.search(r'\bkitchen\b', text, re.IGNORECASE) else 0

    return {
        "plot": {
            "width_ft": plot["width_ft"],
            "length_ft": plot["length_ft"],
            "size_is_estimated": plot["estimated"],
            "size_source": plot["source"],
        },
        "storeys_requested": _parse_storeys(text),
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "kitchens": kitchens,
        "drawing_room": bool(re.search(r'\b(drawing room|sitting room|guest room)\b', text, re.IGNORECASE)),
        "tv_lounge": bool(re.search(r'\b(tv lounge|family lounge|family room|living room|lounge)\b', text, re.IGNORECASE)),
        "store_room": bool(re.search(r'\bstore\s*room\b', text, re.IGNORECASE)),
        "parking": bool(re.search(r'\b(parking|garage|car ?port)\b', text, re.IGNORECASE)),
        "stairs_mentioned": bool(re.search(r'\bstair(s|case)?\b', text, re.IGNORECASE)),
        "raw_prompt": text,
    }
