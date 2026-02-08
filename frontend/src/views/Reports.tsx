/**
 * Performance Reports View
 * =========================
 * Institutional-grade report generation with P&L breakdown,
 * drawdown analysis, risk metrics, strategy attribution,
 * and export capabilities (PDF/CSV).
 * Inspired by Bloomberg, FactSet, and Morningstar reporting.
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  ClipboardList,
  Download,
  FileText,
  Calendar,
  TrendingUp,
  TrendingDown,
  BarChart3,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  PieChart,
  Activity,
  Shield,
  Target,
  Layers,
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
  CartesianGrid,
  LineChart,
  Line,
  ReferenceLine,
  ComposedChart,
} from 'recharts'
import { formatCurrency, formatPercent } from '@/utils/format'
import { Skeleton } from '@/components/ui/LoadingStates'
import { DonutChart } from '@/components/charts/DonutChart'

// ─── Types ────────────────────────────────────────────────────────────────────

interface ReportSummary {
  totalPnl: number
  totalTrades: number
  winRate: number
  profitFactor: number
  sharpeRatio: number
  maxDrawdown: number
  avgWin: number
  avgLoss: number
  avgHoldTime: number
  largestWin: number
  largestLoss: number
  expectancy: number
  sortinoRatio: number
  calmarRatio: number
}

interface DailyPnl {
  date: string
  pnl: number
  cumulative: number
}

interface DrawdownPoint {
  date: string
  drawdown: number
  equity: number
  peak: number
}

interface StrategyBreakdown {
  name: string
  pnl: number
  trades: number
  winRate: number
  profitFactor: number
  color: string
}

interface MonthlyReturn {
  month: string
  year: number
  return_pct: number
}

type DateRange = '7d' | '30d' | '90d' | '1y' | 'all'
type ReportTab = 'overview' | 'drawdown' | 'risk' | 'attribution' | 'monthly'

const STRATEGY_COLORS = ['#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']

const chartTooltipStyle = {
  backgroundColor: '#1a1d20',
  border: '1px solid rgba(255,255,255,0.06)',
  borderRadius: '12px',
  boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function Reports() {
  const [dateRange, setDateRange] = useState<DateRange>('30d')
  const [activeTab, setActiveTab] = useState<ReportTab>('overview')
  const [summary, setSummary] = useState<ReportSummary | null>(null)
  const [dailyPnl, setDailyPnl] = useState<DailyPnl[]>([])
  const [drawdowns, setDrawdowns] = useState<DrawdownPoint[]>([])
  const [strategies, setStrategies] = useState<StrategyBreakdown[]>([])
  const [monthlyReturns, setMonthlyReturns] = useState<MonthlyReturn[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ─── Fetch Report Data ────────────────────────────────────────────────

  const fetchReport = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Fetch summary stats and trade data in parallel
      const [summaryRes, statsRes] = await Promise.all([
        fetch(`/api/reports/summary?range=${dateRange}`),
        fetch(`/api/trades/stats?range=${dateRange}`),
      ])

      // Process summary
      if (summaryRes.ok) {
        const data = await summaryRes.json()
        if (data && data.summary) {
          setSummary({
            totalPnl: data.summary.totalPnl ?? data.summary.total_pnl ?? 0,
            totalTrades: data.summary.totalTrades ?? data.summary.total_trades ?? 0,
            winRate: data.summary.winRate ?? data.summary.win_rate ?? 0,
            profitFactor: data.summary.profitFactor ?? data.summary.profit_factor ?? 0,
            sharpeRatio: data.summary.sharpeRatio ?? data.summary.sharpe_ratio ?? 0,
            maxDrawdown: data.summary.maxDrawdown ?? data.summary.max_drawdown ?? 0,
            avgWin: data.summary.avgWin ?? data.summary.avg_win ?? 0,
            avgLoss: data.summary.avgLoss ?? data.summary.avg_loss ?? 0,
            avgHoldTime: data.summary.avgHoldTime ?? data.summary.avg_hold_time ?? 0,
            largestWin: data.summary.largestWin ?? data.summary.largest_win ?? 0,
            largestLoss: data.summary.largestLoss ?? data.summary.largest_loss ?? 0,
            expectancy: data.summary.expectancy ?? 0,
            sortinoRatio: data.summary.sortinoRatio ?? data.summary.sortino_ratio ?? 0,
            calmarRatio: data.summary.calmarRatio ?? data.summary.calmar_ratio ?? 0,
          })

          // Extract daily P&L if available
          if (data.daily_pnl && Array.isArray(data.daily_pnl)) {
            setDailyPnl(data.daily_pnl)
          }
          if (data.drawdowns && Array.isArray(data.drawdowns)) {
            setDrawdowns(data.drawdowns)
          }
          if (data.strategies && Array.isArray(data.strategies)) {
            setStrategies(data.strategies.map((s: any, i: number) => ({
              ...s,
              color: STRATEGY_COLORS[i % STRATEGY_COLORS.length],
            })))
          }
          if (data.monthly_returns && Array.isArray(data.monthly_returns)) {
            setMonthlyReturns(data.monthly_returns)
          }
        }
      }

      // Process trade stats fallback
      if (statsRes.ok) {
        const statsData = await statsRes.json()
        if (statsData && statsData.status !== 'unavailable' && !summary) {
          setSummary({
            totalPnl: statsData.totalPnl ?? statsData.total_pnl ?? 0,
            totalTrades: statsData.totalTrades ?? statsData.total_trades ?? 0,
            winRate: statsData.winRate ?? statsData.win_rate ?? 0,
            profitFactor: statsData.profitFactor ?? statsData.profit_factor ?? 0,
            sharpeRatio: statsData.sharpeRatio ?? statsData.sharpe_ratio ?? 0,
            maxDrawdown: statsData.maxDrawdown ?? statsData.max_drawdown ?? 0,
            avgWin: statsData.avgWin ?? statsData.avg_win ?? 0,
            avgLoss: statsData.avgLoss ?? statsData.avg_loss ?? 0,
            avgHoldTime: statsData.avgHoldTime ?? statsData.avg_hold_time ?? 0,
            largestWin: statsData.largestWin ?? statsData.largest_win ?? 0,
            largestLoss: statsData.largestLoss ?? statsData.largest_loss ?? 0,
            expectancy: statsData.expectancy ?? 0,
            sortinoRatio: statsData.sortinoRatio ?? statsData.sortino_ratio ?? 0,
            calmarRatio: statsData.calmarRatio ?? statsData.calmar_ratio ?? 0,
          })
        }
      }

      // Chart data (dailyPnl, drawdowns, strategies, monthlyReturns) is only
      // shown when the API provides it. No fabricated fallback data.
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch report')
    } finally {
      setIsLoading(false)
    }
  }, [dateRange])

  // No fabricated sample data -- chart sections show empty states when API
  // doesn't return dailyPnl, drawdowns, strategies, or monthlyReturns.

  useEffect(() => {
    fetchReport()
  }, [fetchReport])

  // ─── Export ───────────────────────────────────────────────────────────

  const generateReport = async (format: 'pdf' | 'csv' | 'json') => {
    setIsGenerating(true)
    try {
      const response = await fetch(`/api/reports/generate?format=${format}&range=${dateRange}`, {
        method: 'POST',
      })
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `trading_report_${dateRange}.${format}`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        window.URL.revokeObjectURL(url)
      }
    } catch {
      setError('Failed to generate report')
    } finally {
      setIsGenerating(false)
    }
  }

  // ─── Days calculation ─────────────────────────────────────────────────

  const days = dateRange === '7d' ? 7 : dateRange === '30d' ? 30 : dateRange === '90d' ? 90 : dateRange === '1y' ? 365 : 365

  // ─── Render ───────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-accent-primary/10">
            <ClipboardList className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">PERFORMANCE REPORTS</h1>
            <p className="text-xs text-foreground-muted">Generate and export trading performance reports</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchReport}
            disabled={isLoading}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            Refresh
          </button>
          <button
            onClick={() => generateReport('pdf')}
            className="btn-primary flex items-center gap-2"
            disabled={isGenerating || !summary || summary.totalTrades === 0}
          >
            <Download className={cn('w-4 h-4', isGenerating && 'animate-bounce')} />
            Export PDF
          </button>
          <button
            onClick={() => generateReport('csv')}
            className="btn-secondary flex items-center gap-2"
            disabled={!summary || summary.totalTrades === 0}
          >
            <FileText className="w-4 h-4" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Date Range + Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 bg-background-tertiary rounded-xl p-1">
          {(['7d', '30d', '90d', '1y', 'all'] as const).map(range => (
            <button
              key={range}
              onClick={() => setDateRange(range)}
              className={cn(
                'px-4 py-1.5 text-xs font-medium rounded-lg transition-colors',
                dateRange === range ? 'bg-accent-primary text-black' : 'text-foreground-muted hover:text-foreground-primary'
              )}
            >
              {range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : range === '90d' ? '90 Days' : range === '1y' ? '1 Year' : 'All Time'}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1 bg-background-tertiary rounded-xl p-1">
          {([
            { id: 'overview', label: 'Overview', icon: BarChart3 },
            { id: 'drawdown', label: 'Drawdown', icon: TrendingDown },
            { id: 'risk', label: 'Risk', icon: Shield },
            { id: 'attribution', label: 'Attribution', icon: Layers },
            { id: 'monthly', label: 'Monthly', icon: Calendar },
          ] as const).map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
                activeTab === tab.id ? 'bg-accent-primary text-black' : 'text-foreground-muted hover:text-foreground-primary'
              )}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
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
          <div className="grid grid-cols-5 gap-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="card p-4"><Skeleton className="h-3 w-16 mb-3" /><Skeleton className="h-6 w-24" /></div>
            ))}
          </div>
          <div className="card p-4"><Skeleton className="h-64 w-full" /></div>
        </div>
      ) : !summary || summary.totalTrades === 0 ? (
        <div className="card p-12 text-center text-foreground-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium text-foreground-secondary">No Trading Data Available</p>
          <p className="text-sm mt-2">Reports will be generated once you have trading history</p>
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-5 gap-3 stagger">
            <MetricCard
              label="Total P&L"
              value={formatCurrency(summary.totalPnl)}
              positive={summary.totalPnl >= 0}
              icon={<TrendingUp className="w-4 h-4" />}
            />
            <MetricCard
              label="Win Rate"
              value={summary.winRate > 0 ? `${summary.winRate.toFixed(1)}%` : 'N/A'}
              icon={<Target className="w-4 h-4" />}
            />
            <MetricCard
              label="Profit Factor"
              value={summary.profitFactor > 0 ? summary.profitFactor.toFixed(2) : 'N/A'}
              icon={<BarChart3 className="w-4 h-4" />}
            />
            <MetricCard
              label="Sharpe Ratio"
              value={summary.sharpeRatio !== 0 ? summary.sharpeRatio.toFixed(2) : 'N/A'}
              icon={<Activity className="w-4 h-4" />}
            />
            <MetricCard
              label="Max Drawdown"
              value={summary.maxDrawdown !== 0 ? `${summary.maxDrawdown.toFixed(1)}%` : 'N/A'}
              negative={summary.maxDrawdown < 0}
              icon={<TrendingDown className="w-4 h-4" />}
            />
          </div>

          {/* Tab Content */}
          {activeTab === 'overview' && (
            <OverviewTab summary={summary} dailyPnl={dailyPnl} />
          )}
          {activeTab === 'drawdown' && (
            <DrawdownTab drawdowns={drawdowns} maxDrawdown={summary.maxDrawdown} />
          )}
          {activeTab === 'risk' && (
            <RiskTab summary={summary} />
          )}
          {activeTab === 'attribution' && (
            <AttributionTab strategies={strategies} />
          )}
          {activeTab === 'monthly' && (
            <MonthlyTab monthlyReturns={monthlyReturns} />
          )}
        </>
      )}
    </div>
  )
}

