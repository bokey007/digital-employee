"""Portal token service — create, validate, and expire magic-link tokens."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from digital_employee.models import PortalToken
from digital_employee.settings import Settings

if TYPE_CHECKING:
    import uuid
    from sqlalchemy.orm import Session
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_TOKEN_BYTES = 48  # → 64-char urlsafe base64 string


# ── Sync helpers (used from Celery tasks) ────────────────────────────────────


def create_token_sync(
    db: "Session",
    *,
    role: str,
    action_type: str,
    actor_email: str,
    actor_name: str,
    edition_id: "uuid.UUID | None" = None,
    submission_id: "uuid.UUID | None" = None,
    context: dict | None = None,
    settings: Settings | None = None,
) -> str:
    """Create a PortalToken and return the raw token string (sync version for Celery)."""
    settings = settings or Settings()
    ttl = timedelta(days=settings.portal_token_ttl_days)
    raw = secrets.token_urlsafe(_TOKEN_BYTES)

    pt = PortalToken(
        token=raw,
        role=role,
        action_type=action_type,
        actor_email=actor_email,
        actor_name=actor_name,
        edition_id=edition_id,
        submission_id=submission_id,
        context_json=json.dumps(context or {}),
        expires_at=datetime.now(timezone.utc) + ttl,
        is_used=False,
    )
    db.add(pt)
    db.flush()
    logger.info("portal_token_created", role=role, action=action_type, actor=actor_email)
    return raw


def validate_token_sync(db: "Session", token_str: str) -> PortalToken | None:
    """Validate a portal token (sync). Returns None if invalid/expired/used."""
    pt = db.execute(
        select(PortalToken).where(PortalToken.token == token_str)
    ).scalars().first()

    if not pt:
        logger.warning("portal_token_not_found")
        return None
    if pt.expires_at < datetime.now(timezone.utc):
        logger.warning("portal_token_expired", actor=pt.actor_email)
        return None
    if pt.is_used:
        logger.warning("portal_token_already_used", actor=pt.actor_email)
        return None
    return pt


# ── Async helpers (used from FastAPI endpoints) ──────────────────────────────


async def create_token_async(
    db: "AsyncSession",
    *,
    role: str,
    action_type: str,
    actor_email: str,
    actor_name: str,
    edition_id: "uuid.UUID | None" = None,
    submission_id: "uuid.UUID | None" = None,
    context: dict | None = None,
    settings: Settings | None = None,
) -> str:
    """Create a PortalToken and return the raw token string (async version for FastAPI)."""
    settings = settings or Settings()
    ttl = timedelta(days=settings.portal_token_ttl_days)
    raw = secrets.token_urlsafe(_TOKEN_BYTES)

    pt = PortalToken(
        token=raw,
        role=role,
        action_type=action_type,
        actor_email=actor_email,
        actor_name=actor_name,
        edition_id=edition_id,
        submission_id=submission_id,
        context_json=json.dumps(context or {}),
        expires_at=datetime.now(timezone.utc) + ttl,
        is_used=False,
    )
    db.add(pt)
    await db.flush()
    logger.info("portal_token_created_async", role=role, action=action_type, actor=actor_email)
    return raw


async def validate_token_async(db: "AsyncSession", token_str: str) -> PortalToken | None:
    """Validate a portal token (async). Returns None if invalid/expired/used.

    Use this for write operations (submit, approve, feedback) that must be
    rejected once the token has been consumed.
    """
    result = await db.execute(
        select(PortalToken).where(PortalToken.token == token_str)
    )
    pt = result.scalars().first()

    if not pt:
        logger.warning("portal_token_not_found")
        return None
    if pt.expires_at < datetime.now(timezone.utc):
        logger.warning("portal_token_expired", actor=pt.actor_email)
        return None
    if pt.is_used:
        logger.warning("portal_token_already_used", actor=pt.actor_email)
        return None
    return pt


async def lookup_token_async(db: "AsyncSession", token_str: str) -> PortalToken | None:
    """Read-only token lookup — checks expiry but NOT is_used.

    Used by GET /portal/token/{token} (page load) so leads can always
    reload their portal link to view/refine content, even after approving.
    The link only becomes truly inaccessible once it expires (14 days).
    """
    result = await db.execute(
        select(PortalToken).where(PortalToken.token == token_str)
    )
    pt = result.scalars().first()

    if not pt:
        logger.warning("portal_token_not_found")
        return None
    if pt.expires_at < datetime.now(timezone.utc):
        logger.warning("portal_token_expired", actor=pt.actor_email)
        return None
    logger.info("portal_token_lookup", actor=pt.actor_email, is_used=pt.is_used)
    return pt


# ── URL builder ──────────────────────────────────────────────────────────────


def build_portal_url(settings: Settings, token_str: str, page: str = "submit") -> str:
    """Build the full portal URL for embedding in emails."""
    base = settings.portal_base_url.rstrip("/")
    return f"{base}/portal/{page}?token={token_str}"
