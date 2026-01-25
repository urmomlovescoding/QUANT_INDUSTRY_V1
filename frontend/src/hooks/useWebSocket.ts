/**
 * Enhanced WebSocket Hook for Real-Time Data Streaming
 * Supports multiple channels: market, signals, trades, brain, system, flow, futures, portfolio
 */

import { useState, useEffect, useCallback, useRef } from 'react'

export type WebSocketChannel =
  | 'market'
  | 'signals'
  | 'trades'
  | 'brain'
  | 'system'
  | 'flow'
  | 'futures'
  | 'portfolio'

export interface WebSocketMessage {
  type: string
  channel?: string
  timestamp?: string
  data?: any
  [key: string]: any
}

export interface MarketTick {
  symbol: string
  price: number
  bid: number
  ask: number
  volume: number
  change: number
  change_pct: number
  timestamp: string
}

export interface TradingSignal {
  id: string
  symbol: string
  direction: 'LONG' | 'SHORT'
  confidence: number
  strategy: string
  entry_price: number
  stop_loss: number
  take_profit: number
  risk_reward: number
  timeframe: string
  regime_alignment: boolean
  timestamp: string
}

export interface TradeUpdate {
  id: string
  symbol: string
  type: 'FILLED' | 'PARTIAL' | 'CANCELLED' | 'CLOSED'
  side: 'BUY' | 'SELL'
  quantity: number
  price: number
  pnl?: number
  commission: number
  timestamp: string
}

export interface FlowUpdate {
  id: string
  symbol: string
  type: 'CALL' | 'PUT'
  side: 'BUY' | 'SELL'
  sentiment: 'BULLISH' | 'BEARISH'
  strike: number
  expiry: string
  premium: number
  contracts: number
  is_unusual: boolean
  is_sweep: boolean
  timestamp: string
}

export interface BrainUpdate {
  type: string
  confidence: number
  accuracy: number
  signals_generated: number
  winning_signals: number
  active_strategies: number
  regime: 'TRENDING' | 'RANGING' | 'VOLATILE' | 'QUIET'
  volatility_regime: string
  active_signals: number
  recent_accuracy: number
  timestamp: string
}

export interface SystemHealth {
  type: string
  cpu_percent: number
  memory_percent: number
  gpu_percent: number
  disk_io: number
  network_latency_ms: number
  api_latency_ms: number
  active_connections: number
  messages_per_second: number
  uptime_hours: number
  timestamp: string
}

interface UseWebSocketOptions {
  autoConnect?: boolean
  reconnectAttempts?: number
  reconnectInterval?: number
  maxReconnectInterval?: number
  useExponentialBackoff?: boolean
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  onReconnecting?: (attempt: number, delay: number) => void
}

interface UseWebSocketReturn {
  isConnected: boolean
  connectionId: string | null
  lastMessage: WebSocketMessage | null
  reconnectAttempt: number
  subscribe: (channels: WebSocketChannel[]) => void
  unsubscribe: (channels: WebSocketChannel[]) => void
  sendMessage: (message: object) => void
  connect: () => void
  disconnect: () => void
}

/**
 * Calculate reconnection delay with exponential backoff and jitter.
 * Matches quant-platform pattern for reliable reconnection.
 */
function calculateBackoffDelay(
  attempt: number,
  baseInterval: number,
  maxInterval: number
): number {
  // Exponential backoff: baseInterval * 2^attempt
  const exponentialDelay = baseInterval * Math.pow(2, attempt)

  // Cap at max interval
  const cappedDelay = Math.min(exponentialDelay, maxInterval)

  // Add random jitter (0-25% of delay) to prevent thundering herd
  const jitter = cappedDelay * Math.random() * 0.25

  return Math.floor(cappedDelay + jitter)
}

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

/**
 * Hook for unified WebSocket connection with channel subscriptions
 * Includes exponential backoff with jitter for reliable reconnection.
 */
