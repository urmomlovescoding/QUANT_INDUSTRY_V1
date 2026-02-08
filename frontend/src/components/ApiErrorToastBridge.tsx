/**
 * ApiErrorToastBridge
 *
 * Watches the Zustand store's `errors` map and triggers toast notifications
 * whenever a new error appears. Deduplicates so the same error key does not
 * produce a toast more than once per 30 seconds.
 *
 * This component renders nothing -- it is a pure side-effect bridge between
 * the Zustand store and the React-context-based Toast system.
 */
import { useEffect, useRef } from 'react'
import { useAppStore } from '@/store'
import { useToastSafe } from '@/components/ui/Toast'

/** Human-friendly labels for store error keys */
const ERROR_LABELS: Record<string, string> = {
  marketStatus: 'Market Status',
  tickers: 'Market Tickers',
  signals: 'Trading Signals',
  positions: 'Positions',
  portfolio: 'Portfolio',
  brainStatus: 'Trading Brain',
  feedbackStatus: 'Feedback Loop',
  riskMetrics: 'Risk Metrics',
}

/** Minimum interval (ms) between duplicate toasts for the same key */
const DEDUPE_INTERVAL_MS = 30_000

export function ApiErrorToastBridge() {
  const errors = useAppStore((s) => s.errors)
  const toast = useToastSafe()

  // Track the last time we showed a toast for each error key
  const lastShown = useRef<Record<string, number>>({})

  useEffect(() => {
    if (!toast) return

    const now = Date.now()

    for (const [key, message] of Object.entries(errors)) {
      if (!message) continue // null means "no error" -- skip

      const last = lastShown.current[key] ?? 0
      if (now - last < DEDUPE_INTERVAL_MS) continue // still within cooldown

      const label = ERROR_LABELS[key] || key
      toast.error(`Failed to load ${label}`, 'API Error')
      lastShown.current[key] = now
    }
  }, [errors, toast])

  return null
}
