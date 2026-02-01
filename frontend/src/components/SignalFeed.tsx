/**
 * Unified Signal Feed
 * Single scrolling feed of all system signals with timestamps.
 * Color-coded by type, filterable, expandable, and exportable.
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowUpRight,
  ArrowDownRight,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronRight,
  Filter,
  Download,
  X,
  Zap,
  Clock,
  Target,
  BarChart3,
  Shield,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { signalsApi, brainApi } from '@/api/client'
import { formatRelativeTime, formatCurrency, formatPercent } from '@/utils/format'
import { useEventSubscription } from '@/hooks/useEventBus'

// Signal types with color coding
type SignalType = 'entry' | 'exit' | 'risk' | 'info' | 'brain'

interface FeedSignal {
  id: string
  type: SignalType
  symbol: string
  title: string
  message: string
  timestamp: string
  confidence?: number
  strategy?: string
  direction?: 'LONG' | 'SHORT'
  price?: number
  stopLoss?: number
  takeProfit?: number
  riskReward?: number
  regime?: string
  source?: string
  details?: Record<string, any>
}

const typeConfig: Record<SignalType, { color: string; bgColor: string; icon: React.ComponentType<{ className?: string }>; label: string }> = {
  entry: { color: 'text-bullish', bgColor: 'bg-bullish/10', icon: ArrowUpRight, label: 'ENTRY' },
  exit: { color: 'text-bearish', bgColor: 'bg-bearish/10', icon: ArrowDownRight, label: 'EXIT' },
  risk: { color: 'text-warning', bgColor: 'bg-warning/10', icon: AlertTriangle, label: 'RISK' },
  info: { color: 'text-foreground-muted', bgColor: 'bg-foreground-muted/10', icon: Info, label: 'INFO' },
  brain: { color: 'text-accent-primary', bgColor: 'bg-accent-primary/10', icon: Zap, label: 'BRAIN' },
}

function normalizeSignal(raw: any): FeedSignal {
  const direction = raw.direction?.toUpperCase()
  let type: SignalType = 'info'

  if (direction === 'LONG' || raw.type === 'entry' || raw.action === 'BUY') {
    type = 'entry'
  } else if (direction === 'SHORT' || raw.type === 'exit' || raw.action === 'SELL') {
    type = 'exit'
  } else if (raw.risk_level === 'HIGH' || raw.type === 'risk' || raw.risk_alert) {
    type = 'risk'
  } else if (raw.source === 'brain' || raw.type === 'brain') {
    type = 'brain'
  }

  return {
    id: raw.id || `sig-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    type,
    symbol: raw.symbol || 'SYSTEM',
    title: raw.title || `${direction || raw.action || 'Signal'} ${raw.symbol || ''}`.trim(),
    message: raw.message || raw.reason || raw.description || `${raw.strategy || 'System'} signal for ${raw.symbol || 'market'}`,
    timestamp: raw.timestamp || new Date().toISOString(),
    confidence: raw.confidence,
    strategy: raw.strategy,
    direction: direction as 'LONG' | 'SHORT' | undefined,
    price: raw.entry_price || raw.price,
    stopLoss: raw.stop_loss,
    takeProfit: raw.take_profit,
    riskReward: raw.risk_reward,
    regime: raw.regime || raw.regime_alignment,
    source: raw.source || raw.strategy,
    details: raw,
  }
}

function SignalItem({ signal, isExpanded, onToggle }: {
  signal: FeedSignal
  isExpanded: boolean
  onToggle: () => void
}) {
  const config = typeConfig[signal.type]
  const Icon = config.icon

  return (
    <div className={cn(
      'border-b border-border/50 transition-colors',
      'hover:bg-background-hover/50 cursor-pointer',
    )}>
      {/* Main row */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
      >
        {/* Type indicator */}
        <div className={cn('flex items-center justify-center w-5 h-5 rounded', config.bgColor)}>
          <Icon className={cn('w-3 h-3', config.color)} />
        </div>

        {/* Timestamp */}
        <span className="text-[10px] font-mono text-foreground-muted w-14 flex-shrink-0">
          {formatRelativeTime(signal.timestamp)}
        </span>

        {/* Type badge */}
        <span className={cn(
          'text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider flex-shrink-0',
          config.bgColor, config.color
        )}>
          {config.label}
        </span>

        {/* Symbol */}
        <span className="text-xs font-bold text-accent-primary flex-shrink-0">
          {signal.symbol}
        </span>

        {/* Message */}
        <span className="text-xs text-foreground-secondary truncate flex-1">
          {signal.title}
        </span>

        {/* Confidence */}
        {signal.confidence !== undefined && (
          <span className={cn(
            'text-[10px] font-mono font-bold flex-shrink-0',
            signal.confidence >= 0.7 ? 'text-bullish' :
            signal.confidence >= 0.4 ? 'text-warning' : 'text-bearish'
          )}>
            {formatPercent(signal.confidence * 100, 0)}
          </span>
        )}

        {/* Expand icon */}
        {isExpanded ? (
          <ChevronDown className="w-3 h-3 text-foreground-muted flex-shrink-0" />
        ) : (
          <ChevronRight className="w-3 h-3 text-foreground-muted flex-shrink-0" />
        )}
      </button>

      {/* Expanded details */}
      {isExpanded && (
        <div className="px-3 pb-3 pt-1 ml-7">
          <div className="bg-background-tertiary rounded-lg p-3 text-xs space-y-2">
            <p className="text-foreground-secondary">{signal.message}</p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2">
              {signal.strategy && (
                <div className="flex items-center gap-1">
                  <Target className="w-3 h-3 text-foreground-muted" />
                  <span className="text-foreground-muted">Strategy:</span>
                  <span className="text-foreground-primary font-medium">{signal.strategy}</span>
                </div>
              )}
              {signal.price && (
                <div className="flex items-center gap-1">
                  <BarChart3 className="w-3 h-3 text-foreground-muted" />
                  <span className="text-foreground-muted">Price:</span>
                  <span className="text-foreground-primary font-mono">${signal.price.toFixed(2)}</span>
                </div>
              )}
              {signal.stopLoss && (
                <div className="flex items-center gap-1">
                  <Shield className="w-3 h-3 text-bearish" />
                  <span className="text-foreground-muted">SL:</span>
                  <span className="text-bearish font-mono">${signal.stopLoss.toFixed(2)}</span>
                </div>
              )}
              {signal.takeProfit && (
                <div className="flex items-center gap-1">
                  <Target className="w-3 h-3 text-bullish" />
                  <span className="text-foreground-muted">TP:</span>
                  <span className="text-bullish font-mono">${signal.takeProfit.toFixed(2)}</span>
                </div>
              )}
              {signal.riskReward && (
                <div className="flex items-center gap-1">
                  <span className="text-foreground-muted">R:R</span>
                  <span className="text-accent-primary font-mono font-bold">{signal.riskReward.toFixed(1)}</span>
                </div>
              )}
              {signal.regime && (
                <div className="flex items-center gap-1">
                  <span className="text-foreground-muted">Regime:</span>
                  <span className="text-foreground-primary">{String(signal.regime)}</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-1 text-foreground-muted pt-1">
              <Clock className="w-3 h-3" />
              <span className="text-[10px]">
                {new Date(signal.timestamp).toLocaleString()}
              </span>
              {signal.source && (
                <>
                  <span className="mx-1">|</span>
                  <span className="text-[10px]">Source: {signal.source}</span>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

interface SignalFeedProps {
  maxHeight?: string
  compact?: boolean
  className?: string
}

export function SignalFeed({ maxHeight = '500px', compact = false, className }: SignalFeedProps) {
  const [signals, setSignals] = useState<FeedSignal[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<SignalType | 'all'>('all')
  const [filterSymbol, setFilterSymbol] = useState('')
  const [filterStrategy, setFilterStrategy] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const feedRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  // Fetch signals from API
  const { data: signalsRes } = useQuery({
    queryKey: ['signal-feed-signals'],
    queryFn: () => signalsApi.getAll(),
    refetchInterval: 5000,
    staleTime: 3000,
  })

  // Fetch brain signals
  const { data: brainRes } = useQuery({
    queryKey: ['signal-feed-brain'],
    queryFn: () => brainApi.getSignals(),
    refetchInterval: 10000,
    staleTime: 5000,
  })

  // Merge signals from all sources
  useEffect(() => {
    const allSignals: FeedSignal[] = []

    if (signalsRes?.ok && signalsRes.data) {
      const normalized = (Array.isArray(signalsRes.data) ? signalsRes.data : []).map(normalizeSignal)
      allSignals.push(...normalized)
    }

    if (brainRes?.ok && brainRes.data) {
      const brainSignals = (Array.isArray(brainRes.data) ? brainRes.data : []).map((s: any) => ({
        ...normalizeSignal(s),
        type: 'brain' as SignalType,
        source: 'brain',
      }))
      allSignals.push(...brainSignals)
    }

    // Sort by timestamp descending
    allSignals.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())

    // Deduplicate by id
    const seen = new Set<string>()
    const unique = allSignals.filter(s => {
      if (seen.has(s.id)) return false
      seen.add(s.id)
      return true
    })

    setSignals(unique.slice(0, 200))
  }, [signalsRes, brainRes])

  // Listen for real-time signal events
  useEventSubscription('signal:new', (event) => {
    if (event.data) {
      const normalized = normalizeSignal(event.data)
      setSignals(prev => [normalized, ...prev].slice(0, 200))
    }
  })

  useEventSubscription('brain:signal', (event) => {
    if (event.data) {
      const normalized = { ...normalizeSignal(event.data), type: 'brain' as SignalType }
      setSignals(prev => [normalized, ...prev].slice(0, 200))
    }
  })

  useEventSubscription('risk:alert', (event) => {
    if (event.data) {
      const riskSignal: FeedSignal = {
        id: `risk-${Date.now()}`,
        type: 'risk',
        symbol: 'RISK',
        title: event.data.type || 'Risk Alert',
        message: event.data.message || 'Risk threshold exceeded',
        timestamp: new Date().toISOString(),
        source: 'risk-engine',
      }
      setSignals(prev => [riskSignal, ...prev].slice(0, 200))
    }
  })

  // Auto-scroll to top on new signals
  useEffect(() => {
    if (autoScroll && feedRef.current) {
      feedRef.current.scrollTop = 0
    }
  }, [signals.length, autoScroll])

  // Filter signals
  const filteredSignals = useMemo(() => {
    return signals.filter(s => {
      if (filterType !== 'all' && s.type !== filterType) return false
      if (filterSymbol && !s.symbol.toLowerCase().includes(filterSymbol.toLowerCase())) return false
      if (filterStrategy && s.strategy && !s.strategy.toLowerCase().includes(filterStrategy.toLowerCase())) return false
      return true
    })
  }, [signals, filterType, filterSymbol, filterStrategy])

  // Export to CSV
  const exportCSV = useCallback(() => {
    const headers = ['Timestamp', 'Type', 'Symbol', 'Title', 'Message', 'Confidence', 'Strategy', 'Direction', 'Price', 'StopLoss', 'TakeProfit', 'RiskReward']
    const rows = filteredSignals.map(s => [
      s.timestamp,
      s.type,
      s.symbol,
      s.title,
      s.message.replace(/,/g, ';'),
      s.confidence?.toString() || '',
      s.strategy || '',
      s.direction || '',
      s.price?.toString() || '',
      s.stopLoss?.toString() || '',
      s.takeProfit?.toString() || '',
      s.riskReward?.toString() || '',
    ])

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `signals_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [filteredSignals])

  // Unique strategies for filter dropdown
  const strategies = useMemo(() => {
    const set = new Set(signals.map(s => s.strategy).filter(Boolean) as string[])
    return Array.from(set).sort()
  }, [signals])

  // Unique symbols for filter
  const symbols = useMemo(() => {
    const set = new Set(signals.map(s => s.symbol).filter(s => s !== 'SYSTEM' && s !== 'RISK'))
    return Array.from(set).sort()
  }, [signals])

  return (
    <div className={cn('flex flex-col bg-background-secondary rounded-lg border border-border overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-background-tertiary/50">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-accent-primary" />
          <span className="text-sm font-medium text-foreground-primary">Signal Feed</span>
          <span className="text-[10px] font-mono text-foreground-muted bg-background-tertiary px-1.5 py-0.5 rounded">
            {filteredSignals.length}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'p-1.5 rounded transition-colors',
              showFilters ? 'bg-accent-primary/20 text-accent-primary' : 'hover:bg-background-hover text-foreground-muted'
            )}
            title="Toggle filters"
          >
            <Filter className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={exportCSV}
            className="p-1.5 rounded hover:bg-background-hover text-foreground-muted transition-colors"
            title="Export to CSV"
          >
            <Download className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-background-tertiary/30 flex-wrap">
          {/* Type filter */}
          <div className="flex items-center gap-1">
            {(['all', 'entry', 'exit', 'risk', 'brain', 'info'] as const).map(t => (
              <button
                key={t}
                onClick={() => setFilterType(t)}
                className={cn(
                  'text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider transition-colors',
                  filterType === t
                    ? t === 'all' ? 'bg-accent-primary/20 text-accent-primary' : `${typeConfig[t as keyof typeof typeConfig].bgColor} ${typeConfig[t as keyof typeof typeConfig].color}`
                    : 'text-foreground-muted hover:bg-background-hover'
                )}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Symbol filter */}
          <div className="relative">
            <input
              type="text"
              value={filterSymbol}
              onChange={e => setFilterSymbol(e.target.value)}
              placeholder="Symbol..."
              className="text-[11px] bg-background-primary border border-border rounded px-2 py-0.5 w-20 text-foreground-primary placeholder-foreground-muted outline-none focus:border-accent-primary"
            />
            {filterSymbol && (
              <button onClick={() => setFilterSymbol('')} className="absolute right-1 top-1/2 -translate-y-1/2">
                <X className="w-3 h-3 text-foreground-muted" />
              </button>
            )}
          </div>

          {/* Strategy filter */}
          <select
            value={filterStrategy}
            onChange={e => setFilterStrategy(e.target.value)}
            className="text-[11px] bg-background-primary border border-border rounded px-2 py-0.5 text-foreground-primary outline-none focus:border-accent-primary"
          >
            <option value="">All Strategies</option>
            {strategies.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          {(filterType !== 'all' || filterSymbol || filterStrategy) && (
            <button
              onClick={() => { setFilterType('all'); setFilterSymbol(''); setFilterStrategy('') }}
              className="text-[10px] text-accent-primary hover:underline"
            >
              Clear
            </button>
          )}
        </div>
      )}

      {/* Signal list */}
      <div
        ref={feedRef}
        className="overflow-y-auto"
        style={{ maxHeight }}
        onScroll={(e) => {
          const el = e.currentTarget
          setAutoScroll(el.scrollTop < 10)
        }}
      >
        {filteredSignals.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-foreground-muted">
            <Zap className="w-8 h-8 mb-2 opacity-30" />
            <p className="text-sm">No signals yet</p>
            <p className="text-xs mt-1">Signals will appear here in real-time</p>
          </div>
        ) : (
          filteredSignals.map(signal => (
            <SignalItem
              key={signal.id}
              signal={signal}
              isExpanded={expandedId === signal.id}
              onToggle={() => setExpandedId(expandedId === signal.id ? null : signal.id)}
            />
          ))
        )}
      </div>

      {/* Footer with auto-scroll indicator */}
      {signals.length > 0 && (
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-border bg-background-tertiary/50 text-[10px] text-foreground-muted">
          <span>
            {filteredSignals.length} signal{filteredSignals.length !== 1 ? 's' : ''}
            {filterType !== 'all' && ` (${filterType})`}
          </span>
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={cn(
              'px-1.5 py-0.5 rounded',
              autoScroll ? 'text-accent-primary' : 'text-foreground-muted hover:text-foreground-primary'
            )}
          >
            {autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
          </button>
        </div>
      )}
    </div>
  )
}
