import React, { useEffect, useState, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'

// ── Types ─────────────────────────────────────────────────────────────────────
interface TokenInfo {
    actor_name: string
    actor_email: string
    role: string
    context: { programme: string; workstream: string; edition_title: string }
    reworded_content: string | null
    previous_submission: string | null
}

interface ChatMessage {
    role: 'user' | 'assistant'
    content: string
}

type Phase = 'loading' | 'invalid' | 'submit' | 'refine' | 'approved'

// ── Section definition ────────────────────────────────────────────────────────
const SECTIONS = [
    {
        key: 'highlights' as const,
        label: '⭐ Key Highlights',
        placeholder: 'e.g. Completed migration of legacy system. Successfully onboarded 3 new team members…',
        hint: 'Major achievements, milestones reached, wins to celebrate',
    },
    {
        key: 'delivery' as const,
        label: '🚀 Delivery Updates',
        placeholder: 'e.g. Sprint 12 completed on time. UAT underway for Phase 2. 2 blockers resolved…',
        hint: 'Progress on deliverables, deadlines, risks, blockers',
    },
    {
        key: 'innovation' as const,
        label: '💡 Innovation & Value Add',
        placeholder: 'e.g. Piloted AI-assisted reporting — saved ~4hrs/week. Proposed new dashboard framework…',
        hint: 'New ideas, efficiency gains, improvements introduced',
    },
]

// ── Quality Metrics fields ────────────────────────────────────────────────────
const QUALITY_FIELDS = [
    { key: 'lean_projects', label: 'Lean Projects Completed', unit: '', placeholder: 'e.g. 4' },
    { key: 'gb_projects', label: 'GB Projects Completed', unit: '', placeholder: 'e.g. 2' },
    { key: 'lean_trained', label: 'Lean Trained & Tested', unit: '%', placeholder: 'e.g. 78' },
    { key: 'gb_trained', label: 'GB Trained & Tested', unit: '%', placeholder: 'e.g. 65' },
    { key: 'lean_certified', label: 'Lean Certified', unit: '%', placeholder: 'e.g. 52' },
    { key: 'gb_certified', label: 'GB Certified', unit: '%', placeholder: 'e.g. 41' },
] as const

type QualityKey = typeof QUALITY_FIELDS[number]['key']
type QualityContent = Record<QualityKey, string>

type SectionKey = 'highlights' | 'delivery' | 'innovation'
type SectionContent = Record<SectionKey, string>

// ── API helpers ───────────────────────────────────────────────────────────────
const API = import.meta.env.VITE_API_URL || ''

async function getTokenInfo(token: string): Promise<TokenInfo> {
    const res = await fetch(`${API}/api/portal/token/${token}`)
    if (!res.ok) throw new Error('Invalid or expired link')
    return res.json()
}

async function submitContent(token: string, rawContent: string) {
    const res = await fetch(`${API}/api/portal/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, raw_content: rawContent }),
    })
    if (!res.ok) throw new Error('Submission failed')
    return res.json()
}

async function approveContent(token: string, finalContent: string) {
    const res = await fetch(`${API}/api/portal/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, final_content: finalContent }),
    })
    if (!res.ok) throw new Error('Approval failed')
    return res.json()
}

