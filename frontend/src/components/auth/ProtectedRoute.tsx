/**
 * Protected Route - Redirects to login if not authenticated or token expired
 */
import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { Loader2 } from 'lucide-react'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, isTokenExpired, logout } = useAuthStore()
  const location = useLocation()

  // Check for expired tokens on mount and periodically
  useEffect(() => {
    if (isAuthenticated && isTokenExpired()) {
      logout()
    }

    // Periodically check token expiry (every 60 seconds)
    const interval = setInterval(() => {
      if (isAuthenticated && isTokenExpired()) {
        logout()
      }
    }, 60000)

    return () => clearInterval(interval)
  }, [isAuthenticated, isTokenExpired, logout])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background-primary">
        <Loader2 className="w-8 h-8 text-accent-primary animate-spin" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
