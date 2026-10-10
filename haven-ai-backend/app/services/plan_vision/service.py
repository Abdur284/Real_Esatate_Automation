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
from . import text as plan_text
from .image_io import (
    MIN_SIDE_PX,
    ImageRejected,
    decode_image,
    extract_embedded_plan,
    rotate_front_to_bottom,
    sniff_image,
)

logger = logging.getLogger(__name__)

FRONT_SIDES = ("bottom", "top", "left", "right")
MAX_OPENING_FT = 5.0          # widest gap normally bridged as a door/window
WIDE_OPENING_FT = (6.5, 8.0)  # tried when the shell stays open (wide windows, sliding doors)
MIN_ROOM_SQFT = 9.0
MIN_ROOM_SIDE_FT = 2.0
MIN_PX_PER_FT = 2.0           # below this a wall is under a pixel or two wide
WARN_PX_PER_FT = 4.0
MISMATCH_BLOCK = 0.15         # typed proportions vs drawing
MISMATCH_WARN = 0.05
REVIEW_CONFIDENCE = 0.6
TEXT_SCALE_WARN = 0.10        # typed dimensions vs printed room sizes
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


def _is_plan_shell(wall: Optional[Dict[str, Any]]) -> bool:
    """Walls that look like a drawn plan: straight strokes of wall thickness
    around a mostly empty interior (photos and renders are filled areas)."""
    if wall is None:
        return False
    bx, by, bw, bh = wall["bbox"]
    shell_fill = float(wall["walls"][by:by + bh, bx:bx + bw].mean()) if bw and bh else 1.0
    too_thick = wall["stroke_p95_px"] > 1.5 * max(wall["thickest_wall_px"], wall["exterior_thickness_px"]) + 3
    return not (bw < 60 or bh < 60 or wall["straightness"] < 0.55 or shell_fill > 0.35 or too_thick)


def _find_walls(gray) -> Optional[Dict[str, Any]]:
    """Solid (or closed outline) walls first; if that does not give a plan,
    walls drawn as two thin parallel lines (typical CAD exports)."""
    wall = segmentation.detect_walls(gray)
    if _is_plan_shell(wall):
        return wall
    double = segmentation.detect_walls(gray, double_lines=True)
    return double if _is_plan_shell(double) else wall


