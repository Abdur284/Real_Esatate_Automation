"""
The backend's single Firebase Admin app (Firestore + ID-token checks).

Every module gets Firebase from here: `get_app()` initialises it from
FIREBASE_CREDS_PATH on first use, `get_db()` returns the Firestore client,
and `is_configured()` lets optional features (chat history) degrade quietly
when no credentials file is present.
"""
import logging
import os
import threading

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings

logger = logging.getLogger(__name__)
_lock = threading.Lock()


class FirebaseUnavailable(RuntimeError):
    pass


def _creds_path() -> str:
    return os.getenv("FIREBASE_CREDS_PATH", settings.FIREBASE_CREDS_PATH)


def is_configured() -> bool:
    return os.path.isfile(_creds_path())


def get_app() -> firebase_admin.App:
    with _lock:
        try:
            return firebase_admin.get_app()
        except ValueError:
            pass
        path = _creds_path()
        if not os.path.isfile(path):
            raise FirebaseUnavailable("Firebase credentials are not configured on the server.")
        try:
            return firebase_admin.initialize_app(credentials.Certificate(path))
        except Exception as e:  # bad or unreadable credentials file
            logger.error("Firebase init failed: %s", e)
            raise FirebaseUnavailable("Firebase could not be initialised on the server.") from e


def get_db():
    """The Firestore client of the shared app."""
    from firebase_admin import firestore
    try:
        return firestore.client(app=get_app())
    except FirebaseUnavailable:
        raise
    except Exception as e:
        raise FirebaseUnavailable("The database is not reachable right now.") from e
