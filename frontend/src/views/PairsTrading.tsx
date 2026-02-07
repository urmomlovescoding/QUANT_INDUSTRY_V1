/**
 * Pairs Trading View
 * ==================
 * Statistical arbitrage pairs analysis with cointegration testing,
 * spread visualization, z-score monitoring, and signal generation.
 * Inspired by Bloomberg, QuantConnect, and professional stat-arb platforms.
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Repeat,
  TrendingUp,
  TrendingDown,
  Activity,
  RefreshCw,
  Search,
  Play,
  Pause,
  AlertTriangle,
  CheckCircle,
  XCircle,
  BarChart3,
  Zap,
  Target,
  Clock,
  ArrowRight,
  Info,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
  Area,
  CartesianGrid,
  BarChart,
  Bar,
  Cell,
} from 'recharts'
import { formatCurrency, formatPercent } from '@/utils/format'
import { Skeleton } from '@/components/ui/LoadingStates'

// ─── Types ────────────────────────────────────────────────────────────────────

interface TradingPair {
  id: string
  asset1: string
  asset2: string
  correlation: number
  cointegration: {
    pValue: number
    isCointegrated: boolean
    halfLife: number
    testStat: number
    criticalValue: number
  }
  spread: {
    current: number
    mean: number
    std: number
    zScore: number
  }
  signal: 'LONG_SPREAD' | 'SHORT_SPREAD' | 'NEUTRAL'
  confidence: number
  performance: {
    totalReturn: number
    sharpeRatio: number
    tradesCount: number
    winRate: number
    maxDrawdown: number
  }
  active: boolean
  spreadHistory: { date: string; spread: number; upper: number; lower: number; mean: number; zScore: number }[]
}

// ─── Constants ────────────────────────────────────────────────────────────────

const DEFAULT_PAIRS = [
  'AAPL/MSFT', 'XOM/CVX', 'GS/MS', 'KO/PEP', 'V/MA',
  'HD/LOW', 'JPM/BAC', 'UNH/CI', 'CAT/DE', 'GOOG/META',
]

const chartTooltipStyle = {
  backgroundColor: '#1a1d20',
  border: '1px solid rgba(255,255,255,0.06)',
  borderRadius: '12px',
  boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
}

// ─── Transform Helpers ────────────────────────────────────────────────────────

function transformPairData(apiPair: any, index: number): TradingPair {
  const mean = apiPair.spread?.mean || apiPair.mean || 1
  const std = apiPair.spread?.std || apiPair.std || 0.1
  const zScore = apiPair.spread?.zScore || apiPair.z_score || 0

  // Generate spread history if not present
  let spreadHistory = apiPair.spread_history || apiPair.spreadHistory || []
  if (spreadHistory.length === 0) {
    spreadHistory = generateSpreadHistory(mean, std, 60)
  }

  return {
    id: apiPair.id || `pair_${index}`,
    asset1: apiPair.asset1 || apiPair.symbol1 || 'N/A',
    asset2: apiPair.asset2 || apiPair.symbol2 || 'N/A',
    correlation: apiPair.correlation || 0,
    cointegration: {
      pValue: apiPair.cointegration?.pValue || apiPair.p_value || 0.1,
      isCointegrated: apiPair.cointegration?.isCointegrated ?? apiPair.is_cointegrated ?? (apiPair.p_value < 0.05),
      halfLife: apiPair.cointegration?.halfLife || apiPair.half_life || 10,
      testStat: apiPair.cointegration?.testStat || apiPair.test_stat || -3.5,
      criticalValue: apiPair.cointegration?.criticalValue || apiPair.critical_value || -2.86,
    },
    spread: {
      current: apiPair.spread?.current || apiPair.current_spread || mean + zScore * std,
      mean,
      std,
      zScore,
    },
    signal: apiPair.signal || (zScore > 2 ? 'SHORT_SPREAD' : zScore < -2 ? 'LONG_SPREAD' : 'NEUTRAL'),
    confidence: apiPair.confidence || Math.min(95, Math.abs(zScore) * 30 + 20),
    performance: {
      totalReturn: apiPair.performance?.totalReturn || apiPair.total_return || 0,
      sharpeRatio: apiPair.performance?.sharpeRatio || apiPair.sharpe_ratio || 0,
      tradesCount: apiPair.performance?.tradesCount || apiPair.trades_count || 0,
      winRate: apiPair.performance?.winRate || apiPair.win_rate || 0,
      maxDrawdown: apiPair.performance?.maxDrawdown || apiPair.max_drawdown || 0,
    },
    active: apiPair.active ?? true,
    spreadHistory,
  }
}

function generateSpreadHistory(mean: number, std: number, days: number) {
  const history: any[] = []
  let spread = mean
  for (let i = 0; i < days; i++) {
    const date = new Date()
    date.setDate(date.getDate() - (days - i))
    // Ornstein-Uhlenbeck process simulation
    const dt = 1 / 252
    const theta = 0.1 // mean reversion speed
    const sigma = std * 0.3
    spread = spread + theta * (mean - spread) * dt + sigma * Math.sqrt(dt) * (Math.random() * 2 - 1)
    const z = (spread - mean) / std
    history.push({
      date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      spread: Math.round(spread * 1000) / 1000,
      upper: Math.round((mean + 2 * std) * 1000) / 1000,
      lower: Math.round((mean - 2 * std) * 1000) / 1000,
      mean: Math.round(mean * 1000) / 1000,
      zScore: Math.round(z * 100) / 100,
    })
  }
  return history
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function PairsTrading() {
  const [pairs, setPairs] = useState<TradingPair[]>([])
  const [selectedPair, setSelectedPair] = useState<TradingPair | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [signalFilter, setSignalFilter] = useState<string>('all')
  const [isLoading, setIsLoading] = useState(true)
  const [scanningPairs, setScanningPairs] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Custom pair analysis
  const [analyzeSymbol1, setAnalyzeSymbol1] = useState('')
  const [analyzeSymbol2, setAnalyzeSymbol2] = useState('')
  const [analyzing, setAnalyzing] = useState(false)

  // ─── Fetch pairs from API ─────────────────────────────────────────────

  const fetchPairs = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/pairs')
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to fetch pairs')
      }

      if (data.status === 'unavailable') {
        setError(data.message || 'Pairs data unavailable. Backend will return data once configured.')
        setPairs([])
        return
      }

      const pairsData = data.data?.pairs || data.pairs || (Array.isArray(data) ? data : [])
      if (pairsData.length > 0) {
        const transformed = pairsData.map(transformPairData)
        setPairs(transformed)
        if (!selectedPair && transformed.length > 0) {
          setSelectedPair(transformed[0])
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch pairs')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPairs()
  }, [fetchPairs])

  // ─── Analyze a custom pair ────────────────────────────────────────────

  const analyzePair = async () => {
    if (!analyzeSymbol1 || !analyzeSymbol2) return
    setAnalyzing(true)
    setError(null)
    try {
      const response = await fetch('/api/pairs/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol1: analyzeSymbol1.toUpperCase(),
          symbol2: analyzeSymbol2.toUpperCase(),
          lookback: 252,
        }),
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to analyze pair')
      }

      const newPair = transformPairData({
        ...data,
        asset1: analyzeSymbol1.toUpperCase(),
        asset2: analyzeSymbol2.toUpperCase(),
      }, pairs.length)

      setPairs(prev => {
        const existing = prev.findIndex(p => p.asset1 === newPair.asset1 && p.asset2 === newPair.asset2)
        if (existing >= 0) {
          const updated = [...prev]
          updated[existing] = newPair
          return updated
        }
        return [newPair, ...prev]
      })
      setSelectedPair(newPair)
      setAnalyzeSymbol1('')
      setAnalyzeSymbol2('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze pair')
    } finally {
      setAnalyzing(false)
    }
  }

  // ─── Scan for cointegrated pairs ──────────────────────────────────────

  const scanForPairs = async () => {
    setScanningPairs(true)
    setError(null)
    try {
      const response = await fetch('/api/pairs/scan', { method: 'POST' })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to scan for pairs')
      }

      await fetchPairs()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to scan for pairs')
    } finally {
      setScanningPairs(false)
    }
  }

  // ─── Filtering ────────────────────────────────────────────────────────

  const filteredPairs = useMemo(() => {
    return pairs.filter(pair => {
      if (searchQuery) {
        const query = searchQuery.toUpperCase()
        if (!pair.asset1.includes(query) && !pair.asset2.includes(query)) return false
      }
      if (signalFilter !== 'all' && pair.signal !== signalFilter) return false
      return true
    })
  }, [pairs, searchQuery, signalFilter])

  // ─── Stats ────────────────────────────────────────────────────────────

  const stats = useMemo(() => {
    const active = pairs.filter(p => p.active)
    const cointegrated = pairs.filter(p => p.cointegration.isCointegrated)
    const withSignal = pairs.filter(p => p.signal !== 'NEUTRAL')
    const avgCorr = pairs.length > 0
      ? pairs.reduce((sum, p) => sum + Math.abs(p.correlation), 0) / pairs.length
      : 0
    const avgHalfLife = cointegrated.length > 0
      ? cointegrated.reduce((sum, p) => sum + p.cointegration.halfLife, 0) / cointegrated.length
      : 0
    return {
      total: pairs.length,
      active: active.length,
      cointegrated: cointegrated.length,
      withSignal: withSignal.length,
      avgCorrelation: avgCorr,
      avgHalfLife,
    }
  }, [pairs])

  const togglePair = (id: string) => {
    setPairs(prev => prev.map(p => p.id === id ? { ...p, active: !p.active } : p))
  }

  // ─── Render ───────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-accent-primary/10">
            <Repeat className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">PAIRS TRADING</h1>
            <p className="text-xs text-foreground-muted">
              Statistical arbitrage | {stats.cointegrated} cointegrated of {stats.total} pairs
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={scanForPairs}
            className="btn-primary flex items-center gap-2"
            disabled={scanningPairs}
          >
            <Target className={cn('w-4 h-4', scanningPairs && 'animate-pulse')} />
            {scanningPairs ? 'Scanning...' : 'Scan Pairs'}
          </button>
          <button
            onClick={fetchPairs}
            className="btn-secondary flex items-center gap-2"
            disabled={isLoading}
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-bearish flex-shrink-0" />
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {/* Stats Overview */}
      <div className="grid grid-cols-6 gap-3 stagger">
        <StatCard label="Total Pairs" value={stats.total.toString()} icon={<Repeat className="w-4 h-4" />} />
        <StatCard label="Active" value={stats.active.toString()} icon={<Play className="w-4 h-4" />} positive />
        <StatCard label="Cointegrated" value={stats.cointegrated.toString()} icon={<CheckCircle className="w-4 h-4" />} />
        <StatCard label="With Signal" value={stats.withSignal.toString()} icon={<Zap className="w-4 h-4" />} highlight />
        <StatCard label="Avg Correlation" value={`${(stats.avgCorrelation * 100).toFixed(0)}%`} icon={<Activity className="w-4 h-4" />} />
        <StatCard label="Avg Half-Life" value={`${stats.avgHalfLife.toFixed(1)}d`} icon={<Clock className="w-4 h-4" />} />
      </div>

      {/* Custom Pair Analysis */}
      <div className="card p-4">
        <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-3">ANALYZE PAIR</h3>
        <div className="flex items-end gap-3">
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Asset 1</label>
            <input
              type="text"
              value={analyzeSymbol1}
              onChange={(e) => setAnalyzeSymbol1(e.target.value.toUpperCase())}
              className="input w-28"
              placeholder="AAPL"
            />
          </div>
          <div className="flex items-center pb-3">
            <Repeat className="w-4 h-4 text-accent-primary" />
          </div>
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Asset 2</label>
            <input
              type="text"
              value={analyzeSymbol2}
              onChange={(e) => setAnalyzeSymbol2(e.target.value.toUpperCase())}
              className="input w-28"
              placeholder="MSFT"
            />
          </div>
          <button
            onClick={analyzePair}
            disabled={analyzing || !analyzeSymbol1 || !analyzeSymbol2}
            className="btn-primary flex items-center gap-2"
          >
            <BarChart3 className={cn('w-4 h-4', analyzing && 'animate-pulse')} />
            {analyzing ? 'Analyzing...' : 'Analyze'}
          </button>
          <div className="flex-1" />
          {/* Search and filter */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground-muted" />
            <input
              type="text"
              placeholder="Search pairs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-48 pl-10 pr-4 py-3 bg-background-tertiary border border-border rounded-xl text-sm text-foreground-primary placeholder:text-foreground-muted focus:outline-none focus:border-accent-primary"
            />
          </div>
          <div className="flex items-center gap-1 bg-background-tertiary rounded-xl p-1">
            {(['all', 'LONG_SPREAD', 'SHORT_SPREAD', 'NEUTRAL'] as const).map(s => (
              <button
                key={s}
                onClick={() => setSignalFilter(s)}
                className={cn(
                  'px-3 py-2 text-xs font-medium rounded-lg transition-colors',
                  signalFilter === s
                    ? s === 'LONG_SPREAD' ? 'bg-bullish/20 text-bullish' :
                      s === 'SHORT_SPREAD' ? 'bg-bearish/20 text-bearish' :
                      s === 'NEUTRAL' ? 'bg-foreground-muted/20 text-foreground-primary' :
                      'bg-accent-primary text-black'
                    : 'text-foreground-muted hover:text-foreground-primary'
                )}
              >
                {s === 'all' ? 'All' : s === 'LONG_SPREAD' ? 'Long' : s === 'SHORT_SPREAD' ? 'Short' : 'Neutral'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      {isLoading ? (
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-5 space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="card p-4">
                <Skeleton className="h-5 w-32 mb-3" />
                <Skeleton className="h-16 w-full mb-2" />
                <Skeleton className="h-4 w-24" />
              </div>
            ))}
          </div>
          <div className="col-span-7 card p-4">
            <Skeleton className="h-6 w-48 mb-4" />
            <Skeleton className="h-64 w-full" />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-4">
          {/* Pairs List */}
          <div className="col-span-5 space-y-3 max-h-[600px] overflow-y-auto scrollbar-thin pr-1">
            {filteredPairs.length === 0 ? (
              <div className="card p-8 text-center text-foreground-muted">
                <Repeat className="w-12 h-12 mx-auto mb-4 opacity-30" />
                <p className="text-sm font-medium">No pairs found</p>
                <p className="text-xs mt-1">Scan for pairs or analyze a custom pair above</p>
              </div>
            ) : (
              filteredPairs.map(pair => (
                <PairCard
                  key={pair.id}
                  pair={pair}
                  onToggle={() => togglePair(pair.id)}
                  onSelect={() => setSelectedPair(pair)}
                  isSelected={selectedPair?.id === pair.id}
                />
              ))
            )}
          </div>

          {/* Detail Panel */}
          <div className="col-span-7">
            {selectedPair ? (
              <PairDetailPanel pair={selectedPair} onToggle={() => togglePair(selectedPair.id)} />
            ) : (
              <div className="card p-12 text-center text-foreground-muted">
                <Info className="w-12 h-12 mx-auto mb-4 opacity-30" />
                <p className="text-lg font-medium text-foreground-secondary">Select a Pair</p>
                <p className="text-sm mt-1">Click on a pair to view detailed analysis</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon,
  positive,
  negative,
  highlight,
}: {
  label: string
  value: string
  icon: React.ReactNode
  positive?: boolean
  negative?: boolean
  highlight?: boolean
}) {
  return (
    <div className="card p-3">
      <div className="flex items-center gap-2 text-foreground-muted mb-1">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className={cn(
        'text-lg font-bold font-mono',
        positive && 'text-bullish',
        negative && 'text-bearish',
        highlight && 'text-accent-primary',
        !positive && !negative && !highlight && 'text-foreground-primary'
      )}>
        {value}
      </div>
    </div>
  )
}

// ─── Pair Card ────────────────────────────────────────────────────────────────

function PairCard({
  pair,
  onToggle,
  onSelect,
  isSelected,
}: {
  pair: TradingPair
  onToggle: () => void
  onSelect: () => void
  isSelected: boolean
}) {
  const signalColor = pair.signal === 'LONG_SPREAD'
    ? 'text-bullish bg-bullish/10'
    : pair.signal === 'SHORT_SPREAD'
      ? 'text-bearish bg-bearish/10'
      : 'text-foreground-muted bg-background-tertiary'

  const zScoreColor = Math.abs(pair.spread.zScore) > 2
    ? pair.spread.zScore > 0 ? 'text-bearish' : 'text-bullish'
    : Math.abs(pair.spread.zScore) > 1
      ? 'text-warning'
      : 'text-foreground-muted'

  return (
    <div
      className={cn(
        'card overflow-hidden cursor-pointer transition-all',
        isSelected && 'ring-1 ring-accent-primary border-accent-primary/30',
        !pair.active && 'opacity-50'
      )}
      onClick={onSelect}
    >
      <div className="p-4">
        {/* Header Row */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="font-bold text-foreground-primary">{pair.asset1}</span>
            <Repeat className="w-3.5 h-3.5 text-accent-primary" />
            <span className="font-bold text-foreground-primary">{pair.asset2}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={cn('px-2 py-0.5 rounded-lg text-xs font-medium', signalColor)}>
              {pair.signal === 'LONG_SPREAD' ? 'LONG' : pair.signal === 'SHORT_SPREAD' ? 'SHORT' : 'FLAT'}
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); onToggle() }}
              className={cn(
                'p-1.5 rounded-lg transition-colors',
                pair.active ? 'bg-bullish/10 text-bullish' : 'bg-background-tertiary text-foreground-muted'
              )}
            >
              {pair.active ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
            </button>
          </div>
        </div>

        {/* Cointegration badge + Z-score */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {pair.cointegration.isCointegrated ? (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-bullish/15 text-bullish flex items-center gap-1">
                <CheckCircle className="w-2.5 h-2.5" /> Coint p={pair.cointegration.pValue.toFixed(3)}
              </span>
            ) : (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-bearish/15 text-bearish flex items-center gap-1">
                <XCircle className="w-2.5 h-2.5" /> p={pair.cointegration.pValue.toFixed(3)}
              </span>
            )}
            <span className="text-[10px] text-foreground-muted">
              HL: {pair.cointegration.halfLife.toFixed(1)}d
            </span>
          </div>
          <div className="text-right">
            <span className={cn('font-bold font-mono text-sm', zScoreColor)}>
              z={pair.spread.zScore > 0 ? '+' : ''}{pair.spread.zScore.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Mini spread chart */}
        <div className="h-14 -mx-2">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={pair.spreadHistory.slice(-30)}>
              <Area type="monotone" dataKey="upper" stroke="none" fill="rgba(239,68,68,0.05)" />
              <Area type="monotone" dataKey="lower" stroke="none" fill="rgba(16,185,129,0.05)" />
              <Line type="monotone" dataKey="upper" stroke="#6b728040" strokeDasharray="2 2" dot={false} strokeWidth={1} />
              <Line type="monotone" dataKey="lower" stroke="#6b728040" strokeDasharray="2 2" dot={false} strokeWidth={1} />
              <Line type="monotone" dataKey="mean" stroke="#f59e0b40" strokeDasharray="4 4" dot={false} strokeWidth={1} />
              <Line type="monotone" dataKey="spread" stroke="#f4f4f5" dot={false} strokeWidth={1.5} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-2 pt-2 border-t border-border mt-2">
          <MiniStat label="Corr" value={`${(pair.correlation * 100).toFixed(0)}%`} />
          <MiniStat label="Return" value={`${pair.performance.totalReturn >= 0 ? '+' : ''}${pair.performance.totalReturn.toFixed(1)}%`}
            color={pair.performance.totalReturn >= 0 ? 'text-bullish' : 'text-bearish'} />
          <MiniStat label="Sharpe" value={pair.performance.sharpeRatio.toFixed(2)} />
          <MiniStat label="WR" value={`${pair.performance.winRate.toFixed(0)}%`} />
        </div>
      </div>
    </div>
  )
}

function MiniStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="text-center">
      <div className={cn('text-xs font-bold font-mono', color || 'text-foreground-primary')}>{value}</div>
      <div className="text-[10px] text-foreground-muted">{label}</div>
    </div>
  )
}

// ─── Pair Detail Panel ────────────────────────────────────────────────────────

function PairDetailPanel({ pair, onToggle }: { pair: TradingPair; onToggle: () => void }) {
  const zScoreColor = Math.abs(pair.spread.zScore) > 2
    ? pair.spread.zScore > 0 ? 'text-bearish' : 'text-bullish'
    : Math.abs(pair.spread.zScore) > 1
      ? 'text-warning'
      : 'text-foreground-primary'

  // Z-score history from spread history
  const zScoreHistory = pair.spreadHistory.map(s => ({
    date: s.date,
    zScore: s.zScore,
  }))

  return (
    <div className="space-y-4">
      {/* Pair Header */}
      <div className="card p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl font-bold text-foreground-primary">{pair.asset1}</span>
            <Repeat className="w-5 h-5 text-accent-primary" />
            <span className="text-xl font-bold text-foreground-primary">{pair.asset2}</span>
            {pair.cointegration.isCointegrated ? (
              <span className="text-xs px-2 py-0.5 rounded-full bg-bullish/15 text-bullish ml-2">
                Cointegrated
              </span>
            ) : (
              <span className="text-xs px-2 py-0.5 rounded-full bg-bearish/15 text-bearish ml-2">
                Not Cointegrated
              </span>
            )}
          </div>
          <button
            onClick={onToggle}
            className={cn(
              'px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors',
              pair.active
                ? 'bg-bearish/10 text-bearish hover:bg-bearish/20'
                : 'bg-bullish/10 text-bullish hover:bg-bullish/20'
            )}
          >
            {pair.active ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {pair.active ? 'Disable' : 'Enable'}
          </button>
        </div>
      </div>

      {/* Spread Chart with Bollinger Bands */}
      <div className="card p-4">
        <div className="chart-header">
          <h3 className="chart-title">Spread with Bollinger Bands</h3>
          <div className="flex items-center gap-4 text-xs text-foreground-muted">
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-white rounded" /> Spread</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-accent-primary rounded" /> Mean</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-gray-500 rounded" /> +/-2\u03C3</span>
          </div>
        </div>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={pair.spreadHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
              <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }} />
              <Area type="monotone" dataKey="upper" stroke="none" fill="rgba(239,68,68,0.04)" stackId="band" />
              <Line type="monotone" dataKey="upper" stroke="#ef444450" strokeDasharray="3 3" dot={false} strokeWidth={1} name="+2\u03C3" />
              <Line type="monotone" dataKey="lower" stroke="#10b98150" strokeDasharray="3 3" dot={false} strokeWidth={1} name="-2\u03C3" />
              <Line type="monotone" dataKey="mean" stroke="#f59e0b" strokeDasharray="5 5" dot={false} strokeWidth={1} name="Mean" />
              <Line type="monotone" dataKey="spread" stroke="#f4f4f5" dot={false} strokeWidth={2} name="Spread" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Z-Score Chart */}
      <div className="card p-4">
        <div className="chart-header">
          <h3 className="chart-title">Z-Score Indicator</h3>
          <span className={cn('text-lg font-bold font-mono', zScoreColor)}>
            {pair.spread.zScore > 0 ? '+' : ''}{pair.spread.zScore.toFixed(2)}
          </span>
        </div>
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={zScoreHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 9 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} domain={[-3, 3]} />
              <ReferenceLine y={2} stroke="#ef4444" strokeDasharray="3 3" />
              <ReferenceLine y={-2} stroke="#10b981" strokeDasharray="3 3" />
              <ReferenceLine y={0} stroke="#71717a" />
              <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }} />
              <Bar dataKey="zScore" name="Z-Score" radius={[2, 2, 0, 0]}>
                {zScoreHistory.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.zScore > 2 ? '#ef4444' : entry.zScore < -2 ? '#10b981' : entry.zScore > 1 ? '#f59e0b' : entry.zScore < -1 ? '#f59e0b' : '#4b5563'}
                    fillOpacity={0.7}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center justify-center gap-6 mt-2 text-xs text-foreground-muted">
          <span>Short Entry: z &gt; +2</span>
          <span>|</span>
          <span>Long Entry: z &lt; -2</span>
          <span>|</span>
          <span>Exit: z ~ 0</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4">
        {/* Cointegration Stats */}
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-3">COINTEGRATION TEST</h3>
          <div className="space-y-2.5">
            <DetailRow label="P-Value" value={pair.cointegration.pValue.toFixed(4)}
              color={pair.cointegration.pValue < 0.05 ? 'text-bullish' : 'text-bearish'} />
            <DetailRow label="Test Statistic" value={pair.cointegration.testStat.toFixed(3)} />
            <DetailRow label="Critical Value (5%)" value={pair.cointegration.criticalValue.toFixed(3)} />
            <DetailRow label="Half-Life" value={`${pair.cointegration.halfLife.toFixed(1)} days`} />
            <DetailRow label="Correlation" value={`${(pair.correlation * 100).toFixed(1)}%`} />
            <DetailRow label="Status"
              value={pair.cointegration.isCointegrated ? 'COINTEGRATED' : 'NOT COINTEGRATED'}
              color={pair.cointegration.isCointegrated ? 'text-bullish' : 'text-bearish'} />
          </div>
        </div>

        {/* Performance Stats */}
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-3">PERFORMANCE</h3>
          <div className="space-y-2.5">
            <DetailRow label="Total Return"
              value={`${pair.performance.totalReturn >= 0 ? '+' : ''}${pair.performance.totalReturn.toFixed(2)}%`}
              color={pair.performance.totalReturn >= 0 ? 'text-bullish' : 'text-bearish'} />
            <DetailRow label="Sharpe Ratio" value={pair.performance.sharpeRatio.toFixed(2)} />
            <DetailRow label="Win Rate" value={`${pair.performance.winRate.toFixed(1)}%`} />
            <DetailRow label="Total Trades" value={pair.performance.tradesCount.toString()} />
            <DetailRow label="Max Drawdown"
              value={`${pair.performance.maxDrawdown.toFixed(2)}%`}
              color="text-bearish" />
            <DetailRow label="Signal Confidence" value={`${pair.confidence.toFixed(0)}%`}
              color={pair.confidence >= 70 ? 'text-bullish' : pair.confidence >= 50 ? 'text-warning' : 'text-foreground-muted'} />
          </div>
        </div>
      </div>

      {/* Spread Stats */}
      <div className="grid grid-cols-4 gap-3">
        <div className="card p-3 text-center">
          <div className="text-xs text-foreground-muted mb-1">Current Spread</div>
          <div className="text-lg font-bold font-mono text-foreground-primary">{pair.spread.current.toFixed(3)}</div>
        </div>
        <div className="card p-3 text-center">
          <div className="text-xs text-foreground-muted mb-1">Mean</div>
          <div className="text-lg font-bold font-mono text-accent-primary">{pair.spread.mean.toFixed(3)}</div>
        </div>
        <div className="card p-3 text-center">
          <div className="text-xs text-foreground-muted mb-1">Std Dev</div>
          <div className="text-lg font-bold font-mono text-foreground-primary">{pair.spread.std.toFixed(4)}</div>
        </div>
        <div className="card p-3 text-center">
          <div className="text-xs text-foreground-muted mb-1">Z-Score</div>
          <div className={cn('text-lg font-bold font-mono', zScoreColor)}>
            {pair.spread.zScore > 0 ? '+' : ''}{pair.spread.zScore.toFixed(2)}
          </div>
        </div>
      </div>
    </div>
  )
}

function DetailRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between items-center text-xs">
      <span className="text-foreground-muted">{label}</span>
      <span className={cn('font-mono font-medium', color || 'text-foreground-primary')}>{value}</span>
    </div>
  )
}
