import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.ratelimit import rate_limit
from app.services.design2d.service import Design2DError, generate_2d_plan

router = APIRouter()
logger = logging.getLogger(__name__)


class PlanRequest(BaseModel):
    prompt: str
    plot_width_ft: Optional[float] = None
    plot_length_ft: Optional[float] = None
    floors: Optional[int] = None


@router.post("/generate", dependencies=[Depends(rate_limit("design2d"))])
async def generate(req: PlanRequest):
    """
    Generates a 2D floor-plan specification from a natural-language brief.

    The plan is produced by Gemini using the 2D design system prompt and then
    checked deterministically; the response's `validation` object reports any
    remaining overlaps, boundary or rule violations.
    """
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=422, detail="`prompt` must not be empty.")
    if req.floors is not None and req.floors not in (1, 2):
        raise HTTPException(status_code=422, detail="`floors` must be 1 or 2.")
    try:
        return await generate_2d_plan(
            prompt=req.prompt,
            plot_width_ft=req.plot_width_ft,
            plot_length_ft=req.plot_length_ft,
            floors=req.floors,
        )
    except Design2DError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("2D plan generation failed")
        raise HTTPException(status_code=500, detail="The floor plan could not be generated. Please try again.")
