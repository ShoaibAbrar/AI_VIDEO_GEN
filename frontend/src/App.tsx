import { Routes, Route, Navigate, Link } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import GenerationPage from './pages/GenerationPage'
import HistoryPage from './pages/HistoryPage'
import ProfilePage from './pages/ProfilePage'
import AdminPage from './pages/AdminPage'
import ProtectedRoute from './components/ProtectedRoute'
import { AppLayout } from './components/AppLayout'
import { ShieldAlert, ArrowLeft } from 'lucide-react'

const UnauthorizedPage = () => (
  <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 text-slate-100 antialiased">
    <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 max-w-md w-full text-center space-y-4 shadow-2xl">
      <div className="w-12 h-12 rounded-2xl bg-rose-950/60 border border-rose-800/80 flex items-center justify-center text-rose-400 mx-auto">
        <ShieldAlert className="w-6 h-6" />
      </div>
      <h1 className="text-3xl font-extrabold text-white">403</h1>
      <h2 className="text-lg font-bold text-slate-200">Access Denied</h2>
      <p className="text-xs text-slate-400 leading-relaxed">
        You don't have permission to access the requested administrator resource.
      </p>
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl text-xs transition"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Return to Dashboard</span>
      </Link>
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

      {/* Protected Routes Wrapped in Universal AppLayout */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <AppLayout title="Dashboard">
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
        path="/generate"
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
            <AppLayout title="Profile & Settings">
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
            <AppLayout title="Admin Control Center">
              <AdminPage />
            </AppLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/users"
        element={
          <ProtectedRoute requiredRoles={['admin']}>
            <AppLayout title="Admin Control Center">
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
