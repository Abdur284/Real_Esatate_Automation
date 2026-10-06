from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.design2d.service import Design2DError, generate_2d_plan

router = APIRouter()


class PlanRequest(BaseModel):
    prompt: str
    plot_width_ft: Optional[float] = None
    plot_length_ft: Optional[float] = None
    floors: Optional[int] = None


@router.post("/generate")
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"2D plan generation error: {exc}")
