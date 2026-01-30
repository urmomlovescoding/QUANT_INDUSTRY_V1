/**
 * Cross-Exchange Arbitrage Data Hooks
 * QUANT_INDUSTRY_V1
 * Uses the v2 API client for type-safe requests.
 */

import { useState, useCallback, useEffect } from 'react';
import { apiV2 } from '@/api/v2';
import type { ApiResponse } from '@/api/v2';
import {
  PriceMatrix,
  ArbOpportunity,
  TriangularArbPath,
  CexDexSpread,
  CexDexSpreadHistory,
  ExchangeLatency,
  ArbExecution,
} from '@/types/cross-exchange';

interface UseCrossExchangeOptions {
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

export function usePriceMatrix(options: UseCrossExchangeOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 2000 } = options;
  const [data, setData] = useState<PriceMatrix[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await apiV2.arbitrage.getPrices(symbol);
      if (response.ok && response.data) {
        const result = response.data as PriceMatrix[] | { data: PriceMatrix[] };
        setData(Array.isArray(result) ? result : result.data || []);
        setError(null);
      } else {
        throw new Error(getErrorMessage(response));
      }
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
      const response = await apiV2.arbitrage.getOpportunities();
      if (response.ok && response.data) {
        const result = response.data as ArbOpportunity[] | { data: ArbOpportunity[] };
        setOpportunities(Array.isArray(result) ? result : result.data || []);
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

  const executeOpportunity = useCallback(async (id: string) => {
    try {
      const response = await apiV2.arbitrage.executeOpportunity(id);
      if (!response.ok) {
        throw new Error(getErrorMessage(response));
      }
      await fetchData();
      return response.data;
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
      const response = await apiV2.arbitrage.getTriangularPaths();
      if (response.ok && response.data) {
        const result = response.data as TriangularArbPath[] | { data: TriangularArbPath[] };
        setPaths(Array.isArray(result) ? result : result.data || []);
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
        apiV2.arbitrage.getCexDexSpread(symbol),
        apiV2.arbitrage.getCexDexHistory(symbol),
      ]);
      
      if (spreadRes.ok && spreadRes.data) {
        setSpread(spreadRes.data as CexDexSpread);
      }
      if (historyRes.ok && historyRes.data) {
        setHistory(historyRes.data as CexDexSpreadHistory);
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
      const response = await apiV2.arbitrage.getLatency();
      if (response.ok && response.data) {
        const result = response.data as ExchangeLatency[] | { data: ExchangeLatency[] };
        setLatencies(Array.isArray(result) ? result : result.data || []);
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
      const response = await apiV2.arbitrage.getExecutions();
      if (response.ok && response.data) {
        const result = response.data as ArbExecution[] | { data: ArbExecution[] };
        setExecutions(Array.isArray(result) ? result : result.data || []);
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
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, autoRefresh, refreshInterval]);

  return { executions, isLoading, error, refresh: fetchData };
}
