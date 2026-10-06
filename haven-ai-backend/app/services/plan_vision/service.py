"""
Entry point for Layer 1: analyse an uploaded 2D floor-plan image.

Result statuses (ordinary problems are statuses, not exceptions, so they can
be shown to the user; only an unreadable/unsupported file raises ImageRejected):

    ANALYZED            plan extracted; the user reviews it before 3D
    NEEDS_DIMENSIONS    rooms were found but no scale is known; nothing is guessed
    DIMENSION_MISMATCH  the typed width/depth disagree with the drawing's proportions
    LOW_RESOLUTION      too few pixels to measure walls reliably
    NOT_A_FLOOR_PLAN    no closed wall layout could be found
"""
import copy
import logging
import time
from typing import Any, Dict, List, Optional

from app.services.design2d.validator import DESIGN_STATUSES, validate_plan

from . import segmentation, structure
from .image_io import (
    MIN_SIDE_PX,
    decode_image,
    extract_embedded_plan,
    rotate_front_to_bottom,
    sniff_image,
)

logger = logging.getLogger(__name__)

FRONT_SIDES = ("bottom", "top", "left", "right")
MAX_OPENING_FT = 5.0          # widest gap still bridged as a door/window
MIN_ROOM_SQFT = 9.0
MIN_ROOM_SIDE_FT = 2.0
MIN_PX_PER_FT = 2.0           # below this a wall is under a pixel or two wide
WARN_PX_PER_FT = 4.0
MISMATCH_BLOCK = 0.15         # typed proportions vs drawing
MISMATCH_WARN = 0.05
REVIEW_CONFIDENCE = 0.6
DIMENSION_LIMITS_FT = (8.0, 400.0)

UNREADABLE_MESSAGE = ("We couldn't find a floor-plan layout in this image. Upload a clear, top-down plan "
                      "drawing with dark walls on a light background (not a photo or 3D render).")


def _clamp(v: float) -> float:
    return round(max(0.0, min(1.0, v)), 2)


