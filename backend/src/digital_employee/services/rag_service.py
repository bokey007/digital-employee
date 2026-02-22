"""RAG service — pgvector-based newsletter search and retrieval."""

from __future__ import annotations

import re
import uuid
from typing import Sequence

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from digital_employee.models import NewsletterEmbedding, NewsletterEdition
from digital_employee.services.llm_service import LLMService

logger = structlog.get_logger(__name__)



class RAGService:
    """Indexes newsletter content into pgvector and retrieves relevant chunks."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    # ── Indexing ─────────────────────────────────────────────────────────────

    async def index_newsletter(
        self,
        session: AsyncSession,
        edition_id: uuid.UUID,
        html_content: str,
        edition_title: str,
    ) -> int:
        """Chunk a newsletter, generate embeddings, and store in pgvector.

        Returns:
            Number of chunks indexed.
        """
        # Strip HTML tags for plain-text chunking
        plain = re.sub(r"<[^>]+>", " ", html_content)
        plain = re.sub(r"\s+", " ", plain).strip()

        chunks = self._chunk_text(plain)
        if not chunks:
            logger.warning("no_chunks_generated", edition_id=str(edition_id))
            return 0

        # Generate embeddings in batch
        embeddings = await self._llm.generate_embeddings(chunks)

        # Store in pgvector table
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            record = NewsletterEmbedding(
                edition_id=edition_id,
                chunk_text=chunk_text,
                chunk_index=i,
                section=self._detect_section(chunk_text),
                embedding=embedding,
            )
            session.add(record)

        await session.flush()
        logger.info(
            "newsletter_indexed",
            edition_id=str(edition_id),
            chunks=len(chunks),
            title=edition_title,
        )
        return len(chunks)

    async def delete_edition_embeddings(
        self,
        session: AsyncSession,
        edition_id: uuid.UUID,
    ) -> None:
        """Remove all embeddings for a specific edition (for re-indexing)."""
        await session.execute(
            text("DELETE FROM newsletter_embeddings WHERE edition_id = :eid"),
            {"eid": edition_id},
        )

    # ── Retrieval ────────────────────────────────────────────────────────────

    async def query(
        self,
        session: AsyncSession,
        question: str,
        months: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Retrieve the most relevant newsletter chunks for a question.

        Args:
            session: SQLAlchemy async session.
            question: User's search query.
            months: Optional list of month names (e.g. ['January', 'February']) to filter by.
            top_k: Number of results to return.

        Returns:
            List of dicts with keys: chunk_text, edition_id, section, score
        """
        query_embedding = await self._llm.generate_query_embedding(question)

        # Build dynamic WHERE clause if months are provided
        where_clause = ""
        params = {
            "query_vec": str(query_embedding),
            "top_k": top_k,
        }
        
        if months:
            conditions = []
            for i, month in enumerate(months):
                key = f"month_{i}"
                conditions.append(f"ed.title ILIKE :{key}")
                params[key] = f"%{month}%"
            where_clause = "WHERE " + " OR ".join(conditions)

        # pgvector cosine distance query (smaller = more similar)
        stmt = text(f"""
            SELECT
                ne.chunk_text,
                ne.edition_id,
                ne.section,
                ne.embedding <=> :query_vec AS distance,
                ed.title AS edition_title,
                ed.created_at AS edition_date
            FROM newsletter_embeddings ne
            JOIN newsletter_editions ed ON ed.id = ne.edition_id
            {where_clause}
            ORDER BY ne.embedding <=> :query_vec
            LIMIT :top_k
        """)

        result = await session.execute(stmt, params)
        rows = result.fetchall()

        return [
            {
                "chunk_text": row.chunk_text,
                "edition_id": str(row.edition_id),
                "edition_title": row.edition_title,
                "edition_date": str(row.edition_date),
                "section": row.section,
                "score": 1 - row.distance,  # Convert distance to similarity
            }
            for row in rows
        ]

    def build_context(self, chunks: list[dict]) -> str:
        """Format retrieved chunks into a context string for the LLM."""
        if not chunks:
            return "No relevant newsletter content found."

        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"[Source {i}: {chunk['edition_title']} — {chunk.get('section', 'General')}]\n"
                f"{chunk['chunk_text']}\n"
            )
        return "\n---\n".join(context_parts)

    # ── Chunking ─────────────────────────────────────────────────────────────

    @staticmethod
    def _chunk_text(text: str) -> list[str]:
        """Return the entire text as a single chunk.
        
        Given modern LLM context windows (128k+ tokens), we can store and 
        retrieve the entire newsletter as a single chunk for better context.
        """
        if text.strip():
            return [text.strip()]
        return []

    @staticmethod
    def _detect_section(chunk_text: str) -> str | None:
        """Return 'Full Newsletter' since we store the entire document."""
        return "Full Newsletter"