export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    autoConnect = true,
    reconnectAttempts = 10,
    reconnectInterval = 1000,  // Base interval (1 second)
    maxReconnectInterval = 30000,  // Max 30 seconds
    useExponentialBackoff = true,
    onOpen,
    onClose,
    onError,
    onReconnecting,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [connectionId, setConnectionId] = useState<string | null>(null)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCountRef = useRef(0)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      wsRef.current = new WebSocket(`${WS_BASE_URL}/ws/unified`)

      wsRef.current.onopen = () => {
        setIsConnected(true)
        reconnectCountRef.current = 0
        setReconnectAttempt(0)
        console.log('[WebSocket] Connected successfully')
        onOpen?.()
      }

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          setLastMessage(message)

          if (message.type === 'connected') {
            setConnectionId(message.connection_id)
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }

      wsRef.current.onclose = () => {
        setIsConnected(false)
        setConnectionId(null)
        onClose?.()

        // Auto reconnect with exponential backoff
        if (reconnectCountRef.current < reconnectAttempts) {
          const delay = useExponentialBackoff
            ? calculateBackoffDelay(reconnectCountRef.current, reconnectInterval, maxReconnectInterval)
            : reconnectInterval

          console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectCountRef.current + 1}/${reconnectAttempts})`)
          onReconnecting?.(reconnectCountRef.current + 1, delay)

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectCountRef.current++
            setReconnectAttempt(reconnectCountRef.current)
            connect()
          }, delay)
        } else {
          console.warn('[WebSocket] Max reconnection attempts reached')
        }
      }

      wsRef.current.onerror = (error) => {
        console.error('[WebSocket] Connection error:', error)
        onError?.(error)
      }
    } catch (e) {
      console.error('WebSocket connection error:', e)
    }
  }, [onOpen, onClose, onError, onReconnecting, reconnectAttempts, reconnectInterval, maxReconnectInterval, useExponentialBackoff])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    reconnectCountRef.current = reconnectAttempts // Prevent reconnection
    wsRef.current?.close()
    wsRef.current = null
    setIsConnected(false)
    setConnectionId(null)
  }, [reconnectAttempts])

  const subscribe = useCallback((channels: WebSocketChannel[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'subscribe',
        channels
      }))
    }
  }, [])

  const unsubscribe = useCallback((channels: WebSocketChannel[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'unsubscribe',
        channels
      }))
    }
  }, [])

  const sendMessage = useCallback((message: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  useEffect(() => {
    if (autoConnect) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [autoConnect, connect, disconnect])

  return {
    isConnected,
    connectionId,
    lastMessage,
    reconnectAttempt,
    subscribe,
    unsubscribe,
    sendMessage,
    connect,
    disconnect,
  }
}

/**
 * Hook for direct channel connection (simpler, single-purpose)
 * Handles React StrictMode double-mounting gracefully
 */
export function useChannelWebSocket<T = any>(
  channel: WebSocketChannel,
  options: UseWebSocketOptions = {}
) {
  const [data, setData] = useState<T | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const optionsRef = useRef(options)
  const disconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const mountedRef = useRef(true)

  // Update options ref on change
  useEffect(() => {
    optionsRef.current = options
  }, [options])

  const connect = useCallback(() => {
    // Cancel any pending disconnect (handles StrictMode remount)
    if (disconnectTimeoutRef.current) {
      clearTimeout(disconnectTimeoutRef.current)
      disconnectTimeoutRef.current = null
    }

    // Don't reconnect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return
    }

    try {
      wsRef.current = new WebSocket(`${WS_BASE_URL}/ws/${channel}`)

      wsRef.current.onopen = () => {
        if (mountedRef.current) {
          setIsConnected(true)
          optionsRef.current.onOpen?.()
        }
      }

      wsRef.current.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const message = JSON.parse(event.data)
          setData(message.data || message)
        } catch (e) {
          console.error('Failed to parse message:', e)
        }
      }

      wsRef.current.onclose = () => {
        if (mountedRef.current) {
          setIsConnected(false)
          optionsRef.current.onClose?.()
        }
      }

      wsRef.current.onerror = (error) => {
        optionsRef.current.onError?.(error)
      }
    } catch (e) {
      console.error('WebSocket connection error:', e)
    }
  }, [channel])

  const disconnect = useCallback(() => {
    if (disconnectTimeoutRef.current) {
      clearTimeout(disconnectTimeoutRef.current)
      disconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      // Delay disconnect to allow StrictMode to remount
      disconnectTimeoutRef.current = setTimeout(() => {
        if (!mountedRef.current && wsRef.current) {
          wsRef.current.close()
          wsRef.current = null
        }
      }, 100)
    }
  }, [channel, connect])

  return { data, isConnected, connect, disconnect }
}

/**
 * Hook specifically for market data with typed updates
 */
export function useMarketData() {
  const [tickers, setTickers] = useState<MarketTick[]>([])
  const { data, isConnected } = useChannelWebSocket<MarketTick[]>('market')

  useEffect(() => {
    if (data) {
      setTickers(data)
    }
  }, [data])

  return { tickers, isConnected }
}

/**
 * Hook specifically for trading signals
 */
export function useSignals() {
  const [signals, setSignals] = useState<TradingSignal[]>([])
  const [latestSignal, setLatestSignal] = useState<TradingSignal | null>(null)

  const { lastMessage, isConnected, subscribe } = useWebSocket()

  useEffect(() => {
    if (isConnected) {
      subscribe(['signals'])
    }
  }, [isConnected, subscribe])

  useEffect(() => {
    if (lastMessage?.channel === 'signals') {
      if (lastMessage.type === 'signal_history') {
        setSignals(lastMessage.data || [])
      } else if (lastMessage.type === 'new_signal') {
        const signal = lastMessage.data as TradingSignal
        setLatestSignal(signal)
        setSignals(prev => [signal, ...prev.slice(0, 49)])
      }
    }
  }, [lastMessage])

  return { signals, latestSignal, isConnected }
}

/**
 * Hook specifically for brain status
 */
export function useBrainStatus() {
  const [status, setStatus] = useState<BrainUpdate | null>(null)
  const { data, isConnected } = useChannelWebSocket<BrainUpdate>('brain')

  useEffect(() => {
    if (data) {
      setStatus(data)
    }
  }, [data])

  return { status, isConnected }
}

/**
 * Hook specifically for options flow
 */
export function useOptionsFlow() {
  const [flows, setFlows] = useState<FlowUpdate[]>([])

  const { lastMessage, isConnected, subscribe } = useWebSocket()

  useEffect(() => {
    if (isConnected) {
      subscribe(['flow'])
    }
  }, [isConnected, subscribe])

  useEffect(() => {
    if (lastMessage?.channel === 'flow' && lastMessage.type === 'flow_update') {
      const flow = lastMessage.data as FlowUpdate
      setFlows(prev => [flow, ...prev.slice(0, 99)])
    }
  }, [lastMessage])

  return { flows, isConnected }
}

/**
 * Hook for system health monitoring
 */
export function useSystemHealth() {
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const { data, isConnected } = useChannelWebSocket<SystemHealth>('system')

  useEffect(() => {
    if (data) {
      setHealth(data)
    }
  }, [data])

  return { health, isConnected }
}