def _valid_dim(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    lo, hi = DIMENSION_LIMITS_FT
    return float(v) if lo <= float(v) <= hi else None


def _embedded_result(plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A plan exported by HAVEN's 2D module: exact data, still re-validated."""
    plan = copy.deepcopy(plan)
    if plan.get("status") not in DESIGN_STATUSES:
        return None
    report = validate_plan(plan)
    if any("outside" in e or "overlaps" in e or "numeric" in e or "non-positive" in e or "plot." in e
           for e in report["errors"]):
        return None
    plan["source"] = "embedded_plan"
    floors = plan.get("design", {}).get("floors")
    rooms = sum(len(plan["design"].get(f, {}).get(s) or [])
                for f in ("ground_floor", "first_floor") for s in ("rooms", "circulation", "open_spaces"))
    return {
        "status": "ANALYZED",
        "message": "This image is a floor plan exported from HAVEN AI, so its exact room layout, "
                   "doors and windows were read directly instead of estimated from pixels.",
        "plan": plan,
        "analysis": {
            "method": "embedded_plan",
            "confidence": {"walls": 1.0, "rooms": 1.0, "openings": 1.0, "dimensions": 1.0,
                           "room_types": 1.0, "overall": 1.0},
            "review_required": False,
            "explicit": ["Plot size, every room's position and size, doors and windows (stored in the file)"],
            "detected": [], "inferred": [], "missing": [],
            "warnings": report["warnings"][:5],
            "counts": {"rooms": rooms, "floors": floors},
        },
    }


def analyze_floor_plan(data: bytes, width_ft: Optional[float] = None, depth_ft: Optional[float] = None,
                       front: str = "bottom") -> Dict[str, Any]:
    started = time.perf_counter()
    sniff_image(data)
    embedded = extract_embedded_plan(data)
    if embedded is not None:
        result = _embedded_result(embedded)
        if result:
            return result
        logger.info("Embedded HAVEN plan failed validation; falling back to image analysis.")

    img = decode_image(data)
    orig_h, orig_w = img.shape[:2]
    if min(orig_h, orig_w) < MIN_SIDE_PX:
        return {"status": "LOW_RESOLUTION",
                "message": f"The image is only {orig_w}×{orig_h} px. Upload a floor plan at least "
                           f"{MIN_SIDE_PX} px on each side so walls and doors can be measured."}

    front = front if front in FRONT_SIDES else "bottom"
    img = rotate_front_to_bottom(img, front)
    bgr, gray, factor = segmentation.prepare(img)
    wall = segmentation.detect_walls(gray)
    if wall is None:
        return {"status": "NOT_A_FLOOR_PLAN", "message": UNREADABLE_MESSAGE}
    bx, by, bw, bh = wall["bbox"]
    shell_fill = float(wall["walls"][by:by + bh, bx:bx + bw].mean()) if bw and bh else 1.0
    too_thick = wall["stroke_p95_px"] > 1.5 * max(wall["thickest_wall_px"], wall["exterior_thickness_px"]) + 3
    if bw < 60 or bh < 60 or wall["straightness"] < 0.55 or shell_fill > 0.35 or too_thick:
        return {"status": "NOT_A_FLOOR_PLAN", "message": UNREADABLE_MESSAGE}

    aspect = bw / bh
    width_ft, depth_ft = _valid_dim(width_ft), _valid_dim(depth_ft)
    warnings: List[str] = []
    explicit: List[str] = []

    if width_ft is None and depth_ft is None:
        # Rooms are still counted so the user knows the drawing was understood,
        # but no size is guessed: the scale must come from the user.
        # With no scale the widest door is unknown, so the gap limit grows
        # (as a share of the building's short side) until the shell closes.
        for share in (0.12, 0.18, 0.25, 0.32):
            seg = segmentation.segment_rooms(bgr, gray, wall, share * min(bw, bh),
                                             0.004 * bw * bh, 0.03 * min(bw, bh))
            if seg["rooms"] and seg["outside_share"] < 0.5:
                break
        if not seg["rooms"]:
            return {"status": "NOT_A_FLOOR_PLAN", "message": UNREADABLE_MESSAGE}
        return {
            "status": "NEEDS_DIMENSIONS",
            "message": "Unable to confidently detect the floor-plan dimensions (printed measurements are "
                       "not read from images). Please enter the overall width and/or depth of the drawn "
                       "plan in feet, measured outside wall to outside wall.",
            "analysis": {"method": "computer_vision",
                         "counts": {"rooms": len(seg["rooms"])},
                         "layout_aspect_ratio": round(aspect, 3),
                         "hint": f"The drawing is {aspect:.2f}× as wide as it is deep: for example, a "
                                 f"25 ft wide plan would be about {25 / aspect:.1f} ft deep."},
        }

    if width_ft is not None and depth_ft is not None:
        sx, sy = bw / width_ft, bh / depth_ft
        mismatch = abs(aspect / (width_ft / depth_ft) - 1)
        if mismatch > MISMATCH_BLOCK:
            return {
                "status": "DIMENSION_MISMATCH",
                "message": f"The dimensions you entered ({width_ft:g} × {depth_ft:g} ft, ratio "
                           f"{width_ft / depth_ft:.2f}) don't match the drawing's proportions (ratio "
                           f"{aspect:.2f}). Check that width is left-to-right with the road at the "
                           f"'{front}' of the image, or enter only one dimension.",
                "analysis": {"method": "computer_vision", "layout_aspect_ratio": round(aspect, 3)},
            }
        if mismatch > MISMATCH_WARN:
            warnings.append(f"The drawing's proportions differ from the entered dimensions by "
                            f"{mismatch * 100:.0f}%; width and depth were scaled separately to match them.")
        explicit.append(f"Overall size {width_ft:g} × {depth_ft:g} ft (entered by you)")
        dim_conf = 1.0 - mismatch
    else:
        s = bw / width_ft if width_ft is not None else bh / depth_ft
        sx = sy = s
        if width_ft is None:
            width_ft = round(bw / s, 2)
            explicit.append(f"Overall depth {depth_ft:g} ft (entered by you)")
            warnings.append(f"Width {width_ft:g} ft was derived from the drawing's proportions.")
        else:
            depth_ft = round(bh / s, 2)
            explicit.append(f"Overall width {width_ft:g} ft (entered by you)")
            warnings.append(f"Depth {depth_ft:g} ft was derived from the drawing's proportions.")
        dim_conf = 0.9

    ppf = min(sx, sy)
    if ppf < MIN_PX_PER_FT:
        return {"status": "LOW_RESOLUTION",
                "message": f"At these dimensions the image has only {ppf:.1f} pixels per foot, too few to "
                           f"measure walls and doors. Upload a larger or sharper image of the plan."}
    if ppf < WARN_PX_PER_FT:
        warnings.append(f"Low resolution ({ppf:.1f} px per foot): small rooms and openings may be missed.")

    seg = segmentation.segment_rooms(bgr, gray, wall, MAX_OPENING_FT * max(sx, sy),
                                     MIN_ROOM_SQFT * sx * sy, MIN_ROOM_SIDE_FT * ppf)
    if not seg["rooms"]:
        return {"status": "NOT_A_FLOOR_PLAN",
                "message": "Walls were found, but no enclosed rooms. The outer wall may be broken or the "
                           "drawing may not be a floor plan. Try a clearer image."}

    plan, report = structure.build_plan(seg, wall, sx, sy, width_ft, depth_ft)
    warnings += report["warnings"]
    if seg["outside_share"] > 0.2:
        warnings.append("Part of the drawn area connects to the outside: the building may be L-shaped, "
                        "or an outer wall has an opening wider than a door.")
    if seg["rejected_regions"]:
        warnings.append(f"{seg['rejected_regions']} very small enclosed area(s) (shafts, cupboards or "
                        f"drawing artefacts) were ignored.")

    fits = [r["coverage"] for r in seg["rooms"]]
    wall_conf = _clamp(0.6 * wall["straightness"] + 0.4 * (1 - min(1.0, seg["outside_share"] * 2)))
    room_conf = _clamp(sum(fits) / len(fits) - 0.05 * min(4, seg["rejected_regions"]))
    open_conf = report["opening_confidence"] if report["opening_confidence"] is not None else 0.5
    type_conf = _clamp(report["typed_rooms"] / max(1, report["distinct_rooms"]))
    overall = _clamp(0.35 * wall_conf + 0.35 * room_conf + 0.15 * open_conf + 0.15 * dim_conf)

    inferred, missing = [], ["Printed room names and dimension text (text is not read from images)",
                             "Furniture (only its presence is noted)", "Upper floors (one image = one floor)"]
    if report["typed_rooms"]:
        inferred.append(f"{report['typed_rooms']} room type(s) from HAVEN's colour legend or stair hatching")
    if report["distinct_rooms"] > report["typed_rooms"]:
        missing.append(f"The type of {report['distinct_rooms'] - report['typed_rooms']} room(s) — "
                       f"name them in the review")
    inferred.append("Door vs. window for each wall gap (from what is drawn inside the gap)")
    if report["interior_wall_thickness_ft"]:
        inferred.append(f"Wall thickness: {report['exterior_wall_thickness_ft'] * 12:.1f} in outside, "
                        f"{report['interior_wall_thickness_ft'] * 12:.1f} in inside (measured)")
    inferred.append("Wall height, door and window heights (standard defaults, not in a 2D plan)")

    review = overall < REVIEW_CONFIDENCE or report["typed_rooms"] < report["distinct_rooms"]
    logger.info("Floor plan analysed in %.2fs: %s", time.perf_counter() - started, report)
    return {
        "status": "ANALYZED",
        "message": f"Found {report['distinct_rooms']} room(s), {report['doors']} door(s) and "
                   f"{report['windows']} window(s). Review the result before generating the 3D model.",
        "plan": plan,
        "analysis": {
            "method": "computer_vision",
            "confidence": {"walls": wall_conf, "rooms": room_conf, "openings": _clamp(open_conf),
                           "dimensions": _clamp(dim_conf), "room_types": type_conf, "overall": overall},
            "review_required": review,
            "low_confidence": overall < REVIEW_CONFIDENCE,
            "detected": [f"{len(plan['walls'])} wall segment(s)",
                         f"{report['distinct_rooms']} enclosed room(s)",
                         f"{report['doors']} door(s), {report['windows']} window(s)"]
                        + ([f"{report['stairs']} staircase(s)"] if report["stairs"] else []),
            "explicit": explicit,
            "inferred": inferred,
            "missing": missing,
            "warnings": warnings,
            "counts": {k: report[k] for k in ("rooms", "distinct_rooms", "doors", "windows", "stairs")},
            "image": {"width_px": orig_w, "height_px": orig_h, "analysed_scale": round(factor, 3),
                      "px_per_ft": [round(sx / factor, 2), round(sy / factor, 2)], "front": front},
            "layout_aspect_ratio": round(aspect, 3),
        },
    }
