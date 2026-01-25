/**
 * Real-Time Notification System
 * Handles alerts for signals, trades, risk warnings, and system events
 */

import { useState, useEffect, useCallback, createContext, useContext, useRef } from 'react'
import { createPortal } from 'react-dom'
import {
  Bell,
  BellRing,
  X,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  Zap,
  DollarSign,
  Shield,
  Brain,
  Activity,
  Clock,
  Trash2,
  Settings,
  Volume2,
  VolumeX,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/utils/cn'

// ============== TYPES ==============

export type NotificationType = 'signal' | 'trade' | 'risk' | 'system' | 'info' | 'success' | 'error'
export type NotificationPriority = 'low' | 'medium' | 'high' | 'critical'

export interface Notification {
  id: string
  type: NotificationType
  priority: NotificationPriority
  title: string
  message: string
  timestamp: Date
  read: boolean
  data?: Record<string, any>
  action?: {
    label: string
    onClick: () => void
  }
}

interface NotificationContextType {
  notifications: Notification[]
  unreadCount: number
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  removeNotification: (id: string) => void
  clearAll: () => void
  soundEnabled: boolean
  setSoundEnabled: (enabled: boolean) => void
}

// ============== CONTEXT ==============

const NotificationContext = createContext<NotificationContextType | null>(null)

export function useNotifications() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotifications must be used within NotificationProvider')
  }
  return context
}

