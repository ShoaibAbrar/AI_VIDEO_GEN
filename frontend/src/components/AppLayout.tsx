import React, { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { HealthStatus } from './HealthStatus'
import { ToastContainer } from './ToastContainer'
import {
  Video,
  LayoutDashboard,
  Sparkles,
  History,
  User,
  Shield,
  LogOut,
  Menu,
  X,
  ChevronRight,
  PlusCircle
} from 'lucide-react'

interface AppLayoutProps {
  children: React.ReactNode
  title?: string
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children, title }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout, isAdmin } = useAuthStore()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const navItems = [
    { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { label: 'Create Video', path: '/dashboard/videos', icon: Sparkles, highlight: true },
    { label: 'My History', path: '/history', icon: History },
    { label: 'Profile', path: '/profile', icon: User },
  ]

  if (isAdmin()) {
    navItems.push({ label: 'Admin Center', path: '/admin', icon: Shield })
  }

  const isActive = (path: string) => {
    if (path === '/dashboard' && location.pathname === '/dashboard') return true
    if (path !== '/dashboard' && location.pathname.startsWith(path)) return true
    return false
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col md:flex-row antialiased selection:bg-indigo-500 selection:text-white">
      <ToastContainer />

      {/* Desktop Sidebar */}
      <aside className="hidden md:flex flex-col w-64 bg-slate-900/90 border-r border-slate-800/80 sticky top-0 h-screen z-40 shrink-0 backdrop-blur-xl">
        {/* Brand Header */}
        <div className="p-6 border-b border-slate-800/80 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-600 to-pink-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/25 shrink-0">
            <Video className="w-5 h-5 stroke-[2.5]" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-tight leading-none flex items-center gap-1">
              GenVid<span className="text-indigo-400 font-black">.AI</span>
            </h1>
            <p className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider mt-1">AI Video Studio</p>
          </div>
        </div>

        {/* Quick Action Button */}
        <div className="p-4">
          <Link
            to="/dashboard/videos"
            className="w-full py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-xl text-sm transition-all duration-200 shadow-md shadow-indigo-600/20 flex items-center justify-center gap-2 group"
          >
            <PlusCircle className="w-4 h-4 group-hover:rotate-90 transition-transform duration-300" />
            <span>Create Video</span>
          </Link>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = isActive(item.path)
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  active
                    ? 'bg-indigo-600/15 text-indigo-300 border border-indigo-500/30 font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${active ? 'text-indigo-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {active && <ChevronRight className="w-4 h-4 text-indigo-400" />}
              </Link>
            )
          })}
        </nav>

        {/* User Card & Logout */}
        <div className="p-4 border-t border-slate-800/80 bg-slate-900/40">
          <div className="flex items-center justify-between gap-3 p-2 rounded-xl bg-slate-800/50 border border-slate-800">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white font-bold text-xs shrink-0 shadow-sm">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white truncate">{user?.username}</p>
                <p className="text-[10px] text-slate-400 truncate">{user?.email}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              title="Sign Out"
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 rounded-lg transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Wrapper */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        {/* Top Header Bar */}
        <header className="bg-slate-900/80 backdrop-blur-md border-b border-slate-800/80 sticky top-0 z-30 px-4 sm:px-8 py-3.5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            {/* Mobile menu trigger */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            {/* Mobile Logo */}
            <div className="md:hidden flex items-center gap-2" onClick={() => navigate('/dashboard')}>
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white">
                <Video className="w-4 h-4" />
              </div>
              <span className="font-bold text-white text-base">GenVid.AI</span>
            </div>

            {/* Breadcrumb Title */}
            <h2 className="hidden md:block text-base font-bold text-white tracking-tight">
              {title || 'GenVid.AI Studio'}
            </h2>
          </div>

          <div className="flex items-center gap-4">
            <HealthStatus />
            <div className="hidden sm:block h-5 w-px bg-slate-800"></div>

            {/* User Profile Badge Link */}
            <Link
              to="/profile"
              className="hidden sm:flex items-center gap-2 hover:opacity-80 transition cursor-pointer"
            >
              <div className="w-7 h-7 rounded-full bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-300 font-semibold text-xs">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </div>
              <span className="text-xs font-semibold text-slate-200">{user?.username}</span>
            </Link>
          </div>
        </header>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-slate-900 border-b border-slate-800 px-4 py-4 space-y-2 animate-fadeIn">
            {navItems.map((item) => {
              const Icon = item.icon
              const active = isActive(item.path)
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center justify-between px-4 py-3 rounded-xl text-sm font-medium ${
                    active ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className="w-5 h-5" />
                    <span>{item.label}</span>
                  </div>
                  {active && <ChevronRight className="w-4 h-4" />}
                </Link>
              )
            })}
            <div className="pt-3 border-t border-slate-800 flex justify-between items-center px-2">
              <span className="text-xs text-slate-400">Signed in as {user?.username}</span>
              <button
                onClick={handleLogout}
                className="px-3 py-1.5 bg-rose-950/50 text-rose-300 rounded-lg text-xs font-semibold border border-rose-800/60"
              >
                Sign Out
              </button>
            </div>
          </div>
        )}

        {/* Page Main Content Area */}
        <main className="flex-1 px-4 sm:px-8 py-8 max-w-7xl w-full mx-auto space-y-8">{children}</main>

        {/* Footer */}
        <footer className="border-t border-slate-900 bg-slate-950 px-6 py-6 text-center text-xs text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-4 max-w-7xl w-full mx-auto">
          <div>
            <span className="font-semibold text-slate-400">GenVid.AI</span> &copy; {new Date().getFullYear()} — AI Video Generation, Reimagined.
          </div>
          <div className="flex items-center gap-4 text-slate-500">
            <span>Powered by Wan2GP Generation Engine</span>
          </div>
        </footer>
      </div>
    </div>
  )
}