def looks_like_floor_plan(data: bytes) -> bool:
    """True when an image is a 2D floor-plan drawing (a HAVEN export, or
    straight walls enclosing at least two rooms). Used to stop a floor plan
    uploaded as a "property photo" from being treated as one."""
    try:
        if extract_embedded_plan(data) is not None:
            return True
        img = decode_image(data)
    except ImageRejected:
        return False
    if min(img.shape[:2]) < MIN_SIDE_PX:
        return False
    bgr, gray, _ = segmentation.prepare(img)
    wall = _find_walls(gray)
    if not _is_plan_shell(wall):
        return False
    bw, bh = wall["bbox"][2], wall["bbox"][3]
    for share in (0.12, 0.18, 0.25):
        seg = segmentation.segment_rooms(bgr, gray, wall, share * min(bw, bh),
                                         0.004 * bw * bh, 0.03 * min(bw, bh))
        if len(seg["rooms"]) >= 2 and seg["outside_share"] < 0.5:
            return True
    return False


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
    # Text is read on the upright image (OCR expects horizontal text) and its
    # boxes are then turned into the road-at-the-bottom frame.
    upright, _, _ = segmentation.prepare(img)
    text_items = plan_text.read_text(upright)
    if text_items is not None:
        text_items = plan_text.rotate_boxes(text_items, front, upright.shape[1], upright.shape[0])
    words = plan_text.classify(text_items) if text_items is not None else None
    img = rotate_front_to_bottom(img, front)
    bgr, gray, factor = segmentation.prepare(img)
    wall = _find_walls(gray)
    if wall is None:
        return {"status": "NOT_A_FLOOR_PLAN", "message": UNREADABLE_MESSAGE}
    if not _is_plan_shell(wall):
        return {"status": "NOT_A_FLOOR_PLAN", "message": UNREADABLE_MESSAGE}
    bx, by, bw, bh = wall["bbox"]

    aspect = bw / bh
    width_ft, depth_ft = _valid_dim(width_ft), _valid_dim(depth_ft)
    warnings: List[str] = []
    explicit: List[str] = []
    printed = None  # scale read from the dimensions printed on the drawing

    if words is not None and (words["pairs"] or words["singles"]):
        printed = _printed_scale(bgr, gray, wall, words)
    from_drawing = width_ft is None and depth_ft is None and printed is not None
    if from_drawing:
        width_ft, depth_ft = printed["width_ft"], printed["depth_ft"]

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
            "message": ("Unable to confidently detect the floor-plan dimensions: "
                        + ("no room sizes or overall dimensions could be read from the drawing. "
                           if words is not None else "text on the drawing could not be read. ")
                        + "Please enter the overall width and/or depth of the drawn plan in feet, "
                          "measured outside wall to outside wall."),
            "analysis": {"method": "computer_vision",
                         "counts": {"rooms": len(seg["rooms"])},
                         "text_read": _text_summary(words),
                         "layout_aspect_ratio": round(aspect, 3),
                         "hint": f"The drawing is {aspect:.2f}× as wide as it is deep: for example, a "
                                 f"25 ft wide plan would be about {25 / aspect:.1f} ft deep."},
        }

    if from_drawing:
        sx, sy = printed["sx"], printed["sy"]
        explicit.append(f"Overall size {width_ft:g} × {depth_ft:g} ft, read from the dimensions printed "
                        f"on the drawing ({printed['basis']})")
        dim_conf = printed["confidence"]
        if printed["confidence"] < 0.8:
            warnings.append("The scale comes from few or slightly inconsistent printed dimensions. "
                            "Check the overall size, or enter it to override.")
    elif width_ft is not None and depth_ft is not None:
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

    if printed and not from_drawing:
        # The user typed a size; cross-check it with the printed one.
        off = max(abs(printed["sx"] / sx - 1), abs(printed["sy"] / sy - 1))
        if off > TEXT_SCALE_WARN:
            warnings.append(f"The dimensions printed on the drawing suggest an overall size of about "
                            f"{printed['width_ft']:g} × {printed['depth_ft']:g} ft, which differs from the "
                            f"size entered by {off * 100:.0f}%. The entered size was used.")

    ppf = min(sx, sy)
    if ppf < MIN_PX_PER_FT:
        return {"status": "LOW_RESOLUTION",
                "message": f"At these dimensions the image has only {ppf:.1f} pixels per foot, too few to "
                           f"measure walls and doors. Upload a larger or sharper image of the plan."}
    if ppf < WARN_PX_PER_FT:
        warnings.append(f"Low resolution ({ppf:.1f} px per foot): small rooms and openings may be missed.")

    seg = segmentation.segment_rooms(bgr, gray, wall, MAX_OPENING_FT * max(sx, sy),
                                     MIN_ROOM_SQFT * sx * sy, MIN_ROOM_SIDE_FT * ppf)
    # A room behind a window wider than a door opens onto the outside and is
    # lost. Wider gap limits are tried then, but kept only if they find more
    # rooms: a wider limit can also fill a narrow room (a stair) solid.
    for wide_ft in WIDE_OPENING_FT:
        if seg["outside_share"] <= 0.15:
            break
        alt = segmentation.segment_rooms(bgr, gray, wall, wide_ft * max(sx, sy),
                                         MIN_ROOM_SQFT * sx * sy, MIN_ROOM_SIDE_FT * ppf)
        if (len(alt["rooms"]), -alt["outside_share"]) > (len(seg["rooms"]), -seg["outside_share"]):
            seg = alt
    if not seg["rooms"]:
        return {"status": "NOT_A_FLOOR_PLAN",
                "message": "Walls were found, but no enclosed rooms. The outer wall may be broken or the "
                           "drawing may not be a floor plan. Try a clearer image."}

    room_text = _room_text(words, seg)
    plan, report = structure.build_plan(seg, wall, sx, sy, width_ft, depth_ft, room_text)
    uncertain = _labels_contradict_rooms(words, room_text, orig_w, orig_h)
    if uncertain:
        return uncertain
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

    inferred = []
    missing = ["Furniture (only its presence is noted)", "Upper floors (one image = one floor)"]
    if words is None:
        missing.insert(0, "Printed room names and dimensions (text recognition is not installed on this server)")
    elif report["named_rooms"]:
        explicit.append(f"{report['named_rooms']} room name(s) read from the labels printed on the drawing")
    if room_text["unplaced"]:
        warnings.append("Label(s) " + ", ".join(f"'{t}'" for t in room_text["unplaced"][:6])
                        + " are not inside any enclosed room that was detected: a room may be open to "
                          "another, or a wall may be missing in the drawing.")
    if report["merged_labels"]:
        warnings.append(f"{report['merged_labels']} detected room(s) carry more than one printed name "
                        f"(an open-plan area, or a wall between them that was not detected).")
    if report["typed_rooms"] > report["named_rooms"]:
        inferred.append(f"{report['typed_rooms'] - report['named_rooms']} room type(s) from HAVEN's colour "
                        f"legend or stair hatching")
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
            "counts": {k: report[k] for k in ("rooms", "distinct_rooms", "named_rooms", "doors", "windows",
                                              "stairs")},
            "text_read": _text_summary(words),
            "image": {"width_px": orig_w, "height_px": orig_h, "analysed_scale": round(factor, 3),
                      "px_per_ft": [round(sx / factor, 2), round(sy / factor, 2)], "front": front},
            "layout_aspect_ratio": round(aspect, 3),
        },
    }


