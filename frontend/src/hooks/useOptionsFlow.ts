/**
 * Options Flow Data Hooks
 * QUANT_INDUSTRY_V1
 */

import { useState, useCallback, useEffect } from 'react';
import {
  UnusualActivity,
  GammaExposureProfile,
  DarkPoolPrint,
  DarkPoolAccumulation,
  InstitutionalFlow,
  SmartMoneyMetrics,
  FlowSignal,
} from '@/types/options-flow';

const API_BASE = '/api/v1/options-flow';

interface UseOptionsFlowOptions {
  symbol?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export function useUnusualActivity(options: UseOptionsFlowOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 30000 } = options;
  const [data, setData] = useState<UnusualActivity[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = symbol ? `?symbol=${symbol}` : '';
      const response = await fetch(`${API_BASE}/unusual${params}`);
      if (!response.ok) throw new Error('Failed to fetch unusual activity');
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
    fetch();
    if (autoRefresh) {
      const interval = setInterval(fetch, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetch, autoRefresh, refreshInterval]);

  return { data, isLoading, error, refresh: fetch };
}

export function useGammaExposure(symbol: string) {
  const [data, setData] = useState<GammaExposureProfile | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/gamma-exposure/${symbol}`);
      if (!response.ok) throw new Error('Failed to fetch gamma exposure');
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
      const params = symbol ? `?symbol=${symbol}` : '';
      const [printsRes, accumRes] = await Promise.all([
        fetch(`${API_BASE}/dark-pool/prints${params}`),
        fetch(`${API_BASE}/dark-pool/accumulation${params}`),
      ]);
      
      if (printsRes.ok) {
        const printsData = await printsRes.json();
        setPrints(printsData.data || printsData);
      }
      if (accumRes.ok) {
        const accumData = await accumRes.json();
        setAccumulation(accumData.data || accumData);
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
      const params = symbol ? `?symbol=${symbol}` : '';
      const [flowRes, metricsRes] = await Promise.all([
        fetch(`${API_BASE}/smart-money/flow${params}`),
        fetch(`${API_BASE}/smart-money/metrics${params}`),
      ]);
      
      if (flowRes.ok) {
        const flowData = await flowRes.json();
        setFlow(flowData.data || flowData);
      }
      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData.data || metricsData);
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
      const params = symbol ? `?symbol=${symbol}` : '';
      const response = await fetch(`${API_BASE}/signals${params}`);
      if (!response.ok) throw new Error('Failed to fetch flow signals');
      const result = await response.json();
      setSignals(result.data || result);
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

  return { signals, isLoading, error, refresh: fetchData };
}
