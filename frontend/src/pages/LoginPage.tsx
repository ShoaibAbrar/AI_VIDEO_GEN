import React, { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useToastStore } from '../store/toastStore'
import { Video, Eye, EyeOff, Lock, User as UserIcon, ArrowRight, AlertCircle, Loader2 } from 'lucide-react'

export const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, isLoading, error } = useAuthStore()
  const { addToast } = useToastStore()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})

  const validateForm = () => {
    const errors: Record<string, string> = {}

    if (!username || username.trim().length < 3) {
      errors.username = 'Please enter your username'
    }

    if (!password || password.length < 1) {
      errors.password = 'Please enter your password'
    }

    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) return

    try {
      await login(username, password)
      addToast({
        type: 'success',
        title: 'Welcome back!',
        message: 'Successfully signed into GenVid.AI Studio',
      })
      const from = (location.state as any)?.from?.pathname || '/dashboard'
      navigate(from, { replace: true })
    } catch (err: any) {
      // User-friendly error message mapping
      const rawError = err.message || error || ''
      let friendlyMessage = 'Invalid username or password. Please try again.'
      if (rawError.includes('Network Error') || rawError.includes('500')) {
        friendlyMessage = 'Unable to connect to GenVid.AI servers. Please check backend network.'
      }
      addToast({
        type: 'error',
        title: 'Authentication Failed',
        message: friendlyMessage,
      })
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(99,102,241,0.2),rgba(255,255,255,0))] flex flex-col justify-between p-6 text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
      {/* Top Header */}
      <div className="max-w-7xl w-full mx-auto flex justify-between items-center">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
            <Video className="w-5 h-5 stroke-[2.5]" />
          </div>
          <span className="text-xl font-bold text-white tracking-tight">
            GenVid<span className="text-indigo-400 font-black">.AI</span>
          </span>
        </Link>
        <Link to="/register" className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition">
          Create Account &rarr;
        </Link>
      </div>

      {/* Main Card Container */}
      <div className="w-full max-w-md mx-auto my-12">
        <div className="bg-slate-900/90 backdrop-blur-2xl rounded-3xl shadow-2xl p-8 sm:p-10 border border-slate-800/90 space-y-6">
          {/* Header */}
          <div className="text-center space-y-2">
            <h1 className="text-2xl font-bold text-white tracking-tight">Welcome to GenVid.AI</h1>
            <p className="text-slate-400 text-xs sm:text-sm">Sign in to access your AI Video Studio</p>
          </div>

          {/* User-Friendly Error Alert */}
          {error && (
            <div className="p-3.5 bg-rose-950/50 border border-rose-800/80 rounded-xl text-rose-200 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>
                {error.includes('401') || error.toLowerCase().includes('credential')
                  ? 'Invalid username or password. Please verify and try again.'
                  : error}
              </span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username */}
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1.5">
                Username
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value)
                    setValidationErrors({ ...validationErrors, username: '' })
                  }}
                  className={`w-full px-4 py-2.5 pl-10 bg-slate-800/70 border rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 transition text-sm ${
                    validationErrors.username
                      ? 'border-rose-500 focus:ring-rose-500/20'
                      : 'border-slate-700/80 focus:border-indigo-500 focus:ring-indigo-500/20'
                  }`}
                  placeholder="Enter your username"
                  disabled={isLoading}
                  autoComplete="username"
                />
                <UserIcon className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              </div>
              {validationErrors.username && (
                <p className="text-rose-400 text-xs mt-1">{validationErrors.username}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300">
                  Password
                </label>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    setValidationErrors({ ...validationErrors, password: '' })
                  }}
                  className={`w-full px-4 py-2.5 pl-10 pr-10 bg-slate-800/70 border rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 transition text-sm ${
                    validationErrors.password
                      ? 'border-rose-500 focus:ring-rose-500/20'
                      : 'border-slate-700/80 focus:border-indigo-500 focus:ring-indigo-500/20'
                  }`}
                  placeholder="Enter your password"
                  disabled={isLoading}
                  autoComplete="current-password"
                />
                <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {validationErrors.password && (
                <p className="text-rose-400 text-xs mt-1">{validationErrors.password}</p>
              )}
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 py-3 px-4 bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 text-white font-semibold rounded-xl transition-all duration-200 shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 text-sm"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-800"></div>
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-3 bg-slate-900 text-slate-500">New to GenVid.AI?</span>
            </div>
          </div>

          {/* Register Link */}
          <Link
            to="/register"
            className="w-full py-2.5 px-4 border border-slate-700/80 hover:border-slate-600 hover:bg-slate-800/50 text-slate-300 hover:text-white font-medium rounded-xl transition duration-200 text-xs text-center block"
          >
            Create your GenVid.AI account
          </Link>
        </div>
      </div>

      {/* Footer */}
      <div className="text-center text-xs text-slate-500">
        GenVid.AI &copy; {new Date().getFullYear()} — Generation Engine: Wan2GP
      </div>
    </div>
  )
}

export default LoginPage
