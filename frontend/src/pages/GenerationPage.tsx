import React, { useEffect, useRef, useState } from 'react'
import apiClient from '@/services/api'
import { useToastStore } from '@/store/toastStore'
import {
  CharacterMode,
  ContinuityLevel,
  DurationMode,
  GenerationJob,
  GenerationPlan,
  GenerationStyle,
  QualityTier,
  UserRequirements,
  VoiceMode,
} from '@/types'
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Download,
  Film,
  Info,
  Loader2,
  Palette,
  Play,
  Ratio,
  RefreshCw,
  Sliders,
  Sparkles,
  Users,
  Video,
  Volume2,
  Mic,
  Cpu,
} from 'lucide-react'

const promptIdeas = [
  'A cinematic aerial shot of a bioluminescent waterfall cascading into a crystal lagoon at dusk.',
  'A cute robot exploring an ancient enchanted forest, golden sunlight filtering through trees.',
  'Futuristic cityscape with flying vehicles and glowing neon holograms under heavy rain.',
  'A serene Japanese tea house beside a koi pond with pink cherry blossom petals falling gracefully.',
]

const styleOptions: { id: GenerationStyle; label: string; desc: string }[] = [
  { id: 'cinematic', label: 'Cinematic Film', desc: 'Dramatic lighting & rich depth' },
  { id: 'realistic', label: 'Photorealistic', desc: 'Natural colors & crisp details' },
  { id: 'anime', label: 'Anime / Manga', desc: 'Vibrant colors & illustration' },
  { id: '3d_animation', label: '3D Animation', desc: 'Smooth CGI render style' },
  { id: 'fantasy', label: 'Epic Fantasy', desc: 'Ethereal glow & magical ambiance' },
  { id: 'cyberpunk', label: 'Cyberpunk', desc: 'Neon lights & futuristic tech' },
  { id: 'documentary', label: 'Documentary', desc: 'Raw handheld realism' },
  { id: 'custom', label: 'Direct / Custom', desc: 'Pure unenhanced prompt' },
]

