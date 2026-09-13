import React, { useEffect, useRef, useState } from 'react'
import apiClient from '../services/api'
import { ModelMetadata, GenerationJob } from '../types'
import { useToastStore } from '../store/toastStore'
import {
  Sparkles,
  Zap,
  Play,
  Download,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  Loader2
} from 'lucide-react'

const samplePrompts = [
  'A cinematic close-up of a futuristic cyberpunk city at night with glowing neon signs reflecting off rainy asphalt...',
  'An ethereal mystical forest with bioluminescent mushrooms, soft floating glowing spores, cinematic lighting 8k...',
  'High-speed tracking shot of a sleek futuristic electric vehicle racing along a dramatic coastal cliff road at sunset...',
  'Macro shot of a drop of water falling onto a calm surface, forming intricate concentric ripple waves in slow motion...'
]

export const GenerationPage: React.FC = () => {
  const { addToast } = useToastStore()
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
    try {
      const response = await apiClient.get('/generations')
      setJobs(response.data || [])
    } catch {
      // Keep state resilient
    }
  }

  useEffect(() => {
    const loadData = async () => {
      try {
        const [modelsResponse, jobsResponse] = await Promise.all([
          apiClient.get('/generations/models'),
          apiClient.get('/generations'),
        ])

        const loadedModels: ModelMetadata[] = modelsResponse.data || []
        setModels(loadedModels)

        const readyModel = loadedModels.find((m) => m.availability?.available)
        if (readyModel) {
          setModelType(readyModel.model_type)
        } else if (loadedModels.length > 0) {
          setModelType(loadedModels[0].model_type)
        }

        setJobs(jobsResponse.data || [])
      } catch (err: any) {
        setModels([])
        setError(err.response?.data?.detail || null)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  // Poll active jobs
  useEffect(() => {
    const hasActiveJobs = jobs.some((job) => job.status === 'QUEUED' || job.status === 'PROCESSING')
    if (!hasActiveJobs) return undefined

    const timer = window.setInterval(() => {
      loadJobs().catch(() => undefined)
    }, 2000)

    return () => window.clearInterval(timer)
  }, [jobs])

  // Fetch blobs for completed video outputs
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
          // Graceful fallback
        }
      }
    }
    loadVideos()
    return () => {
      disposed = true
    }
  }, [jobs, videoUrls])

  useEffect(() => () => Object.values(videoUrlsRef.current).forEach((url) => URL.revokeObjectURL(url)), [])

  const selectedModel = models.find((m) => m.model_type === modelType)
  const isSelectedModelReady = Boolean(selectedModel?.availability?.available)
  const hasGpuRuntime = models.length > 0

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!prompt.trim() || !modelType || !isSelectedModelReady) return

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
      addToast({
        type: 'success',
        title: 'Job Submitted',
        message: 'Your video generation job was sent to the GPU queue.',
      })
      setPrompt('')
      await loadJobs()
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to submit generation task'
      setError(msg)
      addToast({
        type: 'error',
        title: 'Submission Error',
        message: msg,
      })
    } finally {
      setSubmitting(false)
    }
  }

  const activeJob = jobs.find((j) => j.status === 'PROCESSING' || j.status === 'QUEUED')
  const completedJobs = jobs.filter((j) => j.status === 'COMPLETED')

  return (
    <div className="space-y-8">
      {/* Workspace Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
            <Sparkles className="w-6 h-6 text-indigo-400" />
            <span>Create Video</span>
          </h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Turn your ideas into high-fidelity AI video with GenVid.AI multi-model inference.
          </p>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-950/50 border border-rose-800/80 rounded-2xl text-rose-200 text-xs sm:text-sm flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* GPU Runtime Status Warning Banner (Dev Mode / No GPU Machine) */}
      {!loading && !hasGpuRuntime && (
        <div className="bg-amber-950/30 border border-amber-800/60 rounded-2xl p-6 backdrop-blur-md flex items-start gap-4 shadow-lg">
          <div className="w-10 h-10 rounded-xl bg-amber-900/40 border border-amber-700/60 flex items-center justify-center text-amber-300 font-bold text-lg shrink-0">
            <Zap className="w-5 h-5 text-amber-400" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm sm:text-base font-bold text-amber-200">
              GPU Generation Unavailable on this Machine
            </h3>
            <p className="text-slate-300 text-xs sm:text-sm leading-relaxed">
              PyTorch / CUDA hardware runtime is not active in this development environment.
              All frontend controls, auth, history, and API routes are active. When deployed on a GPU Studio instance, dynamic models will activate automatically.
            </p>
          </div>
        </div>
      )}

      {/* Studio Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left / Main Section: Prompt Editor & Hyperparameters */}
        <div className="lg:col-span-2 space-y-6">
          <section className="bg-slate-900/90 rounded-3xl p-6 sm:p-8 border border-slate-800/90 shadow-2xl space-y-6">
            {loading ? (
              <div className="py-12 flex flex-col items-center justify-center text-slate-400 text-xs gap-3">
                <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
                <span>Discovering models from engine...</span>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Prompt Canvas Header */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                      Prompt Description
                    </label>
                    <span className="text-[11px] text-slate-500">{prompt.length} / 4000 chars</span>
                  </div>

                  <textarea
                    required
                    minLength={1}
                    maxLength={4000}
                    value={prompt}
                    onChange={(event) => setPrompt(event.target.value)}
                    placeholder="Describe your scene in detail, e.g. A cinematic close-up of a futuristic cyberpunk city at night with neon lights reflecting off rainy streets..."
                    className="w-full min-h-36 rounded-2xl bg-slate-950/70 border border-slate-700/80 p-4 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 text-sm leading-relaxed"
                  />

                  {/* Preset Prompt Suggestions */}
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                      Sample Prompt Ideas:
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {samplePrompts.map((p, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => setPrompt(p)}
                          className="px-2.5 py-1 bg-slate-800/60 hover:bg-indigo-950/50 hover:border-indigo-700/60 border border-slate-700/70 rounded-lg text-slate-300 text-[11px] truncate max-w-xs transition text-left"
                        >
                          "{p.slice(0, 45)}..."
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Hyperparameter Settings Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                  {/* Dynamic Model Selector */}
                  <div className="sm:col-span-2 md:col-span-1 space-y-1.5">
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                      Select Model
                    </label>
                    <select
                      value={modelType}
                      onChange={(event) => setModelType(event.target.value)}
                      className="w-full rounded-xl bg-slate-950/70 border border-slate-700/80 p-2.5 text-white focus:outline-none focus:border-indigo-500 text-xs font-medium"
                      required
                      disabled={!hasGpuRuntime}
                    >
                      {!hasGpuRuntime ? (
                        <option value="">No GPU model runtime</option>
                      ) : (
                        models.map((m) => {
                          const isReady = Boolean(m.availability?.available)
                          return (
                            <option key={m.model_type} value={m.model_type}>
                              {m.name} {isReady ? '✓ Ready' : '⚠ Missing Checkpoint'}
                            </option>
                          )
                        })
                      )}
                    </select>
                  </div>

                  {/* Frames */}
                  <div className="space-y-1.5">
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                      Video Frames
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={9999}
                      value={videoLength}
                      onChange={(e) => setVideoLength(Number(e.target.value))}
                      className="w-full rounded-xl bg-slate-950/70 border border-slate-700/80 p-2.5 text-white focus:outline-none focus:border-indigo-500 text-xs font-medium"
                      disabled={!hasGpuRuntime}
                    />
                  </div>

                  {/* Inference Steps */}
                  <div className="space-y-1.5">
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                      Sampling Steps
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={steps}
                      onChange={(e) => setSteps(Number(e.target.value))}
                      className="w-full rounded-xl bg-slate-950/70 border border-slate-700/80 p-2.5 text-white focus:outline-none focus:border-indigo-500 text-xs font-medium"
                      disabled={!hasGpuRuntime}
                    />
                  </div>

                  {/* Seed */}
                  <div className="space-y-1.5">
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-300">
                      Random Seed
                    </label>
                    <input
                      type="number"
                      min={-1}
                      value={seed}
                      onChange={(e) => setSeed(Number(e.target.value))}
                      className="w-full rounded-xl bg-slate-950/70 border border-slate-700/80 p-2.5 text-white focus:outline-none focus:border-indigo-500 text-xs font-medium"
                      disabled={!hasGpuRuntime}
                    />
                  </div>
                </div>

                {/* Selected Model Capability Details Badge */}
                {selectedModel && (
                  <div className="p-3.5 bg-slate-950/60 border border-slate-800 rounded-xl text-xs flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white">{selectedModel.name}</span>
                      <span className="text-slate-400 font-mono">({selectedModel.model_type})</span>
                    </div>
                    <div>
                      {isSelectedModelReady ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 font-semibold">
                          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          <span>Checkpoints Ready</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-950/60 border border-amber-800/60 text-amber-300 font-semibold">
                          <AlertTriangle className="w-3 h-3 text-amber-400" />
                          <span>Missing Checkpoints ({selectedModel.availability?.reason || 'Weights missing'})</span>
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Submit Action Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2 border-t border-slate-800">
                  <p className="text-xs text-slate-400">
                    {!hasGpuRuntime
                      ? 'Deploy on GPU Studio instance with model checkpoints to generate video.'
                      : !isSelectedModelReady
                      ? 'Selected model requires checkpoint files before execution.'
                      : 'Ready to submit task to GPU pipeline.'}
                  </p>

                  <button
                    disabled={submitting || !hasGpuRuntime || !isSelectedModelReady}
                    type="submit"
                    className="px-8 py-3.5 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 disabled:opacity-50 text-white font-bold rounded-xl transition-all duration-200 shadow-xl shadow-indigo-600/25 flex items-center justify-center gap-2.5 text-sm shrink-0"
                  >
                    {submitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Submitting Task...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        <span>Generate Video</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>

        {/* Right Section: Active Generation Progress & Latest Output */}
        <div className="space-y-6">
          {/* Active Job Real-Time Card */}
          {activeJob ? (
            <div className="bg-slate-900/90 border border-indigo-500/40 rounded-3xl p-6 shadow-2xl space-y-4 animate-pulse">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
                  <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
                  Generating Video...
                </span>
                <span className="text-xs font-mono font-bold text-indigo-300">{activeJob.progress || 0}%</span>
              </div>

              <p className="text-xs text-slate-300 line-clamp-2 italic">"{activeJob.prompt}"</p>

              <div className="space-y-1.5">
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Phase: {activeJob.phase || activeJob.status_text || 'Processing'}</span>
                  <span>
                    Step {activeJob.current_step || 0} / {activeJob.total_steps || steps}
                  </span>
                </div>
                <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(activeJob.progress || 0, 5)}%` }}
                  ></div>
                </div>
              </div>
            </div>
          ) : (
            /* Standby Card */
            <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6 text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-950/60 border border-indigo-800/60 flex items-center justify-center text-indigo-400 mx-auto">
                <Play className="w-5 h-5 fill-current ml-0.5" />
              </div>
              <h4 className="text-sm font-bold text-white">Generation Output Canvas</h4>
              <p className="text-xs text-slate-400">
                Your active video generation progress and completed MP4 previews will display here.
              </p>
            </div>
          )}

          {/* Latest Video Player Output */}
          {completedJobs.length > 0 && (
            <div className="bg-slate-900/90 border border-slate-800/90 rounded-3xl p-6 shadow-xl space-y-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Latest Completed Output</span>
              </h3>

              {videoUrls[completedJobs[0].id] ? (
                <div className="space-y-3">
                  <video
                    controls
                    className="w-full rounded-2xl border border-slate-800 bg-black shadow-lg"
                    src={videoUrls[completedJobs[0].id]}
                  />
                  <div className="space-y-2">
                    <p className="text-xs text-slate-300 line-clamp-2">"{completedJobs[0].prompt}"</p>
                    <a
                      href={videoUrls[completedJobs[0].id]}
                      download={`genvid-${completedJobs[0].id.slice(0, 8)}.mp4`}
                      className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl text-xs transition shadow-md shadow-emerald-600/20 flex items-center justify-center gap-2"
                    >
                      <Download className="w-4 h-4" />
                      <span>Download MP4 Video</span>
                    </a>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-400">Loading output video stream...</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default GenerationPage