// ============== PROVIDER ==============

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [soundEnabled, setSoundEnabled] = useState(true)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Initialize audio
  useEffect(() => {
    audioRef.current = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2teleQMC/Fqv7fmXRAAP/2u86uGFOwH2XsLt7IxBAQv2eLrp35ZGAQ/1g7Tj2ZNOBxP0jarb1pRPCBfvlZ/V1ZhSDBnrm5rR0ZlVDxzompbNzplZEx3ml5LKyppcFh/jk4/HxptfGSDgkIzFw5xhGiHdjoXBwJ5jGyLbiwi/vp5lHCLZiQ6+vKBmHSTXhw68uqFoHyTViA+8uaRpICTTiRK7t6ZrISTSihW6tqdrIyTRixe4tKhuJCTQjBu3s6lwJSTQjB+1sKpyJSXPjCS0r6t0JSXOjSiyramwdiYmzY4srqurwHknJs2OL6qqq85/KCbMjzKnqKnbhykmy483pKan6Y4qKcqQPKGkpfWXKyrKkD+fn6P/oCwryZFDnZ2h/6guLMmRRpuaoP+rMC3IkUmZmJ7/rjEux5JMlpad/rAyL8aST5SUnP6zNDHFk1KSk5r+tTYyw5NVkJGZ/rc3M8OUV46Ql/+5OTTClVqMj5b/uzo1wZZcio6U/r07Nr+XXoiNk/7APze+mGCGjJL+wkE4vZlih4qR/cVDOryaZIWJkP3HRTu7m2aDiY/9yUc8uZxogYiO/ctIPLibaoGIjf3NSD64nGyAh4z+z0k/tp5uf4aL/tFKQLafcH6Fiv7STEC1oHJ9hYn+1E1BtKF0fISI/tVOQrOidXuDh/7XUEOyo3d7g4b+2FFEs6N4eoKF/tlTRbKkeXqBhP7bVEWxpXp5gYT+3FVGsaZ7eYCD/t1WR7Cme3h/gv7eV0iwp3x4f4H+31lJr6h9eH6A/uBaS6+pfXd+gP7hW0uvqn53fX/+4lxMrqp/d31//uNdTa6rgHZ8fv7kXk6tq4F2fH3+5V9Pra2Cdnx9/uZgUKysgXV7fP7nYVGsrYJ1e3v+6GJSrK6DdXt7/ulmU6uug3R6ev7qZlSqroR0enr+62dVqq+EdHp5/uxoVqmvhXR5ef7taFaosoV0eXj+7mlXqLGGc3l4/u9qWKexh3N4d/7walmosoZzeHb+8WtaqLOIc3h2/vJsW6eziHJ3df7zbFynswhydnX+9G1dp7SJcnd1/vVuXqa0inJ2dP72cF+mtYtydrT+93Bgprack3W0/vhwYaaynZJ1s/75cWGlsp2Sda/++XJipbOdkna0/vpzY6S0nZF2s/77dGSktJ2RdrP+/HVlpLWdkXay/v12ZaO1npB2sv79d2ajtp2Qd7L+/nlno7ackHey/v95Z6O2nJB3sf7/eWijtpyPd7H/AHppo7ack3exAA==')
  }, [])

  const playNotificationSound = useCallback(() => {
    if (soundEnabled && audioRef.current) {
      audioRef.current.currentTime = 0
      audioRef.current.play().catch(() => {})
    }
  }, [soundEnabled])

  const addNotification = useCallback((notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => {
    const newNotification: Notification = {
      ...notification,
      id: `notif_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      read: false
    }

    setNotifications(prev => [newNotification, ...prev].slice(0, 100)) // Keep max 100

    // Play sound for high priority
    if (notification.priority === 'high' || notification.priority === 'critical') {
      playNotificationSound()
    }
  }, [playNotificationSound])

  const markAsRead = useCallback((id: string) => {
    setNotifications(prev => prev.map(n =>
      n.id === id ? { ...n, read: true } : n
    ))
  }, [])

  const markAllAsRead = useCallback(() => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
  }, [])

  const removeNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id))
  }, [])

  const clearAll = useCallback(() => {
    setNotifications([])
  }, [])

  const unreadCount = notifications.filter(n => !n.read).length

  return (
    <NotificationContext.Provider value={{
      notifications,
      unreadCount,
      addNotification,
      markAsRead,
      markAllAsRead,
      removeNotification,
      clearAll,
      soundEnabled,
      setSoundEnabled
    }}>
      {children}
      <ToastContainer />
    </NotificationContext.Provider>
  )
}

// ============== TOAST CONTAINER ==============

function ToastContainer() {
  const { notifications, removeNotification } = useNotifications()
  const [visibleToasts, setVisibleToasts] = useState<Notification[]>([])

  // Show toast for new notifications
  useEffect(() => {
    const latestNotification = notifications[0]
    if (latestNotification && !latestNotification.read) {
      // Check if already visible
      if (!visibleToasts.find(t => t.id === latestNotification.id)) {
        setVisibleToasts(prev => [...prev, latestNotification].slice(-5))

        // Auto-remove after delay based on priority
        const delay = latestNotification.priority === 'critical' ? 10000 :
          latestNotification.priority === 'high' ? 7000 : 5000

        setTimeout(() => {
          setVisibleToasts(prev => prev.filter(t => t.id !== latestNotification.id))
        }, delay)
      }
    }
  }, [notifications, visibleToasts])

  const dismissToast = useCallback((id: string) => {
    setVisibleToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return createPortal(
    <div className="fixed bottom-4 right-4 z-[200] flex flex-col gap-2 max-w-sm">
      {visibleToasts.map(toast => (
        <Toast
          key={toast.id}
          notification={toast}
          onDismiss={() => dismissToast(toast.id)}
        />
      ))}
    </div>,
    document.body
  )
}

// ============== TOAST COMPONENT ==============

function Toast({ notification, onDismiss }: { notification: Notification; onDismiss: () => void }) {
  const Icon = getNotificationIcon(notification.type)
  const colors = getNotificationColors(notification.type, notification.priority)

  return (
    <div className={cn(
      'flex items-start gap-3 p-4 rounded-lg border shadow-lg backdrop-blur-sm animate-in slide-in-from-right-5 duration-300',
      colors.bg,
      colors.border
    )}>
      <div className={cn('p-1.5 rounded-lg', colors.iconBg)}>
        <Icon className={cn('w-4 h-4', colors.icon)} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn('text-sm font-bold', colors.title)}>{notification.title}</span>
          {notification.priority === 'critical' && (
            <span className="px-1.5 py-0.5 bg-bearish/20 text-bearish text-[10px] font-bold rounded animate-pulse">
              CRITICAL
            </span>
          )}
        </div>
        <p className="text-xs text-foreground-secondary mt-0.5 line-clamp-2">
          {notification.message}
        </p>
        {notification.action && (
          <button
            onClick={notification.action.onClick}
            className={cn('text-xs font-medium mt-2 flex items-center gap-1', colors.action)}
          >
            {notification.action.label}
            <ChevronRight className="w-3 h-3" />
          </button>
        )}
      </div>
      <button
        onClick={onDismiss}
        className="p-1 rounded hover:bg-background-tertiary transition-colors"
      >
        <X className="w-4 h-4 text-foreground-muted" />
      </button>
    </div>
  )
}

// ============== NOTIFICATION CENTER ==============

interface NotificationCenterProps {
  isOpen: boolean
  onClose: () => void
}

export function NotificationCenter({ isOpen, onClose }: NotificationCenterProps) {
  const {
    notifications,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAll,
    soundEnabled,
    setSoundEnabled
  } = useNotifications()

  const [filter, setFilter] = useState<NotificationType | 'all'>('all')

  const filteredNotifications = filter === 'all'
    ? notifications
    : notifications.filter(n => n.type === filter)

  if (!isOpen) return null

  return createPortal(
    <div className="fixed inset-0 z-[150]">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Panel */}
      <div className="absolute right-0 top-0 h-full w-full max-w-md bg-background-secondary border-l border-border shadow-2xl animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <BellRing className="w-5 h-5 text-accent-primary" />
            <h2 className="font-bold text-foreground-primary">Notifications</h2>
            {notifications.filter(n => !n.read).length > 0 && (
              <span className="px-2 py-0.5 bg-accent-primary/20 text-accent-primary text-xs font-bold rounded-full">
                {notifications.filter(n => !n.read).length}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSoundEnabled(!soundEnabled)}
              className={cn(
                'p-2 rounded-lg transition-colors',
                soundEnabled ? 'text-accent-primary' : 'text-foreground-muted'
              )}
              title={soundEnabled ? 'Sound On' : 'Sound Off'}
            >
              {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-background-tertiary transition-colors"
            >
              <X className="w-5 h-5 text-foreground-muted" />
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 p-3 border-b border-border overflow-x-auto">
          {(['all', 'signal', 'trade', 'risk', 'system'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                'px-3 py-1 text-xs font-medium rounded-full whitespace-nowrap transition-colors',
                filter === f
                  ? 'bg-accent-primary/20 text-accent-primary'
                  : 'bg-background-tertiary text-foreground-muted hover:text-foreground-secondary'
              )}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-background-tertiary/50">
          <button
            onClick={markAllAsRead}
            className="text-xs text-accent-primary hover:underline"
          >
            Mark all as read
          </button>
          <button
            onClick={clearAll}
            className="text-xs text-foreground-muted hover:text-bearish flex items-center gap-1"
          >
            <Trash2 className="w-3 h-3" />
            Clear all
          </button>
        </div>

        {/* Notification List */}
        <div className="flex-1 overflow-y-auto h-[calc(100vh-180px)]">
          {filteredNotifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-foreground-muted">
              <Bell className="w-12 h-12 mb-3 opacity-50" />
              <p className="text-sm">No notifications</p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {filteredNotifications.map(notification => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onRead={() => markAsRead(notification.id)}
                  onRemove={() => removeNotification(notification.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}

// ============== NOTIFICATION ITEM ==============

function NotificationItem({
  notification,
  onRead,
  onRemove
}: {
  notification: Notification
  onRead: () => void
  onRemove: () => void
}) {
  const Icon = getNotificationIcon(notification.type)
  const colors = getNotificationColors(notification.type, notification.priority)

  const handleClick = () => {
    if (!notification.read) {
      onRead()
    }
    notification.action?.onClick()
  }

  return (
    <div
      className={cn(
        'p-4 hover:bg-background-tertiary/50 transition-colors cursor-pointer',
        !notification.read && 'bg-accent-primary/5'
      )}
      onClick={handleClick}
    >
      <div className="flex items-start gap-3">
        <div className={cn('p-2 rounded-lg', colors.iconBg)}>
          <Icon className={cn('w-4 h-4', colors.icon)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={cn(
              'text-sm font-medium',
              !notification.read ? 'text-foreground-primary' : 'text-foreground-secondary'
            )}>
              {notification.title}
            </span>
            {notification.priority === 'critical' && (
              <span className="px-1.5 py-0.5 bg-bearish/20 text-bearish text-[10px] font-bold rounded">
                CRITICAL
              </span>
            )}
            {notification.priority === 'high' && (
              <span className="px-1.5 py-0.5 bg-warning/20 text-warning text-[10px] font-bold rounded">
                HIGH
              </span>
            )}
          </div>
          <p className="text-xs text-foreground-muted line-clamp-2">{notification.message}</p>
          <div className="flex items-center justify-between mt-2">
            <span className="text-[10px] text-foreground-muted flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatTimeAgo(notification.timestamp)}
            </span>
            {notification.action && (
              <span className={cn('text-xs font-medium', colors.action)}>
                {notification.action.label} →
              </span>
            )}
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
          className="p-1 rounded hover:bg-background-secondary transition-colors opacity-0 group-hover:opacity-100"
        >
          <X className="w-3 h-3 text-foreground-muted" />
        </button>
        {!notification.read && (
          <div className="w-2 h-2 rounded-full bg-accent-primary" />
        )}
      </div>
    </div>
  )
}

// ============== NOTIFICATION BELL (Header Component) ==============

export function NotificationBell() {
  const { unreadCount } = useNotifications()
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="relative p-2 rounded-lg hover:bg-background-tertiary transition-colors"
      >
        <Bell className={cn(
          'w-4 h-4',
          unreadCount > 0 ? 'text-accent-primary' : 'text-foreground-muted'
        )} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-bearish text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
      <NotificationCenter isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  )
}

// ============== HELPERS ==============

function getNotificationIcon(type: NotificationType) {
  switch (type) {
    case 'signal': return Brain
    case 'trade': return DollarSign
    case 'risk': return Shield
    case 'system': return Activity
    case 'success': return CheckCircle
    case 'error': return XCircle
    default: return Info
  }
}

function getNotificationColors(type: NotificationType, priority: NotificationPriority) {
  const base = {
    signal: {
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/30',
      iconBg: 'bg-purple-500/20',
      icon: 'text-purple-400',
      title: 'text-purple-400',
      action: 'text-purple-400 hover:text-purple-300'
    },
    trade: {
      bg: 'bg-bullish/10',
      border: 'border-bullish/30',
      iconBg: 'bg-bullish/20',
      icon: 'text-bullish',
      title: 'text-bullish',
      action: 'text-bullish hover:text-bullish/80'
    },
    risk: {
      bg: 'bg-warning/10',
      border: 'border-warning/30',
      iconBg: 'bg-warning/20',
      icon: 'text-warning',
      title: 'text-warning',
      action: 'text-warning hover:text-warning/80'
    },
    system: {
      bg: 'bg-accent-primary/10',
      border: 'border-accent-primary/30',
      iconBg: 'bg-accent-primary/20',
      icon: 'text-accent-primary',
      title: 'text-accent-primary',
      action: 'text-accent-primary hover:text-accent-primary/80'
    },
    success: {
      bg: 'bg-bullish/10',
      border: 'border-bullish/30',
      iconBg: 'bg-bullish/20',
      icon: 'text-bullish',
      title: 'text-bullish',
      action: 'text-bullish hover:text-bullish/80'
    },
    error: {
      bg: 'bg-bearish/10',
      border: 'border-bearish/30',
      iconBg: 'bg-bearish/20',
      icon: 'text-bearish',
      title: 'text-bearish',
      action: 'text-bearish hover:text-bearish/80'
    },
    info: {
      bg: 'bg-background-tertiary',
      border: 'border-border',
      iconBg: 'bg-background-secondary',
      icon: 'text-foreground-muted',
      title: 'text-foreground-primary',
      action: 'text-accent-primary hover:text-accent-primary/80'
    }
  }

  const colors = base[type] || base.info

  // Override for critical priority
  if (priority === 'critical') {
    return {
      ...colors,
      bg: 'bg-bearish/10',
      border: 'border-bearish/50',
      title: 'text-bearish'
    }
  }

  return colors
}

function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000)

  if (seconds < 60) return 'Just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

// ============== HOOK FOR EASY SIGNAL/TRADE NOTIFICATIONS ==============

export function useTradeNotifications() {
  const { addNotification } = useNotifications()

  const notifySignal = useCallback((symbol: string, direction: 'LONG' | 'SHORT', confidence: number) => {
    addNotification({
      type: 'signal',
      priority: confidence > 0.8 ? 'high' : 'medium',
      title: `${direction} Signal: ${symbol}`,
      message: `AI generated ${direction} signal with ${(confidence * 100).toFixed(0)}% confidence`,
      data: { symbol, direction, confidence },
      action: {
        label: 'View Details',
        onClick: () => window.dispatchEvent(new CustomEvent('view-signal', { detail: { symbol, direction } }))
      }
    })
  }, [addNotification])

  const notifyTrade = useCallback((symbol: string, side: 'BUY' | 'SELL', quantity: number, price: number) => {
    addNotification({
      type: 'trade',
      priority: 'medium',
      title: `Trade Executed: ${symbol}`,
      message: `${side} ${quantity} @ $${price.toFixed(2)}`,
      data: { symbol, side, quantity, price }
    })
  }, [addNotification])

  const notifyRisk = useCallback((title: string, message: string, isCritical: boolean = false) => {
    addNotification({
      type: 'risk',
      priority: isCritical ? 'critical' : 'high',
      title,
      message,
      action: {
        label: 'View Risk Panel',
        onClick: () => window.dispatchEvent(new CustomEvent('open-risk-panel'))
      }
    })
  }, [addNotification])

  return { notifySignal, notifyTrade, notifyRisk }
}
