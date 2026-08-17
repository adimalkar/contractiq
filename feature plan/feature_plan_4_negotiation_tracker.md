# Feature Plan 4: Negotiation Tracker & Version Diff Timeline

## What We're Building

A system to track contract negotiations through multiple rounds of back-and-forth (v1 → counterparty redline → v2 → internal review → v3 → final). For each negotiation, users can:

1. **Upload multiple versions** of the same contract as the negotiation progresses
2. **Auto-diff any two versions** using the existing `ClauseDiffer` (extended for N versions)
3. **Classify each change as a concession** — did "we" give ground or did the counterparty?
4. **Track cumulative risk impact** — how has our risk posture changed across rounds?
5. **Generate a negotiation summary** — AI-produced overview of key concessions and remaining gaps
6. **View a visual timeline** — vertical timeline with version nodes and change summaries

## Why It Matters

Contract negotiation involves 3-10 rounds of back-and-forth for complex deals. Teams lose track of what changed, which concessions were made, and whether the deal is getting better or worse. People compare Word docs side-by-side manually — tedious for long contracts and impossible to see trends across rounds. The concession ledger ("We gave on liability cap, they gave on payment terms") is critical for negotiation strategy but exists only in people's heads.

---

## Architecture & Approach

### Data Flow
```
Upload Version N  →  Parse & Chunk (existing pipeline)
                           ↓
                  Auto-diff against Version N-1
                           ↓
              ┌────────────┴────────────────────┐
              │  1. Clause-level change detection │
              │  2. Change classification          │
              │     (added/removed/modified)        │
              │  3. Concession classification       │
              │     (us/counterparty/neutral)        │
              │  4. Risk impact assessment           │
              │     (increased/decreased/neutral)     │
              └────────────┬────────────────────┘
                           ↓
              NegotiationChange records saved to DB
                           ↓
              Timeline + Concession Ledger available via API
```

### Key Design Decisions
- **Extends existing differ**: `comparison/differ.py` already has `ClauseDiffer` and `comparison/aligner.py` has embedding-based clause alignment. We extend these, not replace them.
- **Per-clause categorization**: Each change is tagged with a clause category (liability, termination, payment, etc.) using the same LLM extraction from Phase 2's obligation extractor.
- **Concession classification via LLM**: The "who gave ground" determination requires understanding negotiation context — this is an LLM call with the original and modified text plus the party context.
- **Risk trajectory is computed**: After each version diff, re-run the risk scorer on the new version and store the delta.

---

## Sub-Phase 1: Database Models

#### [NEW] `src/termnova/db/models/negotiation.py`

```python
"""SQLAlchemy models for negotiation tracking — tracks, versions, and changes."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from termnova.db.models import Base


class NegotiationTrack(Base):
    """Groups multiple versions of a contract through a negotiation."""

    __tablename__ = "negotiation_tracks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    # "Acme Corp MSA Negotiation Q3 2025"
    counterparty: Mapped[str] = mapped_column(String(500), nullable=False)
    # "Acme Corporation"
    contract_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "msa", "sow", etc.
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    # "active", "agreed", "abandoned", "paused"
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    versions: Mapped[list["NegotiationVersion"]] = relationship(
        back_populates="track",
        cascade="all, delete-orphan",
        order_by="NegotiationVersion.version_number",
    )
    changes: Mapped[list["NegotiationChange"]] = relationship(
        back_populates="track",
        cascade="all, delete-orphan",
    )


class NegotiationVersion(Base):
    """Individual version/round in a negotiation."""

    __tablename__ = "negotiation_versions"
    __table_args__ = (UniqueConstraint("track_id", "version_number", name="uq_track_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("negotiation_tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Auto-incremented within the track: 1, 2, 3, ...
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # "internal" or "counterparty" — who sent this version
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "Counterparty rejected liability cap, proposed mutual indemnity"
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Risk score computed for this specific version
    risk_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Change from previous version: +0.15 means risk increased
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    track: Mapped["NegotiationTrack"] = relationship(back_populates="versions")


class NegotiationChange(Base):
    """Tracked change between two consecutive versions."""

    __tablename__ = "negotiation_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("negotiation_tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_version: Mapped[int] = mapped_column(Integer, nullable=False)
    to_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Change details
    clause_category: Mapped[str] = mapped_column(String(50), nullable=False)
    # "liability", "indemnification", "termination", "payment", "ip", "confidentiality", "other"
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # "added", "removed", "modified"
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    modified_text: Mapped[str] = mapped_column(Text, nullable=False)
    diff_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Pre-rendered HTML diff from ClauseDiffer

    # Negotiation intelligence
    risk_impact: Mapped[str] = mapped_column(String(20), nullable=False)
    # "increased_risk", "decreased_risk", "neutral"
    concession_party: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # "us", "counterparty", "mutual", None (if unclear)
    concession_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "We accepted uncapped liability for willful misconduct"
    significance: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    # "low", "medium", "high", "critical"

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    track: Mapped["NegotiationTrack"] = relationship(back_populates="changes")
```

