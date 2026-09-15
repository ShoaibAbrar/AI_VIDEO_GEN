import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import apiClient from '@/services/api'
import { useToastStore } from '@/store/toastStore'
import {
  Sparkles,
  Video,
  Play,
  Download,
  AlertCircle,
  Sliders,
  Loader2,
  RefreshCw,
  Layers
} from 'lucide-react'

type ModelAvailability = {
  model_type: string
  status: string
  status_code: number
  available: boolean
}

type ModelMetadata = {
  model_type: string
  name: string
  description?: string
  availability?: ModelAvailability
  fps?: number
  frames_minimum?: number
  frames_steps?: number
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

const promptIdeas = [
  'A cinematic aerial shot of a bioluminescent waterfall cascading into a crystal lagoon at dusk.',
  'A cute robot exploring an ancient enchanted forest, golden sunlight filtering through trees.',
  'Futuristic cityscape with flying vehicles and glowing neon holograms under heavy rain.',
  'A serene Japanese tea house beside a koi pond with pink cherry blossom petals falling gracefully.'
]

export const GenerationPage: React.FC = () => {
  const { addToast } = useToastStore()

  const [models, setModels] = useState<ModelMetadata[]>([])
  const [jobs, setJobs] = useState<GenerationJob[]>([])
  const [prompt, setPrompt] = useState('')
  const [modelType, setModelType] = useState('')
  const [videoLength, setVideoLength] = useState(81)
  const [steps, setSteps] = useState(25)
  const [seed, setSeed] = useState(-1)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [videoUrls, setVideoUrls] = useState<Record<string, string>>({})
  const videoUrlsRef = useRef<Record<string, string>>({})

  const loadJobs = async () => {
    try {
      const response = await apiClient.get('/generations')
      setJobs(response.data || [])
    } catch {
      // Background poll failure ignored
    }
  }

  useEffect(() => {
    const initData = async () => {
      try {
        const [modelsResponse, jobsResponse] = await Promise.all([
          apiClient.get('/generations/models'),
          apiClient.get('/generations'),
        ])
        const modelList: ModelMetadata[] = modelsResponse.data || []
        setModels(modelList)

        // Select first available model or fallback to first
        const firstAvailable = modelList.find((m) => m.availability?.available)
        if (firstAvailable) {
          setModelType(firstAvailable.model_type)
        } else if (modelList.length > 0) {
          setModelType(modelList[0].model_type)
        }

        setJobs(jobsResponse.data || [])
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Unable to connect to video generation engine.')
      } finally {
        setLoading(false)
      }
    }
    initData()
  }, [])

  // Poll for active jobs
  useEffect(() => {
    const active = jobs.find((job) => job.status === 'QUEUED' || job.status === 'PROCESSING')
    if (active) {
      setActiveJobId(active.id)
    } else {
      setActiveJobId(null)
    }

    const hasActive = Boolean(active)
    if (!hasActive) return undefined

    const timer = window.setInterval(() => {
      loadJobs()
    }, 1500)
    return () => window.clearInterval(timer)
  }, [jobs])

  // Load video blob URLs for completed outputs
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
            setVideoUrls({ ...videoUrlsRef.current })
          }
        } catch {
          // Video fetch failure handled gracefully
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
    if (!prompt.trim()) return
    setSubmitting(true)
    setError(null)

    try {
      const response = await apiClient.post('/generations', {
        prompt: prompt.trim(),
        model_type: modelType,
        video_length: videoLength,
        num_inference_steps: steps,
        seed: seed < 0 ? -1 : seed,
      })

      addToast({
        type: 'info',
        title: 'Job Queued',
        message: 'Your video generation request has been queued for rendering.',
      })

      setActiveJobId(response.data.id)
      setPrompt('')
      await loadJobs()
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to submit video generation request.'
      setError(msg)
      addToast({
        type: 'error',
        title: 'Generation Request Failed',
        message: msg,
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancel = async (jobId: string) => {
    try {
      await apiClient.post(`/generations/${jobId}/cancel`)
      addToast({
        type: 'info',
        title: 'Job Cancelled',
        message: 'The queued video task was successfully cancelled.',
      })
      await loadJobs()
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Cancel Failed',
        message: err.response?.data?.detail || 'Unable to cancel job.',
      })
    }
  }

  const selectedModel = models.find((m) => m.model_type === modelType)
  const isSelectedModelAvailable = selectedModel?.availability?.available ?? true
  const currentActiveJob = jobs.find((j) => j.id === activeJobId)
  const latestCompletedJob = jobs.find((j) => j.status === 'COMPLETED' && j.output_available)

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Studio Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
            <Sparkles className="w-6 h-6 text-indigo-400" />
            <span>AI Video Creation Studio</span>
          </h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Transform text prompts into high-definition videos with state-of-the-art diffusion models.
          </p>
        </div>

        <button
          onClick={loadJobs}
          className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-slate-300 hover:text-white text-xs font-semibold flex items-center gap-2 self-start sm:self-auto transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Queue</span>
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-rose-950/60 border border-rose-800/80 rounded-2xl text-rose-200 text-xs sm:text-sm flex items-start gap-3 shadow-lg">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold block">Generation Notification</span>
            <p className="text-rose-300 text-xs">{error}</p>
          </div>
        </div>
      )}

      {/* Main Grid: Form & Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Prompt and Parameter Studio Form */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-slate-900/90 border border-slate-800/90 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Prompt Canvas */}
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Video className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Prompt Canvas</span>
                  </label>
                  <span className="text-[11px] text-slate-500">{prompt.length} / 4000</span>
                </div>

                <textarea
                  required
                  rows={4}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe your scene in detail: lighting, motion, camera angle, atmosphere, and visual style..."
                  className="w-full bg-slate-950/80 border border-slate-800 focus:border-indigo-500 rounded-2xl p-4 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition resize-none leading-relaxed"
                />

                {/* Prompt Inspiration Chips */}
                <div className="space-y-1.5 pt-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Prompt Ideas:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {promptIdeas.map((idea, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setPrompt(idea)}
                        className="text-[11px] bg-slate-950/60 hover:bg-slate-800 border border-slate-800/80 text-slate-400 hover:text-slate-200 px-2.5 py-1 rounded-lg text-left transition truncate max-w-xs"
                        title={idea}
                      >
                        "{idea.slice(0, 35)}..."
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Model Selection */}
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Inference Model Engine</span>
                  </span>
                  {selectedModel?.availability && (
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                        isSelectedModelAvailable
                          ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/60'
                          : 'bg-amber-950/60 text-amber-300 border border-amber-800/60'
                      }`}
                    >
                      {isSelectedModelAvailable ? '● Ready' : '▲ Missing Weights'}
                    </span>
                  )}
                </label>

                {loading ? (
                  <div className="p-3 bg-slate-950/50 rounded-xl text-xs text-slate-500 animate-pulse">
                    Detecting model configurations...
                  </div>
                ) : (
                  <div className="relative">
                    <select
                      value={modelType}
                      onChange={(e) => setModelType(e.target.value)}
                      className="w-full bg-slate-950/80 border border-slate-800 focus:border-indigo-500 rounded-xl p-3 text-sm text-white focus:outline-none appearance-none cursor-pointer pr-10"
                      required
                    >
                      {models.map((model) => {
                        const isAvail = model.availability?.available ?? true
                        return (
                          <option key={model.model_type} value={model.model_type} className="bg-slate-900 text-white">
                            {model.name} {isAvail ? '(Ready)' : '(Unavailable / Missing Weights)'}
                          </option>
                        )
                      })}
                    </select>
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500 text-xs">▼</div>
                  </div>
                )}

                {selectedModel?.description && (
                  <p className="text-xs text-slate-400 leading-relaxed px-1">{selectedModel.description}</p>
                )}
              </div>

              {/* Hyperparameters Controls */}
              <div className="pt-2 border-t border-slate-800/80 space-y-4">
                <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-300">
                  <Sliders className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Generation Parameters</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  {/* Video Frames */}
                  <div className="p-3.5 bg-slate-950/60 border border-slate-800/80 rounded-2xl space-y-1.5">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-300">Video Frames</span>
                      <span className="text-indigo-400 font-mono font-bold">{videoLength}</span>
                    </div>
                    <input
                      type="number"
                      min={1}
                      max={9999}
                      value={videoLength}
                      onChange={(e) => setVideoLength(Number(e.target.value))}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    />
                    <span className="text-[10px] text-slate-500 block">Typical: 81 (~5s at 16fps)</span>
                  </div>

                  {/* Inference Steps */}
                  <div className="p-3.5 bg-slate-950/60 border border-slate-800/80 rounded-2xl space-y-1.5">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-300">Sampling Steps</span>
                      <span className="text-purple-400 font-mono font-bold">{steps}</span>
                    </div>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={steps}
                      onChange={(e) => setSteps(Number(e.target.value))}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-xs text-white focus:outline-none focus:border-purple-500"
                    />
                    <span className="text-[10px] text-slate-500 block">Range: 15 to 50 steps</span>
                  </div>

                  {/* Random Seed */}
                  <div className="p-3.5 bg-slate-950/60 border border-slate-800/80 rounded-2xl space-y-1.5">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-slate-300">Seed</span>
                      <span className="text-pink-400 font-mono font-bold">{seed === -1 ? 'Random' : seed}</span>
                    </div>
                    <input
                      type="number"
                      min={-1}
                      value={seed}
                      onChange={(e) => setSeed(Number(e.target.value))}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-xs text-white focus:outline-none focus:border-pink-500"
                    />
                    <span className="text-[10px] text-slate-500 block">-1 for randomized seed</span>
                  </div>
                </div>
              </div>

              {/* Submit CTA */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={submitting || !modelType || loading}
                  className="w-full py-4 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-2xl text-base transition-all duration-200 shadow-xl shadow-indigo-600/25 flex items-center justify-center gap-2.5 group"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Submitting Video Request...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5 group-hover:scale-110 transition-transform" />
                      <span>Render AI Video</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Right Column: Live Progress & Instant Preview */}
        <div className="lg:col-span-5 space-y-6">
          {/* Active Job Progress Monitor */}
          {currentActiveJob && (
            <div className="bg-slate-900/90 border border-indigo-500/50 rounded-3xl p-6 shadow-2xl space-y-4 animate-pulse-border">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-ping"></div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">Inference in Progress</h3>
                </div>
                {currentActiveJob.status === 'QUEUED' && (
                  <button
                    onClick={() => handleCancel(currentActiveJob.id)}
                    className="text-xs text-slate-400 hover:text-rose-400 transition"
                  >
                    Cancel
                  </button>
                )}
              </div>

              <div className="p-3.5 bg-slate-950/80 rounded-2xl border border-slate-800 space-y-2">
                <p className="text-xs text-slate-300 font-medium line-clamp-2">"{currentActiveJob.prompt}"</p>
                <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                  <span>Model: {currentActiveJob.model_type}</span>
                  <span>{currentActiveJob.status}</span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-indigo-300">
                    {currentActiveJob.phase || currentActiveJob.status_text || 'Rendering pipeline active...'}
                  </span>
                  <span className="text-white font-mono">{currentActiveJob.progress ?? 0}%</span>
                </div>
                <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 transition-all duration-300"
                    style={{ width: `${Math.max(currentActiveJob.progress ?? 5, 5)}%` }}
                  ></div>
                </div>
                {currentActiveJob.current_step !== null && currentActiveJob.total_steps !== null && (
                  <div className="text-[10px] text-slate-500 text-right">
                    Step {currentActiveJob.current_step} / {currentActiveJob.total_steps}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Latest Video Preview Card */}
          <div className="bg-slate-900/90 border border-slate-800/90 rounded-3xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Play className="w-4 h-4 text-indigo-400" />
                <span>Live Studio Preview</span>
              </h3>
              <Link to="/history" className="text-xs text-indigo-400 hover:text-indigo-300 transition">
                All Creations &rarr;
              </Link>
            </div>

            {latestCompletedJob && videoUrls[latestCompletedJob.id] ? (
              <div className="space-y-4">
                <div className="rounded-2xl overflow-hidden border border-slate-800 bg-black aspect-video flex items-center justify-center relative shadow-lg">
                  <video
                    controls
                    autoPlay
                    loop
                    className="w-full h-full object-contain"
                    src={videoUrls[latestCompletedJob.id]}
                  />
                </div>

                <div className="p-3.5 bg-slate-950/60 rounded-2xl border border-slate-800 space-y-2">
                  <p className="text-xs text-slate-200 line-clamp-2 italic font-mono">
                    "{latestCompletedJob.prompt}"
                  </p>
                  <div className="flex items-center justify-between text-[10px] text-slate-400">
                    <span>{latestCompletedJob.model_type}</span>
                    <span>{new Date(latestCompletedJob.created_at).toLocaleTimeString()}</span>
                  </div>
                </div>

                <a
                  href={videoUrls[latestCompletedJob.id]}
                  download={`genvid-${latestCompletedJob.id}.mp4`}
                  className="w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl text-xs font-semibold text-white transition flex items-center justify-center gap-2"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download MP4 Video</span>
                </a>
              </div>
            ) : (
              <div className="py-16 text-center space-y-3 bg-slate-950/40 rounded-2xl border border-dashed border-slate-800 p-6">
                <div className="w-12 h-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-600 mx-auto">
                  <Video className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-300">No Rendered Preview Yet</p>
                  <p className="text-xs text-slate-500 mt-1">
                    Submit a prompt from the studio canvas to generate and stream video previews here.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default GenerationPage
