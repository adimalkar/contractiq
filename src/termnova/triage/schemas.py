"""Pydantic schemas for Contract Inbox, Triage Classification, and Routing Rules."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClassificationResult(BaseModel):
    """Structured output from contract classification."""

    contract_type: str = Field(
        ..., description="msa, nda, sow, amendment, lease, employment, vendor, etc."
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    summary_bullets: list[str] = Field(
        default_factory=list, description="3-5 executive summary points"
    )
    action_required: str = Field(
        default="Standard legal review", description="Recommended next action"
    )
    detected_dates: dict[str, str | None] = Field(
        default_factory=dict, description="effective_date, expiration_date, notice_deadline"
    )
    detected_value: float | None = Field(
        default=None, description="Estimated total contract value in USD"
    )
    risk_signals: list[str] = Field(
        default_factory=list, description="Identified legal risk signals"
    )


class TriageResultResponse(BaseModel):
    """Response model for a document's triage classification."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    contract_type_detected: str
    type_confidence: float
    urgency_score: int
    urgency_factors: dict[str, Any] = Field(default_factory=dict)
    summary_bullets: list[str] = Field(default_factory=list)
    action_required: str
    suggested_assignee: str | None = None
    auto_tags: list[str] = Field(default_factory=list)
    inbox_status: str
    assigned_to: str | None = None
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    triaged_at: datetime
    created_at: datetime
    updated_at: datetime


class InboxItemResponse(BaseModel):
    """Composite item for the Contract Inbox dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID  # TriageResult id
    document_id: uuid.UUID
    filename: str
    file_type: str
    page_count: int | None = None
    upload_timestamp: datetime
    contract_type: str
    type_confidence: float
    urgency_score: int
    urgency_factors: dict[str, Any] = Field(default_factory=dict)
    summary_bullets: list[str] = Field(default_factory=list)
    action_required: str
    suggested_assignee: str | None = None
    auto_tags: list[str] = Field(default_factory=list)
    inbox_status: str
    assigned_to: str | None = None
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    triaged_at: datetime


class InboxListResponse(BaseModel):
    """Paginated list response of inbox contracts."""

    items: list[InboxItemResponse]
    total_count: int
    page: int
    page_size: int
    has_more: bool


class InboxStatsResponse(BaseModel):
    """KPI summary and distributions for the Contract Inbox."""

    unreviewed_count: int = 0
    in_progress_count: int = 0
    assigned_count: int = 0
    completed_count: int = 0
    archived_count: int = 0
    total_count: int = 0
    high_urgency_count: int = 0  # urgency >= 75
    medium_urgency_count: int = 0  # 40 <= urgency < 75
    low_urgency_count: int = 0  # urgency < 40
    type_distribution: dict[str, int] = Field(default_factory=dict)
    tag_distribution: dict[str, int] = Field(default_factory=dict)


class AssignContractRequest(BaseModel):
    """Request to assign an inbox item to a reviewer."""

    assigned_to: str = Field(..., min_length=1, max_length=100)


class AcknowledgeContractRequest(BaseModel):
    """Request to acknowledge review of an inbox item."""

    acknowledged_by: str = Field(default="Reviewer", max_length=100)


class CompleteContractRequest(BaseModel):
    """Request to mark an inbox item as complete."""

    completed_by: str | None = None


class ModifyTagsRequest(BaseModel):
    """Request to add or remove tags on a triage item."""

    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)


class BulkAssignRequest(BaseModel):
    """Bulk assignment request."""

    document_ids: list[uuid.UUID]
    assigned_to: str


class BulkArchiveRequest(BaseModel):
    """Bulk archive request."""

    document_ids: list[uuid.UUID]


class TriageRuleCreate(BaseModel):
    """Request schema to create an automated routing rule."""

    name: str = Field(..., min_length=1, max_length=200)
    condition: dict[str, Any] = Field(
        ...,
        description="Conditions: contract_type, urgency_min, urgency_max, tags_include, tags_exclude, confidence_min",
    )
    action: dict[str, Any] = Field(
        ...,
        description="Actions: assign_to, add_tags, set_status",
    )
    priority: int = Field(default=100, ge=1, le=1000)
    is_active: bool = True


class TriageRuleUpdate(BaseModel):
    """Request schema to update an existing routing rule."""

    name: str | None = None
    condition: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    priority: int | None = None
    is_active: bool | None = None


class TriageRuleResponse(BaseModel):
    """Response model for a triage routing rule."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    condition: dict[str, Any]
    action: dict[str, Any]
    priority: int
    is_active: bool
    created_at: datetime


class RuleDryRunRequest(BaseModel):
    """Request to test routing rules against a specific document without mutating state."""

    document_id: uuid.UUID


class RuleDryRunResponse(BaseModel):
    """Dry run results showing which rules matched and what actions would apply."""

    matched_rules: list[str]
    would_assign_to: str | None = None
    would_add_tags: list[str] = Field(default_factory=list)
    would_set_status: str | None = None
