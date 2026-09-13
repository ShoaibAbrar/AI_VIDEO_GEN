import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useToastStore } from '../store/toastStore'
import { Video, Eye, EyeOff, Lock, User as UserIcon, Mail, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react'

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate()
  const { register, isLoading, error } = useAuthStore()
  const { addToast } = useToastStore()

  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    firstName: '',
    lastName: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})

  const validateForm = () => {
    const errors: Record<string, string> = {}

    if (!formData.username || formData.username.length < 3) {
      errors.username = 'Username must be at least 3 characters'
    }

    if (!formData.email || !formData.email.includes('@')) {
      errors.email = 'Please enter a valid email address'
    }

    if (!formData.password || formData.password.length < 8) {
      errors.password = 'Password must be at least 8 characters'
    }

    if (formData.password !== formData.confirmPassword) {
      errors.confirmPassword = 'Passwords do not match'
    }

    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) return

    try {
      await register(
        formData.username,
        formData.email,
        formData.password,
        formData.firstName,
        formData.lastName
      )
      addToast({
        type: 'success',
        title: 'Account Created',
        message: 'Your GenVid.AI account was created successfully. You can now sign in.',
      })
      navigate('/login', { replace: true })
    } catch (err: any) {
      const rawError = err.message || error || ''
      let friendlyMessage = 'Unable to create account. Username or email may already be taken.'
      if (rawError.includes('Network Error')) {
        friendlyMessage = 'Unable to connect to GenVid.AI servers.'
      }
      addToast({
        type: 'error',
        title: 'Registration Failed',
        message: friendlyMessage,
      })
    }
  }

  const handleInputChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    setValidationErrors((prev) => ({ ...prev, [field]: '' }))
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
        <Link to="/login" className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition">
          Already registered? Sign In &rarr;
        </Link>
      </div>

      {/* Main Card Container */}
      <div className="w-full max-w-md mx-auto my-8">
        <div className="bg-slate-900/90 backdrop-blur-2xl rounded-3xl shadow-2xl p-8 border border-slate-800/90 space-y-6">
          {/* Header */}
          <div className="text-center space-y-1.5">
            <h1 className="text-2xl font-bold text-white tracking-tight">Create Account</h1>
            <p className="text-slate-400 text-xs sm:text-sm">Join GenVid.AI Video Studio</p>
          </div>

          {/* Server Error Alert */}
          {error && (
            <div className="p-3.5 bg-rose-950/50 border border-rose-800/80 rounded-xl text-rose-200 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-3.5">
            {/* Username */}
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                Username
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => handleInputChange('username', e.target.value)}
                  className={`w-full px-4 py-2 pl-10 bg-slate-800/70 border rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 transition text-sm ${
                    validationErrors.username
                      ? 'border-rose-500 focus:ring-rose-500/20'
                      : 'border-slate-700/80 focus:border-indigo-500 focus:ring-indigo-500/20'
                  }`}
                  placeholder="Choose a username"
                  disabled={isLoading}
                />
                <UserIcon className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              </div>
              {validationErrors.username && (
                <p className="text-rose-400 text-xs mt-1">{validationErrors.username}</p>
              )}
            </div>

            {/* Email */}
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                Email
              </label>
              <div className="relative">
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => handleInputChange('email', e.target.value)}
                  className={`w-full px-4 py-2 pl-10 bg-slate-800/70 border rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 transition text-sm ${
                    validationErrors.email
                      ? 'border-rose-500 focus:ring-rose-500/20'
                      : 'border-slate-700/80 focus:border-indigo-500 focus:ring-indigo-500/20'
                  }`}
                  placeholder="name@example.com"
                  disabled={isLoading}
                />
                <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              </div>
              {validationErrors.email && (
                <p className="text-rose-400 text-xs mt-1">{validationErrors.email}</p>
              )}
            </div>

            {/* First & Last Name */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                  First Name
                </label>
                <input
                  type="text"
                  value={formData.firstName}
                  onChange={(e) => handleInputChange('firstName', e.target.value)}
                  className="w-full px-3.5 py-2 bg-slate-800/70 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 text-sm"
                  placeholder="John"
                  disabled={isLoading}
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                  Last Name
                </label>
                <input
                  type="text"
                  value={formData.lastName}
                  onChange={(e) => handleInputChange('lastName', e.target.value)}
                  className="w-full px-3.5 py-2 bg-slate-800/70 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 text-sm"
                  placeholder="Doe"
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={(e) => handleInputChange('password', e.target.value)}
                  className={`w-full px-4 py-2 pl-10 pr-10 bg-slate-800/70 border rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 transition text-sm ${
                    validationErrors.password
                      ? 'border-rose-500 focus:ring-rose-500/20'
                      : 'border-slate-700/80 focus:border-indigo-500 focus:ring-indigo-500/20'
                  }`}
                  placeholder="At least 8 characters"
                  disabled={isLoading}
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

            {/* Confirm Password */}
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                Confirm Password
              </label>
              <input
                type={showPassword ? 'text' : 'password'}
                value={formData.confirmPassword}
                onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
                className={`w-full px-4 py-2 bg-slate-800/70 border rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 transition text-sm ${
                  validationErrors.confirmPassword
                    ? 'border-rose-500 focus:ring-rose-500/20'
                    : 'border-slate-700/80 focus:border-indigo-500 focus:ring-indigo-500/20'
                }`}
                placeholder="Re-enter your password"
                disabled={isLoading}
              />
              {validationErrors.confirmPassword && (
                <p className="text-rose-400 text-xs mt-1">{validationErrors.confirmPassword}</p>
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
                  <span>Creating Account...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Create Account</span>
                </>
              )}
            </button>
          </form>

          {/* Login Link */}
          <p className="text-center text-slate-400 text-xs mt-4">
            Already have an account?{' '}
            <Link to="/login" className="text-indigo-400 hover:text-indigo-300 font-semibold transition">
              Sign in
            </Link>
          </p>
        </div>
      </div>

      {/* Footer */}
      <div className="text-center text-xs text-slate-500">
        GenVid.AI &copy; {new Date().getFullYear()} — Generation Engine: Wan2GP
      </div>
    </div>
  )
}

export default RegisterPage
