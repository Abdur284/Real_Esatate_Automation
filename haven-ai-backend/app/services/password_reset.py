"""
Forgotten passwords: a 6-digit code sent by email, then a new password.

    1. request(email)          -> emails a code (if an account has that email)
    2. verify(email, code)     -> a short-lived reset token
    3. reset(token, password)  -> sets the new password with the Admin SDK

Codes and tokens live in memory, like the rate limiter: they only have to
survive a few minutes in the single-process FYP deployment, and nothing
secret ends up in Firestore, which the browser can reach. Only a hash of each
code is kept, every code allows a few wrong guesses, and the response to
step 1 never says whether the email has an account.
"""
import hashlib
import hmac
import logging
import secrets
import smtplib
import threading
import time
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

CODE_TTL_SECONDS = 10 * 60
TOKEN_TTL_SECONDS = 10 * 60
RESEND_COOLDOWN_SECONDS = 60
MAX_ATTEMPTS = 5
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128


class ResetError(ValueError):
    """A problem the user can fix (wrong code, expired, weak password)."""


class EmailNotConfigured(RuntimeError):
    pass


@dataclass
class _Code:
    uid: str
    code_hash: str
    expires_at: float
    sent_at: float
    attempts: int = 0


@dataclass
class _Token:
    uid: str
    expires_at: float


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


# ---- Firebase and email (replaced in tests) ----------------------------------------

def firebase_find_uid(email: str) -> Optional[str]:
    from firebase_admin import auth
    from app.core.firebase import get_app
    try:
        return auth.get_user_by_email(email, app=get_app()).uid
    except auth.UserNotFoundError:
        return None


def firebase_set_password(uid: str, password: str) -> None:
    from firebase_admin import auth
    from app.core.firebase import get_app
    app = get_app()
    auth.update_user(uid, password=password, app=app)
    auth.revoke_refresh_tokens(uid, app=app)   # sign out other devices


def smtp_send_code(email: str, code: str) -> None:
    minutes = CODE_TTL_SECONDS // 60
    if settings.RESET_CODE_LOG_ONLY:
        logger.warning("RESET_CODE_LOG_ONLY is on: password reset code for %s is %s", email, code)
        return
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        raise EmailNotConfigured("Email sending is not configured on the server.")

    msg = EmailMessage()
    msg["Subject"] = f"{code} is your {settings.PROJECT_NAME} password reset code"
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = email
    msg.set_content(
        f"Your password reset code is: {code}\n\n"
        f"Enter it on the reset page within {minutes} minutes.\n"
        "If you did not ask to reset your password, you can ignore this email."
    )
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


class PasswordReset:
    def __init__(self,
                 find_uid: Callable[[str], Optional[str]] = firebase_find_uid,
                 set_password: Callable[[str, str], None] = firebase_set_password,
                 send_code: Callable[[str, str], None] = smtp_send_code,
                 clock: Callable[[], float] = time.monotonic):
        self._find_uid = find_uid
        self._set_password = set_password
        self._send_code = send_code
        self._clock = clock
        self._lock = threading.Lock()
        self._codes: Dict[str, _Code] = {}
        self._tokens: Dict[str, _Token] = {}

    def _prune(self, now: float) -> None:
        for k in [k for k, c in self._codes.items() if c.expires_at <= now]:
            del self._codes[k]
        for k in [k for k, t in self._tokens.items() if t.expires_at <= now]:
            del self._tokens[k]

    def request(self, email: str) -> None:
        """Emails a new code if an account has this email. Silent otherwise,
        and silent while the previous code is still within its cooldown."""
        email = normalize_email(email)
        now = self._clock()
        with self._lock:
            self._prune(now)
            prev = self._codes.get(email)
            if prev and now - prev.sent_at < RESEND_COOLDOWN_SECONDS:
                return
        uid = self._find_uid(email)
        if not uid:
            return
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._send_code(email, code)
        with self._lock:
            self._codes[email] = _Code(uid=uid, code_hash=_hash(code),
                                       expires_at=now + CODE_TTL_SECONDS, sent_at=now)

    def verify(self, email: str, code: str) -> str:
        """Checks the code; returns a one-time reset token."""
        email = normalize_email(email)
        code = (code or "").strip()
        now = self._clock()
        with self._lock:
            self._prune(now)
            entry = self._codes.get(email)
            if not entry:
                raise ResetError("This code has expired. Please request a new one.")
            if not hmac.compare_digest(entry.code_hash, _hash(code)):
                entry.attempts += 1
                if entry.attempts >= MAX_ATTEMPTS:
                    del self._codes[email]
                    raise ResetError("Too many wrong codes. Please request a new one.")
                raise ResetError("That code is not correct.")
            del self._codes[email]
            token = secrets.token_urlsafe(32)
            self._tokens[token] = _Token(uid=entry.uid, expires_at=now + TOKEN_TTL_SECONDS)
            return token

    def reset(self, token: str, password: str) -> None:
        if not MIN_PASSWORD_LENGTH <= len(password or "") <= MAX_PASSWORD_LENGTH:
            raise ResetError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        now = self._clock()
        with self._lock:
            self._prune(now)
            entry = self._tokens.pop(token or "", None)
        if not entry:
            raise ResetError("This reset session has expired. Please start again.")
        self._set_password(entry.uid, password)


_service = PasswordReset()


def get_password_reset() -> PasswordReset:
    return _service
