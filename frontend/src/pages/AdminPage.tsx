import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '../services/api'
import { useAuthStore } from '../store/authStore'
import { useToastStore } from '../store/toastStore'
import { UserSummary } from '../types'
import {
  Shield,
  UserPlus,
  Edit2,
  Lock,
  Search,
  Users
} from 'lucide-react'

const emptyCreateForm = {
  username: '',
  email: '',
  password: '',
  first_name: '',
  last_name: '',
}

export const AdminPage: React.FC = () => {
  const navigate = useNavigate()
  const { isAdmin } = useAuthStore()
  const { addToast } = useToastStore()

  const [users, setUsers] = useState<UserSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

  const [createForm, setCreateForm] = useState(emptyCreateForm)
  const [showCreateModal, setShowCreateModal] = useState(false)

  const [editingUserId, setEditingUserId] = useState<number | null>(null)
  const [editingForm, setEditingForm] = useState({ username: '', email: '', first_name: '', last_name: '' })

  const [passwordForm, setPasswordForm] = useState({ userId: null as number | null, password: '' })

  const loadUsers = async () => {
    try {
      const response = await apiClient.get('/admin/users')
      setUsers(response.data || [])
    } catch (err: any) {
      addToast({ type: 'error', title: 'Error', message: err.response?.data?.detail || 'Unable to load users' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!isAdmin()) {
      navigate('/unauthorized', { replace: true })
      return
    }
    loadUsers()
  }, [isAdmin, navigate])

  const handleCreateUser = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      const response = await apiClient.post('/admin/users', createForm)
      setUsers((prev) => [response.data, ...prev])
      setCreateForm(emptyCreateForm)
      setShowCreateModal(false)
      addToast({
        type: 'success',
        title: 'User Created',
        message: `Account for ${response.data.username} was created successfully.`,
      })
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to create user account'
      addToast({ type: 'error', title: 'Error', message: msg })
    }
  }

  const startEdit = (target: UserSummary) => {
    setEditingUserId(target.id)
    setEditingForm({
      username: target.username,
      email: target.email,
      first_name: target.first_name || '',
      last_name: target.last_name || '',
    })
  }

  const handleEditUser = async (event: React.FormEvent) => {
    event.preventDefault()
    if (editingUserId === null) return
    try {
      const response = await apiClient.patch(`/admin/users/${editingUserId}`, editingForm)
      setUsers((prev) => prev.map((u) => (u.id === editingUserId ? response.data : u)))
      setEditingUserId(null)
      addToast({ type: 'success', title: 'User Updated', message: 'Account details updated successfully.' })
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to update user'
      addToast({ type: 'error', title: 'Error', message: msg })
    }
  }

  const handleStatusToggle = async (userId: number, nextState: boolean) => {
    try {
      const response = await apiClient.patch(`/admin/users/${userId}/status`, { is_active: nextState })
      setUsers((prev) => prev.map((u) => (u.id === userId ? response.data : u)))
      addToast({
        type: 'info',
        title: 'Status Changed',
        message: `User account is now ${nextState ? 'Active' : 'Disabled'}.`,
      })
    } catch (err: any) {
      addToast({ type: 'error', title: 'Error', message: err.response?.data?.detail || 'Unable to change status' })
    }
  }

  const handleResetPassword = async (event: React.FormEvent) => {
    event.preventDefault()
    if (passwordForm.userId === null) return
    try {
      await apiClient.patch(`/admin/users/${passwordForm.userId}/password`, { password: passwordForm.password })
      setPasswordForm({ userId: null, password: '' })
      addToast({ type: 'success', title: 'Password Reset', message: 'User password reset successfully.' })
    } catch (err: any) {
      addToast({ type: 'error', title: 'Error', message: err.response?.data?.detail || 'Unable to reset password' })
    }
  }

  const handleRoleUpdate = async (userId: number, roleName: string) => {
    const target = users.find((u) => u.id === userId)
    if (!target) return

    const nextRoles = target.roles.some((r) => r.name === roleName)
      ? target.roles.filter((r) => r.name !== roleName).map((r) => r.name)
      : [...target.roles.map((r) => r.name), roleName]

    try {
      const response = await apiClient.patch(`/admin/users/${userId}/roles`, { roles: nextRoles })
      setUsers((prev) => prev.map((u) => (u.id === userId ? response.data : u)))
      addToast({ type: 'success', title: 'Roles Updated', message: `Updated roles for ${target.username}.` })
    } catch (err: any) {
      addToast({ type: 'error', title: 'Error', message: err.response?.data?.detail || 'Unable to update roles' })
    }
  }

  const filteredUsers = users.filter((u) => {
    const q = searchQuery.toLowerCase()
    return (
      u.username.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      `${u.first_name || ''} ${u.last_name || ''}`.toLowerCase().includes(q)
    )
  })

  if (!isAdmin()) return null

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
            <Shield className="w-6 h-6 text-purple-400" />
            <span>Admin Control Center</span>
          </h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Manage user accounts, assigned roles, credentials, and access privileges.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold rounded-xl text-xs transition shadow-lg shadow-purple-600/25 flex items-center gap-2 self-start sm:self-auto"
        >
          <UserPlus className="w-4 h-4" />
          <span>Create New User Account</span>
        </button>
      </div>

      {/* User Stats Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-1">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Registered</span>
          <p className="text-3xl font-extrabold text-white">{users.length}</p>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-1">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Active Users</span>
          <p className="text-3xl font-extrabold text-emerald-400">
            {users.filter((u) => u.is_active).length}
          </p>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-1">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Disabled Accounts</span>
          <p className="text-3xl font-extrabold text-rose-400">
            {users.filter((u) => !u.is_active).length}
          </p>
        </div>
      </div>

      {/* User Management Section */}
      <div className="bg-slate-900/90 border border-slate-800/90 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Users className="w-5 h-5 text-purple-400" />
            <span>User Accounts</span>
          </h2>

          <div className="relative w-full sm:w-72">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by name or email..."
              className="w-full pl-9 pr-4 py-2 bg-slate-950/70 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-xs"
            />
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-slate-400 text-xs animate-pulse">Loading user accounts...</div>
        ) : filteredUsers.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs">No user accounts found.</div>
        ) : (
          <div className="space-y-4">
            {filteredUsers.map((u) => (
              <div
                key={u.id}
                className="bg-slate-950/60 border border-slate-800 rounded-2xl p-5 space-y-4 hover:border-slate-700 transition"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <h3 className="text-base font-bold text-white">{u.username}</h3>
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${
                          u.is_active
                            ? 'bg-emerald-950/60 border-emerald-800/60 text-emerald-300'
                            : 'bg-rose-950/60 border-rose-800/60 text-rose-300'
                        }`}
                      >
                        {u.is_active ? 'Active' : 'Disabled'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">{u.email}</p>
                    <p className="text-[11px] text-slate-500 mt-1">
                      Registered: {u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/A'} • Last Login: {u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => startEdit(u)}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition border border-slate-700 flex items-center gap-1.5"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                      <span>Edit</span>
                    </button>

                    <button
                      onClick={() => handleStatusToggle(u.id, !u.is_active)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition border ${
                        u.is_active
                          ? 'bg-amber-950/50 hover:bg-amber-900/60 border-amber-800/60 text-amber-300'
                          : 'bg-emerald-950/50 hover:bg-emerald-900/60 border-emerald-800/60 text-emerald-300'
                      }`}
                    >
                      {u.is_active ? 'Disable' : 'Enable'}
                    </button>

                    <button
                      onClick={() => setPasswordForm({ userId: u.id, password: '' })}
                      className="px-3 py-1.5 bg-rose-950/50 hover:bg-rose-900/60 border border-rose-800/60 text-rose-300 rounded-lg text-xs font-semibold transition flex items-center gap-1.5"
                    >
                      <Lock className="w-3.5 h-3.5" />
                      <span>Reset Password</span>
                    </button>
                  </div>
                </div>

                {/* Role Chips */}
                <div className="pt-3 border-t border-slate-900 flex flex-wrap items-center gap-2">
                  <span className="text-[11px] text-slate-500 font-bold uppercase tracking-wider">Roles:</span>
                  {['user', 'manager', 'admin'].map((roleName) => {
                    const hasRole = u.roles.some((r) => r.name === roleName)
                    return (
                      <button
                        key={roleName}
                        type="button"
                        onClick={() => handleRoleUpdate(u.id, roleName)}
                        className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
                          hasRole
                            ? 'bg-purple-600 text-white shadow-sm'
                            : 'bg-slate-900 text-slate-400 border border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        {hasRole ? `✓ ${roleName}` : `+ ${roleName}`}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create User Modal / Card */}
      {showCreateModal && (
        <section className="bg-slate-900/95 border border-purple-800/80 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-4">
          <h2 className="text-xl font-bold text-white tracking-tight">Create New User Account</h2>
          <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input
              required
              className="w-full px-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-xs"
              value={createForm.username}
              onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
              placeholder="Username"
            />
            <input
              required
              type="email"
              className="w-full px-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-xs"
              value={createForm.email}
              onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
              placeholder="Email address"
            />
            <input
              required
              type="password"
              className="w-full px-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-xs"
              value={createForm.password}
              onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
              placeholder="Password (min 8 characters)"
            />
            <div className="grid grid-cols-2 gap-3">
              <input
                className="w-full px-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-xs"
                value={createForm.first_name}
                onChange={(e) => setCreateForm({ ...createForm, first_name: e.target.value })}
                placeholder="First Name"
              />
              <input
                className="w-full px-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 text-xs"
                value={createForm.last_name}
                onChange={(e) => setCreateForm({ ...createForm, last_name: e.target.value })}
                placeholder="Last Name"
              />
            </div>
            <div className="md:col-span-2 flex gap-3 pt-2">
              <button
                type="submit"
                className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded-xl text-xs transition"
              >
                Save Account
              </button>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-xl text-xs transition"
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      {/* Edit User Form Card */}
      {editingUserId !== null && (
        <section className="bg-slate-900/95 border border-purple-800/80 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-4">
          <h2 className="text-xl font-bold text-white tracking-tight">Edit Account Details</h2>
          <form onSubmit={handleEditUser} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input
              required
              className="w-full px-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-purple-500 text-xs"
              value={editingForm.username}
              onChange={(e) => setEditingForm({ ...editingForm, username: e.target.value })}
              placeholder="Username"
            />
            <input
              required
              type="email"
              className="w-full px-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-purple-500 text-xs"
              value={editingForm.email}
              onChange={(e) => setEditingForm({ ...editingForm, email: e.target.value })}
              placeholder="Email"
            />
            <input
              className="w-full px-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-purple-500 text-xs"
              value={editingForm.first_name}
              onChange={(e) => setEditingForm({ ...editingForm, first_name: e.target.value })}
              placeholder="First name"
            />
            <input
              className="w-full px-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-purple-500 text-xs"
              value={editingForm.last_name}
              onChange={(e) => setEditingForm({ ...editingForm, last_name: e.target.value })}
              placeholder="Last name"
            />
            <div className="md:col-span-2 flex gap-3 pt-2">
              <button
                type="submit"
                className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded-xl text-xs transition"
              >
                Save Details
              </button>
              <button
                type="button"
                onClick={() => setEditingUserId(null)}
                className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-xl text-xs transition"
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      {/* Password Reset Form Card */}
      {passwordForm.userId !== null && (
        <section className="bg-slate-900/95 border border-rose-800/80 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-4">
          <h2 className="text-xl font-bold text-white tracking-tight">Reset Password for User #{passwordForm.userId}</h2>
          <form onSubmit={handleResetPassword} className="flex flex-col sm:flex-row gap-3">
            <input
              required
              minLength={8}
              type="password"
              className="flex-1 px-4 py-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-rose-500 text-xs"
              value={passwordForm.password}
              onChange={(e) => setPasswordForm({ ...passwordForm, password: e.target.value })}
              placeholder="Enter new password (min 8 chars)"
            />
            <button
              type="submit"
              className="px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-xl text-xs transition"
            >
              Save Password
            </button>
            <button
              type="button"
              onClick={() => setPasswordForm({ userId: null, password: '' })}
              className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-xl text-xs transition"
            >
              Cancel
            </button>
          </form>
        </section>
      )}
    </div>
  )
}

export default AdminPage
