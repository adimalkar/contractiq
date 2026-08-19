"""Unit tests for ContractClassifier."""

import pytest

from termnova.config import Settings
from termnova.triage.classifier import ContractClassifier


@pytest.mark.unit
@pytest.mark.asyncio
async def test_classify_nda_by_filename(test_settings: Settings):
    """Verify filename patterns identify NDA agreements."""
    classifier = ContractClassifier(test_settings)
    res = await classifier.classify(
        document_text="This Agreement governs confidential disclosures between parties.",
        filename="Mutual_NDA_Acme_2026.pdf",
    )
    assert res.contract_type == "nda"
    assert res.confidence >= 0.85
    assert len(res.summary_bullets) >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_classify_msa_by_filename(test_settings: Settings):
    """Verify filename patterns identify Master Services Agreements."""
    classifier = ContractClassifier(test_settings)
    res = await classifier.classify(
        document_text="Master Services Agreement terms and conditions.",
        filename="vendor_msa_master_agreement.pdf",
    )
    assert res.contract_type == "msa"
    assert res.confidence >= 0.85


@pytest.mark.unit
@pytest.mark.asyncio
async def test_classify_by_text_content(test_settings: Settings):
    """Verify text headers classify contract when filename is generic."""
    classifier = ContractClassifier(test_settings)
    text = """
    COMMERCIAL LEASE AGREEMENT
    This Lease is entered into between Landlord and Tenant as of January 15, 2026.
    Term shall commence immediately.
    """
    res = await classifier.classify(
        document_text=text,
        filename="scan_doc_10293.pdf",
    )
    assert res.contract_type == "lease"
    assert res.confidence >= 0.80


@pytest.mark.unit
@pytest.mark.asyncio
async def test_classify_extracts_dates_values_and_risks(test_settings: Settings):
    """Verify heuristic extraction finds dollar values, dates, and risk signals."""
    classifier = ContractClassifier(test_settings)
    text = """
    STATEMENT OF WORK
    Effective as of March 1, 2026, expiring on December 31, 2026.
    Total compensation under this SOW shall not exceed $750,000 USD.
    Either party may terminate upon 30 days written notice.
    Vendor shall indemnify Client for intellectual property claims.
    Liability shall not be limited for breach of data protection.
    """
    res = await classifier.classify(
        document_text=text,
        filename="cloud_migration_sow.pdf",
    )
    assert res.contract_type == "sow"
    assert res.detected_value == 750000.0
    assert res.detected_dates.get("effective_date") is not None
    assert "uncapped_liability" in res.risk_signals
    assert "broad_indemnity" in res.risk_signals
    assert len(res.summary_bullets) >= 3
