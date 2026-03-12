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
| **Portal-Based Review Workflow** | All leads, programme leads, Ashwin, and Anuj review and approve content through personalised, token-secured web portal links — no email replies required |
| **AI Chatbot in Review Portal** | Ashwin and Anuj can instruct the AI directly in the portal to refine the newsletter before approving. Chat responses stream in real-time via SSE. |
| **Reference Data Panel** | Ashwin can view all workstream and programme lead submissions side-by-side while reviewing. Anuj additionally sees Ashwin's approved draft for full context. |
| **LLM Content Engine** | OpenAI / Azure OpenAI rewording, consolidation, and feedback incorporation |
| **Dedicated Quality Dashboard Pipeline** | Automatically emails numerical metrics requests to the Quality lead and algorithmically maps their response directly into a bespoke HTML dashboard circle grid |
| **Multi-Level Approvals** | 4-stage chain: Workstream Lead → Programme Lead (if configured) → Ashwin → Anuj → Distribution List |
| **Flexible Programme Lead Routing** | Programmes with a `programme_lead_email` in `teams.yaml` always require programme lead approval — regardless of the number of workstreams. Programmes without one go directly to Ashwin. |
| **3-Reminder Email Schedule** | Automatically sends up to 3 daily reminder emails for each pending action across every persona, for the current active cycle only |
| **Agentic AI Chatbot** | LangGraph Tool-calling Agent that dynamically queries both historical RAG data (pgvector) and live SQL Work-In-Progress drafts to answer complex comparative questions |
| **Premium SaaS Template** | Outlook-optimized HTML template with a magazine aesthetic — BI colors, Segoe UI typography, glassmorphism |
| **Admin Control Panel** | Real-time dashboard, newsletter management, lead tracking, activity feed |
| **Production-Ready Infra** | Helm charts for OpenShift, Docker Compose for local dev, HPA, health probes |
| **Impact Tracking** | Automatically calculates internal ROI (Hours Saved & Dollars Saved) natively in the dashboard based on an empirical time-tracking cost model. |

---

## 📈 Dashboard Impact Metrics Justification

The dashboard natively tracks automation savings. To ensure the ROI figures are highly realistic, defensible, and unarguable to stakeholders, the system calculates savings using a conservative enterprise baseline model:

*   **Emails Sent (10 minutes each)**: Time to compose, format, and send personalised review requests and reminders to every lead.
*   **Portal Interactions (10 minutes each)**: Time a human coordinator would spend manually chasing a reviewer, recording their decision, and routing it to the next stage — replaced by the automated portal flow.
*   **Chatbot Questions (15 minutes each)**: Time it takes a human to context-switch, search through SharePoint or wiki files, or interrupt a colleague to find an elusive policy answer.
*   **Content Rewording (20 minutes per section)**: The AI takes raw, unstructured bullet points from engineers and writes a polished, brand-aligned, grammatically correct paragraph.
*   **Newsletter Consolidation (30 minutes)**: Taking 10+ separate workstream texts, assembling them in HTML, formatting headings, applying Boehringer Ingelheim colors, and ensuring a pristine layout.
*   **Cost Savings ($65/hour)**: Represents a blended, highly conservative fully-loaded corporate rate for internal PMs or Communications Managers. *(Calculated algorithmically inside `dashboard.py`)*

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
INITIATE → COLLECT → REWORD → LEAD APPROVAL
                                    │
           ┌────────────────────────┤
           ▼                        ▼
  [Multi-workstream]        [Single-workstream]
  → PROGRAMME LEAD               │
    APPROVAL                     │
           │                     │
           └──────────┬──────────┘
                      ▼
              CONSOLIDATE (full newsletter)
                      │
                      ▼
               ASHWIN REVIEW
          ┌────────┘  └──────────────┐
          ▼                          ▼
      ANUJ REVIEW         INCORPORATE ASHWIN FEEDBACK
     (final sign-off)              │
          │                        └──────► ASHWIN REVIEW
          ▼
  SEND TO CLIENT → COMPLETE
