/**
 * Backtest Visualization View
 * Full-featured backtest runner and visualization dashboard
 *
 * Features:
 * - Interactive equity curve chart (Recharts AreaChart)
 * - Trade markers on chart (entry/exit points)
 * - Drawdown chart
 * - Monthly/yearly returns heatmap
 * - Performance metrics sidebar (Sharpe, Sortino, Calmar, max DD, win rate, profit factor)
 * - Trade log table
 * - API: /api/backtest/run
 */

import { useState, useCallback, useMemo } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, ComposedChart,
  Brush,
} from 'recharts'
import {
  Play, Settings, TrendingUp, BarChart3, AlertCircle,
  Loader2, DollarSign, ChevronDown, ChevronUp,
  ArrowUpRight, ArrowDownRight,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { formatCurrency, formatPercent } from '@/utils/format'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface BacktestPerf {
  total_return: number
  annualized_return: number
  sharpe_ratio: number
  sortino_ratio: number
  max_drawdown: number
  calmar_ratio: number
  volatility: number
}

interface BacktestTrades {
  total: number
  winning: number
  losing: number
  win_rate: number
  avg_win: number
  avg_loss: number
  profit_factor: number
  avg_holding_period: number
}

interface BacktestRisk {
  var_95: number
  cvar_95: number
  beta: number
  alpha: number
}

interface EquityPoint { date: string; equity: number }
interface DrawdownPoint { date: string; drawdown: number }
interface MonthlyReturn { month: string; return: number }
interface TradeLogEntry {
  date: string
  symbol: string
  side: 'buy' | 'sell'
  shares: number
  price: number
  commission: number
  value: number
}

interface BacktestResult {
  job_id?: string
  performance: BacktestPerf
  trades: BacktestTrades
  risk: BacktestRisk
  curves: {
    equity: EquityPoint[]
    drawdown: DrawdownPoint[]
    monthly_returns: MonthlyReturn[]
  }
  trade_log: TradeLogEntry[]
  execution?: { time_seconds: number; data_points: number }
  warnings?: string[]
}

type StrategyType = 'momentum' | 'mean_reversion' | 'trend_following' | 'rsi_reversal'
type TabType = 'equity' | 'drawdown' | 'heatmap' | 'trades'

const STRATEGY_OPTIONS: { value: StrategyType; label: string }[] = [
  { value: 'momentum', label: 'Momentum' },
  { value: 'mean_reversion', label: 'Mean Reversion' },
  { value: 'trend_following', label: 'Trend Following' },
  { value: 'rsi_reversal', label: 'RSI Reversal' },
]

const PERIOD_OPTIONS = ['3M', '6M', '1Y', '2Y', '5Y']

// ---------------------------------------------------------------------------
// Helper: produce monthly heatmap data from monthly returns
// ---------------------------------------------------------------------------
function buildHeatmap(monthlyReturns: MonthlyReturn[]): { year: string; months: (number | null)[] }[] {
  const byYear: Record<string, (number | null)[]> = {}
  for (const mr of monthlyReturns) {
    const [yr, mo] = mr.month.split('-')
    if (!byYear[yr]) byYear[yr] = Array(12).fill(null)
    byYear[yr][parseInt(mo, 10) - 1] = mr.return
  }
  return Object.entries(byYear)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([year, months]) => ({ year, months }))
}

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function heatColor(v: number | null): string {
  if (v === null) return 'bg-background-tertiary'
  if (v >= 0.05) return 'bg-bullish/80'
  if (v >= 0.02) return 'bg-bullish/50'
  if (v >= 0) return 'bg-bullish/20'
  if (v >= -0.02) return 'bg-bearish/20'
  if (v >= -0.05) return 'bg-bearish/50'
  return 'bg-bearish/80'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function BacktestViz() {
  // Form state
  const [ticker, setTicker] = useState('AAPL')
  const [strategy, setStrategy] = useState<StrategyType>('momentum')
  const [period, setPeriod] = useState('1Y')
  const [capital, setCapital] = useState(100000)
  const [showSettings, setShowSettings] = useState(true)

  // Execution state
  const [isRunning, setIsRunning] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // UI state
  const [activeTab, setActiveTab] = useState<TabType>('equity')
  const [tradeSort, setTradeSort] = useState<'date' | 'pnl'>('date')
  const [tradeSortAsc, setTradeSortAsc] = useState(false)

  // ----- Run backtest -----
  const runBacktest = useCallback(async () => {
    setIsRunning(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetch('/api/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: ticker.toUpperCase(),
          strategy,
          period,
          initial_capital: capital,
          params: {},
        }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Backtest failed (${response.status})`)
      }

      const data = await response.json()

      // Normalize: the API may return flat or nested structures
      const normalized: BacktestResult = {
        performance: data.performance ?? {
          total_return: data.total_return ?? 0,
          annualized_return: data.annualized_return ?? 0,
          sharpe_ratio: data.sharpe_ratio ?? 0,
          sortino_ratio: data.sortino_ratio ?? 0,
          max_drawdown: data.max_drawdown ?? 0,
          calmar_ratio: data.calmar_ratio ?? 0,
          volatility: data.volatility ?? 0,
        },
        trades: data.trades ?? {
          total: data.trade_count ?? 0,
          winning: data.winning_trades ?? 0,
          losing: data.losing_trades ?? 0,
          win_rate: data.win_rate ?? 0,
          avg_win: data.avg_win ?? 0,
          avg_loss: data.avg_loss ?? 0,
          profit_factor: data.profit_factor ?? 0,
          avg_holding_period: data.avg_holding_period ?? 0,
        },
        risk: data.risk ?? {
          var_95: data.var_95 ?? 0,
          cvar_95: data.cvar_95 ?? 0,
          beta: data.beta ?? 0,
          alpha: data.alpha ?? 0,
        },
        curves: data.curves ?? {
          equity: data.equity_curve ?? [],
          drawdown: data.drawdown_curve ?? [],
          monthly_returns: data.monthly_returns ?? [],
        },
        trade_log: data.trade_log ?? data.trades_list ?? [],
        execution: data.execution,
        warnings: data.warnings,
      }

      setResult(normalized)
      setShowSettings(false)
    } catch (e: any) {
      setError(e.message || 'Backtest failed')
    } finally {
      setIsRunning(false)
    }
  }, [ticker, strategy, period, capital])

  // ----- Derived data -----
  const equityData = useMemo(() => {
    if (!result?.curves.equity?.length) return []
    const first = result.curves.equity[0].equity
    return result.curves.equity.map((p, i) => ({
      date: p.date,
      equity: p.equity,
      returnPct: ((p.equity - first) / first) * 100,
      drawdown: result.curves.drawdown[i]?.drawdown ?? 0,
    }))
  }, [result])

  const drawdownData = useMemo(() => {
    if (!result?.curves.drawdown?.length) return []
    return result.curves.drawdown.map((p) => ({
      date: p.date,
      drawdown: -(p.drawdown * 100),
    }))
  }, [result])

  const heatmapData = useMemo(() => {
    if (!result?.curves.monthly_returns?.length) return []
    return buildHeatmap(result.curves.monthly_returns)
  }, [result])

  const sortedTrades = useMemo(() => {
    if (!result?.trade_log?.length) return []
    const sorted = [...result.trade_log]
    if (tradeSort === 'date') sorted.sort((a, b) => a.date.localeCompare(b.date))
    else sorted.sort((a, b) => a.value - b.value)
    if (!tradeSortAsc) sorted.reverse()
    return sorted
  }, [result, tradeSort, tradeSortAsc])

  const tabs: { id: TabType; label: string }[] = [
    { id: 'equity', label: 'Equity Curve' },
    { id: 'drawdown', label: 'Drawdown' },
    { id: 'heatmap', label: 'Returns Heatmap' },
    { id: 'trades', label: 'Trade Log' },
  ]

  // ----- Render -----
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <TrendingUp className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">BACKTEST LAB</h1>
            <p className="text-xs text-foreground-muted">Strategy backtesting with real-time visualization</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={cn(
              'p-2 rounded-lg transition-colors',
              showSettings ? 'bg-accent-primary/20 text-accent-primary' : 'bg-background-tertiary text-foreground-muted hover:text-foreground-primary'
            )}
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* ---- Settings Panel ---- */}
        {showSettings && (
          <div className="col-span-12 lg:col-span-3">
            <div className="card p-4 space-y-4">
              <h2 className="text-sm font-bold text-foreground-primary flex items-center gap-2">
                <Settings className="w-4 h-4 text-accent-primary" />
                Configuration
              </h2>

              {/* Ticker */}
              <div>
                <label className="text-[10px] font-bold text-foreground-muted block mb-1">TICKER</label>
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  className="w-full px-3 py-2 bg-background-tertiary border border-border rounded-lg text-sm text-foreground-primary font-mono focus:outline-none focus:border-accent-primary"
                  placeholder="AAPL"
                />
              </div>

              {/* Strategy */}
              <div>
                <label className="text-[10px] font-bold text-foreground-muted block mb-1">STRATEGY</label>
                <select
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value as StrategyType)}
                  className="w-full px-3 py-2 bg-background-tertiary border border-border rounded-lg text-sm text-foreground-primary focus:outline-none focus:border-accent-primary"
                >
                  {STRATEGY_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>

              {/* Period */}
              <div>
                <label className="text-[10px] font-bold text-foreground-muted block mb-1">PERIOD</label>
                <div className="flex gap-1">
                  {PERIOD_OPTIONS.map((p) => (
                    <button
                      key={p}
                      onClick={() => setPeriod(p)}
                      className={cn(
                        'flex-1 py-1.5 text-[10px] font-bold rounded transition-colors',
                        period === p
                          ? 'bg-accent-primary/20 text-accent-primary'
                          : 'bg-background-tertiary text-foreground-muted hover:text-foreground-primary'
                      )}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>

              {/* Capital */}
              <div>
                <label className="text-[10px] font-bold text-foreground-muted block mb-1">
                  <DollarSign className="w-3 h-3 inline mr-0.5" />
                  INITIAL CAPITAL
                </label>
                <input
                  type="number"
                  value={capital}
                  onChange={(e) => setCapital(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-background-tertiary border border-border rounded-lg text-sm text-foreground-primary font-mono focus:outline-none focus:border-accent-primary"
                />
              </div>

              {/* Error */}
              {error && (
                <div className="p-3 bg-bearish/10 border border-bearish/30 rounded-lg flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-bearish flex-shrink-0 mt-0.5" />
                  <span className="text-xs text-bearish">{error}</span>
                </div>
              )}

              {/* Run Button */}
              <button
                onClick={runBacktest}
                disabled={isRunning || !ticker.trim()}
                className={cn(
                  'w-full py-2.5 rounded-lg font-bold text-xs flex items-center justify-center gap-2 transition-colors',
                  isRunning
                    ? 'bg-background-tertiary text-foreground-muted cursor-not-allowed'
                    : 'bg-accent-primary/20 text-accent-primary hover:bg-accent-primary/30'
                )}
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    RUN BACKTEST
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ---- Results Panel ---- */}
        <div className={showSettings ? 'col-span-12 lg:col-span-9' : 'col-span-12'}>
          {result ? (
            <div className="space-y-4">
              {/* Performance Metrics Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3">
                <MetricTile label="Total Return" value={formatPercent(result.performance.total_return * 100, 2)} positive={result.performance.total_return >= 0} />
                <MetricTile label="Ann. Return" value={formatPercent(result.performance.annualized_return * 100, 2)} positive={result.performance.annualized_return >= 0} />
                <MetricTile label="Sharpe" value={result.performance.sharpe_ratio.toFixed(2)} positive={result.performance.sharpe_ratio > 0} />
                <MetricTile label="Sortino" value={result.performance.sortino_ratio.toFixed(2)} positive={result.performance.sortino_ratio > 0} />
                <MetricTile label="Calmar" value={result.performance.calmar_ratio.toFixed(2)} positive={result.performance.calmar_ratio > 0} />
                <MetricTile label="Max DD" value={formatPercent(result.performance.max_drawdown * 100, 2)} positive={false} />
                <MetricTile label="Win Rate" value={formatPercent(result.trades.win_rate * 100, 1)} positive={result.trades.win_rate > 0.5} />
                <MetricTile label="Profit Factor" value={result.trades.profit_factor.toFixed(2)} positive={result.trades.profit_factor > 1} />
              </div>

              {/* Secondary Metrics */}
              <div className="grid grid-cols-12 gap-4">
                {/* Performance Metrics Sidebar */}
                <div className="col-span-12 xl:col-span-3">
                  <div className="card p-4 space-y-3">
                    <h3 className="text-[10px] font-bold text-foreground-muted">PERFORMANCE DETAILS</h3>
                    <MetricRow label="Volatility" value={formatPercent(result.performance.volatility * 100, 2)} />
                    <MetricRow label="VaR (95%)" value={formatPercent(result.risk.var_95 * 100, 2)} negative />
                    <MetricRow label="CVaR (95%)" value={formatPercent(result.risk.cvar_95 * 100, 2)} negative />
                    <MetricRow label="Beta" value={result.risk.beta.toFixed(3)} />
                    <MetricRow label="Alpha" value={formatPercent(result.risk.alpha * 100, 2)} positive={result.risk.alpha > 0} />
                    <div className="border-t border-border pt-2" />
                    <h3 className="text-[10px] font-bold text-foreground-muted">TRADE STATS</h3>
                    <MetricRow label="Total Trades" value={result.trades.total.toString()} />
                    <MetricRow label="Winners" value={result.trades.winning.toString()} positive />
                    <MetricRow label="Losers" value={result.trades.losing.toString()} negative />
                    <MetricRow label="Avg Win" value={formatCurrency(result.trades.avg_win)} positive />
                    <MetricRow label="Avg Loss" value={formatCurrency(Math.abs(result.trades.avg_loss))} negative />
                    <MetricRow label="Avg Holding" value={`${result.trades.avg_holding_period.toFixed(1)}d`} />
                    {result.execution && (
                      <>
                        <div className="border-t border-border pt-2" />
                        <MetricRow label="Exec Time" value={`${result.execution.time_seconds.toFixed(1)}s`} />
                        <MetricRow label="Data Points" value={result.execution.data_points.toLocaleString()} />
                      </>
                    )}
                  </div>
                </div>

                {/* Chart Area */}
                <div className="col-span-12 xl:col-span-9">
                  {/* Tab Navigation */}
                  <div className="flex gap-1 mb-3">
                    {tabs.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => setActiveTab(t.id)}
                        className={cn(
                          'px-3 py-1.5 text-xs font-medium rounded transition-colors',
                          activeTab === t.id
                            ? 'bg-accent-primary/20 text-accent-primary'
                            : 'text-foreground-muted hover:text-foreground-primary'
                        )}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>

                  {/* Charts */}
                  {activeTab === 'equity' && (
                    <div className="card p-4">
                      <h3 className="text-xs font-bold text-foreground-muted mb-3">EQUITY CURVE</h3>
                      {equityData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={380}>
                          <ComposedChart data={equityData}>
                            <defs>
                              <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#00d4aa" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#00d4aa" stopOpacity={0} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                            <XAxis
                              dataKey="date"
                              tick={{ fill: '#6b7280', fontSize: 10 }}
                              tickFormatter={(d) => {
                                const dt = new Date(d)
                                return `${dt.toLocaleDateString('en-US', { month: 'short' })} '${dt.getFullYear().toString().slice(2)}`
                              }}
                              minTickGap={40}
                            />
                            <YAxis
                              yAxisId="eq"
                              tick={{ fill: '#6b7280', fontSize: 10 }}
                              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
                              width={60}
                            />
                            <Tooltip
                              contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                              labelStyle={{ color: '#9ca3af' }}
                              formatter={(v: number, name: string) => {
                                if (name === 'equity') return [`$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 'Equity']
                                return [v, name]
                              }}
                            />
                            <Area
                              yAxisId="eq"
                              type="monotone"
                              dataKey="equity"
                              stroke="#00d4aa"
                              strokeWidth={2}
                              fill="url(#eqGrad)"
                              dot={false}
                            />
                            <ReferenceLine yAxisId="eq" y={capital} stroke="rgba(255,255,255,0.15)" strokeDasharray="5 5" />
                            <Brush dataKey="date" height={24} stroke="rgba(255,255,255,0.1)" fill="#0d1117" travellerWidth={8} />
                          </ComposedChart>
                        </ResponsiveContainer>
                      ) : (
                        <EmptyChart />
                      )}
                    </div>
                  )}

                  {activeTab === 'drawdown' && (
                    <div className="card p-4">
                      <h3 className="text-xs font-bold text-foreground-muted mb-3">UNDERWATER CHART (DRAWDOWN)</h3>
                      {drawdownData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={380}>
                          <AreaChart data={drawdownData}>
                            <defs>
                              <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#ff5252" stopOpacity={0.4} />
                                <stop offset="95%" stopColor="#ff5252" stopOpacity={0.05} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                            <XAxis
                              dataKey="date"
                              tick={{ fill: '#6b7280', fontSize: 10 }}
                              tickFormatter={(d) => new Date(d).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })}
                              minTickGap={40}
                            />
                            <YAxis
                              tick={{ fill: '#6b7280', fontSize: 10 }}
                              tickFormatter={(v) => `${v.toFixed(0)}%`}
                              domain={['dataMin', 0]}
                              width={50}
                            />
                            <Tooltip
                              contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                              labelStyle={{ color: '#9ca3af' }}
                              formatter={(v: number) => [`${v.toFixed(2)}%`, 'Drawdown']}
                            />
                            <Area
                              type="monotone"
                              dataKey="drawdown"
                              stroke="#ff5252"
                              strokeWidth={1.5}
                              fill="url(#ddGrad)"
                              dot={false}
                            />
                            <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" />
                          </AreaChart>
                        </ResponsiveContainer>
                      ) : (
                        <EmptyChart />
                      )}
                    </div>
                  )}

                  {activeTab === 'heatmap' && (
                    <div className="card p-4">
                      <h3 className="text-xs font-bold text-foreground-muted mb-3">MONTHLY RETURNS HEATMAP</h3>
                      {heatmapData.length > 0 ? (
                        <div className="overflow-x-auto">
                          <table className="w-full min-w-[700px]">
                            <thead>
                              <tr>
                                <th className="p-2 text-[10px] font-bold text-foreground-muted text-left w-16">Year</th>
                                {MONTH_LABELS.map((m) => (
                                  <th key={m} className="p-1.5 text-[10px] font-bold text-foreground-muted text-center">{m}</th>
                                ))}
                                <th className="p-2 text-[10px] font-bold text-foreground-muted text-center">Total</th>
                              </tr>
                            </thead>
                            <tbody>
                              {heatmapData.map((row) => {
                                const yearTotal = row.months.reduce((sum, v) => sum + (v ?? 0), 0)
                                return (
                                  <tr key={row.year}>
                                    <td className="p-2 text-xs font-bold text-foreground-secondary font-mono">{row.year}</td>
                                    {row.months.map((v, i) => (
                                      <td key={i} className="p-1">
                                        <div
                                          className={cn(
                                            'rounded px-1.5 py-1.5 text-center text-[10px] font-mono font-bold',
                                            heatColor(v),
                                            v !== null ? 'text-white' : 'text-foreground-muted'
                                          )}
                                        >
                                          {v !== null ? `${(v * 100).toFixed(1)}%` : '-'}
                                        </div>
                                      </td>
                                    ))}
                                    <td className="p-1">
                                      <div
                                        className={cn(
                                          'rounded px-1.5 py-1.5 text-center text-[10px] font-mono font-bold',
                                          yearTotal >= 0 ? 'bg-bullish/30 text-bullish' : 'bg-bearish/30 text-bearish'
                                        )}
                                      >
                                        {(yearTotal * 100).toFixed(1)}%
                                      </div>
                                    </td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="text-center text-foreground-muted py-12">
                          <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                          <p className="text-sm">No monthly return data available</p>
                        </div>
                      )}
                    </div>
                  )}

                  {activeTab === 'trades' && (
                    <div className="card p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-xs font-bold text-foreground-muted">TRADE LOG ({result.trade_log.length} trades)</h3>
                        <div className="flex gap-1">
                          <button
                            onClick={() => { setTradeSort('date'); setTradeSortAsc(!tradeSortAsc) }}
                            className={cn('px-2 py-1 text-[10px] rounded', tradeSort === 'date' ? 'bg-accent-primary/20 text-accent-primary' : 'text-foreground-muted')}
                          >
                            Date {tradeSort === 'date' && (tradeSortAsc ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />)}
                          </button>
                          <button
                            onClick={() => { setTradeSort('pnl'); setTradeSortAsc(!tradeSortAsc) }}
                            className={cn('px-2 py-1 text-[10px] rounded', tradeSort === 'pnl' ? 'bg-accent-primary/20 text-accent-primary' : 'text-foreground-muted')}
                          >
                            P&L {tradeSort === 'pnl' && (tradeSortAsc ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />)}
                          </button>
                        </div>
                      </div>
                      {sortedTrades.length > 0 ? (
                        <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                          <table className="w-full text-xs">
                            <thead className="sticky top-0 bg-background-secondary">
                              <tr className="text-foreground-muted border-b border-border">
                                <th className="text-left py-2 pr-3">Date</th>
                                <th className="text-left py-2 pr-3">Symbol</th>
                                <th className="text-left py-2 pr-3">Side</th>
                                <th className="text-right py-2 pr-3">Shares</th>
                                <th className="text-right py-2 pr-3">Price</th>
                                <th className="text-right py-2 pr-3">Value</th>
                                <th className="text-right py-2">Commission</th>
                              </tr>
                            </thead>
                            <tbody>
                              {sortedTrades.map((t, i) => (
                                <tr key={i} className="border-b border-border/30 hover:bg-background-tertiary/50 transition-colors">
                                  <td className="py-1.5 pr-3 font-mono text-foreground-secondary">{t.date}</td>
                                  <td className="py-1.5 pr-3 font-bold text-accent-primary">{t.symbol}</td>
                                  <td className="py-1.5 pr-3">
                                    <span className={cn(
                                      'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold',
                                      t.side === 'buy' ? 'bg-bullish/15 text-bullish' : 'bg-bearish/15 text-bearish'
                                    )}>
                                      {t.side === 'buy' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                                      {t.side.toUpperCase()}
                                    </span>
                                  </td>
                                  <td className="py-1.5 pr-3 text-right font-mono text-foreground-secondary">{t.shares}</td>
                                  <td className="py-1.5 pr-3 text-right font-mono text-foreground-secondary">${t.price.toFixed(2)}</td>
                                  <td className={cn('py-1.5 pr-3 text-right font-mono font-bold', t.value >= 0 ? 'text-bullish' : 'text-bearish')}>
                                    ${Math.abs(t.value).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                  </td>
                                  <td className="py-1.5 text-right font-mono text-foreground-muted">${t.commission.toFixed(2)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="text-center text-foreground-muted py-12">
                          <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                          <p className="text-sm">No trade log available</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Warnings */}
              {result.warnings && result.warnings.length > 0 && (
                <div className="card p-3 bg-warning/10 border border-warning/30">
                  <p className="text-[10px] font-bold text-warning mb-1">WARNINGS</p>
                  {result.warnings.map((w, i) => (
                    <p key={i} className="text-xs text-foreground-muted">{w}</p>
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* Empty State */
            <div className="card p-12 text-center">
              <div className="w-16 h-16 bg-background-tertiary rounded-full flex items-center justify-center mx-auto mb-4">
                <TrendingUp className="w-8 h-8 text-foreground-muted" />
              </div>
              <h3 className="text-lg font-bold text-foreground-primary mb-2">No Backtest Results</h3>
              <p className="text-sm text-foreground-muted mb-6 max-w-md mx-auto">
                Configure your strategy parameters and run a backtest to see performance analysis, equity curves, drawdown charts, and detailed trade logs.
              </p>
              <button
                onClick={runBacktest}
                disabled={isRunning || !ticker.trim()}
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-accent-primary/20 text-accent-primary rounded-lg font-bold text-xs hover:bg-accent-primary/30 transition-colors"
              >
                <Play className="w-4 h-4" />
                RUN BACKTEST
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function MetricTile({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="card p-3">
      <div className="text-[10px] font-bold text-foreground-muted uppercase mb-1">{label}</div>
      <div className={cn(
        'text-base font-bold font-mono',
        positive === undefined ? 'text-foreground-primary' : positive ? 'text-bullish' : 'text-bearish'
      )}>
        {value}
      </div>
    </div>
  )
}

function MetricRow({ label, value, positive, negative }: { label: string; value: string; positive?: boolean; negative?: boolean }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-xs text-foreground-muted">{label}</span>
      <span className={cn(
        'text-xs font-mono font-bold',
        positive ? 'text-bullish' : negative ? 'text-bearish' : 'text-foreground-secondary'
      )}>
        {value}
      </span>
    </div>
  )
}

function EmptyChart() {
  return (
    <div className="flex items-center justify-center h-[380px] text-foreground-muted">
      <div className="text-center">
        <BarChart3 className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No chart data available</p>
      </div>
    </div>
  )
}

export default BacktestViz
