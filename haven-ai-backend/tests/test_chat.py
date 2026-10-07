"""Chatbot pipeline: routing, entity extraction, caching and the template
fallback used when Gemini is not configured."""
import asyncio

import pytest

from app.services import gemini
from app.services.chat import cache, orchestrator
from app.services.chat.routing import extract_entities, rule_based_classification


@pytest.mark.parametrize("text,module", [
    ("Make me a 2D floor plan for 5 marla", "design_2d"),
    ("show a 3d walkthrough", "design_3d"),
    ("interior colour scheme ideas", "interior_design"),
    ("construction cost of a 10 marla house", "cost_estimation"),
    ("I want to buy a villa in Lahore", "property_rec"),
    ("hello there", None),
])
def test_keyword_routing(text, module):
    assert rule_based_classification(text) == module


def test_entities():
    p = extract_entities("3 bhk house in Lahore under 2 crore, 10 marla")
    assert p == {"location": "lahore", "property_type": "house", "bhk": 3,
                 "budget_value": "2", "budget_unit": "crore", "area_value": "10", "area_unit": "marla"}


@pytest.fixture
def offline(monkeypatch):
    """No Gemini, no Firestore: the orchestrator answers from templates."""
    monkeypatch.setattr(gemini, "client", None)
    monkeypatch.setattr(orchestrator, "is_configured", lambda: False)
    cache.clear()
    yield
    cache.clear()


def test_general_chat_without_gemini_uses_template(offline):
    res = asyncio.run(orchestrator.run_orchestrator("guest_abcdefgh", "hello"))
    assert res["module"] == "general_chat"
    assert "ArchiBot" in res["response"]


def test_empty_message(offline):
    res = asyncio.run(orchestrator.run_orchestrator("guest_abcdefgh", "   "))
    assert res["response"].startswith("Please enter a message")


def test_cache_is_per_session(offline):
    a = asyncio.run(orchestrator.run_orchestrator("guest_aaaaaaaa", "hello"))
    b = asyncio.run(orchestrator.run_orchestrator("guest_aaaaaaaa", "hello"))
    c = asyncio.run(orchestrator.run_orchestrator("guest_bbbbbbbb", "hello"))
    assert "(Cached)" not in a["model_used"]
    assert "(Cached)" in b["model_used"]
    assert "(Cached)" not in c["model_used"]


def test_history_is_mapped_to_gemini_roles():
    contents = orchestrator._build_gemini_contents(
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"},
         {"role": "system", "content": "ignored"}], "now")
    assert [c["role"] for c in contents] == ["user", "model", "user"]
