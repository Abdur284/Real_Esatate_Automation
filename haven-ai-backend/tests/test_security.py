"""
Security behaviour of the API: who the chatbot thinks is calling, admin-only
routes, rate limits, and that internal errors never reach the client.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.api.endpoints import chat as chat_endpoint
from app.core import ratelimit
from app.core.auth import Caller, optional_caller
from app.core.config import settings
from app.main import app
from app.services.admin import get_admin_repo
from app.services.chat import modules, templates


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def sign_in(uid="user-1", admin=False):
    app.dependency_overrides[optional_caller] = lambda: Caller(uid=uid, admin=admin)


@pytest.fixture
def orchestrator(monkeypatch):
    calls = []

    async def fake(session_id, user_msg, conversation_history=None, user_id=None):
        calls.append({"session_id": session_id, "user_id": user_id, "message": user_msg})
        return {"response": "ok", "model_used": "test", "module": "general_chat", "intent": None}

    monkeypatch.setattr(chat_endpoint, "run_orchestrator", fake)
    return calls


# ---- chat identity ----------------------------------------------------------------

def test_guest_chat_needs_a_valid_session_id(client, orchestrator):
    r = client.post("/api/chat/send", json={"message": "hi"})
    assert r.status_code == 422
    r = client.post("/api/chat/send", json={"message": "hi", "session_id": "../../etc"})
    assert r.status_code == 422
    assert orchestrator == []


def test_guests_get_their_own_session(client, orchestrator):
    client.post("/api/chat/send", json={"message": "hi", "session_id": "browserA123"})
    client.post("/api/chat/send", json={"message": "hi", "session_id": "browserB456"})
    assert [c["session_id"] for c in orchestrator] == ["guest_browserA123", "guest_browserB456"]
    assert all(c["user_id"] is None for c in orchestrator)


def test_signed_in_chat_uses_the_verified_uid_not_the_body(client, orchestrator):
    sign_in("real-uid")
    r = client.post("/api/chat/send", json={"message": "hi", "session_id": "someone-elses-id"})
    assert r.status_code == 200
    assert orchestrator == [{"session_id": "user_real-uid", "user_id": "real-uid", "message": "hi"}]


def test_chat_errors_are_generic(client, monkeypatch):
    async def boom(**_):
        raise RuntimeError("secret internal path C:/keys/firebase.json")
    monkeypatch.setattr(chat_endpoint, "run_orchestrator", boom)
    r = client.post("/api/chat/send", json={"message": "hi", "session_id": "browserA123"})
    assert r.status_code == 500
    assert "secret" not in r.text and "firebase" not in r.text


def test_failed_module_service_does_not_leak_url_or_exception():
    data = {"error": "CONNECTION_FAILED", "fallback_data": {"total_cost": "PKR 1"}}
    text = templates.template_response("cost_estimation", data)
    assert "Troubleshooting" not in text and "http" not in text
    assert "PKR 1" in text


def test_connection_failure_payload_has_no_url(monkeypatch):
    monkeypatch.setattr(modules, "COST_ESTIMATION_API", "http://127.0.0.1:9/never")
    monkeypatch.setattr(modules, "API_RETRY_ATTEMPTS", 1)
    result = asyncio.run(modules.call_module_api("cost_estimation", {}, "cost of a house"))
    assert result["error"] == "CONNECTION_FAILED"
    assert "target_url" not in result and "details" not in result


# ---- admin ------------------------------------------------------------------------

class FakeAdminRepo:
    def __init__(self):
        self.deleted, self.verified = [], []

    def stats(self):
        return {"total_users": 2, "total_dealers": 1, "total_properties": 3, "total_views": 7}

    def recent_activity(self):
        return []

    def list_users(self):
        return [{"id": "u1", "name": "A", "email": "a@x", "role": "buyer", "created_at": None}]

    def delete_user(self, uid):
        self.deleted.append(uid)

    def list_properties(self, verified=None):
        return []

    def verify_property(self, pid):
        self.verified.append(pid)
        return pid == "exists"

    def reset_views(self):
        return 3


@pytest.fixture
def admin_repo():
    repo = FakeAdminRepo()
    app.dependency_overrides[get_admin_repo] = lambda: repo
    return repo


@pytest.mark.parametrize("method,path", [
    ("get", "/api/admin/stats"), ("get", "/api/admin/users"), ("delete", "/api/admin/users/u1"),
    ("post", "/api/admin/properties/p1/verify"), ("post", "/api/admin/properties/reset-views"),
])
def test_admin_routes_reject_guests_and_normal_users(client, admin_repo, method, path):
    assert getattr(client, method)(path).status_code == 401
    sign_in("normal-user", admin=False)
    assert getattr(client, method)(path).status_code == 403
    assert admin_repo.deleted == [] and admin_repo.verified == []


def test_admin_can_use_admin_routes(client, admin_repo):
    sign_in("boss", admin=True)
    assert client.get("/api/admin/stats").json()["total_views"] == 7
    assert client.delete("/api/admin/users/u1").status_code == 200
    assert admin_repo.deleted == ["u1"]
    assert client.post("/api/admin/properties/missing/verify").status_code == 404
    assert client.post("/api/admin/properties/exists/verify").status_code == 200
    assert client.post("/api/admin/properties/reset-views").json() == {"reset": 3}


def test_admin_cannot_delete_themselves(client, admin_repo):
    sign_in("boss", admin=True)
    assert client.delete("/api/admin/users/boss").status_code == 400
    assert admin_repo.deleted == []


# ---- rate limiting ----------------------------------------------------------------

def test_rate_limiter_window():
    ratelimit.reset()
    assert all(ratelimit.check("k", 3, now=100.0 + i) is None for i in range(3))
    retry = ratelimit.check("k", 3, now=104.0)
    assert retry is not None and retry > 0
    assert ratelimit.check("k", 3, now=161.0) is None  # the oldest hit left the window
    assert ratelimit.check("other", 3, now=104.0) is None


def test_chat_is_rate_limited_per_caller(client, orchestrator, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)
    ratelimit.reset()
    body = {"message": "hi", "session_id": "browserA123"}
    assert client.post("/api/chat/send", json=body).status_code == 200
    assert client.post("/api/chat/send", json=body).status_code == 200
    r = client.post("/api/chat/send", json=body)
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    sign_in("someone")  # a different caller has its own budget
    assert client.post("/api/chat/send", json=body).status_code == 200


# ---- config -------------------------------------------------------------------------

def test_cors_origins_come_from_settings():
    from app.core.config import Settings
    assert Settings(CORS_ORIGINS="https://a.example, https://b.example").CORS_ORIGINS == \
        ["https://a.example", "https://b.example"]
    assert Settings(CORS_ORIGINS='["https://c.example"]').CORS_ORIGINS == ["https://c.example"]
