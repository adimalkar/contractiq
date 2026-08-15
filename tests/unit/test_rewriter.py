"""Unit tests for QueryRewriter contextual reformulation, HyDE, and query decomposition."""

import pytest

from contractiq.rag.rewriter import QueryRewriter


@pytest.mark.unit
@pytest.mark.asyncio
async def test_passthrough_simple_query():
    """Verify that a single direct question passes through without unnecessary mutation."""
    rewriter = QueryRewriter()
    result = await rewriter.rewrite("What is the payment schedule?")
    assert result.original == "What is the payment schedule?"
    assert result.rewritten == "What is the payment schedule?"
    assert result.strategy_used == "passthrough"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_contextual_rewrite_with_history():
    """Verify that follow-up short queries are enriched with conversation context."""
    rewriter = QueryRewriter()
    history = [
        {
            "query": "What are the liability limits in the Master Services Agreement?",
            "response": "...",
        }
    ]
    result = await rewriter.rewrite("What about termination?", conversation_history=history)
    assert result.strategy_used == "contextual"
    assert "termination" in result.rewritten.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hyde_passage_generation():
    """Verify that HyDE mode creates a hypothetical legal answer passage."""
    rewriter = QueryRewriter()
    result = await rewriter.rewrite("What are the indemnification clauses?", use_hyde=True)
    assert result.hyde_passage is not None
    assert len(result.hyde_passage) > 20


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_decomposition_multi_part():
    """Verify that conjunction-heavy queries are deconstructed into focused sub-queries."""
    rewriter = QueryRewriter()
    result = await rewriter.rewrite(
        "What are the payment terms and also what are the insurance coverage requirements?"
    )
    assert result.strategy_used == "decomposition"
    assert len(result.sub_queries) == 2
