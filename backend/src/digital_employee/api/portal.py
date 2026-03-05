"""Portal API — secure, token-gated endpoints for leads and reviewers."""

from __future__ import annotations

import json
import uuid as _uuid
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessageChunk
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from digital_employee.database import get_db
from digital_employee.models import (
    AuditLog,
    AuditAction,
    LeadSubmission,
    NewsletterEdition,
    PortalToken,
    SubmissionStatus,
)
from digital_employee.services.agent_factory import (
    checkpointer_context,
    create_portal_agent,
    build_portal_submit_system_prompt,
    build_portal_review_system_prompt,
)
from digital_employee.services.llm_service import LLMService
from digital_employee.services.token_service import validate_token_async, lookup_token_async
from digital_employee.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/portal", tags=["portal"])


def _extract_content_body(html: str | None) -> str:
    """Extract the newsletter content body from any HTML format.

    Handles two cases:
    - Content body HTML (tables/divs with section banners) → returned as-is
    - Full HTML document (<!DOCTYPE> ... <body>content</body> ...) → extracts just body innerHTML

    This ensures edition.html_content always stores the content body regardless of
    whether the AI incorrectly wraps its output in a full HTML document.
    """
    if not html:
        return ""
    stripped = html.strip()
    if not (stripped.lower().startswith("<!doctype") or stripped.lower().startswith("<html")):
        return stripped  # already content body
    # Full HTML document — extract body innerHTML
    import re
    body_match = re.search(r"<body[^>]*>(.*?)</body>", stripped, re.DOTALL | re.IGNORECASE)
    if body_match:
        return body_match.group(1).strip()
    return stripped  # fallback: return as-is


# ── Request / Response Schemas ───────────────────────────────────────────────


class TokenInfoResponse(BaseModel):
    actor_name: str
    actor_email: str
    role: str
    action_type: str
    context: dict
    reworded_content: str | None = None
    edition_title: str | None = None
    previous_submission: str | None = None  # Last approved submission for this workstream


class SubmitRequest(BaseModel):
    token: str
    raw_content: str


class SubmitResponse(BaseModel):
    reworded_content: str
    submission_id: str


class ChatRequest(BaseModel):
    token: str
    user_message: str
    current_html: str | None = None  # Latest HTML from the frontend — used for reviewer roles


class ApproveRequest(BaseModel):
    token: str
    final_content: str


class FeedbackRequest(BaseModel):
    token: str
    feedback_text: str


class WorkstreamEntry(BaseModel):
    programme: str
    workstream: str
    lead_name: str
    content_html: str


class ProgrammeSectionEntry(BaseModel):
    programme: str
    lead_name: str
    section_html: str


class ReferenceDataResponse(BaseModel):
    workstream_submissions: list[WorkstreamEntry] = []
    programme_sections: list[ProgrammeSectionEntry] = []
    ashwin_draft: str | None = None  # Anuj only



# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/token/{token_str}", response_model=TokenInfoResponse)
async def get_token_info(token_str: str, db: AsyncSession = Depends(get_db)):
    """Validate a portal token and return the context for that session."""
    # Use read-only lookup — allows already-used tokens so leads can
    # always reload their link to view their submitted content.
    pt = await lookup_token_async(db, token_str)
    if not pt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired link.")

    ctx = json.loads(pt.context_json)

    # If this is a lead submission token, check if content was already reworded
    reworded = None
    if pt.submission_id:
        result = await db.execute(
            select(LeadSubmission).where(LeadSubmission.id == pt.submission_id)
        )
        sub = result.scalars().first()
        if sub and sub.reworded_content:
            reworded = sub.reworded_content

    # Fetch previous approved submission for this workstream (for lead reference panel)
    previous_submission: str | None = None
    if pt.role == "lead" and pt.submission_id:
        workstream = ctx.get("workstream", "")
        # Exclude the current submission — find last APPROVED one
        prev_result = await db.execute(
            select(LeadSubmission)
            .where(
                LeadSubmission.lead_email == pt.actor_email,
                LeadSubmission.workstream == workstream,
                LeadSubmission.status == SubmissionStatus.APPROVED,
                LeadSubmission.id != pt.submission_id,
            )
            .order_by(LeadSubmission.created_at.desc())
            .limit(1)
        )
        prev_sub = prev_result.scalars().first()
        if prev_sub and prev_sub.reworded_content:
            previous_submission = prev_sub.reworded_content

    elif pt.role == "programme_lead" and pt.edition_id:
        # For programme leads: try two sources for "previous month" content:
        # 1. Previous COMPLETED edition's programme_lead_feedback → the actual approved section HTML
        # 2. Fallback: aggregate previous approved LeadSubmission records for this programme's
        #    workstreams (same edition's older submissions). This guarantees data on first run.
        programme = ctx.get("programme", "")

        # --- Tier 1: look up previous completed edition ---
        prev_edition_result = await db.execute(
            select(NewsletterEdition)
            .where(
                NewsletterEdition.id != pt.edition_id,
                NewsletterEdition.status.in_(["completed", "sent_to_client"]),
            )
            .order_by(NewsletterEdition.sent_at.desc())
            .limit(1)
        )
        prev_edition = prev_edition_result.scalars().first()
        if prev_edition and prev_edition.programme_lead_feedback:
            try:
                prev_meta = json.loads(prev_edition.programme_lead_feedback)
                prog_data = prev_meta.get(pt.actor_email.lower(), {})
                prev_html = prog_data.get("section_html") or ""
                if prev_html:
                    previous_submission = prev_html
            except (json.JSONDecodeError, AttributeError):
                pass

        # --- Tier 2 fallback: build from previous approved LeadSubmissions for this programme ---
        if not previous_submission and programme:
            prev_subs_result = await db.execute(
                select(LeadSubmission)
                .where(
                    LeadSubmission.programme == programme,
                    LeadSubmission.status == SubmissionStatus.APPROVED,
                    LeadSubmission.edition_id != pt.edition_id,
                )
                .order_by(LeadSubmission.created_at.desc())
                .limit(10)
            )
            prev_subs = prev_subs_result.scalars().all()
            if prev_subs:
                parts = []
                seen_workstreams: set[str] = set()
                for s in prev_subs:
                    if s.workstream not in seen_workstreams and s.reworded_content:
                        seen_workstreams.add(s.workstream)
                        parts.append(
                            f"<h4>{s.workstream}</h4>{s.reworded_content}"
                        )
                if parts:
                    previous_submission = "".join(parts)

    elif pt.role in ("ashwin", "anuj") and pt.edition_id:
        # Ashwin/Anuj: edition.html_content holds the content body (not full template).
        # Render the full newsletter HTML for portal display; keep content body for the AI.
        edition_result = await db.execute(
            select(NewsletterEdition).where(NewsletterEdition.id == pt.edition_id)
        )
        edition_obj = edition_result.scalars().first()
        if edition_obj and edition_obj.html_content:
            from digital_employee.services.template_service import TemplateService
            from datetime import datetime, timezone
            template_svc = TemplateService()
            rendered_html = template_svc.render_newsletter(
                title=ctx.get("edition_title", edition_obj.title or ""),
                date=edition_obj.sent_at or datetime.now(timezone.utc),
                content_html=edition_obj.html_content,
            )
            ctx["section_html"] = rendered_html        # full template for portal display
            ctx["content_html"] = edition_obj.html_content  # content body for AI editing

        # Previous month: previous completed edition's content body
        prev_result = await db.execute(
            select(NewsletterEdition)
            .where(
                NewsletterEdition.id != pt.edition_id,
                NewsletterEdition.status.in_(["completed", "sent_to_client"]),
            )
            .order_by(NewsletterEdition.sent_at.desc())
            .limit(1)
        )
        prev_edition = prev_result.scalars().first()
        if prev_edition and prev_edition.html_content:
            previous_submission = prev_edition.html_content

    return TokenInfoResponse(
        actor_name=pt.actor_name,
        actor_email=pt.actor_email,
        role=pt.role,
        action_type=pt.action_type,
        context=ctx,
        reworded_content=reworded,
        edition_title=ctx.get("edition_title"),
        previous_submission=previous_submission,
    )


