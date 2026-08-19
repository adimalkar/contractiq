"""Unit tests for UrgencyScorer."""

from datetime import date, timedelta

import pytest

from termnova.triage.urgency import UrgencyScorer


@pytest.mark.unit
def test_urgency_deadline_proximity():
    """Verify deadline proximity awards up to 25 points based on days remaining."""
    today = date.today()

    # Immediate deadline (< 7 days)
    score_7d, factors_7d = UrgencyScorer.compute_urgency(
        expiration_date=today + timedelta(days=5),
        contract_type="nda",
    )
    assert factors_7d["deadline_proximity"]["points"] == 25

    # Medium deadline (14-30 days)
    score_20d, factors_20d = UrgencyScorer.compute_urgency(
        expiration_date=today + timedelta(days=20),
        contract_type="nda",
    )
    assert factors_20d["deadline_proximity"]["points"] == 15

    # Far deadline (> 90 days)
    score_120d, factors_120d = UrgencyScorer.compute_urgency(
        expiration_date=today + timedelta(days=120),
        contract_type="nda",
    )
    assert factors_120d["deadline_proximity"]["points"] == 0


@pytest.mark.unit
def test_urgency_contract_value_and_risks():
    """Verify high contract value and critical risks score 25 points each."""
    score, factors = UrgencyScorer.compute_urgency(
        estimated_value=1_500_000.0,
        risk_signals=["uncapped_liability", "broad_indemnity"],
        contract_type="msa",
    )
    assert factors["contract_value"]["points"] == 25
    assert factors["risk_signals"]["points"] == 25  # Uncapped liability gives max risk score
    assert factors["contract_type_weight"]["points"] == 15  # MSA weight
    assert score >= 65


@pytest.mark.unit
def test_urgency_composite_factors_explainability():
    """Verify composite factors dictionary provides complete transparent breakdown."""
    score, factors = UrgencyScorer.compute_urgency(
        deadline_days=10,
        estimated_value=250_000.0,
        risk_signals=["auto_renewal"],
        contract_type="amendment",
    )
    assert factors["deadline_proximity"]["points"] == 20
    assert factors["contract_value"]["points"] == 15
    assert factors["risk_signals"]["points"] == 10
    assert factors["contract_type_weight"]["points"] == 20
    assert score == 65
