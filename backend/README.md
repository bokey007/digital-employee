# Backend — Digital Employee

Python backend powering the AI newsletter automation agent.

## Stack

- **FastAPI** — async REST API with OpenAPI docs
- **SQLAlchemy** (async) — ORM with PostgreSQL + pgvector
- **LangGraph** — stateful workflow engine with PG checkpointing
- **Celery + Redis** — background tasks (inbox polling, reminders)
- **LangChain / OpenAI** — LLM for content rewording, consolidation, and RAG
- **structlog** — structured JSON logging
- **Pydantic Settings** — type-safe configuration from `.env`

## Quick Start

```bash
# Install dependencies
uv sync

# Copy and edit environment config
cp .env.example .env

# Start PostgreSQL + Redis (via Docker)
docker-compose up postgresql redis -d

# Run the API server
uv run uvicorn digital_employee.main:app --reload --port 8000

# Run Celery worker (separate terminal)
uv run celery -A digital_employee.tasks.celery_app worker --loglevel=info

# Run Celery beat scheduler (separate terminal)
uv run celery -A digital_employee.tasks.celery_app beat --loglevel=info
```

## Module Overview

```
src/digital_employee/
├── main.py              # FastAPI app factory, lifespan, CORS, health probes
├── settings.py          # Pydantic-settings (env vars → typed config)
├── models.py            # ORM: editions, submissions, audit_logs, chat, embeddings
├── database.py          # Async engine, sessions, pgvector init
│
├── api/                 # REST endpoints
│   ├── router.py        # Aggregates all sub-routers
│   ├── newsletters.py   # CRUD, trigger, preview
│   ├── dashboard.py     # Metrics + activity feed
│   ├── chat.py          # RAG chat (POST + SSE streaming)
│   └── leads.py         # Teams config + lead stats
│
├── services/            # Business logic
│   ├── email_service.py # IMAP reading + SMTP sending
│   ├── llm_service.py   # OpenAI/Azure: reword, consolidate, feedback, chat
│   ├── rag_service.py   # pgvector indexing + cosine similarity retrieval
│   ├── template_service.py  # Jinja2 newsletter rendering
│   └── notification.py  # WebSocket connection manager
│
├── workflow/            # LangGraph newsletter state machine
│   ├── state.py         # WorkflowState TypedDict
│   ├── nodes.py         # 8 node functions (initiate → complete)
│   ├── edges.py         # Conditional routing logic
│   └── graph.py         # Graph construction + compile
│
├── tasks/               # Celery background tasks
│   ├── celery_app.py    # Celery config + beat schedule
│   ├── email_tasks.py   # Inbox polling (60s) + daily reminders
│   └── workflow_tasks.py # Reply handling + orchestration
│
└── utils/
    ├── email_parser.py  # Reply classification + content extraction
    └── logging.py       # structlog setup
```

## Database Models

| Table | Purpose |
|-------|---------|
| `newsletter_editions` | Each newsletter cycle (status, HTML content, timestamps) |
| `lead_submissions` | Per-lead submission tracking (raw → reworded → approved) |
| `audit_logs` | Immutable audit trail of every action |
| `chat_messages` | RAG chat conversation history |
| `newsletter_embeddings` | pgvector embeddings for newsletter content |

## Configuration

All configuration is via environment variables (see [`.env.example`](.env.example)):

| Category | Variables |
|----------|-----------|
| **LLM** | `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, Azure variants |
| **Email** | `IMAP_HOST`, `IMAP_PORT`, `SMTP_HOST`, `SMTP_PORT`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD` |
| **Database** | `DATABASE_URL` (async), `DATABASE_URL_SYNC` (Celery) |
| **Redis** | `REDIS_URL` |
| **Recipients** | `ANUJ_EMAIL`, `ANUJ_NAME`, `CLIENT_EMAILS` |
| **Newsletter** | `NEWSLETTER_SUBJECT_PREFIX`, `REMINDER_AFTER_DAYS`, `MAX_REMINDERS` |
| **App** | `APP_NAME`, `APP_ENV`, `LOG_LEVEL`, `SECRET_KEY` |

## Team Configuration

Programmes, workstreams, and lead contacts are defined in [`config/teams.yaml`](config/teams.yaml). This file determines who gets emailed when a newsletter cycle starts.

## Testing

```bash
uv run pytest                    # Run all tests
uv run pytest --cov=digital_employee  # With coverage
```
