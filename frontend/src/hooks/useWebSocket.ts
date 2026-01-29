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

export type ChannelType = 
  | 'market_data'
  | 'order_book'
  | 'signals'
  | 'portfolio'
  | 'risk'
  | 'executions'
  | 'alerts'
  | 'system';

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
  subscribe: (channel: ChannelType, symbols?: string[]) => void;
  unsubscribe: (channel: ChannelType) => void;
  send: (message: any) => void;
  connect: () => void;
  disconnect: () => void;
}

// Use environment variable or default to localhost:8000
const WS_HOST = import.meta.env.VITE_WS_URL || `ws://${window.location.hostname}:8000`;
const DEFAULT_WS_URL = `${WS_HOST}/ws/connect`;

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
        wsRef.current.send(JSON.stringify({ type: 'heartbeat' }));
      }
    }, heartbeatInterval);
  }, [heartbeatInterval]);

  const processPendingSubscriptions = useCallback(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    
    while (pendingSubscriptionsRef.current.length > 0) {
      const sub = pendingSubscriptionsRef.current.shift();
      if (sub) {
        wsRef.current.send(JSON.stringify({
          type: 'subscribe',
          channel: sub.channel,
          symbols: sub.symbols || [],
        }));
      }
    }
  }, []);

  const resubscribeAll = useCallback(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    
    // Re-subscribe to all previously active subscriptions
    activeSubscriptionsRef.current.forEach((symbols, channel) => {
      wsRef.current?.send(JSON.stringify({
        type: 'subscribe',
        channel,
        symbols,
      }));
    });
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
        console.log('[WebSocket] Connected');
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
        console.log('[WebSocket] Disconnected', event.code, event.reason);
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
          
          console.log(`[WebSocket] Reconnecting in ${delay}ms... (attempt ${reconnectAttemptsRef.current})`);
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
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);

          // Handle ACK with client_id
          if (message.type === 'ack' && message.client_id) {
            setClientId(message.client_id);
          }

          // Track successful subscriptions
          if (message.type === 'ack' && message.action === 'subscribe' && message.channel) {
            const symbols = (message as any).symbols || [];
            activeSubscriptionsRef.current.set(message.channel as ChannelType, symbols);
          }

          // Track unsubscriptions
          if (message.type === 'ack' && message.action === 'unsubscribe' && message.channel) {
            activeSubscriptionsRef.current.delete(message.channel as ChannelType);
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

  const subscribe = useCallback((channel: ChannelType, symbols?: string[]) => {
    const subscription = { channel, symbols };
    
    // Track the intended subscription
    activeSubscriptionsRef.current.set(channel, symbols || []);
    
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      send({
        type: 'subscribe',
        channel,
        symbols: symbols || [],
      });
    } else {
      // Queue subscription for when connected
      pendingSubscriptionsRef.current.push(subscription);
    }
  }, [send]);

  const unsubscribe = useCallback((channel: ChannelType) => {
    activeSubscriptionsRef.current.delete(channel);
    
    // Remove from pending if queued
    pendingSubscriptionsRef.current = pendingSubscriptionsRef.current.filter(
      sub => sub.channel !== channel
    );
    
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      send({
        type: 'unsubscribe',
        channel,
      });
    }
  }, [send]);

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
      if (message.channel === 'market_data' && message.type === 'data') {
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
      subscribe('market_data', symbols);
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
  return useChannel<RiskMetrics>('risk');
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
      if (message.channel === 'alerts' && message.type === 'data') {
        setAlerts((prev) => [message.data as Alert, ...prev].slice(0, 50));
      }
    },
  });

  useEffect(() => {
    if (isConnected) {
      subscribe('alerts');
    }
  }, [isConnected]); // eslint-disable-line react-hooks/exhaustive-deps

  return { alerts, isConnected };
}

export default useWebSocket;
