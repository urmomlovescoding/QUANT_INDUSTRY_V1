/**
 * Enhanced Signals Table - Connected to API
 */

import { useState, useEffect, useCallback } from 'react'
import { ArrowUpRight, ArrowDownRight, Play, X, RefreshCw, AlertCircle } from 'lucide-react'
import { cn } from '@/utils/cn'
import { signalsApi, Signal } from '@/api'
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
      const response = await signalsApi.getActive()
      if (response.ok && response.data) {
        setSignals(response.data)
      } else {
        setError(response.error?.message || 'Failed to fetch signals')
        // Use demo data on error
        setSignals(DEMO_SIGNALS)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
      setSignals(DEMO_SIGNALS)
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
      const response = await signalsApi.execute(signal.id)
      if (response.ok) {
        // Remove from list or update status
        setSignals((prev) =>
          prev.map((s) =>
            s.id === signal.id ? { ...s, status: 'executed' as const } : s
          )
        )
      }
    } catch (e) {
      console.error('Failed to execute signal:', e)
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
      const response = await signalsApi.dismiss(signalId)
      if (response.ok) {
        setSignals((prev) => prev.filter((s) => s.id !== signalId))
      }
    } catch (e) {
      console.error('Failed to dismiss signal:', e)
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
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <AlertCircle className="w-8 h-8 text-error mb-2" />
        <p className="text-sm text-error mb-2">Error loading signals</p>
        <p className="text-xs text-foreground-muted mb-4">{displayError}</p>
        <button
          onClick={handleRefresh}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-background-tertiary rounded hover:bg-background-hover"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    )
  }

  if (displaySignals.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <p className="text-foreground-muted">No active signals</p>
        <p className="text-xs text-foreground-muted mt-1">
          Signals will appear here when generated
        </p>
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
            <th>Entry</th>
            {!compact && (
              <>
                <th>Stop Loss</th>
                <th>Take Profit</th>
              </>
            )}
            <th>R:R</th>
            {!compact && <th>Strategy</th>}
            <th>Time</th>
            {showActions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {displaySignals
            .filter((s) => s.status === 'active')
            .map((signal) => (
              <tr key={signal.id}>
                <td>
                  <span className="font-medium text-foreground-primary">
                    {signal.symbol}
                  </span>
                </td>
                <td>
                  <DirectionBadge direction={signal.direction} />
                </td>
                <td>
                  <ConfidenceBar confidence={signal.confidence} />
                </td>
                <td className="font-mono">{formatCurrency(signal.entry_price)}</td>
                {!compact && (
                  <>
                    <td className="font-mono text-bearish">
                      {formatCurrency(signal.stop_loss)}
                    </td>
                    <td className="font-mono text-bullish">
                      {formatCurrency(signal.take_profit)}
                    </td>
                  </>
                )}
                <td className="font-mono">
                  <span
                    className={cn(
                      signal.risk_reward >= 2 ? 'text-bullish' : 'text-foreground-secondary'
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
                <td className="text-foreground-muted text-xs">
                  {formatRelativeTime(signal.timestamp)}
                </td>
                {showActions && (
                  <td>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleExecute(signal)}
                        disabled={executingIds.has(signal.id)}
                        className="p-1.5 rounded bg-bullish/20 text-bullish hover:bg-bullish/30 transition-colors disabled:opacity-50"
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
                        className="p-1.5 rounded bg-background-hover text-foreground-muted hover:bg-background-active transition-colors"
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
        <div className="flex items-center justify-center p-2 text-xs text-foreground-muted">
          <Spinner size="sm" className="mr-2" />
          Refreshing...
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

// Demo data for when API is unavailable
const DEMO_SIGNALS: Signal[] = [
  {
    id: '1',
    symbol: 'AAPL',
    direction: 'LONG',
    confidence: 0.85,
    strategy: 'Momentum',
    entry_price: 185.50,
    stop_loss: 182.00,
    take_profit: 195.00,
    risk_reward: 2.7,
    timeframe: '1H',
    regime_alignment: true,
    timestamp: new Date(Date.now() - 10 * 60000).toISOString(),
    status: 'active',
  },
  {
    id: '2',
    symbol: 'TSLA',
    direction: 'SHORT',
    confidence: 0.72,
    strategy: 'Mean Reversion',
    entry_price: 248.00,
    stop_loss: 255.00,
    take_profit: 230.00,
    risk_reward: 2.6,
    timeframe: '4H',
    regime_alignment: true,
    timestamp: new Date(Date.now() - 25 * 60000).toISOString(),
    status: 'active',
  },
  {
    id: '3',
    symbol: 'NVDA',
    direction: 'LONG',
    confidence: 0.91,
    strategy: 'Breakout',
    entry_price: 878.00,
    stop_loss: 860.00,
    take_profit: 920.00,
    risk_reward: 2.3,
    timeframe: '1D',
    regime_alignment: true,
    timestamp: new Date(Date.now() - 35 * 60000).toISOString(),
    status: 'active',
  },
  {
    id: '4',
    symbol: 'MSFT',
    direction: 'LONG',
    confidence: 0.68,
    strategy: 'Trend Follow',
    entry_price: 415.00,
    stop_loss: 408.00,
    take_profit: 430.00,
    risk_reward: 2.1,
    timeframe: '1H',
    regime_alignment: false,
    timestamp: new Date(Date.now() - 45 * 60000).toISOString(),
    status: 'active',
  },
  {
    id: '5',
    symbol: 'META',
    direction: 'LONG',
    confidence: 0.79,
    strategy: 'Momentum',
    entry_price: 505.00,
    stop_loss: 495.00,
    take_profit: 530.00,
    risk_reward: 2.5,
    timeframe: '4H',
    regime_alignment: true,
    timestamp: new Date(Date.now() - 60 * 60000).toISOString(),
    status: 'active',
  },
]
