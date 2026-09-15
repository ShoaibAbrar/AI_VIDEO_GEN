import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import GenerationPage from './pages/GenerationPage'
import HistoryPage from './pages/HistoryPage'
import ProfilePage from './pages/ProfilePage'
import AdminPage from './pages/AdminPage'
import LandingPage from './pages/LandingPage'
import ProtectedRoute from './components/ProtectedRoute'
import { AppLayout } from './components/AppLayout'

const UnauthorizedPage = () => (
  <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 text-slate-100">
    <div className="text-center max-w-md bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-4">
      <h1 className="text-4xl font-black text-rose-500">403</h1>
      <p className="text-lg font-bold text-white">Access Denied</p>
      <p className="text-slate-400 text-xs">You do not have administrative permissions to view this resource.</p>
      <a href="/dashboard" className="inline-block px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition">
        Return to Dashboard
      </a>
    </div>
  </div>
)

function App() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/unauthorized" element={<UnauthorizedPage />} />

      {/* Protected Routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <AppLayout title="Studio Dashboard">
              <DashboardPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/dashboard/videos"
        element={
          <ProtectedRoute>
            <AppLayout title="AI Video Studio">
              <GenerationPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/history"
        element={
          <ProtectedRoute>
            <AppLayout title="Generation History">
              <HistoryPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <AppLayout title="Account Profile">
              <ProfilePage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      {/* Admin Routes */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute requiredRoles={['admin']}>
            <AppLayout title="Admin Management">
              <AdminPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/users"
        element={
          <ProtectedRoute requiredRoles={['admin']}>
            <AppLayout title="User Management">
              <AdminPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      {/* Catch all - 404 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App

