"""Lead management API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog
import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from digital_employee.database import get_db
from digital_employee.models import LeadSubmission, SubmissionStatus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/leads", tags=["leads"])

TEAMS_CONFIG_PATH = "config/teams.yaml"


# ── Schemas ──────────────────────────────────────────────────────────────────


class LeadInfo(BaseModel):
    lead_name: str
    lead_email: str
    programme: str
    workstream: str


class ProgrammeInfo(BaseModel):
    name: str
    workstreams: list[dict]


class LeadStats(BaseModel):
    lead_email: str
    lead_name: str
    programme: str
    workstream: str
    total_submissions: int
    approved_count: int
    avg_response_hours: Optional[float] = None


class TeamsConfig(BaseModel):
    programmes: list[dict]


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/config", response_model=TeamsConfig)
async def get_teams_config():
    """Get the current team/lead configuration."""
    try:
        with open(TEAMS_CONFIG_PATH) as f:
            data = yaml.safe_load(f)
        return TeamsConfig(programmes=data.get("programmes", []))
    except FileNotFoundError:
        return TeamsConfig(programmes=[])


@router.put("/config")
async def update_teams_config(config: TeamsConfig):
    """Update the team/lead configuration."""
    with open(TEAMS_CONFIG_PATH, "w") as f:
        yaml.dump({"programmes": config.programmes}, f, default_flow_style=False)
    return {"message": "Configuration updated successfully"}


@router.get("/stats", response_model=list[LeadStats])
async def get_lead_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for all leads across editions."""
    # Get distinct leads
    result = await db.execute(
        select(
            LeadSubmission.lead_email,
            LeadSubmission.lead_name,
            LeadSubmission.programme,
            LeadSubmission.workstream,
            func.count(LeadSubmission.id).label("total"),
            func.count(
                func.nullif(LeadSubmission.status != SubmissionStatus.APPROVED, True)
            ).label("approved"),
        )
        .group_by(
            LeadSubmission.lead_email,
            LeadSubmission.lead_name,
            LeadSubmission.programme,
            LeadSubmission.workstream,
        )
    )
    rows = result.all()

    return [
        LeadStats(
            lead_email=row.lead_email,
            lead_name=row.lead_name,
            programme=row.programme,
            workstream=row.workstream,
            total_submissions=row.total,
            approved_count=row.approved,
        )
        for row in rows
    ]
