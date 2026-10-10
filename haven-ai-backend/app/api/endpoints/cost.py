import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core.ratelimit import rate_limit
from app.services.cost.service import CostModelUnavailable, estimate_cost

router = APIRouter()
logger = logging.getLogger(__name__)


class CostRequest(BaseModel):
    text: str


@router.post("/estimate", dependencies=[Depends(rate_limit("cost"))])
async def estimate(req: CostRequest):
    """
    Estimates construction cost from a natural-language brief, e.g.
    "10 marla modern house in Islamabad, 4 bedrooms, double storey".

    Returns the hybrid (rule-based + XGBoost) estimate: a point total, a
    low/high range, a per-sqft rate, an itemised breakdown, the features the
    text parser extracted, and recommendations. Returns 503 if the trained
    model is not installed on this server.
    """
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=422, detail="`text` must not be empty.")
    try:
        return await run_in_threadpool(estimate_cost, req.text)
    except CostModelUnavailable as exc:
        # The path/exception stays in the server log; the client only needs to
        # know the live model is not available here.
        logger.warning("Cost estimate requested but model unavailable: %s", exc)
        raise HTTPException(status_code=503,
                            detail="The cost estimation model is not available on this server.")
    except Exception:
        logger.exception("Cost estimation failed")
        raise HTTPException(status_code=500,
                            detail="The cost estimate could not be generated. Please try again.")
