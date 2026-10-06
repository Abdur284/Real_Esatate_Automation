"""
Image mode for the 3D Design module:

    photo + text + form
      -> upload checks (type by content, size)
      -> photo analysis, by DESIGN3D_PHOTO_ANALYZER:
           "builtin" (default): photo_analyzer.py measures quality and colours
             from a small pixel grid; floors/windows come from the form;
             modification_parser.py reads the requested changes by rules
           "gemini": Gemini vision describes the photo and the request
      -> clarification gate (unusable photo, ambiguous or structural request,
         missing plot dimensions)
      -> deterministic 3D model: the text-mode room planner when rooms were
         requested, otherwise an exterior shell (the photo cannot show rooms)
      -> facade.py applies the proposed front elevation, balconies, colours
      -> optional photorealistic render (Gemini analyser only)

The photo is a reference, never a blueprint: every dimension comes from the
user, and the response lists what was observed separately from what could not
be determined.
"""
import base64
import logging
from typing import Any, Dict, List, Optional

from google.genai import types

from app.core.config import settings
from app.services import gemini
from .facade import apply_facade, build_appearance
from .layout import MAX_STOREYS, compute_footprint, validate_plot
from .model_builder import build_model
from .modification_parser import parse_modifications
from .photo_analyzer import PixelsRejected, analyze_pixels, decode_pixels, palette_summary
from .reference_prompt import REFERENCE_SYSTEM_PROMPT
from .requirements import extract_requirements
from .service import generate_3d_model, validate_model

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PROMPT_LEN = 3000

VISION_MODELS = gemini.model_list(settings.GEMINI_VISION_MODELS,
                                  "gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash-lite")
IMAGE_MODELS = gemini.model_list(settings.GEMINI_IMAGE_MODELS)


class ImageRejected(ValueError):
    """The upload is not an acceptable image."""


