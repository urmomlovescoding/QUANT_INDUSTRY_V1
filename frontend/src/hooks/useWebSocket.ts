/**
 * WebSocket Hook - Real-time Data Connection
 * QUANT_INDUSTRY_V1
 * 
 * Features:
 * - Auto-reconnection with exponential backoff
 * - Subscription queue for pending subscriptions
 * - Connection state management
 * - Heartbeat monitoring
 */

import { useEffect, useRef, useState, useCallback } from 'react';

// Channel types matching backend websocket_routes.py channel_subscribers
export type ChannelType =
  | 'market'      // Real-time market data (backend: "market")
  | 'signals'     // Trading signals (backend: "signals")
  | 'trades'      // Trade executions (backend: "trades")
  | 'brain'       // AI brain status (backend: "brain")
  | 'system'      // System health (backend: "system")
  | 'flow';       // Options flow (backend: "flow")

// Legacy channel names for backward compatibility (map to backend channels)
export type LegacyChannelType =
  | 'market_data'  // maps to 'market'
  | 'order_book'   // maps to 'market'
  | 'portfolio'    // maps to 'trades'
  | 'risk'         // maps to 'system'
  | 'executions'   // maps to 'trades'
  | 'alerts';      // maps to 'system'

// Map legacy channel names to backend channel names
const CHANNEL_MAP: Record<string, ChannelType> = {
  'market_data': 'market',
  'order_book': 'market',
  'portfolio': 'trades',
  'risk': 'system',
  'executions': 'trades',
  'alerts': 'system',
  // Direct mappings
  'market': 'market',
  'signals': 'signals',
  'trades': 'trades',
  'brain': 'brain',
  'system': 'system',
  'flow': 'flow',
};

function mapChannel(channel: string): ChannelType {
  return CHANNEL_MAP[channel] || 'market';
}

export type MessageType = 
  | 'subscribe'
  | 'unsubscribe'
  | 'data'
  | 'error'
  | 'ack'
  | 'heartbeat';

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

export interface WebSocketMessage {
  type: MessageType;
  channel?: ChannelType;
  data?: any;
  timestamp?: string;
  error?: string;
  client_id?: string;
  action?: string;
}

export interface UseWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
  reconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  onMessage?: (message: WebSocketMessage) => void;
  onReconnecting?: (attempt: number) => void;
  onReconnectFailed?: () => void;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  connectionState: ConnectionState;
  clientId: string | null;
  lastMessage: WebSocketMessage | null;
  reconnectAttempt: number;
  subscribe: (channel: ChannelType | LegacyChannelType | string, symbols?: string[]) => void;
  unsubscribe: (channel: ChannelType | LegacyChannelType | string) => void;
  send: (message: any) => void;
  connect: () => void;
  disconnect: () => void;
}

// Use environment variable or default based on environment
// In dev mode, Vite proxy handles /ws/* -> ws://localhost:8000
// In production, use explicit WS URL or same host as page
const WS_HOST = import.meta.env.VITE_WS_URL ||
  (import.meta.env.DEV ? '' : `ws://${window.location.hostname}:8000`);
// FIXED: Use /ws/unified endpoint which exists on backend (not /ws/connect)
const DEFAULT_WS_URL = `${WS_HOST}/ws/unified`;

