"""Unit tests for ConcessionAnalyzer concession classification and summary generation."""

import uuid

import pytest

from termnova.comparison.concession_analyzer import ConcessionAnalyzer
from termnova.db.models import NegotiationChange, NegotiationTrack, NegotiationVersion


@pytest.fixture
def analyzer() -> ConcessionAnalyzer:
    return ConcessionAnalyzer()


@pytest.mark.unit
def test_counterparty_increases_liability_cap_is_our_concession(analyzer: ConcessionAnalyzer):
    """When counterparty raises our liability cap from $500k to $2M, it's our concession / increased risk."""
    orig = "Total liability shall not exceed $500,000."
    mod = "Total liability shall not exceed $2,000,000."
    res = analyzer.analyze_concession(orig, mod, source="counterparty", clause_category="liability")

    assert res.concession_party == "us"
    assert res.risk_impact == "increased_risk"
    assert res.significance == "critical"
    assert "increased from $500,000 to $2,000,000" in res.concession_summary


@pytest.mark.unit
def test_counterparty_reduces_liability_cap_is_their_concession(analyzer: ConcessionAnalyzer):
    """When counterparty accepts reduced liability cap ($2M -> $500k), it's counterparty concession."""
    orig = "Total liability shall not exceed $2,000,000."
    mod = "Total liability shall not exceed $500,000."
    res = analyzer.analyze_concession(orig, mod, source="counterparty", clause_category="liability")

    assert res.concession_party == "counterparty"
    assert res.risk_impact == "decreased_risk"


@pytest.mark.unit
def test_converting_to_mutual_indemnity_is_counterparty_concession(analyzer: ConcessionAnalyzer):
    """Converting unilateral indemnity to mutual indemnity favors us."""
    orig = "Provider shall indemnify Client."
    mod = "Each party shall provide mutual indemnification to the other party."
    res = analyzer.analyze_concession(
        orig, mod, source="counterparty", clause_category="indemnification"
    )

    assert res.concession_party == "counterparty"
    assert res.risk_impact == "decreased_risk"
    assert "mutual" in res.concession_summary.lower()


@pytest.mark.unit
def test_payment_terms_extension_is_our_concession(analyzer: ConcessionAnalyzer):
    """Extending payment terms from Net 30 to Net 60 by counterparty is our concession."""
    orig = "Payment is due Net 30 days."
    mod = "Payment is due Net 60 days."
    res = analyzer.analyze_concession(orig, mod, source="counterparty", clause_category="payment")

    assert res.concession_party == "us"
    assert "Net 30 to Net 60" in res.concession_summary


@pytest.mark.unit
def test_generate_negotiation_summary(analyzer: ConcessionAnalyzer):
    """Verify AI negotiation summary generates executive overview and balance recommendation."""
    track_id = uuid.uuid4()
    track = NegotiationTrack(
        id=track_id,
        name="Enterprise Agreement",
        counterparty="Titan Corp",
        contract_type="msa",
    )
    v1 = NegotiationVersion(track_id=track_id, document_id=uuid.uuid4(), version_number=1)
    v2 = NegotiationVersion(track_id=track_id, document_id=uuid.uuid4(), version_number=2)

    changes = [
        NegotiationChange(
            track_id=track_id,
            from_version=1,
            to_version=2,
            clause_category="liability",
            change_type="modified",
            original_text="Liability is $1M",
            modified_text="Liability is $500k",
            concession_party="counterparty",
            concession_summary="Counterparty agreed to $500k liability cap.",
            risk_impact="decreased_risk",
            significance="high",
        ),
        NegotiationChange(
            track_id=track_id,
            from_version=1,
            to_version=2,
            clause_category="indemnification",
            change_type="modified",
            original_text="Unilateral indemnity",
            modified_text="Mutual indemnity",
            concession_party="counterparty",
            concession_summary="Mutual indemnity accepted.",
            risk_impact="decreased_risk",
            significance="high",
        ),
    ]

    summary = analyzer.generate_negotiation_summary(changes, track, [v1, v2])
    assert summary.track_id == track_id
    assert summary.strategic_recommendation == "favorable"
    assert len(summary.key_concessions_them) >= 1
    assert "Titan Corp" in summary.executive_summary
