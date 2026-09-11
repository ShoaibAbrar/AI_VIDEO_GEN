import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import GenerationPage from './pages/GenerationPage'
import AdminPage from './pages/AdminPage'
import ProtectedRoute from './components/ProtectedRoute'
import { useAuthStore } from './store/authStore'

const UnauthorizedPage = () => (
  <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center">
    <div className="text-center">
      <h1 className="text-4xl font-bold text-white mb-4">403</h1>
      <p className="text-slate-300 text-lg mb-6">Access Denied</p>
      <p className="text-slate-400 mb-8">You don't have permission to access this page</p>
      <a href="/dashboard" className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold">
        Back to Dashboard
      </a>
    </div>
  </div>
)

const WelcomePage = () => {
  const { user, accessToken } = useAuthStore()

  // If already logged in, go to dashboard
  if (accessToken && user) {
    return <Navigate to="/dashboard" replace />
  }

  return <Navigate to="/login" replace />
}

function App() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/unauthorized" element={<UnauthorizedPage />} />

      {/* Protected Routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/dashboard/videos"
        element={
          <ProtectedRoute>
            <GenerationPage />
          </ProtectedRoute>
        }
      />

      {/* Admin Routes (Phase 3) */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute requiredRoles={['admin']}>
            <AdminPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/users"
        element={
          <ProtectedRoute requiredRoles={['admin']}>
            <AdminPage />
          </ProtectedRoute>
        }
      />

      {/* Root Redirect */}
      <Route path="/" element={<WelcomePage />} />

      {/* Catch all - 404 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App

