# 🤖 Digital Employee — AI-Powered Newsletter Automation

An autonomous AI agent that manages the entire lifecycle of monthly client newsletters: collecting updates from team leads, professionally rewording content via LLM, orchestrating multi-level approvals, and delivering the final newsletter — all monitored through a premium admin dashboard.

---

## ⚡ Quick Start (One Command)

```bash
# First time? Run setup:
./scripts/setup.sh      # installs deps, creates .env

# Then launch everything:
./scripts/start.sh      # Docker full stack → localhost:3000

# Or for local dev with hot-reload:
./scripts/dev.sh        # PG+Redis via Docker, everything else native
```

### All Commands

| Script | Make alias | What it does |
|--------|-----------|-------------|
| `./scripts/setup.sh` | `make setup` | Install deps, create `.env` from template |
| `./scripts/start.sh` | `make start` | Build & launch full stack via Docker Compose |
| `./scripts/dev.sh` | `make dev` | Local dev mode: hot-reload backend + frontend, PG+Redis in Docker |
| `./scripts/test.sh` | `make test` | Run backend tests, frontend tests, and import checks |
| `./scripts/stop.sh` | `make stop` | Stop all services (Docker + local processes) |
| — | `make logs` | Tail Docker Compose logs |
| — | `make clean` | Remove containers, volumes, and build artifacts |
| — | `make reset-db` | Wipe ONLY the PostgreSQL database for clean end-to-end testing |

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Autonomous Email Agent** | Polls inbox, classifies replies, sends requests & reminders — zero manual intervention |
| **LLM Content Engine** | OpenAI / Azure OpenAI rewording, consolidation, and feedback incorporation |
| **Dedicated Quality Dashboard Pipeline** | Automatically emails numerical metrics requests to the Quality lead and algorithmically maps their response directly into a bespoke HTML dashboard circle grid |
| **Multi-Level Approvals** | Team leads approve their sections → Delivery leader approves the full newsletter |
| **Agentic AI Chatbot** | LangGraph Tool-calling Agent that dynamically queries *both* historical RAG data (pgvector) and live SQL Work-In-Progress drafts to answer complex comparative questions. Responses are streamed and structured with beautiful ReactMarkdown typography, tailored spacing, and emojis. |
| **Premium SaaS Template** | Outlook-optimized HTML template rebuilt with a sleek, 10/10 magazine aesthetic (glassmorphism/box shadows, Segoe UI typography, Boehringer Ingelheim color palettes) |
| **Admin Control Panel** | Real-time dashboard, newsletter management, lead tracking, activity feed |
| **Production-Ready Infra** | Helm charts for OpenShift, Docker Compose for local dev, HPA, health probes |

---

## 🏗 Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  React Admin │◄───►│  FastAPI      │◄───►│  PostgreSQL      │
│  Dashboard   │ WS  │  Backend API  │     │  + pgvector      │
└──────────────┘     └──────┬───────┘     └──────────────────┘
                            │
                     ┌──────┴───────┐
                     │ Celery       │     ┌──────────────────┐
                     │ Workers      │◄───►│  Redis           │
                     │ + Beat       │     │  (broker/cache)  │
                     └──────┬───────┘     └──────────────────┘
                            │
                     ┌──────┴───────┐
                     │ Email Server │
                     │ (IMAP/SMTP)  │
                     └──────────────┘
