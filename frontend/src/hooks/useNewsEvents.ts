/**
 * News & Events Data Hooks
 * QUANT_INDUSTRY_V1
 * Uses the v2 API client for type-safe requests.
 */

import { useState, useCallback, useEffect } from 'react';
import { apiV2 } from '@/api/v2';
import type { ApiResponse } from '@/api/v2';
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

interface UseNewsEventsOptions {
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

export function useNewsFeed(options: UseNewsEventsOptions = {}) {
  const { symbol, autoRefresh = true, refreshInterval = 60000 } = options;
  const [feed, setFeed] = useState<NewsFeed | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await apiV2.newsEvents.getNews(symbol);
      if (response.ok && response.data) {
        setFeed(response.data as NewsFeed);
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
      const response = await apiV2.newsEvents.getSentiment(symbol);
      if (response.ok && response.data) {
        setMetrics(response.data as SentimentMetrics);
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
      const response = await apiV2.newsEvents.getEarnings(symbol);
      if (response.ok && response.data) {
        const result = response.data as EarningsEvent[] | { data: EarningsEvent[] };
        setEarnings(Array.isArray(result) ? result : result.data || []);
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
      const response = await apiV2.newsEvents.getEconomicCalendar(startDate, endDate);
      if (response.ok && response.data) {
        setCalendar(response.data as EconomicCalendar);
        setError(null);
      } else {
        throw new Error(getErrorMessage(response));
      }
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
      const response = await apiV2.newsEvents.getSignals(symbol);
      if (response.ok && response.data) {
        const result = response.data as EventSignal[] | { data: EventSignal[] };
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

export function useHeadlineAnalysis() {
  const [analysis, setAnalysis] = useState<HeadlineAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyzeHeadline = useCallback(async (headline: string) => {
    setIsLoading(true);
    try {
      const response = await apiV2.newsEvents.analyzeHeadline(headline);
      if (!response.ok) {
        throw new Error(getErrorMessage(response));
      }
      const result = response.data as HeadlineAnalysis;
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
