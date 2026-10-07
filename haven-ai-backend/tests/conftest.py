import pytest

from app.core import ratelimit
from app.core.config import settings


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    """Test suites call the endpoints far faster than a person would; the
    limiter has its own tests in test_security.py."""
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 0)
    ratelimit.reset()
    yield
    ratelimit.reset()