@router.get("/reference-data", response_model=ReferenceDataResponse)
async def get_reference_data(token_str: str, db: AsyncSession = Depends(get_db)):
    """Return source material for Ashwin and Anuj review portal.

    Ashwin: all approved workstream submissions + approved programme lead sections.
    Anuj:   same as Ashwin + edition.html_content (Ashwin's approved draft).
    """
    pt = await lookup_token_async(db, token_str)
    if not pt or pt.role not in ("ashwin", "anuj"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    if not pt.edition_id:
        return ReferenceDataResponse()

    # ── Fetch edition ─────────────────────────────────────────────────────────
    ed_result = await db.execute(
        select(NewsletterEdition).where(NewsletterEdition.id == pt.edition_id)
    )
    edition = ed_result.scalars().first()
    if not edition:
        return ReferenceDataResponse()

    # ── Workstream submissions (APPROVED status) ──────────────────────────────
    subs_result = await db.execute(
        select(LeadSubmission).where(
            LeadSubmission.edition_id == pt.edition_id,
            LeadSubmission.status == SubmissionStatus.APPROVED,
        ).order_by(LeadSubmission.programme, LeadSubmission.workstream)
    )
    subs = subs_result.scalars().all()
    workstream_submissions = [
        WorkstreamEntry(
            programme=s.programme or "",
            workstream=s.workstream or "",
            lead_name=s.lead_name or "",
            content_html=s.reworded_content or "",
        )
        for s in subs if s.reworded_content
    ]

    # ── Programme lead sections (from programme_lead_feedback JSON) ───────────
    import os, yaml
    teams_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "config", "teams.yaml"
    ))
    prog_lead_names: dict[str, str] = {}  # email → name
    if os.path.exists(teams_path):
        with open(teams_path) as f:
            teams_data = yaml.safe_load(f)
        for prog in teams_data.get("programmes", []):
            email = (prog.get("programme_lead_email") or "").lower()
            name = prog.get("programme_lead_name") or email
            prog_name = prog.get("name", "")
            if email:
                prog_lead_names[email] = {"name": name, "programme": prog_name}

    programme_sections = []
    if edition.programme_lead_feedback:
        try:
            pl_meta = json.loads(edition.programme_lead_feedback)
            for email, entry in pl_meta.items():
                section_html = entry.get("section_html", "")
                if section_html:
                    info = prog_lead_names.get(email.lower(), {})
                    programme_sections.append(ProgrammeSectionEntry(
                        programme=info.get("programme", email),
                        lead_name=info.get("name", email),
                        section_html=section_html,
                    ))
        except (json.JSONDecodeError, AttributeError):
            pass

    # ── Ashwin's final draft (Anuj only) ──────────────────────────────────────
    ashwin_draft: str | None = None
    if pt.role == "anuj" and edition.html_content:
        ashwin_draft = edition.html_content

    return ReferenceDataResponse(
        workstream_submissions=workstream_submissions,
        programme_sections=programme_sections,
        ashwin_draft=ashwin_draft,
    )


