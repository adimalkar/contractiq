"""Integration tests for Negotiation Tracker REST API endpoints."""

import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.db.models import (
    NegotiationTrack,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_negotiation_track(api_client: AsyncClient):
    """Verify POST /api/v1/negotiations/ creates a new track."""
    payload = {
        "name": "Acme Master Services Agreement 2026",
        "counterparty": "Acme Corporation",
        "contract_type": "msa",
        "notes": "Prioritize 12-month liability cap and Net 30 payment.",
        "started_by": "Senior Counsel",
    }
    resp = await api_client.post("/api/v1/negotiations/", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["name"] == "Acme Master Services Agreement 2026"
    assert data["counterparty"] == "Acme Corporation"
    assert data["contract_type"] == "msa"
    assert data["status"] == "active"
    assert data["started_by"] == "Senior Counsel"
    assert data["id"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_negotiation_tracks_and_filtering(
    api_client: AsyncClient, test_session: AsyncSession
):
    """Verify GET /api/v1/negotiations/ lists tracks with status and counterparty filters."""
    t1 = NegotiationTrack(
        name="Track Alpha",
        counterparty="Alpha Corp",
        contract_type="msa",
        status="active",
    )
    t2 = NegotiationTrack(
        name="Track Beta",
        counterparty="Beta Inc",
        contract_type="nda",
        status="agreed",
    )
    test_session.add_all([t1, t2])
    await test_session.commit()

    # List all
    resp = await api_client.get("/api/v1/negotiations/")
    assert resp.status_code == 200
    all_tracks = resp.json()
    assert len(all_tracks) >= 2

    # Filter by status=agreed
    resp_agreed = await api_client.get("/api/v1/negotiations/?status=agreed")
    assert resp_agreed.status_code == 200
    agreed_tracks = resp_agreed.json()
    assert len(agreed_tracks) == 1
    assert agreed_tracks[0]["counterparty"] == "Beta Inc"

    # Filter by counterparty
    resp_search = await api_client.get("/api/v1/negotiations/?counterparty=Alpha")
    assert resp_search.status_code == 200
    search_tracks = resp_search.json()
    assert len(search_tracks) == 1
    assert search_tracks[0]["name"] == "Track Alpha"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upload_versions_and_diff_lifecycle(
    api_client: AsyncClient, test_session: AsyncSession
):
    """Verify uploading version 1 and version 2 automatically computes diffs and risk deltas."""
    # 1. Create track
    t = NegotiationTrack(
        name="Cloud Services Contract",
        counterparty="Nebula Cloud",
        contract_type="vendor",
    )
    test_session.add(t)
    await test_session.commit()
    await test_session.refresh(t)

    # 2. Upload Version 1
    v1_content = (
        b"ARTICLE 1: SERVICES\nNebula will provide cloud hosting.\n\n"
        b"ARTICLE 2: LIABILITY\nTotal liability is capped at $500,000.\n\n"
        b"ARTICLE 3: PAYMENT\nInvoices are due Net 30 days."
    )
    files_v1 = {"file": ("cloud_v1.txt", io.BytesIO(v1_content), "text/plain")}
    data_v1 = {"source": "internal", "notes": "Initial draft sent."}

    resp_v1 = await api_client.post(
        f"/api/v1/negotiations/{t.id}/versions",
        files=files_v1,
        data=data_v1,
    )
    assert resp_v1.status_code == 201
    v1_json = resp_v1.json()
    assert v1_json["version_number"] == 1
    assert v1_json["risk_score"] == 0.25
    assert v1_json["risk_delta"] == 0.0

    # 3. Upload Version 2 (Counterparty Redline)
    v2_content = (
        b"ARTICLE 1: SERVICES\nNebula will provide cloud hosting and 24/7 support.\n\n"
        b"ARTICLE 2: LIABILITY\nTotal liability is capped at $2,000,000.\n\n"
        b"ARTICLE 3: PAYMENT\nInvoices are due Net 60 days."
    )
    files_v2 = {"file": ("cloud_v2_redline.txt", io.BytesIO(v2_content), "text/plain")}
    data_v2 = {"source": "counterparty", "notes": "Nebula proposed higher cap and Net 60."}

    resp_v2 = await api_client.post(
        f"/api/v1/negotiations/{t.id}/versions",
        files=files_v2,
        data=data_v2,
    )
    assert resp_v2.status_code == 201
    v2_json = resp_v2.json()
    assert v2_json["version_number"] == 2
    assert v2_json["risk_delta"] is not None

    # 4. Fetch Concession Ledger
    resp_ledger = await api_client.get(f"/api/v1/negotiations/{t.id}/concessions")
    assert resp_ledger.status_code == 200
    ledger = resp_ledger.json()
    assert ledger["total_changes"] >= 1
    assert ledger["balance"] in ("favorable", "balanced", "unfavorable")

    # 5. Fetch Diff
    resp_diff = await api_client.get(
        f"/api/v1/negotiations/{t.id}/diff?from_version=1&to_version=2"
    )
    assert resp_diff.status_code == 200
    diff_data = resp_diff.json()
    assert diff_data["total_changes"] >= 1
    assert len(diff_data["changes"]) >= 1

    # 6. Fetch Risk Trajectory
    resp_traj = await api_client.get(f"/api/v1/negotiations/{t.id}/risk-trajectory")
    assert resp_traj.status_code == 200
    traj_data = resp_traj.json()
    assert len(traj_data["versions"]) == 2
    assert traj_data["versions"][0]["version_number"] == 1
    assert traj_data["versions"][1]["version_number"] == 2

    # 7. Fetch Timeline
    resp_timeline = await api_client.get(f"/api/v1/negotiations/{t.id}/timeline")
    assert resp_timeline.status_code == 200
    timeline = resp_timeline.json()
    assert len(timeline["events"]) == 2

    # 8. Fetch AI Summary
    resp_summary = await api_client.get(f"/api/v1/negotiations/{t.id}/summary")
    assert resp_summary.status_code == 200
    summary = resp_summary.json()
    assert "Nebula Cloud" in summary["executive_summary"]
    assert summary["strategic_recommendation"] in ("favorable", "balanced", "unfavorable")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_and_delete_track(api_client: AsyncClient, test_session: AsyncSession):
    """Verify updating track status and deleting track cascade removes data."""
    t = NegotiationTrack(
        name="Partnership Deal",
        counterparty="Omega Partners",
        contract_type="nda",
    )
    test_session.add(t)
    await test_session.commit()
    await test_session.refresh(t)

    # Patch status to agreed
    resp_patch = await api_client.patch(
        f"/api/v1/negotiations/{t.id}",
        json={"status": "agreed", "notes": "Signed and executed."},
    )
    assert resp_patch.status_code == 200
    assert resp_patch.json()["status"] == "agreed"

    # Delete track
    resp_del = await api_client.delete(f"/api/v1/negotiations/{t.id}")
    assert resp_del.status_code == 204

    # Verify 404 on get
    resp_get = await api_client.get(f"/api/v1/negotiations/{t.id}")
    assert resp_get.status_code == 404
