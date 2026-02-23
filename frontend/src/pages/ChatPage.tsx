import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Sparkles, RefreshCw } from 'lucide-react'
import { chatApi } from '../api/client'
import type { ChatMessage, ChatSource } from '../types'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function ChatPage() {
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [sessionId, setSessionId] = useState<string | null>(null)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    const handleSend = async () => {
        const q = input.trim()
        if (!q || loading) return
        setInput('')

        const userMsg: ChatMessage = { role: 'user', content: q }
        setMessages((prev) => [...prev, userMsg])
        setLoading(true)

        try {
            const res = await chatApi.send(q, sessionId || undefined)
            setSessionId(res.session_id)
            const assistantMsg: ChatMessage = {
                role: 'assistant',
                content: res.answer,
                sources: res.sources,
            }
            setMessages((prev) => [...prev, assistantMsg])
        } catch (err) {
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' },
            ])
        } finally {
            setLoading(false)
        }
    }

    const handleNewChat = () => {
        setMessages([])
        setSessionId(null)
    }

    return (
        <div className="flex flex-col h-[calc(100vh-8rem)]">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700">
                        <Sparkles className="h-5 w-5 text-white" />
                    </div>
                    <div>
                        <h3 className="text-base font-semibold text-gray-800">Newsletter Assistant</h3>
                        <p className="text-xs text-gray-500">Ask questions about current and past newsletters</p>
                    </div>
                </div>
                <button onClick={handleNewChat} className="btn-secondary text-sm flex items-center gap-1.5">
                    <RefreshCw className="h-3.5 w-3.5" />
                    New Chat
                </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto rounded-xl bg-white border border-gray-200 p-4 space-y-4">
                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-gray-400">
                        <Bot className="h-16 w-16 mb-4 text-gray-200" />
                        <p className="text-lg font-medium text-gray-300">Start a conversation</p>
                        <p className="text-sm mt-1">Ask about Key Highlights, Delivery Updates, or any newsletter content</p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-6 w-full max-w-md">
                            {[
                                'What were the key highlights last month?',
                                'Show me delivery updates for Data & Analytics',
                                'Any innovations reported across programmes?',
                                'Summarise the latest newsletter',
                            ].map((q) => (
                                <button
                                    key={q}
                                    onClick={() => { setInput(q); }}
                                    className="text-left text-xs p-3 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors"
                                >
                                    {q}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} className={`flex gap-3 animate-fade-in-up ${msg.role === 'user' ? 'justify-end' : ''}`}>
                        {msg.role === 'assistant' && (
                            <div className="flex-shrink-0 h-8 w-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
                                <Bot className="h-4 w-4 text-white" />
                            </div>
                        )}
                        <div
                            className={`max-w-[75%] rounded-2xl px-4 py-3 ${msg.role === 'user'
                                ? 'bg-brand-700 text-white rounded-br-md'
                                : 'bg-gray-100 text-gray-800 rounded-bl-md'
                                }`}
                        >
                            {msg.role === 'user' ? (
                                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                            ) : (
                                <div className="text-sm prose prose-sm max-w-none 
                                    prose-p:my-1 prose-ul:my-1 prose-li:my-0.5 
                                    prose-headings:text-brand-900 prose-headings:my-2
                                    prose-strong:text-brand-800">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {msg.content}
                                    </ReactMarkdown>
                                </div>
                            )}
                            {msg.sources && msg.sources.length > 0 && (
                                <div className="mt-2 pt-2 border-t border-gray-200/50">
                                    <p className="text-[10px] uppercase tracking-wide text-gray-500 mb-1">Sources</p>
                                    {msg.sources.map((s: ChatSource, j: number) => (
                                        <span key={j} className="inline-block mr-1.5 mb-1 text-[10px] px-1.5 py-0.5 rounded bg-white/60 text-gray-600">
                                            {s.edition} {s.section && `• ${s.section}`}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                        {msg.role === 'user' && (
                            <div className="flex-shrink-0 h-8 w-8 rounded-lg bg-gray-200 flex items-center justify-center">
                                <User className="h-4 w-4 text-gray-600" />
                            </div>
                        )}
                    </div>
                ))}

                {loading && (
                    <div className="flex gap-3 animate-fade-in-up">
                        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
                            <Bot className="h-4 w-4 text-white" />
                        </div>
                        <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
                            <div className="flex gap-1">
                                <span className="h-2 w-2 bg-gray-400 rounded-full typing-dot" />
                                <span className="h-2 w-2 bg-gray-400 rounded-full typing-dot" />
                                <span className="h-2 w-2 bg-gray-400 rounded-full typing-dot" />
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="mt-3 flex gap-2">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Ask about newsletters..."
                    className="flex-1 px-4 py-3 rounded-xl border border-gray-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent placeholder:text-gray-400"
                />
                <button
                    onClick={handleSend}
                    disabled={loading || !input.trim()}
                    className="btn-primary px-4 rounded-xl disabled:opacity-50"
                >
                    <Send className="h-4 w-4" />
                </button>
            </div>
        </div>
    )
}