@router.post("/submit", response_model=SubmitResponse)
async def submit_content(body: SubmitRequest, db: AsyncSession = Depends(get_db)):
    """Lead submits raw content; AI rewords it instantly and returns the result."""
    settings = get_settings()
    pt = await validate_token_async(db, body.token)
    if not pt or pt.role != "lead" or pt.action_type != "submit":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired token.")

    if not pt.submission_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token not linked to a submission.")

    result = await db.execute(
        select(LeadSubmission).where(LeadSubmission.id == pt.submission_id)
    )
    sub = result.scalars().first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission record not found.")

    ctx = json.loads(pt.context_json)

    # Reword via LLM
    llm_svc = LLMService(settings)
    reworded = await llm_svc.reword_content(
        raw_text=body.raw_content,
        programme=ctx.get("programme", ""),
        workstream=ctx.get("workstream", ""),
    )

    # Persist raw + reworded content; keep token active for chat/approve
    sub.raw_content = body.raw_content
    sub.reworded_content = reworded
    sub.status = SubmissionStatus.PENDING  # stays PENDING until approved

    db.add(AuditLog(
        edition_id=sub.edition_id,
        action=AuditAction.CONTENT_REWORDED,
        actor=pt.actor_email,
        detail=f"Content submitted and reworded via portal for {pt.actor_name}",
    ))
    await db.commit()

    logger.info("portal_content_submitted", actor=pt.actor_email, workstream=ctx.get("workstream"))
    return SubmitResponse(reworded_content=reworded, submission_id=str(sub.id))


