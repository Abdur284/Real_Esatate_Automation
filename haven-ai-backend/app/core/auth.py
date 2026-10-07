"""
Who is calling: Firebase ID tokens sent as `Authorization: Bearer <token>`.

The frontend signs users in with Firebase Auth; the backend verifies the
token with the Admin SDK and uses the Firebase uid as the user id.
Administrators carry the custom claim `admin: true`, granted with
scripts/set_admin.py — never decided by the browser.
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException
from starlette.concurrency import run_in_threadpool

from app.core.firebase import FirebaseUnavailable, get_app


@dataclass(frozen=True)
class Caller:
    uid: str
    admin: bool = False


def _verify(token: str) -> Caller:
    from firebase_admin import auth
    decoded = auth.verify_id_token(token, app=get_app())
    return Caller(uid=decoded["uid"], admin=decoded.get("admin") is True)


async def optional_caller(authorization: Optional[str] = Header(None)) -> Optional[Caller]:
    """The signed-in caller, or None for guests. A token that is present but
    invalid is an error rather than silently treated as a guest."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization header.")
    try:
        return await run_in_threadpool(_verify, token)
    except FirebaseUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=401, detail="Your sign-in has expired. Please sign in again.")


async def optional_user(caller: Optional[Caller] = Depends(optional_caller)) -> Optional[str]:
    """The signed-in user's uid, or None for guests."""
    return caller.uid if caller else None


async def require_user(uid: Optional[str] = Depends(optional_user)) -> str:
    if not uid:
        raise HTTPException(status_code=401, detail="Please sign in to save and open designs.")
    return uid


async def require_admin(caller: Optional[Caller] = Depends(optional_caller)) -> Caller:
    if not caller:
        raise HTTPException(status_code=401, detail="Please sign in.")
    if not caller.admin:
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return caller
