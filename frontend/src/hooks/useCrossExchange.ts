/**
 * Cross-Exchange Arbitrage Data Hooks
 * QUANT_INDUSTRY_V1
 */

import { useState, useCallback, useEffect } from 'react';
import {
  PriceMatrix,
  ArbOpportunity,
  TriangularArbPath,
  CexDexSpread,
  CexDexSpreadHistory,
  ExchangeLatency,
  ArbExecution,
} from '@/types/cross-exchange';

const API_BASE = '/api/v1/arbitrage';

interface UseCrossExchangeOptions {
  symbol?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export function usePriceMatrix(options: UseCrossExchangeOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 2000 } = options;
  const [data, setData] = useState<PriceMatrix[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = symbol ? `?symbol=${symbol}` : '';
      const response = await fetch(`${API_BASE}/prices${params}`);
      if (!response.ok) throw new Error('Failed to fetch price matrix');
      const result = await response.json();
      setData(result.data || result);
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

export function useArbOpportunities(options: UseCrossExchangeOptions = {}) {
  const { autoRefresh = true, refreshInterval = 1000 } = options;
  const [opportunities, setOpportunities] = useState<ArbOpportunity[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/opportunities`);
      if (!response.ok) throw new Error('Failed to fetch opportunities');
      const result = await response.json();
      setOpportunities(result.data || result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const executeOpportunity = useCallback(async (id: string) => {
    try {
      const response = await fetch(`${API_BASE}/opportunities/${id}/execute`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to execute opportunity');
      const result = await response.json();
      await fetchData();
      return result;
    } catch (e) {
      throw e;
    }
  }, [fetchData]);

  useEffect(() => {
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, autoRefresh, refreshInterval]);

  return { opportunities, isLoading, error, refresh: fetchData, executeOpportunity };
}

export function useTriangularArb(options: UseCrossExchangeOptions = {}) {
  const { autoRefresh = true, refreshInterval = 2000 } = options;
  const [paths, setPaths] = useState<TriangularArbPath[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/triangular`);
      if (!response.ok) throw new Error('Failed to fetch triangular arb');
      const result = await response.json();
      setPaths(result.data || result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, autoRefresh, refreshInterval]);

  return { paths, isLoading, error, refresh: fetchData };
}

export function useCexDexSpread(symbol: string, options: Omit<UseCrossExchangeOptions, 'symbol'> = {}) {
  const { autoRefresh = true, refreshInterval = 5000 } = options;
  const [spread, setSpread] = useState<CexDexSpread | null>(null);
  const [history, setHistory] = useState<CexDexSpreadHistory | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol) return;
    setIsLoading(true);
    try {
      const [spreadRes, historyRes] = await Promise.all([
        fetch(`${API_BASE}/cex-dex/${symbol}`),
        fetch(`${API_BASE}/cex-dex/${symbol}/history`),
      ]);
      
      if (spreadRes.ok) {
        const spreadData = await spreadRes.json();
        setSpread(spreadData);
      }
      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setHistory(historyData);
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

  return { spread, history, isLoading, error, refresh: fetchData };
}

export function useExchangeLatency(options: UseCrossExchangeOptions = {}) {
  const { autoRefresh = true, refreshInterval = 5000 } = options;
  const [latencies, setLatencies] = useState<ExchangeLatency[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/latency`);
      if (!response.ok) throw new Error('Failed to fetch latency');
      const result = await response.json();
      setLatencies(result.data || result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, autoRefresh, refreshInterval]);

  return { latencies, isLoading, error, refresh: fetchData };
}

export function useArbExecutions(options: UseCrossExchangeOptions = {}) {
  const { autoRefresh = true, refreshInterval = 10000 } = options;
  const [executions, setExecutions] = useState<ArbExecution[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/executions`);
      if (!response.ok) throw new Error('Failed to fetch executions');
      const result = await response.json();
      setExecutions(result.data || result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, autoRefresh, refreshInterval]);

  return { executions, isLoading, error, refresh: fetchData };
}