@router.post("/chat")
async def portal_chat(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Stream a multi-turn AI chat response. Uses direct LLM streaming for instant response."""
    settings = get_settings()
    pt = await validate_token_async(db, body.token)
    if not pt:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired token.")

    ctx = json.loads(pt.context_json)
    llm_svc = LLMService(settings)

    # Fetch current content to give the AI full context
    current_reworded: str = ""
    if pt.role == "lead" and pt.submission_id:
        # Workstream leads: fetch from DB (single authoritative copy)
        result = await db.execute(
            select(LeadSubmission).where(LeadSubmission.id == pt.submission_id)
        )
        sub = result.scalars().first()
        if sub and sub.reworded_content:
            current_reworded = sub.reworded_content
    elif pt.role in ("programme_lead", "ashwin", "anuj"):
        # Reviewer roles: prefer the canonical content body for AI editing.
        # ctx["content_html"] = content body (no template wrapper) — set by get_token_info.
        # body.current_html starts as full rendered template display HTML; after the first
        # AI edit it becomes the edited content body — we track this via a flag in the HTML.
        if pt.role in ("ashwin", "anuj") and ctx.get("content_html"):
            # For ashwin/anuj: always start from the canonical content body from DB.
            # If frontend updates with already-edited content body (no html/head/body tags),
            # prefer that so multi-turn edits are cumulative.
            frontend_html = (body.current_html or "").strip()
            is_full_template = frontend_html.startswith("<!DOCTYPE") or frontend_html.startswith("<html")
            if frontend_html and not is_full_template:
                current_reworded = frontend_html  # already edited content body from prior turn
            else:
                current_reworded = ctx["content_html"]  # canonical content body from DB
        elif body.current_html and body.current_html.strip():
            current_reworded = body.current_html  # programme_lead: use live frontend state
        elif ctx.get("section_html"):
            current_reworded = ctx["section_html"]
        elif pt.edition_id:
            edition_result = await db.execute(
                select(NewsletterEdition).where(NewsletterEdition.id == pt.edition_id)
            )
            edition_obj = edition_result.scalars().first()
            if edition_obj and edition_obj.html_content:
                current_reworded = edition_obj.html_content

    # Build role-appropriate system prompt
    if pt.role == "lead":
        prev_content: str | None = None
        result2 = await db.execute(
            select(LeadSubmission)
            .where(
                LeadSubmission.lead_email == pt.actor_email,
                LeadSubmission.workstream == ctx.get("workstream", ""),
                LeadSubmission.status == SubmissionStatus.APPROVED,
            )
            .order_by(LeadSubmission.created_at.desc())
            .limit(1)
        )
        prev_sub = result2.scalars().first()
        if prev_sub:
            prev_content = prev_sub.reworded_content
        system_prompt = build_portal_submit_system_prompt(
            actor_name=pt.actor_name,
            programme=ctx.get("programme", ""),
            workstream=ctx.get("workstream", ""),
            edition_title=ctx.get("edition_title", ""),
            previous_content=prev_content,
        )
    else:
        system_prompt = build_portal_review_system_prompt(
            actor_name=pt.actor_name,
            role=pt.role,
            edition_title=ctx.get("edition_title", ""),
        )

    # Build message list: system + current draft context + user request
    from langchain_core.messages import SystemMessage, AIMessage
    messages: list = [SystemMessage(content=system_prompt)]
    if current_reworded:
        messages.append(HumanMessage(
            content=f"Here is the current draft content to refine:\n\n{current_reworded}"
        ))
        messages.append(AIMessage(
            content="Got it — I have the current draft. What would you like me to change?"
        ))
    messages.append(HumanMessage(content=body.user_message))

    llm = llm_svc._llm

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for chunk in llm.astream(messages):
                if isinstance(chunk, AIMessageChunk) and isinstance(chunk.content, str) and chunk.content:
                    yield f"data: {json.dumps({'token': chunk.content})}\n\n"
        except Exception as exc:
            logger.error("portal_chat_stream_error", error=str(exc))
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    logger.info("portal_chat_streaming", actor=pt.actor_email, role=pt.role)
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )



@router.post("/approve")
async def portal_approve(body: ApproveRequest, db: AsyncSession = Depends(get_db)):
    """Approve content/newsletter via the portal. Triggers the appropriate Celery task."""
    pt = await validate_token_async(db, body.token)
    if not pt:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired token.")

    ctx = json.loads(pt.context_json)
    edition_title = ctx.get("edition_title", "Newsletter")

    if pt.role == "lead":
        # Update submission to APPROVED
        if not pt.submission_id:
            raise HTTPException(status_code=400, detail="No submission linked to token.")
        result = await db.execute(
            select(LeadSubmission).where(LeadSubmission.id == pt.submission_id)
        )
        sub = result.scalars().first()
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found.")

        # Update final content and status
        sub.reworded_content = body.final_content
        sub.status = SubmissionStatus.APPROVED
        pt.is_used = True

        db.add(AuditLog(
            edition_id=sub.edition_id,
            action=AuditAction.LEAD_APPROVED,
            actor=pt.actor_email,
            detail=f"{pt.actor_name} approved via portal — {ctx.get('workstream', '')}",
        ))
        await db.commit()

        # Dispatch the Celery task to route the workflow forward — the task creates
        # its own sync DB session, finds the submission by lead email, and calls
        # _check_and_route_after_lead_approvals internally.
        from digital_employee.tasks.workflow_tasks import handle_lead_reply
        handle_lead_reply.delay(
            sender_email=pt.actor_email,
            sender_name=pt.actor_name,
            intent="newsletter_approval",
            body_text=body.final_content,
            subject=f"Re: {edition_title}",
        )

    elif pt.role == "programme_lead":
        if pt.edition_id and body.final_content:
            # Persist the programme lead's edited section_html back to the edition
            # BEFORE dispatching the Celery task. Without this, _consolidate_and_send_to_ashwin
            # re-reads the old section_html from programme_lead_feedback and any chat-driven
            # edits are silently lost.
            edition_result = await db.execute(
                select(NewsletterEdition).where(NewsletterEdition.id == pt.edition_id)
            )
            edition_obj = edition_result.scalars().first()
            if edition_obj:
                existing_meta = json.loads(edition_obj.programme_lead_feedback or "{}")
                lead_entry = existing_meta.get(pt.actor_email.lower(), {})
                lead_entry["section_html"] = body.final_content
                existing_meta[pt.actor_email.lower()] = lead_entry
                edition_obj.programme_lead_feedback = json.dumps(existing_meta)

        from digital_employee.tasks.workflow_tasks import handle_programme_lead_reply
        pt.is_used = True
        await db.commit()  # commit BEFORE dispatch so worker reads fresh section_html
        handle_programme_lead_reply.delay(
            intent="newsletter_approval",
            body_text=body.final_content,
            subject=f"Re: {edition_title}",
            sender_email=pt.actor_email,
            sender_name=pt.actor_name,
        )

    elif pt.role == "ashwin":
        if pt.edition_id and body.final_content:
            # Save Ashwin's edited content BEFORE dispatching.
            # _send_to_anuj reads edition.html_content (content body, no template wrapper).
            # Robustly extract content body — handles both content-only and full-document HTML.
            content_to_save = _extract_content_body(body.final_content)
            edition_result = await db.execute(
                select(NewsletterEdition).where(NewsletterEdition.id == pt.edition_id)
            )
            edition_obj = edition_result.scalars().first()
            if edition_obj and content_to_save:
                edition_obj.html_content = content_to_save

        from digital_employee.tasks.workflow_tasks import handle_ashwin_reply
        pt.is_used = True
        await db.commit()  # commit BEFORE dispatch so worker reads fresh html_content
        handle_ashwin_reply.delay(
            intent="newsletter_approval",
            body_text=body.final_content,
            subject=f"Re: {edition_title}",
        )

    elif pt.role == "anuj":
        if pt.edition_id and body.final_content:
            # Save Anuj's edited content BEFORE dispatching.
            # Robustly extract content body — handles both content-only and full-document HTML.
            content_to_save = _extract_content_body(body.final_content)
            edition_result = await db.execute(
                select(NewsletterEdition).where(NewsletterEdition.id == pt.edition_id)
            )
            edition_obj = edition_result.scalars().first()
            if edition_obj and content_to_save:
                edition_obj.html_content = content_to_save

        from digital_employee.tasks.workflow_tasks import handle_anuj_reply
        pt.is_used = True
        await db.commit()   # commit BEFORE dispatch so worker reads fresh html_content
        handle_anuj_reply.delay(
            intent="anuj_approval",
            body_text=body.final_content,
            subject=f"Re: {edition_title}",
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown role: {pt.role}")

    logger.info("portal_approved", role=pt.role, actor=pt.actor_email)
    return {"status": "approved", "message": "Thank you! Your approval has been recorded."}


@router.post("/feedback")
async def portal_feedback(body: FeedbackRequest, db: AsyncSession = Depends(get_db)):
    """Submit feedback/revision request via the portal."""
    pt = await validate_token_async(db, body.token)
    if not pt:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired token.")

    ctx = json.loads(pt.context_json)
    edition_title = ctx.get("edition_title", "Newsletter")
    pt.is_used = True

    if pt.role == "programme_lead":
        from digital_employee.tasks.workflow_tasks import handle_programme_lead_reply
        handle_programme_lead_reply.delay(
            intent="newsletter_changes",
            body_text=body.feedback_text,
            subject=f"Re: {edition_title}",
            sender_email=pt.actor_email,
            sender_name=pt.actor_name,
        )

    elif pt.role == "ashwin":
        from digital_employee.tasks.workflow_tasks import handle_ashwin_reply
        handle_ashwin_reply.delay(
            intent="newsletter_changes",
            body_text=body.feedback_text,
            subject=f"Re: {edition_title}",
        )

    elif pt.role == "anuj":
        from digital_employee.tasks.workflow_tasks import handle_anuj_reply
        handle_anuj_reply.delay(
            intent="anuj_feedback",
            body_text=body.feedback_text,
            subject=f"Re: {edition_title}",
        )

    await db.commit()
    logger.info("portal_feedback_submitted", role=pt.role, actor=pt.actor_email)
    return {"status": "feedback_received", "message": "Your feedback has been submitted. The AI will incorporate it shortly."}
