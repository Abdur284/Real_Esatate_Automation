"""
Property listings from outside sources (/api/properties). Our own dealers'
listings are read by the browser straight from Firestore; this adds
Zameen.com's through the server, where its API key stays.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from starlette.concurrency import run_in_threadpool

from app.core.ratelimit import rate_limit
from app.services import zameen

router = APIRouter()


@router.get("/external", dependencies=[Depends(rate_limit("properties-external", per_minute=60))])
async def external_listings(
    city: str = Query("", max_length=60),
    purpose: Literal["", "for-sale", "for-rent"] = "",
    property_type: str = Query("", max_length=30),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    beds: Optional[int] = Query(None, ge=0, le=20),
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1, le=50),
):
    """Zameen.com listings in our listing shape. Never fails the page: when
    Zameen is off or unreachable it answers with an empty list and a note."""
    mode = zameen.mode()
    filters = zameen.Filters(city=city.strip(), purpose=purpose, property_type=property_type.strip().lower(),
                             min_price=min_price, max_price=max_price, beds=beds, q=q.strip(), page=page)
    try:
        listings = await run_in_threadpool(zameen.search, filters)
        return {"source": "zameen", "mode": mode, "listings": listings, "error": None}
    except zameen.ZameenUnavailable as e:
        return {"source": "zameen", "mode": mode, "listings": [], "error": str(e)}
