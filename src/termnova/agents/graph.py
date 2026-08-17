"""LangGraph StateGraph builder for Termnova agentic reasoning."""

from langgraph.graph import END, StateGraph

from termnova.agents.nodes import (
    classify_query,
    decide_route,
    decompose_query,
    fail_node,
    generate_node,
    grade_node,
    guardrails_node,
    retrieve_node,
    rewrite_node,
)
from termnova.agents.state import AgentState


def build_rag_graph():
    """Construct the compiled agentic RAG workflow graph."""
    graph = StateGraph(AgentState)

    # Add reasoning nodes
    graph.add_node("classify", classify_query)
    graph.add_node("decompose", decompose_query)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("generate", generate_node)
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("fail", fail_node)

    # Set entry point
    graph.set_entry_point("classify")

    # Conditional routing after classification (decompose vs direct retrieval)
    graph.add_conditional_edges(
        "classify",
        lambda state: "decompose" if state.get("should_decompose") else "retrieve",
        {
            "decompose": "decompose",
            "retrieve": "retrieve",
        },
    )

    graph.add_edge("decompose", "retrieve")
    graph.add_edge("retrieve", "grade")

    # Conditional routing after grading (generate vs rewrite vs fail)
    graph.add_conditional_edges(
        "grade",
        decide_route,
        {
            "generate": "generate",
            "rewrite": "rewrite",
            "fail": "fail",
        },
    )

    # Loop back from rewrite to retrieval
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("generate", "guardrails")

    # Conditional routing after guardrails
    graph.add_conditional_edges(
        "guardrails",
        lambda state: (
            "rewrite"
            if state.get("should_rewrite") and state.get("generation_attempts", 0) < 2
            else "end"
        ),
        {
            "rewrite": "rewrite",
            "end": END,
        },
    )

    graph.add_edge("fail", END)

    return graph.compile()