```

> **Programme lead routing** is determined solely by whether `programme_lead_email` is set in `teams.yaml` — not by the number of workstreams. A single-workstream programme **with** a programme lead still goes through that lead's approval before Ashwin.

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
| `ANUJ_EMAIL` | Delivery leader's email for final approval |
| `ASHWIN_EMAIL` | Penultimate reviewer's email (approves before Anuj) |
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

Edit [`backend/config/teams.yaml`](backend/config/teams.yaml) with your actual programmes, workstreams, and lead contacts.

**Routing rule:** The presence of `programme_lead_email` determines whether a programme lead approval step is required — **not** the number of workstreams.

```yaml
programmes:
  # Multi-workstream programme WITH programme lead
  # → All workstream leads approve → programme lead approves → Ashwin
  - name: "Business Reporting"
    programme_lead_name: "Anitha Shalini"
    programme_lead_email: "anitha.shalini.ext@yourorg.com"
    workstreams:
      - name: "CRM & MCE"
        lead_name: "Pallavi Kaushik"
        lead_email: "pallavi.kaushik.ext@yourorg.com"
      - name: "Value & Access"
        lead_name: "Snehasish Samal"
        lead_email: "snehasish.samal.ext@yourorg.com"

  # Single-workstream programme WITH programme lead
  # → Workstream lead approves → programme lead approves → Ashwin
  - name: "Digital"
    programme_lead_name: "Vimal"
    programme_lead_email: "vimal.gunasekaran.ext@yourorg.com"
    workstreams:
      - name: "Digital"
        lead_name: "Shivangi"
        lead_email: "shivangi.singh.ext@yourorg.com"

  # Single-workstream programme WITHOUT programme lead
  # → Workstream lead approves → directly to Ashwin (no intermediate step)
  - name: "Quality"
    workstreams:
      - name: "Quality"
        lead_name: "Mithun"
        lead_email: "mithun.seshadri.ext@yourorg.com"
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/newsletters` | List all editions (paginated, filterable) |
| `GET` | `/api/newsletters/{id}` | Get edition detail with submissions |
| `GET` | `/api/newsletters/{id}/preview` | HTML preview of the newsletter |
| `POST` | `/api/newsletters/trigger` | Start a new newsletter cycle |
| `GET` | `/api/dashboard/metrics` | Dashboard summary metrics (includes ROI) |
| `GET` | `/api/dashboard/activity` | Audit trail / activity feed |
| `POST` | `/api/chat` | RAG chat query (non-streaming) |
| `POST` | `/api/chat/stream` | RAG chat query (SSE streaming) |
| `GET` | `/api/chat/history/{session_id}` | Chat conversation history |
| `GET` | `/api/leads/config` | Get teams.yaml configuration |
| `PUT` | `/api/leads/config` | Update teams configuration |
| `GET` | `/api/leads/stats` | Per-lead statistics |
| `GET` | `/api/portal/token/{token}` | Validate portal token, return role & context |
| `POST` | `/api/portal/chat` | AI chat in the review portal (SSE streaming) |
| `POST` | `/api/portal/approve` | Submit approval via portal |
| `POST` | `/api/portal/feedback` | Submit revision feedback via portal |
| `GET` | `/api/portal/reference-data` | Source materials for Ashwin/Anuj reference panel |
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
2. **Digital Employee emails** all workstream leads a personalised portal link requesting their update
3. Each lead clicks the link, reviews the AI-reworded version of their submission, makes edits via chatbot if needed, and **approves via the portal**
4. For programmes with a `programme_lead_email`: once all workstream leads approve, the consolidated programme section is sent to the **Programme Lead** for intermediate review via their own portal link
5. For programmes **without** a programme lead: workstream lead approval goes directly to Ashwin
6. When all programmes clear, the full newsletter is consolidated and sent to **Ashwin** via a review portal link
7. Ashwin can chat with the AI to refine the newsletter and view all source submissions in the **Reference Data Panel**
8. If Ashwin approves → newsletter forwarded to **Anuj** via a review portal link
9. Anuj can chat, refine, and also view Ashwin's final draft in the **Reference Data Panel**
10. If Anuj approves → the static header, key contacts, and footer are applied **once** and the **newsletter is broadcast to the Distribution List**
11. The completed newsletter is **indexed into pgvector** for RAG / Agent queries

**Reminders:** Up to 3 daily reminder emails are sent automatically for each pending action in the current active cycle only.

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
