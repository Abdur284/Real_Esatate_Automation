"""
Forgotten password: emailed 6-digit code -> reset token -> new password.
Firebase and SMTP are replaced by fakes; the clock is controlled.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import password_reset as pr
from app.services.password_reset import PasswordReset, ResetError, get_password_reset

ACCOUNTS = {"buyer@test.com": "uid-buyer"}


class Fake:
    def __init__(self):
        self.now = 1000.0
        self.sent = []          # (email, code)
        self.passwords = {}     # uid -> password
        self.svc = PasswordReset(
            find_uid=ACCOUNTS.get,
            set_password=lambda uid, pw: self.passwords.__setitem__(uid, pw),
            send_code=lambda email, code: self.sent.append((email, code)),
            clock=lambda: self.now,
        )

    @property
    def last_code(self):
        return self.sent[-1][1]


@pytest.fixture
def fake():
    return Fake()


@pytest.fixture
def client(fake):
    app.dependency_overrides[get_password_reset] = lambda: fake.svc
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_full_flow_changes_the_password(client, fake):
    r = client.post("/api/auth/password-reset/request", json={"email": " Buyer@Test.com "})
    assert r.status_code == 200
    assert fake.sent[0][0] == "buyer@test.com"
    assert len(fake.last_code) == 6 and fake.last_code.isdigit()

    r = client.post("/api/auth/password-reset/verify", json={"email": "buyer@test.com", "code": fake.last_code})
    assert r.status_code == 200
    token = r.json()["reset_token"]

    r = client.post("/api/auth/password-reset/confirm", json={"reset_token": token, "new_password": "newpass123"})
    assert r.status_code == 200
    assert fake.passwords == {"uid-buyer": "newpass123"}

    # the token works once only
    r = client.post("/api/auth/password-reset/confirm", json={"reset_token": token, "new_password": "other123"})
    assert r.status_code == 400


def test_unknown_email_gets_the_same_answer_and_no_email(client, fake):
    known = client.post("/api/auth/password-reset/request", json={"email": "buyer@test.com"})
    unknown = client.post("/api/auth/password-reset/request", json={"email": "nobody@test.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert [e for e, _ in fake.sent] == ["buyer@test.com"]


def test_wrong_code_is_rejected_and_too_many_guesses_kill_the_code(fake):
    fake.svc.request("buyer@test.com")
    good = fake.last_code
    wrong = "000000" if good != "000000" else "111111"
    for _ in range(pr.MAX_ATTEMPTS - 1):
        with pytest.raises(ResetError, match="not correct"):
            fake.svc.verify("buyer@test.com", wrong)
    with pytest.raises(ResetError, match="Too many"):
        fake.svc.verify("buyer@test.com", wrong)
    with pytest.raises(ResetError, match="expired"):
        fake.svc.verify("buyer@test.com", good)


def test_code_expires(fake):
    fake.svc.request("buyer@test.com")
    fake.now += pr.CODE_TTL_SECONDS + 1
    with pytest.raises(ResetError, match="expired"):
        fake.svc.verify("buyer@test.com", fake.last_code)


def test_resend_waits_for_the_cooldown_and_replaces_the_code(fake):
    fake.svc.request("buyer@test.com")
    fake.svc.request("buyer@test.com")
    assert len(fake.sent) == 1
    first = fake.last_code
    fake.now += pr.RESEND_COOLDOWN_SECONDS
    fake.svc.request("buyer@test.com")
    assert len(fake.sent) == 2
    if fake.last_code != first:
        with pytest.raises(ResetError):
            fake.svc.verify("buyer@test.com", first)
    assert fake.svc.verify("buyer@test.com", fake.last_code)


def test_short_password_is_rejected_and_token_kept(fake):
    fake.svc.request("buyer@test.com")
    token = fake.svc.verify("buyer@test.com", fake.last_code)
    with pytest.raises(ResetError, match="at least"):
        fake.svc.reset(token, "123")
    fake.svc.reset(token, "123456")
    assert fake.passwords["uid-buyer"] == "123456"


def test_bad_input_is_a_validation_error(client):
    assert client.post("/api/auth/password-reset/request", json={"email": "not-an-email"}).status_code == 422
    assert client.post("/api/auth/password-reset/verify", json={"email": "buyer@test.com", "code": "12ab56"}).status_code == 422


def test_email_not_configured_is_reported(client, fake, monkeypatch):
    monkeypatch.setattr(pr.settings, "RESET_CODE_LOG_ONLY", False)
    monkeypatch.setattr(pr.settings, "SMTP_HOST", "")
    fake.svc._send_code = pr.smtp_send_code
    r = client.post("/api/auth/password-reset/request", json={"email": "buyer@test.com"})
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]
