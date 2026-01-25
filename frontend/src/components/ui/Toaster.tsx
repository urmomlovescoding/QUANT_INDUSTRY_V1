import { useState, createContext, useContext } from 'react'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'
import { cn } from '@/utils/cn'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  type: ToastType
  title?: string
  message: string
}

interface ToastContextType {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextType | null>(null)

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return context
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = (toast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).substring(7)
    setToasts((prev) => [...prev, { ...toast, id }])

    // Auto-remove after 5 seconds
    setTimeout(() => {
      removeToast(id)
    }, 5000)
  }

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
    </ToastContext.Provider>
  )
}

export function Toaster() {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {/* Placeholder for toasts - would connect to context */}
    </div>
  )
}

const icons = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const colors = {
  success: 'bg-bullish/10 border-bullish/30 text-bullish',
  error: 'bg-bearish/10 border-bearish/30 text-bearish',
  warning: 'bg-warning/10 border-warning/30 text-warning',
  info: 'bg-info/10 border-info/30 text-info',
}

interface ToastItemProps {
  toast: Toast
  onClose: () => void
}

export function ToastItem({ toast, onClose }: ToastItemProps) {
  const Icon = icons[toast.type]

  return (
    <div
      className={cn(
        'flex items-start gap-3 p-4 rounded-lg border shadow-elevated animate-slide-up',
        'bg-background-elevated',
        colors[toast.type]
      )}
    >
      <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        {toast.title && (
          <p className="font-medium text-foreground-primary">{toast.title}</p>
        )}
        <p className="text-sm text-foreground-secondary">{toast.message}</p>
      </div>
      <button
        onClick={onClose}
        className="p-1 rounded hover:bg-background-hover transition-colors"
      >
        <X className="w-4 h-4 text-foreground-muted" />
      </button>
    </div>
  )
}
