"""Integration tests for LangGraph stateful multi-step agent reasoning workflow."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.agents.graph import build_rag_graph
from termnova.pipeline.embedder import EmbeddingService
from termnova.rag.engine import RAGEngine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_langgraph_graph_compiles():
    """Verify that the LangGraph StateGraph builds and compiles without error."""
    graph = build_rag_graph()
    assert graph is not None
    assert "classify" in graph.nodes
    assert "decompose" in graph.nodes
    assert "retrieve" in graph.nodes
    assert "generate" in graph.nodes


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agentic_query_execution(test_session: AsyncSession, test_embedder: EmbeddingService):
    """Verify that query_agentic runs end-to-end through the LangGraph workflow."""
    engine = RAGEngine(test_session, embedder=test_embedder)
    result = await engine.query_agentic("What are the key liability caps and payment terms?")
    assert result is not None
    assert result.query_id is not None
    assert len(result.answer) > 0
    assert result.model_used.endswith("(LangGraph)")