// ─── Metric Card ──────────────────────────────────────────────────────────────

function MetricCard({ label, value, positive, negative, icon }: {
  label: string; value: string; positive?: boolean; negative?: boolean; icon: React.ReactNode
}) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-foreground-muted uppercase tracking-wider">{label}</span>
        <span className={cn(
          positive && 'text-bullish', negative && 'text-bearish',
          !positive && !negative && 'text-foreground-muted'
        )}>
          {icon}
        </span>
      </div>
      <div className={cn(
        'text-xl font-bold font-mono',
        positive && 'text-bullish', negative && 'text-bearish'
      )}>
        {value}
      </div>
    </div>
  )
}

// ─── Overview Tab ─────────────────────────────────────────────────────────────

function OverviewTab({ summary, dailyPnl }: { summary: ReportSummary; dailyPnl: DailyPnl[] }) {
  if (dailyPnl.length === 0) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-8 card p-4">
            <div className="chart-header">
              <h3 className="chart-title">Cumulative P&L</h3>
            </div>
            <div className="h-64 flex items-center justify-center text-foreground-muted text-sm">
              <div className="text-center">
                <BarChart3 className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p>Daily P&L chart data not available from the API</p>
              </div>
            </div>
          </div>
          <div className="col-span-4 card p-4">
            <div className="chart-header">
              <h3 className="chart-title">Win/Loss Distribution</h3>
            </div>
            <div className="flex items-center justify-center h-36">
              <DonutChart
                data={[
                  { name: 'Wins', value: summary.winRate, color: '#10b981' },
                  { name: 'Losses', value: 100 - summary.winRate, color: '#ef4444' },
                ]}
                centerLabel={`${summary.winRate.toFixed(0)}%`}
                centerSubLabel="Win Rate"
                size={120}
              />
            </div>
            <div className="space-y-2.5 mt-3">
              <div className="flex justify-between text-xs">
                <span className="text-foreground-muted">Total Trades</span>
                <span className="font-mono font-bold">{summary.totalTrades}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-foreground-muted">Avg Win</span>
                <span className="font-mono text-bullish">{summary.avgWin > 0 ? formatCurrency(summary.avgWin) : 'N/A'}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-foreground-muted">Avg Loss</span>
                <span className="font-mono text-bearish">{summary.avgLoss !== 0 ? formatCurrency(summary.avgLoss) : 'N/A'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-12 gap-4">
        {/* Cumulative P&L Chart */}
        <div className="col-span-8 card p-4">
          <div className="chart-header">
            <h3 className="chart-title">Cumulative P&L</h3>
            <span className={cn('text-sm font-bold font-mono', summary.totalPnl >= 0 ? 'text-bullish' : 'text-bearish')}>
              {summary.totalPnl >= 0 ? '+' : ''}{formatCurrency(summary.totalPnl)}
            </span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailyPnl}>
                <defs>
                  <linearGradient id="cumGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={summary.totalPnl >= 0 ? '#10b981' : '#ef4444'} stopOpacity={0.2} />
                    <stop offset="95%" stopColor={summary.totalPnl >= 0 ? '#10b981' : '#ef4444'} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false}
                  tickFormatter={(v) => `$${(v / 1000).toFixed(1)}K`} />
                <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }}
                  formatter={(value: number) => [formatCurrency(value), 'Cumulative P&L']} />
                <ReferenceLine y={0} stroke="#71717a" strokeDasharray="3 3" />
                <Area type="monotone" dataKey="cumulative" stroke={summary.totalPnl >= 0 ? '#10b981' : '#ef4444'}
                  strokeWidth={2} fill="url(#cumGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Win/Loss Summary */}
        <div className="col-span-4 card p-4">
          <div className="chart-header">
            <h3 className="chart-title">Win/Loss Distribution</h3>
          </div>
          <div className="flex items-center justify-center h-36">
            <DonutChart
              data={[
                { name: 'Wins', value: summary.winRate, color: '#10b981' },
                { name: 'Losses', value: 100 - summary.winRate, color: '#ef4444' },
              ]}
              centerLabel={`${summary.winRate.toFixed(0)}%`}
              centerSubLabel="Win Rate"
              size={120}
            />
          </div>
          <div className="space-y-2.5 mt-3">
            <div className="flex justify-between text-xs">
              <span className="text-foreground-muted">Total Trades</span>
              <span className="font-mono font-bold">{summary.totalTrades}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-foreground-muted">Avg Win</span>
              <span className="font-mono text-bullish">{summary.avgWin > 0 ? formatCurrency(summary.avgWin) : 'N/A'}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-foreground-muted">Avg Loss</span>
              <span className="font-mono text-bearish">{summary.avgLoss !== 0 ? formatCurrency(summary.avgLoss) : 'N/A'}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-foreground-muted">Largest Win</span>
              <span className="font-mono text-bullish">{summary.largestWin > 0 ? formatCurrency(summary.largestWin) : 'N/A'}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-foreground-muted">Largest Loss</span>
              <span className="font-mono text-bearish">{summary.largestLoss !== 0 ? formatCurrency(summary.largestLoss) : 'N/A'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Daily P&L Bar Chart */}
      <div className="card p-4">
        <div className="chart-header">
          <h3 className="chart-title">Daily P&L</h3>
        </div>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={dailyPnl}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 9 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false}
                tickFormatter={(v) => `$${v}`} />
              <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }}
                formatter={(value: number) => [formatCurrency(value), 'Daily P&L']} />
              <ReferenceLine y={0} stroke="#71717a" />
              <Bar dataKey="pnl" radius={[2, 2, 0, 0]} name="Daily P&L">
                {dailyPnl.map((entry, index) => (
                  <Cell key={index} fill={entry.pnl >= 0 ? '#10b981' : '#ef4444'} fillOpacity={0.7} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

// ─── Drawdown Tab ─────────────────────────────────────────────────────────────

function DrawdownTab({ drawdowns, maxDrawdown }: { drawdowns: DrawdownPoint[]; maxDrawdown: number }) {
  if (drawdowns.length === 0) {
    return (
      <div className="card p-12 text-center text-foreground-muted">
        <TrendingDown className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm font-medium text-foreground-secondary">No Drawdown Data Available</p>
        <p className="text-xs mt-1">Drawdown analysis will appear when the API provides equity curve data</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="chart-header">
          <h3 className="chart-title">Equity Curve</h3>
        </div>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={drawdowns}>
              <defs>
                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false}
                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`} />
              <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }}
                formatter={(value: number) => [formatCurrency(value), '']} />
              <Line type="monotone" dataKey="peak" stroke="#4b5563" strokeDasharray="3 3" dot={false} strokeWidth={1} name="Peak" />
              <Area type="monotone" dataKey="equity" stroke="#f59e0b" strokeWidth={2} fill="url(#eqGrad)" dot={false} name="Equity" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card p-4">
        <div className="chart-header">
          <h3 className="chart-title">Drawdown Analysis</h3>
          <span className="text-sm font-bold font-mono text-bearish">
            Max: {maxDrawdown.toFixed(2)}%
          </span>
        </div>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={drawdowns}>
              <defs>
                <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false}
                tickFormatter={(v) => `${v}%`} domain={['auto', 0]} />
              <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }}
                formatter={(value: number) => [`${value.toFixed(2)}%`, 'Drawdown']} />
              <ReferenceLine y={0} stroke="#71717a" />
              <Area type="monotone" dataKey="drawdown" stroke="#ef4444" strokeWidth={2} fill="url(#ddGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

// ─── Risk Tab ─────────────────────────────────────────────────────────────────

function RiskTab({ summary }: { summary: ReportSummary }) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="card p-5">
        <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">RISK-ADJUSTED RETURNS</h3>
        <div className="space-y-3">
          <RiskMetricRow label="Sharpe Ratio" value={summary.sharpeRatio.toFixed(2)}
            good={summary.sharpeRatio >= 1.5} warning={summary.sharpeRatio >= 1 && summary.sharpeRatio < 1.5} />
          <RiskMetricRow label="Sortino Ratio" value={summary.sortinoRatio.toFixed(2)}
            good={summary.sortinoRatio >= 2} warning={summary.sortinoRatio >= 1 && summary.sortinoRatio < 2} />
          <RiskMetricRow label="Calmar Ratio" value={summary.calmarRatio.toFixed(2)}
            good={summary.calmarRatio >= 3} warning={summary.calmarRatio >= 1 && summary.calmarRatio < 3} />
          <RiskMetricRow label="Profit Factor" value={summary.profitFactor.toFixed(2)}
            good={summary.profitFactor >= 1.5} warning={summary.profitFactor >= 1 && summary.profitFactor < 1.5} />
          <RiskMetricRow label="Expectancy" value={formatCurrency(summary.expectancy)}
            good={summary.expectancy > 0} />
        </div>
      </div>

      <div className="card p-5">
        <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">DRAWDOWN & RISK</h3>
        <div className="space-y-3">
          <RiskMetricRow label="Max Drawdown" value={`${summary.maxDrawdown.toFixed(2)}%`}
            good={Math.abs(summary.maxDrawdown) < 10}
            warning={Math.abs(summary.maxDrawdown) >= 10 && Math.abs(summary.maxDrawdown) < 20} />
          <RiskMetricRow label="Win Rate" value={`${summary.winRate.toFixed(1)}%`}
            good={summary.winRate >= 60} warning={summary.winRate >= 50 && summary.winRate < 60} />
          <RiskMetricRow label="Avg Win / Avg Loss" value={summary.avgLoss !== 0 ? (Math.abs(summary.avgWin / summary.avgLoss)).toFixed(2) : 'N/A'}
            good={summary.avgLoss !== 0 && Math.abs(summary.avgWin / summary.avgLoss) >= 1.5} />
          <RiskMetricRow label="Largest Win" value={formatCurrency(summary.largestWin)} />
          <RiskMetricRow label="Largest Loss" value={formatCurrency(summary.largestLoss)} />
        </div>
      </div>

      <div className="col-span-2 card p-5">
        <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">TRADE STATISTICS</h3>
        <div className="grid grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-2xl font-bold font-mono text-foreground-primary">{summary.totalTrades}</div>
            <div className="text-xs text-foreground-muted mt-1">Total Trades</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold font-mono text-bullish">{summary.avgWin > 0 ? formatCurrency(summary.avgWin) : 'N/A'}</div>
            <div className="text-xs text-foreground-muted mt-1">Avg Winner</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold font-mono text-bearish">{summary.avgLoss !== 0 ? formatCurrency(summary.avgLoss) : 'N/A'}</div>
            <div className="text-xs text-foreground-muted mt-1">Avg Loser</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold font-mono text-foreground-primary">{summary.avgHoldTime > 0 ? `${summary.avgHoldTime.toFixed(1)}h` : 'N/A'}</div>
            <div className="text-xs text-foreground-muted mt-1">Avg Hold Time</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function RiskMetricRow({ label, value, good, warning }: {
  label: string; value: string; good?: boolean; warning?: boolean
}) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-border last:border-0">
      <span className="text-sm text-foreground-muted">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-mono font-semibold text-foreground-primary">{value}</span>
        {good !== undefined && (
          <span className={cn(
            'w-2 h-2 rounded-full',
            good ? 'bg-bullish' : warning ? 'bg-warning' : 'bg-bearish'
          )} />
        )}
      </div>
    </div>
  )
}

// ─── Attribution Tab ──────────────────────────────────────────────────────────

function AttributionTab({ strategies }: { strategies: StrategyBreakdown[] }) {
  if (strategies.length === 0) {
    return (
      <div className="card p-12 text-center text-foreground-muted">
        <Layers className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm font-medium text-foreground-secondary">No Strategy Attribution Data</p>
        <p className="text-xs mt-1">Strategy breakdown will appear when the API provides attribution data</p>
      </div>
    )
  }

  const totalPnl = strategies.reduce((sum, s) => sum + s.pnl, 0)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-12 gap-4">
        {/* Strategy P&L Chart */}
        <div className="col-span-8 card p-4">
          <div className="chart-header">
            <h3 className="chart-title">P&L by Strategy</h3>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={strategies} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" horizontal={false} />
                <XAxis type="number" tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false}
                  tickFormatter={(v) => `$${v}`} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#a1a1aa', fontSize: 11 }} tickLine={false} axisLine={false} width={100} />
                <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }}
                  formatter={(value: number) => [formatCurrency(value), 'P&L']} />
                <Bar dataKey="pnl" radius={[0, 4, 4, 0]} name="P&L">
                  {strategies.map((s, i) => (
                    <Cell key={i} fill={s.pnl >= 0 ? s.color : '#ef4444'} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Strategy allocation donut */}
        <div className="col-span-4 card p-4">
          <div className="chart-header">
            <h3 className="chart-title">Allocation</h3>
          </div>
          <div className="flex items-center justify-center h-36">
            <DonutChart
              data={strategies.filter(s => s.pnl > 0).map(s => ({
                name: s.name,
                value: Math.abs(s.pnl),
                color: s.color,
              }))}
              centerLabel={strategies.length.toString()}
              centerSubLabel="Strategies"
              size={120}
            />
          </div>
          <div className="space-y-1.5 mt-3">
            {strategies.map(s => (
              <div key={s.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
                  <span className="text-foreground-secondary">{s.name}</span>
                </div>
                <span className={cn('font-mono', s.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                  {s.pnl >= 0 ? '+' : ''}{formatCurrency(s.pnl)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Strategy Table */}
      <div className="card overflow-hidden">
        <table className="data-table text-xs">
          <thead>
            <tr>
              <th>Strategy</th>
              <th className="text-right">P&L</th>
              <th className="text-right">Trades</th>
              <th className="text-right">Win Rate</th>
              <th className="text-right">Profit Factor</th>
              <th className="text-right">% of Total</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map(s => (
              <tr key={s.name}>
                <td>
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                    <span className="font-medium">{s.name}</span>
                  </div>
                </td>
                <td className={cn('text-right font-mono', s.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                  {s.pnl >= 0 ? '+' : ''}{formatCurrency(s.pnl)}
                </td>
                <td className="text-right font-mono">{s.trades}</td>
                <td className="text-right font-mono">{s.winRate.toFixed(1)}%</td>
                <td className="text-right font-mono">{s.profitFactor.toFixed(2)}</td>
                <td className="text-right font-mono">
                  {totalPnl !== 0 ? ((s.pnl / totalPnl) * 100).toFixed(1) : '0.0'}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Monthly Tab ──────────────────────────────────────────────────────────────

function MonthlyTab({ monthlyReturns }: { monthlyReturns: MonthlyReturn[] }) {
  if (monthlyReturns.length === 0) {
    return (
      <div className="card p-12 text-center text-foreground-muted">
        <Calendar className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm font-medium text-foreground-secondary">No Monthly Returns Data</p>
        <p className="text-xs mt-1">Monthly returns will appear when the API provides historical performance data</p>
      </div>
    )
  }

  const ytdReturn = monthlyReturns.reduce((sum, m) => sum + m.return_pct, 0)

  return (
    <div className="space-y-4">
      {/* Monthly Returns Bar Chart */}
      <div className="card p-4">
        <div className="chart-header">
          <h3 className="chart-title">Monthly Returns</h3>
          <span className={cn('text-sm font-bold font-mono', ytdReturn >= 0 ? 'text-bullish' : 'text-bearish')}>
            YTD: {ytdReturn >= 0 ? '+' : ''}{ytdReturn.toFixed(2)}%
          </span>
        </div>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={monthlyReturns}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: '#71717a', fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false}
                tickFormatter={(v) => `${v}%`} />
              <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }}
                formatter={(value: number) => [`${value.toFixed(2)}%`, 'Return']} />
              <ReferenceLine y={0} stroke="#71717a" />
              <Bar dataKey="return_pct" radius={[4, 4, 0, 0]} name="Monthly Return">
                {monthlyReturns.map((entry, i) => (
                  <Cell key={i} fill={entry.return_pct >= 0 ? '#10b981' : '#ef4444'} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Monthly Returns Table */}
      <div className="card overflow-hidden">
        <div className="p-4 border-b border-border">
          <h3 className="text-sm font-semibold">Monthly Returns Table</h3>
        </div>
        <div className="grid grid-cols-6 gap-3 p-4">
          {monthlyReturns.map(m => (
            <div key={m.month} className={cn(
              'p-3 rounded-xl text-center',
              m.return_pct >= 0 ? 'bg-bullish/10' : 'bg-bearish/10'
            )}>
              <div className="text-xs text-foreground-muted mb-1">{m.month} {m.year}</div>
              <div className={cn('text-lg font-bold font-mono', m.return_pct >= 0 ? 'text-bullish' : 'text-bearish')}>
                {m.return_pct >= 0 ? '+' : ''}{m.return_pct.toFixed(2)}%
              </div>
            </div>
          ))}
          {/* YTD Summary */}
          <div className={cn(
            'p-3 rounded-xl text-center border-2',
            ytdReturn >= 0 ? 'border-bullish/30 bg-bullish/5' : 'border-bearish/30 bg-bearish/5'
          )}>
            <div className="text-xs text-foreground-muted mb-1">YTD</div>
            <div className={cn('text-lg font-bold font-mono', ytdReturn >= 0 ? 'text-bullish' : 'text-bearish')}>
              {ytdReturn >= 0 ? '+' : ''}{ytdReturn.toFixed(2)}%
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
