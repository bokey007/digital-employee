"""LangGraph node functions — each node performs one step of the workflow."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
import yaml

from digital_employee.models import (
    AuditAction,
    AuditLog,
    EditionStatus,
    LeadSubmission,
    NewsletterEdition,
    SubmissionStatus,
)
from digital_employee.services.email_service import EmailService
from digital_employee.services.llm_service import LLMService
from digital_employee.services.template_service import TemplateService
from digital_employee.settings import Settings
from digital_employee.workflow.state import LeadData, WorkflowState

logger = structlog.get_logger(__name__)


def _load_teams(config_path: str = "config/teams.yaml") -> list[dict]:
    """Load team/lead configuration from YAML."""
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return data.get("programmes", [])


# ── Node Functions ───────────────────────────────────────────────────────────


def initiate_collection(state: WorkflowState) -> dict:
    """Node 1: Start a new newsletter cycle — email all leads requesting updates."""
    settings = Settings()
    email_svc = EmailService(settings)
    teams = _load_teams()

    leads: dict[str, LeadData] = {}

    for programme in teams:
        prog_name = programme["name"]
        for ws in programme.get("workstreams", []):
            ws_name = ws["name"]
            lead_email = ws["lead_email"]
            lead_name = ws["lead_name"]

            # Send request email
            email_svc.send_update_request(
                lead_email=lead_email,
                lead_name=lead_name,
                programme=prog_name,
                workstream=ws_name,
                edition_title=state["edition_title"],
            )

            leads[lead_email] = LeadData(
                lead_email=lead_email,
                lead_name=lead_name,
                programme=prog_name,
                workstream=ws_name,
                raw_content=None,
                reworded_content=None,
                status="pending",
                reminder_count=0,
            )

    logger.info("collection_initiated", lead_count=len(leads))

    return {
        "leads": leads,
        "status": "collecting",
    }


async def reword_content(state: WorkflowState) -> dict:
    """Node 3: LLM rewrites the raw content professionally."""
    settings = Settings()
    llm_svc = LLMService(settings)

    lead_email = state["current_lead_email"]
    if not lead_email or lead_email not in state["leads"]:
        return {"error": f"No current lead set for rewording: {lead_email}"}

    lead = state["leads"][lead_email]
    raw = lead.get("raw_content", "")

    if not raw:
        return {"error": f"No raw content for lead {lead_email}"}

    reworded = await llm_svc.reword_content(
        raw_text=raw,
        programme=lead["programme"],
        workstream=lead["workstream"],
    )

    # Update lead state
    updated_leads = {**state["leads"]}
    updated_leads[lead_email] = {**lead, "reworded_content": reworded, "status": "reworded"}

    logger.info("content_reworded", lead=lead_email)
    return {"leads": updated_leads, "status": "rewording"}


def seek_lead_approval(state: WorkflowState) -> dict:
    """Node 4: Email reworded content to the lead for sign-off."""
    settings = Settings()
    email_svc = EmailService(settings)

    lead_email = state["current_lead_email"]
    if not lead_email or lead_email not in state["leads"]:
        return {"error": f"No current lead for approval: {lead_email}"}

    lead = state["leads"][lead_email]

    email_svc.send_approval_request(
        lead_email=lead_email,
        lead_name=lead["lead_name"],
        programme=lead["programme"],
        workstream=lead["workstream"],
        reworded_content=lead.get("reworded_content", ""),
    )

    updated_leads = {**state["leads"]}
    updated_leads[lead_email] = {**lead, "status": "approval_sent"}

    logger.info("approval_requested", lead=lead_email)
    return {"leads": updated_leads, "status": "awaiting_lead_approval"}


async def consolidate_newsletter(state: WorkflowState) -> dict:
    """Node 5: All leads approved — merge into the standard newsletter HTML."""
    settings = Settings()
    llm_svc = LLMService(settings)
    template_svc = TemplateService()

    # Gather all approved sections
    sections = []
    for lead_data in state["leads"].values():
        if lead_data["status"] == "approved" and lead_data.get("reworded_content"):
            sections.append(
                {
                    "programme": lead_data["programme"],
                    "workstream": lead_data["workstream"],
                    "lead_name": lead_data["lead_name"],
                    "content": lead_data["reworded_content"],
                }
            )

    if not sections:
        return {"error": "No approved sections to consolidate"}

    # LLM consolidation
    content_html = await llm_svc.consolidate_newsletter(sections)

    # Render into the full newsletter template
    newsletter_html = template_svc.render_newsletter(
        title=state["edition_title"],
        date=datetime.now(timezone.utc),
        content_html=content_html,
    )

    logger.info("newsletter_consolidated", sections=len(sections))
    return {
        "newsletter_html": newsletter_html,
        "status": "consolidating",
    }


def seek_anuj_approval(state: WorkflowState) -> dict:
    """Node 6: Email the newsletter to Anuj for review."""
    settings = Settings()
    email_svc = EmailService(settings)

    email_svc.send_newsletter_for_review(
        reviewer_email=settings.anuj_email,
        reviewer_name=settings.anuj_name,
        newsletter_html=state["newsletter_html"] or "",
        edition_title=state["edition_title"],
    )

    logger.info("sent_to_anuj")
    return {
        "status": "awaiting_anuj_approval",
        "attempt_count": state.get("attempt_count", 0) + 1,
    }


async def incorporate_feedback(state: WorkflowState) -> dict:
    """Node 7: LLM revises the newsletter based on Anuj's feedback."""
    settings = Settings()
    llm_svc = LLMService(settings)
    template_svc = TemplateService()

    feedback = state.get("anuj_feedback", "")
    current_html = state.get("newsletter_html", "")

    if not feedback:
        return {"error": "No feedback to incorporate"}

    revised_content = await llm_svc.incorporate_feedback(current_html, feedback)

    # Re-render with template
    newsletter_html = template_svc.render_newsletter(
        title=state["edition_title"],
        date=datetime.now(timezone.utc),
        content_html=revised_content,
    )

    logger.info("feedback_incorporated", attempt=state.get("attempt_count", 0))
    return {
        "newsletter_html": newsletter_html,
        "anuj_feedback": None,  # Clear feedback after incorporating
        "status": "incorporating_feedback",
    }


def send_to_client(state: WorkflowState) -> dict:
    """Node 8: Anuj approved — send the final newsletter to the distribution list."""
    settings = Settings()
    email_svc = EmailService(settings)

    email_svc.send_newsletter_to_client(
        distribution_list=settings.distribution_list,
        newsletter_html=state["newsletter_html"] or "",
        edition_title=state["edition_title"],
    )

    logger.info("sent_to_client", recipients=len(settings.distribution_list))
    return {"status": "sent_to_client"}


def complete(state: WorkflowState) -> dict:
    """Node 9: Archive the edition and log completion."""
    logger.info("workflow_completed", edition=state["edition_title"])
    return {"status": "completed"}
