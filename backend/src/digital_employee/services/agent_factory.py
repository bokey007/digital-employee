"""LangGraph agent factory — creates checkpointed agents for admin chat and portal collaboration."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import structlog
try:
    from langchain.agents import create_react_agent as _create_react_agent
except ImportError:
    from langgraph.prebuilt import create_react_agent as _create_react_agent
create_react_agent = _create_react_agent

logger = structlog.get_logger(__name__)

# ── Shared Digital Employee Persona ─────────────────────────────────────────

DIGITAL_EMPLOYEE_PERSONA = (
    "You are BI's Digital Employee — an intelligent, warm, and professional AI colleague "
    "at Boehringer Ingelheim Information Management Shared Services. "
    "You address people by their first name. "
    "You write with clarity, confidence, and a human touch. "
    "You are concise and never verbose. "
    "You never fabricate facts or invent content. "
    "You proactively guide people to the next step. "
)


# ── Connection string helper ─────────────────────────────────────────────────

def _to_psycopg_conn_string(conn_string: str) -> str:
    """Convert any SQLAlchemy DSN to a plain psycopg3-compatible connection string."""
    return (
        conn_string
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg2://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
    )


# ── Checkpointer context manager ─────────────────────────────────────────────

@asynccontextmanager
async def checkpointer_context(conn_string: str):
    """Async context manager that yields an initialised AsyncPostgresSaver.

    The connection stays alive for the duration of the `async with` block.
    Use this for per-request portal chat streams.

    Usage:
        async with checkpointer_context(settings.database_url_sync) as cp:
            agent = create_portal_agent(llm, system_prompt, cp)
            async for chunk in agent.astream(...):
                ...
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    psycopg_conn = _to_psycopg_conn_string(conn_string)
    async with AsyncPostgresSaver.from_conn_string(psycopg_conn) as checkpointer:
        await checkpointer.setup()   # idempotent — creates LG tables if not present
        yield checkpointer


# ── System prompt builders ───────────────────────────────────────────────────

def build_admin_agent_system_prompt() -> str:
    """Build the system prompt for the admin RAG chat agent."""
    return (
        DIGITAL_EMPLOYEE_PERSONA
        + "\n\nYou are helping internal administrators and programme leads understand "
        "newsletter progress. You have access to two tools:\n"
        "1. search_past_newsletters: Semantic search over approved, historical newsletters.\n"
        "2. get_current_inprogress_updates: Fetches real-time draft updates for the active cycle.\n\n"
        "== COMMUNICATION STYLE ==\n"
        "- Always respond in clear, well-structured Markdown.\n"
        "- Use emojis (🚀, 📊, 💡, ✅) to make responses engaging.\n"
        "- Use bold for names, workstreams, and key metrics.\n"
        "- Use headings (###) to separate workstreams or time periods.\n\n"
        "== MULTI-MONTH COMPARISONS ==\n"
        "- For multi-month queries, call search_past_newsletters ONCE PER MONTH.\n"
        "- Also call get_current_inprogress_updates for 'current/ongoing' queries.\n"
        "Use tools ONLY when necessary. For greetings or general questions, reply naturally."
    )


def build_portal_submit_system_prompt(
    actor_name: str,
    programme: str,
    workstream: str,
    edition_title: str,
    previous_content: str | None = None,
) -> str:
    """Build the system prompt for a portal submission chat session."""
    prev_ref = ""
    if previous_content:
        prev_ref = (
            f"\n\nPREVIOUS MONTH'S CONTENT FOR REFERENCE (from {workstream}):\n"
            f"{previous_content[:1500]}\n\n"
            "Use this as a style reference only if the user asks — never copy it verbatim.\n"
        )

    return (
        DIGITAL_EMPLOYEE_PERSONA
        + f"\n\nYou are helping {actor_name} craft their newsletter contribution "
        f"for the **{workstream}** workstream under the **{programme}** programme "
        f"for the **{edition_title}**.\n\n"
        "Your job is to help refine the AI-reworded content based on their feedback.\n"
        "Stay strictly within the content they provided — never add facts.\n\n"
        "== RESPONSE FORMAT ==\n"
        "When the user asks for changes:\n"
        "1. First write a SHORT plain-text summary of what you changed (1-2 sentences max, no HTML).\n"
        "2. Then output the FULL updated draft inside [DRAFT] and [/DRAFT] tags:\n"
        "   [DRAFT]\n"
        "   <h4>Key Highlights</h4><ul><li>...</li></ul>\n"
        "   <h4>Delivery Updates</h4><ul><li>...</li></ul>\n"
        "   <h4>Innovation & Value Add</h4><ul><li>...</li></ul>\n"
        "   [/DRAFT]\n\n"
        "IMPORTANT: Keep your conversational text brief and plain. Never include HTML outside the [DRAFT] block.\n"
        "If the user is just chatting (not asking for changes), reply normally with no [DRAFT] block.\n"
        + prev_ref
    )


