"""Unit tests for 15-category clause taxonomy detection and risk classification."""

import pytest

from termnova.intelligence.clause_analyzer import (
    CLAUSE_KEYS,
    ClausePresenceAnalyzer,
)


@pytest.mark.unit
def test_all_15_taxonomy_categories_present():
    """Verify all 15 required standard clause categories are defined."""
    assert len(CLAUSE_KEYS) == 15
    assert "liability" in CLAUSE_KEYS
    assert "indemnification" in CLAUSE_KEYS
    assert "termination" in CLAUSE_KEYS
    assert "payment" in CLAUSE_KEYS
    assert "confidentiality" in CLAUSE_KEYS
    assert "ip_ownership" in CLAUSE_KEYS
    assert "data_protection" in CLAUSE_KEYS
    assert "insurance" in CLAUSE_KEYS
    assert "force_majeure" in CLAUSE_KEYS
    assert "dispute_resolution" in CLAUSE_KEYS
    assert "warranty" in CLAUSE_KEYS
    assert "non_compete" in CLAUSE_KEYS
    assert "assignment" in CLAUSE_KEYS
    assert "audit_rights" in CLAUSE_KEYS
    assert "representations" in CLAUSE_KEYS


@pytest.mark.unit
def test_keyword_scan_finds_liability_and_indemnity():
    """Verify analyzer detects liability and indemnification clauses."""
    analyzer = ClausePresenceAnalyzer()
    chunks = [
        "ARTICLE 1: LIMITATION OF LIABILITY\nIn no event shall aggregate liability exceed $1,000,000.",
        "ARTICLE 2: INDEMNIFICATION\nEach party agrees to indemnify and hold harmless the other from third-party claims.",
    ]

    results = analyzer.analyze_chunks(chunks)

    assert results["liability"].present is True
    assert results["liability"].risk_level in ("low", "medium")
    assert results["liability"].confidence >= 0.9
    assert "$1,000,000" in (results["liability"].excerpt or "")

    assert results["indemnification"].present is True
    assert results["indemnification"].risk_level == "low"  # mutual indemnity
    assert results["indemnification"].confidence >= 0.9


@pytest.mark.unit
def test_keyword_scan_uncapped_liability_classified_critical():
    """Verify uncapped liability is flagged with critical risk level."""
    analyzer = ClausePresenceAnalyzer()
    chunks = [
        "SECTION 8: DAMAGES. The parties agree there shall be uncapped liability for gross negligence and willful misconduct."
    ]

    results = analyzer.analyze_chunks(chunks)
    assert results["liability"].present is True
    assert results["liability"].risk_level == "critical"


@pytest.mark.unit
def test_analyze_document_marks_absent_clauses():
    """Verify missing categories are marked present=False with None risk level."""
    analyzer = ClausePresenceAnalyzer()
    chunks = [
        "CONFIDENTIALITY: All shared trade secrets shall remain strictly confidential for 3 years."
    ]

    results = analyzer.analyze_chunks(chunks)

    assert results["confidentiality"].present is True
    assert results["confidentiality"].risk_level == "low"

    # Insurance, IP, and force majeure should be absent
    assert results["insurance"].present is False
    assert results["insurance"].risk_level is None
    assert results["ip_ownership"].present is False
    assert results["force_majeure"].present is False
