"""Unit tests for Prometheus custom telemetry metrics."""

import pytest

from contractiq.observability.metrics import (
    CHUNKS_CREATED,
    DOCUMENTS_INGESTED,
    FAITHFULNESS_SCORE,
    HALLUCINATION_FLAGS,
    QUERY_COUNTER,
)


@pytest.mark.unit
def test_prometheus_metrics_increment():
    """Verify that custom telemetry metrics record observations without exception."""
    QUERY_COUNTER.labels(status="success", model="gpt-4o-mini").inc()
    DOCUMENTS_INGESTED.labels(status="completed", file_type="pdf").inc()
    CHUNKS_CREATED.inc(10)
    FAITHFULNESS_SCORE.observe(0.92)
    HALLUCINATION_FLAGS.labels(verdict="unsupported").inc()
    assert True
