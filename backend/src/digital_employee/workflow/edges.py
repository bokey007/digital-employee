"""Conditional edge functions for the LangGraph workflow."""

from __future__ import annotations

from digital_employee.workflow.state import WorkflowState


def check_all_leads_responded(state: WorkflowState) -> str:
    """After processing a lead response, check if all leads have responded.

    Returns:
        'all_done' — all leads have submitted content → proceed to reword
        'waiting' — still waiting for more responses
    """
    leads = state.get("leads", {})
    if not leads:
        return "waiting"

    for lead in leads.values():
        if lead["status"] == "pending":
            return "waiting"

    return "all_done"


def check_all_leads_approved(state: WorkflowState) -> str:
    """After a lead approval, check if all leads have approved.

    Returns:
        'all_approved' — all leads approved → consolidate
        'has_pending' — some leads still pending approval
        'has_reword' — a lead needs content reworded (first time or after changes)
    """
    leads = state.get("leads", {})

    for lead in leads.values():
        if lead["status"] == "received":
            return "has_reword"
        if lead["status"] in ("reworded", "approval_sent", "changes_requested"):
            return "has_pending"

    # Check if all are approved
    all_approved = all(lead["status"] == "approved" for lead in leads.values())
    return "all_approved" if all_approved else "has_pending"


def check_anuj_decision(state: WorkflowState) -> str:
    """After Anuj responds, route to send or incorporate feedback.

    Returns:
        'approved' — Anuj approved → send to client
        'feedback' — Anuj has feedback → incorporate and re-submit
    """
    feedback = state.get("anuj_feedback")
    status = state.get("status", "")

    # If status indicates Anuj approved (set by the email handler)
    if status == "anuj_approved" or not feedback:
        return "approved"
    return "feedback"


def route_after_initiation(state: WorkflowState) -> str:
    """After initiating collection, move to waiting state."""
    return "wait_for_responses"


def next_lead_to_process(state: WorkflowState) -> str | None:
    """Find the next lead that needs rewording.

    Returns:
        The email of the next lead to process, or None.
    """
    leads = state.get("leads", {})
    for email, lead in leads.items():
        if lead["status"] == "received":
            return email
    return None