export const GenerationPage: React.FC = () => {
  const { addToast } = useToastStore()

  // User Requirements state
  const [prompt, setPrompt] = useState('')
  const [duration, setDuration] = useState<DurationMode>('short')
  const [customSeconds, setCustomSeconds] = useState(10)
  const [voiceMode, setVoiceMode] = useState<VoiceMode>('none')
  const [audioPrompt, setAudioPrompt] = useState('')
  const [referenceAudioUrl, setReferenceAudioUrl] = useState('')
  const [characterMode, setCharacterMode] = useState<CharacterMode>('single')
  const [continuity, setContinuity] = useState<ContinuityLevel>('standard')
  const [quality, setQuality] = useState<QualityTier>('high')
  const [generationStyle, setGenerationStyle] = useState<GenerationStyle>('cinematic')
  const [aspectRatio, setAspectRatio] = useState('16:9')
  const [seed, setSeed] = useState(-1)
  const [preferredEngine, setPreferredEngine] = useState('')

  // Engine discovery state
  const [availableEngines, setAvailableEngines] = useState<Array<{ engine_id: string; display_name: string; is_available: boolean }>>([])

  // Capability Plan & Queue state
  const [plan, setPlan] = useState<GenerationPlan | null>(null)
  const [planLoading, setPlanLoading] = useState(false)
  const [showDevPlan, setShowDevPlan] = useState(false)
  const [jobs, setJobs] = useState<GenerationJob[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [videoUrls, setVideoUrls] = useState<Record<string, string>>({})
  const videoUrlsRef = useRef<Record<string, string>>({})

  // Load registered engines
  const loadEngines = async () => {
    try {
      const response = await apiClient.get('/generations/engines')
      setAvailableEngines(response.data || [])
    } catch {
      // Ignore background fetch error
    }
  }

  // Load jobs history
  const loadJobs = async () => {
    try {
      const response = await apiClient.get('/generations')
      setJobs(response.data || [])
    } catch {
      // Ignore background poll errors
    }
  }

  // Real-time Capability Plan Resolution (debounced)
  useEffect(() => {
    if (!prompt.trim()) {
      setPlan(null)
      return
    }

    const timer = setTimeout(async () => {
      setPlanLoading(true)
      try {
        const payload: UserRequirements & { preferred_engine_id?: string } = {
          prompt: prompt.trim(),
          duration,
          custom_seconds: duration === 'custom' ? customSeconds : null,
          voice_mode: voiceMode,
          audio_prompt: voiceMode !== 'none' ? audioPrompt : null,
          character_mode: characterMode,
          continuity,
          quality,
          generation_style: generationStyle,
          aspect_ratio: aspectRatio,
          seed: seed < 0 ? -1 : seed,
          reference_audio_url: voiceMode === 'custom_user_voice' ? referenceAudioUrl : null,
          preferred_engine_id: preferredEngine || undefined,
        }
        const response = await apiClient.post('/generations/plan', payload)
        setPlan(response.data)
      } catch {
        // Plan preview failure handled silently
      } finally {
        setPlanLoading(false)
      }
    }, 350)

    return () => clearTimeout(timer)
  }, [
    prompt,
    duration,
    customSeconds,
    voiceMode,
    audioPrompt,
    referenceAudioUrl,
    characterMode,
    continuity,
    quality,
    generationStyle,
    aspectRatio,
    seed,
    preferredEngine,
  ])

  // Initial load
  useEffect(() => {
    loadJobs()
    loadEngines()
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
          // Handled gracefully
        }
      }
    }
    loadVideos()
    return () => {
      disposed = true
    }
  }, [jobs, videoUrls])

  useEffect(() => () => Object.values(videoUrlsRef.current).forEach((url) => URL.revokeObjectURL(url)), [])

  // Submit Generation Request by User Requirements
  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!prompt.trim()) return
    setSubmitting(true)
    setError(null)

    try {
      const payload: UserRequirements & { preferred_engine_id?: string } = {
        prompt: prompt.trim(),
        duration,
        custom_seconds: duration === 'custom' ? customSeconds : null,
        voice_mode: voiceMode,
        audio_prompt: voiceMode !== 'none' ? audioPrompt : null,
        character_mode: characterMode,
        continuity,
        quality,
        generation_style: generationStyle,
        aspect_ratio: aspectRatio,
        seed: seed < 0 ? -1 : seed,
        reference_audio_url: voiceMode === 'custom_user_voice' ? referenceAudioUrl : null,
        preferred_engine_id: preferredEngine || undefined,
      }

      const response = await apiClient.post('/generations/by-requirements', payload)

      addToast({
        type: 'info',
        title: 'Video Queued',
        message: 'Your video generation request has been scheduled with the optimal AI engine.',
      })

      setActiveJobId(response.data.id)
      setPrompt('')
      await loadJobs()
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to submit video generation request.'
      setError(msg)
      addToast({
        type: 'error',
        title: 'Generation Failed',
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
            Describe your creative vision. The intelligent capability engine selects and configures the optimal AI video model.
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

      {/* Main Grid: Requirement Form & Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Requirements Studio Form */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-slate-900/90 border border-slate-800/90 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Prompt Canvas */}
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Video className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Scene Prompt Canvas</span>
                  </label>
                  <span className="text-[11px] text-slate-500">{prompt.length} / 4000</span>
                </div>

                <textarea
                  required
                  rows={4}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe your scene in detail: lighting, motion, camera angle, atmosphere, and visual narrative..."
                  className="w-full bg-slate-950/80 border border-slate-800 focus:border-indigo-500 rounded-2xl p-4 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition resize-none leading-relaxed"
                />

                {/* Prompt Inspiration Chips */}
                <div className="space-y-1.5 pt-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">Prompt Inspiration:</span>
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

              {/* Requirement Section 1: Duration & Aspect Ratio */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-800/80">
                {/* Duration Mode */}
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Duration Target</span>
                  </label>
                  <div className="grid grid-cols-3 gap-1.5 bg-slate-950/80 p-1.5 rounded-2xl border border-slate-800">
                    {(['short', 'long', 'custom'] as DurationMode[]).map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => setDuration(d)}
                        className={`py-2 px-2 text-xs font-semibold rounded-xl capitalize transition text-center ${
                          duration === d
                            ? 'bg-indigo-600 text-white shadow-md'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                        }`}
                      >
                        {d === 'short' ? 'Short (2.5s)' : d === 'long' ? 'Long (10s+)' : 'Custom'}
                      </button>
                    ))}
                  </div>

                  {duration === 'custom' && (
                    <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-1.5 mt-2">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-slate-400">Duration in Seconds</span>
                        <span className="text-indigo-400 font-mono">{customSeconds}s</span>
                      </div>
                      <input
                        type="range"
                        min={2}
                        max={60}
                        step={1}
                        value={customSeconds}
                        onChange={(e) => setCustomSeconds(Number(e.target.value))}
                        className="w-full accent-indigo-500 cursor-pointer"
                      />
                    </div>
                  )}
                </div>

                {/* Aspect Ratio */}
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Ratio className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Aspect Ratio</span>
                  </label>
                  <div className="grid grid-cols-3 gap-1.5 bg-slate-950/80 p-1.5 rounded-2xl border border-slate-800">
                    {[
                      { id: '16:9', label: '16:9 (Landscape)' },
                      { id: '9:16', label: '9:16 (Vertical)' },
                      { id: '1:1', label: '1:1 (Square)' },
                    ].map((ratio) => (
                      <button
                        key={ratio.id}
                        type="button"
                        onClick={() => setAspectRatio(ratio.id)}
                        className={`py-2 px-2 text-xs font-semibold rounded-xl transition text-center ${
                          aspectRatio === ratio.id
                            ? 'bg-indigo-600 text-white shadow-md'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                        }`}
                      >
                        {ratio.id}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Requirement Section 2: Voice Mode & Character Continuity */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-800/80">
                {/* Voice Synthesis Mode */}
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Volume2 className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Voice & Audio Mode</span>
                  </label>
                  <select
                    value={voiceMode}
                    onChange={(e) => setVoiceMode(e.target.value as VoiceMode)}
                    className="w-full bg-slate-950/80 border border-slate-800 focus:border-indigo-500 rounded-xl p-3 text-xs text-white focus:outline-none cursor-pointer"
                  >
                    <option value="none">Silent (No Audio Synthesis)</option>
                    <option value="ai">AI Voiceover (Edge TTS / Narrative Audio)</option>
                    <option value="human_like">Human-Like Dialogue (Conditioned Speech)</option>
                    <option value="custom_user_voice">Custom Voice Clone (Chatterbox Zero-Shot)</option>
                  </select>

                  {voiceMode !== 'none' && (
                    <div className="space-y-2 mt-2">
                      <input
                        type="text"
                        value={audioPrompt}
                        onChange={(e) => setAudioPrompt(e.target.value)}
                        placeholder="Dialogue line or voiceover script..."
                        className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none"
                      />

                      {voiceMode === 'custom_user_voice' && (
                        <div className="p-3 bg-indigo-950/30 border border-indigo-800/60 rounded-xl space-y-1.5">
                          <label className="text-[11px] font-semibold text-indigo-300 flex items-center gap-1">
                            <Mic className="w-3 h-3 text-indigo-400" />
                            <span>Voice Profile ID or Reference Audio Path</span>
                          </label>
                          <input
                            type="text"
                            value={referenceAudioUrl}
                            onChange={(e) => setReferenceAudioUrl(e.target.value)}
                            placeholder="e.g. materials/test_reference_voice.wav or vp_uuid"
                            className="w-full bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-lg p-2 text-xs text-white font-mono placeholder-slate-600 focus:outline-none"
                          />
                          <p className="text-[10px] text-slate-400">
                            Zero-shot Chatterbox voice cloning requires an authorized voice profile or reference WAV audio.
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Character & Continuity Mode */}
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Users className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Characters & Narrative Flow</span>
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setCharacterMode('single')}
                      className={`p-2.5 rounded-xl border text-xs font-semibold text-left transition ${
                        characterMode === 'single'
                          ? 'bg-indigo-950/40 border-indigo-600 text-indigo-200'
                          : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:bg-slate-900'
                      }`}
                    >
                      <span className="block font-bold">Single Subject</span>
                      <span className="text-[10px] text-slate-500">Focused framing</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setCharacterMode('multiple')}
                      className={`p-2.5 rounded-xl border text-xs font-semibold text-left transition ${
                        characterMode === 'multiple'
                          ? 'bg-indigo-950/40 border-indigo-600 text-indigo-200'
                          : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:bg-slate-900'
                      }`}
                    >
                      <span className="block font-bold">Multiple Subjects</span>
                      <span className="text-[10px] text-slate-500">H3 Director multi-character</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Requirement Section 3: Quality Tier, Motion Continuity & Engine Preference */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 border-t border-slate-800/80">
                {/* Quality Tier */}
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Film className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Quality Tier</span>
                  </label>
                  <div className="grid grid-cols-3 gap-1 bg-slate-950/80 p-1 rounded-2xl border border-slate-800">
                    {[
                      { id: 'standard', label: 'Std' },
                      { id: 'high', label: 'High' },
                      { id: 'cinematic', label: 'Cine' },
                    ].map((q) => (
                      <button
                        key={q.id}
                        type="button"
                        onClick={() => setQuality(q.id as QualityTier)}
                        className={`py-2 px-1 text-[11px] font-semibold rounded-xl capitalize transition text-center ${
                          quality === q.id
                            ? 'bg-indigo-600 text-white shadow-md'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                        }`}
                      >
                        {q.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Continuity Level */}
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Sliders className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Continuity Level</span>
                  </label>
                  <div className="grid grid-cols-3 gap-1 bg-slate-950/80 p-1 rounded-2xl border border-slate-800">
                    {[
                      { id: 'standard', label: 'Std' },
                      { id: 'high', label: 'Flow' },
                      { id: 'maximum', label: 'Max' },
                    ].map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => setContinuity(c.id as ContinuityLevel)}
                        className={`py-2 px-1 text-[11px] font-semibold rounded-xl capitalize transition text-center ${
                          continuity === c.id
                            ? 'bg-indigo-600 text-white shadow-md'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                        }`}
                      >
                        {c.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Engine Override */}
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Engine Strategy</span>
                  </label>
                  <select
                    value={preferredEngine}
                    onChange={(e) => setPreferredEngine(e.target.value)}
                    className="w-full bg-slate-950/80 border border-slate-800 focus:border-indigo-500 rounded-xl p-2.5 text-xs text-white focus:outline-none cursor-pointer"
                  >
                    <option value="">Auto (Intelligent Selection)</option>
                    {availableEngines.map((eng) => (
                      <option key={eng.engine_id} value={eng.engine_id}>
                        {eng.display_name} {!eng.is_available ? '(Offline/Stub)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Requirement Section 4: Aesthetic Style Palette */}
              <div className="space-y-2 pt-2 border-t border-slate-800/80">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <Palette className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Aesthetic Style Direction</span>
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {styleOptions.map((style) => (
                    <button
                      key={style.id}
                      type="button"
                      onClick={() => setGenerationStyle(style.id)}
                      className={`p-2.5 rounded-xl border text-left transition ${
                        generationStyle === style.id
                          ? 'bg-indigo-950/50 border-indigo-500 text-white shadow-lg'
                          : 'bg-slate-950/60 border-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                      }`}
                    >
                      <span className="text-xs font-bold block">{style.label}</span>
                      <span className="text-[10px] text-slate-500 block truncate">{style.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Real-time Capability Plan Resolution Banner */}
              {plan && (
                <div className="p-4 bg-slate-950/90 border border-indigo-900/60 rounded-2xl space-y-3 shadow-inner">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-indigo-400" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        Intelligent Engine Plan
                      </span>
                      {planLoading && <Loader2 className="w-3 h-3 text-indigo-400 animate-spin" />}
                    </div>

                    <div className="flex items-center gap-2">
                      {plan.satisfies_all ? (
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-800/80 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Optimal Fit</span>
                        </span>
                      ) : (
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-amber-950/80 text-amber-300 border border-amber-800/80 flex items-center gap-1">
                          <Info className="w-3 h-3" />
                          <span>Fallback Compromise</span>
                        </span>
                      )}

                      <button
                        type="button"
                        onClick={() => setShowDevPlan(!showDevPlan)}
                        className="text-[11px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-0.5 ml-2"
                      >
                        <span>{showDevPlan ? 'Hide Technical' : 'Inspect Plan'}</span>
                        {showDevPlan ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      </button>
                    </div>
                  </div>

                  <div className="text-xs text-slate-300 leading-relaxed">
                    <span className="font-semibold text-white">Engine Strategy: </span>
                    {plan.reason}
                  </div>

                  {plan.unsupported_requirements.length > 0 && (
                    <div className="p-2.5 bg-amber-950/30 border border-amber-800/50 rounded-xl text-[11px] text-amber-300 space-y-1">
                      <span className="font-bold block">Capability Notices:</span>
                      {plan.unsupported_requirements.map((item, idx) => (
                        <p key={idx}>• {item}</p>
                      ))}
                    </div>
                  )}

                  {/* Collapsible Developer / Technical Details */}
                  {showDevPlan && (
                    <div className="pt-3 border-t border-slate-900 space-y-2 text-[11px] text-slate-400 font-mono">
                      <div className="flex justify-between">
                        <span>Selected Engine ID:</span>
                        <span className="text-indigo-300 font-bold">{plan.selected_engine_id}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Target Model:</span>
                        <span className="text-purple-300">{plan.selected_model_type}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Sampling Steps:</span>
                        <span className="text-white">{plan.normalized_settings.num_inference_steps}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Frames Budget:</span>
                        <span className="text-white">{plan.normalized_settings.video_length}</span>
                      </div>
                      <div className="flex justify-between items-center pt-1">
                        <span>Seed Override:</span>
                        <input
                          type="number"
                          value={seed}
                          onChange={(e) => setSeed(Number(e.target.value))}
                          placeholder="-1"
                          className="w-24 bg-slate-900 border border-slate-800 rounded px-2 py-0.5 text-xs text-white"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Submit CTA */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={submitting || !prompt.trim()}
                  className="w-full py-4 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-2xl text-base transition-all duration-200 shadow-xl shadow-indigo-600/25 flex items-center justify-center gap-2.5 group"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Scheduling Generation Request...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5 group-hover:scale-110 transition-transform" />
                      <span>Generate AI Video</span>
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
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">Rendering in Progress</h3>
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
                  <span>Status: {currentActiveJob.status}</span>
                  <span>{new Date(currentActiveJob.created_at).toLocaleTimeString()}</span>
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
                    <span>Rendered Output</span>
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
                    Configure your scene requirements and click Generate to stream video previews here.
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
