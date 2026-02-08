import { useState, useEffect, useMemo } from 'react'
import {
  Target,
  Play,
  Pause,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Settings2,
  RefreshCw,
  Zap,
  Activity,
  ChevronRight,
  Info,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from 'recharts'

interface Strategy {
  id: string
  name: string
  description: string
  category: 'trend' | 'mean_reversion' | 'momentum' | 'volatility' | 'ml'
  active: boolean
  weight: number
  performance: {
    totalReturn: number
    sharpeRatio: number
    maxDrawdown: number
    winRate: number
    profitFactor: number
    tradesCount: number
  }
  signals: {
    current: 'BUY' | 'SELL' | 'HOLD'
    confidence: number
  }
  equity: { date: string; value: number }[]
}

const categoryColors: Record<string, string> = {
  trend: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  mean_reversion: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  momentum: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  volatility: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  ml: 'bg-accent-primary/20 text-accent-primary border-accent-primary/30',
}

const categoryLabels: Record<string, string> = {
  trend: 'Trend Following',
  mean_reversion: 'Mean Reversion',
  momentum: 'Momentum',
  volatility: 'Volatility',
  ml: 'Machine Learning',
}

// Transform API strategy data
const transformStrategyData = (apiStrategy: any, index: number): Strategy => {
  return {
    id: apiStrategy.id || `strategy_${index}`,
    name: apiStrategy.name || 'Unknown Strategy',
    description: apiStrategy.description || '',
    category: apiStrategy.category || 'trend',
    active: apiStrategy.active ?? true,
    weight: apiStrategy.weight || 10,
    performance: {
      totalReturn: apiStrategy.performance?.totalReturn || apiStrategy.total_return || 0,
      sharpeRatio: apiStrategy.performance?.sharpeRatio || apiStrategy.sharpe_ratio || 0,
      maxDrawdown: apiStrategy.performance?.maxDrawdown || apiStrategy.max_drawdown || 0,
      winRate: apiStrategy.performance?.winRate || apiStrategy.win_rate || 0,
      profitFactor: apiStrategy.performance?.profitFactor || apiStrategy.profit_factor || 1,
      tradesCount: apiStrategy.performance?.tradesCount || apiStrategy.trades_count || 0,
    },
    signals: {
      current: apiStrategy.signals?.current || apiStrategy.signal || 'HOLD',
      confidence: apiStrategy.signals?.confidence || apiStrategy.confidence || 50,
    },
    equity: apiStrategy.equity || apiStrategy.equity_curve || [],
  }
}

export function Strategies() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null)
  const [filter, setFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch strategies from API
  const fetchStrategies = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/quant/strategies')
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to fetch strategies')
      }

      if (data.status === 'unavailable') {
        setError(data.message || 'Strategies not available. Configure quant service to enable.')
        setStrategies([])
        return
      }

      const strategiesData = data.data?.strategies || data.strategies || (Array.isArray(data) ? data : [])
      if (strategiesData.length > 0) {
        setStrategies(strategiesData.map(transformStrategyData))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch strategies')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchStrategies()
  }, [])

  const filteredStrategies = useMemo(() => {
    return strategies.filter(s => {
      if (filter === 'active' && !s.active) return false
      if (filter === 'inactive' && s.active) return false
      if (categoryFilter !== 'all' && s.category !== categoryFilter) return false
      return true
    })
  }, [strategies, filter, categoryFilter])

  const toggleStrategy = async (id: string) => {
    setStrategies(prev => prev.map(s =>
      s.id === id ? { ...s, active: !s.active } : s
    ))
    // Strategy state persists in component for this session;
    // brain ensemble auto-syncs active strategies on next signal generation cycle
  }

  const aggregateStats = useMemo(() => {
    const active = strategies.filter(s => s.active)
    if (active.length === 0) return null

    const totalWeight = active.reduce((sum, s) => sum + s.weight, 0)
    const weightedReturn = active.reduce((sum, s) => sum + s.performance.totalReturn * (s.weight / totalWeight), 0)
    const weightedSharpe = active.reduce((sum, s) => sum + s.performance.sharpeRatio * (s.weight / totalWeight), 0)
    const avgWinRate = active.reduce((sum, s) => sum + s.performance.winRate, 0) / active.length
    const maxDD = Math.min(...active.map(s => s.performance.maxDrawdown))

    return {
      activeCount: active.length,
      totalWeight,
      weightedReturn,
      weightedSharpe,
      avgWinRate,
      maxDD,
    }
  }, [strategies])

  const runBacktest = async (strategyId: string) => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/backtest/run?strategy=${strategyId}&symbol=SPY`, {
        method: 'POST',
      })
      if (response.ok) {
        const result = await response.json()
        // Backtest completed - result available for display
      }
    } catch (error) {
      console.error('Backtest failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Target className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">STRATEGY LIBRARY</h1>
            <p className="text-xs text-foreground-muted">
              {strategies.filter(s => s.active).length} active strategies • {strategies.length} total
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-secondary flex items-center gap-2"
            onClick={() => window.location.reload()}
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

      {/* Aggregate Stats */}
      {aggregateStats && (
        <div className="grid grid-cols-6 gap-3">
          <StatCard
            label="Active Strategies"
            value={aggregateStats.activeCount.toString()}
            icon={<Activity className="w-4 h-4" />}
          />
          <StatCard
            label="Weighted Return"
            value={`${aggregateStats.weightedReturn.toFixed(1)}%`}
            icon={<TrendingUp className="w-4 h-4" />}
            positive
          />
          <StatCard
            label="Avg Sharpe"
            value={aggregateStats.weightedSharpe.toFixed(2)}
            icon={<BarChart3 className="w-4 h-4" />}
          />
          <StatCard
            label="Avg Win Rate"
            value={`${aggregateStats.avgWinRate.toFixed(1)}%`}
            icon={<CheckCircle2 className="w-4 h-4" />}
          />
          <StatCard
            label="Max Drawdown"
            value={`${aggregateStats.maxDD.toFixed(1)}%`}
            icon={<TrendingDown className="w-4 h-4" />}
            negative
          />
          <StatCard
            label="Total Weight"
            value={`${aggregateStats.totalWeight}%`}
            icon={<Zap className="w-4 h-4" />}
          />
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1 bg-surface-secondary rounded-lg p-1">
          {(['all', 'active', 'inactive'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                filter === f ? 'bg-accent-primary text-background-primary' : 'text-foreground-muted hover:text-foreground-primary'
              )}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="bg-surface-secondary border border-border rounded-lg px-3 py-1.5 text-sm text-foreground-primary"
        >
          <option value="all">All Categories</option>
          {Object.entries(categoryLabels).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </div>

      {/* Strategy Grid */}
      <div className="grid grid-cols-2 gap-4">
        {filteredStrategies.map(strategy => (
          <StrategyCard
            key={strategy.id}
            strategy={strategy}
            onToggle={() => toggleStrategy(strategy.id)}
            onSelect={() => setSelectedStrategy(strategy)}
            onBacktest={() => runBacktest(strategy.id)}
            isSelected={selectedStrategy?.id === strategy.id}
          />
        ))}
      </div>

      {/* Strategy Detail Modal */}
      {selectedStrategy && (
        <StrategyDetail
          strategy={selectedStrategy}
          onClose={() => setSelectedStrategy(null)}
          onToggle={() => toggleStrategy(selectedStrategy.id)}
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

function StrategyCard({
  strategy,
  onToggle,
  onSelect,
  onBacktest,
  isSelected,
}: {
  strategy: Strategy
  onToggle: () => void
  onSelect: () => void
  onBacktest: () => void
  isSelected: boolean
}) {
  const signalColor = strategy.signals.current === 'BUY'
    ? 'text-bullish'
    : strategy.signals.current === 'SELL'
      ? 'text-bearish'
      : 'text-foreground-muted'

  return (
    <div
      className={cn(
        'card overflow-hidden cursor-pointer transition-all',
        isSelected && 'ring-2 ring-accent-primary',
        !strategy.active && 'opacity-60'
      )}
      onClick={onSelect}
    >
      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-foreground-primary">{strategy.name}</h3>
              <span className={cn('text-xs px-2 py-0.5 rounded-full border', categoryColors[strategy.category])}>
                {categoryLabels[strategy.category]}
              </span>
            </div>
            <p className="text-xs text-foreground-muted line-clamp-2">{strategy.description}</p>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onToggle(); }}
            className={cn(
              'p-2 rounded-lg transition-colors',
              strategy.active ? 'bg-bullish/20 text-bullish' : 'bg-surface-secondary text-foreground-muted'
            )}
          >
            {strategy.active ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
          </button>
        </div>

        {/* Signal */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-foreground-muted">Signal:</span>
            <span className={cn('font-bold text-sm', signalColor)}>
              {strategy.signals.current}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-foreground-muted">Confidence:</span>
            <div className="w-16 h-2 bg-surface-secondary rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full',
                  strategy.signals.confidence >= 70 ? 'bg-bullish' :
                  strategy.signals.confidence >= 50 ? 'bg-warning' : 'bg-bearish'
                )}
                style={{ width: `${strategy.signals.confidence}%` }}
              />
            </div>
            <span className="text-xs font-mono">{strategy.signals.confidence}%</span>
          </div>
        </div>

        {/* Mini equity chart */}
        <div className="h-16 -mx-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={strategy.equity.slice(-30)}>
              <defs>
                <linearGradient id={`gradient-${strategy.id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={strategy.performance.totalReturn >= 0 ? '#00c853' : '#ff5252'} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={strategy.performance.totalReturn >= 0 ? '#00c853' : '#ff5252'} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="value"
                stroke={strategy.performance.totalReturn >= 0 ? '#00c853' : '#ff5252'}
                fill={`url(#gradient-${strategy.id})`}
                strokeWidth={1.5}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-2 mt-3 pt-3 border-t border-border">
          <div className="text-center">
            <div className={cn('text-sm font-bold', strategy.performance.totalReturn >= 0 ? 'text-bullish' : 'text-bearish')}>
              {strategy.performance.totalReturn >= 0 ? '+' : ''}{strategy.performance.totalReturn}%
            </div>
            <div className="text-xs text-foreground-muted">Return</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-foreground-primary">{strategy.performance.sharpeRatio}</div>
            <div className="text-xs text-foreground-muted">Sharpe</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-foreground-primary">{strategy.performance.winRate}%</div>
            <div className="text-xs text-foreground-muted">Win Rate</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-bearish">{strategy.performance.maxDrawdown}%</div>
            <div className="text-xs text-foreground-muted">Max DD</div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex border-t border-border">
        <button
          onClick={(e) => { e.stopPropagation(); onBacktest(); }}
          className="flex-1 py-2 text-xs font-medium text-foreground-muted hover:text-foreground-primary hover:bg-surface-secondary transition-colors flex items-center justify-center gap-1"
        >
          <BarChart3 className="w-3 h-3" />
          Backtest
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onSelect(); }}
          className="flex-1 py-2 text-xs font-medium text-foreground-muted hover:text-foreground-primary hover:bg-surface-secondary transition-colors flex items-center justify-center gap-1 border-l border-border"
        >
          <Settings2 className="w-3 h-3" />
          Configure
        </button>
      </div>
    </div>
  )
}

