/**
 * News & Events Data Hooks
 * QUANT_INDUSTRY_V1
 */

import { useState, useCallback, useEffect } from 'react';
import {
  NewsArticle,
  NewsFeed,
  SentimentMetrics,
  EarningsEvent,
  EconomicEvent,
  EconomicCalendar,
  EventSignal,
  HeadlineAnalysis,
} from '@/types/news-events';

import { API_ENDPOINTS } from '@/config/api';
const API_BASE = API_ENDPOINTS.NEWS_EVENTS;

interface UseNewsEventsOptions {
  symbol?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export function useNewsFeed(options: UseNewsEventsOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 60000 } = options;
  const [feed, setFeed] = useState<NewsFeed | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = symbol ? `?symbol=${symbol}` : '';
      const response = await fetch(`${API_BASE}/news${params}`);
      if (!response.ok) throw new Error('Failed to fetch news');
      const result = await response.json();
      setFeed(result);
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

  return { feed, isLoading, error, refresh: fetchData };
}

export function useSentiment(symbol?: string, options: Omit<UseNewsEventsOptions, 'symbol'> = {}) {
  const { autoRefresh = true, refreshInterval = 30000 } = options;
  const [metrics, setMetrics] = useState<SentimentMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const endpoint = symbol 
        ? `${API_BASE}/sentiment/${symbol}`
        : `${API_BASE}/sentiment/market`;
      const response = await fetch(endpoint);
      if (!response.ok) throw new Error('Failed to fetch sentiment');
      const result = await response.json();
      setMetrics(result);
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

  return { metrics, isLoading, error, refresh: fetchData };
}

export function useEarningsCalendar(options: UseNewsEventsOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 300000 } = options;
  const [earnings, setEarnings] = useState<EarningsEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = symbol ? `?symbol=${symbol}` : '';
      const response = await fetch(`${API_BASE}/earnings${params}`);
      if (!response.ok) throw new Error('Failed to fetch earnings');
      const result = await response.json();
      setEarnings(result.data || result);
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

  return { earnings, isLoading, error, refresh: fetchData };
}

export function useEconomicCalendar(startDate?: string, endDate?: string, options: UseNewsEventsOptions = {}) {
  const { autoRefresh = true, refreshInterval = 300000 } = options;
  const [calendar, setCalendar] = useState<EconomicCalendar | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (startDate) params.set('start', startDate);
      if (endDate) params.set('end', endDate);
      const queryString = params.toString() ? `?${params.toString()}` : '';
      
      const response = await fetch(`${API_BASE}/economic${queryString}`);
      if (!response.ok) throw new Error('Failed to fetch economic calendar');
      const result = await response.json();
      setCalendar(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchData, autoRefresh, refreshInterval]);

  return { calendar, isLoading, error, refresh: fetchData };
}

export function useEventSignals(options: UseNewsEventsOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 15000 } = options;
  const [signals, setSignals] = useState<EventSignal[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = symbol ? `?symbol=${symbol}` : '';
      const response = await fetch(`${API_BASE}/signals${params}`);
      if (!response.ok) throw new Error('Failed to fetch event signals');
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

export function useHeadlineAnalysis() {
  const [analysis, setAnalysis] = useState<HeadlineAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyzeHeadline = useCallback(async (headline: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/analyze-headline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ headline }),
      });
      if (!response.ok) throw new Error('Failed to analyze headline');
      const result = await response.json();
      setAnalysis(result);
      setError(null);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
      throw e;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { analysis, isLoading, error, analyzeHeadline };
}
