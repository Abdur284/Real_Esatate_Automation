"""
Admin API (/api/admin). Every route requires a Firebase ID token whose user
has the `admin` custom claim (scripts/set_admin.py grants it).
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from app.core.auth import Caller, require_admin
from app.core.firebase import FirebaseUnavailable
from app.services.admin import get_admin_repo

router = APIRouter(dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)


async def _run(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except HTTPException:
        raise
    except FirebaseUnavailable:
        raise HTTPException(status_code=503, detail="The database is not available right now.")
    except Exception:
        logger.exception("Admin request failed")
        raise HTTPException(status_code=500, detail="The request failed. Please try again.")


@router.get("/stats")
async def stats(repo=Depends(get_admin_repo)):
    return await _run(repo.stats)


@router.get("/activity")
async def activity(repo=Depends(get_admin_repo)):
    return {"items": await _run(repo.recent_activity)}


@router.get("/users")
async def users(repo=Depends(get_admin_repo)):
    return {"users": await _run(repo.list_users)}


@router.delete("/users/{uid}")
async def delete_user(uid: str, caller: Caller = Depends(require_admin), repo=Depends(get_admin_repo)):
    if uid == caller.uid:
        raise HTTPException(status_code=400, detail="You cannot delete your own admin account.")
    await _run(repo.delete_user, uid)
    return {"deleted": uid}


@router.get("/properties")
async def properties(verified: Optional[bool] = None, repo=Depends(get_admin_repo)):
    return {"properties": await _run(repo.list_properties, verified)}


@router.post("/properties/{property_id}/verify")
async def verify_property(property_id: str, repo=Depends(get_admin_repo)):
    if not await _run(repo.verify_property, property_id):
        raise HTTPException(status_code=404, detail="Property not found.")
    return {"verified": property_id}


@router.post("/properties/reset-views")
async def reset_views(repo=Depends(get_admin_repo)):
    return {"reset": await _run(repo.reset_views)}


@router.get("/health")
async def health():
    from app.core.firebase import is_configured
    from app.services import gemini
    return {"api": "ok", "firebase_configured": is_configured(), "gemini_configured": gemini.client is not None}