def build_portal_review_system_prompt(
    actor_name: str,
    role: str,
    edition_title: str,
) -> str:
    """Build the system prompt for a portal review chat session."""
    role_label = {
        "programme_lead": "Programme Lead",
        "ashwin": "Senior Reviewer",
        "anuj": "Delivery Leader",
    }.get(role, "Reviewer")

    return (
        DIGITAL_EMPLOYEE_PERSONA
        + f"\n\nYou are assisting {actor_name} ({role_label}) in reviewing the **{edition_title}**.\n\n"
        "The user can ask you to revise specific sections, rephrase paragraphs, adjust tone, "
        "or make any editorial changes to the newsletter. "
        "Do not add facts. Preserve all figures and project names exactly as given. "
        "Be concise in your explanations and proactive in suggesting improvements if asked.\n\n"
        "IMPORTANT — Output format when making any changes:\n"
        "1. Write a short conversational acknowledgement (1-2 sentences max) — NO HTML here.\n"
        "2. Then output the CONTENT BODY HTML wrapped in delimiters EXACTLY like this:\n"
        "[DRAFT]\n"
        "<your revised content body HTML here>\n"
        "[/DRAFT]\n"
        "CRITICAL: The content inside [DRAFT]...[/DRAFT] must be CONTENT BODY HTML ONLY.\n"
        "Do NOT include <!DOCTYPE>, <html>, <head>, or <body> tags — those are added automatically.\n"
        "Do NOT include the newsletter header, navigation bar, key contacts section, or footer.\n"
        "Output ONLY the inner newsletter sections (KEY HIGHLIGHTS, DELIVERY UPDATES, QUALITY, INNOVATION).\n"
        "The frontend will automatically extract and apply the HTML from inside [DRAFT]...[/DRAFT]. "
        "Do NOT put explanations or HTML outside those delimiters."
    )


# ── Agent creators ───────────────────────────────────────────────────────────

async def create_admin_rag_agent(llm: Any, tools: list, conn_string: str):
    """Create the admin RAG chat agent with an open psycopg connection per-request."""
    import psycopg
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    psycopg_conn = _to_psycopg_conn_string(conn_string)
    conn = await psycopg.AsyncConnection.connect(
        psycopg_conn, autocommit=True, prepare_threshold=0
    )
    checkpointer = AsyncPostgresSaver(conn=conn)
    await checkpointer.setup()

    agent = create_react_agent(
        llm,
        tools=tools,
        prompt=build_admin_agent_system_prompt(),
        checkpointer=checkpointer,
    )
    logger.info("admin_rag_agent_created")
    return agent


def create_portal_agent(llm: Any, system_prompt: str, checkpointer: Any):
    """Create a stateless portal chat agent. Caller owns the checkpointer lifecycle.

    Always call this inside a `checkpointer_context()` block:

        async with checkpointer_context(conn_string) as cp:
            agent = create_portal_agent(llm, system_prompt, cp)
            async for chunk in agent.astream(...):
                ...
    """
    agent = create_react_agent(
        llm,
        tools=[],          # portal does pure conversational chat — no tools
        prompt=system_prompt,
        checkpointer=checkpointer,
    )
    logger.info("portal_agent_created")
    return agent
