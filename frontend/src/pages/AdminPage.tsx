import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '@/services/api'
import { useAuthStore } from '@/store/authStore'
import { useToastStore } from '@/store/toastStore'
import {
  Shield,
  UserPlus,
  Edit2,
  KeyRound,
  CheckCircle2,
  XCircle,
  Search,
  RefreshCw,
  AlertCircle,
  Users
} from 'lucide-react'

interface RoleSummary {
  id: number
  name: string
  description?: string
}

interface UserSummary {
  id: number
  username: string
  email: string
  first_name?: string
  last_name?: string
  is_active: boolean
  created_at?: string
  last_login?: string | null
  roles: RoleSummary[]
}

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
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState(emptyCreateForm)
  const [editingUserId, setEditingUserId] = useState<number | null>(null)
  const [editingForm, setEditingForm] = useState({ username: '', email: '', first_name: '', last_name: '' })
  const [passwordForm, setPasswordForm] = useState({ userId: null as number | null, password: '' })

  const loadUsers = async () => {
    try {
      const response = await apiClient.get('/admin/users')
      setUsers(response.data || [])
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to load user registry')
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
      setError(null)
      addToast({
        type: 'success',
        title: 'User Created',
        message: `Account for ${response.data.username} created successfully.`,
      })
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to create user account'
      setError(msg)
      addToast({ type: 'error', title: 'Creation Failed', message: msg })
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
      setError(null)
      addToast({
        type: 'success',
        title: 'User Updated',
        message: `Updated profile details for ${response.data.username}.`,
      })
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to edit user'
      setError(msg)
      addToast({ type: 'error', title: 'Update Failed', message: msg })
    }
  }

  const handleStatusToggle = async (userId: number, nextState: boolean) => {
    try {
      const response = await apiClient.patch(`/admin/users/${userId}/status`, { is_active: nextState })
      setUsers((prev) => prev.map((u) => (u.id === userId ? response.data : u)))
      addToast({
        type: 'info',
        title: 'Status Changed',
        message: `User is now ${nextState ? 'Active' : 'Disabled'}.`,
      })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to update status')
    }
  }

  const handleResetPassword = async (event: React.FormEvent) => {
    event.preventDefault()
    if (passwordForm.userId === null) return
    try {
      await apiClient.patch(`/admin/users/${passwordForm.userId}/password`, { password: passwordForm.password })
      setPasswordForm({ userId: null, password: '' })
      setError(null)
      addToast({
        type: 'success',
        title: 'Password Reset',
        message: 'The user password was reset successfully.',
      })
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Unable to reset password'
      setError(msg)
      addToast({ type: 'error', title: 'Reset Failed', message: msg })
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
      setError(null)
      addToast({
        type: 'info',
        title: 'Roles Updated',
        message: `Updated roles for ${response.data.username}.`,
      })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to update roles')
    }
  }

  if (!isAdmin()) {
    return null
  }

  const filteredUsers = users.filter((u) => {
    const q = searchQuery.toLowerCase()
    return (
      u.username.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      (u.first_name && u.first_name.toLowerCase().includes(q)) ||
      (u.last_name && u.last_name.toLowerCase().includes(q))
    )
  })

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Admin Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
            <Shield className="w-6 h-6 text-indigo-400" />
            <span>Admin Center & User Management</span>
          </h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Manage user accounts, credentials, access controls, and monitor system resources.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadUsers}
            className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-slate-300 hover:text-white text-xs font-semibold flex items-center gap-2 transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setShowCreateModal(!showCreateModal)}
            className="px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-lg shadow-indigo-600/20 transition"
          >
            <UserPlus className="w-4 h-4" />
            <span>Add User</span>
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 bg-rose-950/60 border border-rose-800/80 rounded-2xl text-rose-200 text-xs flex items-start gap-2.5 shadow-lg">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Create User Form Drawer/Card */}
      {showCreateModal && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-5 animate-fadeIn">
          <div className="flex justify-between items-center border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2.5">
              <UserPlus className="w-5 h-5 text-indigo-400" />
              <h3 className="text-base font-bold text-white">Create New Platform User</h3>
            </div>
            <button
              onClick={() => setShowCreateModal(false)}
              className="text-slate-400 hover:text-white text-xs font-semibold"
            >
              Close
            </button>
          </div>

          <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Username *</label>
              <input
                required
                value={createForm.username}
                onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
                placeholder="johndoe"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Email Address *</label>
              <input
                required
                type="email"
                value={createForm.email}
                onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                placeholder="john@example.com"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Temporary Password *</label>
              <input
                required
                type="password"
                value={createForm.password}
                onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                placeholder="••••••••"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">First Name</label>
                <input
                  value={createForm.first_name}
                  onChange={(e) => setCreateForm({ ...createForm, first_name: e.target.value })}
                  placeholder="John"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Last Name</label>
                <input
                  value={createForm.last_name}
                  onChange={(e) => setCreateForm({ ...createForm, last_name: e.target.value })}
                  placeholder="Doe"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="md:col-span-2 pt-2 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-600/20"
              >
                Create Account
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Edit User Modal */}
      {editingUserId !== null && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-5 animate-fadeIn">
          <div className="flex justify-between items-center border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2.5">
              <Edit2 className="w-5 h-5 text-purple-400" />
              <h3 className="text-base font-bold text-white">Edit User Information</h3>
            </div>
            <button
              onClick={() => setEditingUserId(null)}
              className="text-slate-400 hover:text-white text-xs font-semibold"
            >
              Close
            </button>
          </div>

          <form onSubmit={handleEditUser} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Username</label>
              <input
                value={editingForm.username}
                onChange={(e) => setEditingForm({ ...editingForm, username: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Email Address</label>
              <input
                type="email"
                value={editingForm.email}
                onChange={(e) => setEditingForm({ ...editingForm, email: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">First Name</label>
              <input
                value={editingForm.first_name}
                onChange={(e) => setEditingForm({ ...editingForm, first_name: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Last Name</label>
              <input
                value={editingForm.last_name}
                onChange={(e) => setEditingForm({ ...editingForm, last_name: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="md:col-span-2 pt-2 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setEditingUserId(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-purple-600/20"
              >
                Save Changes
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Password Reset Modal */}
      {passwordForm.userId !== null && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-5 animate-fadeIn">
          <div className="flex justify-between items-center border-b border-slate-800 pb-4">
            <div className="flex items-center gap-2.5">
              <KeyRound className="w-5 h-5 text-pink-400" />
              <h3 className="text-base font-bold text-white">Reset User Password</h3>
            </div>
            <button
              onClick={() => setPasswordForm({ userId: null, password: '' })}
              className="text-slate-400 hover:text-white text-xs font-semibold"
            >
              Close
            </button>
          </div>

          <form onSubmit={handleResetPassword} className="space-y-4 max-w-md">
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">New Password</label>
              <input
                type="password"
                required
                value={passwordForm.password}
                onChange={(e) => setPasswordForm({ ...passwordForm, password: e.target.value })}
                placeholder="Enter new strong password"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-pink-500"
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                className="px-5 py-2 bg-pink-600 hover:bg-pink-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-pink-600/20"
              >
                Update Password
              </button>
              <button
                type="button"
                onClick={() => setPasswordForm({ userId: null, password: '' })}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Search Toolbar */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-lg">
        <div className="relative w-full sm:w-80">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search users by name, username, email..."
            className="w-full pl-9 pr-4 py-2 bg-slate-950/70 border border-slate-800 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 text-xs"
          />
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
        </div>

        <div className="text-xs text-slate-400 font-medium">
          Showing {filteredUsers.length} of {users.length} registered users
        </div>
      </div>

      {/* Users Table / List */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-bold text-white">Registered Platform Accounts</h2>
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-slate-500 text-xs animate-pulse">Loading accounts...</div>
        ) : filteredUsers.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-xs">No users matching search query.</div>
        ) : (
          <div className="divide-y divide-slate-800/80">
            {filteredUsers.map((userItem) => (
              <div key={userItem.id} className="py-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-white">{userItem.username}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex items-center gap-1 ${
                        userItem.is_active
                          ? 'bg-emerald-950/60 border border-emerald-800/60 text-emerald-300'
                          : 'bg-rose-950/60 border border-rose-800/60 text-rose-300'
                      }`}
                    >
                      {userItem.is_active ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                      <span>{userItem.is_active ? 'Active' : 'Disabled'}</span>
                    </span>
                  </div>

                  <p className="text-xs text-slate-400">{userItem.email}</p>

                  <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500 pt-1">
                    <span>
                      Name: {userItem.first_name || 'N/A'} {userItem.last_name || ''}
                    </span>
                    <span>·</span>
                    <span>Created: {userItem.created_at ? new Date(userItem.created_at).toLocaleDateString() : 'N/A'}</span>
                    <span>·</span>
                    <span>Last Login: {userItem.last_login ? new Date(userItem.last_login).toLocaleString() : 'Never'}</span>
                  </div>

                  {/* Role Pills */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-2">
                    <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider mr-1">Roles:</span>
                    {['user', 'manager', 'admin'].map((roleName) => {
                      const hasRole = userItem.roles.some((r) => r.name === roleName)
                      return (
                        <button
                          key={roleName}
                          type="button"
                          onClick={() => handleRoleUpdate(userItem.id, roleName)}
                          className={`px-2.5 py-0.5 rounded-lg text-[11px] font-semibold transition ${
                            hasRole
                              ? 'bg-indigo-600 text-white shadow-sm'
                              : 'bg-slate-950/80 text-slate-500 border border-slate-800 hover:border-slate-700 hover:text-slate-300'
                          }`}
                          title={`Toggle ${roleName} role`}
                        >
                          {hasRole ? `✓ ${roleName}` : `+ ${roleName}`}
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex flex-wrap items-center gap-2 self-start lg:self-center">
                  <button
                    onClick={() => startEdit(userItem)}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl text-xs font-semibold text-slate-200 transition flex items-center gap-1.5"
                  >
                    <Edit2 className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Edit</span>
                  </button>

                  <button
                    onClick={() => handleStatusToggle(userItem.id, !userItem.is_active)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition ${
                      userItem.is_active
                        ? 'bg-amber-950/40 hover:bg-amber-950/60 border-amber-800/60 text-amber-300'
                        : 'bg-emerald-950/40 hover:bg-emerald-950/60 border-emerald-800/60 text-emerald-300'
                    }`}
                  >
                    {userItem.is_active ? 'Disable' : 'Enable'}
                  </button>

                  <button
                    onClick={() => setPasswordForm({ userId: userItem.id, password: '' })}
                    className="px-3 py-1.5 bg-rose-950/40 hover:bg-rose-950/60 border border-rose-800/60 text-rose-300 rounded-xl text-xs font-semibold transition flex items-center gap-1.5"
                  >
                    <KeyRound className="w-3.5 h-3.5" />
                    <span>Reset Pass</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default AdminPage
