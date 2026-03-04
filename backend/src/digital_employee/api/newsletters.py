"""Newsletter API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from digital_employee.database import get_db
from digital_employee.models import (
    AuditAction,
    AuditLog,
    EditionStatus,
    LeadSubmission,
    NewsletterEdition,
    SubmissionStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/newsletters", tags=["newsletters"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class NewsletterSummary(BaseModel):
    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    attempt_count: int
    submission_count: int = 0
    approved_count: int = 0

    class Config:
        from_attributes = True


class SubmissionDetail(BaseModel):
    id: str
    lead_email: str
    lead_name: str
    programme: str
    workstream: str
    status: str
    raw_content: Optional[str] = None
    reworded_content: Optional[str] = None
    reminder_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class NewsletterDetail(BaseModel):
    id: str
    title: str
    status: str
    html_content: Optional[str] = None
    anuj_feedback: Optional[str] = None
    attempt_count: int
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    submissions: list[SubmissionDetail] = []

    class Config:
        from_attributes = True


class TriggerRequest(BaseModel):
    title: str = ""


class TriggerResponse(BaseModel):
    edition_id: str
    message: str


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[NewsletterSummary])
async def list_newsletters(
    status: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all newsletter editions with pagination."""
    stmt = select(NewsletterEdition).order_by(NewsletterEdition.created_at.desc())
    if status:
        stmt = stmt.where(NewsletterEdition.status == status)
    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)
    editions = result.scalars().all()

    # Get submission counts
    summaries = []
    for ed in editions:
        sub_result = await db.execute(
            select(func.count()).where(LeadSubmission.edition_id == ed.id)
        )
        total_subs = sub_result.scalar() or 0

        approved_result = await db.execute(
            select(func.count()).where(
                LeadSubmission.edition_id == ed.id,
                LeadSubmission.status == SubmissionStatus.APPROVED,
            )
        )
        approved_subs = approved_result.scalar() or 0

        summaries.append(
            NewsletterSummary(
                id=str(ed.id),
                title=ed.title,
                status=ed.status.value,
                created_at=ed.created_at,
                updated_at=ed.updated_at,
                sent_at=ed.sent_at,
                attempt_count=ed.attempt_count,
                submission_count=total_subs,
                approved_count=approved_subs,
            )
        )

    return summaries


@router.get("/{edition_id}", response_model=NewsletterDetail)
async def get_newsletter(
    edition_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a newsletter edition with all submissions."""
    uid = uuid.UUID(edition_id)
    result = await db.execute(
        select(NewsletterEdition).where(NewsletterEdition.id == uid)
    )
    edition = result.scalars().first()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")

    subs_result = await db.execute(
        select(LeadSubmission).where(LeadSubmission.edition_id == uid)
    )
    submissions = subs_result.scalars().all()

    return NewsletterDetail(
        id=str(edition.id),
        title=edition.title,
        status=edition.status.value,
        html_content=edition.html_content,
        anuj_feedback=edition.anuj_feedback,
        attempt_count=edition.attempt_count,
        created_at=edition.created_at,
        updated_at=edition.updated_at,
        sent_at=edition.sent_at,
        submissions=[
            SubmissionDetail(
                id=str(s.id),
                lead_email=s.lead_email,
                lead_name=s.lead_name,
                programme=s.programme,
                workstream=s.workstream,
                status=s.status.value,
                raw_content=s.raw_content,
                reworded_content=s.reworded_content,
                reminder_count=s.reminder_count,
                created_at=s.created_at,
            )
            for s in submissions
        ],
    )


@router.get("/{edition_id}/preview")
async def preview_newsletter(
    edition_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the rendered HTML preview of a newsletter."""
    uid = uuid.UUID(edition_id)
    result = await db.execute(
        select(NewsletterEdition).where(NewsletterEdition.id == uid)
    )
    edition = result.scalars().first()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")

    from fastapi.responses import HTMLResponse

    return HTMLResponse(content=edition.html_content or "<p>No content yet</p>")


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_newsletter(
    body: TriggerRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually start a new newsletter cycle."""
    title = body.title or f"Monthly Newsletter — {datetime.now().strftime('%B %Y')}"

    # Create the edition record
    edition = NewsletterEdition(title=title, status=EditionStatus.INITIATED)
    db.add(edition)
    await db.flush()

    # Load team config and create submissions
    try:
        with open("config/teams.yaml") as f:
            teams_config = yaml.safe_load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="teams.yaml not found")

    for programme in teams_config.get("programmes", []):
        for ws in programme.get("workstreams", []):
            sub = LeadSubmission(
                edition_id=edition.id,
                lead_email=ws["lead_email"],
                lead_name=ws["lead_name"],
                programme=programme["name"],
                workstream=ws["name"],
                status=SubmissionStatus.PENDING,
            )
            db.add(sub)

    # Audit log
    db.add(AuditLog(
        edition_id=edition.id,
        action=AuditAction.CYCLE_STARTED,
        actor="admin",
        detail=f"Newsletter cycle '{title}' started",
    ))

    await db.flush()

    # Fire off portal links to all leads
    from digital_employee.services.email_service import EmailService
    from digital_employee.services.token_service import create_token_async, build_portal_url
    from digital_employee.settings import get_settings

    settings = get_settings()
    email_svc = EmailService(settings)

    subs_result = await db.execute(
        select(LeadSubmission).where(LeadSubmission.edition_id == edition.id)
    )
    for sub in subs_result.scalars().all():
        # Generate a unique, time-limited portal token for each lead
        token_str = await create_token_async(
            db,
            role="lead",
            action_type="submit",
            actor_email=sub.lead_email,
            actor_name=sub.lead_name,
            edition_id=edition.id,
            submission_id=sub.id,
            context={
                "programme": sub.programme,
                "workstream": sub.workstream,
                "edition_title": title,
            },
            settings=settings,
        )
        portal_url = build_portal_url(settings, token_str, page="submit")

        email_svc.send_update_request(
            lead_email=sub.lead_email,
            lead_name=sub.lead_name,
            programme=sub.programme,
            workstream=sub.workstream,
            edition_title=title,
            portal_url=portal_url,
        )
        sub.status = SubmissionStatus.PENDING
        db.add(AuditLog(
            edition_id=edition.id,
            action=AuditAction.REQUEST_SENT,
            actor="system",
            detail=f"Portal link sent to {sub.lead_name} ({sub.lead_email})",
        ))

    edition.status = EditionStatus.COLLECTING
    await db.flush()

    logger.info("newsletter_triggered", edition_id=str(edition.id), title=title)
    return TriggerResponse(
        edition_id=str(edition.id),
        message=f"Newsletter cycle '{title}' started successfully",
    )