def _printed_scale(bgr, gray, wall, words) -> Optional[Dict[str, Any]]:
    """Pixels per foot from the dimensions printed on the drawing: room sizes
    inside rooms (each checked against the room's drawn proportions) and/or
    overall dimensions outside the building. Returns None when nothing usable
    was printed, so the caller asks the user instead of guessing."""
    bx, by, bw, bh = wall["bbox"]
    # A provisional segmentation (gap limit relative to the building, as when
    # no scale is known), only to find which room each size string is in.
    seg = None
    for share in (0.12, 0.18, 0.25):
        seg = segmentation.segment_rooms(bgr, gray, wall, share * min(bw, bh),
                                         0.004 * bw * bh, 0.03 * min(bw, bh))
        if seg["rooms"] and seg["outside_share"] < 0.5:
            break
    rooms = None
    if seg and seg["rooms"] and words["pairs"]:
        rooms = plan_text.scale_from_rooms(words["pairs"], seg["rooms"], seg["labels"], float(wall["k"]),
                                           seg["fixtures"])
    overall = plan_text.overall_from_singles(words["singles"], wall["bbox"], words["pairs"])

    candidates = []
    ow, od = overall["width_ft"], overall["depth_ft"]
    if ow or od:
        osx = bw / ow if ow else bh / od
        osy = bh / od if od else osx
        consistent = rooms is None or (abs(osx / rooms["sx"] - 1) < 0.08 and abs(osy / rooms["sy"] - 1) < 0.08)
        if consistent and (not (ow and od) or abs((bw / bh) / (ow / od) - 1) < 0.08):
            conf = 0.95 if rooms else (0.85 if ow and od else 0.7)
            candidates.append({"sx": osx, "sy": osy, "confidence": conf,
                               "basis": "overall dimensions" + (" checked against room sizes" if rooms else "")})
    if rooms:
        candidates.append({"sx": rooms["sx"], "sy": rooms["sy"], "confidence": rooms["confidence"],
                           "basis": f"{len(rooms['used'])} printed room size(s)"})
    if not candidates:
        return None
    best = max(candidates, key=lambda c: c["confidence"])
    sx, sy = best["sx"], best["sy"]
    # Drawings are almost always to one scale; a small x/y disagreement is
    # measurement noise, so it is averaged away.
    if abs(sx / sy - 1) < 0.05:
        sx = sy = (sx * sy) ** 0.5
    width, depth = round(bw / sx, 1), round(bh / sy, 1)
    if _valid_dim(width) is None or _valid_dim(depth) is None:
        return None
    return {"sx": bw / width, "sy": bh / depth, "width_ft": width, "depth_ft": depth,
            "confidence": best["confidence"], "basis": best["basis"]}


def _room_text(words, seg) -> Dict[str, Any]:
    """Room names and printed sizes, keyed by the segmentation's room label."""
    out: Dict[str, Any] = {"names": {}, "sizes": {}, "unplaced": []}
    if not words:
        return out
    room_ids = {r["label"] for r in seg["rooms"]}
    for lab in words["labels"]:
        rid = plan_text.region_at(seg["labels"], lab["box"], room_ids, seg["fixtures"])
        if rid is None:
            out["unplaced"].append(lab["text"])
        else:
            out["names"].setdefault(rid, []).append(lab)
    for p in words["pairs"]:
        rid = plan_text.region_at(seg["labels"], p["box"], room_ids, seg["fixtures"])
        if rid is not None:
            out["sizes"].setdefault(rid, []).append(p)
    return out


def _text_summary(words) -> Optional[Dict[str, Any]]:
    if words is None:
        return None
    return {"room_labels": [w["text"] for w in words["labels"]],
            "dimensions": [w["text"] for w in words["pairs"]] + [w["text"] for w in words["singles"]],
            "other": [w["text"] for w in words["other"]][:20]}


def _labels_contradict_rooms(words, room_text, width_px: int, height_px: int) -> Optional[Dict[str, Any]]:
    """The printed room names are an independent check on the traced walls:
    every name should sit in its own enclosed room. When many names fall
    outside every room, or several share one, the walls were not traced
    correctly, and building that layout would produce a different house, so
    the analysis stops and says so instead."""
    if not words or len(words["labels"]) < 3:
        return None
    unplaced = list(room_text["unplaced"])
    merged = [[t["name"] for t in names] for names in room_text["names"].values() if len(names) > 1]
    problems = len(unplaced) + sum(len(m) - 1 for m in merged)
    if problems < max(2, 0.25 * len(words["labels"])):
        return None
    details = []
    if unplaced:
        details.append("no closed room was found around " + ", ".join(unplaced[:8]))
    if merged:
        details.append("these ran together into one area: " + "; ".join(" + ".join(m) for m in merged[:4]))
    advice = ("Upload a larger, sharper image of the plan (this one is "
              f"{width_px}×{height_px} px; at least 1500 px across works best), ideally without furniture, "
              "or check that the walls between these rooms are drawn closed.")
    return {
        "status": "UNCERTAIN_LAYOUT",
        "message": "Unable to confidently identify the room layout, so no 3D model was built from it. "
                   f"The drawing names {len(words['labels'])} spaces, but " + "; ".join(details) + ". " + advice,
        "analysis": {"method": "computer_vision", "text_read": _text_summary(words),
                     "counts": {"named_spaces": len(words["labels"]), "unplaced_labels": len(unplaced),
                                "merged_labels": sum(len(m) - 1 for m in merged)}},
    }
