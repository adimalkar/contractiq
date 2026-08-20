"""Unit tests for NegotiationDiffer clause categorization and multi-version diffing."""

import pytest

from termnova.comparison.negotiation_differ import NegotiationDiffer


@pytest.fixture
def differ() -> NegotiationDiffer:
    return NegotiationDiffer()


@pytest.mark.unit
def test_categorize_clause_liability(differ: NegotiationDiffer):
    """Verify liability category recognition."""
    text = "In no event shall aggregate liability exceed the total fees paid in the prior twelve months."
    assert differ.categorize_clause(text) == "liability"


@pytest.mark.unit
def test_categorize_clause_indemnification(differ: NegotiationDiffer):
    """Verify indemnification category recognition."""
    text = "Provider agrees to defend, indemnify and hold harmless Client from third-party claims."
    assert differ.categorize_clause(text) == "indemnification"


@pytest.mark.unit
def test_categorize_clause_termination(differ: NegotiationDiffer):
    """Verify termination category recognition."""
    text = "Either party may terminate this Agreement for convenience upon 30 days written notice."
    assert differ.categorize_clause(text) == "termination"


@pytest.mark.unit
def test_categorize_clause_payment(differ: NegotiationDiffer):
    """Verify payment category recognition."""
    text = "All invoices shall be payable Net 30 days from the invoice issuance date."
    assert differ.categorize_clause(text) == "payment"


@pytest.mark.unit
def test_categorize_clause_ip(differ: NegotiationDiffer):
    """Verify intellectual property category recognition."""
    text = "Client retains all right, title, and interest in and to its Intellectual Property."
    assert differ.categorize_clause(text) == "ip"


@pytest.mark.unit
def test_categorize_clause_confidentiality(differ: NegotiationDiffer):
    """Verify confidentiality category recognition."""
    text = "Each party agrees to maintain the confidentiality of Proprietary Information."
    assert differ.categorize_clause(text) == "confidentiality"


@pytest.mark.unit
def test_categorize_clause_governing_law(differ: NegotiationDiffer):
    """Verify governing law category recognition."""
    text = "This Agreement shall be governed by the laws of the State of Delaware."
    assert differ.categorize_clause(text) == "governing_law"


@pytest.mark.unit
def test_diff_identical_versions_returns_no_changes(differ: NegotiationDiffer):
    """Verify identical version chunks result in 0 changes."""
    chunks_a = [
        "ARTICLE 1: SERVICES. Provider will deliver software.",
        "ARTICLE 2: PAYMENT. Invoices are due Net 30.",
    ]
    chunks_b = [
        "ARTICLE 1: SERVICES. Provider will deliver software.",
        "ARTICLE 2: PAYMENT. Invoices are due Net 30.",
    ]
    changes = differ.diff_versions(chunks_a, chunks_b)
    assert len(changes) == 0


@pytest.mark.unit
def test_diff_detects_added_modified_and_removed(differ: NegotiationDiffer):
    """Verify modified, added, and removed clause changes are detected."""
    chunks_a = [
        "ARTICLE 1: SERVICES. Provider will deliver software.",
        "ARTICLE 2: PAYMENT. Invoices are due Net 30.",
        "ARTICLE 3: REMOVED. This section is deleted.",
    ]
    chunks_b = [
        "ARTICLE 1: SERVICES. Provider will deliver software and support.",
        "ARTICLE 2: PAYMENT. Invoices are due Net 60.",
        "ARTICLE 4: NEW CLAUSE. Intellectual Property license granted.",
    ]
    changes = differ.diff_versions(chunks_a, chunks_b)
    assert len(changes) >= 2

    categories = [c.clause_category for c in changes]
    assert "payment" in categories
