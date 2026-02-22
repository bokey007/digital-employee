import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import {
    LayoutDashboard,
    Newspaper,
    MessageSquare,
    Users,
    Menu,
    X,
} from 'lucide-react'
import { useState } from 'react'
import DashboardPage from './pages/DashboardPage'
import NewslettersPage from './pages/NewslettersPage'
import ChatPage from './pages/ChatPage'
import LeadsPage from './pages/LeadsPage'

const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/newsletters', icon: Newspaper, label: 'Newsletters' },
    { to: '/chat', icon: MessageSquare, label: 'Chat' },
    { to: '/leads', icon: Users, label: 'Leads' },
]

export default function App() {
    const [sidebarOpen, setSidebarOpen] = useState(false)
    const location = useLocation()

    return (
        <div className="flex h-screen overflow-hidden bg-gray-50">
            {/* Sidebar */}
            <aside
                className={`fixed inset-y-0 left-0 z-50 w-64 transform bg-gradient-to-b from-brand-950 via-brand-800 to-brand-950 transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'
                    }`}
            >
                {/* Logo */}
                <div className="flex h-16 items-center gap-3 px-6 border-b border-white/10">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/20 backdrop-blur">
                        <Newspaper className="h-5 w-5 text-brand-400" />
                    </div>
                    <div>
                        <h1 className="text-sm font-bold text-white tracking-tight">Digital Employee</h1>
                        <p className="text-[10px] text-brand-300/80 uppercase tracking-widest">Boehringer Ingelheim</p>
                    </div>
                    <button
                        onClick={() => setSidebarOpen(false)}
                        className="ml-auto lg:hidden text-white/60 hover:text-white"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>

                {/* Nav */}
                <nav className="mt-6 px-3 space-y-1">
                    {navItems.map(({ to, icon: Icon, label }) => (
                        <NavLink
                            key={to}
                            to={to}
                            end={to === '/'}
                            onClick={() => setSidebarOpen(false)}
                            className={({ isActive }) =>
                                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${isActive
                                    ? 'bg-brand-500/15 text-brand-300 shadow-sm'
                                    : 'text-brand-200/60 hover:bg-white/5 hover:text-white'
                                }`
                            }
                        >
                            <Icon className="h-4.5 w-4.5 flex-shrink-0" />
                            {label}
                        </NavLink>
                    ))}
                </nav>

                {/* Bottom */}
                <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-white/10">
                    <div className="flex items-center gap-3 px-2">
                        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center">
                            <span className="text-xs font-bold text-white">AI</span>
                        </div>
                        <div>
                            <p className="text-xs font-medium text-white">AI Employee</p>
                            <p className="text-[10px] text-brand-400 flex items-center gap-1">
                                <span className="h-1.5 w-1.5 rounded-full bg-brand-400 animate-pulse" />
                                Active
                            </p>
                        </div>
                    </div>
                </div>
            </aside>

            {/* Overlay */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/50 lg:hidden"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Main */}
            <div className="flex flex-1 flex-col overflow-hidden">
                {/* Header */}
                <header className="flex h-16 items-center gap-4 border-b border-gray-200 bg-white px-6">
                    <button
                        onClick={() => setSidebarOpen(true)}
                        className="lg:hidden text-gray-500 hover:text-gray-700"
                    >
                        <Menu className="h-5 w-5" />
                    </button>
                    <h2 className="text-lg font-semibold text-gray-800">
                        {navItems.find((n) => n.to === location.pathname)?.label || 'Dashboard'}
                    </h2>
                    <div className="ml-auto hidden sm:flex items-center gap-2">
                        <span className="text-xs text-gray-400">Powered by</span>
                        <span className="text-xs font-semibold text-brand-700">Boehringer Ingelheim AI</span>
                    </div>
                </header>

                {/* Content */}
                <main className="flex-1 overflow-y-auto p-6">
                    <Routes>
                        <Route path="/" element={<DashboardPage />} />
                        <Route path="/newsletters" element={<NewslettersPage />} />
                        <Route path="/chat" element={<ChatPage />} />
                        <Route path="/leads" element={<LeadsPage />} />
                    </Routes>
                </main>
            </div>
        </div>
    )
}
