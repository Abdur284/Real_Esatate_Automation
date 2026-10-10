import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.ratelimit import rate_limit
from app.services.design3d import model_store
from app.services.design3d.fidelity import check_glb
from app.services.design3d.from_plan2d import generate_3d_from_plan2d
from app.services.design3d.gltf_export import export_glb
from app.services.design3d.reference import (
    MAX_IMAGE_BYTES,
    ImageRejected,
    generate_3d_from_reference,
)
from app.services.gemini import GeminiUnavailable
from app.services.design3d.service import generate_3d_model

router = APIRouter()
logger = logging.getLogger(__name__)


def _with_glb(result: Dict[str, Any]) -> Dict[str, Any]:
    """Adds the GLB for a FEASIBLE result: structured JSON -> 3D geometry -> GLB.
    The model JSON stays in the response (it drives the properties panel and
    is the renderer-independent source of truth)."""
    if not isinstance(result, dict) or result.get("status") != "FEASIBLE" or not result.get("model"):
        return result
    try:
        data, metadata = export_glb(result["model"])
    except Exception:  # never lose the structured result because of the mesh
        logger.exception("GLB export failed")
        result["glb_error"] = "The 3D model file could not be generated from this design."
        return result
    if isinstance(result.get("validation"), dict):
        glb_check = check_glb(result["model"], metadata)
        result["validation"]["checks"].append(glb_check)
        if not glb_check["ok"]:
            result["validation"]["passed"] = False
            result["glb_error"] = "The 3D model file did not contain every room of the design."
            return result
    model_id = model_store.put(data)
    result["glb"] = {
        "model_url": f"/api/design/3d/models/{model_id}.glb",
        "format": "glb",
        "expires_in_s": model_store.TTL_SECONDS,
        "metadata": metadata,
    }
    return result


def _is_floor_plan(data: bytes) -> bool:
    try:
        from app.services.plan_vision.service import looks_like_floor_plan
    except ImportError:  # OpenCV missing: the photo path works as before
        return False
    try:
        return looks_like_floor_plan(data)
    except Exception:
        logger.exception("Floor-plan check failed")
        return False


class ModelRequest(BaseModel):
    prompt: str
    plot_width_ft: Optional[float] = None
    plot_length_ft: Optional[float] = None
    storeys: Optional[int] = None


@router.post("/generate", dependencies=[Depends(rate_limit("design3d"))])
async def generate(req: ModelRequest):
    """
    Generates a validated 3D building model from a natural-language brief
    and/or explicit plot dimensions.

    The response contains structured geometry (walls, openings, slabs, roof,
    stairs) in feet. Rendering is done by the client; no image or mesh is
    generated here.
    """
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=422, detail="`prompt` must not be empty.")
    # DESIGN3D_TEXT_GENERATOR=gemini has Gemini generate the 2D layout, which is
    # then built in 3D; the default "builtin" uses the local rule-based planner.
    if settings.DESIGN3D_TEXT_GENERATOR.lower() == "gemini":
        from app.services.design3d.gemini_generate import generate_3d_from_prompt
        try:
            return _with_glb(await generate_3d_from_prompt(
                prompt=req.prompt,
                plot_width_ft=req.plot_width_ft,
                plot_length_ft=req.plot_length_ft,
                storeys=req.storeys,
            ))
        except GeminiUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception:
            logger.exception("Gemini 3D model generation failed")
            raise HTTPException(status_code=500, detail="The 3D model could not be generated. Please try again.")
    try:
        return _with_glb(generate_3d_model(
            prompt=req.prompt,
            plot_width_ft=req.plot_width_ft,
            plot_length_ft=req.plot_length_ft,
            storeys=req.storeys,
        ))
    except Exception:
        logger.exception("3D model generation failed")
        raise HTTPException(status_code=500, detail="The 3D model could not be generated. Please try again.")


class FromPlan2DRequest(BaseModel):
    plan: Dict[str, Any]


@router.post("/from-2d", dependencies=[Depends(rate_limit("design3d"))])
async def from_2d(req: FromPlan2DRequest):
    """
    Builds a 3D model from a structured floor plan -- one returned by
    POST /api/design/2d/generate, or one read from an image by
    POST /api/design/3d/analyze and reviewed by the user -- keeping its exact
    room positions, doors and windows. The response includes a GLB model URL.
    """
    try:
        return _with_glb(generate_3d_from_plan2d(req.plan))
    except Exception:
        logger.exception("2D to 3D conversion failed")
        raise HTTPException(status_code=500, detail="This floor plan could not be converted to 3D. "
                                                    "Please check it and try again.")


