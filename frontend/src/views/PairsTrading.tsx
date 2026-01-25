import { useState, useEffect, useMemo } from 'react'
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
  AreaChart,
  Area,
  ComposedChart,
  Bar,
} from 'recharts'

interface TradingPair {
  id: string
  asset1: string
  asset2: string
  correlation: number
  cointegration: {
    pValue: number
    isCointegrated: boolean
    halfLife: number
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
  }
  active: boolean
  spreadHistory: { date: string; spread: number; upper: number; lower: number; mean: number }[]
}

// Generate mock spread history
const generateSpreadHistory = (days: number, mean: number, std: number) => {
  const data = []
  let spread = mean
  for (let i = 0; i < days; i++) {
    const noise = (Math.random() - 0.5) * std * 2
    spread = spread * 0.95 + mean * 0.05 + noise // Mean reversion + noise
    data.push({
      date: new Date(Date.now() - (days - i) * 24 * 60 * 60 * 1000).toLocaleDateString(),
      spread: spread,
      upper: mean + 2 * std,
      lower: mean - 2 * std,
      mean: mean,
    })
  }
  return data
}

// Mock pairs data
const mockPairs: TradingPair[] = [
  {
    id: 'pair_1',
    asset1: 'XOM',
    asset2: 'CVX',
    correlation: 0.92,
    cointegration: { pValue: 0.02, isCointegrated: true, halfLife: 12 },
    spread: { current: 1.23, mean: 1.15, std: 0.18, zScore: 0.44 },
    signal: 'NEUTRAL',
    confidence: 65,
    performance: { totalReturn: 18.5, sharpeRatio: 1.42, tradesCount: 34, winRate: 68 },
    active: true,
    spreadHistory: generateSpreadHistory(60, 1.15, 0.18),
  },
  {
    id: 'pair_2',
    asset1: 'KO',
    asset2: 'PEP',
    correlation: 0.89,
    cointegration: { pValue: 0.01, isCointegrated: true, halfLife: 8 },
    spread: { current: 0.78, mean: 0.85, std: 0.12, zScore: -0.58 },
    signal: 'LONG_SPREAD',
    confidence: 72,
    performance: { totalReturn: 22.3, sharpeRatio: 1.65, tradesCount: 42, winRate: 71 },
    active: true,
    spreadHistory: generateSpreadHistory(60, 0.85, 0.12),
  },
  {
    id: 'pair_3',
    asset1: 'GS',
    asset2: 'MS',
    correlation: 0.87,
    cointegration: { pValue: 0.03, isCointegrated: true, halfLife: 15 },
    spread: { current: 2.45, mean: 2.10, std: 0.22, zScore: 1.59 },
    signal: 'SHORT_SPREAD',
    confidence: 78,
    performance: { totalReturn: 15.8, sharpeRatio: 1.28, tradesCount: 28, winRate: 64 },
    active: true,
    spreadHistory: generateSpreadHistory(60, 2.10, 0.22),
  },
  {
    id: 'pair_4',
    asset1: 'MSFT',
    asset2: 'GOOGL',
    correlation: 0.85,
    cointegration: { pValue: 0.08, isCointegrated: false, halfLife: 25 },
    spread: { current: 0.52, mean: 0.48, std: 0.08, zScore: 0.50 },
    signal: 'NEUTRAL',
    confidence: 45,
    performance: { totalReturn: 8.2, sharpeRatio: 0.95, tradesCount: 18, winRate: 56 },
    active: false,
    spreadHistory: generateSpreadHistory(60, 0.48, 0.08),
  },
  {
    id: 'pair_5',
    asset1: 'HD',
    asset2: 'LOW',
    correlation: 0.91,
    cointegration: { pValue: 0.015, isCointegrated: true, halfLife: 10 },
    spread: { current: 1.85, mean: 1.92, std: 0.15, zScore: -0.47 },
    signal: 'LONG_SPREAD',
    confidence: 68,
    performance: { totalReturn: 19.7, sharpeRatio: 1.48, tradesCount: 38, winRate: 66 },
    active: true,
    spreadHistory: generateSpreadHistory(60, 1.92, 0.15),
  },
  {
    id: 'pair_6',
    asset1: 'V',
    asset2: 'MA',
    correlation: 0.94,
    cointegration: { pValue: 0.005, isCointegrated: true, halfLife: 6 },
    spread: { current: 0.68, mean: 0.65, std: 0.09, zScore: 0.33 },
    signal: 'NEUTRAL',
    confidence: 55,
    performance: { totalReturn: 24.1, sharpeRatio: 1.72, tradesCount: 52, winRate: 73 },
    active: true,
    spreadHistory: generateSpreadHistory(60, 0.65, 0.09),
  },
]

