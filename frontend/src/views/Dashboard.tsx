/**
 * Dashboard View - Main overview screen
 * Connected to backend API with real-time updates
 *
 * First impression: institutional-grade, data-rich, Bloomberg Terminal meets modern fintech
 */

import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Target,
  Activity,
  Brain,
  Cpu,
  Zap,
  RefreshCw,
  Shield,
  BarChart3,
  GraduationCap,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { AreaChart } from '@/components/charts/AreaChart'
import { DonutChart } from '@/components/charts/DonutChart'
import { BarChart } from '@/components/charts/BarChart'
import { GaugeChart } from '@/components/charts/GaugeChart'
import { MetricCard } from '@/components/cards/MetricCard'
import { SignalsTable } from '@/components/tables/SignalsTable'
import { useDashboardData } from '@/hooks'
import { Skeleton } from '@/components/ui/LoadingStates'
import { cn } from '@/utils/cn'
import {
  formatCurrency,
  formatPercent,
  formatNumber,
  formatCompactCurrency,
  getPnLColorClass,
} from '@/utils/format'

// ---- Empty State Placeholder Component ----
function EmptyStateCard({
  icon: Icon,
  title,
  description,
  actionLabel,
  actionPath,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  description: string
  actionLabel?: string
  actionPath?: string
}) {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="w-12 h-12 rounded-2xl bg-background-tertiary/80 flex items-center justify-center mb-3">
        <Icon className="w-6 h-6 text-foreground-muted" />
      </div>
      <p className="text-sm font-medium text-foreground-primary mb-1">{title}</p>
      <p className="text-xs text-foreground-muted max-w-[240px] leading-relaxed">{description}</p>
      {actionLabel && actionPath && (
        <button
          onClick={() => navigate(actionPath)}
          className="mt-3 px-3 py-1.5 text-xs font-medium text-accent-primary bg-accent-primary/10 hover:bg-accent-primary/15 rounded-lg transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  )
}

// ---- Inline Stat Block for compact metric display ----
function StatBlock({
  label,
  value,
  colorClass,
  mono = true,
}: {
  label: string
  value: string
  colorClass?: string
  mono?: boolean
}) {
  return (
    <div className="bg-background-tertiary/60 rounded-xl p-3 text-center">
      <div className="text-[10px] font-semibold text-foreground-muted uppercase tracking-wider mb-1.5">{label}</div>
      <div className={cn(
        'text-base font-bold',
        mono && 'font-mono tabular-nums',
        colorClass || 'text-foreground-primary'
      )}>
        {value}
      </div>
    </div>
  )
}

export function Dashboard() {
  const navigate = useNavigate()
  const {
    brainStatus,
    feedbackStatus,
    signals,
    portfolio,
    riskMetrics,
    isLoading,
    isRefreshing,
    errors,
    refresh,
  } = useDashboardData(15000) // 15 second refresh

  // Portfolio calculations
  const portfolioValue = portfolio?.equity ?? 0
  const dayPnl = portfolio?.day_pnl ?? 0
  const dayPnlPct = portfolio?.day_pnl_pct ?? 0
  const winRate = feedbackStatus?.win_rate ? feedbackStatus.win_rate * 100 : 0
  const activeSignalCount = signals?.filter(s => s.status === 'active').length ?? 0
  const highConfidenceCount = signals?.filter(s => s.confidence >= 0.7).length ?? 0
  const hasPortfolioData = portfolioValue > 0 || dayPnl !== 0

  // Convergence progress calculation
  const convergenceProgress = feedbackStatus
    ? feedbackStatus.is_converged
      ? 100
      : Object.values(feedbackStatus.convergence_progress || {}).length > 0
        ? Math.round(
            (Object.values(feedbackStatus.convergence_progress).reduce((a: number, b: number) => a + b, 0) /
              Math.max(1, Object.keys(feedbackStatus.convergence_progress).length)) *
              100
          )
        : 0
    : 0

  return (
    <div className="space-y-4 stagger">
      {/* ============ TOP METRICS ROW ============ */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          title="Portfolio Value"
          value={hasPortfolioData ? formatCurrency(portfolioValue) : '--'}
          change={hasPortfolioData ? dayPnl : undefined}
          changePercent={hasPortfolioData ? dayPnlPct : undefined}
          icon={DollarSign}
          trend={dayPnl >= 0 ? 'up' : 'down'}
          isLoading={isLoading}
        />
        <MetricCard
          title="Today's P&L"
          value={hasPortfolioData ? `${dayPnl >= 0 ? '+' : ''}${formatCurrency(dayPnl)}` : '--'}
          change={hasPortfolioData ? dayPnlPct : undefined}
          changePercent={hasPortfolioData ? dayPnlPct : undefined}
          icon={dayPnl >= 0 ? TrendingUp : TrendingDown}
          trend={dayPnl >= 0 ? 'up' : 'down'}
          valueColor={hasPortfolioData ? (dayPnl >= 0 ? 'bullish' : 'bearish') : 'default'}
          isLoading={isLoading}
        />
        <MetricCard
          title="Win Rate"
          value={feedbackStatus ? formatPercent(winRate) : '--'}
          change={undefined}
          changePercent={undefined}
          icon={Target}
          trend="up"
          isLoading={isLoading}
        />
        <MetricCard
          title="Active Signals"
          value={signals ? activeSignalCount.toString() : '--'}
          change={signals ? highConfidenceCount : undefined}
          icon={Activity}
          trend="up"
          subtitle={signals ? `${highConfidenceCount} high confidence` : undefined}
          isLoading={isLoading}
        />
      </div>

      {/* ============ MAIN CONTENT GRID ============ */}
      <div className="grid grid-cols-12 gap-4">

        {/* ---- Equity Curve (large) ---- */}
        <div className="col-span-8 card p-5">
          <div className="chart-header">
            <h3 className="chart-title">Equity Curve</h3>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-4 text-xs">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-accent-primary" />
                  <span className="text-foreground-secondary">Equity</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-foreground-muted/50" />
                  <span className="text-foreground-secondary">Benchmark</span>
                </span>
              </div>
              <select className="text-[11px] bg-background-tertiary text-foreground-secondary px-2.5 py-1.5 rounded-lg border border-border cursor-pointer focus:border-accent-primary/50 focus:outline-none transition-colors">
                <option>1M</option>
                <option>3M</option>
                <option>6M</option>
                <option>1Y</option>
                <option>ALL</option>
              </select>
            </div>
          </div>
          <AreaChart />
        </div>

        {/* ---- P&L Distribution ---- */}
        <div className="col-span-4 card p-5">
          <div className="chart-header">
            <h3 className="chart-title">P&L Distribution</h3>
          </div>
          <BarChart />
        </div>

        {/* ---- Win/Loss Donut ---- */}
        <div className="col-span-4 card p-5">
          <div className="chart-header">
            <h3 className="chart-title">Win vs Loss</h3>
          </div>
          {feedbackStatus ? (
            <>
              <div className="flex items-center justify-center h-44">
                <DonutChart
                  data={[
                    { name: 'Winning', value: winRate || 1, color: '#10b981' },
                    { name: 'Losing', value: (100 - winRate) || 1, color: '#ef4444' },
                  ]}
                  centerLabel={formatPercent(winRate, 1)}
                  centerSubLabel="Win Rate"
                />
              </div>
              <div className="flex justify-center gap-10 mt-2">
                <div className="text-center">
                  <div className="text-lg font-bold font-mono tabular-nums text-bullish">
                    {feedbackStatus.total_trades ? formatNumber(Math.round(feedbackStatus.total_trades * (feedbackStatus.win_rate || 0))) : '0'}
                  </div>
                  <div className="text-[10px] text-foreground-muted uppercase tracking-wider font-medium">Winning</div>
                </div>
                <div className="w-px bg-border" />
                <div className="text-center">
                  <div className="text-lg font-bold font-mono tabular-nums text-bearish">
                    {feedbackStatus.total_trades ? formatNumber(Math.round(feedbackStatus.total_trades * (1 - (feedbackStatus.win_rate || 0)))) : '0'}
                  </div>
                  <div className="text-[10px] text-foreground-muted uppercase tracking-wider font-medium">Losing</div>
                </div>
              </div>
            </>
          ) : (
            <EmptyStateCard
              icon={GraduationCap}
              title="No trading data yet"
              description="Run ML Training to start generating trade statistics and win/loss analysis"
              actionLabel="Go to ML Training"
              actionPath="/ml-training"
            />
          )}
        </div>

        {/* ---- Risk Gauge ---- */}
        <div className="col-span-4 card p-5">
          <div className="chart-header">
            <h3 className="chart-title flex items-center gap-2">
              <Shield className="w-3.5 h-3.5 text-info" />
              Risk Exposure
            </h3>
          </div>
          <div className="flex items-center justify-center h-44">
            <GaugeChart
              value={riskMetrics?.risk_score ?? 0}
              maxValue={100}
              label="Portfolio Risk"
            />
          </div>
          <div className="grid grid-cols-3 gap-3 mt-3">
            <StatBlock
              label="VaR 95%"
              value={riskMetrics ? formatCompactCurrency(riskMetrics.var_95 * portfolioValue) : '--'}
            />
            <StatBlock
              label="Exposure"
              value={riskMetrics ? formatPercent(riskMetrics.max_position_exposure * 100, 0) : '--'}
              colorClass="text-warning"
            />
            <StatBlock
              label="Sharpe"
              value={feedbackStatus?.sharpe_ratio?.toFixed(2) ?? '--'}
              colorClass={feedbackStatus?.sharpe_ratio && feedbackStatus.sharpe_ratio >= 1.5 ? 'text-bullish' : 'text-foreground-primary'}
            />
          </div>
        </div>

        {/* ---- Strategy Performance ---- */}
        <div className="col-span-4 card p-5">
          <div className="chart-header">
            <h3 className="chart-title flex items-center gap-2">
              <BarChart3 className="w-3.5 h-3.5 text-accent-primary" />
              Profit Factor by Strategy
            </h3>
          </div>
          <BarChart horizontal />
        </div>

        {/* ============ BRAIN & FEEDBACK ROW ============ */}

        {/* ---- Brain Status Panel ---- */}
        <div className="col-span-6 card p-5">
          <div className="chart-header">
            <h3 className="chart-title flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-400" />
              PropFirm Brain V6
            </h3>
            <div className="flex items-center gap-2">
              <button
                onClick={refresh}
                disabled={isRefreshing}
                className={cn(
                  'p-1.5 rounded-lg hover:bg-background-tertiary transition-all disabled:opacity-50',
                  isRefreshing && 'animate-spin'
                )}
                title="Refresh data"
              >
                <RefreshCw className="w-3.5 h-3.5 text-foreground-muted" />
              </button>
              <span className="text-[10px] text-foreground-muted font-mono tabular-nums">
                {new Date().toLocaleTimeString('en-US', { hour12: false })}
              </span>
            </div>
          </div>
          {brainStatus ? (
            <div className="space-y-4 mt-3">
              {/* Device & Status */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Cpu className={cn('w-4 h-4', brainStatus.device === 'cuda' ? 'text-bullish' : 'text-foreground-muted')} />
                  <span className="text-xs font-bold uppercase tracking-wider">{brainStatus.device}</span>
                </div>
                <span className={cn(
                  'px-2.5 py-1 rounded-lg text-[10px] font-bold tracking-wider',
                  brainStatus.is_trained
                    ? 'bg-bullish/15 text-bullish'
                    : 'bg-warning/15 text-warning'
                )}>
                  {brainStatus.is_trained ? 'TRAINED' : 'UNTRAINED'}
                </span>
              </div>

              {/* Quick Stats */}
              <div className="grid grid-cols-3 gap-3">
                <StatBlock
                  label="Regime"
                  value={brainStatus.current_regime || '--'}
                  colorClass="text-info"
                  mono={false}
                />
                <StatBlock
                  label="Trades"
                  value={formatNumber(brainStatus.total_trades || 0)}
                />
                <StatBlock
                  label="Auto-Train"
                  value={brainStatus.auto_train_enabled ? 'ON' : 'OFF'}
                  colorClass={brainStatus.auto_train_enabled ? 'text-bullish' : 'text-foreground-muted'}
                  mono={false}
                />
              </div>

              {/* Top Strategies */}
              {brainStatus.strategies && brainStatus.strategies.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[10px] font-semibold text-foreground-muted uppercase tracking-wider">Top Strategies</div>
                  {brainStatus.strategies.slice(0, 3).map((s: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-border/30 last:border-0">
                      <span className="text-foreground-primary font-medium">{s.name}</span>
                      <div className="flex items-center gap-3 font-mono tabular-nums">
                        <span className="text-foreground-muted">{(s.weight * 100).toFixed(0)}%</span>
                        <span className={cn(
                          'font-semibold',
                          s.win_rate >= 50 ? 'text-bullish' : 'text-bearish'
                        )}>
                          {s.win_rate.toFixed(1)}% WR
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : isLoading ? (
            <div className="space-y-4 mt-3">
              <div className="flex items-center justify-between">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-6 w-20 rounded-lg" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="bg-background-tertiary/60 rounded-xl p-3">
                    <Skeleton className="h-3 w-12 mx-auto mb-2" />
                    <Skeleton className="h-5 w-16 mx-auto" />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyStateCard
              icon={Brain}
              title="Brain not initialized"
              description="Configure API keys and run ML Training to activate the PropFirm Brain V6 engine"
              actionLabel="Configure API Keys"
              actionPath="/api-connector"
            />
          )}
        </div>

        {/* ---- Feedback Loop Panel ---- */}
        <div className="col-span-6 card p-5">
          <div className="chart-header">
            <h3 className="chart-title flex items-center gap-2">
              <Zap className="w-4 h-4 text-accent-primary" />
              Feedback Loop
            </h3>
            {feedbackStatus && (
              <span className={cn(
                'px-2.5 py-1 rounded-lg text-[10px] font-bold tracking-wider',
                feedbackStatus.is_converged
                  ? 'bg-bullish/15 text-bullish'
                  : 'bg-info/15 text-info'
              )}>
                {feedbackStatus.phase.toUpperCase()}
              </span>
            )}
          </div>
          {feedbackStatus ? (
            <div className="space-y-4 mt-3">
              {/* Metrics Grid */}
              <div className="grid grid-cols-4 gap-3">
                <StatBlock
                  label="Win Rate"
                  value={formatPercent(feedbackStatus.win_rate * 100, 1)}
                  colorClass={feedbackStatus.win_rate >= 0.65 ? 'text-bullish' : 'text-warning'}
                />
                <StatBlock
                  label="Profit Factor"
                  value={feedbackStatus.profit_factor.toFixed(2)}
                  colorClass={feedbackStatus.profit_factor >= 1.5 ? 'text-bullish' : 'text-warning'}
                />
                <StatBlock
                  label="Sharpe"
                  value={feedbackStatus.sharpe_ratio.toFixed(2)}
                  colorClass={feedbackStatus.sharpe_ratio >= 1.5 ? 'text-bullish' : 'text-warning'}
                />
                <StatBlock
                  label="Trades"
                  value={formatNumber(feedbackStatus.total_trades)}
                />
              </div>

              {/* Convergence Progress */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-foreground-muted font-medium">Convergence Progress</span>
                  <span className="font-mono font-bold tabular-nums text-foreground-primary">
                    {convergenceProgress}%
                  </span>
                </div>
                <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-700 ease-out',
                      convergenceProgress >= 100
                        ? 'bg-gradient-to-r from-bullish to-bullish-soft'
                        : 'bg-gradient-to-r from-info to-bullish'
                    )}
                    style={{ width: `${convergenceProgress}%` }}
                  />
                </div>
              </div>

              {/* Convergence Targets */}
              <div className="grid grid-cols-3 gap-3 text-[10px]">
                <div className="flex items-center justify-between">
                  <span className="text-foreground-muted">WR Target</span>
                  <span className={cn('font-mono font-bold', feedbackStatus.win_rate >= 0.65 ? 'text-bullish' : 'text-foreground-muted')}>
                    65%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-foreground-muted">PF Target</span>
                  <span className={cn('font-mono font-bold', feedbackStatus.profit_factor >= 1.5 ? 'text-bullish' : 'text-foreground-muted')}>
                    1.5x
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-foreground-muted">SR Target</span>
                  <span className={cn('font-mono font-bold', feedbackStatus.sharpe_ratio >= 1.5 ? 'text-bullish' : 'text-foreground-muted')}>
                    1.5
                  </span>
                </div>
              </div>
            </div>
          ) : isLoading ? (
            <div className="space-y-4 mt-3">
              <div className="grid grid-cols-4 gap-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="bg-background-tertiary/60 rounded-xl p-3 text-center">
                    <Skeleton className="h-3 w-12 mx-auto mb-2" />
                    <Skeleton className="h-5 w-16 mx-auto" />
                  </div>
                ))}
              </div>
              <Skeleton className="h-2 w-full rounded-full" />
            </div>
          ) : (
            <EmptyStateCard
              icon={Zap}
              title="Feedback loop inactive"
              description="The feedback loop activates after the brain starts generating signals and recording trades"
              actionLabel="View ML Training"
              actionPath="/ml-training"
            />
          )}
        </div>

        {/* ============ SIGNALS TABLE ============ */}
        <div className="col-span-12 card p-5">
          <div className="chart-header">
            <h3 className="chart-title flex items-center gap-2">
              <Activity className="w-4 h-4 text-accent-primary" />
              Active Signals
            </h3>
            <div className="flex items-center gap-3">
              {activeSignalCount > 0 && (
                <span className="text-[10px] font-bold text-foreground-muted uppercase tracking-wider">
                  {activeSignalCount} active
                </span>
              )}
              <button className="btn-primary text-xs px-4 py-2">Execute All</button>
            </div>
          </div>
          <SignalsTable
            signals={signals}
            isLoading={isLoading}
            error={errors?.signals}
            onRefresh={refresh}
          />
        </div>
      </div>
    </div>
  )
}
