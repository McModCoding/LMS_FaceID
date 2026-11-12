import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { UserRole } from '../types/user'
import { Loader2 } from 'lucide-react'

interface PrivateRouteProps {
  children: React.ReactNode
  allowedRoles?: UserRole[]
}

const getHomePage = (role: string): string => {
  if (role === 'admin') return '/admin/dashboard'
  if (role === 'lecturer') return '/lecturer/dashboard'
  if (role === 'student') return '/student/dashboard'
  return '/login'
}

export const PrivateRoute: React.FC<PrivateRouteProps> = ({ children, allowedRoles }) => {
  const { user, isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-screen bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={getHomePage(user.role)} replace />
  }

  return <>{children}</>
}

export default PrivateRoute
