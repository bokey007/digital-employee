"""RAG Chat API endpoint with Server-Sent Events streaming."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from digital_employee.database import get_db
from digital_employee.models import ChatMessage, NewsletterEdition, LeadSubmission, EditionStatus
from digital_employee.services.llm_service import LLMService
from digital_employee.services.rag_service import RAGService
from digital_employee.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[dict]


class ChatHistoryItem(BaseModel):
    role: str
    content: str
    sources: Optional[list[dict]] = None
    timestamp: datetime


# ── Endpoints ────────────────────────────────────────────────────────────────


from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

AGENT_SYSTEM_PROMPT = """You are the AI Digital Employee for the Data & Analytics Programme.
You help project leads and the delivery leader understand newsletter progress.
You have access to two tools:
1. search_past_newsletters: Semantic search over approved, historical newsletters. Use this for queries about past achievements, historical progress, or specific months.
2. get_current_inprogress_updates: Fetches real-time, unapproved draft updates for the active cycle. Use this for queries about "current status", "what is pending", or "ongoing work".

== COMMUNICATION STYLE & FORMATTING ==
- Always respond in clear, well-structured, and beautiful Markdown.
- Use emojis and icons (🚀, 📊, 💡, ✅, etc.) to make your responses engaging, fun to read, and professional.
- Use bold text (`**`) for emphasis, especially for names, workstreams, and key metrics.
- Use headings (`###`) to separate different workstreams or time periods cleanly.
- Use bullet points (`-`) for lists of updates or highlights.

== CRITICAL INSTRUCTIONS FOR MULTI-MONTH COMPARISONS ==
- If a user asks for progress across multiple completed months AND current ongoing work (e.g. "for each month this year" or "compare Jan to now"):
    - You MUST call `search_past_newsletters` MULTIPLE TIMES, once for each specific completed month.
    - If the user asks about "current", "pending", "this month", or "ongoing" work alongside past months, you MUST ALSO explicitly call `get_current_inprogress_updates()` in the same session.
    - DO NOT try to search all months in one call. By calling it once per month, you ensure you get the specific updates for every single period.
    - After gathering all information from all tool calls (both past and WIP), synthesize a comprehensive comparative answer for the user.

