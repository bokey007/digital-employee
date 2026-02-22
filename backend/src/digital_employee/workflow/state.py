"""LangGraph workflow state definition."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


class LeadData(TypedDict):
    """State data for a single lead's submission."""

    lead_email: str
    lead_name: str
    programme: str
    workstream: str
    raw_content: str | None
    reworded_content: str | None
    status: str  # pending | received | reworded | approval_sent | approved | changes_requested
    reminder_count: int


class WorkflowState(TypedDict):
    """The complete state carried through the LangGraph workflow.

    This state persists across checkpoints and survives process restarts.
    """

    # Edition identity
    edition_id: str  # UUID as string for serialisation
    edition_title: str

    # Overall workflow status
    status: str

    # Lead tracking
    leads: dict[str, LeadData]  # email -> LeadData
    current_lead_email: str | None  # Lead being processed right now

    # Newsletter content
    newsletter_html: str | None

    # Anuj review
    anuj_feedback: str | None
    attempt_count: int

    # Error tracking
    error: str | None
