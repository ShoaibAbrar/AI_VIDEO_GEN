import React from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import {
  Video,
  Sparkles,
  Zap,
  Layers,
  History,
  ArrowRight,
  Play,
  Sliders,
  CheckCircle2,
  Cpu
} from 'lucide-react'

export const LandingPage: React.FC = () => {
  const navigate = useNavigate()
  const { accessToken, user } = useAuthStore()

  const isAuthenticated = Boolean(accessToken && user)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 antialiased selection:bg-indigo-500 selection:text-white flex flex-col">
      {/* Navbar */}
      <nav className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-600 to-pink-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/25">
              <Video className="w-5 h-5 stroke-[2.5]" />
            </div>
            <div>
              <span className="text-xl font-bold text-white tracking-tight">
                GenVid<span className="text-indigo-400 font-black">.AI</span>
              </span>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            <a href="#features" className="hover:text-white transition">Features</a>
            <a href="#models" className="hover:text-white transition">Models</a>
            <a href="#how-it-works" className="hover:text-white transition">How it Works</a>
          </div>

          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <button
                onClick={() => navigate('/dashboard')}
                className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-xl text-sm transition shadow-lg shadow-indigo-600/20 flex items-center gap-2"
              >
                <span>Open Studio</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-4 py-2 text-slate-300 hover:text-white font-medium text-sm transition"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl text-sm transition shadow-lg shadow-indigo-600/20"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden py-20 lg:py-28 px-6 max-w-7xl mx-auto w-full">
        {/* Subtle Background Glow */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-600/15 blur-[120px] rounded-full pointer-events-none"></div>

        <div className="text-center max-w-3xl mx-auto space-y-6 relative z-10">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-indigo-950/60 border border-indigo-800/60 rounded-full text-indigo-300 text-xs font-semibold shadow-sm">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>AI Video Generation, Reimagined.</span>
          </div>

          <h1 className="text-4xl sm:text-6xl font-black text-white tracking-tight leading-[1.15]">
            Create stunning AI videos from <span className="bg-gradient-to-r from-indigo-400 via-purple-300 to-pink-400 bg-clip-text text-transparent">simple ideas.</span>
          </h1>

          <p className="text-slate-400 text-base sm:text-lg leading-relaxed max-w-2xl mx-auto">
            GenVid.AI provides a unified workspace for AI video generation powered by state-of-the-art multi-model GPU inference engines.
          </p>

          <div className="pt-4 flex flex-wrap justify-center items-center gap-4">
            <button
              onClick={() => navigate(isAuthenticated ? '/dashboard/videos' : '/register')}
              className="px-8 py-4 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white font-bold rounded-xl text-base transition-all duration-200 shadow-xl shadow-indigo-600/30 flex items-center gap-3"
            >
              <span>{isAuthenticated ? 'Launch Video Studio' : 'Start Creating Now'}</span>
              <ArrowRight className="w-5 h-5" />
            </button>
            <a
              href="#models"
              className="px-6 py-4 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-200 font-semibold rounded-xl text-base transition flex items-center gap-2"
            >
              <span>Explore Capabilities</span>
            </a>
          </div>
        </div>

        {/* Visual Studio Representation */}
        <div className="mt-16 relative max-w-5xl mx-auto">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/90 shadow-2xl overflow-hidden backdrop-blur-xl">
            <div className="bg-slate-950/80 px-4 py-3 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-rose-500"></div>
                <div className="w-3 h-3 rounded-full bg-amber-500"></div>
                <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
                <span className="text-xs text-slate-400 font-mono ml-2">GenVid.AI Studio Workspace</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                <span>Multi-Model GPU Engine</span>
              </div>
            </div>

            <div className="p-6 md:p-8 grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="md:col-span-2 space-y-4">
                <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-2">
                  <span className="text-[10px] uppercase font-bold text-indigo-400 tracking-wider">Prompt Canvas</span>
                  <p className="text-sm text-slate-200 italic font-mono">
                    "A cinematic ultra-wide shot of a serene mountain lake at sunrise, mist floating over turquoise waters, photorealistic lighting 8k resolution..."
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800">
                    <span className="text-slate-500 block">Model Engine</span>
                    <span className="text-white font-semibold">Wan2GP Powered</span>
                  </div>
                  <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800">
                    <span className="text-slate-500 block">Sampling Steps</span>
                    <span className="text-white font-semibold">25 Steps</span>
                  </div>
                  <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800">
                    <span className="text-slate-500 block">Resolution</span>
                    <span className="text-white font-semibold">High Definition</span>
                  </div>
                </div>
              </div>

              <div className="bg-slate-950/90 border border-slate-800 rounded-xl p-4 flex flex-col items-center justify-center text-center space-y-3 min-h-[180px]">
                <div className="w-12 h-12 rounded-full bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
                  <Play className="w-5 h-5 fill-current ml-0.5" />
                </div>
                <div>
                  <span className="text-sm font-semibold text-white">Instant Video Preview</span>
                  <p className="text-xs text-slate-500 mt-0.5">MP4 video output with direct download</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-6 max-w-7xl mx-auto w-full border-t border-slate-900">
        <div className="text-center max-w-2xl mx-auto mb-16 space-y-3">
          <h2 className="text-3xl font-bold text-white tracking-tight">Built for Professional AI Creators</h2>
          <p className="text-slate-400 text-sm">Everything you need to prompt, iterate, render, and manage video generations.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 hover:border-indigo-500/40 transition">
            <div className="w-12 h-12 rounded-xl bg-indigo-950/80 border border-indigo-800/60 flex items-center justify-center text-indigo-400">
              <Layers className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-white">Multi-Model Engine</h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Access all supported Wan2GP video models through one unified user interface with dynamic model discovery.
            </p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 hover:border-indigo-500/40 transition">
            <div className="w-12 h-12 rounded-xl bg-purple-950/80 border border-purple-800/60 flex items-center justify-center text-purple-400">
              <Zap className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-white">Fast GPU Acceleration</h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Real-time progress monitoring and high-throughput GPU rendering pipelines with step-by-step feedback.
            </p>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 hover:border-indigo-500/40 transition">
            <div className="w-12 h-12 rounded-xl bg-pink-950/80 border border-pink-800/60 flex items-center justify-center text-pink-400">
              <History className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-white">Generation History</h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Keep your prompts, model parameters, and rendered MP4 files organized in your personal media vault.
            </p>
          </div>
        </div>
      </section>

      {/* Dynamic Model Overview Section */}
      <section id="models" className="py-20 px-6 max-w-7xl mx-auto w-full border-t border-slate-900 bg-slate-900/30">
        <div className="max-w-4xl mx-auto text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-purple-950/60 border border-purple-800/60 rounded-full text-purple-300 text-xs font-semibold">
            <Sliders className="w-3.5 h-3.5" />
            <span>Dynamic Discovery Architecture</span>
          </div>

          <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
            One Unified Workspace for Multiple Video Models
          </h2>

          <p className="text-slate-400 text-base leading-relaxed">
            GenVid.AI automatically discovers available model definitions from the underlying Wan2GP engine. Whether deployed with lightweight 1.3B models or full 14B production checkpoints, GenVid.AI renders model capabilities dynamically.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-6 text-left">
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <h4 className="font-semibold text-white text-sm">Automatic Model Detection</h4>
              <p className="text-xs text-slate-400">Discovers newly added model weights without needing frontend updates.</p>
            </div>
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <h4 className="font-semibold text-white text-sm">Checkpoint Readiness</h4>
              <p className="text-xs text-slate-400">Shows ready vs missing dependency status clearly before generation.</p>
            </div>
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <h4 className="font-semibold text-white text-sm">Fine-Grained Controls</h4>
              <p className="text-xs text-slate-400">Configure frames, sampling steps, and random seed parameters seamlessly.</p>
            </div>
          </div>
        </div>
      </section>

      {/* How it Works Section */}
      <section id="how-it-works" className="py-20 px-6 max-w-7xl mx-auto w-full border-t border-slate-900">
        <div className="text-center max-w-2xl mx-auto mb-16 space-y-3">
          <h2 className="text-3xl font-bold text-white tracking-tight">How GenVid.AI Works</h2>
          <p className="text-slate-400 text-sm">From text prompt to rendered MP4 video in four easy steps.</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            { step: '01', title: 'Describe Idea', desc: 'Write a detailed prompt describing your video concept and lighting.' },
            { step: '02', title: 'Choose Model', desc: 'Select any active video model discovered from the engine.' },
            { step: '03', title: 'Configure Settings', desc: 'Adjust video frames, sampling steps, and random seed.' },
            { step: '04', title: 'Generate & Download', desc: 'Watch real-time progress and download your final MP4 video.' }
          ].map((item) => (
            <div key={item.step} className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-3 relative">
              <span className="text-3xl font-black text-indigo-500/40">{item.step}</span>
              <h3 className="text-lg font-bold text-white">{item.title}</h3>
              <p className="text-xs text-slate-400 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Final CTA Banner */}
      <section className="py-16 px-6 max-w-7xl mx-auto w-full">
        <div className="bg-gradient-to-r from-indigo-950/80 via-purple-950/60 to-slate-900 border border-indigo-800/50 rounded-3xl p-10 text-center space-y-6 shadow-2xl">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white">Turn your ideas into video today.</h2>
          <p className="text-slate-300 text-sm max-w-xl mx-auto">
            Get started with GenVid.AI and harness multi-model AI video generation.
          </p>
          <div>
            <button
              onClick={() => navigate(isAuthenticated ? '/dashboard/videos' : '/register')}
              className="px-8 py-3.5 bg-white text-slate-950 font-bold rounded-xl text-sm hover:bg-slate-200 transition shadow-lg"
            >
              {isAuthenticated ? 'Open Video Studio' : 'Get Started for Free'}
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-900 py-10 px-6 max-w-7xl mx-auto w-full text-sm text-slate-500 flex flex-col sm:flex-row justify-between items-center gap-4 mt-auto">
        <div className="flex items-center gap-2">
          <span className="font-bold text-white">GenVid.AI</span>
          <span>&copy; {new Date().getFullYear()} — All rights reserved.</span>
        </div>
        <div className="flex items-center gap-6 text-xs">
          <span>Privacy Policy</span>
          <span>Terms of Service</span>
          <span>Engine: Wan2GP</span>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage
