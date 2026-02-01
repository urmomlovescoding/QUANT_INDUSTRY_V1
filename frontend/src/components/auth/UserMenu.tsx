/**
 * User Menu - Dropdown menu for authenticated user
 */
import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, LogOut, Settings, Building2, ChevronDown } from 'lucide-react'
import { cn } from '@/utils/cn'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/api/auth'

export function UserMenu() {
  const navigate = useNavigate()
  const { user, tokens, logout, isAuthenticated } = useAuthStore()
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close menu on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleLogout = async () => {
    if (tokens?.access_token) {
      await authApi.logout(tokens.access_token)
    }
    logout()
    navigate('/login')
  }

  if (!isAuthenticated || !user) {
    return (
      <button
        onClick={() => navigate('/login')}
        className={cn(
          'flex items-center gap-2 px-4 py-2 rounded-xl',
          'bg-gradient-to-r from-accent-primary to-accent-secondary',
          'text-black font-semibold text-sm',
          'hover:opacity-90 transition-opacity'
        )}
      >
        Sign in
      </button>
    )
  }

  const initials = user.full_name
    ? user.full_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : user.email[0].toUpperCase()

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center gap-2 px-2 py-1.5 rounded-xl',
          'hover:bg-background-hover/50 transition-colors',
          isOpen && 'bg-background-hover/50'
        )}
      >
        <div className={cn(
          'w-8 h-8 rounded-lg flex items-center justify-center',
          'bg-gradient-to-br from-accent-primary to-accent-secondary',
          'text-black font-bold text-sm'
        )}>
          {initials}
        </div>
        <div className="hidden md:flex flex-col items-start">
          <span className="text-sm font-medium text-foreground-primary leading-tight">
            {user.full_name || user.email}
          </span>
          <span className="text-[10px] text-foreground-muted leading-tight">
            {user.organization_name}
          </span>
        </div>
        <ChevronDown className={cn(
          'w-4 h-4 text-foreground-muted transition-transform',
          isOpen && 'rotate-180'
        )} />
      </button>

      {isOpen && (
        <div className={cn(
          'absolute right-0 top-full mt-2 w-64',
          'bg-background-secondary border border-border rounded-xl',
          'shadow-xl shadow-black/20 overflow-hidden z-50'
        )}>
          {/* User Info */}
          <div className="p-4 border-b border-border">
            <div className="flex items-center gap-3">
              <div className={cn(
                'w-10 h-10 rounded-lg flex items-center justify-center',
                'bg-gradient-to-br from-accent-primary to-accent-secondary',
                'text-black font-bold'
              )}>
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground-primary truncate">
                  {user.full_name || 'User'}
                </p>
                <p className="text-xs text-foreground-muted truncate">
                  {user.email}
                </p>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <Building2 className="w-3 h-3 text-foreground-muted" />
              <span className="text-xs text-foreground-muted">
                {user.organization_name}
              </span>
              <span className={cn(
                'ml-auto px-2 py-0.5 rounded text-[10px] font-semibold uppercase',
                user.role === 'owner' ? 'bg-accent-primary/20 text-accent-primary' :
                user.role === 'admin' ? 'bg-warning/20 text-warning' :
                'bg-foreground-muted/20 text-foreground-muted'
              )}>
                {user.role}
              </span>
            </div>
          </div>

          {/* Menu Items */}
          <div className="p-2">
            <button
              onClick={() => {
                setIsOpen(false)
                navigate('/settings')
              }}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg',
                'text-foreground-secondary hover:text-foreground-primary',
                'hover:bg-background-hover/50 transition-colors'
              )}
            >
              <User className="w-4 h-4" />
              <span className="text-sm">Account Settings</span>
            </button>

            <button
              onClick={() => {
                setIsOpen(false)
                navigate('/settings')
              }}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg',
                'text-foreground-secondary hover:text-foreground-primary',
                'hover:bg-background-hover/50 transition-colors'
              )}
            >
              <Settings className="w-4 h-4" />
              <span className="text-sm">Preferences</span>
            </button>
          </div>

          {/* Logout */}
          <div className="p-2 border-t border-border">
            <button
              onClick={handleLogout}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg',
                'text-bearish hover:bg-bearish/10 transition-colors'
              )}
            >
              <LogOut className="w-4 h-4" />
              <span className="text-sm font-medium">Sign out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
