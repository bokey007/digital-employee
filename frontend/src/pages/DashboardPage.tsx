import { useEffect, useState } from 'react'
import {
    Newspaper,
    Activity,
    Users,
    Clock,
    TrendingUp,
    AlertCircle,
    CheckCircle2,
    Mail,
    RefreshCw,
    Send,
} from 'lucide-react'
import { dashboardApi } from '../api/client'
import type { ActivityItem, DashboardMetrics } from '../types'

const ACTION_ICONS: Record<string, typeof Activity> = {
    cycle_started: Newspaper,
    request_sent: Mail,
    response_received: Mail,
    content_reworded: RefreshCw,
    approval_requested: Send,
    lead_approved: CheckCircle2,
    lead_changes_requested: AlertCircle,
    newsletter_consolidated: Newspaper,
    sent_to_anuj: Send,
    anuj_approved: CheckCircle2,
    anuj_feedback: AlertCircle,
    feedback_incorporated: RefreshCw,
    sent_to_client: Send,
    reminder_sent: Clock,
    error: AlertCircle,
}

const ACTION_COLORS: Record<string, string> = {
    cycle_started: 'text-brand-600 bg-brand-50',
    lead_approved: 'text-emerald-500 bg-emerald-50',
    anuj_approved: 'text-emerald-600 bg-emerald-50',
    sent_to_client: 'text-brand-700 bg-brand-50',
    error: 'text-red-500 bg-red-50',
    reminder_sent: 'text-amber-500 bg-amber-50',
    email_reply: 'text-brand-600 bg-brand-50',
}

export default function DashboardPage() {
    const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
    const [activity, setActivity] = useState<ActivityItem[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        Promise.all([dashboardApi.getMetrics(), dashboardApi.getActivity(30)])
            .then(([m, a]) => {
                setMetrics(m)
                setActivity(a)
            })
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <RefreshCw className="h-6 w-6 animate-spin text-brand-500" />
            </div>
        )
    }

    const cards = metrics
        ? [
            { label: 'Total Editions', value: metrics.total_editions, icon: Newspaper, color: 'brand' },
            { label: 'Active Cycles', value: metrics.active_cycles, icon: Activity, color: 'amber' },
            { label: 'Completed', value: metrics.completed_editions, icon: CheckCircle2, color: 'emerald' },
            { label: 'Pending Responses', value: metrics.pending_responses, icon: Clock, color: 'red' },
            { label: 'Total Leads', value: metrics.total_leads, icon: Users, color: 'purple' },
            {
                label: 'Avg Turnaround',
                value: metrics.avg_turnaround_days ? `${metrics.avg_turnaround_days}d` : '—',
                icon: TrendingUp,
                color: 'teal',
            },
        ]
        : []

    return (
        <div className="space-y-6">
            {/* Metrics Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {cards.map((card) => (
                    <div key={card.label} className="card p-5">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-500 font-medium">{card.label}</p>
                                <p className="mt-1 text-2xl font-bold text-gray-900">{card.value}</p>
                            </div>
                            <div className={`p-3 rounded-xl bg-${card.color}-50`}>
                                <card.icon className={`h-5 w-5 text-${card.color}-500`} />
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Activity Feed */}
            <div className="card">
                <div className="p-5 border-b border-gray-100">
                    <h3 className="text-base font-semibold text-gray-800">Recent Activity</h3>
                    <p className="text-sm text-gray-500">Actions taken by the AI employee</p>
                </div>
                <div className="divide-y divide-gray-50 max-h-[500px] overflow-y-auto">
                    {activity.map((item) => {
                        const Icon = ACTION_ICONS[item.action] || Activity
                        const colorClass = ACTION_COLORS[item.action] || 'text-gray-500 bg-gray-50'
                        return (
                            <div key={item.id} className="flex items-start gap-3 px-5 py-3 hover:bg-gray-50/50 transition-colors">
                                <div className={`mt-0.5 p-1.5 rounded-lg ${colorClass}`}>
                                    <Icon className="h-3.5 w-3.5" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm text-gray-800">
                                        <span className="font-medium">{item.action.replace(/_/g, ' ')}</span>
                                        {item.edition_title && (
                                            <span className="text-gray-500"> • {item.edition_title}</span>
                                        )}
                                    </p>
                                    {item.detail && <p className="text-xs text-gray-500 mt-0.5 truncate">{item.detail}</p>}
                                </div>
                                <time className="text-xs text-gray-400 whitespace-nowrap">
                                    {new Date(item.timestamp).toLocaleString()}
                                </time>
                            </div>
                        )
                    })}
                    {activity.length === 0 && (
                        <div className="px-5 py-10 text-center text-gray-400 text-sm">No activity yet</div>
                    )}
                </div>
            </div>
        </div>
    )
}
