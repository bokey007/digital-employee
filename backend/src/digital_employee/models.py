"""SQLAlchemy ORM models for the Digital Employee."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# ── Enums ────────────────────────────────────────────────────────────────────


class EditionStatus(str, enum.Enum):
    """Newsletter edition lifecycle status."""

    INITIATED = "initiated"
    COLLECTING = "collecting"
    REWORDING = "rewording"
    AWAITING_LEAD_APPROVAL = "awaiting_lead_approval"
    AWAITING_PROGRAMME_LEAD_APPROVAL = "awaiting_programme_lead_approval"  # new
    CONSOLIDATING = "consolidating"
    AWAITING_ASHWIN_APPROVAL = "awaiting_ashwin_approval"  # new
    INCORPORATING_ASHWIN_FEEDBACK = "incorporating_ashwin_feedback"  # new
    AWAITING_ANUJ_APPROVAL = "awaiting_anuj_approval"
    INCORPORATING_FEEDBACK = "incorporating_feedback"
    SENT_TO_CLIENT = "sent_to_client"
    COMPLETED = "completed"
    FAILED = "failed"


class SubmissionStatus(str, enum.Enum):
    """Status of an individual lead's submission."""

    PENDING = "pending"  # request sent, waiting for reply
    RECEIVED = "received"  # raw content received from lead
    REWORDED = "reworded"  # LLM reworded content ready
    APPROVAL_SENT = "approval_sent"  # reworded sent to lead for approval
    APPROVED = "approved"  # lead approved the reworded content
    CHANGES_REQUESTED = "changes_requested"  # lead wants edits
    SKIPPED = "skipped"  # lead unresponsive, skipped from newsletter


class AuditAction(str, enum.Enum):
    """Types of auditable actions."""

    CYCLE_STARTED = "cycle_started"
    REQUEST_SENT = "request_sent"
    RESPONSE_RECEIVED = "response_received"
    CONTENT_REWORDED = "content_reworded"
    APPROVAL_REQUESTED = "approval_requested"
    LEAD_APPROVED = "lead_approved"
    LEAD_CHANGES_REQUESTED = "lead_changes_requested"
    NEWSLETTER_CONSOLIDATED = "newsletter_consolidated"
    SENT_TO_PROGRAMME_LEAD = "sent_to_programme_lead"  # new
    PROGRAMME_LEAD_APPROVED = "programme_lead_approved"  # new
    PROGRAMME_LEAD_FEEDBACK = "programme_lead_feedback"  # new
    SENT_TO_ASHWIN = "sent_to_ashwin"  # new
    ASHWIN_APPROVED = "ashwin_approved"  # new
    ASHWIN_FEEDBACK = "ashwin_feedback"  # new
    SENT_TO_ANUJ = "sent_to_anuj"
    ANUJ_APPROVED = "anuj_approved"
    ANUJ_FEEDBACK = "anuj_feedback"
    FEEDBACK_INCORPORATED = "feedback_incorporated"
    SENT_TO_CLIENT = "sent_to_client"
    REMINDER_SENT = "reminder_sent"
    EMAIL_REPLY = "email_reply"
    LEAD_SKIPPED = "lead_skipped"
    ERROR = "error"


# ── Models ───────────────────────────────────────────────────────────────────


class NewsletterEdition(Base):
    """A single newsletter cycle / edition."""

    __tablename__ = "newsletter_editions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[EditionStatus] = mapped_column(
        Enum(EditionStatus), default=EditionStatus.INITIATED, nullable=False
    )
    html_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    anuj_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    programme_lead_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)  # new
    ashwin_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)  # new
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    submissions: Mapped[list[LeadSubmission]] = relationship(
        back_populates="edition", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="edition", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<NewsletterEdition {self.id} [{self.status.value}]>"


class LeadSubmission(Base):
    """Content submission from a single sub-workstream lead."""

    __tablename__ = "lead_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("newsletter_editions.id"), nullable=False
    )
    lead_email: Mapped[str] = mapped_column(String(320), nullable=False)
    lead_name: Mapped[str] = mapped_column(String(200), nullable=False)
    programme: Mapped[str] = mapped_column(String(300), nullable=False)
    workstream: Mapped[str] = mapped_column(String(300), nullable=False)

    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    reworded_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus), default=SubmissionStatus.PENDING, nullable=False
    )
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    edition: Mapped[NewsletterEdition] = relationship(back_populates="submissions")

    def __repr__(self) -> str:
        return f"<LeadSubmission {self.lead_email} [{self.status.value}]>"


class AuditLog(Base):
    """Immutable audit trail of every action."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    edition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("newsletter_editions.id"), nullable=True
    )
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)
    actor: Mapped[str] = mapped_column(
        String(320), nullable=False, default="system"
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    edition: Mapped[NewsletterEdition | None] = relationship(
        back_populates="audit_logs"
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action.value} @ {self.timestamp}>"


class ChatMessage(Base):
    """Chat message for RAG Q&A sessions."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NewsletterEmbedding(Base):
    """Vector embeddings for newsletter content (pgvector)."""

    __tablename__ = "newsletter_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("newsletter_editions.id"), nullable=False
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    embedding = Column(Vector(1536))  # OpenAI text-embedding-3-small dimension

    __table_args__ = (
        Index(
            "ix_newsletter_embeddings_vector",
            embedding,
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<NewsletterEmbedding edition={self.edition_id} chunk={self.chunk_index}>"


class EmailConversation(Base):
    """Tracks email conversation threads for non-newsletter emails."""

    __tablename__ = "email_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    sender_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    thread_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    messages_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )  # JSON array of {role, content, timestamp}
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<EmailConversation {self.sender_email} [{self.subject[:40]}]>"