@router.post("/generate-from-image", dependencies=[Depends(rate_limit("design3d"))])
async def generate_from_image(
    image: UploadFile = File(...),
    prompt: str = Form(""),
    plot_width_ft: Optional[float] = Form(None),
    plot_length_ft: Optional[float] = Form(None),
    storeys: Optional[int] = Form(None),
    render: bool = Form(False),
    pixels: str = Form(""),
    pixels_width: int = Form(0),
    pixels_height: int = Form(0),
    front_windows: Optional[int] = Form(None),
    garage_door: bool = Form(False),
    existing_balcony: bool = Form(False),
):
    """
    Generates a 3D design using a photo of the user's existing property as the
    reference, combined with the requested modifications and plot details.

    The photo is analysed in memory and never written to disk. It is checked
    by content (JPEG/PNG/WebP only, at most 8 MB); its filename and declared
    type are ignored. The status may be NEEDS_CLARIFICATION, with questions.

    With the built-in analyser (default) the browser also sends `pixels`, a
    base64 RGB grid of the photo at most 128 px a side, and the form's
    description of the existing facade (front windows per floor, garage door,
    balcony), since those are not detected automatically.
    """
    if front_windows is not None and not 0 <= front_windows <= 12:
        raise HTTPException(status_code=422, detail="`front_windows` must be between 0 and 12.")
    if storeys is not None and storeys not in (1, 2):
        raise HTTPException(status_code=422, detail="`storeys` must be 1 or 2.")
    data = await image.read(MAX_IMAGE_BYTES + 1)
    await image.close()
    # A floor plan uploaded here would otherwise be used as a facade photo and
    # a house would be built from the text brief instead of from the drawing.
    if await run_in_threadpool(_is_floor_plan, data):
        return {
            "status": "FLOOR_PLAN_DETECTED",
            "mode": "image",
            "message": "This image is a 2D floor plan, not a photo of a building. Floor plans are "
                       "reconstructed exactly (same rooms, walls, doors and windows) with "
                       "\"Upload 2D design\" instead.",
        }
    try:
        return _with_glb(await generate_3d_from_reference(
            image=data, prompt=prompt, plot_width_ft=plot_width_ft,
            plot_length_ft=plot_length_ft, storeys=storeys, render=render,
            pixels={"data": pixels, "width": pixels_width, "height": pixels_height},
            existing={"front_windows": front_windows, "garage_door": garage_door,
                      "balcony": existing_balcony},
        ))
    except ImageRejected as exc:
        raise HTTPException(status_code=415, detail=str(exc))
    except GeminiUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("Image-based 3D generation failed")
        raise HTTPException(status_code=500, detail="The 3D design could not be created from this photo. "
                                                    "Please try again.")


@router.post("/analyze", dependencies=[Depends(rate_limit("design3d"))])
async def analyze(
    image: UploadFile = File(...),
    width_ft: Optional[float] = Form(None),
    depth_ft: Optional[float] = Form(None),
    front: str = Form("bottom"),
):
    """
    Layer 1: reads a 2D floor-plan image (PNG/JPEG/WebP, max 8 MB, checked by
    content) and returns the structured floor plan in the 2D Design schema,
    with confidence scores and what was detected, entered, inferred or is
    missing. `width_ft`/`depth_ft` are the drawn plan's overall outside
    dimensions; without at least one the status is NEEDS_DIMENSIONS. `front`
    is the image side the road is on (bottom/top/left/right). The image is
    processed in memory and never stored.
    """
    if front not in ("bottom", "top", "left", "right"):
        raise HTTPException(status_code=422, detail="`front` must be bottom, top, left or right.")
    for name, value in (("width_ft", width_ft), ("depth_ft", depth_ft)):
        if value is not None and not 8 <= value <= 400:
            raise HTTPException(status_code=422, detail=f"`{name}` must be between 8 and 400 ft.")

    # PLAN_ANALYZER=gemini reads the drawing with Gemini vision (no OpenCV);
    # the default "builtin" uses the local computer-vision pipeline.
    if settings.PLAN_ANALYZER.lower() == "gemini":
        from app.services.plan_vision.gemini_reader import (
            MAX_IMAGE_BYTES as PLAN_MAX_IMAGE_BYTES,
            PlanImageRejected,
            read_floor_plan,
        )
        data = await image.read(PLAN_MAX_IMAGE_BYTES + 1)
        await image.close()
        try:
            return await read_floor_plan(data, width_ft, depth_ft, front)
        except PlanImageRejected as exc:
            raise HTTPException(status_code=415, detail=str(exc))
        except GeminiUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception:
            logger.exception("Gemini floor-plan reading failed")
            raise HTTPException(status_code=500, detail="The floor-plan analysis failed unexpectedly. "
                                                        "Please try another image.")

    # Imported here so that a missing OpenCV install only disables this
    # endpoint instead of the whole 3D Design API.
    try:
        from app.services.plan_vision.image_io import MAX_IMAGE_BYTES as PLAN_MAX_IMAGE_BYTES
        from app.services.plan_vision.image_io import ImageRejected as PlanImageRejected
        from app.services.plan_vision.service import analyze_floor_plan
    except ImportError:
        logger.exception("Floor-plan analysis unavailable")
        raise HTTPException(status_code=503, detail="Floor-plan image analysis is not available on this "
                                                    "server (OpenCV is not installed). Set "
                                                    "PLAN_ANALYZER=gemini to read plans with Gemini vision.")
    data = await image.read(PLAN_MAX_IMAGE_BYTES + 1)
    await image.close()
    try:
        return await run_in_threadpool(analyze_floor_plan, data, width_ft, depth_ft, front)
    except PlanImageRejected as exc:
        raise HTTPException(status_code=415, detail=str(exc))
    except Exception:
        logger.exception("Floor-plan analysis failed")
        raise HTTPException(status_code=500, detail="The floor-plan analysis failed unexpectedly. "
                                                    "Please try another image.")


@router.get("/models/{model_id}.glb")
async def get_model(model_id: str):
    """Serves a generated GLB by its opaque id. Models expire after a while;
    the client then regenerates from the structured JSON."""
    data = model_store.get(model_id)
    if data is None:
        raise HTTPException(status_code=404, detail="This 3D model has expired. Generate it again.")
    return Response(content=data, media_type="model/gltf-binary",
                    headers={"Cache-Control": "private, max-age=3600"})
