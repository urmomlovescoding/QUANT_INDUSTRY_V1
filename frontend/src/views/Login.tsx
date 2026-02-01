/**
 * Login Page
 */
import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Eye, EyeOff, Zap, AlertCircle, Loader2 } from 'lucide-react'
import { cn } from '@/utils/cn'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'

export function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const setAuth = useAuthStore((s) => s.setAuth)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const from = (location.state as any)?.from?.pathname || '/dashboard'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      const response = await authApi.login({ email, password })

      if (response.ok && response.data) {
        setAuth(response.data.user, response.data.tokens)
        navigate(from, { replace: true })
      } else {
        setError(response.error?.message || 'Login failed')
      }
    } catch (err) {
      setError('An unexpected error occurred')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background-primary p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className={cn(
            'w-12 h-12 rounded-xl flex items-center justify-center',
            'bg-gradient-to-br from-accent-secondary to-accent-primary',
            'shadow-lg shadow-accent-primary/20'
          )}>
            <Zap className="w-7 h-7 text-black" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-xl text-foreground-primary tracking-tight">
              STOCK SUITE
            </span>
            <span className="text-xs text-accent-primary font-semibold tracking-wider">
              PRO v10.0 QUANT
            </span>
          </div>
        </div>

        {/* Login Card */}
        <div className="bg-background-secondary rounded-2xl border border-border p-8 shadow-xl">
          <h1 className="text-2xl font-bold text-foreground-primary mb-2">
            Welcome back
          </h1>
          <p className="text-foreground-muted mb-6">
            Sign in to access your trading dashboard
          </p>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-bearish/10 border border-bearish/20 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-bearish flex-shrink-0" />
              <span className="text-sm text-bearish">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                className={cn(
                  'w-full px-4 py-3 rounded-xl',
                  'bg-background-primary border border-border',
                  'text-foreground-primary placeholder:text-foreground-muted/50',
                  'focus:outline-none focus:ring-2 focus:ring-accent-primary/50 focus:border-accent-primary',
                  'transition-all duration-200'
                )}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  className={cn(
                    'w-full px-4 py-3 pr-12 rounded-xl',
                    'bg-background-primary border border-border',
                    'text-foreground-primary placeholder:text-foreground-muted/50',
                    'focus:outline-none focus:ring-2 focus:ring-accent-primary/50 focus:border-accent-primary',
                    'transition-all duration-200'
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-foreground-muted hover:text-foreground-primary transition-colors"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className={cn(
                'w-full py-3 px-4 rounded-xl font-semibold',
                'bg-gradient-to-r from-accent-primary to-accent-secondary',
                'text-black hover:opacity-90',
                'focus:outline-none focus:ring-2 focus:ring-accent-primary/50',
                'transition-all duration-200',
                'flex items-center justify-center gap-2',
                isLoading && 'opacity-70 cursor-not-allowed'
              )}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Signing in...
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <span className="text-foreground-muted">Don't have an account? </span>
            <Link
              to="/register"
              className="text-accent-primary hover:text-accent-secondary font-medium transition-colors"
            >
              Sign up
            </Link>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-foreground-muted mt-6">
          By signing in, you agree to our Terms of Service and Privacy Policy
        </p>
      </div>
    </div>
  )
}
