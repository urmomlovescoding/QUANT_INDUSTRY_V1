/**
 * Event Bus for Frontend State Management
 * ========================================
 * Provides a lightweight pub/sub system for cross-component communication.
 * Matches quant-platform pattern for decoupled state updates.
 */

import { useCallback, useEffect, useRef } from 'react'

// ============== EVENT TYPES ==============

export type EventType =
  // Trading Events
  | 'signal:new'
  | 'signal:executed'
  | 'signal:expired'
  | 'trade:opened'
  | 'trade:closed'
  | 'trade:updated'
  | 'order:filled'
  | 'order:cancelled'
  | 'order:rejected'
  // Market Events
  | 'market:open'
  | 'market:close'
  | 'market:halt'
  | 'tick:update'
  | 'quote:update'
  // System Events
  | 'connection:open'
  | 'connection:close'
  | 'connection:error'
  | 'connection:reconnecting'
  // Risk Events
  | 'risk:alert'
  | 'risk:limit_reached'
  | 'risk:killswitch'
  // Brain Events
  | 'brain:signal'
  | 'brain:regime_change'
  | 'brain:model_update'
  | 'brain:drift_detected'
  // UI Events
  | 'notification:show'
  | 'notification:dismiss'
  | 'modal:open'
  | 'modal:close'
  | 'theme:change'
  // Custom Events
  | `custom:${string}`

export interface EventPayload {
  type: EventType
  timestamp: number
  data?: any
  source?: string
  id?: string
}

type EventCallback<T = any> = (payload: EventPayload & { data?: T }) => void
type UnsubscribeFn = () => void

interface EventSubscription {
  id: string
  eventType: EventType | '*'
  callback: EventCallback
  once: boolean
}

// ============== EVENT BUS IMPLEMENTATION ==============

class EventBus {
  private subscriptions: Map<string, EventSubscription> = new Map()
  private eventHistory: EventPayload[] = []
  private maxHistorySize = 100
  private idCounter = 0

  /**
   * Subscribe to an event type
   */
  subscribe<T = any>(
    eventType: EventType | '*',
    callback: EventCallback<T>,
    options: { once?: boolean } = {}
  ): UnsubscribeFn {
    const id = `sub_${++this.idCounter}`

    this.subscriptions.set(id, {
      id,
      eventType,
      callback,
      once: options.once ?? false
    })

    return () => {
      this.subscriptions.delete(id)
    }
  }

  /**
   * Subscribe to an event type, automatically unsubscribing after first event
   */
  once<T = any>(eventType: EventType, callback: EventCallback<T>): UnsubscribeFn {
    return this.subscribe(eventType, callback, { once: true })
  }

  /**
   * Emit an event to all subscribers
   */
  emit(eventType: EventType, data?: any, source?: string): void {
    const payload: EventPayload = {
      type: eventType,
      timestamp: Date.now(),
      data,
      source,
      id: `evt_${++this.idCounter}`
    }

    // Store in history
    this.eventHistory.push(payload)
    if (this.eventHistory.length > this.maxHistorySize) {
      this.eventHistory.shift()
    }

    // Notify subscribers
    const toRemove: string[] = []

    this.subscriptions.forEach((sub) => {
      if (sub.eventType === eventType || sub.eventType === '*') {
        try {
          sub.callback(payload)
          if (sub.once) {
            toRemove.push(sub.id)
          }
        } catch {
          // Silently ignore event handler errors
        }
      }
    })

    // Remove one-time subscriptions
    toRemove.forEach(id => this.subscriptions.delete(id))
  }

  /**
   * Get recent event history
   */
  getHistory(limit = 10, eventType?: EventType): EventPayload[] {
    let history = this.eventHistory

    if (eventType) {
      history = history.filter(e => e.type === eventType)
    }

    return history.slice(-limit)
  }

  /**
   * Clear all subscriptions
   */
  clear(): void {
    this.subscriptions.clear()
  }

  /**
   * Get subscription count
   */
  getSubscriptionCount(eventType?: EventType): number {
    if (!eventType) {
      return this.subscriptions.size
    }

    let count = 0
    this.subscriptions.forEach(sub => {
      if (sub.eventType === eventType) count++
    })
    return count
  }

  /**
   * Wait for a specific event (Promise-based)
   */
  waitFor<T = any>(
    eventType: EventType,
    timeout = 30000
  ): Promise<EventPayload & { data?: T }> {
    return new Promise((resolve, reject) => {
      let timeoutId: NodeJS.Timeout

      const unsubscribe = this.once<T>(eventType, (payload) => {
        clearTimeout(timeoutId)
        resolve(payload)
      })

      timeoutId = setTimeout(() => {
        unsubscribe()
        reject(new Error(`Timeout waiting for event: ${eventType}`))
      }, timeout)
    })
  }
}

// Singleton instance
const eventBus = new EventBus()

// ============== REACT HOOKS ==============

/**
 * Hook to subscribe to events
 *
 * @example
 * useEventSubscription('signal:new', (event) => {
 *   console.log('New signal:', event.data)
 * })
 */