### Tests for Sub-Phase 1
```
tests/unit/test_negotiation_models.py
  - test_create_track_with_counterparty
  - test_add_version_to_track
  - test_version_number_unique_within_track
  - test_create_change_between_versions
  - test_change_concession_classification
```

---

## Sub-Phase 2: Negotiation Differ & Concession Analyzer

### 2A. Extended Differ

#### [NEW] `src/termnova/comparison/negotiation_differ.py`

```python
"""Multi-version contract diffing with clause-level change tracking."""

from termnova.comparison.aligner import ClauseAligner
from termnova.comparison.differ import ClauseDiffer


class NegotiationDiffer:
    """Extends clause diffing for N-version negotiation tracking."""

    def __init__(self, aligner: ClauseAligner, differ: ClauseDiffer):
        self.aligner = aligner
        self.differ = differ

    async def diff_versions(
        self,
        version_a_chunks: list[str],  # Chunks from version N
        version_b_chunks: list[str],  # Chunks from version N+1
    ) -> list[ClauseChange]:
        """
        1. Use ClauseAligner to align clauses between versions
           (embedding cosine similarity to match "same" clause across rewrites)
        2. For aligned pairs, use ClauseDiffer.generate_html_diff()
        3. For unaligned chunks in A → classified as "removed"
        4. For unaligned chunks in B → classified as "added"
        5. Return list of ClauseChange objects
        """

    async def categorize_clause(self, clause_text: str) -> str:
        """
        Categorize a clause into a standard category.
        Uses keyword matching first, falls back to LLM:
        - "liability" / "limitation of liability" → "liability"
        - "indemnif" → "indemnification"
        - "terminat" → "termination"
        - "payment" / "invoice" / "fee" → "payment"
        - "intellectual property" / "ip" / "patent" → "ip"
        - "confidential" → "confidentiality"
        """
```

### 2B. Concession Analyzer

#### [NEW] `src/termnova/comparison/concession_analyzer.py`

```python
"""AI-powered concession classification for negotiation changes."""


class ConcessionAnalyzer:
    """Determines who gave ground on each change."""

    async def analyze_concession(
        self,
        original_text: str,
        modified_text: str,
        source: str,  # "internal" or "counterparty" — who sent this version
        clause_category: str,
    ) -> ConcessionResult:
        """
        Uses LLM to determine:
        1. concession_party: "us" | "counterparty" | "mutual"
           - If counterparty's version weakens OUR position → "us" (we conceded)
           - If counterparty's version strengthens OUR position → "counterparty" (they conceded)
           - If balanced trade → "mutual"
        2. risk_impact: "increased_risk" | "decreased_risk" | "neutral"
        3. concession_summary: one-sentence human-readable summary
        4. significance: "low" | "medium" | "high" | "critical"
        """

    async def generate_negotiation_summary(
        self,
        all_changes: list[NegotiationChange],
        track: NegotiationTrack,
    ) -> NegotiationSummary:
        """
        AI-generated summary of the entire negotiation:
        - Key concessions made by each party
        - Remaining gaps / unresolved issues
        - Overall risk trajectory
        - Recommendation: "favorable", "unfavorable", "balanced"
        """
```

