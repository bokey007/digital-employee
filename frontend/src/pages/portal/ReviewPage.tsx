import React, { useEffect, useState, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'

// ── Types ─────────────────────────────────────────────────────────────────────
interface TokenInfo {
    actor_name: string
    actor_email: string
    role: string
    context: { edition_title: string; programme?: string; section_html?: string }
    previous_submission: string | null
}

interface ChatMessage {
    role: 'user' | 'assistant'
    content: string
}

type Phase = 'loading' | 'invalid' | 'review' | 'feedback' | 'approved'

// ── API helpers ───────────────────────────────────────────────────────────────
const API = import.meta.env.VITE_API_URL || ''

async function getTokenInfo(token: string): Promise<TokenInfo> {
    const res = await fetch(`${API}/api/portal/token/${token}`)
    if (!res.ok) throw new Error('Invalid or expired link')
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

async function sendFeedback(token: string, feedbackText: string) {
    const res = await fetch(`${API}/api/portal/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, feedback_text: feedbackText }),
    })
    if (!res.ok) throw new Error('Feedback submission failed')
    return res.json()
}

async function streamChat(
    token: string,
    userMessage: string,
    currentHtml: string,
    onToken: (t: string) => void
): Promise<void> {
    const res = await fetch(`${API}/api/portal/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, user_message: userMessage, current_html: currentHtml }),
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
                } catch {/* ignore */ }
            }
        }
    }
}

// ── Role label helper ─────────────────────────────────────────────────────────
function getRoleLabel(role: string): string {
    return {
        programme_lead: 'Programme Lead',
        ashwin: 'Senior Reviewer',
        anuj: 'Delivery Leader',
    }[role] || 'Reviewer'
}

// ── Chip prompts for reviewers ────────────────────────────────────────────────
const CHIP_PROMPTS = [
    'Summarise the key points',
    'Make the intro more impactful',
    'Sharpen the Quality section',
    'Reduce length by 20%',
    'Highlight wins more clearly',
]