```

### Newsletter Workflow (LangGraph State Machine)

```
INITIATE → COLLECT → REWORD → LEAD APPROVAL → CONSOLIDATE → ANUJ REVIEW
                                                                │
                                          ┌─────────────────────┤
                                          ▼                     ▼
                                  INCORPORATE FEEDBACK    SEND TO CLIENT → COMPLETE
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend API** | Python 3.12, FastAPI, SQLAlchemy (async), Pydantic |
| **Workflow Engine** | LangGraph with PostgreSQL checkpointing |
| **Task Queue** | Celery + Redis (60s inbox polling, daily reminders) |
| **LLM** | OpenAI / Azure OpenAI (GPT-4o, text-embedding-3-small) |
| **Database** | PostgreSQL 16 + pgvector extension |
| **Email** | IMAP (imapclient) + SMTP (smtplib) |
| **Frontend** | React 18, TypeScript, Tailwind CSS, Vite |
| **Charts** | Recharts |
| **State Management** | Zustand |
| **Containerisation** | Docker (multi-stage builds) |
| **Orchestration** | Docker Compose (dev), Helm + OpenShift (prod) |
| **Logging** | structlog (JSON) |

---

## 📁 Project Structure

```
digital_employee/
├── backend/
│   ├── src/digital_employee/
│   │   ├── api/              # FastAPI routers (newsletters, dashboard, chat, leads)
│   │   ├── services/         # Email, LLM, RAG, Template, WebSocket services
│   │   ├── workflow/         # LangGraph state, nodes, edges, graph
│   │   ├── tasks/            # Celery tasks (inbox polling, workflow orchestration)
│   │   ├── utils/            # Email parser, structured logging
│   │   ├── models.py         # SQLAlchemy ORM models + pgvector
│   │   ├── database.py       # Async engine & session management
│   │   ├── settings.py       # Pydantic-settings configuration
│   │   └── main.py           # FastAPI app factory
│   ├── config/teams.yaml     # Programme / workstream / lead definitions
│   ├── templates/            # Jinja2 newsletter HTML template
│   ├── tests/                # pytest test suite
│   ├── Dockerfile            # Multi-stage production build
│   └── pyproject.toml        # Dependencies (managed by uv)
├── frontend/
│   ├── src/
│   │   ├── api/client.ts     # Typed API client
│   │   ├── pages/            # Dashboard, Newsletters, Chat, Leads
│   │   ├── types/index.ts    # Shared TypeScript interfaces
│   │   ├── App.tsx           # App shell with sidebar navigation
│   │   └── index.css         # Tailwind + custom components
│   ├── Dockerfile            # Node build + nginx
│   └── package.json
├── helm/digital-employee/    # Helm chart for OpenShift
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/            # Deployments, Services, Route, HPA, ConfigMap, Secrets
├── docker-compose.yaml       # Local development stack
└── README.md                 # ← You are here
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+** and [`uv`](https://docs.astral.sh/uv/) (backend)
- **Node.js 20+** and `npm` (frontend)
- **Docker** and **Docker Compose** (for PostgreSQL, Redis, and full-stack runs)

### 1. Clone & Configure

```bash
cd digital_employee
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your credentials:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `EMAIL_ADDRESS` | The digital employee's email address |
| `EMAIL_PASSWORD` | App password for the email account |
| `IMAP_HOST` / `SMTP_HOST` | Mail server settings |
| `ANUJ_EMAIL` | Delivery leader's email for approvals |
| `DISTRIBUTION_LIST` | Comma-separated recipient list (e.g. `"client1@ext.com, stakeholder@int.com"`) |

### 2. Quick Start (Docker Compose)

```bash
# Spin up everything: PostgreSQL, Redis, Backend, Worker, Beat, Frontend
docker-compose up -d

# Access:
#   Frontend:  http://localhost:3000
#   API Docs:  http://localhost:8000/docs
#   Health:    http://localhost:8000/healthz
```

### 3. Local Development (Without Docker)

```bash
# Terminal 1: Backend API
cd backend
uv sync
uv run uvicorn digital_employee.main:app --reload --port 8000

# Terminal 2: Celery Worker
cd backend
uv run celery -A digital_employee.tasks.celery_app worker --loglevel=info

# Terminal 3: Celery Beat
cd backend
uv run celery -A digital_employee.tasks.celery_app beat --loglevel=info

# Terminal 4: Frontend
cd frontend
npm install
npm run dev
```

