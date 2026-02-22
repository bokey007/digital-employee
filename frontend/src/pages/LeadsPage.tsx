import { useEffect, useState } from 'react'
import { Users, Building2, Network, RefreshCw, Mail, CheckCircle2 } from 'lucide-react'
import { leadsApi } from '../api/client'
import type { LeadStats, TeamsConfig } from '../types'

export default function LeadsPage() {
    const [config, setConfig] = useState<TeamsConfig | null>(null)
    const [stats, setStats] = useState<LeadStats[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        Promise.all([leadsApi.getConfig(), leadsApi.getStats()])
            .then(([c, s]) => { setConfig(c); setStats(s); })
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

    const totalLeads = config?.programmes.reduce(
        (sum, p) => sum + (p.workstreams?.length || 0), 0
    ) || 0

    return (
        <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="card p-5 flex items-center gap-4">
                    <div className="p-3 rounded-xl bg-brand-50">
                        <Building2 className="h-5 w-5 text-brand-600" />
                    </div>
                    <div>
                        <p className="text-2xl font-bold text-gray-900">{config?.programmes.length || 0}</p>
                        <p className="text-sm text-gray-500">Programmes</p>
                    </div>
                </div>
                <div className="card p-5 flex items-center gap-4">
                    <div className="p-3 rounded-xl bg-brand-100">
                        <Network className="h-5 w-5 text-brand-700" />
                    </div>
                    <div>
                        <p className="text-2xl font-bold text-gray-900">{totalLeads}</p>
                        <p className="text-sm text-gray-500">Sub-Workstreams</p>
                    </div>
                </div>
                <div className="card p-5 flex items-center gap-4">
                    <div className="p-3 rounded-xl bg-emerald-50">
                        <Users className="h-5 w-5 text-emerald-500" />
                    </div>
                    <div>
                        <p className="text-2xl font-bold text-gray-900">{totalLeads}</p>
                        <p className="text-sm text-gray-500">Leads</p>
                    </div>
                </div>
            </div>

            {/* Programme / Workstream Tree */}
            <div className="card">
                <div className="p-5 border-b border-gray-100">
                    <h3 className="text-base font-semibold text-gray-800">Team Structure</h3>
                    <p className="text-sm text-gray-500">Programmes, workstreams, and assigned leads</p>
                </div>
                <div className="divide-y divide-gray-50">
                    {config?.programmes.map((prog, i) => (
                        <div key={i} className="p-5">
                            <div className="flex items-center gap-2 mb-3">
                                <Building2 className="h-4 w-4 text-brand-600" />
                                <h4 className="font-semibold text-gray-800">{prog.name}</h4>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 ml-6">
                                {prog.workstreams?.map((ws: any, j: number) => {
                                    const stat = stats.find(
                                        (s) => s.lead_email === ws.lead_email && s.workstream === ws.name
                                    )
                                    return (
                                        <div key={j} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50/80 border border-gray-100">
                                            <div className="flex-1">
                                                <p className="text-sm font-medium text-gray-700">{ws.name}</p>
                                                <div className="flex items-center gap-1.5 mt-1">
                                                    <Users className="h-3 w-3 text-gray-400" />
                                                    <span className="text-xs text-gray-500">{ws.lead_name}</span>
                                                </div>
                                                <div className="flex items-center gap-1.5 mt-0.5">
                                                    <Mail className="h-3 w-3 text-gray-400" />
                                                    <span className="text-xs text-gray-400">{ws.lead_email}</span>
                                                </div>
                                            </div>
                                            {stat && (
                                                <div className="text-right">
                                                    <div className="flex items-center gap-1 text-xs text-emerald-600">
                                                        <CheckCircle2 className="h-3 w-3" />
                                                        {stat.approved_count}/{stat.total_submissions}
                                                    </div>
                                                    <p className="text-[10px] text-gray-400 mt-0.5">approved</p>
                                                </div>
                                            )}
                                        </div>
                                    )
                                })}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