### 2C. Version Upload Pipeline

#### [NEW] `src/termnova/comparison/version_processor.py`

```python
"""Pipeline for processing a new negotiation version."""


class VersionProcessor:
    async def process_new_version(
        self,
        track_id: uuid.UUID,
        document_id: uuid.UUID,
        source: str,
        uploaded_by: uuid.UUID,
        notes: str | None,
    ) -> tuple[NegotiationVersion, list[NegotiationChange]]:
        """
        1. Determine version_number (max existing + 1)
        2. If version_number > 1, diff against previous version:
           a. Load chunks from both versions
           b. Run NegotiationDiffer.diff_versions()
           c. For each change, run ConcessionAnalyzer
           d. Run risk scorer on new version
           e. Compute risk_delta
        3. Persist NegotiationVersion and NegotiationChange records
        4. Return version + changes for API response
        """
```

### Tests for Sub-Phase 2
```
tests/unit/test_negotiation_differ.py
  - test_diff_identical_versions_returns_no_changes
  - test_diff_added_clause_detected
  - test_diff_removed_clause_detected
  - test_diff_modified_clause_with_html
  - test_categorize_clause_liability
  - test_categorize_clause_termination
  - test_categorize_clause_payment

tests/unit/test_concession_analyzer.py
  - test_counterparty_weakens_position_is_our_concession
  - test_counterparty_strengthens_position_is_their_concession
  - test_mutual_trade_classified_as_mutual
  - test_significance_critical_for_liability_changes
  - test_generate_negotiation_summary_includes_key_concessions

tests/unit/test_version_processor.py
  - test_first_version_no_diff
  - test_second_version_diffs_against_first
  - test_risk_delta_computed_correctly
  - test_version_number_auto_increments
```

---

## Sub-Phase 3: API Endpoints

#### [NEW] `src/termnova/api/routes/negotiations.py`

```python
router = APIRouter(prefix="/api/v1/negotiations", tags=["Negotiation Tracker"])

# Track CRUD
POST   /
    → Body: {name, counterparty, contract_type, notes?}
    → Creates track, current user as starter
    → Response: NegotiationTrackResponse

GET    /
    → Query: status=active, counterparty=Acme
    → List all negotiations for org
    → Response: [NegotiationTrackListItem]

GET    /{track_id}
    → Full track detail with all versions and change summary
    → Response: NegotiationTrackDetailResponse

PATCH  /{track_id}
    → Body: {status?, notes?, name?}
    → Update track metadata

# Version management
POST   /{track_id}/versions
    → Body: multipart — file upload + {source: "internal"|"counterparty", notes?}
    → Uploads document, runs ingestion, diffs against previous version
    → Response: {version: NegotiationVersionResponse, changes: [ChangeResponse]}

GET    /{track_id}/versions
    → List all versions with risk scores
    → Response: [NegotiationVersionResponse]

# Diff & Analysis
GET    /{track_id}/diff
    → Query: from=1&to=3 (version numbers)
    → Returns clause-by-clause diff between any two versions
    → Response: {changes: [ChangeDetail], summary: str}

GET    /{track_id}/concessions
    → AI-generated concession ledger
    → Response: {
        our_concessions: [{clause, summary, significance}],
        their_concessions: [{clause, summary, significance}],
        mutual_trades: [...],
        balance: "favorable" | "unfavorable" | "balanced",
      }

GET    /{track_id}/risk-trajectory
    → Risk score for each version (for charting)
    → Response: {versions: [{number, risk_score, risk_delta, source, date}]}

GET    /{track_id}/timeline
    → Timeline-formatted data for UI rendering
    → Response: {events: [{version_number, source, date, change_count, key_changes, notes}]}

GET    /{track_id}/summary
    → AI-generated negotiation summary
    → Response: {summary, key_concessions, remaining_gaps, recommendation}
```

