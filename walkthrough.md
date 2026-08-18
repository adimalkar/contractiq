# Walkthrough: Feature 1 — Document Visualizer & Contract Knowledge Graph

## Overview
We have implemented **Feature 1: Interactive Document Visualizer & Contract Knowledge Graph** across the full Termnova stack. Contracts are automatically analyzed upon ingestion to extract key legal entities (companies, signatories, governing law jurisdictions), resolve cross-contract relationships (Amendments, SOW parent links, renewals), and visualize the contract topology using an interactive D3.js force-directed graph and hierarchical Document Stack Tree view.

---

## Changes Implemented

### 1. Database Schema (`src/termnova/db/models.py`)
- **`EntityNode`**: Extracted legal entities (`name`, `normalized_name`, `entity_type`, `aliases`, `metadata`).
- **`DocumentEntity`**: Junction table mapping entities to documents with specific roles (`party_a`, `party_b`, `governing_jurisdiction`, etc.).
- **`DocumentRelationship`**: Directed cross-contract edges (`source_document_id`, `target_document_id`, `relationship_type`, `metadata`).
- Added bidirectional relationships to `Document` model.

### 2. Entity Extraction & Normalization (`src/termnova/graph/entity_extractor.py`)
- **LLM + Heuristic Extraction**: Structured JSON extraction for contract types, parties, effective/expiration dates, governing law, and referenced agreements with rule-based regex fallback.
- **Fuzzy Entity Deduplication**: Corporate suffix stripping (`Inc.`, `LLC`, `Corp.`), token overlap matching, and alias accumulation to avoid entity node duplication.

### 3. Knowledge Graph Engine (`src/termnova/graph/builder.py`)
- **Automatic Graph Construction**: `build_graph_for_document()` called during ingestion.
- **Cross-Contract Relationship Detection**: Matches filename conventions, explicit text references, and counterparty overlaps.
- **D3.js Topology Serializer**: `get_graph_data()` returning nodes (color-coded by contract/entity type) and directed edges with labels and weights.
- **Document Stack Hierarchy**: `get_document_stack()` constructing parent MSA $\rightarrow$ child SOWs/Amendments trees.

### 4. REST API Endpoints (`src/termnova/api/routes/graph.py`)
- `GET /api/v1/graph/visualize`: Returns D3.js force graph nodes and edges.
- `GET /api/v1/graph/stack/{doc_id}`: Returns hierarchical document stack.
- `GET /api/v1/graph/documents/{doc_id}/relationships`: Retrieves direct connections.
- `GET /api/v1/graph/entities`: Paginated list of extracted entities with contract counts.
- `POST /api/v1/graph/relationships`: Manually link two contracts.
- `DELETE /api/v1/graph/relationships/{id}`: Delete an edge.
- `POST /api/v1/graph/auto-detect/{doc_id}`: Trigger AI entity/relationship scan.

### 5. Interactive D3.js Frontend UI (`src/termnova/static/`)
- **`graph.js`**: D3.js force simulation (`d3.forceSimulation`), zoom & pan, node dragging, entity toggles, type filter pills, SVG export, and detail drawer.
- **`graph.css`**: Dark-themed node styling with glowing highlights, filter chips, and responsive side drawers.
- **`index.html` & `app.js`**: Added **Document Map** sidebar tab, view mode switcher (Force Graph vs Document Stack View), search bar, and "Query Contract in Studio" direct action.

---

## Verification & Test Results

### 1. Test Suite Execution
Executed full automated test suite with **51 tests**:
```bash
.venv/bin/pytest -v
```
**Results:**
- `tests/unit/test_entity_extractor.py`: **4 passed** (Normalization, Fuzzy Matching, Heuristics, DB Persistence)
- `tests/unit/test_graph_builder.py`: **3 passed** (Graph building, Stack hierarchy, Manual CRUD)
- `tests/integration/test_graph_api.py`: **1 passed** (End-to-end Graph API lifecycle)
- `tests/e2e/test_api.py`: **2 passed** (Health check & RAG query lifecycle)
- **Total: 51 passed in 28.93s (100% PASS)**

### 2. Code Quality & Formatting
```bash
.venv/bin/ruff check . && .venv/bin/ruff format .
```
- 0 lint errors, all 102 files cleanly formatted.

### 3. Production Deployment
- Pushed commit `26853b6` to GitHub `main` branch triggering automatic Render deployment to `https://termnova.onrender.com`.