export function PairsTrading() {
  const [pairs, setPairs] = useState<TradingPair[]>(mockPairs)
  const [selectedPair, setSelectedPair] = useState<TradingPair | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [signalFilter, setSignalFilter] = useState<string>('all')
  const [isLoading, setIsLoading] = useState(false)
  const [scanningPairs, setScanningPairs] = useState(false)

  // Fetch pairs from API
  useEffect(() => {
    const fetchPairs = async () => {
      try {
        const response = await fetch('/api/pairs')
        if (response.ok) {
          const data = await response.json()
          if (Array.isArray(data) && data.length > 0) {
            setPairs(data)
          }
        }
      } catch (error) {
        console.error('Failed to fetch pairs:', error)
      }
    }
    fetchPairs()
  }, [])

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

  const togglePair = (id: string) => {
    setPairs(prev => prev.map(p => p.id === id ? { ...p, active: !p.active } : p))
  }

  const scanForPairs = async () => {
    setScanningPairs(true)
    await new Promise(resolve => setTimeout(resolve, 2000))
    setScanningPairs(false)
  }

  const stats = useMemo(() => {
    const active = pairs.filter(p => p.active)
    const cointegrated = pairs.filter(p => p.cointegration.isCointegrated)
    const withSignal = pairs.filter(p => p.signal !== 'NEUTRAL')
    return {
      total: pairs.length,
      active: active.length,
      cointegrated: cointegrated.length,
      withSignal: withSignal.length,
      avgCorrelation: pairs.reduce((sum, p) => sum + p.correlation, 0) / pairs.length,
    }
  }, [pairs])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Repeat className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">PAIRS TRADING</h1>
            <p className="text-xs text-foreground-muted">
              Statistical arbitrage • {stats.active} active pairs
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
            onClick={() => window.location.reload()}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-5 gap-3">
        <StatCard label="Total Pairs" value={stats.total.toString()} icon={<Repeat className="w-4 h-4" />} />
        <StatCard label="Active" value={stats.active.toString()} icon={<Play className="w-4 h-4" />} positive />
        <StatCard label="Cointegrated" value={stats.cointegrated.toString()} icon={<CheckCircle className="w-4 h-4" />} />
        <StatCard label="With Signal" value={stats.withSignal.toString()} icon={<Zap className="w-4 h-4" />} />
        <StatCard label="Avg Correlation" value={`${(stats.avgCorrelation * 100).toFixed(0)}%`} icon={<Activity className="w-4 h-4" />} />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground-muted" />
          <input
            type="text"
            placeholder="Search pairs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-foreground-primary placeholder:text-foreground-muted focus:outline-none focus:border-accent-primary"
          />
        </div>

        <div className="flex items-center gap-1 bg-surface-secondary rounded-lg p-1">
          {(['all', 'LONG_SPREAD', 'SHORT_SPREAD', 'NEUTRAL'] as const).map(s => (
            <button
              key={s}
              onClick={() => setSignalFilter(s)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                signalFilter === s
                  ? s === 'LONG_SPREAD' ? 'bg-bullish/20 text-bullish' :
                    s === 'SHORT_SPREAD' ? 'bg-bearish/20 text-bearish' :
                    s === 'NEUTRAL' ? 'bg-foreground-muted/20 text-foreground-primary' :
                    'bg-accent-primary text-background-primary'
                  : 'text-foreground-muted hover:text-foreground-primary'
              )}
            >
              {s === 'all' ? 'All' : s === 'LONG_SPREAD' ? 'Long' : s === 'SHORT_SPREAD' ? 'Short' : 'Neutral'}
            </button>
          ))}
        </div>
      </div>

      {/* Pairs Grid */}
      <div className="grid grid-cols-2 gap-4">
        {filteredPairs.map(pair => (
          <PairCard
            key={pair.id}
            pair={pair}
            onToggle={() => togglePair(pair.id)}
            onSelect={() => setSelectedPair(pair)}
            isSelected={selectedPair?.id === pair.id}
          />
        ))}
      </div>

      {/* Pair Detail Modal */}
      {selectedPair && (
        <PairDetail
          pair={selectedPair}
          onClose={() => setSelectedPair(null)}
          onToggle={() => togglePair(selectedPair.id)}
        />
      )}
    </div>
  )
}

