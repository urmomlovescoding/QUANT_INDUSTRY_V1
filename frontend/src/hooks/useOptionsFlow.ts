/**
 * Options Flow Data Hooks
 * QUANT_INDUSTRY_V1
 * Uses the v2 API client for type-safe requests.
 */

import { useState, useCallback, useEffect } from 'react';
import { apiV2 } from '@/api/v2';
import type { ApiResponse } from '@/api/v2';
import {
  UnusualActivity,
  GammaExposureProfile,
  DarkPoolPrint,
  DarkPoolAccumulation,
  InstitutionalFlow,
  SmartMoneyMetrics,
  FlowSignal,
} from '@/types/options-flow';

interface UseOptionsFlowOptions {
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

export function useUnusualActivity(options: UseOptionsFlowOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 30000 } = options;
  const [data, setData] = useState<UnusualActivity[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await apiV2.optionsFlow.getUnusualActivity(symbol);
      if (response.ok && response.data) {
        const result = response.data as unknown as UnusualActivity[] | { data: UnusualActivity[] };
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

export function useGammaExposure(symbol: string) {
  const [data, setData] = useState<GammaExposureProfile | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol) return;
    setIsLoading(true);
    try {
      const response = await apiV2.optionsFlow.getGammaExposure(symbol);
      if (response.ok && response.data) {
        setData(response.data as unknown as GammaExposureProfile);
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
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return { data, isLoading, error, refresh: fetchData };
}

export function useDarkPool(options: UseOptionsFlowOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 30000 } = options;
  const [prints, setPrints] = useState<DarkPoolPrint[]>([]);
  const [accumulation, setAccumulation] = useState<DarkPoolAccumulation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [printsRes, accumRes] = await Promise.all([
        apiV2.optionsFlow.getDarkPoolPrints(symbol),
        apiV2.optionsFlow.getDarkPoolAccumulation(symbol),
      ]);
      
      if (printsRes.ok && printsRes.data) {
        const result = printsRes.data as unknown as DarkPoolPrint[] | { data: DarkPoolPrint[] };
        setPrints(Array.isArray(result) ? result : result.data || []);
      }
      if (accumRes.ok && accumRes.data) {
        const result = accumRes.data as unknown as DarkPoolAccumulation[] | { data: DarkPoolAccumulation[] };
        setAccumulation(Array.isArray(result) ? result : result.data || []);
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

  return { prints, accumulation, isLoading, error, refresh: fetchData };
}

export function useSmartMoney(options: UseOptionsFlowOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 30000 } = options;
  const [flow, setFlow] = useState<InstitutionalFlow[]>([]);
  const [metrics, setMetrics] = useState<SmartMoneyMetrics[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [flowRes, metricsRes] = await Promise.all([
        apiV2.optionsFlow.getSmartMoneyFlow(symbol),
        apiV2.optionsFlow.getSmartMoneyMetrics(symbol),
      ]);
      
      if (flowRes.ok && flowRes.data) {
        const result = flowRes.data as unknown as InstitutionalFlow[] | { data: InstitutionalFlow[] };
        setFlow(Array.isArray(result) ? result : result.data || []);
      }
      if (metricsRes.ok && metricsRes.data) {
        const result = metricsRes.data as unknown as SmartMoneyMetrics[] | { data: SmartMoneyMetrics[] };
        setMetrics(Array.isArray(result) ? result : result.data || []);
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

  return { flow, metrics, isLoading, error, refresh: fetchData };
}

export function useFlowSignals(options: UseOptionsFlowOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 10000 } = options;
  const [signals, setSignals] = useState<FlowSignal[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await apiV2.optionsFlow.getFlowSignals(symbol);
      if (response.ok && response.data) {
        const result = response.data as unknown as FlowSignal[] | { data: FlowSignal[] };
        setSignals(Array.isArray(result) ? result : result.data || []);
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

  return { signals, isLoading, error, refresh: fetchData };
}
