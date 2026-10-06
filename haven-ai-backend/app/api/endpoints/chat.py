from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from app.services.CentralizedChatbot import run_orchestrator

router = APIRouter()

class ChatMessage(BaseModel):
    user_id: str
    message: str
    context: Optional[str] = ""   
    conversation_history: Optional[List[Dict]] = []

class ChatResponse(BaseModel):
    response: str
    model_used: str
    module: Optional[str] = None
    intent: Optional[Dict] = None

@router.post("/send", response_model=ChatResponse)
async def send_message(chat_msg: ChatMessage):
    """
    Endpoint to receive user message and return AI response.
    Routes the request through the Centralized AI Chatbot Orchestrator.
    """
    try:
        # Pass data to orchestrator
        # user_id acts as session_id for persistence
        res = await run_orchestrator(
            session_id=chat_msg.user_id,
            user_msg=chat_msg.message,
            conversation_history=chat_msg.conversation_history
        )

        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration Error: {str(e)}")

@router.get("/status")
async def get_status():
    return {"status": "Centralized Orchestrator Chat service is active"}
