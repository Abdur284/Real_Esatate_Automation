import logging
import re
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import optional_user
from app.core.ratelimit import rate_limit
from app.services.chat import run_orchestrator

router = APIRouter()
logger = logging.getLogger(__name__)

# Guests send a random id their browser generated once (not a user id): it only
# keeps one visitor's conversation together. Signed-in users are identified by
# their verified token instead, whatever the body says.
GUEST_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class ChatMessage(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., max_length=4000)
    context: Optional[str] = ""
    conversation_history: Optional[List[Dict]] = Field(default_factory=list, max_length=50)


class ChatResponse(BaseModel):
    response: str
    model_used: str
    module: Optional[str] = None
    intent: Optional[Dict] = None


def _session_for(uid: Optional[str], session_id: Optional[str]) -> str:
    if uid:
        return f"user_{uid}"
    if not session_id or not GUEST_SESSION_RE.match(session_id):
        raise HTTPException(status_code=422, detail="A valid `session_id` is required for guest chats.")
    return f"guest_{session_id}"


@router.post("/send", response_model=ChatResponse, dependencies=[Depends(rate_limit("chat"))])
async def send_message(chat_msg: ChatMessage, uid: Optional[str] = Depends(optional_user)):
    """
    Endpoint to receive user message and return AI response.
    Routes the request through the Centralized AI Chatbot Orchestrator.
    """
    session_id = _session_for(uid, chat_msg.session_id)
    try:
        return await run_orchestrator(
            session_id=session_id,
            user_msg=chat_msg.message,
            conversation_history=chat_msg.conversation_history,
            user_id=uid,
        )
    except Exception:
        logger.exception("Chat orchestration failed")
        raise HTTPException(status_code=500, detail="The assistant could not answer right now. Please try again.")


@router.get("/status")
async def get_status():
    return {"status": "Centralized Orchestrator Chat service is active"}
