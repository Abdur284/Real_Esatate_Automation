"""
Gemini-vision floor-plan reader for POST /api/design/3d/analyze.

An alternative to the OpenCV pipeline in service.py, selected with
PLAN_ANALYZER=gemini. Gemini reads the uploaded 2D drawing and returns the
layout in the same schema the 2D Design module uses (validator.py), so the
reviewed plan can be sent straight to POST /api/design/3d/from-2d.

Nothing here trusts the model: the returned geometry is checked by the same
deterministic validator as a generated plan, with one repair round-trip, and
only an unreadable/unsupported file raises PlanImageRejected. Ordinary
problems (not a plan, no scale) are statuses, shown to the user.

This module deliberately has no OpenCV dependency: the whole point of the
Gemini path is to read plans on servers where OpenCV is not installed.
"""
import logging
from typing import Any, Dict, List, Optional

from google.genai import types

from app.core.config import settings
from app.services import gemini
from app.services.design2d.validator import validate_plan

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_REPAIR_ATTEMPTS = 1
FRONT_SIDES = ("bottom", "top", "left", "right")
DIMENSION_LIMITS_FT = (8.0, 400.0)

PLAN_MODELS = gemini.model_list(settings.GEMINI_PLAN_MODELS, "gemini-3.8-flash", "gemini-flash-latest")


class PlanImageRejected(ValueError):
    """The upload is not an acceptable image (-> HTTP 415)."""


