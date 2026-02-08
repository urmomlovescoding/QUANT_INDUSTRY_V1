/**
 * Microstructure Data Hooks
 * QUANT_INDUSTRY_V1
 * Uses the v2 API client for type-safe requests.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { apiV2 } from '@/api/v2';
import type { ApiResponse } from '@/api/v2';
import {
  OrderBook,
  OrderBookHeatmapData,
  ImbalanceMetrics,
  TapeEntry,
  TapeAnalysis,
  FlowModelMetrics,
  OrderFlowBacktestResult,
} from '@/types/microstructure';

interface UseMicrostructureOptions {
  symbol?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

/**
 * Helper to extract error message from ApiResponse
 */
function getErrorMessage(response: ApiResponse<unknown>): string {
  return response.error?.message || 'Unknown error';
}

export function useOrderBook(symbol: string, options: Omit<UseMicrostructureOptions, 'symbol'> = {}) {
  const { autoRefresh = true, refreshInterval = 1000 } = options;
  const [data, setData] = useState<OrderBook | null>(null);
  const [history, setHistory] = useState<OrderBookHeatmapData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    if (!symbol || !mountedRef.current) return;
    setIsLoading(true);
    try {
      const response = await apiV2.microstructure.getOrderBook(symbol);
      if (!mountedRef.current) return;
      if (response.ok && response.data) {
        const result = response.data as unknown as OrderBook;
        setData(result);

        // Append to history for heatmap
        if (result.bids && result.asks) {
          const heatmapEntry: OrderBookHeatmapData = {
            timestamp: result.timestamp,
            priceLevel: result.midPrice,
            bidSize: result.bids.reduce((sum: number, b: { size: number }) => sum + b.size, 0),
            askSize: result.asks.reduce((sum: number, a: { size: number }) => sum + a.size, 0),
            intensity: Math.abs(result.imbalance),
          };
          setHistory(prev => [...prev.slice(-100), heatmapEntry]);
        }
        setError(null);
      } else {
        throw new Error(getErrorMessage(response));
      }
    } catch (e) {
      if (mountedRef.current) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [symbol]);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => {
        mountedRef.current = false;
        clearInterval(interval);
      };
    }
    return () => { mountedRef.current = false; };
  }, [fetchData, autoRefresh, refreshInterval]);

  return { data, history, isLoading, error, refresh: fetchData };
}

export function useImbalance(symbol: string, options: Omit<UseMicrostructureOptions, 'symbol'> = {}) {
  const { autoRefresh = true, refreshInterval = 2000 } = options;
  const [data, setData] = useState<ImbalanceMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    if (!symbol || !mountedRef.current) return;
    setIsLoading(true);
    try {
      const response = await apiV2.microstructure.getImbalance(symbol);
      if (!mountedRef.current) return;
      if (response.ok && response.data) {
        setData(response.data as unknown as ImbalanceMetrics);
        setError(null);
      } else {
        throw new Error(getErrorMessage(response));
      }
    } catch (e) {
      if (mountedRef.current) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [symbol]);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => {
        mountedRef.current = false;
        clearInterval(interval);
      };
    }
    return () => { mountedRef.current = false; };
  }, [fetchData, autoRefresh, refreshInterval]);

  return { data, isLoading, error, refresh: fetchData };
}

export function useTape(symbol: string, options: Omit<UseMicrostructureOptions, 'symbol'> = {}) {
  const { autoRefresh = true, refreshInterval = 500 } = options;
  const [entries, setEntries] = useState<TapeEntry[]>([]);
  const [analysis, setAnalysis] = useState<TapeAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    if (!symbol || !mountedRef.current) return;
    setIsLoading(true);
    try {
      const [entriesRes, analysisRes] = await Promise.all([
        apiV2.microstructure.getTape(symbol, 100),
        apiV2.microstructure.getTapeAnalysis(symbol),
      ]);

      if (!mountedRef.current) return;
      if (entriesRes.ok && entriesRes.data) {
        const result = entriesRes.data as unknown as TapeEntry[] | { data: TapeEntry[] };
        setEntries(Array.isArray(result) ? result : result.data || []);
      }
      if (analysisRes.ok && analysisRes.data) {
        setAnalysis(analysisRes.data as unknown as TapeAnalysis);
      }
      setError(null);
    } catch (e) {
      if (mountedRef.current) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [symbol]);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => {
        mountedRef.current = false;
        clearInterval(interval);
      };
    }
    return () => { mountedRef.current = false; };
  }, [fetchData, autoRefresh, refreshInterval]);

  return { entries, analysis, isLoading, error, refresh: fetchData };
}

export function useFlowModels() {
  const [metrics, setMetrics] = useState<FlowModelMetrics[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await apiV2.microstructure.getModelMetrics();
      if (response.ok && response.data) {
        const result = response.data as unknown as FlowModelMetrics[] | { data: FlowModelMetrics[] };
        setMetrics(Array.isArray(result) ? result : result.data || []);
        setError(null);
      } else {
        throw new Error(getErrorMessage(response));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return { metrics, isLoading, error, refresh: fetchData };
}

export function useFlowBacktest() {
  const [results, setResults] = useState<OrderFlowBacktestResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await apiV2.microstructure.getBacktestResults();
      if (response.ok && response.data) {
        const result = response.data as unknown as OrderFlowBacktestResult[] | { data: OrderFlowBacktestResult[] };
        setResults(Array.isArray(result) ? result : result.data || []);
        setError(null);
      } else {
        throw new Error(getErrorMessage(response));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const runBacktest = useCallback(async (config: Record<string, unknown>) => {
    setIsLoading(true);
    try {
      const response = await apiV2.microstructure.runBacktest(config);
      if (!response.ok) {
        throw new Error(getErrorMessage(response));
      }
      const result = response.data as unknown as OrderFlowBacktestResult;
      setResults(prev => [result, ...prev]);
      setError(null);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
      throw e;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { results, isLoading, error, refresh: fetchData, runBacktest };
}
