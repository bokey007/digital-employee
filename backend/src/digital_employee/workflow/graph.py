"""Build and compile the LangGraph workflow."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from digital_employee.workflow.edges import (
    check_all_leads_approved,
    check_anuj_decision,
)
from digital_employee.workflow.nodes import (
    complete,
    consolidate_newsletter,
    incorporate_feedback,
    initiate_collection,
    reword_content,
    seek_anuj_approval,
    seek_lead_approval,
    send_to_client,
)
from digital_employee.workflow.state import WorkflowState


def build_graph() -> StateGraph:
    """Construct the newsletter automation workflow graph.

    Graph structure:
        INITIATE → (wait) → REWORD → SEEK_LEAD_APPROVAL
            ↳ all approved? → CONSOLIDATE → SEEK_ANUJ_APPROVAL
                ↳ approved? → SEND_TO_CLIENT → COMPLETE
                ↳ feedback? → INCORPORATE_FEEDBACK → SEEK_ANUJ_APPROVAL
            ↳ pending? → (wait for more approvals)
    """
    graph = StateGraph(WorkflowState)

    # ── Add nodes ────────────────────────────────────────────────────────────
    graph.add_node("initiate", initiate_collection)
    graph.add_node("reword", reword_content)
    graph.add_node("seek_lead_approval", seek_lead_approval)
    graph.add_node("consolidate", consolidate_newsletter)
    graph.add_node("seek_anuj_approval", seek_anuj_approval)
    graph.add_node("incorporate_feedback", incorporate_feedback)
    graph.add_node("send_to_client", send_to_client)
    graph.add_node("complete", complete)

    # ── Entry point ──────────────────────────────────────────────────────────
    graph.set_entry_point("initiate")

    # ── Edges ────────────────────────────────────────────────────────────────

    # After initiation, the graph pauses — the email listener will resume it
    # when leads respond. We end here; the graph is re-invoked with updated
    # state when a response arrives.
    graph.add_edge("initiate", END)

    # After rewording, send for lead approval
    graph.add_edge("reword", "seek_lead_approval")

    # After seeking lead approval, the graph pauses again (waiting for reply)
    graph.add_edge("seek_lead_approval", END)

    # After consolidation, send to Anuj
    graph.add_edge("consolidate", "seek_anuj_approval")

    # After seeking Anuj approval, pause (waiting for reply)
    graph.add_edge("seek_anuj_approval", END)

    # After incorporating feedback, re-submit to Anuj
    graph.add_edge("incorporate_feedback", "seek_anuj_approval")

    # After sending to client, complete
    graph.add_edge("send_to_client", "complete")

    # Complete is terminal
    graph.add_edge("complete", END)

    return graph


def compile_graph(checkpointer=None):
    """Build and compile the graph with an optional checkpointer.

    Args:
        checkpointer: A LangGraph checkpointer (e.g. PostgresSaver) for
                       persisting state across restarts.

    Returns:
        A compiled LangGraph ready for invocation.
    """
    graph = build_graph()
    return graph.compile(checkpointer=checkpointer)