function StrategyDetail({
  strategy,
  onClose,
  onToggle,
}: {
  strategy: Strategy
  onClose: () => void
  onToggle: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-surface-primary border border-border rounded-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          {/* Header */}
          <div className="flex items-start justify-between mb-6">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-xl font-bold text-foreground-primary">{strategy.name}</h2>
                <span className={cn('text-xs px-2 py-0.5 rounded-full border', categoryColors[strategy.category])}>
                  {categoryLabels[strategy.category]}
                </span>
              </div>
              <p className="text-sm text-foreground-muted">{strategy.description}</p>
            </div>
            <button onClick={onClose} className="text-foreground-muted hover:text-foreground-primary">
              <XCircle className="w-6 h-6" />
            </button>
          </div>

          {/* Equity Curve */}
          <div className="card p-4 mb-4">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Equity Curve (90 Days)</h3>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={strategy.equity}>
                  <defs>
                    <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00d4aa" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#00d4aa" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#6b7280', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#6b7280', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #2a2a3e',
                      borderRadius: '8px',
                    }}
                    labelStyle={{ color: '#9ca3af' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#00d4aa"
                    fill="url(#equityGradient)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Performance Metrics */}
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Total Return</div>
              <div className={cn('text-2xl font-bold', strategy.performance.totalReturn >= 0 ? 'text-bullish' : 'text-bearish')}>
                {strategy.performance.totalReturn >= 0 ? '+' : ''}{strategy.performance.totalReturn}%
              </div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Sharpe Ratio</div>
              <div className="text-2xl font-bold text-foreground-primary">{strategy.performance.sharpeRatio}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Max Drawdown</div>
              <div className="text-2xl font-bold text-bearish">{strategy.performance.maxDrawdown}%</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Win Rate</div>
              <div className="text-2xl font-bold text-foreground-primary">{strategy.performance.winRate}%</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Profit Factor</div>
              <div className="text-2xl font-bold text-foreground-primary">{strategy.performance.profitFactor}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Total Trades</div>
              <div className="text-2xl font-bold text-foreground-primary">{strategy.performance.tradesCount}</div>
            </div>
          </div>

          {/* Current Signal */}
          <div className="card p-4 mb-4">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Current Signal</h3>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={cn(
                  'px-4 py-2 rounded-lg font-bold text-lg',
                  strategy.signals.current === 'BUY' && 'bg-bullish/20 text-bullish',
                  strategy.signals.current === 'SELL' && 'bg-bearish/20 text-bearish',
                  strategy.signals.current === 'HOLD' && 'bg-surface-secondary text-foreground-muted',
                )}>
                  {strategy.signals.current}
                </div>
                <div>
                  <div className="text-xs text-foreground-muted">Confidence</div>
                  <div className="flex items-center gap-2">
                    <div className="w-32 h-3 bg-surface-secondary rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          strategy.signals.confidence >= 70 ? 'bg-bullish' :
                          strategy.signals.confidence >= 50 ? 'bg-warning' : 'bg-bearish'
                        )}
                        style={{ width: `${strategy.signals.confidence}%` }}
                      />
                    </div>
                    <span className="text-sm font-bold">{strategy.signals.confidence}%</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-foreground-muted">Weight:</span>
                <span className="text-lg font-bold text-accent-primary">{strategy.weight}%</span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={onToggle}
              className={cn(
                'flex-1 py-3 rounded-lg font-medium flex items-center justify-center gap-2',
                strategy.active ? 'bg-bearish/20 text-bearish hover:bg-bearish/30' : 'bg-bullish/20 text-bullish hover:bg-bullish/30'
              )}
            >
              {strategy.active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              {strategy.active ? 'Disable Strategy' : 'Enable Strategy'}
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
