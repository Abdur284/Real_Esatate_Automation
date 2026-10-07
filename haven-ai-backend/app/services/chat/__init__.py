"""Centralized chatbot: routing (routing.py), module calls (modules.py),
reply templates (templates.py), cache (cache.py), entry point (orchestrator.py)."""
from app.services.chat.orchestrator import run_orchestrator

__all__ = ["run_orchestrator"]
