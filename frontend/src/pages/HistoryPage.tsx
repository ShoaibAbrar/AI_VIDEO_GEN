import React, { useEffect, useRef, useState } from 'react'
import apiClient from '../services/api'
import { GenerationJob } from '../types'
import {
  History,
  Search,
  Download,
  RefreshCw
} from 'lucide-react'

export const HistoryPage: React.FC = () => {
  const [jobs, setJobs] = useState<GenerationJob[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [videoUrls, setVideoUrls] = useState<Record<string, string>>({})
  const videoUrlsRef = useRef<Record<string, string>>({})

  const fetchJobs = async () => {
    try {
      const response = await apiClient.get('/generations')
      setJobs(response.data || [])
    } catch {
      setJobs([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchJobs()
  }, [])

  useEffect(() => {
    let disposed = false
    const loadVideos = async () => {
      for (const job of jobs.filter((item) => item.status === 'COMPLETED' && item.output_available)) {
        if (videoUrls[job.id]) continue
        try {
          const response = await apiClient.get(`/generations/${job.id}/video`, { responseType: 'blob' })
          if (!disposed) {
            const url = URL.createObjectURL(response.data)
            videoUrlsRef.current = { ...videoUrlsRef.current, [job.id]: url }
            setVideoUrls(videoUrlsRef.current)
          }
        } catch {
          // Ignore individual fetch failure
        }
      }
    }
    loadVideos()
    return () => {
      disposed = true
    }
  }, [jobs, videoUrls])

  useEffect(() => () => Object.values(videoUrlsRef.current).forEach((url) => URL.revokeObjectURL(url)), [])

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      job.prompt.toLowerCase().includes(searchQuery.toLowerCase()) ||
      job.model_type.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = statusFilter === 'ALL' || job.status === statusFilter
    return matchesSearch && matchesStatus
  })

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
            <History className="w-6 h-6 text-indigo-400" />
            <span>Generation History</span>
          </h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Review and download all your past AI-generated video outputs.
          </p>
        </div>

        <button
          onClick={fetchJobs}
          className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-slate-300 hover:text-white text-xs font-semibold flex items-center gap-2 self-start sm:self-auto transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="bg-slate-900/90 border border-slate-800/90 rounded-2xl p-4 flex flex-col md:flex-row items-center justify-between gap-4 shadow-lg">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search prompts or models..."
            className="w-full pl-9 pr-4 py-2 bg-slate-950/70 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 text-xs"
          />
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
        </div>

        {/* Status Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
          {['ALL', 'COMPLETED', 'PROCESSING', 'FAILED', 'QUEUED'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
                statusFilter === st
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-slate-800/60 text-slate-400 hover:text-white border border-slate-700/60'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Jobs Grid */}
      {loading ? (
        <div className="text-center py-16 text-slate-400 text-xs animate-pulse">Loading generation history...</div>
      ) : filteredJobs.length === 0 ? (
        <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-12 text-center space-y-3">
          <History className="w-8 h-8 text-slate-600 mx-auto" />
          <h3 className="text-base font-bold text-white">No Generations Found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            {searchQuery || statusFilter !== 'ALL'
              ? 'No video generations match your current search filters.'
              : 'You have not submitted any AI video generations yet.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredJobs.map((job) => (
            <article
              key={job.id}
              className="bg-slate-900/90 border border-slate-800/90 rounded-3xl p-6 space-y-4 shadow-xl hover:border-slate-700 transition flex flex-col justify-between"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800 text-indigo-300 text-xs font-semibold">
                    {job.model_type}
                  </span>
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

                <p className="text-sm font-semibold text-white leading-relaxed line-clamp-3">"{job.prompt}"</p>

                <p className="text-[11px] text-slate-500">
                  Created: {new Date(job.created_at).toLocaleString()}
                </p>

                {/* Processing status bar */}
                {job.status === 'PROCESSING' && (
                  <div className="space-y-1 pt-2">
                    <div className="flex justify-between text-xs text-slate-300">
                      <span>{job.phase || job.status_text || 'Processing...'}</span>
                      <span className="font-mono text-indigo-400 font-bold">{job.progress || 0}%</span>
                    </div>
                    <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                      <div
                        className="h-full bg-indigo-500 rounded-full transition-all duration-300"
                        style={{ width: `${Math.max(job.progress || 0, 5)}%` }}
                      ></div>
                    </div>
                  </div>
                )}

                {job.status === 'FAILED' && (
                  <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-xl text-rose-300 text-xs">
                    {job.error_message || 'Generation failed on engine.'}
                  </div>
                )}
              </div>

              {/* Video Player Output */}
              {videoUrls[job.id] && (
                <div className="space-y-3 pt-3 border-t border-slate-800">
                  <video
                    controls
                    className="w-full rounded-2xl border border-slate-800 bg-black shadow-md"
                    src={videoUrls[job.id]}
                  />
                  <a
                    href={videoUrls[job.id]}
                    download={`genvid-${job.id.slice(0, 8)}.mp4`}
                    className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl text-xs transition shadow-md flex items-center justify-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download MP4 Video</span>
                  </a>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}

export default HistoryPage
