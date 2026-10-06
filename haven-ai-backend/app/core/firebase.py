"""
The backend's Firebase Admin app (Firestore + ID-token checks).

The chatbot initialises the default app when its module is imported; this
reuses it, or initialises it from FIREBASE_CREDS_PATH on first use.
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


def get_app() -> firebase_admin.App:
    with _lock:
        try:
            return firebase_admin.get_app()
        except ValueError:
            pass
        path = os.getenv("FIREBASE_CREDS_PATH", settings.FIREBASE_CREDS_PATH)
        if not os.path.isfile(path):
            raise FirebaseUnavailable("Firebase credentials are not configured on the server.")
        try:
            return firebase_admin.initialize_app(credentials.Certificate(path))
        except Exception as e:  # bad or unreadable credentials file
            logger.error("Firebase init failed: %s", e)
            raise FirebaseUnavailable("Firebase could not be initialised on the server.") from e