function StatCard({
  label,
  value,
  icon,
  positive,
  negative
}: {
  label: string
  value: string
  icon: React.ReactNode
  positive?: boolean
  negative?: boolean
}) {
  return (
    <div className="card p-3">
      <div className="flex items-center gap-2 text-foreground-muted mb-1">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className={cn(
        'text-lg font-bold',
        positive && 'text-bullish',
        negative && 'text-bearish',
        !positive && !negative && 'text-foreground-primary'
      )}>
        {value}
      </div>
    </div>
  )
}

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
      : 'text-foreground-muted bg-surface-secondary'

  const zScoreColor = Math.abs(pair.spread.zScore) > 2
    ? pair.spread.zScore > 0 ? 'text-bearish' : 'text-bullish'
    : Math.abs(pair.spread.zScore) > 1
      ? 'text-warning'
      : 'text-foreground-muted'

  return (
    <div
      className={cn(
        'card overflow-hidden cursor-pointer transition-all',
        isSelected && 'ring-2 ring-accent-primary',
        !pair.active && 'opacity-60'
      )}
      onClick={onSelect}
    >
      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-bold text-lg text-foreground-primary">{pair.asset1}</span>
              <Repeat className="w-4 h-4 text-accent-primary" />
              <span className="font-bold text-lg text-foreground-primary">{pair.asset2}</span>
            </div>
            <div className="flex items-center gap-2">
              {pair.cointegration.isCointegrated ? (
                <span className="text-xs px-2 py-0.5 rounded-full bg-bullish/20 text-bullish flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" /> Cointegrated
                </span>
              ) : (
                <span className="text-xs px-2 py-0.5 rounded-full bg-bearish/20 text-bearish flex items-center gap-1">
                  <XCircle className="w-3 h-3" /> Not Cointegrated
                </span>
              )}
              <span className="text-xs text-foreground-muted">
                p={pair.cointegration.pValue.toFixed(3)}
              </span>
            </div>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onToggle(); }}
            className={cn(
              'p-2 rounded-lg transition-colors',
              pair.active ? 'bg-bullish/20 text-bullish' : 'bg-surface-secondary text-foreground-muted'
            )}
          >
            {pair.active ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
          </button>
        </div>

        {/* Signal & Z-Score */}
        <div className="flex items-center justify-between mb-3">
          <div className={cn('px-3 py-1 rounded-lg text-sm font-medium', signalColor)}>
            {pair.signal === 'LONG_SPREAD' ? 'LONG SPREAD' : pair.signal === 'SHORT_SPREAD' ? 'SHORT SPREAD' : 'NEUTRAL'}
          </div>
          <div className="text-right">
            <div className="text-xs text-foreground-muted">Z-Score</div>
            <div className={cn('font-bold text-lg font-mono', zScoreColor)}>
              {pair.spread.zScore > 0 ? '+' : ''}{pair.spread.zScore.toFixed(2)}
            </div>
          </div>
        </div>

        {/* Mini spread chart */}
        <div className="h-20 -mx-2 mb-3">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={pair.spreadHistory.slice(-30)}>
              <Line type="monotone" dataKey="upper" stroke="#6b7280" strokeDasharray="3 3" dot={false} strokeWidth={1} />
              <Line type="monotone" dataKey="lower" stroke="#6b7280" strokeDasharray="3 3" dot={false} strokeWidth={1} />
              <Line type="monotone" dataKey="mean" stroke="#00d4aa" strokeDasharray="5 5" dot={false} strokeWidth={1} />
              <Line type="monotone" dataKey="spread" stroke="#fff" dot={false} strokeWidth={2} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-2 pt-3 border-t border-border">
          <div className="text-center">
            <div className="text-sm font-bold text-foreground-primary">{(pair.correlation * 100).toFixed(0)}%</div>
            <div className="text-xs text-foreground-muted">Correlation</div>
          </div>
          <div className="text-center">
            <div className={cn('text-sm font-bold', pair.performance.totalReturn >= 0 ? 'text-bullish' : 'text-bearish')}>
              {pair.performance.totalReturn >= 0 ? '+' : ''}{pair.performance.totalReturn}%
            </div>
            <div className="text-xs text-foreground-muted">Return</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-foreground-primary">{pair.performance.sharpeRatio}</div>
            <div className="text-xs text-foreground-muted">Sharpe</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-foreground-primary">{pair.performance.winRate}%</div>
            <div className="text-xs text-foreground-muted">Win Rate</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function PairDetail({
  pair,
  onClose,
  onToggle,
}: {
  pair: TradingPair
  onClose: () => void
  onToggle: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-surface-primary border border-border rounded-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          {/* Header */}
          <div className="flex items-start justify-between mb-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl font-bold text-foreground-primary">{pair.asset1}</span>
                <Repeat className="w-6 h-6 text-accent-primary" />
                <span className="text-2xl font-bold text-foreground-primary">{pair.asset2}</span>
              </div>
              <div className="flex items-center gap-3">
                {pair.cointegration.isCointegrated ? (
                  <span className="text-sm px-3 py-1 rounded-full bg-bullish/20 text-bullish">Cointegrated</span>
                ) : (
                  <span className="text-sm px-3 py-1 rounded-full bg-bearish/20 text-bearish">Not Cointegrated</span>
                )}
                <span className="text-sm text-foreground-muted">Half-life: {pair.cointegration.halfLife} days</span>
              </div>
            </div>
            <button onClick={onClose} className="text-foreground-muted hover:text-foreground-primary">
              <XCircle className="w-6 h-6" />
            </button>
          </div>

          {/* Spread Chart */}
          <div className="card p-4 mb-4">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Spread History (60 Days)</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={pair.spreadHistory}>
                  <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                    labelStyle={{ color: '#9ca3af' }}
                  />
                  <ReferenceLine y={pair.spread.mean + 2 * pair.spread.std} stroke="#ff5252" strokeDasharray="3 3" />
                  <ReferenceLine y={pair.spread.mean - 2 * pair.spread.std} stroke="#00c853" strokeDasharray="3 3" />
                  <ReferenceLine y={pair.spread.mean} stroke="#00d4aa" strokeDasharray="5 5" />
                  <Line type="monotone" dataKey="spread" stroke="#fff" dot={false} strokeWidth={2} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Current Spread</div>
              <div className="text-2xl font-bold text-foreground-primary">{pair.spread.current.toFixed(2)}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Mean</div>
              <div className="text-2xl font-bold text-foreground-primary">{pair.spread.mean.toFixed(2)}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Std Dev</div>
              <div className="text-2xl font-bold text-foreground-primary">{pair.spread.std.toFixed(2)}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Z-Score</div>
              <div className={cn(
                'text-2xl font-bold',
                Math.abs(pair.spread.zScore) > 2 ? pair.spread.zScore > 0 ? 'text-bearish' : 'text-bullish' :
                Math.abs(pair.spread.zScore) > 1 ? 'text-warning' : 'text-foreground-primary'
              )}>
                {pair.spread.zScore > 0 ? '+' : ''}{pair.spread.zScore.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Performance */}
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Total Return</div>
              <div className={cn('text-2xl font-bold', pair.performance.totalReturn >= 0 ? 'text-bullish' : 'text-bearish')}>
                {pair.performance.totalReturn >= 0 ? '+' : ''}{pair.performance.totalReturn}%
              </div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Sharpe Ratio</div>
              <div className="text-2xl font-bold text-foreground-primary">{pair.performance.sharpeRatio}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Win Rate</div>
              <div className="text-2xl font-bold text-foreground-primary">{pair.performance.winRate}%</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Total Trades</div>
              <div className="text-2xl font-bold text-foreground-primary">{pair.performance.tradesCount}</div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={onToggle}
              className={cn(
                'flex-1 py-3 rounded-lg font-medium flex items-center justify-center gap-2',
                pair.active ? 'bg-bearish/20 text-bearish hover:bg-bearish/30' : 'bg-bullish/20 text-bullish hover:bg-bullish/30'
              )}
            >
              {pair.active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              {pair.active ? 'Disable Pair' : 'Enable Pair'}
            </button>
            <button className="flex-1 py-3 rounded-lg font-medium bg-accent-primary/20 text-accent-primary hover:bg-accent-primary/30 flex items-center justify-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Run Backtest
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
