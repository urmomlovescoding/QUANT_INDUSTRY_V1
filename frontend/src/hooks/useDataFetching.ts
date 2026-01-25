/**
 * Data Fetching Hooks with Auto-Refresh
 */

import { useEffect, useCallback, useRef, useState } from 'react'
import { useAppStore } from '@/store'

interface UseAutoRefreshOptions {
  enabled?: boolean
  interval?: number // in milliseconds
  onError?: (error: Error) => void
}

/**
 * Hook for auto-refreshing data at specified intervals
 */
export function useAutoRefresh(
  fetchFn: () => Promise<void>,
  options: UseAutoRefreshOptions = {}
) {
  const { enabled = true, interval = 15000, onError } = options
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    setIsRefreshing(true)
    try {
      await fetchFn()
    } catch (e) {
      if (onError && e instanceof Error) {
        onError(e)
      }
    }
    setIsRefreshing(false)
  }, [fetchFn, onError])

  useEffect(() => {
    if (!enabled) return

    // Initial fetch
    refresh()

    // Set up interval
    intervalRef.current = setInterval(refresh, interval)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [enabled, interval, refresh])

  return { refresh, isRefreshing }
}

/**
 * Hook for dashboard data with auto-refresh
 */
export function useDashboardData(refreshInterval = 15000) {
  const fetchAll = useAppStore((s) => s.fetchAll)
  const brainStatus = useAppStore((s) => s.brainStatus)
  const feedbackStatus = useAppStore((s) => s.feedbackStatus)
  const signals = useAppStore((s) => s.signals)
  const positions = useAppStore((s) => s.positions)
  const portfolio = useAppStore((s) => s.portfolio)
  const riskMetrics = useAppStore((s) => s.riskMetrics)
  const isLoading = useAppStore((s) => Object.values(s.isLoading).some(Boolean))
  const errors = useAppStore((s) => s.errors)

  const { refresh, isRefreshing } = useAutoRefresh(fetchAll, {
    enabled: true,
    interval: refreshInterval,
  })

  return {
    brainStatus,
    feedbackStatus,
    signals,
    positions,
    portfolio,
    riskMetrics,
    isLoading,
    isRefreshing,
    errors,
    refresh,
  }
}

/**
 * Hook for market data with real-time updates
 */
export function useMarketData(refreshInterval = 30000) {
  const fetchTickers = useAppStore((s) => s.fetchTickers)
  const tickers = useAppStore((s) => s.tickers)
  const marketStatus = useAppStore((s) => s.marketStatus)
  const isLoading = useAppStore((s) => s.isLoading['tickers'])
  const error = useAppStore((s) => s.errors['tickers'])

  const { refresh, isRefreshing } = useAutoRefresh(fetchTickers, {
    enabled: true,
    interval: refreshInterval,
  })

  return {
    tickers,
    marketStatus,
    isLoading,
    isRefreshing,
    error,
    refresh,
  }
}

/**
 * Hook for trading signals with auto-refresh
 */
export function useSignalsData(refreshInterval = 10000) {
  const fetchSignals = useAppStore((s) => s.fetchSignals)
  const signals = useAppStore((s) => s.signals)
  const isLoading = useAppStore((s) => s.isLoading['signals'])
  const error = useAppStore((s) => s.errors['signals'])
  const addSignal = useAppStore((s) => s.addSignal)
  const updateSignal = useAppStore((s) => s.updateSignal)
  const removeSignal = useAppStore((s) => s.removeSignal)

  const { refresh, isRefreshing } = useAutoRefresh(fetchSignals, {
    enabled: true,
    interval: refreshInterval,
  })

  // Filter helpers
  const activeSignals = signals.filter((s) => s.status === 'active')
  const highConfidenceSignals = signals.filter((s) => s.confidence >= 0.7)
  const longSignals = signals.filter((s) => s.direction === 'LONG')
  const shortSignals = signals.filter((s) => s.direction === 'SHORT')

  return {
    signals,
    activeSignals,
    highConfidenceSignals,
    longSignals,
    shortSignals,
    isLoading,
    isRefreshing,
    error,
    refresh,
    addSignal,
    updateSignal,
    removeSignal,
  }
}

/**
 * Hook for portfolio data with auto-refresh
 */
