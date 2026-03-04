/** API client for communicating with the backend. */

const API_BASE = '/api'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${url}`, {
        headers: { 'Content-Type': 'application/json', ...options?.headers },
        ...options,
    })
    if (!res.ok) {
        const error = await res.text()
        throw new Error(`API error ${res.status}: ${error}`)
    }
    return res.json()
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

import type {
    ActivityItem,
    ChatMessage,
    DashboardMetrics,
    LeadStats,
    NewsletterDetail,
    NewsletterSummary,
    TeamsConfig,
} from '../types'

export const dashboardApi = {
    getMetrics: () => fetchJSON<DashboardMetrics>('/dashboard/metrics'),
    getActivity: (limit = 50) => fetchJSON<ActivityItem[]>(`/dashboard/activity?limit=${limit}`),
}

// ── Newsletters ───────────────────────────────────────────────────────────────

export const newslettersApi = {
    list: (skip = 0, limit = 20, status?: string) => {
        let url = `/newsletters?skip=${skip}&limit=${limit}`
        if (status) url += `&status=${status}`
        return fetchJSON<NewsletterSummary[]>(url)
    },
    get: (id: string) => fetchJSON<NewsletterDetail>(`/newsletters/${id}`),
    trigger: (title?: string) =>
        fetchJSON<{ edition_id: string; message: string }>('/newsletters/trigger', {
            method: 'POST',
            body: JSON.stringify({ title: title || '' }),
        }),
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export const chatApi = {
    send: (question: string, sessionId?: string) =>
        fetchJSON<{ session_id: string; answer: string; sources: any[] }>('/chat', {
            method: 'POST',
            body: JSON.stringify({ question, session_id: sessionId }),
        }),
    getHistory: (sessionId: string) =>
        fetchJSON<ChatMessage[]>(`/chat/history/${sessionId}`),
}

// ── Leads ─────────────────────────────────────────────────────────────────────

export const leadsApi = {
    getConfig: () => fetchJSON<TeamsConfig>('/leads/config'),
    updateConfig: (config: TeamsConfig) =>
        fetchJSON<{ message: string }>('/leads/config', {
            method: 'PUT',
            body: JSON.stringify(config),
        }),
    getStats: () => fetchJSON<LeadStats[]>('/leads/stats'),
}

// ── Portal (magic-link, no auth) ──────────────────────────────────────────────

export interface PortalTokenInfo {
    actor_name: string
    actor_email: string
    role: string
    action_type: string
    context: { programme?: string; workstream?: string; edition_title?: string; section_html?: string }
    reworded_content?: string | null
    edition_title?: string | null
}

export const portalApi = {
    getTokenInfo: (token: string) =>
        fetchJSON<PortalTokenInfo>(`/portal/token/${token}`),

    submit: (token: string, rawContent: string) =>
        fetchJSON<{ reworded_content: string; submission_id: string }>('/portal/submit', {
            method: 'POST',
            body: JSON.stringify({ token, raw_content: rawContent }),
        }),

    approve: (token: string, finalContent: string) =>
        fetchJSON<{ status: string; message: string }>('/portal/approve', {
            method: 'POST',
            body: JSON.stringify({ token, final_content: finalContent }),
        }),

    feedback: (token: string, feedbackText: string) =>
        fetchJSON<{ status: string; message: string }>('/portal/feedback', {
            method: 'POST',
            body: JSON.stringify({ token, feedback_text: feedbackText }),
        }),

    // Note: /portal/chat uses SSE streaming — handled directly in the portal pages
}
