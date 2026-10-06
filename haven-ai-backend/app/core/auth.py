"""
Who is calling: Firebase ID tokens sent as `Authorization: Bearer <token>`.

The frontend signs users in with Firebase Auth; the backend verifies the
token with the Admin SDK and uses the Firebase uid as the user id.
"""
from typing import Optional

from fastapi import Depends, Header, HTTPException
from starlette.concurrency import run_in_threadpool

from app.core.firebase import FirebaseUnavailable, get_app


def _verify(token: str) -> str:
    from firebase_admin import auth
    decoded = auth.verify_id_token(token, app=get_app())
    return decoded["uid"]


async def optional_user(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """The signed-in user's uid, or None for guests. A token that is present
    but invalid is an error rather than silently treated as a guest."""
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


async def require_user(uid: Optional[str] = Depends(optional_user)) -> str:
    if not uid:
        raise HTTPException(status_code=401, detail="Please sign in to save and open designs.")
    return uid
