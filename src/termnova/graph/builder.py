"""Graph builder service constructing contract networks and D3.js topology datasets."""

import uuid
from typing import Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from termnova.config import Settings, get_settings
from termnova.db.models import Document, DocumentEntity, DocumentRelationship, EntityNode
from termnova.graph.entity_extractor import EntityExtractor
from termnova.graph.schemas import (
    DocumentRelationshipResponse,
    DocumentStack,
    DocumentStackItem,
    EntityItemResponse,
    EntityListResponse,
    ExtractedEntities,
    GraphData,
    GraphEdge,
    GraphNode,
)

logger = structlog.get_logger(__name__)


class GraphBuilder:
    """Constructs and queries the contract relationship and entity knowledge graph."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.extractor = EntityExtractor(self.settings)

    async def build_graph_for_document(self, document_id: uuid.UUID) -> dict[str, Any]:
        """Extract entities, detect cross-contract edges, and store graph links for a document."""
        # 1. Fetch document and initial chunks
        stmt = (
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.id == document_id)
        )
        result = await self.session.execute(stmt)
        doc = result.scalars().first()
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found.")

        # Aggregate text from initial chunks
        full_text = "\n\n".join(c.content for c in doc.chunks[:5]) if doc.chunks else doc.filename

        # 2. Extract structured entities & metadata
        extracted = await self.extractor.extract(full_text, doc.filename)

        # 3. Update document metadata with extracted legal insights
        meta = dict(doc.metadata_ or {})
        meta["contract_type"] = extracted.contract_type
        if extracted.title:
            meta["title"] = extracted.title
        if extracted.governing_law:
            meta["governing_law"] = extracted.governing_law
        if extracted.effective_date:
            meta["effective_date"] = extracted.effective_date
        if extracted.expiration_date:
            meta["expiration_date"] = extracted.expiration_date
        if extracted.renewal_terms:
            meta["renewal_terms"] = extracted.renewal_terms
        if extracted.total_value_usd:
            meta["total_value_usd"] = extracted.total_value_usd

        meta["extracted_parties"] = [p.model_dump() for p in extracted.parties]
        doc.metadata_ = meta

        # 4. Persist entities & document links
        persisted_entities = await self.extractor.persist_entities(self.session, doc.id, extracted)

        # 5. Detect and link relationships to other existing documents
        detected_rels = await self.detect_relationships(doc.id, extracted)

        await self.session.flush()

        logger.info(
            "Graph construction complete for document",
            document_id=str(doc.id),
            filename=doc.filename,
            entities_count=len(persisted_entities),
            relationships_count=len(detected_rels),
        )

        return {
            "document_id": str(doc.id),
            "contract_type": extracted.contract_type,
            "entities_linked": len(persisted_entities),
            "relationships_created": len(detected_rels),
        }

    async def detect_relationships(
        self,
        document_id: uuid.UUID,
        extracted: ExtractedEntities | None = None,
    ) -> list[DocumentRelationship]:
        """Detect cross-contract links using title matching, filename patterns, and entity overlap."""
        doc = await self.session.get(Document, document_id)
        if not doc:
            return []

        # Query other documents
        stmt = select(Document).where(Document.id != document_id)
        res = await self.session.execute(stmt)
        other_docs = res.scalars().all()
        if not other_docs:
            return []

        created_relationships: list[DocumentRelationship] = []
        doc_fn = doc.filename.lower()
        doc_type = (doc.metadata_ or {}).get("contract_type", "other")

        # 1. Match from explicit referenced_contracts in extracted metadata
        if extracted and extracted.referenced_contracts:
            for ref in extracted.referenced_contracts:
                target_title_clean = ref.target_title.lower()
                for target_doc in other_docs:
                    target_fn = target_doc.filename.lower()
                    target_meta_title = (target_doc.metadata_ or {}).get("title", "").lower()
                    if (
                        target_fn in target_title_clean
                        or target_title_clean in target_fn
                        or (target_meta_title and target_meta_title in target_title_clean)
                    ):
                        rel = await self._add_relationship_if_missing(
                            source_id=doc.id,
                            target_id=target_doc.id,
                            rel_type=ref.relationship_type,
                            metadata={"auto_detected": True, "context": ref.context_snippet},
                        )
                        if rel:
                            created_relationships.append(rel)

        # 2. Heuristic filename pattern matching
        # Example: SOW referencing MSA
        for target_doc in other_docs:
            target_fn = target_doc.filename.lower()
            target_stem = target_fn.rsplit(".", 1)[0]
            target_type = (target_doc.metadata_ or {}).get("contract_type", "other")

            # Check if current is amendment to target (requires filename stem match or shared counterparties)
            if "amendment" in doc_fn:
                stem_match = len(target_stem) > 3 and target_stem in doc_fn
                shared_parties = target_type in ["msa", "lease"] and await self._share_parties(
                    doc.id, target_doc.id
                )
                if stem_match or shared_parties:
                    rel = await self._add_relationship_if_missing(
                        source_id=doc.id,
                        target_id=target_doc.id,
                        rel_type="amends",
                        metadata={"auto_detected": True, "rule": "amendment_match"},
                    )
                    if rel:
                        created_relationships.append(rel)

            # Check if current is SOW belonging to parent MSA
            elif doc_type == "sow" and target_type == "msa":
                # Check for shared party names
                if await self._share_parties(doc.id, target_doc.id):
                    rel = await self._add_relationship_if_missing(
                        source_id=doc.id,
                        target_id=target_doc.id,
                        rel_type="parent_sow",
                        metadata={"auto_detected": True, "rule": "shared_party_msa_sow"},
                    )
                    if rel:
                        created_relationships.append(rel)

        return created_relationships

    async def _share_parties(self, doc_a_id: uuid.UUID, doc_b_id: uuid.UUID) -> bool:
        """Check if two documents share at least one actual counterparty (excluding governing jurisdictions)."""
        stmt_a = (
            select(DocumentEntity.entity_id)
            .join(EntityNode, DocumentEntity.entity_id == EntityNode.id)
            .where(
                DocumentEntity.document_id == doc_a_id,
                DocumentEntity.role != "governing_jurisdiction",
                EntityNode.entity_type != "jurisdiction",
            )
        )
        stmt_b = (
            select(DocumentEntity.entity_id)
            .join(EntityNode, DocumentEntity.entity_id == EntityNode.id)
            .where(
                DocumentEntity.document_id == doc_b_id,
                DocumentEntity.role != "governing_jurisdiction",
                EntityNode.entity_type != "jurisdiction",
            )
        )
        res_a = set((await self.session.execute(stmt_a)).scalars().all())
        res_b = set((await self.session.execute(stmt_b)).scalars().all())
        return len(res_a.intersection(res_b)) > 0

    async def _add_relationship_if_missing(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        rel_type: str,
        metadata: dict[str, Any],
    ) -> DocumentRelationship | None:
        """Helper to create relationship edge if not existing."""
        stmt = select(DocumentRelationship).where(
            DocumentRelationship.source_document_id == source_id,
            DocumentRelationship.target_document_id == target_id,
            DocumentRelationship.relationship_type == rel_type,
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        if existing:
            return None

        rel = DocumentRelationship(
            source_document_id=source_id,
            target_document_id=target_id,
            relationship_type=rel_type,
            metadata_=metadata,
        )
        self.session.add(rel)
        await self.session.flush()
        return rel

    async def get_graph_data(
        self,
        root_document_id: uuid.UUID | None = None,
        depth: int = 3,
        include_entities: bool = True,
    ) -> GraphData:
        """Fetch nodes and edges formatted for D3.js force-directed graph."""
        nodes: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []
        entity_nodes: list[GraphNode] = []

        # 1. Fetch all documents (or traverse from root)
        doc_stmt = select(Document).order_by(Document.upload_timestamp.desc())
        doc_res = await self.session.execute(doc_stmt)
        all_docs = doc_res.scalars().all()

        for d in all_docs:
            d_meta = d.metadata_ or {}
            c_type = d_meta.get("contract_type", "other")
            node = GraphNode(
                id=str(d.id),
                label=d_meta.get("title") or d.filename,
                node_type=c_type,
                document_id=str(d.id),
                status=d.processing_status,
                file_type=d.file_type,
                page_count=d.page_count,
                metadata={
                    "filename": d.filename,
                    "effective_date": d_meta.get("effective_date"),
                    "expiration_date": d_meta.get("expiration_date"),
                    "governing_law": d_meta.get("governing_law"),
                    "total_value_usd": d_meta.get("total_value_usd"),
                },
            )
            nodes[str(d.id)] = node

        # 2. Fetch Document Relationships
        rel_stmt = select(DocumentRelationship)
        rel_res = await self.session.execute(rel_stmt)
        all_rels = rel_res.scalars().all()

        for r in all_rels:
            s_id = str(r.source_document_id)
            t_id = str(r.target_document_id)
            if s_id in nodes and t_id in nodes:
                edge = GraphEdge(
                    id=str(r.id),
                    source=s_id,
                    target=t_id,
                    relationship_type=r.relationship_type,
                    label=r.relationship_type.replace("_", " ").title(),
                    weight=1.5,
                )
                edges.append(edge)

        # 3. Fetch Entities if requested
        if include_entities:
            ent_stmt = select(EntityNode).options(selectinload(EntityNode.document_links))
            ent_res = await self.session.execute(ent_stmt)
            all_entities = ent_res.scalars().all()

            for ent in all_entities:
                ent_id = f"entity_{ent.id}"
                e_node = GraphNode(
                    id=ent_id,
                    label=ent.name,
                    node_type=ent.entity_type,
                    metadata={
                        "normalized_name": ent.normalized_name,
                        "aliases": ent.aliases,
                        "document_count": len(ent.document_links),
                    },
                )
                entity_nodes.append(e_node)

                # Link entity to documents
                for link in ent.document_links:
                    d_id = str(link.document_id)
                    if d_id in nodes:
                        edges.append(
                            GraphEdge(
                                id=f"edge_{ent.id}_{link.document_id}",
                                source=ent_id,
                                target=d_id,
                                relationship_type="party_to",
                                label=link.role.replace("_", " ").title(),
                                weight=1.0,
                            )
                        )

        # 4. If root_document_id specified, filter to subgraph within depth
        if root_document_id:
            root_str = str(root_document_id)
            visited_nodes: set[str] = {root_str}
            current_level: set[str] = {root_str}

            for _ in range(depth):
                next_level: set[str] = set()
                for edge in edges:
                    if edge.source in current_level and edge.target not in visited_nodes:
                        next_level.add(edge.target)
                        visited_nodes.add(edge.target)
                    elif edge.target in current_level and edge.source not in visited_nodes:
                        next_level.add(edge.source)
                        visited_nodes.add(edge.source)
                current_level = next_level

            # Filter nodes and edges
            filtered_nodes = [n for n in nodes.values() if n.id in visited_nodes]
            filtered_entities = [n for n in entity_nodes if n.id in visited_nodes]
            filtered_edges = [
                e for e in edges if e.source in visited_nodes and e.target in visited_nodes
            ]

            return GraphData(
                nodes=filtered_nodes,
                edges=filtered_edges,
                entity_nodes=filtered_entities,
                total_contracts=len(filtered_nodes),
                total_entities=len(filtered_entities),
                total_relationships=len(filtered_edges),
            )

        all_node_list = list(nodes.values())
        return GraphData(
            nodes=all_node_list,
            edges=edges,
            entity_nodes=entity_nodes,
            total_contracts=len(all_node_list),
            total_entities=len(entity_nodes),
            total_relationships=len(edges),
        )

    async def get_document_stack(self, root_document_id: uuid.UUID) -> DocumentStack:
        """Construct hierarchical tree view for document stack view."""
        root_doc = await self.session.get(Document, root_document_id)
        if not root_doc:
            raise ValueError(f"Document {root_document_id} not found")

        root_meta = root_doc.metadata_ or {}
        root_item = DocumentStackItem(
            document_id=root_doc.id,
            filename=root_doc.filename,
            title=root_meta.get("title"),
            contract_type=root_meta.get("contract_type", "other"),
            risk_score=root_meta.get("risk_score"),
            effective_date=root_meta.get("effective_date"),
            expiration_date=root_meta.get("expiration_date"),
            parties=[
                p.get("name", "")
                for p in root_meta.get("extracted_parties", [])
                if isinstance(p, dict)
            ],
            children=[],
        )

        # Traverse outbound relationships (children)
        total_descendants = 0
        total_value = root_meta.get("total_value_usd", 0.0) or 0.0

        rel_stmt = (
            select(DocumentRelationship)
            .options(selectinload(DocumentRelationship.target_document))
            .where(
                (DocumentRelationship.source_document_id == root_doc.id)
                | (DocumentRelationship.target_document_id == root_doc.id)
            )
        )
        rel_res = await self.session.execute(rel_stmt)
        rels = rel_res.scalars().all()

        seen_child_ids: set[uuid.UUID] = {root_doc.id}

        for r in rels:
            child_doc_id = (
                r.target_document_id
                if r.source_document_id == root_doc.id
                else r.source_document_id
            )
            if child_doc_id in seen_child_ids:
                continue

            child_doc = await self.session.get(Document, child_doc_id)
            if child_doc:
                seen_child_ids.add(child_doc.id)
                total_descendants += 1
                c_meta = child_doc.metadata_ or {}
                if c_meta.get("total_value_usd"):
                    total_value += c_meta.get("total_value_usd", 0.0)

                child_item = DocumentStackItem(
                    document_id=child_doc.id,
                    filename=child_doc.filename,
                    title=c_meta.get("title"),
                    contract_type=c_meta.get("contract_type", "other"),
                    risk_score=c_meta.get("risk_score"),
                    effective_date=c_meta.get("effective_date"),
                    expiration_date=c_meta.get("expiration_date"),
                    parties=[
                        p.get("name", "")
                        for p in c_meta.get("extracted_parties", [])
                        if isinstance(p, dict)
                    ],
                    children=[],
                )
                root_item.children.append(child_item)

        return DocumentStack(
            root_document_id=root_doc.id,
            root_filename=root_doc.filename,
            stack=root_item,
            total_descendants=total_descendants,
            total_value_usd=round(total_value, 2) if total_value else None,
        )

    async def create_relationship(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        rel_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentRelationship:
        """Manually link two contracts."""
        stmt = select(DocumentRelationship).where(
            DocumentRelationship.source_document_id == source_id,
            DocumentRelationship.target_document_id == target_id,
            DocumentRelationship.relationship_type == rel_type,
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        if existing:
            return existing

        rel = DocumentRelationship(
            source_document_id=source_id,
            target_document_id=target_id,
            relationship_type=rel_type,
            metadata_=metadata or {},
        )
        self.session.add(rel)
        await self.session.flush()
        return rel

    async def delete_relationship(self, relationship_id: uuid.UUID) -> bool:
        """Remove a relationship edge."""
        stmt = delete(DocumentRelationship).where(DocumentRelationship.id == relationship_id)
        res = await self.session.execute(stmt)
        await self.session.flush()
        return (res.rowcount or 0) > 0

    async def get_document_relationships(
        self, document_id: uuid.UUID
    ) -> list[DocumentRelationshipResponse]:
        """Fetch all relationships connected to a document."""
        stmt = (
            select(DocumentRelationship)
            .options(
                selectinload(DocumentRelationship.source_document),
                selectinload(DocumentRelationship.target_document),
            )
            .where(
                (DocumentRelationship.source_document_id == document_id)
                | (DocumentRelationship.target_document_id == document_id)
            )
        )
        res = await self.session.execute(stmt)
        rels = res.scalars().all()

        responses: list[DocumentRelationshipResponse] = []
        for r in rels:
            responses.append(
                DocumentRelationshipResponse(
                    id=r.id,
                    source_document_id=r.source_document_id,
                    target_document_id=r.target_document_id,
                    source_filename=r.source_document.filename if r.source_document else "Unknown",
                    target_filename=r.target_document.filename if r.target_document else "Unknown",
                    relationship_type=r.relationship_type,
                    metadata=r.metadata_ or {},
                )
            )
        return responses

    async def get_entities(
        self,
        entity_type: str | None = None,
        search_query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> EntityListResponse:
        """Fetch list of extracted entities with contract counts."""
        query = select(EntityNode).options(selectinload(EntityNode.document_links))

        if entity_type:
            query = query.where(EntityNode.entity_type == entity_type)
        if search_query:
            query = query.where(
                EntityNode.normalized_name.ilike(f"%{search_query.strip().lower()}%")
                | EntityNode.name.ilike(f"%{search_query.strip()}%")
            )

        total_stmt = select(func.count(EntityNode.id))
        if entity_type:
            total_stmt = total_stmt.where(EntityNode.entity_type == entity_type)
        if search_query:
            total_stmt = total_stmt.where(
                EntityNode.normalized_name.ilike(f"%{search_query.strip().lower()}%")
                | EntityNode.name.ilike(f"%{search_query.strip()}%")
            )

        total_res = await self.session.execute(total_stmt)
        total_count = total_res.scalar() or 0

        query = query.order_by(EntityNode.name).limit(limit).offset(offset)
        res = await self.session.execute(query)
        entities = res.scalars().all()

        items: list[EntityItemResponse] = []
        for e in entities:
            items.append(
                EntityItemResponse(
                    id=e.id,
                    name=e.name,
                    normalized_name=e.normalized_name,
                    entity_type=e.entity_type,
                    aliases=e.aliases,
                    document_count=len(e.document_links),
                    created_at=e.created_at.isoformat() if e.created_at else "",
                )
            )

        return EntityListResponse(entities=items, total=total_count)
