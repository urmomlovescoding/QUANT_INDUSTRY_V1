/**
 * Microstructure Data Hooks
 * QUANT_INDUSTRY_V1
 */

import { useState, useCallback, useEffect } from 'react';
import {
  OrderBook,
  OrderBookHeatmapData,
  ImbalanceMetrics,
  TapeEntry,
  TapeAnalysis,
  FlowModelMetrics,
  OrderFlowBacktestResult,
} from '@/types/microstructure';

const API_BASE = '/api/v1/microstructure';

interface UseMicrostructureOptions {
  symbol?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export function useOrderBook(symbol: string, options: Omit<UseMicrostructureOptions, 'symbol'> = {}) {
  const { autoRefresh = true, refreshInterval = 1000 } = options;
  const [data, setData] = useState<OrderBook | null>(null);
  const [history, setHistory] = useState<OrderBookHeatmapData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/orderbook/${symbol}`);
      if (!response.ok) throw new Error('Failed to fetch order book');
      const result = await response.json();
      setData(result);
      
      // Append to history for heatmap
      if (result.bids && result.asks) {
        const heatmapEntry: OrderBookHeatmapData = {
          timestamp: result.timestamp,
          priceLevel: result.midPrice,
          bidSize: result.bids.reduce((sum: number, b: any) => sum + b.size, 0),
          askSize: result.asks.reduce((sum: number, a: any) => sum + a.size, 0),
          intensity: Math.abs(result.imbalance),
        };
        setHistory(prev => [...prev.slice(-100), heatmapEntry]);
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, autoRefresh, refreshInterval]);

  return { data, history, isLoading, error, refresh: fetchData };
}

export function useImbalance(symbol: string, options: Omit<UseMicrostructureOptions, 'symbol'> = {}) {
  const { autoRefresh = true, refreshInterval = 2000 } = options;
  const [data, setData] = useState<ImbalanceMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/imbalance/${symbol}`);
      if (!response.ok) throw new Error('Failed to fetch imbalance');
      const result = await response.json();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, autoRefresh, refreshInterval]);

  return { data, isLoading, error, refresh: fetchData };
}

export function useTape(symbol: string, options: Omit<UseMicrostructureOptions, 'symbol'> = {}) {
  const { autoRefresh = true, refreshInterval = 500 } = options;
  const [entries, setEntries] = useState<TapeEntry[]>([]);
  const [analysis, setAnalysis] = useState<TapeAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol) return;
    setIsLoading(true);
    try {
      const [entriesRes, analysisRes] = await Promise.all([
        fetch(`${API_BASE}/tape/${symbol}?limit=100`),
        fetch(`${API_BASE}/tape/${symbol}/analysis`),
      ]);
      
      if (entriesRes.ok) {
        const entriesData = await entriesRes.json();
        setEntries(entriesData.data || entriesData);
      }
      if (analysisRes.ok) {
        const analysisData = await analysisRes.json();
        setAnalysis(analysisData);
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
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
      const response = await fetch(`${API_BASE}/models/metrics`);
      if (!response.ok) throw new Error('Failed to fetch model metrics');
      const result = await response.json();
      setMetrics(result.data || result);
      setError(null);
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
      const response = await fetch(`${API_BASE}/backtest/results`);
      if (!response.ok) throw new Error('Failed to fetch backtest results');
      const result = await response.json();
      setResults(result.data || result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const runBacktest = useCallback(async (config: any) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/backtest/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!response.ok) throw new Error('Failed to run backtest');
      const result = await response.json();
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
