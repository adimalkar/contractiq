"""Pydantic v2 validation schemas for negotiation tracking, version diffs, and concession ledgers."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NegotiationTrackCreate(BaseModel):
    """Schema for initializing a new contract negotiation track."""

    name: str = Field(..., min_length=1, max_length=500, description="Negotiation track title")
    counterparty: str = Field(
        ..., min_length=1, max_length=500, description="Counterparty organization"
    )
    contract_type: str = Field(
        "other", max_length=50, description="Type: msa, sow, nda, vendor, lease, other"
    )
    notes: str | None = Field(None, description="Initial negotiation goals and notes")
    started_by: str = Field("Legal Counsel", max_length=100)


class NegotiationTrackUpdate(BaseModel):
    """Schema for updating negotiation track status and metadata."""

    name: str | None = Field(None, max_length=500)
    counterparty: str | None = Field(None, max_length=500)
    contract_type: str | None = Field(None, max_length=50)
    status: Literal["active", "agreed", "abandoned", "paused"] | None = None
    notes: str | None = None


class NegotiationVersionCreate(BaseModel):
    """Schema for adding a new version round to a negotiation track."""

    source: Literal["internal", "counterparty"] = "internal"
    notes: str | None = None
    uploaded_by: str = "Legal Counsel"


class NegotiationVersionResponse(BaseModel):
    """Response representation of an individual negotiation version."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    track_id: uuid.UUID
    document_id: uuid.UUID
    filename: str = ""
    version_number: int
    source: str
    notes: str | None = None
    risk_score: float | None = None
    risk_delta: float | None = None
    uploaded_by: str
    uploaded_at: datetime


class NegotiationChangeResponse(BaseModel):
    """Response representation of a tracked clause change between rounds."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    track_id: uuid.UUID
    from_version: int
    to_version: int
    clause_category: str
    change_type: str
    original_text: str
    modified_text: str
    diff_html: str | None = None
    risk_impact: str
    concession_party: str | None = None
    concession_summary: str | None = None
    significance: str
    created_at: datetime


class NegotiationTrackListItem(BaseModel):
    """Summary item for the negotiation tracks index list."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    counterparty: str
    contract_type: str
    status: str
    version_count: int = 0
    latest_risk_score: float | None = None
    started_by: str
    started_at: datetime
    updated_at: datetime


class NegotiationTrackDetailResponse(BaseModel):
    """Complete negotiation track details including version history and change logs."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    counterparty: str
    contract_type: str
    status: str
    notes: str | None = None
    started_by: str
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    versions: list[NegotiationVersionResponse] = []
    changes: list[NegotiationChangeResponse] = []


class ConcessionItem(BaseModel):
    """Structured concession ledger entry."""

    change_id: uuid.UUID
    clause_category: str
    from_version: int
    to_version: int
    summary: str
    significance: str
    risk_impact: str
    original_snippet: str
    modified_snippet: str


class ConcessionLedgerResponse(BaseModel):
    """Two-column concession ledger balancing concessions between parties."""

    track_id: uuid.UUID
    our_concessions: list[ConcessionItem] = []
    their_concessions: list[ConcessionItem] = []
    mutual_trades: list[ConcessionItem] = []
    neutral_changes: list[ConcessionItem] = []
    balance: Literal["favorable", "balanced", "unfavorable"] = "balanced"
    total_changes: int = 0


class RiskTrajectoryPoint(BaseModel):
    """Data point representing version risk over negotiation timeline."""

    version_number: int
    source: str
    risk_score: float
    risk_delta: float
    date: str
    notes: str | None = None


class RiskTrajectoryResponse(BaseModel):
    """Full risk trajectory across all negotiation versions for visualization."""

    track_id: uuid.UUID
    versions: list[RiskTrajectoryPoint] = []
    overall_trend: Literal["improving", "deteriorating", "stable"] = "stable"


class TimelineEvent(BaseModel):
    """Vertical timeline card event representing a version exchange."""

    version_number: int
    source: str
    date: str
    uploaded_by: str
    document_filename: str
    change_count: int = 0
    risk_score: float | None = None
    risk_delta: float | None = None
    notes: str | None = None
    key_changes: list[str] = []


class NegotiationTimelineResponse(BaseModel):
    """Timeline data formatted for vertical UI rendering."""

    track_id: uuid.UUID
    track_name: str
    counterparty: str
    status: str
    events: list[TimelineEvent] = []


class NegotiationSummaryResponse(BaseModel):
    """AI-generated executive summary of the entire contract negotiation."""

    track_id: uuid.UUID
    executive_summary: str
    key_concessions_us: list[str] = []
    key_concessions_them: list[str] = []
    remaining_gaps: list[str] = []
    risk_assessment: str
    strategic_recommendation: Literal["favorable", "balanced", "unfavorable"] = "balanced"


class NegotiationDiffResponse(BaseModel):
    """Comparison result between two arbitrary versions."""

    track_id: uuid.UUID
    from_version: int
    to_version: int
    total_changes: int
    changes: list[NegotiationChangeResponse] = []
    summary: str
