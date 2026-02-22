# Frontend — Digital Employee Admin Panel

React admin dashboard for monitoring and controlling the AI newsletter agent.

## Stack

- **React 18** with TypeScript
- **Vite** — fast dev server and build tool
- **Tailwind CSS** — utility-first styling with custom design system
- **React Router** — client-side routing (4 pages)
- **Lucide React** — icon library
- **Recharts** — dashboard charts
- **Zustand** — lightweight state management

## Quick Start

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # Production build → dist/
npm test           # Vitest test suite
```

> The Vite dev server proxies `/api` and `/ws` to the backend at `localhost:8000`.

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | **Dashboard** | 6 metric cards (total editions, active cycles, pending, etc.) + scrollable activity feed |
| `/newsletters` | **Newsletters** | Edition list with status badges, detail panel with submission tracking, HTML preview iframe, "New Cycle" trigger button |
| `/chat` | **Chat** | RAG-powered Q&A about newsletters with bubble UI, typing animation, source citations, and suggested questions |
| `/leads` | **Leads** | Team structure tree view (programmes → workstreams → leads) with per-lead approval stats |

## Project Structure

```
src/
├── api/
│   └── client.ts        # Typed API client (dashboard, newsletters, chat, leads)
├── pages/
│   ├── DashboardPage.tsx # Metrics grid + activity feed
│   ├── NewslettersPage.tsx # Master-detail edition management
│   ├── ChatPage.tsx      # RAG chat with animations
│   └── LeadsPage.tsx     # Team structure + stats
├── types/
│   └── index.ts          # Shared TypeScript interfaces
├── App.tsx               # App shell: gradient sidebar, responsive nav, routing
├── main.tsx              # Entry point
├── index.css             # Tailwind layers + custom components + animations
└── vite-env.d.ts         # Vite type declarations
```

## Design System

The UI uses a custom Tailwind theme with:

- **Brand palette** — Blue gradient (50–950) for primary elements
- **Glassmorphism** — `.card-glass` class for frosted glass panels
- **Status badges** — Color-coded for each workflow state (green/blue/amber/red/purple)
- **Animations** — `animate-fade-in-up` for chat bubbles, `typing-dot` for AI typing indicator
- **Inter font** — Loaded from Google Fonts for clean typography
- **Custom scrollbar** — Slim 6px with subtle track

## API Client

The typed API client at `src/api/client.ts` provides methods for all endpoints:

```typescript
import { dashboardApi, newslettersApi, chatApi, leadsApi } from './api/client'

// Dashboard
const metrics = await dashboardApi.getMetrics()
const activity = await dashboardApi.getActivity(50)

// Newsletters
const editions = await newslettersApi.list()
const detail = await newslettersApi.get(editionId)
await newslettersApi.trigger('March 2026 Newsletter')

// Chat
const response = await chatApi.send('What were last month's highlights?')

// Leads
const config = await leadsApi.getConfig()
const stats = await leadsApi.getStats()
```

## Environment

The frontend communicates with the backend through Vite's dev proxy (see `vite.config.ts`). In production (Docker/Helm), nginx handles the proxy — see the [Dockerfile](Dockerfile).
