import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import apiClient from '../services/api'
import { GenerationJob } from '../types'
import {
  Sparkles,
  Video,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Shield,
  History,
  Cpu
} from 'lucide-react'

export const DashboardPage: React.FC = () => {
  const { user, isAdmin } = useAuthStore()
  const [recentJobs, setRecentJobs] = useState<GenerationJob[]>([])
  const [loadingJobs, setLoadingJobs] = useState(true)

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const response = await apiClient.get('/generations')
        setRecentJobs(response.data || [])
      } catch {
        setRecentJobs([])
      } finally {
        setLoadingJobs(false)
      }
    }
    fetchJobs()
  }, [])

  const totalCount = recentJobs.length
  const completedCount = recentJobs.filter((j) => j.status === 'COMPLETED').length
  const processingCount = recentJobs.filter((j) => j.status === 'PROCESSING' || j.status === 'QUEUED').length
  const failedCount = recentJobs.filter((j) => j.status === 'FAILED').length

  return (
    <div className="space-y-8">
      {/* Welcome Hero Card */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-indigo-950/80 via-purple-950/50 to-slate-900 border border-indigo-800/40 p-8 sm:p-10 shadow-2xl backdrop-blur-xl">
        <div className="relative z-10 max-w-2xl space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-900/50 border border-indigo-700/60 rounded-full text-indigo-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>GenVid.AI Studio Workspace</span>
          </div>

          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Welcome back, {user?.first_name || user?.username}!
          </h1>

          <p className="text-slate-300 text-sm leading-relaxed">
            Create, manage, and explore high-fidelity AI video generations powered by multi-model GPU inference.
          </p>

          <div className="pt-2 flex flex-wrap gap-3">
            <Link
              to="/dashboard/videos"
              className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-xl text-sm transition-all duration-200 shadow-lg shadow-indigo-600/25 flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4" />
              <span>Create New Video</span>
              <ArrowRight className="w-4 h-4" />
            </Link>

            <Link
              to="/history"
              className="px-5 py-3 bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 text-slate-200 font-semibold rounded-xl text-sm transition flex items-center gap-2"
            >
              <History className="w-4 h-4 text-slate-400" />
              <span>View History</span>
            </Link>

            {isAdmin() && (
              <Link
                to="/admin"
                className="px-5 py-3 bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 text-purple-300 font-semibold rounded-xl text-sm transition flex items-center gap-2"
              >
                <Shield className="w-4 h-4 text-purple-400" />
                <span>Admin Panel</span>
              </Link>
            )}
          </div>
        </div>

        {/* Decorative Graphic Element */}
        <div className="absolute right-[-40px] top-[-40px] w-80 h-80 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none"></div>
      </div>

      {/* Metrics & Statistics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-2">
          <div className="flex justify-between items-center text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Generations</span>
            <Video className="w-4 h-4 text-indigo-400" />
          </div>
          <p className="text-3xl font-extrabold text-white">{totalCount}</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-2">
          <div className="flex justify-between items-center text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Completed</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-3xl font-extrabold text-emerald-400">{completedCount}</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-2">
          <div className="flex justify-between items-center text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Processing / Queued</span>
            <Clock className="w-4 h-4 text-blue-400" />
          </div>
          <p className="text-3xl font-extrabold text-blue-400">{processingCount}</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-2">
          <div className="flex justify-between items-center text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Failed</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-3xl font-extrabold text-slate-400">{failedCount}</p>
        </div>
      </div>

      {/* Feature Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 space-y-4 hover:border-slate-700 transition flex flex-col justify-between">
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-950/80 border border-indigo-800/60 flex items-center justify-center text-indigo-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-bold text-white">AI Video Studio</h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Launch the studio workspace to prompt multi-model AI engines, adjust inference steps, and render MP4 videos.
            </p>
          </div>
          <Link
            to="/dashboard/videos"
            className="w-full py-2.5 px-4 bg-slate-800 hover:bg-indigo-600 border border-slate-700 text-slate-200 hover:text-white font-semibold rounded-xl text-xs transition text-center block"
          >
            Open Studio Workspace &rarr;
          </Link>
        </div>

        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 space-y-4 hover:border-slate-700 transition flex flex-col justify-between">
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-xl bg-purple-950/80 border border-purple-800/60 flex items-center justify-center text-purple-400">
              <Cpu className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-bold text-white">Engine & Dynamic Discovery</h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              GenVid.AI connects directly to the underlying Wan2GP engine to query model availability and GPU hardware status.
            </p>
          </div>
          <Link
            to="/profile"
            className="w-full py-2.5 px-4 bg-slate-800 hover:bg-purple-600 border border-slate-700 text-slate-200 hover:text-white font-semibold rounded-xl text-xs transition text-center block"
          >
            View Account & Permissions &rarr;
          </Link>
        </div>
      </div>

      {/* Recent Generations Showcase */}
      <div className="bg-slate-900/90 rounded-2xl p-6 sm:p-8 border border-slate-800/90 shadow-xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">Recent Generations</h2>
            <p className="text-slate-400 text-xs mt-0.5">Your latest video generation tasks</p>
          </div>
          <Link to="/history" className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition">
            View All History &rarr;
          </Link>
        </div>

        {loadingJobs ? (
          <div className="text-center py-10 text-slate-400 text-xs animate-pulse">Loading recent video tasks...</div>
        ) : recentJobs.length === 0 ? (
          <div className="text-center py-12 text-slate-500 space-y-3">
            <p className="text-sm">No videos generated yet.</p>
            <Link
              to="/dashboard/videos"
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl text-xs transition"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Create your first video</span>
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {recentJobs.slice(0, 4).map((job) => (
              <div
                key={job.id}
                className="p-4 bg-slate-800/50 border border-slate-800 hover:border-slate-700 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition"
              >
                <div className="space-y-1 min-w-0">
                  <p className="text-sm font-semibold text-white truncate">{job.prompt}</p>
                  <div className="flex items-center gap-3 text-xs text-slate-400">
                    <span className="font-mono bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-indigo-300">
                      {job.model_type}
                    </span>
                    <span>•</span>
                    <span>{new Date(job.created_at).toLocaleString()}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-semibold border ${
                      job.status === 'COMPLETED'
                        ? 'bg-emerald-950/60 border-emerald-800/60 text-emerald-300'
                        : job.status === 'PROCESSING'
                        ? 'bg-blue-950/60 border-blue-800/60 text-blue-300 animate-pulse'
                        : job.status === 'FAILED'
                        ? 'bg-rose-950/60 border-rose-800/60 text-rose-300'
                        : 'bg-amber-950/60 border-amber-800/60 text-amber-300'
                    }`}
                  >
                    {job.status}
                  </span>
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
