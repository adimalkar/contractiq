"""Unit tests for Responsible AI guardrails, PII redaction, and hallucination detection."""

import uuid

import pytest

from contractiq.config import Settings
from contractiq.rag import GeneratedAnswer, GradedChunk
from contractiq.rag.guardrails import GuardrailChecker


@pytest.mark.unit
def test_pii_redaction_ssn():
    """Verify SSN patterns are identified and scrubbed."""
    checker = GuardrailChecker(Settings(LLM_PROVIDER="mock"))
    text = "The representative SSN is 123-45-6789 for tax identification."
    redacted, was_found = checker._redact_pii(text)
    assert was_found is True
    assert "123-45-6789" not in redacted
    assert "[REDACTED_SSN]" in redacted


@pytest.mark.unit
def test_pii_redaction_email():
    """Verify email addresses are scrubbed."""
    checker = GuardrailChecker(Settings(LLM_PROVIDER="mock"))
    text = "Please forward notices to legal-notices@acme-corp.com immediately."
    redacted, was_found = checker._redact_pii(text)
    assert was_found is True
    assert "legal-notices@acme-corp.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted


@pytest.mark.unit
def test_pii_redaction_clean_text():
    """Verify text without PII remains untouched."""
    checker = GuardrailChecker(Settings(LLM_PROVIDER="mock"))
    clean = "Article 3 states that liability shall not exceed two million dollars."
    redacted, was_found = checker._redact_pii(clean)
    assert was_found is False
    assert redacted == clean


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hallucination_detection_supported_and_unsupported():
    """Verify entailment auditor detects supported vs unsupported claims."""
    checker = GuardrailChecker(Settings(LLM_PROVIDER="mock"))

    chunks = [
        GradedChunk(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            content="Total liability under this agreement is strictly capped at $2,500,000.",
            page_number=1,
            section_header="LIABILITY",
            document_filename="msa.pdf",
            semantic_score=0.9,
            keyword_score=0.9,
            fused_score=0.9,
            relevance_score=0.95,
            is_relevant=True,
        )
    ]

    # Test supported answer
    supported_ans = GeneratedAnswer(
        answer_text="The total liability under this agreement is capped at $2,500,000.",
        citations=[],
    )
    res_supported = await checker.check(supported_ans, chunks)
    assert res_supported.faithfulness_score >= 0.70
    assert len(res_supported.hallucination_flags) == 0

    # Test unsupported / hallucinated answer
    hallucinated_ans = GeneratedAnswer(
        answer_text="The agreement guarantees a fifty million dollar cryptocurrency indemnity fund.",
        citations=[],
    )
    res_hallucinated = await checker.check(hallucinated_ans, chunks)
    assert res_hallucinated.faithfulness_score < 0.70
    assert len(res_hallucinated.hallucination_flags) > 0


@pytest.mark.unit
def test_confidence_score_bounds():
    """Verify confidence score is bounded between 0.0 and 1.0."""
    checker = GuardrailChecker(Settings(LLM_PROVIDER="mock"))
    chunks = [
        GradedChunk(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            content="Text",
            page_number=1,
            section_header="Sec",
            document_filename="doc.pdf",
            semantic_score=0.8,
            keyword_score=0.8,
            fused_score=0.85,
            relevance_score=0.9,
            is_relevant=True,
        )
    ]
    conf = checker._compute_confidence(chunks, faithfulness_score=0.95)
    assert 0.0 <= conf <= 1.0
    assert conf > 0.8