async function streamChat(
    token: string,
    userMessage: string,
    onToken: (t: string) => void
): Promise<void> {
    const res = await fetch(`${API}/api/portal/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, user_message: userMessage }),
    })
    if (!res.ok || !res.body) throw new Error('Chat stream failed')

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = line.slice(6).trim()
                if (data === '[DONE]') return
                try {
                    const parsed = JSON.parse(data)
                    if (parsed.token) onToken(parsed.token)
                } catch { /* ignore */ }
            }
        }
    }
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function SubmitPage() {
    const [searchParams] = useSearchParams()
    const token = searchParams.get('token') || ''

    const [phase, setPhase] = useState<Phase>('loading')
    const [info, setInfo] = useState<TokenInfo | null>(null)
    const [sections, setSections] = useState<SectionContent>({ highlights: '', delivery: '', innovation: '' })
    const [qualityMetrics, setQualityMetrics] = useState<QualityContent>({
        lean_projects: '', gb_projects: '', lean_trained: '', gb_trained: '', lean_certified: '', gb_certified: ''
    })
    const [rewording, setRewording] = useState(false)
    const [rewrordedContent, setRewrordedContent] = useState('')
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [inputValue, setInputValue] = useState('')
    const [aiTyping, setAiTyping] = useState(false)
    const [error, setError] = useState('')
    const [approving, setApproving] = useState(false)
    const [showPrevious, setShowPrevious] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    const CHIP_PROMPTS = [
        'Make it more concise',
        'Make it more formal',
        'Add patient-centric tone',
        'Emphasise innovation more',
        'Shorten by 20%',
    ]

    useEffect(() => {
        if (!token) { setPhase('invalid'); return }
        getTokenInfo(token)
            .then(data => {
                setInfo(data)
                if (data.reworded_content) {
                    setRewrordedContent(data.reworded_content)
                    setPhase('refine')
                } else {
                    setPhase('submit')
                }
            })
            .catch(() => setPhase('invalid'))
    }, [token])

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, aiTyping])

    const firstName = info?.actor_name?.split(' ')[0] || 'there'
    const isQuality = (
        info?.context?.programme?.toLowerCase() === 'quality' ||
        info?.context?.workstream?.toLowerCase() === 'quality metrics'
    )
    const hasAnyContent = isQuality
        ? Object.values(qualityMetrics).some(v => v.trim())
        : Object.values(sections).some(v => v.trim())

    // Combine sections into structured raw text for the LLM
    const buildRawContent = () => {
        if (isQuality) {
            return QUALITY_FIELDS
                .filter(f => qualityMetrics[f.key].trim())
                .map(f => `${f.label}: ${qualityMetrics[f.key].trim()}${f.unit}`)
                .join('\n')
        }
        return SECTIONS
            .map(s => `${s.label.replace(/^[^\w]+/, '')}:\n${sections[s.key]}`)
            .filter(s => !s.endsWith(':\n'))
            .join('\n\n')
    }

    const handleSubmit = async () => {
        if (!hasAnyContent) return
        setRewording(true)
        setError('')
        try {
            const result = await submitContent(token, buildRawContent())
            setRewrordedContent(result.reworded_content)
            setPhase('refine')
        } catch {
            setError('Something went wrong. Please try again.')
        } finally {
            setRewording(false)
        }
    }

    const sendMessage = async (message: string) => {
        if (!message.trim() || aiTyping) return
        setMessages(prev => [...prev, { role: 'user', content: message }])
        setInputValue('')
        setAiTyping(true)
        let aiContent = ''
        setMessages(prev => [...prev, { role: 'assistant', content: '' }])
        try {
            await streamChat(token, message, t => {
                aiContent += t

                // Parse [DRAFT]...[/DRAFT] delimiter:
                // - Show only the conversational text (before [DRAFT]) in the chat bubble
                // - Silently extract the HTML and update the live draft panel
                const draftStart = aiContent.indexOf('[DRAFT]')
                const draftEnd = aiContent.indexOf('[/DRAFT]')

                let chatText: string
                if (draftStart !== -1) {
                    // Conversational text is everything before [DRAFT]
                    chatText = aiContent.slice(0, draftStart).trim()
                    // Once [/DRAFT] is complete, extract and apply the HTML draft
                    if (draftEnd !== -1) {
                        const draftHtml = aiContent.slice(draftStart + 7, draftEnd).trim()
                        if (draftHtml) setRewrordedContent(draftHtml)
                    }
                } else {
                    chatText = aiContent
                }

                setMessages(prev => {
                    const updated = [...prev]
                    updated[updated.length - 1] = { role: 'assistant', content: chatText || '✏️ Updating your draft…' }
                    return updated
                })
            })
        } catch {
            setMessages(prev => {
                const updated = [...prev]
                updated[updated.length - 1] = { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }
                return updated
            })
        } finally {
            setAiTyping(false)
        }
    }

    const handleApprove = async () => {
        setApproving(true)
        try {
            await approveContent(token, rewrordedContent)
            setPhase('approved')
        } catch {
            setError('Approval failed. Please try again.')
            setApproving(false)
        }
    }

    // ── Shared header ──
    const PortalHeader = () => (
        <div style={{ background: 'linear-gradient(135deg, #08312A 0%, #0a4035 100%)', padding: '18px 32px', display: 'flex', alignItems: 'center', gap: 14, borderBottom: '2px solid #00E47C' }}>
            <div style={{ width: 42, height: 42, borderRadius: '50%', background: '#00E47C', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20 }}>🤖</div>
            <div>
                <div style={{ color: '#00E47C', fontWeight: 700, fontSize: 16, fontFamily: 'Calibri, sans-serif' }}>BI Digital Employee</div>
                <div style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12, fontFamily: 'Calibri, sans-serif' }}>
                    Newsletter Submission Portal • {info?.context?.edition_title || ''}
                    {info?.context?.workstream && <span style={{ marginLeft: 8, color: 'rgba(255,255,255,0.4)' }}>| {info.context.workstream}</span>}
                </div>
            </div>
        </div>
    )

    if (phase === 'loading') return (
        <div style={fullPageStyle}>
            <PortalHeader />
            <div style={centerStyle}><div style={spinnerStyle} /><p style={{ color: 'rgba(255,255,255,0.5)', fontFamily: 'Calibri, sans-serif', marginTop: 16 }}>Loading your portal…</p></div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    )

    if (phase === 'invalid') return (
        <div style={fullPageStyle}>
            <PortalHeader />
            <div style={centerStyle}>
                <div style={{ fontSize: 52 }}>⏱️</div>
                <h2 style={{ color: '#fff', margin: '14px 0 8px', fontFamily: 'Calibri, sans-serif' }}>Link Expired or Invalid</h2>
                <p style={{ color: 'rgba(255,255,255,0.55)', fontFamily: 'Calibri, sans-serif', textAlign: 'center', maxWidth: 400, lineHeight: 1.6 }}>
                    This link may have expired or already been used. Please check your email for a fresh link.
                </p>
            </div>
        </div>
    )

    if (phase === 'approved') return (
        <div style={fullPageStyle}>
            <PortalHeader />
            <div style={centerStyle}>
                <div style={{ fontSize: 68 }}>🎉</div>
                <h2 style={{ color: '#00E47C', margin: '14px 0 8px', fontFamily: 'Calibri, sans-serif', fontSize: 26 }}>Approved! Thank you, {firstName}.</h2>
                <p style={{ color: 'rgba(255,255,255,0.7)', fontFamily: 'Calibri, sans-serif', textAlign: 'center', maxWidth: 460, fontSize: 14, lineHeight: 1.6 }}>
                    Your content for <strong style={{ color: '#00E47C' }}>{info?.context?.workstream}</strong> has been submitted for the <strong style={{ color: '#00E47C' }}>{info?.context?.edition_title}</strong> newsletter. The programme team will be notified automatically.
                </p>
                <div style={{ marginTop: 20, padding: '12px 24px', background: 'rgba(0,228,124,0.07)', borderRadius: 8, border: '1px solid #00E47C25' }}>
                    <span style={{ color: 'rgba(255,255,255,0.5)', fontFamily: 'Calibri, sans-serif', fontSize: 13 }}>You can safely close this window.</span>
                </div>
            </div>
        </div>
    )

    // ── PHASE: Submit (3-section form) ──
    if (phase === 'submit') return (
        <div style={fullPageStyle}>
            <PortalHeader />
            <div style={{ display: 'flex', height: 'calc(100vh - 82px)' }}>

                {/* Main form */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px' }}>
                    <h2 style={{ color: '#00E47C', margin: '0 0 4px', fontFamily: 'Calibri, sans-serif', fontSize: 22 }}>Hi {firstName} 👋</h2>
                    <p style={{ color: 'rgba(255,255,255,0.7)', margin: '0 0 24px', fontFamily: 'Calibri, sans-serif', fontSize: 14, lineHeight: 1.6 }}>
                        {isQuality ? (
                            <>Submit the latest <strong style={{ color: '#fff' }}>Quality Metrics</strong> for <strong style={{ color: '#fff' }}>{info?.context?.programme}</strong>. The AI will format them into a professional dashboard-style newsletter section.</>
                        ) : (
                            <>Share your updates for <strong style={{ color: '#fff' }}>{info?.context?.workstream}</strong> under <strong style={{ color: '#fff' }}>{info?.context?.programme}</strong>. Fill in as many sections as are relevant — the AI will professionally reword and structure them for the newsletter.</>
                        )}
                    </p>

                    {/* Form: Quality Metrics or Standard 3-section */}
                    {isQuality ? (
                        /* ── Quality Metrics: 6 numeric fields ── */
                        <div>
                            <p style={{ color: 'rgba(255,255,255,0.55)', margin: '0 0 20px', fontFamily: 'Calibri, sans-serif', fontSize: 13, lineHeight: 1.6 }}>
                                Enter the latest metric values below. Leave a field blank if not applicable this month.
                            </p>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                                {QUALITY_FIELDS.map(field => (
                                    <div key={field.key}>
                                        <label style={{ display: 'block', color: '#00E47C', fontFamily: 'Calibri, sans-serif', fontWeight: 700, fontSize: 13, marginBottom: 6 }}>
                                            {field.label}{field.unit && <span style={{ color: 'rgba(255,255,255,0.35)', fontWeight: 400, marginLeft: 4 }}>({field.unit})</span>}
                                        </label>
                                        <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(255,255,255,0.04)', border: `1px solid ${qualityMetrics[field.key] ? '#00E47C40' : 'rgba(255,255,255,0.12)'}`, borderRadius: 8, overflow: 'hidden', transition: 'border-color 0.2s' }}>
                                            <input
                                                id={`metric-${field.key}`}
                                                type="text"
                                                inputMode="decimal"
                                                value={qualityMetrics[field.key]}
                                                onChange={e => setQualityMetrics(prev => ({ ...prev, [field.key]: e.target.value }))}
                                                placeholder={field.placeholder}
                                                style={{ flex: 1, padding: '11px 14px', background: 'transparent', border: 'none', color: '#fff', fontFamily: 'Calibri, sans-serif', fontSize: 15, outline: 'none' }}
                                            />
                                            {field.unit && (
                                                <span style={{ padding: '0 14px 0 4px', color: '#00E47C', fontFamily: 'Calibri, sans-serif', fontWeight: 700, fontSize: 15 }}>{field.unit}</span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        /* ── Standard 3-section textarea form ── */
                        SECTIONS.map(section => (
                            <div key={section.key} style={{ marginBottom: 20 }}>
                                <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
                                    <label style={{ color: '#00E47C', fontFamily: 'Calibri, sans-serif', fontWeight: 700, fontSize: 14 }}>
                                        {section.label}
                                    </label>
                                    <span style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'Calibri, sans-serif', fontSize: 12 }}>
                                        {section.hint}
                                    </span>
                                </div>
                                <textarea
                                    id={`section-${section.key}`}
                                    value={sections[section.key]}
                                    onChange={e => setSections(prev => ({ ...prev, [section.key]: e.target.value }))}
                                    placeholder={section.placeholder}
                                    rows={4}
                                    style={{
                                        width: '100%', padding: '12px 14px',
                                        background: 'rgba(255,255,255,0.04)', border: `1px solid ${sections[section.key] ? '#00E47C40' : 'rgba(255,255,255,0.12)'}`,
                                        borderRadius: 8, color: '#fff', fontFamily: 'Calibri, sans-serif', fontSize: 13,
                                        lineHeight: 1.7, resize: 'vertical', outline: 'none', boxSizing: 'border-box',
                                        transition: 'border-color 0.2s',
                                    }}
                                />
                            </div>
                        ))
                    )}

                    {error && <p style={{ color: '#ff6b6b', fontFamily: 'Calibri, sans-serif', fontSize: 13, marginBottom: 8 }}>{error}</p>}

                    <button
                        id="submit-btn"
                        onClick={handleSubmit}
                        disabled={!hasAnyContent || rewording}
                        style={btnStyle(!hasAnyContent || rewording)}
                    >
                        {rewording ? '✨ AI is rewording your updates…' : '✨ Submit & Let AI Reword'}
                    </button>
                </div>

                {/* Previous month reference panel */}
                {info?.previous_submission ? (
                    <div style={{ width: 320, borderLeft: '1px solid rgba(255,255,255,0.08)', background: '#071f1a', display: 'flex', flexDirection: 'column' }}>
                        <button
                            onClick={() => setShowPrevious(!showPrevious)}
                            style={{ padding: '14px 18px', background: 'none', border: 'none', borderBottom: '1px solid rgba(255,255,255,0.08)', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                        >
                            <span style={{ color: '#00E47C', fontFamily: 'Calibri, sans-serif', fontWeight: 700, fontSize: 13 }}>📅 Previous Month's Updates</span>
                            <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>{showPrevious ? '▲ Hide' : '▼ Show'}</span>
                        </button>
                        {showPrevious && (
                            <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
                                <p style={{ color: 'rgba(255,255,255,0.45)', fontFamily: 'Calibri, sans-serif', fontSize: 11, margin: '0 0 12px', lineHeight: 1.5 }}>
                                    📖 For reference only — use this to maintain continuity in your updates.
                                </p>
                                <div
                                    style={{ color: 'rgba(255,255,255,0.75)', fontFamily: 'Calibri, sans-serif', fontSize: 12, lineHeight: 1.75 }}
                                    dangerouslySetInnerHTML={{ __html: info.previous_submission }}
                                />
                            </div>
                        )}
                    </div>
                ) : (
                    // Subtle hint when no prior data
                    <div style={{ width: 280, borderLeft: '1px solid rgba(255,255,255,0.06)', background: '#071f1a', padding: '18px 16px' }}>
                        <p style={{ color: '#00E47C', fontFamily: 'Calibri, sans-serif', fontWeight: 700, fontSize: 13, margin: '0 0 8px' }}>📅 Previous Month</p>
                        <p style={{ color: 'rgba(255,255,255,0.3)', fontFamily: 'Calibri, sans-serif', fontSize: 12, lineHeight: 1.6, margin: 0 }}>
                            No previous updates found for <strong style={{ color: 'rgba(255,255,255,0.45)' }}>{info?.context?.workstream}</strong> yet.
                            <br /><br />
                            Once you approve this month's submission, it will appear here next month as a reference for continuity.
                        </p>
                    </div>
                )}
            </div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    )

    // ── PHASE: Refine (AI reworded content + chat) ──
    return (
        <div style={fullPageStyle}>
            <PortalHeader />
            <div style={{ display: 'flex', height: 'calc(100vh - 82px)' }}>

                {/* Left: Live Draft Preview */}
                <div style={{ flex: 1, overflowY: 'auto', padding: '22px 28px', borderRight: '1px solid rgba(255,255,255,0.08)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
                        <h3 style={{ color: '#00E47C', margin: 0, fontFamily: 'Calibri, sans-serif', fontSize: 16 }}>📄 Your Live Draft</h3>
                        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                            {info?.previous_submission && (
                                <button
                                    onClick={() => setShowPrevious(!showPrevious)}
                                    style={{ background: 'rgba(0,228,124,0.08)', border: '1px solid #00E47C30', color: '#00E47C', borderRadius: 6, padding: '7px 14px', fontFamily: 'Calibri, sans-serif', fontSize: 12, cursor: 'pointer' }}
                                >
                                    📅 {showPrevious ? 'Hide Previous' : 'Show Previous Month'}
                                </button>
                            )}
                            <button
                                id="approve-btn"
                                onClick={handleApprove}
                                disabled={approving}
                                style={{ background: approving ? '#333' : '#00E47C', color: approving ? '#888' : '#08312A', border: 'none', borderRadius: 6, padding: '10px 20px', fontWeight: 700, fontFamily: 'Calibri, sans-serif', cursor: approving ? 'not-allowed' : 'pointer', fontSize: 14, transition: 'all 0.2s' }}
                            >
                                {approving ? 'Saving…' : '✅ Approve This Version'}
                            </button>
                        </div>
                    </div>

                    <div style={{ display: 'flex', gap: 16 }}>
                        {/* Reworded content — rendered with proper visual hierarchy */}
                        <div style={{ flex: 1 }}>
                            <style>{`
                                .draft-content h3 {
                                    font-size: 15px; font-weight: 700; color: #00E47C;
                                    margin: 18px 0 5px; padding-bottom: 4px;
                                    border-bottom: 1px solid rgba(0,228,124,0.25);
                                }
                                .draft-content h4 {
                                    font-size: 13px; font-weight: 700; color: #a0f0cc;
                                    margin: 12px 0 3px;
                                }
                                .draft-content p {
                                    margin: 0 0 8px; line-height: 1.75; color: #e8e8e8;
                                }
                                .draft-content ul {
                                    margin: 4px 0 10px 0; padding-left: 20px;
                                }
                                .draft-content li {
                                    margin-bottom: 4px; color: #e0e0e0; line-height: 1.65;
                                }
                                .draft-content strong { color: #fff; }
                                .draft-content table {
                                    width: 100%; border-collapse: collapse; margin: 10px 0;
                                }
                                .draft-content th {
                                    background: rgba(0,228,124,0.12); color: #00E47C;
                                    padding: 7px 12px; text-align: left; font-size: 12px;
                                    border-bottom: 1px solid rgba(0,228,124,0.3);
                                }
                                .draft-content td {
                                    padding: 7px 12px; border-bottom: 1px solid rgba(255,255,255,0.07);
                                    font-size: 13px; color: #e0e0e0;
                                }
                            `}</style>
                            <div
                                className="draft-content"
                                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '20px 24px', fontFamily: 'Calibri, sans-serif', fontSize: 14, lineHeight: 1.75 }}
                                dangerouslySetInnerHTML={{ __html: rewrordedContent }}
                            />
                        </div>

                        {/* Previous month panel (inline in refine phase) */}
                        {showPrevious && info?.previous_submission && (
                            <div style={{ width: 300, background: 'rgba(0,228,124,0.04)', border: '1px solid #00E47C20', borderRadius: 8, padding: '16px', flexShrink: 0 }}>
                                <p style={{ color: '#00E47C', fontFamily: 'Calibri, sans-serif', fontSize: 12, fontWeight: 700, margin: '0 0 10px' }}>📅 Last Month's Approved Content</p>
                                <div
                                    style={{ color: 'rgba(255,255,255,0.6)', fontFamily: 'Calibri, sans-serif', fontSize: 12, lineHeight: 1.7 }}
                                    dangerouslySetInnerHTML={{ __html: info.previous_submission }}
                                />
                            </div>
                        )}
                    </div>
                    {error && <p style={{ color: '#ff6b6b', fontFamily: 'Calibri, sans-serif', fontSize: 13, marginTop: 12 }}>{error}</p>}
                </div>

                {/* Right: Chat Panel */}
                <div style={{ width: 370, display: 'flex', flexDirection: 'column', background: '#071f1a' }}>
                    <div style={{ padding: '14px 18px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                        <p style={{ color: 'rgba(255,255,255,0.85)', margin: 0, fontFamily: 'Calibri, sans-serif', fontSize: 13, lineHeight: 1.6 }}>
                            🤖 Ask me to refine any part of your draft. I'll update it instantly.
                        </p>
                    </div>

                    {/* Chip prompts */}
                    <div style={{ padding: '10px 14px', display: 'flex', flexWrap: 'wrap', gap: 6, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                        {CHIP_PROMPTS.map(chip => (
                            <button key={chip} onClick={() => sendMessage(chip)} style={{ background: 'rgba(0,228,124,0.08)', border: '1px solid #00E47C35', color: '#00E47C', borderRadius: 20, padding: '4px 12px', fontFamily: 'Calibri, sans-serif', fontSize: 12, cursor: 'pointer' }}>
                                {chip}
                            </button>
                        ))}
                    </div>

                    {/* Messages */}
                    <div style={{ flex: 1, overflowY: 'auto', padding: '14px' }}>
                        {messages.length === 0 && (
                            <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.25)', fontSize: 13, fontFamily: 'Calibri, sans-serif', marginTop: 28 }}>Start a conversation to refine…</div>
                        )}
                        {messages.map((msg, i) => (
                            <div key={i} style={{ marginBottom: 10, display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                                <div style={{ maxWidth: '88%', padding: '9px 13px', background: msg.role === 'user' ? '#00E47C' : 'rgba(255,255,255,0.07)', color: msg.role === 'user' ? '#08312A' : '#e8e8e8', fontFamily: 'Calibri, sans-serif', fontSize: 13, lineHeight: 1.6, borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px' }}>
                                    {msg.content}
                                </div>
                            </div>
                        ))}
                        {aiTyping && (
                            <div style={{ display: 'flex', gap: 5, padding: '5px 0' }}>
                                {[0, 1, 2].map(i => <div key={i} style={{ width: 7, height: 7, borderRadius: '50%', background: '#00E47C', animation: `bounce 1s ${i * 0.15}s infinite` }} />)}
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input */}
                    <div style={{ padding: '10px 14px', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                        <textarea
                            id="chat-input"
                            value={inputValue}
                            onChange={e => setInputValue(e.target.value)}
                            onKeyDown={e => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault()
                                    sendMessage(inputValue)
                                }
                            }}
                            onInput={e => {
                                const el = e.currentTarget
                                el.style.height = 'auto'
                                el.style.height = Math.min(el.scrollHeight, 180) + 'px'
                            }}
                            placeholder="Ask me to refine… (Shift+Enter for new line)"
                            rows={3}
                            style={{
                                flex: 1, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: 8, padding: '9px 13px', color: '#fff',
                                fontFamily: 'Calibri, sans-serif', fontSize: 13, outline: 'none',
                                resize: 'none', lineHeight: '1.5', minHeight: 72, maxHeight: 180, overflowY: 'auto',
                            }}
                        />
                        <button
                            onClick={() => sendMessage(inputValue)}
                            disabled={!inputValue.trim() || aiTyping}
                            style={{
                                background: inputValue.trim() && !aiTyping ? '#00E47C' : '#1a3530',
                                color: inputValue.trim() && !aiTyping ? '#08312A' : '#444',
                                border: 'none', borderRadius: 8, width: 38, cursor: 'pointer',
                                fontWeight: 700, fontSize: 18, transition: 'all 0.2s', height: 40, flexShrink: 0,
                            }}
                        >↑</button>
                    </div>
                </div>
            </div>

            <style>{`
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
        </div>
    )
}

// ── Shared styles ──────────────────────────────────────────────────────────────
const fullPageStyle: React.CSSProperties = { minHeight: '100vh', background: 'linear-gradient(180deg, #051a16 0%, #061f19 100%)', fontFamily: 'Calibri, sans-serif' }
const centerStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 82px)', padding: 32 }
const spinnerStyle: React.CSSProperties = { width: 38, height: 38, borderRadius: '50%', border: '3px solid rgba(0,228,124,0.15)', borderTop: '3px solid #00E47C', animation: 'spin 0.8s linear infinite' }
const btnStyle = (disabled: boolean): React.CSSProperties => ({
    width: '100%', padding: '14px', marginTop: 8,
    background: disabled ? '#1a3530' : 'linear-gradient(135deg, #00E47C, #00b860)',
    color: disabled ? '#444' : '#08312A',
    border: 'none', borderRadius: 8, fontFamily: 'Calibri, sans-serif',
    fontWeight: 700, fontSize: 15, cursor: disabled ? 'not-allowed' : 'pointer', transition: 'all 0.2s',
})