export function useEventSubscription<T = any>(
  eventType: EventType | '*',
  callback: EventCallback<T>,
  deps: React.DependencyList = []
): void {
  const callbackRef = useRef(callback)
  callbackRef.current = callback

  useEffect(() => {
    const handler: EventCallback<T> = (payload) => {
      callbackRef.current(payload)
    }

    const unsubscribe = eventBus.subscribe(eventType, handler)
    return unsubscribe
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventType, ...deps])
}

/**
 * Hook to emit events
 *
 * @example
 * const emit = useEventEmitter()
 * emit('notification:show', { message: 'Trade executed!' })
 */
export function useEventEmitter(): (eventType: EventType, data?: any, source?: string) => void {
  const emit = useCallback(
    (eventType: EventType, data?: any, source?: string) => {
      eventBus.emit(eventType, data, source)
    },
    []
  )

  return emit
}

/**
 * Hook combining subscribe and emit
 *
 * @example
 * const { emit, subscribe, history } = useEventBus()
 */
export function useEventBus() {
  const emit = useEventEmitter()

  const subscribe = useCallback(
    <T = any>(eventType: EventType | '*', callback: EventCallback<T>) => {
      return eventBus.subscribe(eventType, callback)
    },
    []
  )

  const getHistory = useCallback(
    (limit = 10, eventType?: EventType) => {
      return eventBus.getHistory(limit, eventType)
    },
    []
  )

  const waitFor = useCallback(
    <T = any>(eventType: EventType, timeout?: number) => {
      return eventBus.waitFor<T>(eventType, timeout)
    },
    []
  )

  return {
    emit,
    subscribe,
    getHistory,
    waitFor
  }
}

/**
 * Hook to listen for multiple event types
 *
 * @example
 * useMultiEventSubscription(
 *   ['signal:new', 'signal:executed'],
 *   (event) => console.log('Signal event:', event)
 * )
 */
export function useMultiEventSubscription<T = any>(
  eventTypes: EventType[],
  callback: EventCallback<T>,
  deps: React.DependencyList = []
): void {
  const callbackRef = useRef(callback)
  callbackRef.current = callback

  useEffect(() => {
    const handler: EventCallback<T> = (payload) => {
      callbackRef.current(payload)
    }

    const unsubscribes = eventTypes.map(type =>
      eventBus.subscribe(type, handler)
    )

    return () => {
      unsubscribes.forEach(unsub => unsub())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(eventTypes), ...deps])
}

// ============== TYPED EVENT HELPERS ==============

export interface SignalEvent {
  id: string
  symbol: string
  direction: 'LONG' | 'SHORT'
  confidence: number
  strategy: string
  timestamp: string
}

export interface TradeEvent {
  id: string
  symbol: string
  side: 'BUY' | 'SELL'
  quantity: number
  price: number
  pnl?: number
  timestamp: string
}

export interface RiskAlertEvent {
  level: 'WARNING' | 'CRITICAL'
  type: string
  message: string
  metrics?: Record<string, number>
}

export interface NotificationEvent {
  id?: string
  type: 'info' | 'success' | 'warning' | 'error'
  title?: string
  message: string
  duration?: number
  action?: {
    label: string
    onClick: () => void
  }
}

/**
 * Type-safe event emitters
 */
export const events = {
  signal: {
    new: (data: SignalEvent) => eventBus.emit('signal:new', data, 'brain'),
    executed: (data: SignalEvent) => eventBus.emit('signal:executed', data, 'execution'),
    expired: (data: { id: string }) => eventBus.emit('signal:expired', data, 'brain')
  },

  trade: {
    opened: (data: TradeEvent) => eventBus.emit('trade:opened', data, 'execution'),
    closed: (data: TradeEvent) => eventBus.emit('trade:closed', data, 'execution'),
    updated: (data: TradeEvent) => eventBus.emit('trade:updated', data, 'execution')
  },

  risk: {
    alert: (data: RiskAlertEvent) => eventBus.emit('risk:alert', data, 'risk'),
    limitReached: (data: { type: string; current: number; limit: number }) =>
      eventBus.emit('risk:limit_reached', data, 'risk'),
    killswitch: () => eventBus.emit('risk:killswitch', { triggered: true }, 'risk')
  },

  notification: {
    show: (data: NotificationEvent) => eventBus.emit('notification:show', data, 'ui'),
    dismiss: (id: string) => eventBus.emit('notification:dismiss', { id }, 'ui')
  },

  connection: {
    open: (data?: { url?: string }) => eventBus.emit('connection:open', data, 'websocket'),
    close: (data?: { code?: number; reason?: string }) =>
      eventBus.emit('connection:close', data, 'websocket'),
    error: (data: { error: string }) => eventBus.emit('connection:error', data, 'websocket'),
    reconnecting: (data: { attempt: number; delay: number }) =>
      eventBus.emit('connection:reconnecting', data, 'websocket')
  },

  brain: {
    signal: (data: SignalEvent) => eventBus.emit('brain:signal', data, 'brain'),
    regimeChange: (data: { from: string; to: string; confidence: number }) =>
      eventBus.emit('brain:regime_change', data, 'brain'),
    driftDetected: (data: { type: string; score: number }) =>
      eventBus.emit('brain:drift_detected', data, 'brain')
  }
}

// Export the bus instance for advanced use cases
export { eventBus }
