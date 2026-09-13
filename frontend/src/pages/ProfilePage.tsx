import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { User, Shield, LogOut, CheckCircle2 } from 'lucide-react'

export const ProfilePage: React.FC = () => {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
          <User className="w-6 h-6 text-indigo-400" />
          <span>Account Profile & Settings</span>
        </h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Manage your GenVid.AI account details and assigned permissions.
        </p>
      </div>

      {/* Main Profile Card */}
      <div className="bg-slate-900/90 border border-slate-800/90 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
        <div className="flex items-center gap-4 border-b border-slate-800 pb-6">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-500 via-purple-600 to-pink-500 flex items-center justify-center text-white font-extrabold text-2xl shadow-xl shadow-indigo-500/20">
            {user?.username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">{user?.username}</h2>
            <p className="text-xs text-slate-400">{user?.email}</p>
            <div className="flex items-center gap-2 mt-2">
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 text-[11px] font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                <span>Account Active</span>
              </span>
            </div>
          </div>
        </div>

        {/* Account Details Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-2xl space-y-1">
            <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Username</span>
            <p className="text-sm font-semibold text-white">{user?.username}</p>
          </div>

          <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-2xl space-y-1">
            <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Email Address</span>
            <p className="text-sm font-semibold text-white">{user?.email}</p>
          </div>

          <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-2xl space-y-1">
            <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">First Name</span>
            <p className="text-sm font-semibold text-white">{user?.first_name || 'Not set'}</p>
          </div>

          <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-2xl space-y-1">
            <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Last Name</span>
            <p className="text-sm font-semibold text-white">{user?.last_name || 'Not set'}</p>
          </div>
        </div>

        {/* Assigned Roles */}
        <div className="space-y-3 pt-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-300 block">
            Assigned Roles & Access Privileges
          </span>
          <div className="flex flex-wrap gap-2">
            {user?.roles && user.roles.length > 0 ? (
              user.roles.map((role) => (
                <span
                  key={role.id}
                  className="px-3 py-1 rounded-xl bg-indigo-950/60 border border-indigo-700/60 text-indigo-300 text-xs font-semibold flex items-center gap-1.5"
                >
                  <Shield className="w-3.5 h-3.5" />
                  <span>{role.name}</span>
                </span>
              ))
            ) : (
              <span className="text-xs text-slate-500">Standard User</span>
            )}
          </div>
        </div>

        {/* Sign Out Action */}
        <div className="pt-4 border-t border-slate-800 flex justify-between items-center">
          <span className="text-xs text-slate-500">GenVid.AI Account Security</span>
          <button
            onClick={handleLogout}
            className="px-5 py-2.5 bg-rose-950/60 hover:bg-rose-900/80 border border-rose-800/80 text-rose-200 font-semibold rounded-xl text-xs transition flex items-center gap-2"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out of GenVid.AI</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default ProfilePage
