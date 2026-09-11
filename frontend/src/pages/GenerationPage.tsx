import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '@/services/api'
import { useAuthStore } from '@/store/authStore'

type ModelMetadata = {
  model_type: string
  name: string
  description?: string
}

type GenerationJob = {
  id: string
  status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  prompt: string
  model_type: string
  progress: number | null
  current_step: number | null
  total_steps: number | null
  phase: string | null
  status_text: string | null
  output_available: boolean
  error_message: string | null
  created_at: string
  completed_at: string | null
}

const statusLabel: Record<GenerationJob['status'], string> = {
  QUEUED: 'Queued',
  PROCESSING: 'Processing',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
}

export const GenerationPage: React.FC = () => {
  const navigate = useNavigate()
  const { logout, user } = useAuthStore()
  const [models, setModels] = useState<ModelMetadata[]>([])
  const [jobs, setJobs] = useState<GenerationJob[]>([])
  const [prompt, setPrompt] = useState('')
  const [modelType, setModelType] = useState('')
  const [videoLength, setVideoLength] = useState(81)
  const [steps, setSteps] = useState(20)
  const [seed, setSeed] = useState(-1)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [videoUrls, setVideoUrls] = useState<Record<string, string>>({})
  const videoUrlsRef = useRef<Record<string, string>>({})

  const loadJobs = async () => {
    const response = await apiClient.get('/generations')
    setJobs(response.data)
  }

  useEffect(() => {
    const load = async () => {
      try {
        const [modelsResponse, jobsResponse] = await Promise.all([
          apiClient.get('/generations/models'),
          apiClient.get('/generations'),
        ])
        setModels(modelsResponse.data)
        setModelType(modelsResponse.data[0]?.model_type || '')
        setJobs(jobsResponse.data)
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Unable to load generation data')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  useEffect(() => {
    const hasActiveJobs = jobs.some((job) => job.status === 'QUEUED' || job.status === 'PROCESSING')
    if (!hasActiveJobs) return undefined
    const timer = window.setInterval(() => {
      loadJobs().catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [jobs])

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
          // The history entry remains visible when a video is unavailable.
        }
      }
    }
    loadVideos()
    return () => {
      disposed = true
    }
  }, [jobs, videoUrls])

  useEffect(() => () => Object.values(videoUrlsRef.current).forEach((url) => URL.revokeObjectURL(url)), [])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await apiClient.post('/generations', {
        prompt,
        model_type: modelType,
        video_length: videoLength,
        num_inference_steps: steps,
        seed,
      })
      setPrompt('')
      await loadJobs()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to submit generation')
    } finally {
      setSubmitting(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
      <header className="bg-black bg-opacity-50 border-b border-slate-700">
        <div className="max-w-6xl mx-auto px-6 py-4 flex justify-between items-center">
          <button onClick={() => navigate('/dashboard')} className="text-xl font-bold text-white">Wan2GP Platform</button>
          <div className="flex items-center gap-4">
            <span className="text-slate-300">{user?.username}</span>
            <button onClick={handleLogout} className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded font-semibold">Sign Out</button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-8">
        {error && <div className="p-4 bg-red-900/30 border border-red-700 rounded text-red-200">{error}</div>}

        <section className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h1 className="text-2xl font-bold text-white mb-5">Generate Video</h1>
          {loading ? <p className="text-slate-300">Loading available Wan2GP models...</p> : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <textarea required minLength={1} maxLength={4000} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Describe the video to generate" className="w-full min-h-28 rounded bg-slate-900 border border-slate-600 p-3 text-white" />
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <label className="text-slate-300">Model<select value={modelType} onChange={(event) => setModelType(event.target.value)} className="mt-1 w-full rounded bg-slate-900 border border-slate-600 p-2 text-white" required><option value="">Select model</option>{models.map((model) => <option key={model.model_type} value={model.model_type}>{model.name}</option>)}</select></label>
                <label className="text-slate-300">Frames<input type="number" min={1} max={9999} value={videoLength} onChange={(event) => setVideoLength(Number(event.target.value))} className="mt-1 w-full rounded bg-slate-900 border border-slate-600 p-2 text-white" /></label>
                <label className="text-slate-300">Steps<input type="number" min={1} max={100} value={steps} onChange={(event) => setSteps(Number(event.target.value))} className="mt-1 w-full rounded bg-slate-900 border border-slate-600 p-2 text-white" /></label>
                <label className="text-slate-300">Seed<input type="number" min={-1} value={seed} onChange={(event) => setSeed(Number(event.target.value))} className="mt-1 w-full rounded bg-slate-900 border border-slate-600 p-2 text-white" /></label>
              </div>
              <button disabled={submitting || !modelType} type="submit" className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white rounded font-semibold">{submitting ? 'Submitting...' : 'Generate'}</button>
            </form>
          )}
        </section>

        <section className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-xl font-bold text-white mb-5">Generation History</h2>
          {jobs.length === 0 ? <p className="text-slate-300">No generations submitted yet.</p> : <div className="space-y-4">{jobs.map((job) => (
            <article key={job.id} className="bg-slate-700 rounded-lg p-4 border border-slate-600">
              <div className="flex flex-col md:flex-row md:justify-between gap-3">
                <div><h3 className="text-white font-semibold">{job.prompt}</h3><p className="text-slate-400 text-sm">{job.model_type} · {new Date(job.created_at).toLocaleString()}</p></div>
                <span className="text-slate-200 font-semibold">{statusLabel[job.status]}{job.progress !== null ? ` · ${job.progress}%` : ''}</span>
              </div>
              {job.status === 'PROCESSING' && <p className="text-slate-300 text-sm mt-2">{job.phase || job.status_text || 'Generating...'}</p>}
              {job.status === 'FAILED' && <p className="text-red-300 text-sm mt-2">{job.error_message || 'Generation failed'}</p>}
              {videoUrls[job.id] && <video controls className="mt-4 w-full max-w-2xl rounded" src={videoUrls[job.id]} />}
            </article>
          ))}</div>}
        </section>
      </main>
    </div>
  )
}

export default GenerationPage
