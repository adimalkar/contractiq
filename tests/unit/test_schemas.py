"""Unit tests for Pydantic v2 request/response schemas and input validation."""

import uuid

import pytest
from pydantic import ValidationError

from termnova.api.schemas import FeedbackRequest, QueryRequest


@pytest.mark.unit
def test_query_request_valid():
    """Verify valid query requests instantiate properly."""
    req = QueryRequest(query="What are the SLA terms?", top_k=8, stream=False)
    assert req.query == "What are the SLA terms?"
    assert req.top_k == 8
    assert req.stream is False


@pytest.mark.unit
def test_query_request_invalid_empty():
    """Verify that empty or single-character queries fail validation."""
    with pytest.raises(ValidationError):
        QueryRequest(query="")

    with pytest.raises(ValidationError):
        QueryRequest(query="?")


@pytest.mark.unit
def test_query_request_top_k_bounds():
    """Verify top_k bounds enforcement (ge=1, le=20)."""
    with pytest.raises(ValidationError):
        QueryRequest(query="Valid query", top_k=0)

    with pytest.raises(ValidationError):
        QueryRequest(query="Valid query", top_k=100)


@pytest.mark.unit
def test_feedback_request_rating_range():
    """Verify rating is strictly between 1 and 5."""
    q_id = uuid.uuid4()
    req = FeedbackRequest(query_id=q_id, rating=5)
    assert req.rating == 5

    with pytest.raises(ValidationError):
        FeedbackRequest(query_id=q_id, rating=0)

    with pytest.raises(ValidationError):
        FeedbackRequest(query_id=q_id, rating=6)
