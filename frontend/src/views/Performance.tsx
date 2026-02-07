/**
 * Performance Center View
 * ========================
 * Comprehensive trading performance analytics with:
 * - Time-weighted return calculations
 * - Rolling returns chart
 * - Drawdown analysis
 * - Win/loss distribution histogram
 * - Trade P&L scatter by holding time
 * - Monthly returns heatmap table
 * Inspired by Bloomberg PORT, FactSet, and Morningstar analytics.
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  BarChart3,
  RefreshCw,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Target,
  Activity,
  Clock,
  Zap,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { formatCurrency, formatPercent } from '@/utils/format'
import { DonutChart } from '@/components/charts/DonutChart'
import { Skeleton } from '@/components/ui/LoadingStates'
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
  CartesianGrid,
  ScatterChart,
  Scatter,
  ZAxis,
  ReferenceLine,
  LineChart,
  Line,
  Legend,
} from 'recharts'

// ─── Types ────────────────────────────────────────────────────────────────────

interface TradeStats {
  totalTrades: number
  winners: number
  losers: number
  winRate: number | null
  totalPnl: number
  avgWin: number | null
  avgLoss: number | null
  profitFactor: number | null
  largestWin: number | null
  largestLoss: number | null
  sharpeRatio: number | null
  sortinoRatio: number | null
  maxDrawdown: number | null
  expectancy: number | null
  avgHoldingTime: number | null
  source: string
  is_real: boolean
}

interface ClosedTrade {
  id: string
  symbol: string
  side: string
  entry_price: number
  exit_price: number
  quantity: number
  pnl: number
  pnl_pct: number
  entry_time: string
  exit_time: string
  strategy?: string
  holding_hours?: number
}

interface MonthlyReturn {
  month: string
  year: number
  return_pct: number
  trades: number
}

const chartTooltipStyle = {
  backgroundColor: '#1a1d20',
  border: '1px solid rgba(255,255,255,0.06)',
  borderRadius: '12px',
  boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function Performance() {
  const [stats, setStats] = useState<TradeStats | null>(null)
  const [trades, setTrades] = useState<ClosedTrade[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [period, setPeriod] = useState('30d')

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const [statsRes, tradesRes] = await Promise.all([
        fetch(`/api/trades/stats?range=${period}`),
        fetch('/api/trades/closed'),
      ])

      const statsData = await statsRes.json()
      const tradesData = await tradesRes.json()

      if (statsData.status === 'unavailable') {
        setStats(null)
      } else {
        setStats({
          totalTrades: statsData.totalTrades ?? statsData.total_trades ?? 0,
          winners: statsData.winners ?? statsData.winning_trades ?? 0,
          losers: statsData.losers ?? statsData.losing_trades ?? 0,
          winRate: statsData.winRate ?? statsData.win_rate ?? null,
          totalPnl: statsData.totalPnl ?? statsData.total_pnl ?? 0,
          avgWin: statsData.avgWin ?? statsData.avg_win ?? null,
          avgLoss: statsData.avgLoss ?? statsData.avg_loss ?? null,
          profitFactor: statsData.profitFactor ?? statsData.profit_factor ?? null,
          largestWin: statsData.largestWin ?? statsData.largest_win ?? null,
          largestLoss: statsData.largestLoss ?? statsData.largest_loss ?? null,
          sharpeRatio: statsData.sharpeRatio ?? statsData.sharpe_ratio ?? null,
          sortinoRatio: statsData.sortinoRatio ?? statsData.sortino_ratio ?? null,
          maxDrawdown: statsData.maxDrawdown ?? statsData.max_drawdown ?? null,
          expectancy: statsData.expectancy ?? null,
          avgHoldingTime: statsData.avgHoldingTime ?? statsData.avg_holding_time ?? null,
          source: statsData.source ?? 'api',
          is_real: statsData.is_real ?? true,
        })
      }

      const rawTrades = Array.isArray(tradesData) ? tradesData : tradesData.trades || []
      setTrades(rawTrades.map((t: any) => ({
        id: t.id || t.trade_id || '',
        symbol: t.symbol || '',
        side: t.side || t.direction || '',
        entry_price: t.entry_price || 0,
        exit_price: t.exit_price || 0,
        quantity: t.quantity || t.qty || 0,
        pnl: t.pnl || 0,
        pnl_pct: t.pnl_pct || t.pnl_percent || 0,
        entry_time: t.entry_time || t.opened_at || '',
        exit_time: t.exit_time || t.closed_at || '',
        strategy: t.strategy || '',
        holding_hours: t.holding_hours || (t.entry_time && t.exit_time
          ? (new Date(t.exit_time).getTime() - new Date(t.entry_time).getTime()) / 3600000
          : null),
      })))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch performance data')
    } finally {
      setIsLoading(false)
    }
  }, [period])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // ─── Derived Data ─────────────────────────────────────────────────────

  const winRate = stats?.winRate ?? 0
  const lossRate = 100 - winRate

  // P&L distribution histogram
  const pnlDistribution = useMemo(() => {
    if (trades.length === 0) return []
    const bucketSize = 50
    const buckets: Record<number, number> = {}
    trades.forEach(t => {
      const bucket = Math.round(t.pnl / bucketSize) * bucketSize
      buckets[bucket] = (buckets[bucket] || 0) + 1
    })
    return Object.entries(buckets)
      .map(([bucket, count]) => ({ bucket: parseFloat(bucket), count }))
      .sort((a, b) => a.bucket - b.bucket)
  }, [trades])

  // Trade P&L scatter by holding time
  const scatterData = useMemo(() => {
    return trades
      .filter(t => t.holding_hours != null && t.holding_hours > 0)
      .map(t => ({
        holdingHours: Math.round(t.holding_hours! * 10) / 10,
        pnl: t.pnl,
        symbol: t.symbol,
        size: Math.abs(t.pnl),
      }))
  }, [trades])

  // Rolling equity curve
  const equityCurve = useMemo(() => {
    if (trades.length === 0) return []
    let equity = 0
    let peak = 0
    return trades
      .sort((a, b) => new Date(a.exit_time).getTime() - new Date(b.exit_time).getTime())
      .map((t, i) => {
        equity += t.pnl
        peak = Math.max(peak, equity)
        const dd = peak > 0 ? ((equity - peak) / peak) * 100 : 0
        return {
          trade: i + 1,
          equity: Math.round(equity * 100) / 100,
          drawdown: Math.round(dd * 100) / 100,
          date: t.exit_time ? new Date(t.exit_time).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : `#${i + 1}`,
        }
      })
  }, [trades])

  // Monthly returns table
  const monthlyReturns = useMemo(() => {
    if (trades.length === 0) return []
    const monthly: Record<string, { pnl: number; trades: number }> = {}
    trades.forEach(t => {
      if (!t.exit_time) return
      const d = new Date(t.exit_time)
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      if (!monthly[key]) monthly[key] = { pnl: 0, trades: 0 }
      monthly[key].pnl += t.pnl
      monthly[key].trades += 1
    })
    return Object.entries(monthly)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, val]) => {
        const [year, month] = key.split('-')
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        return {
          month: months[parseInt(month) - 1],
          year: parseInt(year),
          return_pct: val.pnl,
          trades: val.trades,
        }
      })
  }, [trades])

  // ─── Render ───────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-accent-primary/10">
            <BarChart3 className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">PERFORMANCE CENTER</h1>
            <p className="text-xs text-foreground-muted">Trading performance analytics and metrics</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-background-tertiary rounded-xl p-1">
            {(['7d', '30d', '90d', 'all'] as const).map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
                  period === p ? 'bg-accent-primary text-black' : 'text-foreground-muted hover:text-foreground-primary'
                )}
              >
                {p === '7d' ? '7D' : p === '30d' ? '30D' : p === '90d' ? '90D' : 'All'}
              </button>
            ))}
          </div>
          <button
            onClick={fetchData}
            disabled={isLoading}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-bearish flex-shrink-0" />
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="card p-4"><Skeleton className="h-3 w-16 mb-3" /><Skeleton className="h-6 w-24" /></div>
            ))}
          </div>
          <div className="card p-4"><Skeleton className="h-64 w-full" /></div>
        </div>
      ) : !stats ? (
        <div className="card p-12 text-center text-foreground-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium text-foreground-secondary">No Trading Data Available</p>
          <p className="text-sm mt-2">Performance stats will appear once you execute trades</p>
        </div>
      ) : (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-6 gap-3 stagger">
            <MetricCard
              label="Net P&L"
              value={`${stats.totalPnl >= 0 ? '+' : ''}${formatCurrency(stats.totalPnl)}`}
              color={stats.totalPnl >= 0 ? 'text-bullish' : 'text-bearish'}
              icon={stats.totalPnl >= 0 ? TrendingUp : TrendingDown}
            />
            <MetricCard
              label="Win Rate"
              value={stats.winRate !== null ? `${stats.winRate.toFixed(1)}%` : 'N/A'}
              icon={Target}
            />
            <MetricCard
              label="Profit Factor"
              value={stats.profitFactor !== null ? stats.profitFactor.toFixed(2) : 'N/A'}
              icon={Zap}
            />
            <MetricCard
              label="Sharpe Ratio"
              value={stats.sharpeRatio !== null ? stats.sharpeRatio.toFixed(2) : 'N/A'}
              icon={Activity}
            />
            <MetricCard
              label="Max Drawdown"
              value={stats.maxDrawdown !== null ? `${stats.maxDrawdown.toFixed(1)}%` : 'N/A'}
              color="text-bearish"
              icon={TrendingDown}
            />
            <MetricCard
              label="Total Trades"
              value={stats.totalTrades.toString()}
              icon={BarChart3}
            />
          </div>

          {/* Charts Row 1: Equity + Win Rate */}
          <div className="grid grid-cols-12 gap-4">
            {/* Equity Curve */}
            <div className="col-span-8 card p-4">
              <div className="chart-header">
                <h3 className="chart-title">Equity Curve</h3>
                <span className={cn('text-sm font-bold font-mono', stats.totalPnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                  {stats.totalPnl >= 0 ? '+' : ''}{formatCurrency(stats.totalPnl)}
                </span>
              </div>
              <div className="h-56">
                {equityCurve.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={equityCurve}>
                      <defs>
                        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={stats.totalPnl >= 0 ? '#10b981' : '#ef4444'} stopOpacity={0.2} />
                          <stop offset="95%" stopColor={stats.totalPnl >= 0 ? '#10b981' : '#ef4444'} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                      <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} />
                      <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false}
                        tickFormatter={(v) => `$${v}`} />
                      <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }}
                        formatter={(v: number) => [formatCurrency(v), 'Equity']} />
                      <ReferenceLine y={0} stroke="#71717a" strokeDasharray="3 3" />
                      <Area type="monotone" dataKey="equity" stroke={stats.totalPnl >= 0 ? '#10b981' : '#ef4444'}
                        strokeWidth={2} fill="url(#eqGrad)" dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-foreground-muted text-sm">
                    Execute trades to see equity curve
                  </div>
                )}
              </div>
            </div>

            {/* Win Rate Donut + Key Stats */}
            <div className="col-span-4 card p-4">
              <div className="chart-header">
                <h3 className="chart-title">Win / Loss</h3>
              </div>
              {stats.totalTrades > 0 ? (
                <>
                  <div className="flex items-center justify-center h-36">
                    <DonutChart
                      data={[
                        { name: 'Winning', value: winRate, color: '#10b981' },
                        { name: 'Losing', value: lossRate, color: '#ef4444' },
                      ]}
                      centerLabel={`${winRate.toFixed(0)}%`}
                      centerSubLabel="Win Rate"
                      size={120}
                    />
                  </div>
                  <div className="space-y-2 mt-2">
                    <StatRow label="Winners" value={stats.winners.toString()} color="text-bullish" />
                    <StatRow label="Losers" value={stats.losers.toString()} color="text-bearish" />
                    <StatRow label="Avg Win" value={stats.avgWin !== null ? formatCurrency(stats.avgWin) : 'N/A'} color="text-bullish" />
                    <StatRow label="Avg Loss" value={stats.avgLoss !== null ? formatCurrency(stats.avgLoss) : 'N/A'} color="text-bearish" />
                    <StatRow label="Largest Win" value={stats.largestWin !== null ? formatCurrency(stats.largestWin) : 'N/A'} color="text-bullish" />
                    <StatRow label="Largest Loss" value={stats.largestLoss !== null ? formatCurrency(stats.largestLoss) : 'N/A'} color="text-bearish" />
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-48 text-foreground-muted text-sm">
                  No trades yet
                </div>
              )}
            </div>
          </div>

          {/* Charts Row 2: Drawdown + P&L Distribution */}
          <div className="grid grid-cols-12 gap-4">
            {/* Drawdown Chart */}
            <div className="col-span-6 card p-4">
              <div className="chart-header">
                <h3 className="chart-title">Drawdown</h3>
                {stats.maxDrawdown !== null && (
                  <span className="text-sm font-bold font-mono text-bearish">
                    Max: {stats.maxDrawdown.toFixed(2)}%
                  </span>
                )}
              </div>
              <div className="h-48">
                {equityCurve.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={equityCurve}>
                      <defs>
                        <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#ef4444" stopOpacity={0.05} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                      <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 9 }} tickLine={false} axisLine={false} />
                      <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false}
                        tickFormatter={(v) => `${v}%`} domain={['auto', 0]} />
                      <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }}
                        formatter={(v: number) => [`${v.toFixed(2)}%`, 'Drawdown']} />
                      <ReferenceLine y={0} stroke="#71717a" />
                      <Area type="monotone" dataKey="drawdown" stroke="#ef4444" strokeWidth={2} fill="url(#ddGrad)" dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-foreground-muted text-sm">
                    No data
                  </div>
                )}
              </div>
            </div>

            {/* P&L Distribution Histogram */}
            <div className="col-span-6 card p-4">
              <div className="chart-header">
                <h3 className="chart-title">P&L Distribution</h3>
              </div>
              <div className="h-48">
                {pnlDistribution.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={pnlDistribution}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                      <XAxis dataKey="bucket" tick={{ fill: '#71717a', fontSize: 9 }} tickLine={false} axisLine={false}
                        tickFormatter={(v) => `$${v}`} />
                      <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} />
                      <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }}
                        formatter={(v: number, name: string) => [v, 'Count']}
                        labelFormatter={(v) => `$${v} P&L`} />
                      <ReferenceLine x={0} stroke="#71717a" />
                      <Bar dataKey="count" radius={[3, 3, 0, 0]} name="Trades">
                        {pnlDistribution.map((entry, i) => (
                          <Cell key={i} fill={entry.bucket >= 0 ? '#10b981' : '#ef4444'} fillOpacity={0.7} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-foreground-muted text-sm">
                    No trade data for distribution
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Charts Row 3: Scatter + Monthly */}
          <div className="grid grid-cols-12 gap-4">
            {/* Trade P&L Scatter by Holding Time */}
            <div className="col-span-6 card p-4">
              <div className="chart-header">
                <h3 className="chart-title">P&L vs Holding Time</h3>
              </div>
              <div className="h-48">
                {scatterData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                      <XAxis type="number" dataKey="holdingHours" name="Hours"
                        tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false}
                        label={{ value: 'Holding Time (hrs)', position: 'bottom', fill: '#71717a', fontSize: 10, offset: -5 }} />
                      <YAxis type="number" dataKey="pnl" name="P&L"
                        tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false}
                        tickFormatter={(v) => `$${v}`} />
                      <ZAxis type="number" dataKey="size" range={[20, 200]} />
                      <Tooltip
                        contentStyle={chartTooltipStyle}
                        formatter={(v: number, name: string) => {
                          if (name === 'P&L') return [formatCurrency(v), 'P&L']
                          if (name === 'Hours') return [`${v}h`, 'Hold Time']
                          return [v, name]
                        }}
                      />
                      <ReferenceLine y={0} stroke="#71717a" strokeDasharray="3 3" />
                      <Scatter data={scatterData.filter(d => d.pnl >= 0)} fill="#10b981" fillOpacity={0.6} name="Winners" />
                      <Scatter data={scatterData.filter(d => d.pnl < 0)} fill="#ef4444" fillOpacity={0.6} name="Losers" />
                    </ScatterChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-foreground-muted text-sm">
                    No holding time data available
                  </div>
                )}
              </div>
            </div>

            {/* Monthly Returns Table */}
            <div className="col-span-6 card p-4">
              <div className="chart-header">
                <h3 className="chart-title">Monthly Returns</h3>
              </div>
              {monthlyReturns.length > 0 ? (
                <div className="grid grid-cols-4 gap-2 mt-2">
                  {monthlyReturns.map(m => (
                    <div key={`${m.month}-${m.year}`} className={cn(
                      'p-2.5 rounded-xl text-center transition-colors',
                      m.return_pct >= 0 ? 'bg-bullish/10 hover:bg-bullish/15' : 'bg-bearish/10 hover:bg-bearish/15'
                    )}>
                      <div className="text-[10px] text-foreground-muted mb-0.5">{m.month} {m.year}</div>
                      <div className={cn('text-sm font-bold font-mono', m.return_pct >= 0 ? 'text-bullish' : 'text-bearish')}>
                        {m.return_pct >= 0 ? '+' : ''}{formatCurrency(m.return_pct)}
                      </div>
                      <div className="text-[10px] text-foreground-muted mt-0.5">{m.trades} trades</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-center h-40 text-foreground-muted text-sm">
                  No monthly data available
                </div>
              )}
            </div>
          </div>

          {/* Recent Trades Table */}
          <div className="card overflow-hidden">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <h3 className="text-sm font-semibold text-foreground-primary">RECENT TRADES</h3>
              <span className="text-xs text-foreground-muted">{trades.length} closed trades</span>
            </div>
            {trades.length === 0 ? (
              <div className="p-8 text-center text-foreground-muted">
                <p className="text-sm">No closed trades to display</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table text-xs">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Side</th>
                      <th className="text-right">Qty</th>
                      <th className="text-right">Entry</th>
                      <th className="text-right">Exit</th>
                      <th className="text-right">P&L</th>
                      <th className="text-right">P&L %</th>
                      <th className="text-right">Hold Time</th>
                      <th>Strategy</th>
                      <th className="text-right">Exit Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.slice(0, 25).map((trade) => (
                      <tr key={trade.id}>
                        <td>
                          <span className="font-semibold">{trade.symbol}</span>
                        </td>
                        <td>
                          <span className={cn(
                            'px-1.5 py-0.5 rounded text-[10px] font-medium',
                            trade.side === 'LONG' || trade.side === 'BUY'
                              ? 'bg-bullish/15 text-bullish'
                              : 'bg-bearish/15 text-bearish'
                          )}>
                            {trade.side}
                          </span>
                        </td>
                        <td className="text-right font-mono">{trade.quantity}</td>
                        <td className="text-right font-mono">${trade.entry_price.toFixed(2)}</td>
                        <td className="text-right font-mono">${trade.exit_price.toFixed(2)}</td>
                        <td className={cn('text-right font-mono font-medium', trade.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                          {trade.pnl >= 0 ? '+' : ''}{formatCurrency(trade.pnl)}
                        </td>
                        <td className={cn('text-right font-mono', trade.pnl_pct >= 0 ? 'text-bullish' : 'text-bearish')}>
                          {trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct.toFixed(2)}%
                        </td>
                        <td className="text-right font-mono text-foreground-muted">
                          {trade.holding_hours ? `${trade.holding_hours.toFixed(1)}h` : '-'}
                        </td>
                        <td className="text-foreground-muted">{trade.strategy || '-'}</td>
                        <td className="text-right text-foreground-muted">
                          {trade.exit_time ? new Date(trade.exit_time).toLocaleString() : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ─── Subcomponents ────────────────────────────────────────────────────────────

function MetricCard({ label, value, color, icon: Icon }: {
  label: string; value: string; color?: string; icon: any
}) {
  return (
    <div className="card p-3">
      <div className="flex items-center gap-2 text-foreground-muted mb-1">
        <Icon className="w-4 h-4" />
        <span className="text-xs">{label}</span>
      </div>
      <div className={cn('text-lg font-bold font-mono', color || 'text-foreground-primary')}>
        {value}
      </div>
    </div>
  )
}

function StatRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between items-center text-xs">
      <span className="text-foreground-muted">{label}</span>
      <span className={cn('font-mono font-medium', color || 'text-foreground-primary')}>
        {value}
      </span>
    </div>
  )
}
