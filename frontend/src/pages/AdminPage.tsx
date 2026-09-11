import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '@/services/api'
import { useAuthStore } from '@/store/authStore'

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
  const { user, logout, isAdmin } = useAuthStore()
  const [users, setUsers] = useState<UserSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [createForm, setCreateForm] = useState(emptyCreateForm)
  const [editingUserId, setEditingUserId] = useState<number | null>(null)
  const [editingForm, setEditingForm] = useState({ username: '', email: '', first_name: '', last_name: '' })
  const [passwordForm, setPasswordForm] = useState({ userId: null as number | null, password: '' })

  const loadUsers = async () => {
    try {
      const response = await apiClient.get('/admin/users')
      setUsers(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to load users')
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

  const handleLogout = async () => {
    try {
      await apiClient.post('/auth/logout')
    } catch {
      // Ignore logout errors; client-side state is still cleared.
    }
    logout()
    navigate('/login', { replace: true })
  }

  const handleCreateUser = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      const response = await apiClient.post('/admin/users', createForm)
      setUsers((prev) => [response.data, ...prev])
      setCreateForm(emptyCreateForm)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to create user')
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
      setUsers((prev) => prev.map((user) => (user.id === editingUserId ? response.data : user)))
      setEditingUserId(null)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to edit user')
    }
  }

  const handleStatusToggle = async (userId: number, nextState: boolean) => {
    try {
      const response = await apiClient.patch(`/admin/users/${userId}/status`, { is_active: nextState })
      setUsers((prev) => prev.map((user) => (user.id === userId ? response.data : user)))
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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to reset password')
    }
  }

  const handleRoleUpdate = async (userId: number, roleName: string) => {
    const target = users.find((u) => u.id === userId)
    if (!target) return

    const nextRoles = target.roles.some((r) => r.name === roleName)
      ? target.roles.filter((r) => r.name !== roleName).map((r) => r.name)
      : [...target.roles.map((r) => r.name), roleName]

    try {
      const response = await apiClient.patch(`/admin/users/${userId}/roles`, {
        roles: nextRoles,
      })
      setUsers((prev) => prev.map((u) => (u.id === userId ? response.data : u)))
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to update roles')
    }
  }

  if (!isAdmin()) {
    return null
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
      <header className="bg-black bg-opacity-50 border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-white">⚙️ Admin Dashboard</h1>
          <div className="flex items-center gap-4">
            <span className="text-slate-300">Signed in as {user?.username}</span>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded font-semibold transition"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10 space-y-8">
        {error && (
          <div className="p-4 bg-red-900 bg-opacity-30 border border-red-700 rounded text-red-200 text-sm">
            {error}
          </div>
        )}

        <section className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-xl font-bold text-white mb-5">Create User</h2>
          <form onSubmit={handleCreateUser} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input className="..." value={createForm.username} onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })} placeholder="Username" />
            <input className="..." value={createForm.email} onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })} placeholder="Email" type="email" />
            <input className="..." value={createForm.password} onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })} placeholder="Password" type="password" />
            <input className="..." value={createForm.first_name} onChange={(e) => setCreateForm({ ...createForm, first_name: e.target.value })} placeholder="First name" />
            <input className="..." value={createForm.last_name} onChange={(e) => setCreateForm({ ...createForm, last_name: e.target.value })} placeholder="Last name" />
            <div className="md:col-span-2"><button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold">Create User</button></div>
          </form>
        </section>

        <section className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-xl font-bold text-white mb-5">Users</h2>
          {loading ? (
            <p className="text-slate-300">Loading users...</p>
          ) : users.length === 0 ? (
            <p className="text-slate-300">No users found</p>
          ) : (
            <div className="space-y-4">
              {users.map((userItem) => (
                <div key={userItem.id} className="bg-slate-700 rounded-lg p-4 border border-slate-600">
                  <div className="flex flex-col md:flex-row md:justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-white">{userItem.username}</h3>
                      <p className="text-slate-300">{userItem.email}</p>
                      <p className="text-slate-400 text-sm">Status: {userItem.is_active ? 'Active' : 'Disabled'} | Created: {userItem.created_at ? new Date(userItem.created_at).toLocaleDateString() : 'N/A'} | Last login: {userItem.last_login ? new Date(userItem.last_login).toLocaleString() : 'Never'}</p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button onClick={() => startEdit(userItem)} className="px-3 py-1 bg-slate-900 text-slate-200 rounded">Edit</button>
                      <button onClick={() => handleStatusToggle(userItem.id, !userItem.is_active)} className={`px-3 py-1 rounded ${userItem.is_active ? 'bg-yellow-600 text-white' : 'bg-green-600 text-white'}`}>
                        {userItem.is_active ? 'Disable' : 'Enable'}
                      </button>
                      <button onClick={() => setPasswordForm({ userId: userItem.id, password: '' })} className="px-3 py-1 bg-red-600 text-white rounded">Reset Password</button>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {['user', 'manager', 'admin'].map((roleName) => {
                      const hasRole = userItem.roles.some((role) => role.name === roleName)
                      return (
                        <button
                          key={roleName}
                          type="button"
                          onClick={() => handleRoleUpdate(userItem.id, roleName)}
                          className={`px-3 py-1 rounded-full text-sm font-semibold transition ${
                            hasRole ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300 border border-slate-600 hover:border-slate-500'
                          }`}
                        >
                          {roleName}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {editingUserId !== null && (
          <section className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-xl font-bold text-white mb-5">Edit User</h2>
            <form onSubmit={handleEditUser} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input className="..." value={editingForm.username} onChange={(e) => setEditingForm({ ...editingForm, username: e.target.value })} placeholder="Username" />
              <input className="..." value={editingForm.email} onChange={(e) => setEditingForm({ ...editingForm, email: e.target.value })} placeholder="Email" type="email" />
              <input className="..." value={editingForm.first_name} onChange={(e) => setEditingForm({ ...editingForm, first_name: e.target.value })} placeholder="First name" />
              <input className="..." value={editingForm.last_name} onChange={(e) => setEditingForm({ ...editingForm, last_name: e.target.value })} placeholder="Last name" />
              <div className="md:col-span-2 flex gap-3"><button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold">Save Changes</button><button type="button" onClick={() => setEditingUserId(null)} className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded font-semibold">Cancel</button></div>
            </form>
          </section>
        )}

        {passwordForm.userId !== null && (
          <section className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-xl font-bold text-white mb-5">Reset Password</h2>
            <form onSubmit={handleResetPassword} className="flex flex-col md:flex-row gap-3">
              <input className="..." type="password" value={passwordForm.password} onChange={(e) => setPasswordForm({ ...passwordForm, password: e.target.value })} placeholder="New password" />
              <button type="submit" className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded font-semibold">Save New Password</button>
              <button type="button" onClick={() => setPasswordForm({ userId: null, password: '' })} className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded font-semibold">Cancel</button>
            </form>
          </section>
        )}
      </main>
    </div>
  )
}

export default AdminPage
