import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

interface ProtectedRouteProps {
  children: React.ReactNode
  requiredRoles?: string[]
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, requiredRoles }) => {
  const { user, accessToken } = useAuthStore()
  const location = useLocation()

  // Not logged in
  if (!accessToken || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Check required roles
  if (requiredRoles && requiredRoles.length > 0) {
    const userRoles = user.roles?.map((role) => role.name) || []
    const hasRequiredRole = requiredRoles.some((role) => userRoles.includes(role))

    if (!hasRequiredRole) {
      return <Navigate to="/unauthorized" replace />
    }
  }

  return <>{children}</>
}

export default ProtectedRoute
