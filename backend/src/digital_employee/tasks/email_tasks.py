"""Background email tasks — LLM-powered inbox polling and reminders."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from digital_employee.settings import Settings
from digital_employee.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _get_sync_session():
    """Create a synchronous DB session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    settings = Settings()
    engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _run_async(coro):
    """Run an async coroutine from sync Celery context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _build_workflow_context(session) -> str:
    """Build a comprehensive workflow context string for the LLM.

    This gives the LLM full awareness of the current state so it can
    classify emails and generate contextual responses.
    """
    lines = []

    # Active editions
    active_editions = session.execute(
        select(NewsletterEdition).where(
            NewsletterEdition.status.notin_([
                EditionStatus.COMPLETED,
                EditionStatus.FAILED,
            ])
        ).order_by(NewsletterEdition.updated_at.desc())
    ).scalars().all()

    if not active_editions:
        lines.append("No active newsletter cycles at the moment.")
    else:
        for edition in active_editions:
            lines.append(f"Active Newsletter: \"{edition.title}\" — Status: {edition.status.value}")
            subs = session.execute(
                select(LeadSubmission).where(LeadSubmission.edition_id == edition.id)
            ).scalars().all()
            for sub in subs:
                lines.append(
                    f"  - {sub.lead_name} ({sub.lead_email}): "
                    f"Programme={sub.programme}, Workstream={sub.workstream}, "
                    f"Status={sub.status.value}"
                )

    # Load teams config for lead awareness
    import yaml, os
    teams_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "config", "teams.yaml")
    if os.path.exists(teams_path):
        with open(teams_path) as f:
            teams = yaml.safe_load(f)
        lines.append("\nKnown team structure:")
        for prog in teams.get("programmes", []):
            for ws in prog.get("workstreams", []):
                lines.append(f"  - {prog['name']} / {ws['name']}: Lead = {ws['lead_name']} ({ws['lead_email']})")

    return "\n".join(lines)


def _get_programme_lead_emails() -> set[str]:
    """Return a set of all programme lead emails from teams.yaml."""
    import yaml, os
    # __file__ is backend/src/digital_employee/tasks/email_tasks.py
    # teams.yaml is in backend/config/teams.yaml
    teams_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "teams.yaml"))
    prog_leads = set()
    if os.path.exists(teams_path):
        with open(teams_path) as f:
            teams = yaml.safe_load(f)
        for prog in teams.get("programmes", []):
            email = prog.get("programme_lead_email")
            if email:
                prog_leads.add(email.lower())
    return prog_leads


@celery_app.task(name="digital_employee.tasks.email_tasks.poll_inbox")
def poll_inbox() -> dict:
    """DEPRECATED: Inbox polling removed — inbound email is now handled by the web portal.
    This task is retained as a no-op to avoid beat schedule errors.
    """
    logger.info("poll_inbox_disabled", reason="Replaced by web portal magic-link workflow")
    return {"status": "disabled", "reason": "Web portal workflow is active"}

    session = _get_sync_session()
    llm_svc = LLMService(settings)
    workflow_context = _build_workflow_context(session)

    processed = 0
    for email_msg in emails:
        try:
            # Skip emails from ourselves (avoid loops)
            if email_msg.from_addr.lower() == settings.email_address.lower():
                email_svc.mark_as_read(email_msg.uid)
                continue

            body = email_msg.body_text or email_msg.body_html or ""

            # ── LLM Classification ─────────────────────────────────────
            classification = _run_async(llm_svc.classify_email(
                sender_email=email_msg.from_addr,
                sender_name=email_msg.from_name,
                subject=email_msg.subject,
                body=body,
                workflow_context=workflow_context,
            ))

            intent = classification.get("intent", "general_question")
            extracted = classification.get("extracted_content") or body

            logger.info(
                "email_classified",
                sender=email_msg.from_addr,
                intent=intent,
                subject=email_msg.subject[:60],
                body_len=len(body),
                extracted_len=len(extracted) if extracted else 0,
                extracted_preview=(extracted or "")[:150],
            )

            # ── Route based on LLM intent ──────────────────────────────
            from digital_employee.tasks.workflow_tasks import (
                handle_anuj_reply,
                handle_ashwin_reply,
                handle_lead_reply,
                handle_programme_lead_reply,
                handle_general_email,
            )

            sender = email_msg.from_addr.lower()
            programme_lead_emails = _get_programme_lead_emails()

            if intent in ("newsletter_content", "newsletter_approval", "newsletter_changes"):
                # Determine who is sending this — programme lead, Ashwin, Anuj, or workstream lead
                if sender == settings.anuj_email.lower():
                    # Anuj sending newsletter-related reply — treat as anuj_approval/feedback
                    anuj_intent = "anuj_approval" if intent == "newsletter_approval" else "anuj_feedback"
                    handle_anuj_reply.delay(
                        intent=anuj_intent,
                        body_text=extracted,
                        subject=email_msg.subject,
                    )
                elif settings.ashwin_email and sender == settings.ashwin_email.lower():
                    ashwin_intent = "newsletter_approval" if intent == "newsletter_approval" else "newsletter_feedback"
                    handle_ashwin_reply.delay(
                        intent=ashwin_intent,
                        body_text=extracted,
                        subject=email_msg.subject,
                    )
                elif sender in programme_lead_emails:
                    handle_programme_lead_reply.delay(
                        sender_email=email_msg.from_addr,
                        sender_name=email_msg.from_name,
                        intent=intent,
                        body_text=extracted,
                        subject=email_msg.subject,
                    )
                else:
                    handle_lead_reply.delay(
                        sender_email=email_msg.from_addr,
                        sender_name=email_msg.from_name,
                        intent=intent,
                        body_text=extracted,
                        subject=email_msg.subject,
                    )
            elif intent in ("anuj_approval", "anuj_feedback"):
                handle_anuj_reply.delay(
                    intent=intent,
                    body_text=extracted,
                    subject=email_msg.subject,
                )
            elif intent == "spam_ignore":
                logger.info("spam_ignored", sender=email_msg.from_addr)
            else:
                # newsletter_question, out_of_scope, or anything else
                handle_general_email.delay(
                    sender_email=email_msg.from_addr,
                    sender_name=email_msg.from_name,
                    subject=email_msg.subject,
                    body_text=body,
                )

            email_svc.mark_as_read(email_msg.uid)
            processed += 1

        except Exception as exc:
            logger.error("email_processing_error", uid=email_msg.uid, error=str(exc))

    email_svc.disconnect_imap()
    session.close()

    logger.info("inbox_polled", processed=processed, total=len(emails))
    return {"processed": processed, "total": len(emails)}


@celery_app.task(name="digital_employee.tasks.email_tasks.check_and_send_reminders")
def check_and_send_reminders() -> dict:
    """Check for non-responsive leads and send reminders.

    After max_reminders are sent without a response, the lead's submission
    is marked SKIPPED and the newsletter proceeds without them.
    """
    settings = Settings()
    email_svc = EmailService(settings)
    session = _get_sync_session()

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.reminder_after_days)

    # ── Step 1: Send reminders to leads who still have attempts left ──────
    pending_subs = session.execute(
        select(LeadSubmission)
        .join(NewsletterEdition)
        .where(
            LeadSubmission.status == SubmissionStatus.PENDING,
            LeadSubmission.created_at < cutoff,
            LeadSubmission.reminder_count < settings.max_reminders,
            NewsletterEdition.status.in_([
                EditionStatus.COLLECTING,
                EditionStatus.INITIATED,
            ]),
        )
    ).scalars().all()

    sent = 0
    for sub in pending_subs:
        try:
            edition = sub.edition
            edition_title = edition.title if edition else "Newsletter"

            # Generate a fresh portal token for this reminder
            from digital_employee.services.token_service import create_token_sync, build_portal_url
            portal_url = build_portal_url(
                settings,
                create_token_sync(
                    session,
                    role="lead",
                    action_type="submit",
                    actor_email=sub.lead_email,
                    actor_name=sub.lead_name,
                    edition_id=sub.edition_id,
                    submission_id=sub.id,
                    context={
                        "programme": sub.programme,
                        "workstream": sub.workstream,
                        "edition_title": edition_title,
                    },
                    settings=settings,
                ),
                page="submit",
            )
            session.flush()

            email_svc.send_reminder(
                lead_email=sub.lead_email,
                lead_name=sub.lead_name,
                programme=sub.programme,
                workstream=sub.workstream,
                edition_title=edition_title,
                reminder_number=sub.reminder_count + 1,
                portal_url=portal_url,
            )
            sub.reminder_count += 1
            sub.last_reminder_at = datetime.now(timezone.utc)

            session.add(AuditLog(
                edition_id=sub.edition_id,
                action=AuditAction.REMINDER_SENT,
                actor="system",
                detail=f"Reminder #{sub.reminder_count} sent to {sub.lead_email} with fresh portal link",
            ))
            sent += 1
        except Exception as exc:
            logger.error("reminder_failed", lead=sub.lead_email, error=str(exc))

    # ── Step 2: Skip leads who exhausted all reminders ────────────────────
    exhausted_subs = session.execute(
        select(LeadSubmission)
        .join(NewsletterEdition)
        .where(
            LeadSubmission.status == SubmissionStatus.PENDING,
            LeadSubmission.reminder_count >= settings.max_reminders,
            NewsletterEdition.status.in_([
                EditionStatus.COLLECTING,
                EditionStatus.INITIATED,
            ]),
        )
    ).scalars().all()

    skipped = 0
    # Group by edition to send one skip notification per edition
    editions_to_check: dict = {}  # edition_id -> edition obj
    for sub in exhausted_subs:
        sub.status = SubmissionStatus.SKIPPED
        session.add(AuditLog(
            edition_id=sub.edition_id,
            action=AuditAction.LEAD_SKIPPED,
            actor="system",
            detail=f"{sub.lead_name} ({sub.lead_email}) skipped after {sub.reminder_count} reminders — {sub.programme}/{sub.workstream}",
        ))
        skipped += 1
        editions_to_check[sub.edition_id] = sub.edition

    # Send skip notification for each affected edition
    for edition_id, edition in editions_to_check.items():
        if not edition:
            continue
        all_subs = session.execute(
            select(LeadSubmission).where(LeadSubmission.edition_id == edition_id)
        ).scalars().all()

        skipped_leads_data = [
            {
                "lead_name": s.lead_name,
                "lead_email": s.lead_email,
                "programme": s.programme,
                "workstream": s.workstream,
                "reminder_count": s.reminder_count,
            }
            for s in all_subs if s.status == SubmissionStatus.SKIPPED
        ]
        all_lead_emails = [s.lead_email for s in all_subs]

        try:
            email_svc.send_skip_notification(
                reviewer_email=settings.anuj_email,
                reviewer_name=settings.anuj_name,
                edition_title=edition.title,
                skipped_leads=skipped_leads_data,
                all_lead_emails=all_lead_emails,
            )
            logger.info("skip_notification_sent", edition=edition.title, skipped=len(skipped_leads_data))
        except Exception as exc:
            logger.error("skip_notification_failed", error=str(exc))

        # Trigger consolidation check — skipped + approved = proceed
        from digital_employee.tasks.workflow_tasks import _check_and_route_after_lead_approvals
        _check_and_route_after_lead_approvals(session, edition, settings)

    session.commit()
    session.close()

    logger.info("reminders_checked", sent=sent, skipped=skipped)
    return {"sent": sent, "skipped": skipped}


# ── Reviewer Reminders (Programme Lead / Ashwin / Anuj) ──────────────────────

def _count_reviewer_reminders(session, edition_id: int, actor_email: str) -> int:
    """Count REMINDER_SENT AuditLog entries for a specific reviewer+edition."""
    from sqlalchemy import func
    result = session.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.edition_id == edition_id,
            AuditLog.action == AuditAction.REMINDER_SENT,
            AuditLog.detail.like(f"%{actor_email}%"),
        )
    ).scalar()
    return result or 0


def _days_since_utc(dt: datetime) -> int:
    """Return how many full days have elapsed since dt (UTC-aware)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days