interface PendingSubscription {
  channel: ChannelType;
  symbols?: string[];
}

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    url = DEFAULT_WS_URL,
    autoConnect = true,
    reconnect = true,
    reconnectInterval = 2000, // Start with 2s
    maxReconnectAttempts = 10,
    heartbeatInterval = 30000,
    onOpen,
    onClose,
    onError,
    onMessage,
    onReconnecting,
    onReconnectFailed,
  } = options;

  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [clientId, setClientId] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimeoutRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingSubscriptionsRef = useRef<PendingSubscription[]>([]);
  const activeSubscriptionsRef = useRef<Map<ChannelType, string[]>>(new Map());
  const isManualDisconnectRef = useRef(false);

  const isConnected = connectionState === 'connected';

  const clearTimeouts = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (heartbeatTimeoutRef.current) {
      clearInterval(heartbeatTimeoutRef.current);
      heartbeatTimeoutRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    if (heartbeatTimeoutRef.current) {
      clearInterval(heartbeatTimeoutRef.current);
    }
    heartbeatTimeoutRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        // Backend expects 'action: ping' not 'type: heartbeat'
        wsRef.current.send(JSON.stringify({ action: 'ping' }));
      }
    }, heartbeatInterval);
  }, [heartbeatInterval]);

  const processPendingSubscriptions = useCallback(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;

    // Collect all pending channels
    const channels: string[] = [];
    while (pendingSubscriptionsRef.current.length > 0) {
      const sub = pendingSubscriptionsRef.current.shift();
      if (sub) {
        const backendChannel = mapChannel(sub.channel);
        if (!channels.includes(backendChannel)) {
          channels.push(backendChannel);
        }
      }
    }

    // Backend expects: { action: 'subscribe', channels: [...] }
    if (channels.length > 0) {
      wsRef.current.send(JSON.stringify({
        action: 'subscribe',
        channels,
      }));
    }
  }, []);

  const resubscribeAll = useCallback(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;

    // Collect all active channels and map to backend names
    const channels: string[] = [];
    activeSubscriptionsRef.current.forEach((symbols, channel) => {
      const backendChannel = mapChannel(channel);
      if (!channels.includes(backendChannel)) {
        channels.push(backendChannel);
      }
    });

    // Backend expects: { action: 'subscribe', channels: [...] }
    if (channels.length > 0) {
      wsRef.current?.send(JSON.stringify({
        action: 'subscribe',
        channels,
      }));
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || 
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    isManualDisconnectRef.current = false;
    setConnectionState(reconnectAttemptsRef.current > 0 ? 'reconnecting' : 'connecting');

    try {
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        if (import.meta.env.DEV) console.log('[WebSocket] Connected');
        setConnectionState('connected');
        reconnectAttemptsRef.current = 0;
        setReconnectAttempt(0);
        startHeartbeat();
        
        // Re-subscribe to previous subscriptions after reconnect
        resubscribeAll();
        
        // Process any pending subscriptions
        processPendingSubscriptions();
        
        onOpen?.();
      };

      wsRef.current.onclose = (event) => {
        if (import.meta.env.DEV) console.log('[WebSocket] Disconnected', event.code, event.reason);
        setConnectionState('disconnected');
        setClientId(null);
        clearTimeouts();
        onClose?.();

        // Don't reconnect if manually disconnected or max attempts reached
        if (isManualDisconnectRef.current) {
          return;
        }

        // Attempt reconnection with exponential backoff
        if (reconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1;
          setReconnectAttempt(reconnectAttemptsRef.current);
          
          // Exponential backoff: 2s, 4s, 8s, 16s, max 30s
          const delay = Math.min(
            reconnectInterval * Math.pow(2, reconnectAttemptsRef.current - 1),
            30000
          );
          
          if (import.meta.env.DEV) console.log(`[WebSocket] Reconnecting in ${delay}ms... (attempt ${reconnectAttemptsRef.current})`);
          onReconnecting?.(reconnectAttemptsRef.current);
          
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.error('[WebSocket] Max reconnection attempts reached');
          onReconnectFailed?.();
        }
      };

      wsRef.current.onerror = (event) => {
        console.error('[WebSocket] Error:', event);
        onError?.(event);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const rawMessage = JSON.parse(event.data);

          // Backend sends various message types:
          // - { type: 'connected', connection_id, available_channels }
          // - { type: 'subscribed' }
          // - { type: 'pong' }
          // - { type: 'market_update', data: [...], timestamp }
          // - { type: 'brain_update', ... }
          // - { type: 'system_health', ... }

          // Normalize to our WebSocketMessage format
          const message: WebSocketMessage = {
            type: rawMessage.type === 'connected' ? 'ack' :
                  rawMessage.type === 'subscribed' ? 'ack' :
                  rawMessage.type === 'pong' ? 'ack' :
                  rawMessage.type?.includes('update') || rawMessage.type?.includes('health') ? 'data' :
                  rawMessage.type === 'error' ? 'error' : 'data',
            channel: rawMessage.channel as ChannelType,
            data: rawMessage.data || rawMessage,
            timestamp: rawMessage.timestamp,
            error: rawMessage.error,
            client_id: rawMessage.connection_id,
            action: rawMessage.type,
          };

          setLastMessage(message);

          // Handle connection confirmation
          if (rawMessage.type === 'connected' && rawMessage.connection_id) {
            setClientId(rawMessage.connection_id);
            console.log('[WebSocket] Connected with ID:', rawMessage.connection_id);
            console.log('[WebSocket] Available channels:', rawMessage.available_channels);
          }

          // Handle subscription confirmation
          if (rawMessage.type === 'subscribed') {
            console.log('[WebSocket] Subscription confirmed');
          }

          // Handle pong (heartbeat response)
          if (rawMessage.type === 'pong') {
            // Heartbeat received, connection is alive
          }

          onMessage?.(message);
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error);
        }
      };
    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
      setConnectionState('disconnected');
    }
  }, [url, reconnect, reconnectInterval, maxReconnectAttempts, onOpen, onClose, onError, onMessage, onReconnecting, onReconnectFailed, startHeartbeat, clearTimeouts, processPendingSubscriptions, resubscribeAll]);

  const disconnect = useCallback(() => {
    isManualDisconnectRef.current = true;
    clearTimeouts();
    reconnectAttemptsRef.current = 0;
    setReconnectAttempt(0);
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect');
      wsRef.current = null;
    }
    setConnectionState('disconnected');
    setClientId(null);
    activeSubscriptionsRef.current.clear();
  }, [clearTimeouts]);

  const send = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    } else {
      console.warn('[WebSocket] Cannot send - not connected');
      return false;
    }
  }, []);

  const subscribe = useCallback((channel: ChannelType | LegacyChannelType | string, symbols?: string[]) => {
    // Map to backend channel name
    const backendChannel = mapChannel(channel);
    const subscription = { channel: backendChannel, symbols };

    // Track the intended subscription
    activeSubscriptionsRef.current.set(backendChannel, symbols || []);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Backend expects: { action: 'subscribe', channels: [...] }
      wsRef.current.send(JSON.stringify({
        action: 'subscribe',
        channels: [backendChannel],
      }));
    } else {
      // Queue subscription for when connected
      pendingSubscriptionsRef.current.push(subscription);
    }
  }, []);

  const unsubscribe = useCallback((channel: ChannelType | LegacyChannelType | string) => {
    const backendChannel = mapChannel(channel);
    activeSubscriptionsRef.current.delete(backendChannel);

    // Remove from pending if queued
    pendingSubscriptionsRef.current = pendingSubscriptionsRef.current.filter(
      sub => mapChannel(sub.channel) !== backendChannel
    );

    // Note: Backend doesn't have unsubscribe - disconnect removes all subscriptions
    // For now, just track locally
    console.log('[WebSocket] Unsubscribed from:', backendChannel);
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    isConnected,
    connectionState,
    clientId,
    lastMessage,
    reconnectAttempt,
    subscribe,
    unsubscribe,
    send,
    connect,
    disconnect,
  };
}