def sniff_image(data: bytes) -> str:
    """Returns the MIME type from the file's content (never its name or the
    browser-supplied type), or raises ImageRejected."""
    if not data:
        raise ImageRejected("The uploaded file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageRejected(f"The image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ImageRejected("Only JPEG, PNG or WebP photos are accepted.")


def _form_text(width: Optional[float], length: Optional[float], storeys: Optional[int]) -> str:
    rows = []
    if width:
        rows.append(f"Plot width: {width:g} ft")
    if length:
        rows.append(f"Plot length: {length:g} ft")
    if storeys:
        rows.append(f"Requested storeys: {storeys}")
    return "\n".join(rows) or "(none given)"


async def analyze_reference(image: bytes, mime: str, prompt: str, width, length, storeys) -> Dict[str, Any]:
    text = (f"<user_request>\n{prompt or '(no text given)'}\n</user_request>\n\n"
            f"Property information from the form:\n{_form_text(width, length, storeys)}")
    response, model = await gemini.generate(
        [types.Part.from_bytes(data=image, mime_type=mime), text],
        VISION_MODELS,
        {"system_instruction": REFERENCE_SYSTEM_PROMPT,
         "response_mime_type": "application/json", "temperature": 0.2},
        feature="3D image analysis",
    )
    analysis = gemini.parse_json(response.text)
    analysis["_model"] = model
    return analysis


async def render_photo(image: bytes, mime: str, prompt: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Photorealistic render of the proposed design, edited from the user's
    photo. Image-generation models have no free-tier quota, so this reports
    `available: false` rather than failing the whole request."""
    proposed = analysis.get("proposed") or {}
    request = analysis.get("request") or {}
    changes = "; ".join(f"{m.get('element')}: {m.get('change')}"
                        for m in request.get("modifications") or [] if isinstance(m, dict))
    keep = "; ".join(str(p) for p in request.get("preserve") or [])
    instruction = (
        "Edit this photo of an existing house into a photorealistic architectural visualization of "
        "the proposed design. Keep the same camera viewpoint, plot, surroundings and overall building "
        "massing and proportions. Only change what is listed.\n"
        f"Requested changes: {changes or prompt or 'none'}\n"
        f"Keep: {keep or 'everything else'}\n"
        f"Style: {proposed.get('style') or 'as requested'}; facade finish: "
        f"{proposed.get('facade_cladding') or 'as existing'}; colours: {proposed.get('colors') or 'as existing'}.\n"
        "Realistic materials, daylight, soft shadows. No text, labels or watermarks."
    )
    try:
        response, model = await gemini.generate(
            [types.Part.from_bytes(data=image, mime_type=mime), instruction],
            IMAGE_MODELS, {"response_modalities": ["IMAGE", "TEXT"]}, feature="3D render")
    except gemini.GeminiUnavailable as e:
        reason = str(e)
        if "quota" in reason.lower():
            reason = ("Photorealistic rendering needs a Gemini image-generation model, which has no "
                      "free-tier quota. Enable billing on the Google Cloud project behind the API key "
                      "to use it.")
        return {"available": False, "reason": reason}
    for cand in response.candidates or []:
        for part in (cand.content.parts if cand.content else []) or []:
            if part.inline_data and part.inline_data.data:
                data = part.inline_data.data
                encoded = base64.b64encode(data).decode() if isinstance(data, bytes) else data
                return {"available": True, "model": model,
                        "image": f"data:{part.inline_data.mime_type or 'image/png'};base64,{encoded}",
                        "note": "AI-generated concept image based on your photo. It is not a measured "
                                "drawing and does not verify structure or dimensions."}
    return {"available": False, "reason": "The image model did not return an image."}


def _shell_floors(footprint: Dict[str, float], floors: int) -> List[List[Dict]]:
    """One enclosed volume per storey: the exterior is known from the photo,
    the rooms inside are not, so none are invented."""
    return [[{
        "id": f"r{level}_1", "type": "interior",
        "label": "Interior (layout not visible in photo)",
        "x": 0.0, "y": 0.0, "width": footprint["width_ft"], "depth": footprint["depth_ft"],
        "enclosed": True,
    }] for level in range(1, floors + 1)]


def _clarify(message: str, questions: List[Dict[str, Any]], base: Dict[str, Any]) -> Dict[str, Any]:
    base.update({"status": "NEEDS_CLARIFICATION", "message": message, "clarifications": questions})
    return base


def builtin_analysis(pixels: Dict[str, Any], prompt: str, floors: int,
                     existing: Dict[str, Any]) -> Dict[str, Any]:
    """Same result shape as the Gemini analysis, from local code only."""
    try:
        width, height = int(pixels.get("width") or 0), int(pixels.get("height") or 0)
        grid = decode_pixels(pixels.get("data", ""), width, height)
    except (PixelsRejected, TypeError, ValueError) as e:
        raise ImageRejected(f"The photo could not be read ({e}). Please choose it again.")
    measured = analyze_pixels(grid, width, height)
    quality = measured["quality"]
    parsed = parse_modifications(prompt, measured["colors"], floors, existing)

    windows = existing.get("front_windows")
    described = windows is not None or existing.get("garage_door") or existing.get("balcony")
    elevation = [{"level": lvl, "doors": 1 if lvl == 1 else 0, "windows": windows,
                  "garage_door": bool(existing.get("garage_door")) and lvl == 1,
                  "balcony": bool(existing.get("balcony")) and lvl == 2}
                 for lvl in range(1, floors + 1)] if described else []
    observed = {
        "building_type": "Existing property (floors and openings as described by you)",
        "visible_floors": floors, "floors_confidence": "provided by you",
        "front_elevation": elevation,
        "exterior_walls": palette_summary(measured["colors"]),
        "materials": [], "colors": measured["colors"],
        "architectural_style": None,
        "major_elements": [f"Photo quality: brightness {quality['brightness']}, contrast "
                           f"{quality['contrast']}, sharpness {quality['sharpness']}"],
        "palette": measured["palette"],
    }
    mods = parsed["request"]["modifications"]
    summary = (f"The built-in analyser measured the photo's colours (main wall colour "
               f"{measured['colors']['walls']}). "
               + (f"Requested changes: {', '.join(m['change'] for m in mods)}." if mods
                  else "No changes were requested, so the property is modelled as described."))
    return {
        "image_check": {"shows_property": True, "usable": quality["usable"],
                        "issue": " ".join(quality["issues"]) or None},
        "observed": observed,
        "not_determinable": [
            "plot and building dimensions",
            "interior layout",
            "structure and construction details",
            "exact positions and sizes of doors and windows",
            "roof type and materials (not detected by the built-in analyser)",
        ],
        "request": parsed["request"],
        "proposed": parsed["proposed"],
        "clarifications": parsed["clarifications"],
        "assumptions": ["Floors, windows, garage door and balcony come from the form; the built-in "
                        "analyser only measures photo quality and colours."] + parsed["assumptions"],
        "summary": summary,
        "_model": "built-in analyser (no AI service)",
    }


async def generate_3d_from_reference(
    image: bytes,
    prompt: str = "",
    plot_width_ft: Optional[float] = None,
    plot_length_ft: Optional[float] = None,
    storeys: Optional[int] = None,
    render: bool = False,
    pixels: Optional[Dict[str, Any]] = None,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    mime = sniff_image(image)
    use_gemini = settings.DESIGN3D_PHOTO_ANALYZER.lower() == "gemini"
    existing = existing or {}
    prompt = (prompt or "").strip()[:MAX_PROMPT_LEN]
    reqs = extract_requirements(prompt)

    width = plot_width_ft if plot_width_ft else reqs["plot"]["width_ft"]
    length = plot_length_ft if plot_length_ft else reqs["plot"]["length_ft"]
    requested_storeys = storeys or reqs.get("storeys_requested")

    missing_dims = {
        "question": "What are the plot's width and length in feet (or its size in marla/kanal)?",
        "reason": "A photo cannot show real dimensions, and the 3D model is built to scale.",
        "blocking": True}
    if width is None or length is None:
        # Asked before calling Gemini, so an incomplete request costs no quota.
        return _clarify("Some information is needed before the 3D design can be generated.",
                        [missing_dims], {"mode": "image", "plot": {"width_ft": width, "length_ft": length}})

    if use_gemini:
        analysis = await analyze_reference(image, mime, prompt, width, length, requested_storeys)
    else:
        if not requested_storeys:
            return _clarify("Some information is needed before the 3D design can be generated.",
                            [{"question": "How many floors does the property have (single or double storey)?",
                              "reason": "The built-in analyser does not count floors from the photo.",
                              "blocking": True}],
                            {"mode": "image", "plot": {"width_ft": width, "length_ft": length}})
        analysis = builtin_analysis(pixels or {}, prompt, min(int(requested_storeys), MAX_STOREYS), existing)
    observed = analysis.get("observed") or {}
    proposed = analysis.get("proposed") or {}
    check = analysis.get("image_check") or {}
    reference = {
        "observed": observed,
        "not_determinable": analysis.get("not_determinable") or [],
        "request": analysis.get("request") or {},
        "proposed": proposed,
        "summary": analysis.get("summary") or "",
        "model": analysis.get("_model"),
    }
    base: Dict[str, Any] = {"mode": "image", "reference": reference,
                            "plot": {"width_ft": width, "length_ft": length}}

    # --- clarification gate -------------------------------------------------
    if not check.get("shows_property", True) or not check.get("usable", True):
        return _clarify("The photo could not be used as a reference for the property.",
                        [{"question": "Please upload a clear, well-lit photo of the front of the property.",
                          "reason": check.get("issue") or "The building is not clearly visible.",
                          "blocking": True}], base)

    questions = [q for q in analysis.get("clarifications") or [] if isinstance(q, dict)]
    blocking = [q for q in questions if q.get("blocking")]
    if blocking:
        return _clarify("Some information is needed before the 3D design can be generated.", blocking, base)

    problem = validate_plot(width, length)
    if problem:
        base.update({"status": "INVALID_DIMENSIONS",
                     "message": f"A plot of {width}x{length} ft cannot be modelled; each side must be "
                                f"between 12 and 400 ft."})
        return base

    observed_floors = observed.get("visible_floors")
    floors = requested_storeys or proposed.get("floors") or observed_floors or 1
    try:
        floors = int(floors)
    except (TypeError, ValueError):
        floors = 1
    if floors > MAX_STOREYS:
        base.update({"status": "NOT_FEASIBLE",
                     "message": f"The design needs {floors} storeys, but this module models at most "
                                f"{MAX_STOREYS} (ground + first floor).",
                     "suggestion": "Ask for a design of the ground and first floor only."})
        return base
    floors = max(1, floors)

    assumptions: List[str] = [
        "The photo was used as a visual reference only; no dimensions were measured from it.",
    ]
    assumptions += [str(a) for a in analysis.get("assumptions") or []]
    assumptions += [f"Not blocking: {q.get('question')}" for q in questions if not q.get("blocking")]

    # --- geometry (deterministic) -------------------------------------------
    has_rooms = any(reqs.get(k) for k in ("bedrooms", "bathrooms", "kitchens", "drawing_room",
                                          "tv_lounge", "store_room", "parking"))
    if has_rooms:
        result = generate_3d_model(prompt, width, length, floors)
        if result.get("status") != "FEASIBLE":
            result.update({"mode": "image", "reference": reference})
            return result
        model = result["model"]
        assumptions += result.get("assumptions", [])
        if model["totals"]["storeys"] != floors:
            assumptions.append(f"The requested rooms fit on {model['totals']['storeys']} storey(s), "
                               f"so the model has {model['totals']['storeys']}.")
    else:
        footprint = compute_footprint(width, length)
        footprint.update({"buildable_width_ft": footprint["width_ft"],
                          "buildable_depth_ft": footprint["depth_ft"]})
        model = build_model(_shell_floors(footprint, floors), footprint,
                            {"width_ft": width, "length_ft": length})
        assumptions.append(
            f"Building footprint assumed to fill the buildable area ({footprint['width_ft']:g} x "
            f"{footprint['depth_ft']:g} ft after front {footprint['front_setback_ft']:g} ft, rear "
            f"{footprint['rear_setback_ft']:g} ft and side {footprint['side_setback_ft']:g} ft setbacks). "
            f"The real depth is not visible in the photo - give it for an exact model.")
        assumptions.append("Rooms are not shown: the interior layout cannot be seen in a photo. "
                           "List the rooms you need (e.g. \"3 bedrooms, 2 bathrooms, kitchen\") to add them.")

    model["appearance"] = build_appearance(proposed)
    assumptions += apply_facade(model, proposed)
    if (observed.get("roof") or {}).get("type") in ("pitched", "mixed"):
        assumptions.append("The roof is drawn flat; pitched roofs are not modelled.")

    errors = validate_model(model)
    if errors:
        logger.error(f"Image-mode geometry validation failed: {errors}")
        base.update({"status": "NOT_FEASIBLE",
                     "message": "The generated geometry failed validation (" + "; ".join(errors[:3]) + ")."})
        return base

    base.update({
        "status": "FEASIBLE",
        "message": f"Generated a {model['totals']['storeys']}-storey 3D design from your photo"
                   + (" and requirements." if prompt else "."),
        "model": model,
        "assumptions": assumptions,
    })
    if render:
        base["render"] = (await render_photo(image, mime, prompt, analysis) if use_gemini else
                          {"available": False,
                           "reason": "Photorealistic rendering is switched off while the built-in analyser "
                                     "is used (it needs a Gemini image model)."})
    return base
