/** Shared TypeScript types for the frontend. */

export interface DashboardMetrics {
    total_editions: number
    active_cycles: number
    completed_editions: number
    pending_responses: number
    total_leads: number
    avg_turnaround_days: number | null
    emails_sent: number
    emails_received: number
    questions_answered: number
    hours_saved: number
    dollar_value_saved: number
}

export interface ActivityItem {
    id: string
    edition_id: string | null
    edition_title: string | null
    action: string
    actor: string
    detail: string | null
    timestamp: string
}

export interface NewsletterSummary {
    id: string
    title: string
    status: string
    created_at: string
    updated_at: string
    sent_at: string | null
    attempt_count: number
    submission_count: number
    approved_count: number
}

export interface SubmissionDetail {
    id: string
    lead_email: string
    lead_name: string
    programme: string
    workstream: string
    status: string
    raw_content: string | null
    reworded_content: string | null
    reminder_count: number
    created_at: string
}

export interface NewsletterDetail extends NewsletterSummary {
    html_content: string | null
    anuj_feedback: string | null
    submissions: SubmissionDetail[]
}

export interface ChatMessage {
    role: 'user' | 'assistant'
    content: string
    sources?: ChatSource[]
    timestamp?: string
}

export interface ChatSource {
    edition: string
    section: string
    score: number
}

export interface LeadStats {
    lead_email: string
    lead_name: string
    programme: string
    workstream: string
    total_submissions: number
    approved_count: number
    avg_response_hours: number | null
}

export interface TeamsConfig {
    programmes: Programme[]
}

export interface Programme {
    name: string
    workstreams: Workstream[]
}

export interface Workstream {
    name: string
    lead_name: string
    lead_email: string
}
