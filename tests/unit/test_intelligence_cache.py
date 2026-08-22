"""Unit tests for IntelligenceCache key building and caching helpers."""

import uuid

import pytest

from termnova.intelligence.cache import IntelligenceCache


@pytest.mark.unit
def test_build_key_deterministic_and_org_scoped():
    """Verify cache keys are deterministic across dictionary ordering and scoped by org."""
    org_id = uuid.uuid4()
    key1 = IntelligenceCache.build_key(
        "clause-heatmap", org_id=org_id, params={"contract_type": "msa", "vendor": "Acme"}
    )
    key2 = IntelligenceCache.build_key(
        "clause-heatmap", org_id=org_id, params={"vendor": "Acme", "contract_type": "msa"}
    )
    assert key1 == key2
    assert str(org_id) in key1
    assert "ciq:intelligence" in key1


@pytest.mark.unit
def test_build_key_different_org_produces_different_key():
    """Verify different tenant orgs produce distinct cache keys preventing data leaks."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    key_a = IntelligenceCache.build_key("summary", org_id=org_a)
    key_b = IntelligenceCache.build_key("summary", org_id=org_b)
    assert key_a != key_b


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cache_get_and_set_with_none_client_graceful():
    """Verify cache gracefully returns None when Redis is unavailable."""
    res = await IntelligenceCache.get("dummy_key", None)
    assert res is None

    # Should not raise exception
    await IntelligenceCache.set("dummy_key", {"data": 123}, None)
    deleted = await IntelligenceCache.invalidate_org(uuid.uuid4(), None)
    assert deleted == 0
