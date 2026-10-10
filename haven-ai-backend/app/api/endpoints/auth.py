"""
Account API (/api/auth): resetting a forgotten password with an emailed code.
See app/services/password_reset.py for the flow.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.core.firebase import FirebaseUnavailable
from app.core.ratelimit import rate_limit
from app.services.password_reset import EmailNotConfigured, PasswordReset, ResetError, get_password_reset

router = APIRouter()
logger = logging.getLogger(__name__)

SENT_MESSAGE = "If an account exists for this email, a verification code has been sent to it."


class ResetRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: str = Field(..., min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ResetVerify(ResetRequest):
    code: str = Field(..., pattern=r"^\d{6}$")


class ResetConfirm(BaseModel):
    reset_token: str = Field(..., min_length=10, max_length=200)
    new_password: str = Field(..., max_length=128)


async def _run(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except ResetError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except EmailNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except FirebaseUnavailable:
        raise HTTPException(status_code=503, detail="Accounts are not available right now. Please try again later.")
    except Exception:
        logger.exception("Password reset step failed")
        raise HTTPException(status_code=503, detail="The code could not be sent right now. Please try again later.")


@router.post("/password-reset/request", dependencies=[Depends(rate_limit("reset-request", per_minute=5))])
async def request_code(body: ResetRequest, svc: PasswordReset = Depends(get_password_reset)):
    await _run(svc.request, body.email)
    return {"message": SENT_MESSAGE}


@router.post("/password-reset/verify", dependencies=[Depends(rate_limit("reset-verify", per_minute=10))])
async def verify_code(body: ResetVerify, svc: PasswordReset = Depends(get_password_reset)):
    token = await _run(svc.verify, body.email, body.code)
    return {"reset_token": token}


@router.post("/password-reset/confirm", dependencies=[Depends(rate_limit("reset-confirm", per_minute=10))])
async def confirm_reset(body: ResetConfirm, svc: PasswordReset = Depends(get_password_reset)):
    await _run(svc.reset, body.reset_token, body.new_password)
    return {"message": "Your password has been changed. You can sign in now."}
