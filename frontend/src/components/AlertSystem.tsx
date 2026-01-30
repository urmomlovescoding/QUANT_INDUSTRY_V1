/**
 * Alert System
 * Define custom alerts, receive desktop + in-app notifications,
 * and track alert history with acknowledgment.
 */

import { useState, useEffect, useCallback, useRef, createContext, useContext } from 'react'
import { createPortal } from 'react-dom'
import {
  Bell,
  BellOff,
  Plus,
  X,
  Check,
  AlertTriangle,
  TrendingDown,
  TrendingUp,
  Activity,
  Volume2,
  Shield,
  Cpu,
  ChevronDown,
  Trash2,
  Clock,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { useEventSubscription, useEventEmitter } from '@/hooks/useEventBus'
import { formatRelativeTime } from '@/utils/format'

// Alert types
type AlertCondition = 'price_above' | 'price_below' | 'price_change_pct' | 'volume_spike' | 'signal_generated' | 'risk_breach' | 'system_error'
type AlertStatus = 'active' | 'triggered' | 'acknowledged' | 'expired'

interface Alert {
  id: string
  name: string
  condition: AlertCondition
  symbol?: string
  threshold: number
  status: AlertStatus
  createdAt: string
  triggeredAt?: string
  acknowledgedAt?: string
  message?: string
  repeat: boolean
}

interface AlertToast {
  id: string
  alertId: string
  title: string
  message: string
  type: 'price' | 'volume' | 'signal' | 'risk' | 'system'
  timestamp: string
  acknowledged: boolean
}

const conditionLabels: Record<AlertCondition, string> = {
  price_above: 'Price Above',
  price_below: 'Price Below',
  price_change_pct: 'Price Change %',
  volume_spike: 'Volume Spike',
  signal_generated: 'Signal Generated',
  risk_breach: 'Risk Breach',
  system_error: 'System Error',
}

const conditionIcons: Record<AlertCondition, React.ComponentType<{ className?: string }>> = {
  price_above: TrendingUp,
  price_below: TrendingDown,
  price_change_pct: Activity,
  volume_spike: Volume2,
  signal_generated: Bell,
  risk_breach: Shield,
  system_error: Cpu,
}

// Alert store context
interface AlertStore {
  alerts: Alert[]
  toasts: AlertToast[]
  addAlert: (alert: Omit<Alert, 'id' | 'status' | 'createdAt'>) => void
  removeAlert: (id: string) => void
  acknowledgeAlert: (id: string) => void
  dismissToast: (id: string) => void
  clearToasts: () => void
}

const AlertContext = createContext<AlertStore | null>(null)

export function useAlerts() {
  const ctx = useContext(AlertContext)
  if (!ctx) throw new Error('useAlerts must be used within AlertProvider')
  return ctx
}

// Persistent storage key
const ALERTS_STORAGE_KEY = 'quant-alerts'

function loadAlerts(): Alert[] {
  try {
    const stored = localStorage.getItem(ALERTS_STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}

function saveAlerts(alerts: Alert[]) {
  try {
    localStorage.setItem(ALERTS_STORAGE_KEY, JSON.stringify(alerts))
  } catch { /* ignore */ }
}

export function AlertProvider({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = useState<Alert[]>(loadAlerts)
  const [toasts, setToasts] = useState<AlertToast[]>([])
  const emit = useEventEmitter()

  // Persist alerts
  useEffect(() => {
    saveAlerts(alerts)
  }, [alerts])

  const addAlert = useCallback((alert: Omit<Alert, 'id' | 'status' | 'createdAt'>) => {
    const newAlert: Alert = {
      ...alert,
      id: `alert-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      status: 'active',
      createdAt: new Date().toISOString(),
    }
    setAlerts(prev => [newAlert, ...prev])
  }, [])

  const removeAlert = useCallback((id: string) => {
    setAlerts(prev => prev.filter(a => a.id !== id))
  }, [])

  const acknowledgeAlert = useCallback((id: string) => {
    setAlerts(prev => prev.map(a =>
      a.id === id ? { ...a, status: 'acknowledged' as AlertStatus, acknowledgedAt: new Date().toISOString() } : a
    ))
    setToasts(prev => prev.map(t =>
      t.alertId === id ? { ...t, acknowledged: true } : t
    ))
  }, [])

  const triggerAlert = useCallback((alert: Alert, message: string) => {
    // Update alert status
    setAlerts(prev => prev.map(a =>
      a.id === alert.id
        ? { ...a, status: 'triggered' as AlertStatus, triggeredAt: new Date().toISOString(), message }
        : a
    ))

    // Create toast
    const toast: AlertToast = {
      id: `toast-${Date.now()}`,
      alertId: alert.id,
      title: alert.name,
      message,
      type: alert.condition.includes('price') ? 'price' :
            alert.condition === 'volume_spike' ? 'volume' :
            alert.condition === 'signal_generated' ? 'signal' :
            alert.condition === 'risk_breach' ? 'risk' : 'system',
      timestamp: new Date().toISOString(),
      acknowledged: false,
    }
    setToasts(prev => [toast, ...prev].slice(0, 50))

    // Desktop notification
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(alert.name, {
        body: message,
        icon: '/favicon.ico',
        tag: alert.id,
      })
    }

    // Emit event
    emit('notification:show', {
      type: 'warning',
      title: alert.name,
      message,
    })
  }, [emit])

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const clearToasts = useCallback(() => {
    setToasts([])
  }, [])

  // Listen for events that may trigger alerts
  useEventSubscription('signal:new', (event) => {
    const activeAlerts = alerts.filter(a => a.status === 'active' && a.condition === 'signal_generated')
    activeAlerts.forEach(alert => {
      if (!alert.symbol || alert.symbol === event.data?.symbol) {
        triggerAlert(alert, `New signal: ${event.data?.symbol} ${event.data?.direction}`)
      }
    })
  })

  useEventSubscription('risk:alert', (event) => {
    const activeAlerts = alerts.filter(a => a.status === 'active' && a.condition === 'risk_breach')
    activeAlerts.forEach(alert => {
      triggerAlert(alert, event.data?.message || 'Risk threshold breached')
    })
  })

  // Auto-dismiss old toasts
  useEffect(() => {
    const timer = setInterval(() => {
      setToasts(prev => prev.filter(t => {
        const age = Date.now() - new Date(t.timestamp).getTime()
        return age < 30000 || !t.acknowledged
      }))
    }, 5000)
    return () => clearInterval(timer)
  }, [])

  return (
    <AlertContext.Provider value={{ alerts, toasts, addAlert, removeAlert, acknowledgeAlert, dismissToast, clearToasts }}>
      {children}
      <AlertToastContainer />
    </AlertContext.Provider>
  )
}

// Toast container - renders toasts in bottom-right corner
function AlertToastContainer() {
  const { toasts, dismissToast, acknowledgeAlert } = useAlerts()
  const visibleToasts = toasts.filter(t => !t.acknowledged).slice(0, 5)

  if (visibleToasts.length === 0) return null

  return createPortal(
    <div className="fixed bottom-4 right-4 z-[90] flex flex-col gap-2 max-w-sm">
      {visibleToasts.map((toast, i) => (
        <div
          key={toast.id}
          className={cn(
            'bg-background-elevated border border-border rounded-lg shadow-elevated p-3',
            'animate-in slide-in-from-right-5 duration-300',
          )}
          style={{ animationDelay: `${i * 50}ms` }}
        >
          <div className="flex items-start gap-2">
            <AlertTriangle className={cn(
              'w-4 h-4 flex-shrink-0 mt-0.5',
              toast.type === 'risk' ? 'text-bearish' :
              toast.type === 'price' ? 'text-warning' :
              'text-accent-primary'
            )} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground-primary">{toast.title}</p>
              <p className="text-xs text-foreground-secondary mt-0.5">{toast.message}</p>
              <p className="text-[10px] text-foreground-muted mt-1">{formatRelativeTime(toast.timestamp)}</p>
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              <button
                onClick={() => acknowledgeAlert(toast.alertId)}
                className="p-1 rounded hover:bg-bullish/20 text-bullish transition-colors"
                title="Acknowledge"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => dismissToast(toast.id)}
                className="p-1 rounded hover:bg-background-hover text-foreground-muted transition-colors"
                title="Dismiss"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>,
    document.body
  )
}

// Alert Manager Panel - for creating and managing alerts
interface AlertManagerProps {
  isOpen: boolean
  onClose: () => void
}

export function AlertManager({ isOpen, onClose }: AlertManagerProps) {
  const { alerts, addAlert, removeAlert, acknowledgeAlert } = useAlerts()
  const [showCreate, setShowCreate] = useState(false)
  const [tab, setTab] = useState<'active' | 'history'>('active')

  // Create alert form state
  const [name, setName] = useState('')
  const [condition, setCondition] = useState<AlertCondition>('price_below')
  const [symbol, setSymbol] = useState('')
  const [threshold, setThreshold] = useState('')
  const [repeat, setRepeat] = useState(false)

  // Request notification permission
  useEffect(() => {
    if (isOpen && 'Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [isOpen])

  const handleCreate = () => {
    if (!name.trim()) return
    addAlert({
      name: name.trim(),
      condition,
      symbol: symbol.trim() || undefined,
      threshold: parseFloat(threshold) || 0,
      repeat,
    })
    setName('')
    setSymbol('')
    setThreshold('')
    setRepeat(false)
    setShowCreate(false)
  }

  const activeAlerts = alerts.filter(a => a.status === 'active')
  const historyAlerts = alerts.filter(a => a.status !== 'active')

  if (!isOpen) return null

  return createPortal(
    <div className="fixed inset-0 z-[95] flex items-start justify-center pt-[10vh]">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-background-secondary border border-border rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Bell className="w-5 h-5 text-accent-primary" />
            <h2 className="text-sm font-bold text-foreground-primary">Alert Manager</h2>
            <span className="text-[10px] bg-accent-primary/20 text-accent-primary px-1.5 py-0.5 rounded font-bold">
              {activeAlerts.length} active
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-accent-primary/20 text-accent-primary hover:bg-accent-primary/30 transition-colors"
            >
              <Plus className="w-3 h-3" />
              New Alert
            </button>
            <button onClick={onClose} className="p-1 rounded hover:bg-background-hover text-foreground-muted">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Create alert form */}
        {showCreate && (
          <div className="px-4 py-3 border-b border-border bg-background-tertiary/50 space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-foreground-muted uppercase">Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="e.g., AAPL Drop Alert"
                  className="w-full text-xs bg-background-primary border border-border rounded px-2 py-1.5 text-foreground-primary placeholder-foreground-muted outline-none focus:border-accent-primary mt-1"
                />
              </div>
              <div>
                <label className="text-[10px] text-foreground-muted uppercase">Condition</label>
                <select
                  value={condition}
                  onChange={e => setCondition(e.target.value as AlertCondition)}
                  className="w-full text-xs bg-background-primary border border-border rounded px-2 py-1.5 text-foreground-primary outline-none focus:border-accent-primary mt-1"
                >
                  {Object.entries(conditionLabels).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-foreground-muted uppercase">Symbol (optional)</label>
                <input
                  type="text"
                  value={symbol}
                  onChange={e => setSymbol(e.target.value.toUpperCase())}
                  placeholder="AAPL"
                  className="w-full text-xs bg-background-primary border border-border rounded px-2 py-1.5 text-foreground-primary placeholder-foreground-muted outline-none focus:border-accent-primary mt-1"
                />
              </div>
              <div>
                <label className="text-[10px] text-foreground-muted uppercase">Threshold</label>
                <input
                  type="number"
                  value={threshold}
                  onChange={e => setThreshold(e.target.value)}
                  placeholder="150.00"
                  className="w-full text-xs bg-background-primary border border-border rounded px-2 py-1.5 text-foreground-primary placeholder-foreground-muted outline-none focus:border-accent-primary mt-1"
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-xs text-foreground-secondary cursor-pointer">
                <input
                  type="checkbox"
                  checked={repeat}
                  onChange={e => setRepeat(e.target.checked)}
                  className="rounded border-border"
                />
                Repeat alert
              </label>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowCreate(false)}
                  className="text-xs px-3 py-1 rounded text-foreground-muted hover:bg-background-hover transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreate}
                  disabled={!name.trim()}
                  className="text-xs px-3 py-1 rounded bg-accent-primary text-background-primary font-bold hover:bg-accent-hover transition-colors disabled:opacity-50"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex border-b border-border">
          {(['active', 'history'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                'flex-1 text-xs py-2 font-medium transition-colors capitalize',
                tab === t
                  ? 'text-accent-primary border-b-2 border-accent-primary'
                  : 'text-foreground-muted hover:text-foreground-secondary'
              )}
            >
              {t} ({t === 'active' ? activeAlerts.length : historyAlerts.length})
            </button>
          ))}
        </div>

        {/* Alert list */}
        <div className="max-h-[400px] overflow-y-auto">
          {(tab === 'active' ? activeAlerts : historyAlerts).length === 0 ? (
            <div className="py-12 text-center text-foreground-muted">
              <BellOff className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No {tab} alerts</p>
            </div>
          ) : (
            (tab === 'active' ? activeAlerts : historyAlerts).map(alert => {
              const Icon = conditionIcons[alert.condition]
              return (
                <div
                  key={alert.id}
                  className="flex items-center gap-3 px-4 py-3 border-b border-border/50 hover:bg-background-hover/50 transition-colors"
                >
                  <div className={cn(
                    'w-8 h-8 rounded flex items-center justify-center flex-shrink-0',
                    alert.status === 'triggered' ? 'bg-warning/10' :
                    alert.status === 'acknowledged' ? 'bg-bullish/10' :
                    'bg-accent-primary/10'
                  )}>
                    <Icon className={cn(
                      'w-4 h-4',
                      alert.status === 'triggered' ? 'text-warning' :
                      alert.status === 'acknowledged' ? 'text-bullish' :
                      'text-accent-primary'
                    )} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground-primary truncate">{alert.name}</span>
                      {alert.symbol && (
                        <span className="text-[10px] font-bold text-accent-primary">{alert.symbol}</span>
                      )}
                    </div>
                    <div className="text-[10px] text-foreground-muted flex items-center gap-2">
                      <span>{conditionLabels[alert.condition]}: {alert.threshold}</span>
                      <span>|</span>
                      <span className="flex items-center gap-0.5">
                        <Clock className="w-2.5 h-2.5" />
                        {formatRelativeTime(alert.triggeredAt || alert.createdAt)}
                      </span>
                      {alert.repeat && <span className="text-accent-primary">repeat</span>}
                    </div>
                    {alert.message && (
                      <p className="text-[10px] text-foreground-secondary mt-0.5 truncate">{alert.message}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {alert.status === 'triggered' && (
                      <button
                        onClick={() => acknowledgeAlert(alert.id)}
                        className="p-1 rounded hover:bg-bullish/20 text-bullish transition-colors"
                        title="Acknowledge"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button
                      onClick={() => removeAlert(alert.id)}
                      className="p-1 rounded hover:bg-bearish/20 text-foreground-muted hover:text-bearish transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-border bg-background-tertiary/50 text-[10px] text-foreground-muted flex items-center justify-between">
          <span>Desktop notifications: {typeof Notification !== 'undefined' && Notification.permission === 'granted' ? 'enabled' : 'disabled'}</span>
          <kbd className="px-1.5 py-0.5 bg-background-tertiary rounded">Ctrl+Shift+A</kbd>
        </div>
      </div>
    </div>,
    document.body
  )
}