@celery_app.task(name="digital_employee.tasks.email_tasks.send_reviewer_reminders")
def send_reviewer_reminders() -> dict:
    """Send up to 3 daily reminder emails to programme leads, Ashwin, and Anuj
    for the most recent active newsletter cycle only.

    Schedule: Reminder 1 on day 1, Reminder 2 on day 2, Reminder 3 on day 3.
    Once 3 reminders are sent the reviewer is no longer chased.
    """
    settings = Settings()
    email_svc = EmailService(settings)
    session = _get_sync_session()
    sent = 0
    MAX_REMINDERS = 3

    try:
        from digital_employee.services.token_service import create_token_sync, build_portal_url

        def _maybe_send(edition, reviewer_email, reviewer_name, role, role_label, page):
            nonlocal sent
            days = _days_since_utc(edition.updated_at)
            reminders_sent = _count_reviewer_reminders(session, edition.id, reviewer_email)
            # Send next reminder if we haven't caught up with days elapsed (max 3)
            if reminders_sent >= MAX_REMINDERS or reminders_sent >= days:
                return
            reminder_number = reminders_sent + 1
            token = create_token_sync(
                session,
                role=role,
                action_type="review",
                actor_email=reviewer_email,
                actor_name=reviewer_name,
                edition_id=edition.id,
                context={"edition_title": edition.title},
                settings=settings,
            )
            portal_url = build_portal_url(settings, token, page=page)
            session.flush()
            email_svc.send_reviewer_reminder(
                reviewer_email=reviewer_email,
                reviewer_name=reviewer_name,
                role_label=role_label,
                edition_title=edition.title,
                reminder_number=reminder_number,
                portal_url=portal_url,
            )
            session.add(AuditLog(
                edition_id=edition.id,
                action=AuditAction.REMINDER_SENT,
                actor="system",
                detail=f"Reminder #{reminder_number} sent to {reviewer_email} ({role_label})",
            ))
            sent += 1
            logger.info("reviewer_reminder_sent", role=role, email=reviewer_email,
                        reminder=reminder_number, edition=edition.title)

        # ── Programme leads: check pending entries in programme_lead_feedback ─
        import json as _json, yaml as _yaml, os as _os
        teams_path = _os.path.abspath(_os.path.join(
            _os.path.dirname(__file__), "..", "..", "..", "config", "teams.yaml"
        ))
        prog_lead_map: dict[str, str] = {}  # email → name
        if _os.path.exists(teams_path):
            with open(teams_path) as f:
                teams_data = _yaml.safe_load(f)
            for prog in teams_data.get("programmes", []):
                email = (prog.get("programme_lead_email") or "").lower()
                name = prog.get("programme_lead_name") or email
                if email:
                    prog_lead_map[email] = name

        pl_edition = session.execute(
            select(NewsletterEdition)
            .where(NewsletterEdition.status == EditionStatus.AWAITING_PROGRAMME_LEAD_APPROVAL)
            .order_by(NewsletterEdition.updated_at.desc())
            .limit(1)
        ).scalars().first()
        if pl_edition:
            meta = _json.loads(pl_edition.programme_lead_feedback or "{}")
            for email_key, entry in meta.items():
                if entry.get("status") == "pending" and email_key in prog_lead_map:
                    _maybe_send(pl_edition, email_key, prog_lead_map[email_key],
                                "programme_lead", "Programme Lead", "review")

        # ── Ashwin ────────────────────────────────────────────────────────────
        ashwin_ed = session.execute(
            select(NewsletterEdition)
            .where(NewsletterEdition.status == EditionStatus.AWAITING_ASHWIN_APPROVAL)
            .order_by(NewsletterEdition.updated_at.desc())
            .limit(1)
        ).scalars().first()
        if ashwin_ed:
            _maybe_send(ashwin_ed, settings.ashwin_email, settings.ashwin_name,
                        "ashwin", "Senior Reviewer", "review")

        # ── Anuj ──────────────────────────────────────────────────────────────
        anuj_ed = session.execute(
            select(NewsletterEdition)
            .where(NewsletterEdition.status == EditionStatus.AWAITING_ANUJ_APPROVAL)
            .order_by(NewsletterEdition.updated_at.desc())
            .limit(1)
        ).scalars().first()
        if anuj_ed:
            _maybe_send(anuj_ed, settings.anuj_email, settings.anuj_name,
                        "anuj", "Delivery Leader", "review")

        session.commit()
    except Exception as exc:
        logger.error("reviewer_reminders_error", error=str(exc))
        session.rollback()
    finally:
        session.close()

    logger.info("reviewer_reminders_done", sent=sent)
    return {"sent": sent}