Use tools ONLY when necessary. If the user asks a general question or just says "hi", just reply naturally without tools.
"""

@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ask a question using a dynamic tool-calling agent (non-streaming)."""
    settings = get_settings()
    llm_svc = LLMService(settings)
    rag_svc = RAGService(llm_svc)

    session_id = body.session_id or str(uuid.uuid4())
    history = await _get_chat_history(db, session_id)

    sources_list = []

    @tool
    async def search_past_newsletters(query: str, months: list[str] = None) -> str:
        """Search for information across past APPROVED, completed newsletters.
        Args:
            query: Semantic search query (e.g. "1ID decommissioning").
            months: Optional list of month names (e.g. ["January", "February"]).
        """
        chunks = await rag_svc.query(db, query, months=months, top_k=5)
        for c in chunks:
            sources_list.append({"edition": c["edition_title"], "section": c.get("section", ""), "score": c["score"]})
        return rag_svc.build_context(chunks)

    @tool
    async def get_current_inprogress_updates() -> str:
        """Fetch real-time, unapproved Work-In-Progress updates from the CURRENT active cycle."""
        return await _get_active_progress(db) or "No active work-in-progress drafts."

    agent = create_react_agent(
        llm_svc._llm, 
        tools=[search_past_newsletters, get_current_inprogress_updates],
        prompt=AGENT_SYSTEM_PROMPT
    )

    msg_history = []
    for m in history:
        msg_history.append(HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"]))
    msg_history.append(HumanMessage(content=body.question))

    response = await agent.ainvoke({"messages": msg_history})
    final_answer = response["messages"][-1].content

    # Save messages to DB
    db.add(ChatMessage(session_id=session_id, role="user", content=body.question))
    db.add(ChatMessage(session_id=session_id, role="assistant", content=final_answer, sources=json.dumps(sources_list)))
    await db.flush()

    return ChatResponse(session_id=session_id, answer=final_answer, sources=sources_list)


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Stream a chat response via Server-Sent Events using an intelligent Tool-Calling Agent."""
    settings = get_settings()
    llm_svc = LLMService(settings)
    rag_svc = RAGService(llm_svc)

    session_id = body.session_id or str(uuid.uuid4())
    history = await _get_chat_history(db, session_id)

    sources_list = []

    @tool
    async def search_past_newsletters(query: str, months: list[str] = None) -> str:
        """Search for information across past APPROVED, completed newsletters.
        Args:
            query: Semantic search query (e.g. "Data platform progress").
            months: Optional list of month names (e.g. ["Jan", "Feb", "March"]).
        """
        chunks = await rag_svc.query(db, query, months=months, top_k=5)
        for c in chunks:
            sources_list.append({"edition": c["edition_title"], "section": c.get("section", ""), "score": c["score"]})
        return rag_svc.build_context(chunks)

    @tool
    async def get_current_inprogress_updates() -> str:
        """Fetch real-time, unapproved Work-In-Progress updates from the CURRENT active cycle."""
        return await _get_active_progress(db) or "No active work-in-progress drafts."

    agent = create_react_agent(
        llm_svc._llm, 
        tools=[search_past_newsletters, get_current_inprogress_updates],
        prompt=AGENT_SYSTEM_PROMPT
    )

    msg_history = []
    for m in history:
        msg_history.append(HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"]))
    msg_history.append(HumanMessage(content=body.question))

    db.add(ChatMessage(session_id=session_id, role="user", content=body.question))
    await db.flush()

    async def event_generator():
        full_response = []
        
        # Stream events from the agent
        async for msg, meta in agent.astream({"messages": msg_history}, stream_mode="messages"):
            # If the model emits AI Message chunks, we stream them to the UI
            if msg.type == "AIMessageChunk" and msg.content:
                # If we just got our first real content token, emit the sources we collected from any tool calls
                if not full_response and sources_list:
                    # Deduplicate sources based on edition title
                    unique_sources = []
                    seen = set()
                    for s in sources_list:
                        if s["edition"] not in seen:
                            unique_sources.append(s)
                            seen.add(s["edition"])
                    yield {"event": "sources", "data": json.dumps({"sources": unique_sources, "session_id": session_id})}
                
                full_response.append(msg.content)
                yield {"event": "token", "data": json.dumps({"token": msg.content})}
            
            # We can optionally emit tool call events if we want the UI to show "Searching past newsletters..."
            elif msg.type == "AIMessageChunk" and msg.tool_calls:
                for tc in msg.tool_calls:
                    yield {"event": "tool_call", "data": json.dumps({"tool": tc["name"]})}

        answer = "".join(full_response)
        
        # Fallback if AI didn't stream any chunks but just returned an AIMessage (edge case)
        if not answer:
            final_state = await agent.ainvoke({"messages": msg_history})
            answer = final_state["messages"][-1].content
            yield {"event": "token", "data": json.dumps({"token": answer})}

        async with db.begin():
            db.add(ChatMessage(
                session_id=session_id,
                role="assistant",
                content=answer,
                sources=json.dumps(sources_list),
            ))

        yield {"event": "done", "data": json.dumps({"session_id": session_id})}

    return EventSourceResponse(event_generator())


@router.get("/history/{session_id}", response_model=list[ChatHistoryItem])
async def get_chat_history_endpoint(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get chat history for a session."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp.asc())
    )
    messages = result.scalars().all()

    return [
        ChatHistoryItem(
            role=msg.role,
            content=msg.content,
            sources=json.loads(msg.sources) if msg.sources else None,
            timestamp=msg.timestamp,
        )
        for msg in messages
    ]


async def _get_chat_history(db: AsyncSession, session_id: str) -> list[dict]:
    """Retrieve recent chat history for context."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp.desc())
        .limit(10)
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


async def _get_active_progress(db: AsyncSession) -> str:
    """Fetch unapproved, active Work-In-Progress updates from the database."""
    result = await db.execute(
        select(NewsletterEdition, LeadSubmission)
        .join(LeadSubmission, LeadSubmission.edition_id == NewsletterEdition.id)
        .where(NewsletterEdition.status != EditionStatus.COMPLETED)
        .where(LeadSubmission.raw_content.isnot(None))
        .order_by(NewsletterEdition.created_at.desc())
    )
    rows = result.all()
    if not rows:
        return ""

    context_parts = ["[CURRENT WORK IN PROGRESS (NOT YET APPROVED)]\nNote: The following information is currently being processed for the active newsletter cycle and may not be fully approved yet."]
    for edition, sub in rows:
        content = sub.reworded_content or sub.raw_content
        context_parts.append(
            f"Edition: {edition.title} | Overall Status: {edition.status.value}\n"
            f"Programme: {sub.programme} | Workstream: {sub.workstream} | Lead: {sub.lead_name}\n"
            f"Updates so far:\n{content}"
        )
    return "\n\n---\n\n".join(context_parts)