// ── Component ─────────────────────────────────────────────────────────────────
export default function ReviewPage() {
    const [searchParams] = useSearchParams()
    const token = searchParams.get('token') || ''

    const [phase, setPhase] = useState<Phase>('loading')
    const [info, setInfo] = useState<TokenInfo | null>(null)
    const [currentHtml, setCurrentHtml] = useState('')
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [inputValue, setInputValue] = useState('')
    const [aiTyping, setAiTyping] = useState(false)
    const [feedbackText, setFeedbackText] = useState('')
    const [submittingFeedback, setSubmittingFeedback] = useState(false)
    const [approving, setApproving] = useState(false)
    const [error, setError] = useState('')
    const [showPrevious, setShowPrevious] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (!token) { setPhase('invalid'); return }
        getTokenInfo(token)
            .then(data => {
                setInfo(data)
                const html = data.context?.section_html || ''
                setCurrentHtml(html)
                setPhase('review')
            })
            .catch(() => setPhase('invalid'))
    }, [token])

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, aiTyping])

    const firstName = info?.actor_name?.split(' ')[0] || 'there'

    // ── Chat ──
    const sendMessage = async (message: string) => {
        if (!message.trim() || aiTyping) return
        setMessages(prev => [...prev, { role: 'user', content: message }])
        setInputValue('')
        setAiTyping(true)

        let aiContent = ''
        setMessages(prev => [...prev, { role: 'assistant', content: '' }])

        try {
            await streamChat(token, message, currentHtml, (t) => {
                aiContent += t

                // Parse [DRAFT]...[/DRAFT] delimiter:
                // - Show only conversational text in the chat bubble
                // - Silently extract HTML and update the live preview
                const draftStart = aiContent.indexOf('[DRAFT]')
                const draftEnd = aiContent.indexOf('[/DRAFT]')

                let chatText: string
                if (draftStart !== -1) {
                    chatText = aiContent.slice(0, draftStart).trim()
                    if (draftEnd !== -1) {
                        const draftHtml = aiContent.slice(draftStart + 7, draftEnd).trim()
                        if (draftHtml) setCurrentHtml(draftHtml)
                    }
                } else {
                    chatText = aiContent
                }

                setMessages(prev => {
                    const updated = [...prev]
                    updated[updated.length - 1] = { role: 'assistant', content: chatText || '✏️ Updating the section…' }
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

    // ── Approve ──
    const handleApprove = async () => {
        setApproving(true)
        setError('')
        try {
            await approveContent(token, currentHtml)
            setPhase('approved')
        } catch {
            setError('Approval failed. Please try again.')
            setApproving(false)
        }
    }

    // ── Feedback ──
    const handleSubmitFeedback = async () => {
        if (!feedbackText.trim()) return
        setSubmittingFeedback(true)
        try {
            await sendFeedback(token, feedbackText)
            setPhase('approved')
        } catch {
            setError('Feedback submission failed. Please try again.')
            setSubmittingFeedback(false)
        }
    }

    // ── Shared header ──
    const PortalHeader = () => (
        <div style={{
            background: 'linear-gradient(135deg, #08312A 0%, #0a4035 100%)',
            padding: '20px 32px',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            borderBottom: '2px solid #00E47C',
        }}>
            <div style={{
                width: 44, height: 44, borderRadius: '50%',
                background: '#00E47C', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 22,
            }}>🤖</div>
            <div>
                <div style={{ color: '#00E47C', fontWeight: 700, fontSize: 17, fontFamily: 'Calibri, sans-serif' }}>
                    BI Digital Employee
                </div>
                <div style={{ color: 'rgba(255,255,255,0.65)', fontSize: 12, fontFamily: 'Calibri, sans-serif' }}>
                    Review Portal • {info?.context?.edition_title || ''}
                    {info?.role && (
                        <span style={{ marginLeft: 8, background: 'rgba(0,228,124,0.15)', color: '#00E47C', padding: '2px 8px', borderRadius: 10, fontSize: 11 }}>
                            {getRoleLabel(info.role)}
                        </span>
                    )}
                </div>
            </div>
        </div>
    )

    // ── PHASE: Loading ──
    if (phase === 'loading') return (
        <div style={fullPageStyle}>
            <PortalHeader />
            <div style={centerStyle}>
                <div style={spinnerStyle}></div>
                <p style={{ color: 'rgba(255,255,255,0.5)', fontFamily: 'Calibri, sans-serif', marginTop: 16 }}>
                    Loading your review portal…
                </p>
            </div>
            <style>{spinAnimation}</style>
        </div>
    )

    // ── PHASE: Invalid ──
    if (phase === 'invalid') return (
        <div style={fullPageStyle}>
            <PortalHeader />
            <div style={centerStyle}>
                <div style={{ fontSize: 56 }}>⏱️</div>
                <h2 style={{ color: '#fff', margin: '16px 0 8px', fontFamily: 'Calibri, sans-serif' }}>Link Expired or Invalid</h2>
                <p style={{ color: 'rgba(255,255,255,0.55)', fontFamily: 'Calibri, sans-serif', textAlign: 'center', maxWidth: 400 }}>
                    This review link may have expired or already been used. Please check your email for the latest link.
                </p>
            </div>
        </div>
    )

    // ── PHASE: Approved (covers both approve + feedback submitted) ──
    if (phase === 'approved') return (
        <div style={fullPageStyle}>
            <PortalHeader />
            <div style={centerStyle}>
                <div style={{ fontSize: 72 }}>✅</div>
                <h2 style={{ color: '#00E47C', margin: '16px 0 8px', fontFamily: 'Calibri, sans-serif', fontSize: 28 }}>
                    Thank you, {firstName}!
                </h2>
                <p style={{ color: 'rgba(255,255,255,0.7)', fontFamily: 'Calibri, sans-serif', textAlign: 'center', maxWidth: 460, fontSize: 15 }}>
                    Your decision has been recorded for the{' '}
                    <strong style={{ color: '#00E47C' }}>{info?.context?.edition_title}</strong>.
                    The Digital Employee will automatically route the newsletter to the next step.
                </p>
                <div style={{ marginTop: 24, padding: '14px 28px', background: 'rgba(0,228,124,0.08)', borderRadius: 8, border: '1px solid #00E47C30' }}>
                    <span style={{ color: 'rgba(255,255,255,0.55)', fontFamily: 'Calibri, sans-serif', fontSize: 13 }}>
                        You can safely close this window.
                    </span>
                </div>
            </div>
        </div>
    )

    // ── PHASE: Review (main split view) ──
    return (
        <div style={fullPageStyle}>
            <PortalHeader />
            <div style={{ display: 'flex', height: 'calc(100vh - 86px)' }}>

                {/* Left: Newsletter Preview */}
                <div style={{
                    flex: 1, overflowY: 'auto', padding: '24px',
                    borderRight: '1px solid rgba(255,255,255,0.08)',
                }}>
                    {/* Action bar */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
                        <h3 style={{ color: '#00E47C', margin: 0, fontFamily: 'Calibri, sans-serif', fontSize: 16 }}>
                            📰 {info?.context?.programme ? `${info.context.programme} Section` : `${info?.context?.edition_title}`}
                        </h3>
                        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                            {/* Previous month toggle — any role with prior data */}
                            {info?.previous_submission && (
                                <button
                                    onClick={() => setShowPrevious(!showPrevious)}
                                    style={{ background: 'rgba(0,228,124,0.08)', border: '1px solid #00E47C30', color: '#00E47C', borderRadius: 6, padding: '7px 14px', fontFamily: 'Calibri, sans-serif', fontSize: 12, cursor: 'pointer' }}
                                >
                                    📅 {showPrevious ? 'Hide Previous Month' : 'Show Previous Month'}
                                </button>
                            )}
                            {/* Request Changes button removed — all reviewers use the AI chat to refine */}
                            <button
                                id="approve-btn"
                                onClick={handleApprove}
                                disabled={approving}
                                style={{
                                    background: approving ? '#333' : '#00E47C',
                                    color: approving ? '#888' : '#08312A',
                                    border: 'none', borderRadius: 6, padding: '9px 18px',
                                    fontWeight: 700, fontFamily: 'Calibri, sans-serif',
                                    cursor: approving ? 'not-allowed' : 'pointer',
                                    fontSize: 13, transition: 'all 0.2s',
                                }}
                            >
                                {approving ? 'Saving…' : '✅ Approve & Forward'}
                            </button>
                        </div>
                    </div>

                    {error && <p style={{ color: '#ff6b6b', fontFamily: 'Calibri, sans-serif', fontSize: 13, marginBottom: 12 }}>{error}</p>}

                    {/* Newsletter content — rendered HTML with scoped styles */}
                    <style>{`
                        .newsletter-content h3 {
                            font-size: 17px; font-weight: 700; color: #08312A;
                            margin: 22px 0 6px; padding-bottom: 4px;
                            border-bottom: 2px solid #00E47C;
                        }
                        .newsletter-content h4 {
                            font-size: 14px; font-weight: 700; color: #08312A;
                            margin: 16px 0 4px;
                        }
                        .newsletter-content p {
                            margin: 0 0 10px; color: #333; line-height: 1.75;
                        }
                        .newsletter-content ul {
                            margin: 4px 0 12px 0; padding-left: 22px;
                        }
                        .newsletter-content li {
                            margin-bottom: 5px; color: #333; line-height: 1.65;
                        }
                        .newsletter-content strong {
                            color: #08312A;
                        }
                        .newsletter-content table {
                            width: 100%; border-collapse: collapse; margin: 12px 0;
                        }
                        .newsletter-content th {
                            background: #08312A; color: #00E47C; padding: 8px 12px;
                            text-align: left; font-size: 12px; letter-spacing: 0.5px;
                        }
                        .newsletter-content td {
                            padding: 8px 12px; border-bottom: 1px solid #e5e7eb;
                            font-size: 13px; color: #333;
                        }
                        .newsletter-content tr:nth-child(even) td {
                            background: #f9fafb;
                        }
                        .newsletter-content section, .newsletter-content .workstream-section {
                            margin-bottom: 20px;
                        }
                    `}</style>

                    {/* Content + optional Previous Month side-by-side */}
                    <div style={{ display: 'flex', gap: 16 }}>
                        <div
                            id="newsletter-preview"
                            className="newsletter-content"
                            style={{
                                flex: 1, background: '#fff', borderRadius: 8, padding: '28px 32px', color: '#333',
                                fontFamily: 'Calibri, sans-serif', fontSize: 14, lineHeight: 1.75,
                                boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
                            }}
                            dangerouslySetInnerHTML={{ __html: currentHtml || '<p style="color:#999;">Newsletter content loading…</p>' }}
                        />

                        {/* Previous month reference panel */}
                        {showPrevious && info?.previous_submission && (
                            <div style={{ width: 320, flexShrink: 0, background: 'rgba(0,228,124,0.04)', border: '1px solid #00E47C20', borderRadius: 8, padding: '18px', overflowY: 'auto', maxHeight: 'calc(100vh - 180px)' }}>
                                <p style={{ color: '#00E47C', fontFamily: 'Calibri, sans-serif', fontSize: 12, fontWeight: 700, margin: '0 0 10px' }}>📅 Last Month's Approved Section</p>
                                <p style={{ color: 'rgba(255,255,255,0.4)', fontFamily: 'Calibri, sans-serif', fontSize: 11, margin: '0 0 14px', lineHeight: 1.5 }}>For reference only — use the chat to refine this month's version.</p>
                                <div
                                    className="newsletter-content"
                                    style={{ background: '#fff', borderRadius: 6, padding: '16px 20px', fontSize: 13 }}
                                    dangerouslySetInnerHTML={{ __html: info.previous_submission }}
                                />
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: AI Chat Panel */}
                <div style={{ width: 380, display: 'flex', flexDirection: 'column', background: '#071f1a' }}>
                    <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                        <p style={{ color: 'rgba(255,255,255,0.85)', margin: 0, fontFamily: 'Calibri, sans-serif', fontSize: 13, lineHeight: 1.6 }}>
                            🤖 Hi {firstName}! Ask me to revise any section of the newsletter and I'll update it instantly.
                        </p>
                    </div>

                    {/* Chip prompts */}
                    <div style={{ padding: '12px 16px', display: 'flex', flexWrap: 'wrap', gap: 6, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                        {CHIP_PROMPTS.map(chip => (
                            <button
                                key={chip}
                                onClick={() => sendMessage(chip)}
                                style={{
                                    background: 'rgba(0,228,124,0.08)', border: '1px solid #00E47C40',
                                    color: '#00E47C', borderRadius: 20, padding: '4px 12px',
                                    fontFamily: 'Calibri, sans-serif', fontSize: 12, cursor: 'pointer',
                                    transition: 'all 0.2s',
                                }}
                            >
                                {chip}
                            </button>
                        ))}
                    </div>

                    {/* Messages */}
                    <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
                        {messages.length === 0 && (
                            <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.3)', fontSize: 13, fontFamily: 'Calibri, sans-serif', marginTop: 32 }}>
                                Use the chat to refine any section, or approve above…
                            </div>
                        )}
                        {messages.map((msg, i) => (
                            <div key={i} style={{
                                marginBottom: 12,
                                display: 'flex',
                                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                            }}>
                                <div style={{
                                    maxWidth: '85%', padding: '10px 14px',
                                    background: msg.role === 'user' ? '#00E47C' : 'rgba(255,255,255,0.07)',
                                    color: msg.role === 'user' ? '#08312A' : '#e8e8e8',
                                    fontFamily: 'Calibri, sans-serif', fontSize: 13, lineHeight: 1.6,
                                    borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                                }}>
                                    {msg.content}
                                </div>
                            </div>
                        ))}
                        {aiTyping && (
                            <div style={{ display: 'flex', gap: 6, padding: '6px 0' }}>
                                {[0, 1, 2].map(i => (
                                    <div key={i} style={{
                                        width: 7, height: 7, borderRadius: '50%', background: '#00E47C',
                                        animation: `bounce 1s ${i * 0.15}s infinite`,
                                    }} />
                                ))}
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input */}
                    <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', gap: 8, alignItems: 'flex-end' }}>
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
                            placeholder="Ask me to revise… (Shift+Enter for new line)"
                            rows={3}
                            style={{
                                flex: 1, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: 8, padding: '10px 14px', color: '#fff',
                                fontFamily: 'Calibri, sans-serif', fontSize: 13, outline: 'none',
                                resize: 'none', lineHeight: '1.5', minHeight: 72, maxHeight: 180,
                                overflowY: 'auto',
                            }}
                        />
                        <button
                            onClick={() => sendMessage(inputValue)}
                            disabled={!inputValue.trim() || aiTyping}
                            style={{
                                background: inputValue.trim() && !aiTyping ? '#00E47C' : '#1a3530',
                                color: inputValue.trim() && !aiTyping ? '#08312A' : '#444',
                                border: 'none', borderRadius: 8, width: 40, cursor: 'pointer',
                                fontWeight: 700, fontSize: 18, transition: 'all 0.2s',
                                height: 40, flexShrink: 0,
                            }}
                        >
                            ↑
                        </button>
                    </div>

                </div>
            </div>

            {/* ── Feedback overlay ── */}
            {phase === 'feedback' && (
                <div style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
                }}>
                    <div style={{
                        background: '#0a2820', border: '1px solid rgba(255,255,255,0.12)',
                        borderRadius: 12, padding: '32px', width: 520, maxWidth: '90vw',
                    }}>
                        <h3 style={{ color: '#fff', margin: '0 0 8px', fontFamily: 'Calibri, sans-serif' }}>✏️ Request Changes</h3>
                        <p style={{ color: 'rgba(255,255,255,0.6)', fontFamily: 'Calibri, sans-serif', fontSize: 13, margin: '0 0 16px' }}>
                            Describe the changes you'd like made, or paste your edited version below.
                        </p>
                        <textarea
                            id="feedback-textarea"
                            value={feedbackText}
                            onChange={e => setFeedbackText(e.target.value)}
                            placeholder="e.g. Please shorten the D&A section, and fix the typo in paragraph 2…"
                            style={{
                                width: '100%', minHeight: 160, padding: '12px 14px',
                                background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)',
                                borderRadius: 8, color: '#fff', fontFamily: 'Calibri, sans-serif',
                                fontSize: 13, lineHeight: 1.7, resize: 'vertical', outline: 'none',
                                boxSizing: 'border-box',
                            }}
                        />
                        {error && <p style={{ color: '#ff6b6b', fontSize: 13, fontFamily: 'Calibri, sans-serif', marginTop: 8 }}>{error}</p>}
                        <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
                            <button
                                onClick={() => { setPhase('review'); setError('') }}
                                style={{
                                    background: 'transparent', color: 'rgba(255,255,255,0.6)',
                                    border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6,
                                    padding: '9px 18px', fontFamily: 'Calibri, sans-serif',
                                    cursor: 'pointer', fontSize: 13,
                                }}
                            >
                                Cancel
                            </button>
                            <button
                                id="submit-feedback-btn"
                                onClick={handleSubmitFeedback}
                                disabled={!feedbackText.trim() || submittingFeedback}
                                style={{
                                    background: feedbackText.trim() && !submittingFeedback ? '#ff8080' : '#333',
                                    color: feedbackText.trim() && !submittingFeedback ? '#fff' : '#666',
                                    border: 'none', borderRadius: 6, padding: '9px 20px',
                                    fontWeight: 700, fontFamily: 'Calibri, sans-serif',
                                    cursor: feedbackText.trim() && !submittingFeedback ? 'pointer' : 'not-allowed',
                                    fontSize: 13,
                                }}
                            >
                                {submittingFeedback ? 'Submitting…' : 'Submit Feedback'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <style>{`
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
        </div>
    )
}

// ── Shared styles ──────────────────────────────────────────────────────────────
const fullPageStyle: React.CSSProperties = {
    minHeight: '100vh',
    background: 'linear-gradient(180deg, #051a16 0%, #061f19 100%)',
    fontFamily: 'Calibri, sans-serif',
}

const centerStyle: React.CSSProperties = {
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    minHeight: 'calc(100vh - 88px)', padding: 32,
}

const spinnerStyle: React.CSSProperties = {
    width: 40, height: 40, borderRadius: '50%',
    border: '3px solid rgba(0,228,124,0.15)',
    borderTop: '3px solid #00E47C',
    animation: 'spin 0.8s linear infinite',
}

const spinAnimation = `@keyframes spin { to { transform: rotate(360deg); } }`
