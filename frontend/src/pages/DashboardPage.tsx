import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate()
  const { user, logout, isAdmin } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
      {/* Header */}
      <header className="bg-black bg-opacity-50 border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-white">🎬 Wan2GP Platform</h1>
          <div className="flex items-center gap-4">
            <span className="text-slate-300">Welcome, {user?.username}!</span>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded font-semibold transition"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-12">
        {/* User Info Card */}
        <div className="bg-slate-800 rounded-lg shadow-xl p-8 mb-8 border border-slate-700">
          <h2 className="text-2xl font-bold text-white mb-6">Profile Information</h2>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="text-slate-400 text-sm mb-1">Username</p>
              <p className="text-white text-lg font-semibold">{user?.username}</p>
            </div>
            <div>
              <p className="text-slate-400 text-sm mb-1">Email</p>
              <p className="text-white text-lg font-semibold">{user?.email}</p>
            </div>
            <div>
              <p className="text-slate-400 text-sm mb-1">Full Name</p>
              <p className="text-white text-lg font-semibold">
                {user?.first_name || 'N/A'} {user?.last_name || ''}
              </p>
            </div>
            <div>
              <p className="text-slate-400 text-sm mb-1">Roles</p>
              <div className="flex gap-2">
                {user?.roles && user.roles.length > 0 ? (
                  user.roles.map((role) => (
                    <span
                      key={role.id}
                      className="px-3 py-1 bg-blue-900 text-blue-200 rounded-full text-sm font-semibold"
                    >
                      {role.name}
                    </span>
                  ))
                ) : (
                  <span className="text-slate-400">No roles assigned</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* User Dashboard */}
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-slate-600 transition">
            <h3 className="text-xl font-bold text-white mb-3">📊 User Dashboard</h3>
            <p className="text-slate-300 mb-4">View your video generation jobs and history</p>
            <button
              onClick={() => navigate('/dashboard/videos')}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold transition"
            >
              Go to Dashboard
            </button>
          </div>

          {/* Admin Panel */}
          {isAdmin() && (
            <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-slate-600 transition">
              <h3 className="text-xl font-bold text-white mb-3">⚙️ Admin Panel</h3>
              <p className="text-slate-300 mb-4">Manage users, roles, and system settings</p>
              <button
                onClick={() => navigate('/admin')}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded font-semibold transition"
              >
                Open Admin Panel
              </button>
            </div>
          )}
        </div>

        <div className="mt-8 bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h3 className="text-lg font-bold text-white mb-4">Generation status</h3>
          <p className="text-slate-300">Submit and monitor real Wan2GP generations from the video dashboard.</p>
        </div>
      </main>
    </div>
  )
}

export default DashboardPage
