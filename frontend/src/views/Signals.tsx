import { useState, useEffect } from 'react'
import { Signal as SignalIcon, Filter, RefreshCw, Play, AlertCircle } from 'lucide-react'
import { SignalsTable } from '@/components/tables/SignalsTable'
import { Signal } from '@/api/client'
import { apiV2 } from '@/api/v2'
import { cn } from '@/utils/cn'

/** API may return signals as a wrapped object */
interface SignalsResponse {
  signals: Signal[]
}

export function Signals() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [directionFilter, setDirectionFilter] = useState('all')

  const fetchSignals = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const { data, error: apiError, ok } = await apiV2.signals.getActive()

      if (!ok || apiError) {
        throw new Error(apiError?.message || 'Failed to fetch signals')
      }

      if (Array.isArray(data)) {
        setSignals(data)
      } else if (data && typeof data === 'object' && 'signals' in data) {
        setSignals((data as SignalsResponse).signals)
      } else {
        setSignals([])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch signals')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchSignals()
  }, [])

  // Calculate stats from real data
  const activeSignals = signals.filter(s => s.status === 'active')
  const longSignals = signals.filter(s => s.direction === 'LONG')
  const shortSignals = signals.filter(s => s.direction === 'SHORT')
  const highConfidence = signals.filter(s => s.confidence >= 0.8)
  const avgConfidence = signals.length > 0
    ? signals.reduce((sum, s) => sum + (s.confidence || 0), 0) / signals.length * 100
    : 0
  const avgRiskReward = signals.length > 0
    ? signals.reduce((sum, s) => sum + (s.risk_reward || 0), 0) / signals.length
    : 0

  const filteredSignals = directionFilter === 'all'
    ? signals
    : directionFilter === 'long'
    ? longSignals
    : shortSignals

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <SignalIcon className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground-primary">Signal Analysis</h1>
            <p className="text-sm text-foreground-muted">
              {signals.length > 0
                ? `${activeSignals.length} active signals • ${longSignals.length} long • ${shortSignals.length} short`
                : 'No active signals'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchSignals}
            disabled={isLoading}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        <SummaryCard label="Total Signals" value={signals.length.toString()} />
        <SummaryCard label="High Confidence" value={highConfidence.length.toString()} subLabel=">80%" />
        <SummaryCard
          label="Avg Risk/Reward"
          value={avgRiskReward !== 0 ? `${avgRiskReward.toFixed(2)}:1` : 'N/A'}
          positive={avgRiskReward > 1}
        />
        <SummaryCard
          label="Avg Confidence"
          value={avgConfidence > 0 ? `${avgConfidence.toFixed(0)}%` : 'N/A'}
        />
      </div>

      {/* Main content */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-accent-primary" />
        </div>
      ) : signals.length === 0 ? (
        <div className="card p-8 text-center text-foreground-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">No Active Signals</p>
          <p className="text-sm mt-2">Signals will appear when the AI detects trading opportunities</p>
        </div>
      ) : (
        <div className="card p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-foreground-primary">All Signals</h2>
            <div className="flex items-center gap-2">
              <select
                value={directionFilter}
                onChange={(e) => setDirectionFilter(e.target.value)}
                className="text-xs bg-background-tertiary text-foreground-secondary px-3 py-1.5 rounded border border-border"
              >
                <option value="all">All Directions</option>
                <option value="long">Long Only</option>
                <option value="short">Short Only</option>
              </select>
            </div>
          </div>
          <SignalsTable signals={filteredSignals} />
        </div>
      )}
    </div>
  )
}

interface SummaryCardProps {
  label: string
  value: string
  subLabel?: string
  positive?: boolean
}

function SummaryCard({ label, value, subLabel, positive }: SummaryCardProps) {
  return (
    <div className="card p-4">
      <p className="text-xs text-foreground-muted uppercase tracking-wider">{label}</p>
      <div className="flex items-baseline gap-2 mt-1">
        <p className={`text-2xl font-bold ${positive ? 'text-bullish' : 'text-foreground-primary'}`}>
          {value}
        </p>
        {subLabel && (
          <span className="text-xs text-foreground-muted">{subLabel}</span>
        )}
      </div>
    </div>
  )
}
