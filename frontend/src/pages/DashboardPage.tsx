import React, { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import apiClient from '@/services/api'
import { GenerationJob } from '@/types'
import {
  Sparkles,
  Video,
  History,
  Shield,
  Layers,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Play
} from 'lucide-react'

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate()
  const { user, isAdmin } = useAuthStore()
  const [jobs, setJobs] = useState<GenerationJob[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchRecentJobs = async () => {
      try {
        const response = await apiClient.get('/generations')
        setJobs(response.data || [])
      } catch {
        setJobs([])
      } finally {
        setLoading(false)
      }
    }
    fetchRecentJobs()
  }, [])

  const completedCount = jobs.filter((j) => j.status === 'COMPLETED').length
  const activeCount = jobs.filter((j) => j.status === 'PROCESSING' || j.status === 'QUEUED').length

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden bg-gradient-to-r from-indigo-950/80 via-purple-950/60 to-slate-900 border border-indigo-800/50 rounded-3xl p-6 sm:p-8 shadow-xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-900/60 border border-indigo-700/60 text-indigo-300 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              <span>Studio Workspace</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Welcome back, {user?.first_name || user?.username}!
            </h1>
            <p className="text-slate-300 text-xs sm:text-sm leading-relaxed">
              Create and manage AI video renders with powerful multi-model generation engines.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => navigate('/dashboard/videos')}
              className="px-6 py-3 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white font-bold rounded-xl text-sm transition shadow-lg shadow-indigo-600/25 flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4" />
              <span>Launch Video Studio</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl flex items-center justify-between shadow-sm">
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Generations</p>
            <p className="text-2xl font-bold text-white mt-1">{jobs.length}</p>
          </div>
          <div className="w-11 h-11 rounded-xl bg-indigo-950/80 border border-indigo-800/60 flex items-center justify-center text-indigo-400">
            <Video className="w-5 h-5" />
          </div>
        </div>

        <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl flex items-center justify-between shadow-sm">
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Completed Videos</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">{completedCount}</p>
          </div>
          <div className="w-11 h-11 rounded-xl bg-emerald-950/80 border border-emerald-800/60 flex items-center justify-center text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="p-5 bg-slate-900/80 border border-slate-800 rounded-2xl flex items-center justify-between shadow-sm">
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Active Queue</p>
            <p className="text-2xl font-bold text-indigo-300 mt-1">{activeCount}</p>
          </div>
          <div className="w-11 h-11 rounded-xl bg-purple-950/80 border border-purple-800/60 flex items-center justify-center text-purple-400">
            <Clock className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div
          onClick={() => navigate('/dashboard/videos')}
          className="p-6 bg-slate-900/80 border border-slate-800 rounded-2xl hover:border-indigo-500/50 transition cursor-pointer group shadow-lg"
        >
          <div className="w-10 h-10 rounded-xl bg-indigo-950/80 border border-indigo-800/60 flex items-center justify-center text-indigo-400 mb-4 group-hover:scale-105 transition-transform">
            <Sparkles className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-white mb-1 flex items-center justify-between">
            <span>Video Studio</span>
            <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-indigo-400 group-hover:translate-x-1 transition" />
          </h3>
          <p className="text-xs text-slate-400 leading-relaxed">
            Prompt, parameterize, and render AI videos using dynamically discovered inference models.
          </p>
        </div>

        <div
          onClick={() => navigate('/history')}
          className="p-6 bg-slate-900/80 border border-slate-800 rounded-2xl hover:border-indigo-500/50 transition cursor-pointer group shadow-lg"
        >
          <div className="w-10 h-10 rounded-xl bg-purple-950/80 border border-purple-800/60 flex items-center justify-center text-purple-400 mb-4 group-hover:scale-105 transition-transform">
            <History className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-white mb-1 flex items-center justify-between">
            <span>Generation History</span>
            <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-purple-400 group-hover:translate-x-1 transition" />
          </h3>
          <p className="text-xs text-slate-400 leading-relaxed">
            Search, preview, and download your previous video creations and prompts.
          </p>
        </div>

        {isAdmin() ? (
          <div
            onClick={() => navigate('/admin')}
            className="p-6 bg-slate-900/80 border border-slate-800 rounded-2xl hover:border-indigo-500/50 transition cursor-pointer group shadow-lg"
          >
            <div className="w-10 h-10 rounded-xl bg-pink-950/80 border border-pink-800/60 flex items-center justify-center text-pink-400 mb-4 group-hover:scale-105 transition-transform">
              <Shield className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white mb-1 flex items-center justify-between">
              <span>Admin Center</span>
              <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-pink-400 group-hover:translate-x-1 transition" />
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Manage platform users, roles, password resets, and inspect system health.
            </p>
          </div>
        ) : (
          <div
            onClick={() => navigate('/profile')}
            className="p-6 bg-slate-900/80 border border-slate-800 rounded-2xl hover:border-indigo-500/50 transition cursor-pointer group shadow-lg"
          >
            <div className="w-10 h-10 rounded-xl bg-pink-950/80 border border-pink-800/60 flex items-center justify-center text-pink-400 mb-4 group-hover:scale-105 transition-transform">
              <Layers className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-white mb-1 flex items-center justify-between">
              <span>Account & Roles</span>
              <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-pink-400 group-hover:translate-x-1 transition" />
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Check your account status, assigned permissions, and platform settings.
            </p>
          </div>
        )}
      </div>

      {/* Recent Generations List */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">Recent Activity</h2>
            <p className="text-xs text-slate-400">Your latest video generation submissions</p>
          </div>
          <Link
            to="/history"
            className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {loading ? (
          <div className="py-12 text-center text-slate-500 text-xs animate-pulse">Loading recent generations...</div>
        ) : jobs.length === 0 ? (
          <div className="py-12 text-center space-y-3 bg-slate-950/40 rounded-2xl border border-dashed border-slate-800">
            <Video className="w-8 h-8 text-slate-600 mx-auto" />
            <p className="text-sm font-semibold text-slate-300">No video generations yet</p>
            <p className="text-xs text-slate-500">Your generated videos will appear here once submitted.</p>
            <button
              onClick={() => navigate('/dashboard/videos')}
              className="mt-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition inline-flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Create First Video</span>
            </button>
          </div>
        ) : (
          <div className="divide-y divide-slate-800/80">
            {jobs.slice(0, 5).map((job) => (
              <div key={job.id} className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-white truncate">{job.prompt}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    <span className="text-slate-300 font-mono">{job.model_type}</span> · {new Date(job.created_at).toLocaleString()}
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold inline-flex items-center gap-1.5 ${
                      job.status === 'COMPLETED'
                        ? 'bg-emerald-950/60 border border-emerald-800/60 text-emerald-300'
                        : job.status === 'PROCESSING'
                        ? 'bg-indigo-950/60 border border-indigo-800/60 text-indigo-300 animate-pulse'
                        : job.status === 'FAILED'
                        ? 'bg-rose-950/60 border border-rose-800/60 text-rose-300'
                        : 'bg-slate-800 text-slate-300'
                    }`}
                  >
                    {job.status === 'COMPLETED' && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
                    {job.status === 'FAILED' && <AlertTriangle className="w-3 h-3 text-rose-400" />}
                    <span>{job.status}</span>
                    {job.progress !== null && job.status === 'PROCESSING' && <span>({job.progress}%)</span>}
                  </span>

                  {job.status === 'COMPLETED' && job.output_available && (
                    <button
                      onClick={() => navigate('/history')}
                      className="p-1.5 text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800 rounded-lg transition"
                      title="Play in History"
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default DashboardPage
