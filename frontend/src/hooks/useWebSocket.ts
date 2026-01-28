/**
 * WebSocket Hook - Real-time Data Connection
 * QUANT_INDUSTRY_V1
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

export interface WebSocketMessage {
  type: MessageType;
  channel?: ChannelType;
  data?: any;
  timestamp?: string;
  error?: string;
  client_id?: string;
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
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  clientId: string | null;
  lastMessage: WebSocketMessage | null;
  subscribe: (channel: ChannelType, symbols?: string[]) => void;
  unsubscribe: (channel: ChannelType) => void;
  send: (message: any) => void;
  connect: () => void;
  disconnect: () => void;
}

const DEFAULT_WS_URL = `ws://${window.location.hostname}:8000/ws/connect`;

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    url = DEFAULT_WS_URL,
    autoConnect = true,
    reconnect = true,
    reconnectInterval = 5000,
    maxReconnectAttempts = 10,
    heartbeatInterval = 30000,
    onOpen,
    onClose,
    onError,
    onMessage,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [clientId, setClientId] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimeoutRef = useRef<NodeJS.Timeout | null>(null);

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
    heartbeatTimeoutRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'heartbeat' }));
      }
    }, heartbeatInterval);
  }, [heartbeatInterval]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        console.log('[WebSocket] Connected');
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        startHeartbeat();
        onOpen?.();
      };

      wsRef.current.onclose = () => {
        console.log('[WebSocket] Disconnected');
        setIsConnected(false);
        setClientId(null);
        clearTimeouts();
        onClose?.();

        // Attempt reconnection
        if (reconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1;
          console.log(`[WebSocket] Reconnecting... (attempt ${reconnectAttemptsRef.current})`);
          reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
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

          onMessage?.(message);
        } catch (error) {
          console.error('[WebSocket] Failed to parse message:', error);
        }
      };
    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
    }
  }, [url, reconnect, reconnectInterval, maxReconnectAttempts, onOpen, onClose, onError, onMessage, startHeartbeat, clearTimeouts]);

  const disconnect = useCallback(() => {
    clearTimeouts();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
    setClientId(null);
  }, [clearTimeouts]);

  const send = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('[WebSocket] Cannot send - not connected');
    }
  }, []);

  const subscribe = useCallback((channel: ChannelType, symbols?: string[]) => {
    send({
      type: 'subscribe',
      channel,
      symbols: symbols || [],
    });
  }, [send]);

  const unsubscribe = useCallback((channel: ChannelType) => {
    send({
      type: 'unsubscribe',
      channel,
    });
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
    clientId,
    lastMessage,
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
