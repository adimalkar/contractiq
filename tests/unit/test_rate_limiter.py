"""Unit tests for SlowAPI rate limiting configuration and authentication."""

import pytest

from termnova.security.auth import verify_api_key
from termnova.security.rate_limiter import limiter


@pytest.mark.unit
def test_rate_limiter_initialization():
    """Verify that the SlowAPI limiter is initialized with default rules."""
    assert limiter is not None
    assert len(limiter._default_limits) > 0


@pytest.mark.unit
def test_verify_api_key_when_disabled():
    """Verify that when REQUIRE_AUTH is false, anonymous access is allowed."""
    key = verify_api_key(x_api_key=None)
    assert key == "anonymous"