export function usePortfolioData(refreshInterval = 30000) {
  const fetchPortfolio = useAppStore((s) => s.fetchPortfolio)
  const fetchPositions = useAppStore((s) => s.fetchPositions)
  const portfolio = useAppStore((s) => s.portfolio)
  const positions = useAppStore((s) => s.positions)
  const isLoading = useAppStore(
    (s) => s.isLoading['portfolio'] || s.isLoading['positions']
  )
  const error = useAppStore(
    (s) => s.errors['portfolio'] || s.errors['positions']
  )

  const fetchBoth = useCallback(async () => {
    await Promise.all([fetchPortfolio(), fetchPositions()])
  }, [fetchPortfolio, fetchPositions])

  const { refresh, isRefreshing } = useAutoRefresh(fetchBoth, {
    enabled: true,
    interval: refreshInterval,
  })

  // Calculate metrics
  const totalValue = positions.reduce(
    (sum, p) => sum + p.quantity * p.current_price,
    0
  )
  const totalPnL = positions.reduce((sum, p) => sum + p.pnl, 0)
  const positionCount = positions.length

  return {
    portfolio,
    positions,
    totalValue,
    totalPnL,
    positionCount,
    isLoading,
    isRefreshing,
    error,
    refresh,
  }
}

/**
 * Hook for brain/AI status with auto-refresh
 */
export function useBrainData(refreshInterval = 20000) {
  const fetchBrainStatus = useAppStore((s) => s.fetchBrainStatus)
  const fetchFeedbackStatus = useAppStore((s) => s.fetchFeedbackStatus)
  const brainStatus = useAppStore((s) => s.brainStatus)
  const feedbackStatus = useAppStore((s) => s.feedbackStatus)
  const isLoading = useAppStore(
    (s) => s.isLoading['brainStatus'] || s.isLoading['feedbackStatus']
  )
  const error = useAppStore(
    (s) => s.errors['brainStatus'] || s.errors['feedbackStatus']
  )

  const fetchBoth = useCallback(async () => {
    await Promise.all([fetchBrainStatus(), fetchFeedbackStatus()])
  }, [fetchBrainStatus, fetchFeedbackStatus])

  const { refresh, isRefreshing } = useAutoRefresh(fetchBoth, {
    enabled: true,
    interval: refreshInterval,
  })

  return {
    brainStatus,
    feedbackStatus,
    isLoading,
    isRefreshing,
    error,
    refresh,
  }
}

/**
 * Hook for risk metrics with auto-refresh
 */
export function useRiskData(refreshInterval = 30000) {
  const fetchRiskMetrics = useAppStore((s) => s.fetchRiskMetrics)
  const riskMetrics = useAppStore((s) => s.riskMetrics)
  const safetyStatus = useAppStore((s) => s.safetyStatus)
  const isLoading = useAppStore((s) => s.isLoading['riskMetrics'])
  const error = useAppStore((s) => s.errors['riskMetrics'])

  const { refresh, isRefreshing } = useAutoRefresh(fetchRiskMetrics, {
    enabled: true,
    interval: refreshInterval,
  })

  return {
    riskMetrics,
    safetyStatus,
    isLoading,
    isRefreshing,
    error,
    refresh,
  }
}

/**
 * Hook for quote data (single symbol)
 */
export function useQuote(symbol: string) {
  const [quote, setQuote] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const storeQuotes = useAppStore((s) => s.quotes)
  const setQuoteInStore = useAppStore((s) => s.setQuote)

  const fetchQuote = useCallback(async () => {
    if (!symbol) return
    setIsLoading(true)
    try {
      const response = await fetch(`/api/quote/${symbol}`)
      if (response.ok) {
        const data = await response.json()
        setQuote(data)
        setQuoteInStore(symbol, data)
        setError(null)
      } else {
        setError('Failed to fetch quote')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    }
    setIsLoading(false)
  }, [symbol, setQuoteInStore])

  useEffect(() => {
    fetchQuote()
    const interval = setInterval(fetchQuote, 30000)
    return () => clearInterval(interval)
  }, [fetchQuote])

  // Return from store if available
  const storedQuote = storeQuotes[symbol]

  return {
    quote: storedQuote || quote,
    isLoading,
    error,
    refresh: fetchQuote,
  }
}
