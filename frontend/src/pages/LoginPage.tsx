import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

export const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, isLoading, error } = useAuthStore()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})

  const validateForm = () => {
    const errors: Record<string, string> = {}

    if (!username || username.trim().length < 3) {
      errors.username = 'Username must be at least 3 characters'
    }

    if (!password || password.length < 8) {
      errors.password = 'Password must be at least 8 characters'
    }

    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) {
      return
    }

    try {
      await login(username, password)
      const from = (location.state as any)?.from?.pathname || '/dashboard'
      navigate(from)
    } catch (err) {
      // Error is already set in the store
    }
  }

  const handleRegisterClick = () => {
    navigate('/register')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="bg-slate-800 rounded-lg shadow-2xl p-8 border border-slate-700">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">🎬 Wan2GP</h1>
            <p className="text-slate-300">Sign in to your account</p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-900 bg-opacity-30 border border-red-700 rounded text-red-200 text-sm">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username */}
            <div>
              <label className="block text-sm font-medium text-slate-200 mb-2">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value)
                  setValidationErrors({ ...validationErrors, username: '' })
                }}
                className={`w-full px-4 py-2 bg-slate-700 border rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 ${
                  validationErrors.username ? 'border-red-500 focus:ring-red-500' : 'border-slate-600 focus:ring-blue-500'
                }`}
                placeholder="username"
                disabled={isLoading}
              />
              {validationErrors.username && (
                <p className="text-red-400 text-sm mt-1">{validationErrors.username}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-slate-200 mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  setValidationErrors({ ...validationErrors, password: '' })
                }}
                className={`w-full px-4 py-2 bg-slate-700 border rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 ${
                  validationErrors.password ? 'border-red-500 focus:ring-red-500' : 'border-slate-600 focus:ring-blue-500'
                }`}
                placeholder="password"
                disabled={isLoading}
              />
              {validationErrors.password && (
                <p className="text-red-400 text-sm mt-1">{validationErrors.password}</p>
              )}
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-6 py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white font-semibold rounded transition duration-200"
            >
              {isLoading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-600"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-slate-800 text-slate-400">or</span>
            </div>
          </div>

          {/* Register Link */}
          <button
            type="button"
            onClick={handleRegisterClick}
            className="w-full py-2 px-4 border border-slate-600 hover:border-slate-500 text-slate-300 hover:text-white font-semibold rounded transition duration-200"
          >
            Create an account
          </button>

          {/* Footer */}
          <p className="text-center text-slate-400 text-sm mt-6">
            Demo credentials: user/password (when available)
          </p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
