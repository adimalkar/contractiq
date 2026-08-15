"""Unit tests for ClauseDiffer inline HTML diffing and key difference extraction."""

import pytest

from contractiq.comparison import ClauseAlignment
from contractiq.comparison.differ import ClauseDiffer


@pytest.mark.unit
def test_diff_identical_texts():
    """Verify that identical clause texts produce matching diff markup."""
    text = "Provider will maintain $2,000,000 in general liability insurance."
    html_diff = ClauseDiffer.generate_html_diff(text, text)
    assert "diff-identical" in html_diff
    assert "Provider will maintain" in html_diff


@pytest.mark.unit
def test_diff_modified_texts():
    """Verify that modified texts properly generate ins and del HTML tags."""
    text_a = "Payment is due within 30 days of invoice."
    text_b = "Payment is due within 60 days of invoice."
    html_diff = ClauseDiffer.generate_html_diff(text_a, text_b)
    assert "<del class='diff-del'>" in html_diff
    assert "<ins class='diff-ins'>" in html_diff
    assert "30" in html_diff
    assert "60" in html_diff


@pytest.mark.unit
def test_extract_key_differences_financial():
    """Verify that altered monetary figures are surfaced as key differences."""
    alignment = ClauseAlignment(
        section_a="ARTICLE 4: FEES",
        section_b="ARTICLE 4: FEES",
        text_a="Monthly recurring fee is $50,000.",
        text_b="Monthly recurring fee is $75,000.",
        similarity_score=0.88,
        diff_type="modified",
        diff_html="...",
    )
    diffs = ClauseDiffer.extract_key_differences([alignment])
    assert len(diffs) > 0
    assert "Financial change in [ARTICLE 4: FEES]" in diffs[0]
