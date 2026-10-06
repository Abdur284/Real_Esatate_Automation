"""
Entry point for the 3D Design module.

Pipeline:
    prompt -> requirement extraction -> plot validation -> space planning
    -> feasibility -> 3D geometry -> geometry validation -> model

Callers (the REST endpoint and the centralized chatbot) use generate_3d_model
and never touch the stages directly. Ordinary bad input comes back as a
structured status rather than an exception so it can be shown to the user.
"""
import logging
from typing import Any, Dict, List, Optional

from .layout import (
    FRONT_SETBACK_FT,
    MAX_STOREYS,
    REAR_SETBACK_FT,
    compute_footprint,
    plan_storeys,
    validate_plot,
)
from .model_builder import (
    STOREY_PITCH_FT,
    WALL_HEIGHT_FT,
    build_model,
)
from .requirements import extract_requirements

logger = logging.getLogger(__name__)


def _overlaps(a: Dict, b: Dict) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"] + 1e-6 or
        b["x"] + b["width"] <= a["x"] + 1e-6 or
        a["y"] + a["depth"] <= b["y"] + 1e-6 or
        b["y"] + b["depth"] <= a["y"] + 1e-6
    )


def validate_model(model: Dict) -> List[str]:
    """Geometry safety net. The packer should make all of these impossible;
    if one ever fires the model is withheld rather than shown to the user."""
    errors: List[str] = []
    width = model["footprint"]["width_ft"]
    depth = model["footprint"]["depth_ft"]

    for storey in model["storeys"]:
        rooms = storey["rooms"]
        for room in rooms:
            if room["x"] < -1e-6 or room["y"] < -1e-6:
                errors.append(f"{room['label']} ({storey['label']}) starts outside the footprint.")
            if room["x"] + room["width"] > width + 1e-6 or room["y"] + room["depth"] > depth + 1e-6:
                errors.append(f"{room['label']} ({storey['label']}) extends outside the footprint.")
            if room["width"] <= 0 or room["depth"] <= 0:
                errors.append(f"{room['label']} ({storey['label']}) has a non-positive dimension.")

        for i in range(len(rooms)):
            for j in range(i + 1, len(rooms)):
                if _overlaps(rooms[i], rooms[j]):
                    errors.append(
                        f"{rooms[i]['label']} overlaps {rooms[j]['label']} on {storey['label']}."
                    )

        for wall in storey["walls"]:
            for cx in (wall["x1"], wall["x2"]):
                if cx < -1e-6 or cx > width + 1e-6:
                    errors.append(f"Wall {wall['id']} on {storey['label']} leaves the footprint.")
            for cy in (wall["y1"], wall["y2"]):
                if cy < -1e-6 or cy > depth + 1e-6:
                    errors.append(f"Wall {wall['id']} on {storey['label']} leaves the footprint.")
            for opening in wall["openings"]:
                half = opening["width"] / 2
                if opening["center"] - half < -1e-6 or opening["center"] + half > wall["length"] + 1e-6:
                    errors.append(f"An opening in wall {wall['id']} falls outside the wall.")
                if opening["sill"] + opening["height"] > wall["height"] + 1e-6:
                    errors.append(f"An opening in wall {wall['id']} is taller than the wall.")

    return errors


def _assumptions(footprint: Dict[str, float], storeys: int) -> List[str]:
    return [
        f"Setbacks assumed: front {FRONT_SETBACK_FT}ft, rear {REAR_SETBACK_FT}ft, "
        f"side {footprint['side_setback_ft']}ft each. These are generic residential planning "
        f"conventions, not any specific society's bylaws -- verify locally before construction.",
        f"Floor-to-floor height assumed at {STOREY_PITCH_FT}ft ({WALL_HEIGHT_FT}ft clear).",
        "Rooms are laid out in full-width bands, so partition walls stay aligned; "
        "room sizes may exceed the requested minimums where space allows.",
        f"This module models a maximum of {MAX_STOREYS} storeys and produces a conceptual "
        "massing model, not a construction drawing.",
    ]


def generate_3d_model(
    prompt: str,
    plot_width_ft: Optional[float] = None,
    plot_length_ft: Optional[float] = None,
    storeys: Optional[int] = None,
) -> Dict[str, Any]:
    """Runs the full pipeline and returns a JSON-serialisable result."""
    try:
        reqs = extract_requirements(prompt or "")
    except Exception as exc:  # defensive: extraction must never break the endpoint
        logger.error(f"3D requirement extraction failed: {exc}")
        return {
            "status": "ERROR",
            "message": "Could not interpret that request. Describe the plot size and the rooms "
                       "you need, for example \"25x50 ft plot, 3 bedrooms, 2 bathrooms, kitchen, "
                       "TV lounge, parking, double storey\".",
        }

    # Explicit fields from the form win over anything parsed out of the text.
    width = plot_width_ft if plot_width_ft is not None else reqs["plot"]["width_ft"]
    length = plot_length_ft if plot_length_ft is not None else reqs["plot"]["length_ft"]
    if storeys is not None:
        reqs["storeys_requested"] = max(1, min(int(storeys), MAX_STOREYS))

    base = {"requirements": reqs, "plot": {"width_ft": width, "length_ft": length}}

    problem = validate_plot(width, length)
    if problem == "MISSING_DIMENSIONS":
        base.update({
            "status": "MISSING_DIMENSIONS",
            "message": "No plot dimensions were found. Give the width and length in feet "
                       "(for example \"25 x 50 ft\") or a marla/kanal size.",
        })
        return base
    if problem == "INVALID_DIMENSIONS":
        base.update({
            "status": "INVALID_DIMENSIONS",
            "message": f"A plot of {width}x{length} ft cannot be modelled as a residential "
                       f"building. Each side must be between 12 and 400 ft.",
        })
        return base

    footprint = compute_footprint(width, length)
    plan = plan_storeys(reqs, footprint)

    if plan["status"] != "FEASIBLE":
        base.update({
            "status": plan["status"],
            "message": plan["message"],
            "suggestion": plan.get("suggestion"),
            "footprint": footprint,
            "assumptions": _assumptions(footprint, 0),
        })
        return base

    # The building occupies only the depth its rooms need; the rest of the
    # buildable area stays open as back garden.
    building_footprint = dict(footprint)
    building_footprint.update({
        "buildable_width_ft": footprint["width_ft"],
        "buildable_depth_ft": footprint["depth_ft"],
        "width_ft": plan["building"]["width_ft"],
        "depth_ft": plan["building"]["depth_ft"],
    })

    model = build_model(plan["floors"], building_footprint, {"width_ft": width, "length_ft": length})

    errors = validate_model(model)
    if errors:
        logger.error(f"3D geometry validation failed: {errors}")
        base.update({
            "status": "NOT_FEASIBLE",
            "message": "The generated geometry failed validation (" + "; ".join(errors[:3]) + ").",
            "suggestion": "Try adjusting the plot size or the number of rooms.",
            "footprint": footprint,
        })
        return base

    base.update({
        "status": "FEASIBLE",
        "message": f"Generated a {model['totals']['storeys']}-storey model with "
                   f"{model['totals']['covered_area_sqft']:g} sqft of covered area.",
        "model": model,
        "assumptions": _assumptions(footprint, model["totals"]["storeys"]),
    })
    return base
