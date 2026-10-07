"""
Intent routing for the chatbot: which of the 5 modules a message is for, plus
simple structured parameters pulled out of the free text so downstream
modules (especially property_rec) receive location / type / budget / area.
"""
import re
from typing import Any, Dict, Optional

KNOWN_LOCATIONS = [
    "lahore", "karachi", "islamabad", "rawalpindi", "faisalabad", "multan",
    "bangalore", "pune", "mumbai", "hinjewadi", "whitefield", "andheri",
]
PROPERTY_TYPES = ["villa", "flat", "apartment", "house", "bungalow", "plot"]


def extract_entities(text: str) -> Dict[str, Any]:
    text_l = text.lower()
    params: Dict[str, Any] = {}

    for loc in KNOWN_LOCATIONS:
        if loc in text_l:
            params["location"] = loc
            break

    for ptype in PROPERTY_TYPES:
        if ptype in text_l:
            params["property_type"] = ptype
            break

    bhk_match = re.search(r'(\d+)\s*-?\s*bhk', text_l)
    if bhk_match:
        params["bhk"] = int(bhk_match.group(1))

    budget_match = re.search(r'(\d[\d,]*)\s*(lakh|lac|crore|million)', text_l)
    if budget_match:
        params["budget_value"] = budget_match.group(1).replace(",", "")
        params["budget_unit"] = budget_match.group(2)

    area_match = re.search(r'(\d[\d,]*)\s*(sqft|sq\s?ft|marla|kanal)', text_l)
    if area_match:
        params["area_value"] = area_match.group(1).replace(",", "")
        params["area_unit"] = area_match.group(2)

    return params


def rule_based_classification(text: str) -> Optional[str]:
    """Keyword router across the 5 modules. Returns None when nothing matches —
    caller routes that case to general_chat, which Gemini answers freely."""
    text = text.lower()
    if re.search(r'\b(2d|floor plan|blueprint|layout)\b', text):
        return "design_2d"
    if re.search(r'\b(3d|render|tour|visualization|walkthrough)\b', text):
        return "design_3d"
    if re.search(r'\b(interior|furniture|decor|color scheme|theme)\b', text):
        return "interior_design"
    if re.search(r'\b(cost|price|estimate|budget|worth|construction|marla|kanal|rate|expense)\b', text):
        return "cost_estimation"
    if re.search(r'\b(buy|rent|sale|propert|recommend|bhk|villa|flat|apartment)\b', text):
        return "property_rec"
    return None


async def classify_intent(user_message: str) -> Dict:
    text = user_message.lower().strip()
    params = extract_entities(user_message)

    module = rule_based_classification(text)
    if module:
        confidence = 0.95  # fixed sentinel for a deterministic keyword hit — not a measured
                            # probability
        method = "Keyword match"
    else:
        module = "general_chat"
        confidence = 0.0
        method = "No keyword match -> Gemini"

    # params is real entity data forwarded to downstream APIs — keep classification
    # metadata (method) out of it, in the response envelope instead.
    return {
        "module": module,
        "confidence": confidence,
        "extracted_params": params,
        "method": method,
        "reasoning": f"Classified via {method}"
    }
