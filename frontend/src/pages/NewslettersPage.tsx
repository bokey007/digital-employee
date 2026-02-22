import { useEffect, useState } from 'react'
import { Newspaper, Plus, Eye, RefreshCw, ChevronRight } from 'lucide-react'
import { newslettersApi } from '../api/client'
import type { NewsletterDetail, NewsletterSummary } from '../types'

const STATUS_BADGES: Record<string, { class: string; label: string }> = {
    initiated: { class: 'badge-blue', label: 'Initiated' },
    collecting: { class: 'badge-blue', label: 'Collecting' },
    rewording: { class: 'badge-purple', label: 'Rewording' },
    awaiting_lead_approval: { class: 'badge-yellow', label: 'Awaiting Lead Approval' },
    consolidating: { class: 'badge-purple', label: 'Consolidating' },
    awaiting_anuj_approval: { class: 'badge-yellow', label: 'Awaiting Review' },
    incorporating_feedback: { class: 'badge-yellow', label: 'Revising' },
    sent_to_client: { class: 'badge-green', label: 'Sent to Dist. List' },
    completed: { class: 'badge-green', label: 'Completed' },
    failed: { class: 'badge-red', label: 'Failed' },
}

export default function NewslettersPage() {
    const [editions, setEditions] = useState<NewsletterSummary[]>([])
    const [selected, setSelected] = useState<NewsletterDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const [triggering, setTriggering] = useState(false)
    const [showPreview, setShowPreview] = useState(false)

    const loadEditions = () => {
        setLoading(true)
        newslettersApi
            .list()
            .then(setEditions)
            .catch(console.error)
            .finally(() => setLoading(false))
    }

    useEffect(() => { loadEditions() }, [])

    const handleTrigger = async () => {
        setTriggering(true)
        try {
            await newslettersApi.trigger()
            loadEditions()
        } catch (err) {
            console.error(err)
        } finally {
            setTriggering(false)
        }
    }

    const handleSelect = async (id: string) => {
        try {
            const detail = await newslettersApi.get(id)
            setSelected(detail)
        } catch (err) {
            console.error(err)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <RefreshCw className="h-6 w-6 animate-spin text-brand-500" />
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold text-gray-800">Newsletter Editions</h3>
                    <p className="text-sm text-gray-500">{editions.length} editions</p>
                </div>
                <button onClick={handleTrigger} disabled={triggering} className="btn-primary flex items-center gap-2">
                    {triggering ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                    New Cycle
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Edition List */}
                <div className="lg:col-span-1 space-y-2">
                    {editions.map((ed) => {
                        const badge = STATUS_BADGES[ed.status] || STATUS_BADGES.initiated
                        return (
                            <button
                                key={ed.id}
                                onClick={() => handleSelect(ed.id)}
                                className={`w-full text-left card p-4 transition-all ${selected?.id === ed.id ? 'ring-2 ring-brand-500 shadow-md' : ''
                                    }`}
                            >
                                <div className="flex items-start justify-between">
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-gray-800 truncate">{ed.title}</p>
                                        <p className="text-xs text-gray-400 mt-1">
                                            {new Date(ed.created_at).toLocaleDateString()}
                                        </p>
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-gray-300 flex-shrink-0 mt-1" />
                                </div>
                                <div className="flex items-center gap-2 mt-2">
                                    <span className={`badge ${badge.class}`}>{badge.label}</span>
                                    <span className="text-xs text-gray-400">
                                        {ed.approved_count}/{ed.submission_count} approved
                                    </span>
                                </div>
                            </button>
                        )
                    })}
                    {editions.length === 0 && (
                        <div className="card p-10 text-center">
                            <Newspaper className="h-10 w-10 text-gray-300 mx-auto mb-3" />
                            <p className="text-sm text-gray-500">No newsletters yet</p>
                            <p className="text-xs text-gray-400 mt-1">Click "New Cycle" to start one</p>
                        </div>
                    )}
                </div>

                {/* Detail Panel */}
                <div className="lg:col-span-2">
                    {selected ? (
                        <div className="card">
                            <div className="p-5 border-b border-gray-100 flex items-center justify-between">
                                <div>
                                    <h4 className="font-semibold text-gray-800">{selected.title}</h4>
                                    <p className="text-xs text-gray-500 mt-1">
                                        Created {new Date(selected.created_at).toLocaleString()}
                                        {selected.sent_at && ` • Sent ${new Date(selected.sent_at).toLocaleString()}`}
                                    </p>
                                </div>
                                {selected.html_content && (
                                    <button onClick={() => setShowPreview(!showPreview)} className="btn-secondary flex items-center gap-2 text-sm">
                                        <Eye className="h-4 w-4" />
                                        {showPreview ? 'Hide' : 'Preview'}
                                    </button>
                                )}
                            </div>

                            {showPreview && selected.html_content ? (
                                <div className="p-5">
                                    <iframe
                                        srcDoc={selected.html_content}
                                        className="w-full h-[600px] border border-gray-200 rounded-lg"
                                        title="Newsletter Preview"
                                    />
                                </div>
                            ) : (
                                <div className="divide-y divide-gray-50">
                                    {selected.submissions.map((sub) => {
                                        const subBadge = STATUS_BADGES[sub.status] || { class: 'badge-gray', label: sub.status }
                                        return (
                                            <div key={sub.id} className="p-4 hover:bg-gray-50/50">
                                                <div className="flex items-center justify-between">
                                                    <div>
                                                        <p className="text-sm font-medium text-gray-800">{sub.lead_name}</p>
                                                        <p className="text-xs text-gray-500">{sub.programme} → {sub.workstream}</p>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        {sub.reminder_count > 0 && (
                                                            <span className="text-xs text-amber-600">{sub.reminder_count} reminder(s)</span>
                                                        )}
                                                        <span className={`badge ${subBadge.class}`}>{subBadge.label}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        )
                                    })}
                                    {selected.anuj_feedback && (
                                        <div className="p-4 bg-amber-50/50">
                                            <p className="text-xs font-medium text-amber-700 mb-1">Anuj's Feedback</p>
                                            <p className="text-sm text-amber-900">{selected.anuj_feedback}</p>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="card p-16 text-center">
                            <Newspaper className="h-12 w-12 text-gray-200 mx-auto mb-3" />
                            <p className="text-gray-400">Select an edition to view details</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