> **Note:** You'll need PostgreSQL (with pgvector) and Redis running locally. Use `docker-compose up postgresql redis` to start just those.

### 4. Configure Teams

Edit [`backend/config/teams.yaml`](backend/config/teams.yaml) with your actual programmes, workstreams, and lead contacts:

```yaml
programmes:
  - name: "Data & Analytics"
    workstreams:
      - name: "Data Platform"
        lead_name: "Priya Sharma"
        lead_email: "priya.sharma@yourorg.com"
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/newsletters` | List all editions (paginated, filterable) |
| `GET` | `/api/newsletters/{id}` | Get edition detail with submissions |
| `GET` | `/api/newsletters/{id}/preview` | HTML preview of the newsletter |
| `POST` | `/api/newsletters/trigger` | Start a new newsletter cycle |
| `GET` | `/api/dashboard/metrics` | Dashboard summary metrics |
| `GET` | `/api/dashboard/activity` | Audit trail / activity feed |
| `POST` | `/api/chat` | RAG chat query (non-streaming) |
| `POST` | `/api/chat/stream` | RAG chat query (SSE streaming) |
| `GET` | `/api/chat/history/{session_id}` | Chat conversation history |
| `GET` | `/api/leads/config` | Get teams.yaml configuration |
| `PUT` | `/api/leads/config` | Update teams configuration |
| `GET` | `/api/leads/stats` | Per-lead statistics |
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/readyz` | Readiness probe (checks DB) |
| `WS` | `/ws` | WebSocket real-time notifications |

Full interactive docs at `http://localhost:8000/docs` (Swagger UI).

---

## 🚢 Production Deployment (OpenShift / Helm)

```bash
# Build and push images
docker build -t your-registry/digital-employee-backend:0.1.0 backend/
docker build -t your-registry/digital-employee-frontend:0.1.0 frontend/

# Install Helm chart
cd helm/digital-employee
helm dependency update
helm install digital-employee . \
  --namespace digital-employee \
  --create-namespace \
  --set secrets.openaiApiKey="sk-..." \
  --set secrets.emailPassword="your-app-password" \
  --set secrets.secretKey="$(openssl rand -hex 32)" \
  --set route.host="digital-employee.apps.your-cluster.com" \
  --set backend.image.repository="your-registry/digital-employee-backend" \
  --set frontend.image.repository="your-registry/digital-employee-frontend"
```

The chart includes:
- Backend Deployment + Service (with health probes)
- Celery Worker Deployment (configurable concurrency)
- Celery Beat Deployment (single replica)
- Frontend Deployment + Service
- PostgreSQL StatefulSet (Bitnami, with pgvector init)
- Redis StatefulSet (Bitnami)
- OpenShift Route (TLS edge termination)
- HPA for backend and worker pods
- ConfigMap + Secret for all configuration

---

## 🔄 How the Workflow Works

1. **Admin triggers** a new newsletter cycle via the dashboard or API
2. **Digital Employee emails** all sub-workstream leads requesting updates
3. **Celery Beat** polls the inbox every 60 seconds for replies
4. When a lead replies, the **Email Parser** classifies it and the **LLM rewrites** it professionally
5. The reworded content is **sent back to the lead for approval**
6. Once **all leads approve**, the LLM **consolidates** everything into one newsletter
7. The consolidated newsletter is **sent to Anuj** for final review
8. If Anuj gives feedback → LLM incorporates it and re-submits
9. If Anuj approves → **newsletter is broadcasted to the entire Distribution List**
10. The completed newsletter is **indexed into pgvector** for RAG / Agent queries

Reminders are sent automatically if leads don't respond within the configured window (default: 3 days, max 2 reminders).

---

## 🧪 Testing

```bash
# Backend
cd backend
uv run pytest

# Frontend
cd frontend
npm test
```

---

## 📄 License

Internal use only. All rights reserved.