### Tests for Sub-Phase 3
```
tests/integration/test_negotiation_api.py
  - test_create_negotiation_track
  - test_list_tracks_filtered_by_status
  - test_upload_first_version_no_diff
  - test_upload_second_version_generates_diff
  - test_diff_between_arbitrary_versions
  - test_concessions_ledger_categorizes_correctly
  - test_risk_trajectory_returns_scores_per_version
  - test_timeline_returns_ordered_events
  - test_negotiation_summary_generated
  - test_update_track_status_to_agreed
  - test_negotiation_respects_org_isolation
```

---

## Sub-Phase 4: Frontend — Timeline & Concession Ledger

#### [NEW] `src/termnova/static/js/negotiation.js`

```javascript
// Key UI components:

// 1. Negotiation List Page
function renderNegotiationList(tracks) { ... }
// Card list: track name, counterparty, status badge, version count, latest risk score
// Filter by: status (active/agreed/abandoned), counterparty

// 2. Timeline View (Main visualization)
function renderTimeline(timelineData) { ... }
// Vertical timeline:
// - Each node = version (circle, colored by source: blue=internal, orange=counterparty)
// - Between nodes: change count badge ("12 changes")
// - Click between nodes → expands to show clause-level changes
// - Each node shows: version number, source, date, notes, risk score
// - Risk score shown as small colored indicator (green/yellow/red)

// 3. Diff Viewer (between any two versions)
function renderDiffView(fromVersion, toVersion, changes) { ... }
// Reuses existing redline diff HTML rendering
// Groups changes by clause category
// Each change shows: category badge, original text, modified text, diff markup
// Concession indicator: "We conceded" / "They conceded" / "Mutual trade"

// 4. Concession Ledger
function renderConcessionLedger(concessions) { ... }
// Two-column layout:
// Left: "We Gave" (red tint) — list of our concessions with significance badges
// Right: "They Gave" (green tint) — list of counterparty concessions
// Bottom: balance indicator ("Favorable" / "Balanced" / "Unfavorable")

// 5. Risk Trajectory Chart
function renderRiskChart(trajectory) { ... }
// Line chart using SVG (no chart library dependency):
// X-axis: version numbers
// Y-axis: risk score (0.0 - 1.0)
// Line color changes: green sections where risk decreased, red where increased
// Hover tooltip: version details

// 6. Version Upload Modal
function showUploadVersionModal(trackId) { ... }
// Modal with:
// - File upload input
// - Source radio: "Internal" / "Counterparty"
// - Notes textarea
// - Upload button → triggers /versions POST
```

#### [MODIFY] `src/termnova/static/index.html`
- Add "Negotiations" navigation tab
- Negotiation detail page layout: timeline | diff viewer | concession ledger

#### [NEW] `src/termnova/static/css/negotiation.css`
- Timeline vertical line with version nodes
- Concession ledger two-column layout
- Risk trajectory chart styling
- Diff viewer clause grouping
- Version upload modal

### Tests for Sub-Phase 4
```
tests/e2e/test_negotiation_ui.py
  - test_negotiation_list_page_loads
  - test_create_new_negotiation_track
  - test_upload_version_shows_in_timeline
  - test_click_between_versions_shows_diff
  - test_concession_ledger_renders
  - test_risk_chart_renders_with_data_points
```

---

## Verification Checklist

- [ ] `negotiation_tracks` table created with org isolation
- [ ] `negotiation_versions` table with unique version numbers per track
- [ ] `negotiation_changes` table with clause-level change records
- [ ] First version upload: no diff, just risk score computation
- [ ] Second version upload: auto-diffs against version 1
- [ ] Clause alignment works across rewrites (semantic matching)
- [ ] Changes categorized by clause type
- [ ] Concession classification determines who gave ground
- [ ] Risk trajectory computed across all versions
- [ ] Diff between arbitrary versions (e.g., v1 vs v5) works
- [ ] AI negotiation summary covers key concessions and gaps
- [ ] Timeline API returns ordered events
- [ ] Concession ledger correctly balances "we gave" vs "they gave"
- [ ] Frontend timeline renders with version nodes
- [ ] Org isolation enforced on all endpoints
- [ ] `ruff check` and `ruff format --check` pass
- [ ] All tests pass
