"""Dashboard API endpoints — metrics and activity feed."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from digital_employee.database import get_db
from digital_employee.models import (
    AuditLog,
    EditionStatus,
    LeadSubmission,
    NewsletterEdition,
    SubmissionStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class DashboardMetrics(BaseModel):
    total_editions: int
    active_cycles: int
    completed_editions: int
    pending_responses: int
    total_leads: int
    avg_turnaround_days: Optional[float] = None


class ActivityItem(BaseModel):
    id: str
    edition_id: Optional[str] = None
    edition_title: Optional[str] = None
    action: str
    actor: str
    detail: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/metrics", response_model=DashboardMetrics)
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """Get dashboard summary metrics."""
    # Total editions
    total = await db.execute(select(func.count(NewsletterEdition.id)))
    total_editions = total.scalar() or 0

    # Active (not completed/failed/sent)
    active = await db.execute(
        select(func.count(NewsletterEdition.id)).where(
            NewsletterEdition.status.notin_([
                EditionStatus.COMPLETED,
                EditionStatus.FAILED,
                EditionStatus.SENT_TO_CLIENT,
            ])
        )
    )
    active_cycles = active.scalar() or 0

    # Completed
    completed = await db.execute(
        select(func.count(NewsletterEdition.id)).where(
            NewsletterEdition.status == EditionStatus.COMPLETED
        )
    )
    completed_editions = completed.scalar() or 0

    # Pending
    pending = await db.execute(
        select(func.count(LeadSubmission.id)).where(
            LeadSubmission.status == SubmissionStatus.PENDING
        )
    )
    pending_responses = pending.scalar() or 0

    # Total unique leads
    leads = await db.execute(
        select(func.count(func.distinct(LeadSubmission.lead_email)))
    )
    total_leads = leads.scalar() or 0

    # Avg turnaround (completed editions only)
    avg_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", NewsletterEdition.sent_at)
                - func.extract("epoch", NewsletterEdition.created_at)
            )
        ).where(
            NewsletterEdition.status == EditionStatus.COMPLETED,
            NewsletterEdition.sent_at.isnot(None),
        )
    )
    avg_seconds = avg_result.scalar()
    avg_days = round(avg_seconds / 86400, 1) if avg_seconds else None

    return DashboardMetrics(
        total_editions=total_editions,
        active_cycles=active_cycles,
        completed_editions=completed_editions,
        pending_responses=pending_responses,
        total_leads=total_leads,
        avg_turnaround_days=avg_days,
    )


@router.get("/activity", response_model=list[ActivityItem])
async def get_activity(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    edition_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get recent activity feed / audit log."""
    stmt = (
        select(AuditLog)
        .outerjoin(NewsletterEdition, AuditLog.edition_id == NewsletterEdition.id)
        .order_by(AuditLog.timestamp.desc())
    )

    if edition_id:
        import uuid as uuid_mod
        stmt = stmt.where(AuditLog.edition_id == uuid_mod.UUID(edition_id))

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    items = []
    for log in logs:
        # Fetch edition title if available
        edition_title = None
        if log.edition_id:
            ed_result = await db.execute(
                select(NewsletterEdition.title).where(
                    NewsletterEdition.id == log.edition_id
                )
            )
            edition_title = ed_result.scalar()

        items.append(
            ActivityItem(
                id=str(log.id),
                edition_id=str(log.edition_id) if log.edition_id else None,
                edition_title=edition_title,
                action=log.action.value,
                actor=log.actor,
                detail=log.detail,
                timestamp=log.timestamp,
            )
        )

    return items