def sniff_image(data: bytes) -> str:
    """MIME type from the file's content (never its name or declared type)."""
    if not data:
        raise PlanImageRejected("The uploaded file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise PlanImageRejected(f"The image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise PlanImageRejected("Only PNG, JPEG or WebP floor-plan images are accepted.")


SYSTEM_PROMPT = r"""
# FLOOR-PLAN READING SYSTEM PROMPT

## ROLE
You are an architectural floor-plan reader. You are given ONE image of a 2D
residential floor plan (a top-down line drawing, not a photo or 3D render) and,
optionally, its overall outside dimensions. Your job is to READ the drawing and
reproduce the EXISTING layout as structured data. You are not designing: do not
add, remove, resize or rearrange rooms. Reproduce what is actually drawn.

## WHAT TO READ
* The outer boundary (outside wall to outside wall).
* Every enclosed room: its position, size and, where a label is printed, its name and type.
* Doors and windows in each wall (an opening with a swing arc or a thin gap = door; a gap drawn with a thin/double line across it = window).
* A staircase (parallel treads / an up-arrow).
* Printed room names and dimension text, used to name rooms and to set the scale.

## SCALE AND ORIENTATION
* If overall width/length are supplied below, use them as plot.width_ft / plot.length_ft and scale every room to them.
* Otherwise read the scale from dimensions printed on the drawing (overall dimensions, or room sizes).
* If neither supplies a reliable scale, you MUST return status "INSUFFICIENT_INFORMATION" with the missing dimensions in analysis.missing_information. Never invent a scale or guess overall dimensions.
* The road / front of the plot is given below. Reorient the layout so the road is at the BOTTOM edge: origin (0,0) is the bottom-left corner, x runs left-to-right parallel to the road (0..plot.width_ft), y runs away from the road into the plot (0..plot.length_ft).

## ONE IMAGE = ONE FLOOR
Treat the image as a single floor. Use status "FEASIBLE" with design.floors = 1,
put every room in ground_floor, and leave first_floor lists empty. Only use two
floors if the single image unambiguously shows two separate floor plans.

## NOT A FLOOR PLAN
If the image is not a readable 2D floor plan (a photo, a 3D render, an elevation,
or no enclosed rooms can be made out), return status "NOT_FEASIBLE" and explain
why in analysis.reason. Do not fabricate a layout.

## OUTPUT (return ONE JSON object, no markdown, no comments)
{
  "plan": {
    "status": "FEASIBLE | INSUFFICIENT_INFORMATION | NOT_FEASIBLE",
    "plot": {"length_ft": 0, "width_ft": 0, "area_sqft": 0, "shape": "rectangular"},
    "requirements": {},
    "analysis": {"reason": "", "assumptions": [], "suggestions": [], "missing_information": []},
    "design": {
      "floors": 1,
      "ground_floor": {"rooms": [], "circulation": [], "open_spaces": []},
      "first_floor": {"rooms": [], "circulation": [], "open_spaces": []}
    },
    "preferences": {}
  },
  "reading": {
    "is_floor_plan": true,
    "scale_source": "provided_dimensions | printed_dimensions | none",
    "confidence": {"walls": 0.0, "rooms": 0.0, "openings": 0.0, "dimensions": 0.0, "room_types": 0.0, "overall": 0.0},
    "detected": [], "explicit": [], "inferred": [], "missing": [], "warnings": [], "notes": ""
  }
}

### plan.requirements
Leave requirements as an empty object {}. You are reading, not fulfilling a brief.

### Items (every entry in rooms / circulation / open_spaces)
{
  "name": "Bedroom 1", "type": "bedroom", "purpose": "",
  "x": 0, "y": 20, "width": 12, "length": 14,
  "approximate_dimensions_ft": {"length": 14, "width": 12},
  "position": "rear-left", "connections": [], "special_requirements": [],
  "doors": [], "windows": []
}
* type is one of: bedroom, master_bedroom, bathroom, kitchen, living_room,
  drawing_room, dining_room, tv_lounge, garage, parking, staircase, store,
  laundry, study, prayer_room, servant_room, guest_room, corridor, lobby,
  entrance, courtyard, lawn, terrace, balcony, setback, other. Use "other" when a
  room has no label and no clear type.
* x,y,width,length are in feet; approximate_dimensions_ft must equal width/length.
* Rectangles on a floor must not overlap (sharing an edge is fine) and must stay inside the plot.
* Round coordinates to at most one decimal place.

### Doors and windows
Each door/window: {"wall": "south|north|east|west", "offset_ft": 2, "width_ft": 3, "to": "Corridor"}
wall is the side of that room's rectangle (south = the y edge, north = the y+length edge,
west = the x edge, east = the x+width edge). offset_ft is measured from the wall's start.
"to" is for doors only; the main entrance door uses "to": "Outside".

### reading
Report what you actually saw. confidence values are 0..1. Put room names/sizes you
read from printed text in "explicit"; things you deduced (door vs window, a room's
type from its shape) in "inferred"; what you could not determine in "missing".

Return a single JSON object and nothing else.
"""


def _valid_dim(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    lo, hi = DIMENSION_LIMITS_FT
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi else None


def _user_text(width_ft: Optional[float], depth_ft: Optional[float], front: str) -> str:
    lines = [f"The road / front of the plot faces the '{front}' side of this image. "
             "Reorient the layout so the road is at the bottom (y = 0)."]
    w, d = _valid_dim(width_ft), _valid_dim(depth_ft)
    if w is not None:
        lines.append(f"Overall width (parallel to the road), outside wall to outside wall: {w:g} ft.")
    if d is not None:
        lines.append(f"Overall depth (away from the road), outside wall to outside wall: {d:g} ft.")
    if w is None and d is None:
        lines.append("No overall dimensions were supplied. Read the scale from dimensions printed on "
                     "the drawing; if none can be read, return status INSUFFICIENT_INFORMATION.")
    return "\n".join(lines)


async def _ask(image: bytes, mime: str, text: str) -> Dict[str, Any]:
    response, model = await gemini.generate(
        [types.Part.from_bytes(data=image, mime_type=mime), text],
        PLAN_MODELS,
        {"system_instruction": SYSTEM_PROMPT, "response_mime_type": "application/json",
         "temperature": 0.2},
        feature="Floor-plan reading",
    )
    if not response or not response.text:
        raise gemini.GeminiUnavailable(f"{model} returned an empty response.")
    data = gemini.parse_json(response.text)
    data["_model"] = model
    return data


def _counts(plan: Dict[str, Any]) -> Dict[str, int]:
    out = {"rooms": 0, "doors": 0, "windows": 0, "stairs": 0}
    floor = (plan.get("design") or {}).get("ground_floor") or {}
    for section in ("rooms", "circulation", "open_spaces"):
        for item in floor.get(section) or []:
            if not isinstance(item, dict):
                continue
            out["rooms"] += 1
            out["doors"] += len(item.get("doors") or [])
            out["windows"] += len(item.get("windows") or [])
            if str(item.get("type", "")).lower() == "staircase":
                out["stairs"] += 1
    return out


def _analysis_block(reading: Dict[str, Any], report: Dict[str, Any], model: str,
                    plan: Dict[str, Any], review: bool) -> Dict[str, Any]:
    conf = reading.get("confidence") or {}
    counts = _counts(plan)
    return {
        "method": "gemini_vision",
        "model": model,
        "confidence": {k: conf.get(k) for k in
                       ("walls", "rooms", "openings", "dimensions", "room_types", "overall")},
        "review_required": review,
        "low_confidence": (conf.get("overall") or 0) < 0.6,
        "scale_source": reading.get("scale_source"),
        "detected": [str(x) for x in reading.get("detected") or []]
                    or [f"{counts['rooms']} room(s), {counts['doors']} door(s), {counts['windows']} window(s)"],
        "explicit": [str(x) for x in reading.get("explicit") or []],
        "inferred": [str(x) for x in reading.get("inferred") or []]
                    + ["Door vs. window for each wall gap (from what is drawn in the gap)",
                       "Wall, door and window heights (standard defaults, not in a 2D plan)"],
        "missing": [str(x) for x in reading.get("missing") or []]
                   + ["Furniture (only its presence is noted)", "Upper floors (one image = one floor)"],
        "warnings": [str(x) for x in reading.get("warnings") or []] + list(report.get("warnings") or []),
        "counts": counts,
        "notes": reading.get("notes") or "",
    }


async def read_floor_plan(data: bytes, width_ft: Optional[float] = None,
                          depth_ft: Optional[float] = None, front: str = "bottom") -> Dict[str, Any]:
    """Reads a 2D floor-plan image with Gemini vision. Same result shape as
    service.analyze_floor_plan: a status plus (for ANALYZED) a `plan` in the 2D
    Design schema and an `analysis` block."""
    mime = sniff_image(data)
    front = front if front in FRONT_SIDES else "bottom"
    text = _user_text(width_ft, depth_ft, front)

    result = await _ask(data, mime, text)
    plan = result.get("plan") if isinstance(result.get("plan"), dict) else None
    reading = result.get("reading") if isinstance(result.get("reading"), dict) else {}
    model = result.get("_model", "")
    if plan is None:
        return {"status": "NOT_A_FLOOR_PLAN",
                "message": "The drawing could not be read. Upload a clear, top-down 2D floor plan."}

    status = str(plan.get("status") or "").upper()
    if status == "NOT_FEASIBLE" or reading.get("is_floor_plan") is False:
        reason = (plan.get("analysis") or {}).get("reason")
        return {"status": "NOT_A_FLOOR_PLAN",
                "message": reason or ("This image is not a readable 2D floor plan. Upload a clear, "
                                      "top-down plan drawing (not a photo, elevation or 3D render).")}
    if status == "INSUFFICIENT_INFORMATION":
        missing = (plan.get("analysis") or {}).get("missing_information") or []
        return {"status": "NEEDS_DIMENSIONS",
                "message": ("The drawing's scale could not be established"
                            + (": " + "; ".join(str(m) for m in missing) if missing else "")
                            + ". Please enter the overall width and/or depth of the drawn plan in feet, "
                              "measured outside wall to outside wall."),
                "analysis": {"method": "gemini_vision", "model": model,
                             "text_read": reading.get("explicit") or []}}

    # Geometry is validated like a generated plan, with one repair round-trip.
    report = validate_plan(plan)
    attempts = 1
    while not report["passed"] and attempts <= MAX_REPAIR_ATTEMPTS:
        logger.info("Gemini plan reader: repairing, errors: %s", report["errors"])
        repair = (text + "\n\nThe application's validator rejected your JSON:\n- "
                  + "\n- ".join(report["errors"])
                  + "\n\nReturn the corrected single JSON object (same {\"plan\", \"reading\"} shape). "
                    "Fix every listed problem by reading the drawing more carefully; do not invent rooms.")
        try:
            result = await _ask(data, mime, repair)
        except gemini.GeminiUnavailable:
            break
        plan = result.get("plan") if isinstance(result.get("plan"), dict) else plan
        reading = result.get("reading") if isinstance(result.get("reading"), dict) else reading
        model = result.get("_model", model)
        report = validate_plan(plan)
        attempts += 1

    plan["source"] = "gemini_vision"
    plan["validation"] = {**report, "attempts": attempts, "model": model}

    conf_overall = (reading.get("confidence") or {}).get("overall") or 0
    review = bool(not report["passed"] or conf_overall < 0.6)
    warnings: List[str] = list(report.get("warnings") or [])
    if not report["passed"]:
        warnings.append("Some geometry could not be fully validated after reading "
                        "(" + "; ".join(report["errors"][:3]) + "). Please check and correct it "
                        "in the review before generating the 3D model.")
        reading.setdefault("warnings", [])
        reading["warnings"] = list(reading["warnings"]) + warnings[-1:]

    counts = _counts(plan)
    return {
        "status": "ANALYZED",
        "message": f"Read {counts['rooms']} room(s), {counts['doors']} door(s) and "
                   f"{counts['windows']} window(s) from the drawing with Gemini vision. "
                   f"Review the result before generating the 3D model.",
        "plan": plan,
        "analysis": _analysis_block(reading, report, model, plan, review),
    }
