/**
 * Enhanced Signals Table - Connected to API
 * 
 * Migrated to use apiV2 client for type-safe API calls.
 */

import { useState, useEffect, useCallback } from 'react'
import { ArrowUpRight, ArrowDownRight, Play, X, RefreshCw, AlertCircle } from 'lucide-react'
import { cn } from '@/utils/cn'
import { Signal } from '@/api'
// V2 API Client - Domain-based structure
import { apiV2 } from '@/api/v2'
// OLD: import { signalsApi, Signal } from '@/api'
import { Spinner, SkeletonTable } from '@/components/ui/Loading'
import { formatCurrency, formatPercent, formatRelativeTime } from '@/utils/format'

interface SignalsTableProps {
  signals?: Signal[]
  isLoading?: boolean
  error?: string | null
  onExecute?: (signal: Signal) => void
  onDismiss?: (signalId: string) => void
  onRefresh?: () => void
  showActions?: boolean
  compact?: boolean
}

export function SignalsTable({
  signals: externalSignals,
  isLoading: externalLoading,
  error: externalError,
  onExecute,
  onDismiss,
  onRefresh,
  showActions = true,
  compact = false,
}: SignalsTableProps) {
  const [signals, setSignals] = useState<Signal[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [executingIds, setExecutingIds] = useState<Set<string>>(new Set())

  const fetchSignals = useCallback(async () => {
    if (externalSignals !== undefined) return

    setIsLoading(true)
    setError(null)
    try {
      // V2: apiV2.signals.getActive() instead of signalsApi.getActive()
      const response = await apiV2.signals.getActive()
      if (response.ok && response.data) {
        setSignals(response.data as unknown as Signal[])
      } else {
        setError(response.error?.message || 'Failed to fetch signals')
        setSignals([])
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
      setSignals([])
    }
    setIsLoading(false)
  }, [externalSignals])

  useEffect(() => {
    fetchSignals()
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchSignals, 30000)
    return () => clearInterval(interval)
  }, [fetchSignals])

  const handleExecute = async (signal: Signal) => {
    if (onExecute) {
      onExecute(signal)
      return
    }

    setExecutingIds((prev) => new Set(prev).add(signal.id))
    try {
      // V2: apiV2.signals.execute() instead of signalsApi.execute()
      const response = await apiV2.signals.execute(signal.id)
      if (response.ok) {
        // Remove from list or update status
        setSignals((prev) =>
          prev.map((s) =>
            s.id === signal.id ? { ...s, status: 'executed' as const } : s
          )
        )
      }
    } catch {
      // Silent fail - UI will remain unchanged
    }
    setExecutingIds((prev) => {
      const next = new Set(prev)
      next.delete(signal.id)
      return next
    })
  }

  const handleDismiss = async (signalId: string) => {
    if (onDismiss) {
      onDismiss(signalId)
      return
    }

    try {
      // V2: apiV2.signals.dismiss() instead of signalsApi.dismiss()
      const response = await apiV2.signals.dismiss(signalId)
      if (response.ok) {
        setSignals((prev) => prev.filter((s) => s.id !== signalId))
      }
    } catch {
      // Silent fail - signal will remain in list
    }
  }

  const handleRefresh = () => {
    if (onRefresh) {
      onRefresh()
    } else {
      fetchSignals()
    }
  }

  const displaySignals = externalSignals ?? signals
  const displayLoading = externalLoading ?? isLoading
  const displayError = externalError ?? error

  if (displayLoading && displaySignals.length === 0) {
    return <SkeletonTable rows={5} cols={compact ? 6 : 10} />
  }

  if (displayError && displaySignals.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-10 text-center">
        <div className="w-12 h-12 rounded-2xl bg-bearish/10 flex items-center justify-center mb-3">
          <AlertCircle className="w-6 h-6 text-bearish" />
        </div>
        <p className="text-sm font-medium text-foreground-primary mb-1">Error loading signals</p>
        <p className="text-xs text-foreground-muted mb-4 max-w-xs">{displayError}</p>
        <button
          onClick={handleRefresh}
          className="flex items-center gap-2 px-4 py-2 text-xs font-medium bg-background-tertiary rounded-lg hover:bg-background-hover transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </button>
      </div>
    )
  }

  if (displaySignals.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <div className="w-12 h-12 rounded-2xl bg-background-tertiary/80 flex items-center justify-center mb-3">
          <ArrowUpRight className="w-6 h-6 text-foreground-muted" />
        </div>
        <p className="text-sm font-medium text-foreground-primary mb-1">No active signals</p>
        <p className="text-xs text-foreground-muted mt-0.5 max-w-[280px] leading-relaxed">
          The trading brain will generate signals when market conditions align with your strategies
        </p>
        <button
          onClick={handleRefresh}
          className="mt-4 flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium text-accent-primary bg-accent-primary/10 hover:bg-accent-primary/15 rounded-lg transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          Check for signals
        </button>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Direction</th>
            <th>Confidence</th>
            <th className="text-right">Entry</th>
            {!compact && (
              <>
                <th className="text-right">Stop Loss</th>
                <th className="text-right">Take Profit</th>
              </>
            )}
            <th className="text-right">R:R</th>
            {!compact && <th>Strategy</th>}
            <th>Time</th>
            {showActions && <th className="text-right">Actions</th>}
          </tr>
        </thead>
        <tbody>
          {displaySignals
            .filter((s) => s.status === 'active')
            .map((signal) => (
              <tr key={signal.id}>
                <td>
                  <span className="font-semibold text-foreground-primary tracking-wide">
                    {signal.symbol}
                  </span>
                </td>
                <td>
                  <DirectionBadge direction={signal.direction} />
                </td>
                <td>
                  <ConfidenceBar confidence={signal.confidence} />
                </td>
                <td className="text-right font-mono tabular-nums">{formatCurrency(signal.entry_price)}</td>
                {!compact && (
                  <>
                    <td className="text-right font-mono tabular-nums text-bearish">
                      {formatCurrency(signal.stop_loss)}
                    </td>
                    <td className="text-right font-mono tabular-nums text-bullish">
                      {formatCurrency(signal.take_profit)}
                    </td>
                  </>
                )}
                <td className="text-right font-mono tabular-nums">
                  <span
                    className={cn(
                      'font-semibold',
                      signal.risk_reward >= 2 ? 'text-bullish' : signal.risk_reward >= 1.5 ? 'text-accent-primary' : 'text-foreground-secondary'
                    )}
                  >
                    1:{signal.risk_reward.toFixed(1)}
                  </span>
                </td>
                {!compact && (
                  <td>
                    <span className="badge badge-info">{signal.strategy}</span>
                  </td>
                )}
                <td className="text-foreground-muted text-xs whitespace-nowrap">
                  {formatRelativeTime(signal.timestamp)}
                </td>
                {showActions && (
                  <td className="text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        onClick={() => handleExecute(signal)}
                        disabled={executingIds.has(signal.id)}
                        className="p-1.5 rounded-lg bg-bullish/15 text-bullish hover:bg-bullish/25 transition-all disabled:opacity-50"
                        title="Execute Signal"
                      >
                        {executingIds.has(signal.id) ? (
                          <Spinner size="sm" />
                        ) : (
                          <Play className="w-3.5 h-3.5" />
                        )}
                      </button>
                      <button
                        onClick={() => handleDismiss(signal.id)}
                        className="p-1.5 rounded-lg bg-background-hover/50 text-foreground-muted hover:bg-background-active hover:text-foreground-primary transition-all"
                        title="Dismiss Signal"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
        </tbody>
      </table>
      {displayLoading && (
        <div className="flex items-center justify-center py-2.5 text-[11px] text-foreground-muted gap-2">
          <Spinner size="sm" />
          <span>Refreshing signals...</span>
        </div>
      )}
    </div>
  )
}

function DirectionBadge({ direction }: { direction: 'LONG' | 'SHORT' }) {
  const isLong = direction === 'LONG'

  return (
    <span
      className={cn(
        'badge inline-flex items-center gap-1',
        isLong ? 'badge-bullish' : 'badge-bearish'
      )}
    >
      {isLong ? (
        <ArrowUpRight className="w-3 h-3" />
      ) : (
        <ArrowDownRight className="w-3 h-3" />
      )}
      {direction}
    </span>
  )
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const percentage = confidence * 100

  const getColor = () => {
    if (percentage >= 80) return 'bg-bullish'
    if (percentage >= 60) return 'bg-accent-primary'
    return 'bg-warning'
  }

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-background-tertiary rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', getColor())}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs font-medium tabular-nums text-foreground-primary">
        {percentage.toFixed(0)}%
      </span>
    </div>
  )
}

// No demo data - signals come from real API only
