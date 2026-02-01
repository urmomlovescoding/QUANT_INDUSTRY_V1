/**
 * Register Page
 */
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Zap, AlertCircle, Loader2, Check } from 'lucide-react'
import { cn } from '@/utils/cn'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'

export function Register() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    organization_name: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const passwordRequirements = [
    { label: 'At least 8 characters', met: formData.password.length >= 8 },
    { label: 'Contains a number', met: /\d/.test(formData.password) },
    { label: 'Passwords match', met: formData.password === formData.confirmPassword && formData.confirmPassword.length > 0 },
  ]

  const allRequirementsMet = passwordRequirements.every((r) => r.met)

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!allRequirementsMet) {
      setError('Please meet all password requirements')
      return
    }

    setIsLoading(true)

    try {
      const response = await authApi.register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        organization_name: formData.organization_name,
      })

      if (response.ok && response.data) {
        setAuth(response.data.user, response.data.tokens)
        navigate('/dashboard', { replace: true })
      } else {
        setError(response.error?.message || 'Registration failed')
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

        {/* Register Card */}
        <div className="bg-background-secondary rounded-2xl border border-border p-8 shadow-xl">
          <h1 className="text-2xl font-bold text-foreground-primary mb-2">
            Create your account
          </h1>
          <p className="text-foreground-muted mb-6">
            Start your trading journey today
          </p>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-bearish/10 border border-bearish/20 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-bearish flex-shrink-0" />
              <span className="text-sm text-bearish">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground-secondary mb-1.5">
                  Full Name
                </label>
                <input
                  type="text"
                  name="full_name"
                  value={formData.full_name}
                  onChange={handleChange}
                  placeholder="John Doe"
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
                  Organization
                </label>
                <input
                  type="text"
                  name="organization_name"
                  value={formData.organization_name}
                  onChange={handleChange}
                  placeholder="Acme Trading"
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
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-1.5">
                Email
              </label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
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
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Create a strong password"
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

            <div>
              <label className="block text-sm font-medium text-foreground-secondary mb-1.5">
                Confirm Password
              </label>
              <input
                type="password"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="Confirm your password"
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

            {/* Password Requirements */}
            <div className="space-y-2 py-2">
              {passwordRequirements.map((req, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className={cn(
                    'w-4 h-4 rounded-full flex items-center justify-center',
                    req.met ? 'bg-bullish' : 'bg-background-tertiary'
                  )}>
                    {req.met && <Check className="w-3 h-3 text-black" />}
                  </div>
                  <span className={cn(
                    'text-xs',
                    req.met ? 'text-bullish' : 'text-foreground-muted'
                  )}>
                    {req.label}
                  </span>
                </div>
              ))}
            </div>

            <button
              type="submit"
              disabled={isLoading || !allRequirementsMet}
              className={cn(
                'w-full py-3 px-4 rounded-xl font-semibold',
                'bg-gradient-to-r from-accent-primary to-accent-secondary',
                'text-black hover:opacity-90',
                'focus:outline-none focus:ring-2 focus:ring-accent-primary/50',
                'transition-all duration-200',
                'flex items-center justify-center gap-2',
                (isLoading || !allRequirementsMet) && 'opacity-70 cursor-not-allowed'
              )}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Creating account...
                </>
              ) : (
                'Create account'
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <span className="text-foreground-muted">Already have an account? </span>
            <Link
              to="/login"
              className="text-accent-primary hover:text-accent-secondary font-medium transition-colors"
            >
              Sign in
            </Link>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-foreground-muted mt-6">
          By creating an account, you agree to our Terms of Service and Privacy Policy
        </p>
      </div>
    </div>
  )
}
