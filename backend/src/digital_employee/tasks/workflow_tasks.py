"""Background workflow tasks — LLM-driven email handling and newsletter orchestration."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from digital_employee.models import (
    AuditAction,
    AuditLog,
    EditionStatus,
    EmailConversation,
    LeadSubmission,
    NewsletterEdition,
    SubmissionStatus,
)
from digital_employee.services.llm_service import LLMService
from digital_employee.services.rag_service import RAGService
from digital_employee.settings import Settings
from digital_employee.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _get_sync_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    settings = Settings()
    engine = create_engine(settings.database_url_sync)
    return sessionmaker(bind=engine)()


def _run_async(coro):
    """Run an async coroutine from sync Celery context."""
    import asyncio
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
    """Build workflow context string for LLM."""
    from digital_employee.tasks.email_tasks import _build_workflow_context
    return _build_workflow_context(session)


# ─────────────────────────────────────────────────────────────────────────────
# Newsletter Workflow Handlers
# ─────────────────────────────────────────────────────────────────────────────


@celery_app.task(name="digital_employee.tasks.workflow_tasks.handle_lead_reply")
def handle_lead_reply(
    sender_email: str,
    sender_name: str,
    intent: str,
    body_text: str,
    subject: str,
) -> dict:
    """Process a newsletter-related reply from a sub-workstream lead.

    The LLM has already classified the intent — we trust it.
    """
    session = _get_sync_session()
    settings = Settings()

    try:
        # Find the active submission for this lead
        sub = session.execute(
            select(LeadSubmission)
            .join(NewsletterEdition)
            .where(
                LeadSubmission.lead_email == sender_email,
                NewsletterEdition.status.notin_([
                    EditionStatus.COMPLETED,
                    EditionStatus.FAILED,
                    EditionStatus.SENT_TO_CLIENT,
                ]),
            )
            .order_by(LeadSubmission.created_at.desc())
        ).scalars().first()

        if not sub:
            # Lead not in active cycle — treat as general email
            logger.info("lead_not_in_cycle, routing_to_general", sender=sender_email)
            handle_general_email.delay(
                sender_email=sender_email,
                sender_name=sender_name,
                subject=subject,
                body_text=body_text,
            )
            return {"status": "routed_to_general", "lead": sender_email}

        edition = session.execute(
            select(NewsletterEdition).where(NewsletterEdition.id == sub.edition_id)
        ).scalars().first()

        if intent == "newsletter_approval":
            # Lead approved their reworded section
            sub.status = SubmissionStatus.APPROVED

            session.add(AuditLog(
                edition_id=sub.edition_id,
                action=AuditAction.LEAD_APPROVED,
                actor=sender_email,
                detail=f"{sub.lead_name} approved their section",
            ))

            # Send acknowledgement
            _send_llm_reply(
                settings, sender_email, sender_name, subject, body_text,
                f"Lead {sub.lead_name} just APPROVED their section for {sub.programme}/{sub.workstream}. "
                f"Acknowledge the approval warmly and explain the next step.",
                session,
            )

            # Check if all leads approved → consolidate
            _check_and_consolidate(session, edition, settings)

        elif intent == "newsletter_changes":
            sub.status = SubmissionStatus.CHANGES_REQUESTED
            sub.raw_content = body_text

            session.add(AuditLog(
                edition_id=sub.edition_id,
                action=AuditAction.LEAD_CHANGES_REQUESTED,
                actor=sender_email,
                detail=f"{sub.lead_name} requested changes",
            ))

            _reword_and_send_approval(session, sub, settings)

        elif intent == "newsletter_content":
            # Lead sent their raw updates
            sub.raw_content = body_text
            sub.status = SubmissionStatus.RECEIVED

            logger.info(
                "storing_raw_content",
                lead=sender_email,
                raw_len=len(body_text),
                raw_preview=body_text[:200],
            )

            session.add(AuditLog(
                edition_id=sub.edition_id,
                action=AuditAction.RESPONSE_RECEIVED,
                actor=sender_email,
                detail=f"Raw content received from {sub.lead_name}",
            ))

            # Trigger rewording → approval flow
            _reword_and_send_approval(session, sub, settings)

        session.commit()
        return {"status": "processed", "lead": sender_email, "intent": intent}

    except Exception as exc:
        logger.error("lead_reply_error", sender=sender_email, error=str(exc))
        session.rollback()
        return {"error": str(exc)}
    finally:
        session.close()


@celery_app.task(name="digital_employee.tasks.workflow_tasks.handle_anuj_reply")
def handle_anuj_reply(
    intent: str,
    body_text: str,
    subject: str,
) -> dict:
    """Process a reply from the delivery leader (Anuj)."""
    session = _get_sync_session()
    settings = Settings()

    try:
        # Find the edition awaiting Anuj's review
        edition = session.execute(
            select(NewsletterEdition).where(
                NewsletterEdition.status == EditionStatus.AWAITING_ANUJ_APPROVAL
            ).order_by(NewsletterEdition.updated_at.desc())
        ).scalars().first()

        if not edition:
            # No edition awaiting — treat as general email
            handle_general_email.delay(
                sender_email=settings.anuj_email,
                sender_name=settings.anuj_name,
                subject=subject,
                body_text=body_text,
            )
            return {"status": "routed_to_general"}

        if intent == "anuj_approval":
            # Anuj approved — send to client
            edition.status = EditionStatus.SENT_TO_CLIENT
            edition.sent_at = datetime.now(timezone.utc)

            session.add(AuditLog(
                edition_id=edition.id,
                action=AuditAction.ANUJ_APPROVED,
                actor=settings.anuj_email,
                detail="Newsletter approved for client delivery",
            ))

            # Send to client
            from digital_employee.services.email_service import EmailService

            email_svc = EmailService(settings)
            email_svc.send_newsletter_to_client(
                distribution_list=settings.distribution_list,
                newsletter_html=edition.html_content or "",
                edition_title=edition.title,
            )

            session.add(AuditLog(
                edition_id=edition.id,
                action=AuditAction.SENT_TO_CLIENT,
                actor="system",
                detail=f"Newsletter sent to {len(settings.distribution_list)} recipients on the distribution list",
            ))

            # Mark complete and index for RAG
            edition.status = EditionStatus.COMPLETED
            _index_newsletter_for_rag(session, edition, settings)

            # Acknowledge Anuj
            _send_llm_reply(
                settings, settings.anuj_email, settings.anuj_name, subject, body_text,
                f"Anuj just APPROVED the newsletter '{edition.title}'. "
                f"Confirm that the newsletter has been sent to {len(settings.distribution_list)} people on the distribution list.",
                session,
            )

        else:
            # Anuj gave feedback — incorporate and re-submit
            edition.anuj_feedback = body_text
            edition.status = EditionStatus.INCORPORATING_FEEDBACK
            edition.attempt_count += 1

            session.add(AuditLog(
                edition_id=edition.id,
                action=AuditAction.ANUJ_FEEDBACK,
                actor=settings.anuj_email,
                detail=f"Feedback received (attempt {edition.attempt_count})",
            ))

            session.commit()

            # Incorporate feedback via LLM and re-send
            _incorporate_and_resubmit(session, edition, settings)

        session.commit()
        return {"status": "processed", "intent": intent}

    except Exception as exc:
        logger.error("anuj_reply_error", error=str(exc))
        session.rollback()
        return {"error": str(exc)}
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# General Email Handler — Conversational AI
# ─────────────────────────────────────────────────────────────────────────────


@celery_app.task(name="digital_employee.tasks.workflow_tasks.handle_general_email")
def handle_general_email(
    sender_email: str,
    sender_name: str,
    subject: str,
    body_text: str,
) -> dict:
    """Handle non-newsletter emails: questions, conversations, anything.

    The LLM generates a contextual, conversational reply.
    """
    session = _get_sync_session()
    settings = Settings()

    try:
        workflow_context = _build_workflow_context(session)

        # Load or create conversation thread
        conv = session.execute(
            select(EmailConversation)
            .where(EmailConversation.sender_email == sender_email)
            .order_by(EmailConversation.updated_at.desc())
        ).scalars().first()

        conversation_history = "No prior conversation."
        if conv:
            try:
                messages = json.loads(conv.messages_json)
                conversation_history = "\n".join(
                    f"{m['role']}: {m['content'][:300]}" for m in messages[-10:]
                )
            except (json.JSONDecodeError, KeyError):
                pass

        # Generate reply via LLM
        llm_svc = LLMService(settings)
        reply_text = _run_async(llm_svc.generate_email_reply(
            sender_email=sender_email,
            sender_name=sender_name,
            subject=subject,
            body=body_text,
            workflow_context=workflow_context,
            conversation_history=conversation_history,
        ))

        # Send the reply
        from digital_employee.services.email_service import EmailService

        email_svc = EmailService(settings)
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        reply_html = f"<html><body>{reply_text.replace(chr(10), '<br/>')}</body></html>"
        email_svc.send_email(sender_email, reply_subject, reply_html, body_text=reply_text)

        # Update conversation history
        now = datetime.now(timezone.utc).isoformat()
        if conv:
            messages = json.loads(conv.messages_json) if conv.messages_json else []
        else:
            conv = EmailConversation(
                sender_email=sender_email,
                sender_name=sender_name,
                subject=subject,
            )
            session.add(conv)
            messages = []

        messages.append({"role": "user", "content": body_text[:1000], "timestamp": now})
        messages.append({"role": "assistant", "content": reply_text[:1000], "timestamp": now})
        # Keep last 20 messages
        conv.messages_json = json.dumps(messages[-20:])

        # Audit log
        session.add(AuditLog(
            action=AuditAction.EMAIL_REPLY,
            actor="system",
            detail=f"Replied to {sender_email}: {subject[:100]}",
        ))

        session.commit()
        logger.info("general_email_replied", sender=sender_email, subject=subject[:60])
        return {"status": "replied", "sender": sender_email}

    except Exception as exc:
        logger.error("general_email_error", sender=sender_email, error=str(exc))
        session.rollback()
        return {"error": str(exc)}
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _send_llm_reply(
    settings: Settings,
    sender_email: str,
    sender_name: str,
    subject: str,
    body: str,
    extra_context: str,
    session,
):
    """Quick helper to send an LLM-generated reply for workflow acknowledgements."""
    llm_svc = LLMService(settings)
    workflow_context = _build_workflow_context(session) + f"\n\nADDITIONAL: {extra_context}"

    reply_text = _run_async(llm_svc.generate_email_reply(
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        body=body,
        workflow_context=workflow_context,
    ))

    from digital_employee.services.email_service import EmailService
    email_svc = EmailService(settings)
    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    reply_html = f"<html><body>{reply_text.replace(chr(10), '<br/>')}</body></html>"
    email_svc.send_email(sender_email, reply_subject, reply_html, body_text=reply_text)


def _reword_and_send_approval(session, sub: LeadSubmission, settings: Settings):
    """Reword content via LLM and send for lead approval."""
    from digital_employee.services.email_service import EmailService

    llm_svc = LLMService(settings)
    email_svc = EmailService(settings)

    reworded = _run_async(llm_svc.reword_content(
        raw_text=sub.raw_content or "",
        programme=sub.programme,
        workstream=sub.workstream,
    ))

    sub.reworded_content = reworded
    sub.status = SubmissionStatus.APPROVAL_SENT

    session.add(AuditLog(
        edition_id=sub.edition_id,
        action=AuditAction.CONTENT_REWORDED,
        actor="system",
        detail=f"Content reworded for {sub.lead_name}",
    ))

    email_svc.send_approval_request(
        lead_email=sub.lead_email,
        lead_name=sub.lead_name,
        programme=sub.programme,
        workstream=sub.workstream,
        reworded_content=reworded,
    )

    session.add(AuditLog(
        edition_id=sub.edition_id,
        action=AuditAction.APPROVAL_REQUESTED,
        actor="system",
        detail=f"Reworded content sent to {sub.lead_name} for approval",
    ))


def _check_and_consolidate(session, edition: NewsletterEdition, settings: Settings):
    """Check if all leads approved and consolidate if so."""
    subs = session.execute(
        select(LeadSubmission).where(LeadSubmission.edition_id == edition.id)
    ).scalars().all()

    # Check: all leads must be either APPROVED or SKIPPED
    all_resolved = all(
        s.status in (SubmissionStatus.APPROVED, SubmissionStatus.SKIPPED) for s in subs
    )
    any_approved = any(s.status == SubmissionStatus.APPROVED for s in subs)

    if not all_resolved or not any_approved:
        return

    # All resolved — consolidate (only include approved leads' content)
    from digital_employee.services.email_service import EmailService

    llm_svc = LLMService(settings)
    email_svc = EmailService(settings)

    sections = [
        {
            "programme": s.programme,
            "workstream": s.workstream,
            "lead_name": s.lead_name,
            "content": s.reworded_content or "",
        }
        for s in subs
        if s.status == SubmissionStatus.APPROVED and s.reworded_content
    ]

    content_html = _run_async(llm_svc.consolidate_newsletter(sections))

    from digital_employee.services.template_service import TemplateService

    template_svc = TemplateService()
    newsletter_html = template_svc.render_newsletter(
        title=edition.title,
        date=datetime.now(timezone.utc),
        content_html=content_html,
    )

    review_html = template_svc.render_newsletter(
        title=edition.title,
        date=datetime.now(timezone.utc),
        content_html=content_html,
        anuj_instructions=True,
        reviewer_name=settings.anuj_name,
    )

    edition.html_content = newsletter_html
    edition.status = EditionStatus.AWAITING_ANUJ_APPROVAL

    session.add(AuditLog(
        edition_id=edition.id,
        action=AuditAction.NEWSLETTER_CONSOLIDATED,
        actor="system",
        detail=f"Newsletter consolidated from {len(sections)} sections",
    ))

    # Send to Anuj
    email_svc.send_newsletter_for_review(
        reviewer_email=settings.anuj_email,
        reviewer_name=settings.anuj_name,
        newsletter_html=review_html,
        edition_title=edition.title,
    )

    session.add(AuditLog(
        edition_id=edition.id,
        action=AuditAction.SENT_TO_ANUJ,
        actor="system",
        detail="Consolidated newsletter sent to Anuj for review",
    ))


def _incorporate_and_resubmit(session, edition: NewsletterEdition, settings: Settings):
    """Incorporate Anuj's feedback and re-submit."""
    from digital_employee.services.email_service import EmailService

    llm_svc = LLMService(settings)
    email_svc = EmailService(settings)

    revised_content = _run_async(llm_svc.incorporate_feedback(
        current_newsletter=edition.html_content or "",
        feedback=edition.anuj_feedback or "",
    ))

    from digital_employee.services.template_service import TemplateService

    template_svc = TemplateService()
    newsletter_html = template_svc.render_newsletter(
        title=edition.title,
        date=datetime.now(timezone.utc),
        content_html=revised_content,
    )

    review_html = template_svc.render_newsletter(
        title=edition.title,
        date=datetime.now(timezone.utc),
        content_html=revised_content,
        anuj_instructions=True,
        reviewer_name=settings.anuj_name,
    )

    edition.html_content = newsletter_html
    edition.status = EditionStatus.AWAITING_ANUJ_APPROVAL
    edition.anuj_feedback = None

    session.add(AuditLog(
        edition_id=edition.id,
        action=AuditAction.FEEDBACK_INCORPORATED,
        actor="system",
        detail=f"Feedback incorporated (attempt {edition.attempt_count})",
    ))

    email_svc.send_newsletter_for_review(
        reviewer_email=settings.anuj_email,
        reviewer_name=settings.anuj_name,
        newsletter_html=review_html,
        edition_title=edition.title,
    )

    session.add(AuditLog(
        edition_id=edition.id,
        action=AuditAction.SENT_TO_ANUJ,
        actor="system",
        detail=f"Revised newsletter re-submitted to Anuj (attempt {edition.attempt_count})",
    ))


def _index_newsletter_for_rag(session, edition: NewsletterEdition, settings: Settings):
    """Index a completed newsletter into pgvector for RAG."""
    try:
        llm_svc = LLMService(settings)
        rag_svc = RAGService(llm_svc)

        async def _index():
            from digital_employee.database import async_session_factory
            async with async_session_factory() as async_session:
                await rag_svc.index_newsletter(
                    session=async_session,
                    edition_id=edition.id,
                    html_content=edition.html_content or "",
                    edition_title=edition.title,
                )
                await async_session.commit()

        _run_async(_index())
        logger.info("newsletter_indexed_for_rag", edition_id=str(edition.id))

    except Exception as exc:
        logger.error("rag_indexing_failed", edition_id=str(edition.id), error=str(exc))
