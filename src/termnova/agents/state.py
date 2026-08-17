"""Agent state schema for LangGraph multi-step reasoning workflows."""

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Unified state schema flowing through the LangGraph reasoning workflow."""

    query: str
    rewritten_query: str | None
    sub_queries: list[str]
    retrieved_chunks: list[Any]
    graded_chunks: list[Any]
    generation_attempts: int
    answer: str
    citations: list[Any]
    faithfulness_score: float
    confidence_score: float
    hallucination_flags: list[Any]
    should_rewrite: bool
    should_decompose: bool
    route_decision: str  # "retrieve" | "generate" | "rewrite" | "fail"
    nodes_visited: list[str]
    error: str | None
    metadata: dict[str, Any]
