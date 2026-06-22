import { useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import { Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'

interface ProtectedRouteProps {
  children: ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { token, user, isLoading, checkAuth } = useAuthStore()

  useEffect(() => {
    if (token && !user && !isLoading) {
      checkAuth()
    }
  }, [token, user, isLoading, checkAuth])

  // No token at all — redirect to login
  if (!token) {
    return <Navigate to="/login" replace />
  }

  // Token exists but still loading / validating
  if (isLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    )
  }

  return <>{children}</>
}