/**
 * Hook for subscribing to specific channels with typed data
 */
export function useChannel<T = any>(
  channel: ChannelType,
  symbols?: string[],
  options?: UseWebSocketOptions
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { isConnected, subscribe, unsubscribe, lastMessage } = useWebSocket({
    ...options,
    onMessage: (message) => {
      if (message.channel === channel) {
        if (message.type === 'data') {
          setData(message.data);
          setError(null);
        } else if (message.type === 'error') {
          setError(message.error || 'Unknown error');
        }
      }
      options?.onMessage?.(message);
    },
  });

  useEffect(() => {
    if (isConnected) {
      subscribe(channel, symbols);
    }

    return () => {
      if (isConnected) {
        unsubscribe(channel);
      }
    };
  }, [isConnected, channel, JSON.stringify(symbols)]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, error, isConnected };
}

/**
 * Hook for real-time market data
 */
export interface MarketData {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  volume: number;
  change: number;
  change_pct: number;
}

export function useMarketData(symbols: string[]) {
  const [quotes, setQuotes] = useState<Record<string, MarketData>>({});

  const { isConnected, subscribe, lastMessage } = useWebSocket({
    onMessage: (message) => {
      // Backend sends channel as 'market' (mapped from legacy 'market_data')
      if (message.channel === 'market' && message.type === 'data') {
        const data = message.data as MarketData;
        setQuotes((prev) => ({
          ...prev,
          [data.symbol]: data,
        }));
      }
    },
  });

  useEffect(() => {
    if (isConnected && symbols.length > 0) {
      // Subscribe using backend channel name 'market'
      subscribe('market', symbols);
    }
  }, [isConnected, JSON.stringify(symbols)]); // eslint-disable-line react-hooks/exhaustive-deps

  return { quotes, isConnected };
}

/**
 * Hook for risk metrics
 */
export interface RiskMetrics {
  var_95: number;
  cvar_95: number;
  portfolio_beta: number;
  current_drawdown: number;
  sector_exposure: Record<string, number>;
  updated_at: string;
}

export function useRiskMetrics() {
  // Risk metrics come through the 'system' channel on backend
  return useChannel<RiskMetrics>('system');
}

/**
 * Hook for trading signals
 */
export interface Signal {
  symbol: string;
  signal_type: string;
  direction: string;
  strength: number;
  metadata: Record<string, any>;
  generated_at: string;
}

export function useSignals(symbols?: string[]) {
  const [signals, setSignals] = useState<Signal[]>([]);

  const { isConnected, subscribe, lastMessage } = useWebSocket({
    onMessage: (message) => {
      if (message.channel === 'signals' && message.type === 'data') {
        setSignals((prev) => [message.data as Signal, ...prev].slice(0, 100));
      }
    },
  });

  useEffect(() => {
    if (isConnected) {
      subscribe('signals', symbols);
    }
  }, [isConnected, JSON.stringify(symbols)]); // eslint-disable-line react-hooks/exhaustive-deps

  return { signals, isConnected };
}

/**
 * Hook for alerts
 */
export interface Alert {
  alert_type: string;
  severity: string;
  message: string;
  details: Record<string, any>;
  triggered_at: string;
}

export function useAlerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  const { isConnected, subscribe, lastMessage } = useWebSocket({
    onMessage: (message) => {
      // Alerts come through the 'system' channel on backend
      if (message.channel === 'system' && message.type === 'data') {
        setAlerts((prev) => [message.data as Alert, ...prev].slice(0, 50));
      }
    },
  });

  useEffect(() => {
    if (isConnected) {
      // Subscribe using backend channel name 'system'
      subscribe('system');
    }
  }, [isConnected]); // eslint-disable-line react-hooks/exhaustive-deps

  return { alerts, isConnected };
}

export default useWebSocket;
