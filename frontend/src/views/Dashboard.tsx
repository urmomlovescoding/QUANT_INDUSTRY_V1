/**
 * Dashboard View - Main overview screen
 * Connected to backend API with real-time updates
 */

import { useEffect } from 'react'
import {
  TrendingUp,
  DollarSign,
  Target,
  Activity,
  Brain,
  Cpu,
  Zap,
  RefreshCw,
} from 'lucide-react'
import { AreaChart } from '@/components/charts/AreaChart'
import { DonutChart } from '@/components/charts/DonutChart'
import { BarChart } from '@/components/charts/BarChart'
import { GaugeChart } from '@/components/charts/GaugeChart'
import { MetricCard } from '@/components/cards/MetricCard'
import { SignalsTable } from '@/components/tables/SignalsTable'
import { useDashboardData } from '@/hooks'
import { Skeleton } from '@/components/ui/LoadingStates'
import { formatCurrency, formatPercent } from '@/utils/format'

export function Dashboard() {
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

  // Portfolio calculations - no fake defaults, show actual data or 0
  const portfolioValue = portfolio?.equity ?? 0
  const dayPnl = portfolio?.day_pnl ?? 0
  const dayPnlPct = portfolio?.day_pnl_pct ?? 0
  const winRate = feedbackStatus?.win_rate ? feedbackStatus.win_rate * 100 : 0
  const activeSignalCount = signals?.filter(s => s.status === 'active').length ?? 0
  const highConfidenceCount = signals?.filter(s => s.confidence >= 0.7).length ?? 0

  return (
    <div className="space-y-4">
      {/* Top metrics row */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          title="Portfolio Value"
          value={formatCurrency(portfolioValue)}
          change={dayPnl}
          changePercent={dayPnlPct}
          icon={DollarSign}
          trend={dayPnl >= 0 ? 'up' : 'down'}
          isLoading={isLoading}
        />
        <MetricCard
          title="Today's P&L"
          value={`${dayPnl >= 0 ? '+' : ''}${formatCurrency(dayPnl)}`}
          change={dayPnlPct}
          changePercent={dayPnlPct}
          icon={TrendingUp}
          trend={dayPnl >= 0 ? 'up' : 'down'}
          valueColor={dayPnl >= 0 ? 'bullish' : 'bearish'}
          isLoading={isLoading}
        />
        <MetricCard
          title="Win Rate"
          value={formatPercent(winRate)}
          icon={Target}
          trend={winRate >= 50 ? 'up' : winRate > 0 ? 'down' : 'up'}
          isLoading={isLoading}
        />
        <MetricCard
          title="Active Signals"
          value={activeSignalCount.toString()}
          change={highConfidenceCount}
          icon={Activity}
          trend="up"
          subtitle={`${highConfidenceCount} high confidence`}
          isLoading={isLoading}
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Equity curve - large */}
        <div className="col-span-8 card p-4">
          <div className="chart-header">
            <h3 className="chart-title">Monthly Result</h3>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-4 text-sm">
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-accent-primary" />
                  Equity
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-foreground-muted" />
                  Benchmark
                </span>
              </div>
              <select className="text-xs bg-background-tertiary text-foreground-secondary px-2 py-1 rounded border border-border">
                <option>1M</option>
                <option>3M</option>
                <option>6M</option>
                <option>1Y</option>
                <option>ALL</option>
              </select>
            </div>
          </div>
          <AreaChart emptyMessage="Equity data will populate with trading history" />
        </div>

        {/* Daily P&L distribution */}
        <div className="col-span-4 card p-4">
          <div className="chart-header">
            <h3 className="chart-title">Daily P&L Distribution</h3>
          </div>
          <BarChart emptyMessage="P&L data will populate with trades" />
        </div>

        {/* Bottom row - 3 columns */}
        <div className="col-span-4 card p-4">
          <div className="chart-header">
            <h3 className="chart-title">Win vs Loss</h3>
          </div>
          <div className="flex items-center justify-center h-48">
            <DonutChart
              data={[
                { name: 'Winning', value: winRate, color: '#00c853' },
                { name: 'Losing', value: 100 - winRate, color: '#ff1744' },
              ]}
              centerLabel={formatPercent(winRate)}
              centerSubLabel="Win Rate"
            />
          </div>
          <div className="flex justify-center gap-8 mt-2">
            <div className="text-center">
              <div className="text-lg font-bold text-bullish">
                {feedbackStatus?.total_trades ? Math.round(feedbackStatus.total_trades * (feedbackStatus.win_rate || 0)) : 0}
              </div>
              <div className="text-xs text-foreground-muted">Winning</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-bearish">
                {feedbackStatus?.total_trades ? Math.round(feedbackStatus.total_trades * (1 - (feedbackStatus.win_rate || 0))) : 0}
              </div>
              <div className="text-xs text-foreground-muted">Losing</div>
            </div>
          </div>
        </div>

        <div className="col-span-4 card p-4">
          <div className="chart-header">
            <h3 className="chart-title">Risk Exposure</h3>
          </div>
          <div className="flex items-center justify-center h-48">
            <GaugeChart
              value={riskMetrics?.risk_score ?? 0}
              maxValue={100}
              label="Portfolio Risk"
            />
          </div>
          <div className="grid grid-cols-3 gap-4 mt-4">
            <div className="text-center">
              <div className="text-sm font-bold text-foreground-primary">
                {riskMetrics ? formatCurrency(riskMetrics.var_95 * portfolioValue) : '--'}
              </div>
              <div className="text-xs text-foreground-muted">VaR 95%</div>
            </div>
            <div className="text-center">
              <div className="text-sm font-bold text-warning">
                {riskMetrics ? formatPercent(riskMetrics.max_position_exposure * 100) : '--'}
              </div>
              <div className="text-xs text-foreground-muted">Exposure</div>
            </div>
            <div className="text-center">
              <div className="text-sm font-bold text-bullish">
                {feedbackStatus?.sharpe_ratio?.toFixed(1) ?? '--'}
              </div>
              <div className="text-xs text-foreground-muted">Sharpe</div>
            </div>
          </div>
        </div>

        <div className="col-span-4 card p-4">
          <div className="chart-header">
            <h3 className="chart-title">Profit Factor by Strategy</h3>
          </div>
          <BarChart horizontal emptyMessage="Strategy data will populate with trading" />
        </div>

        {/* Brain Status Panel */}
        <div className="col-span-6 card p-4">
          <div className="chart-header">
            <h3 className="chart-title flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-400" />
              PropFirm Brain V6
            </h3>
            <div className="flex items-center gap-2">
              <button
                onClick={refresh}
                disabled={isRefreshing}
                className={`p-1 rounded hover:bg-background-tertiary disabled:opacity-50 ${isRefreshing ? 'animate-spin' : ''}`}
              >
                <RefreshCw className="w-4 h-4" />
              </button>
              <span className="text-xs text-foreground-muted">
                {new Date().toLocaleTimeString()}
              </span>
            </div>
          </div>
          {brainStatus ? (
            <div className="space-y-4 mt-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Cpu className={`w-4 h-4 ${brainStatus.device === 'cuda' ? 'text-green-400' : 'text-slate-400'}`} />
                  <span className="text-sm font-medium uppercase">{brainStatus.device}</span>
                </div>
                <div className={`px-2 py-1 rounded text-xs font-medium ${
                  brainStatus.is_trained ? 'bg-green-500/20 text-green-400' : 'bg-amber-500/20 text-amber-400'
                }`}>
                  {brainStatus.is_trained ? 'TRAINED' : 'UNTRAINED'}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-background-tertiary rounded-lg p-3">
                  <div className="text-xs text-foreground-muted">Regime</div>
                  <div className="text-sm font-bold text-cyan-400 capitalize">{brainStatus.current_regime}</div>
                </div>
                <div className="bg-background-tertiary rounded-lg p-3">
                  <div className="text-xs text-foreground-muted">Trades</div>
                  <div className="text-sm font-bold">{brainStatus.total_trades}</div>
                </div>
                <div className="bg-background-tertiary rounded-lg p-3">
                  <div className="text-xs text-foreground-muted">Auto-Train</div>
                  <div className={`text-sm font-bold ${brainStatus.auto_train_enabled ? 'text-green-400' : 'text-slate-400'}`}>
                    {brainStatus.auto_train_enabled ? 'ON' : 'OFF'}
                  </div>
                </div>
              </div>
              {brainStatus.strategies && brainStatus.strategies.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs text-foreground-muted">Top Strategies</div>
                  {brainStatus.strategies.slice(0, 3).map((s, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span>{s.name}</span>
                      <div className="flex items-center gap-3">
                        <span className="text-foreground-muted">{(s.weight * 100).toFixed(0)}%</span>
                        <span className={s.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}>
                          {s.win_rate.toFixed(1)}% WR
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4 mt-4">
              <div className="flex items-center justify-between">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-6 w-20" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="bg-background-tertiary rounded-lg p-3">
                    <Skeleton className="h-3 w-12 mb-2" />
                    <Skeleton className="h-5 w-16" />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Feedback Loop Status */}
        <div className="col-span-6 card p-4">
          <div className="chart-header">
            <h3 className="chart-title flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              Feedback Loop
            </h3>
            {feedbackStatus && (
              <div className={`px-2 py-1 rounded text-xs font-medium ${
                feedbackStatus.is_converged ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
              }`}>
                {feedbackStatus.phase.toUpperCase()}
              </div>
            )}
          </div>
          {feedbackStatus ? (
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-background-tertiary rounded-lg p-3 text-center">
                  <div className="text-xs text-foreground-muted">Win Rate</div>
                  <div className={`text-lg font-bold ${feedbackStatus.win_rate >= 0.65 ? 'text-green-400' : 'text-amber-400'}`}>
                    {(feedbackStatus.win_rate * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="bg-background-tertiary rounded-lg p-3 text-center">
                  <div className="text-xs text-foreground-muted">Profit Factor</div>
                  <div className={`text-lg font-bold ${feedbackStatus.profit_factor >= 1.5 ? 'text-green-400' : 'text-amber-400'}`}>
                    {feedbackStatus.profit_factor.toFixed(2)}
                  </div>
                </div>
                <div className="bg-background-tertiary rounded-lg p-3 text-center">
                  <div className="text-xs text-foreground-muted">Sharpe</div>
                  <div className={`text-lg font-bold ${feedbackStatus.sharpe_ratio >= 1.5 ? 'text-green-400' : 'text-amber-400'}`}>
                    {feedbackStatus.sharpe_ratio.toFixed(2)}
                  </div>
                </div>
                <div className="bg-background-tertiary rounded-lg p-3 text-center">
                  <div className="text-xs text-foreground-muted">Trades</div>
                  <div className="text-lg font-bold">{feedbackStatus.total_trades}</div>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-foreground-muted">Convergence Progress</span>
                  <span className="font-medium">
                    {feedbackStatus.is_converged ? '100%' :
                      Object.values(feedbackStatus.convergence_progress || {}).length > 0
                        ? `${Math.round(Object.values(feedbackStatus.convergence_progress).reduce((a, b) => a + b, 0) / Math.max(1, Object.keys(feedbackStatus.convergence_progress).length) * 100)}%`
                        : '0%'
                    }
                  </span>
                </div>
                <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-green-500 transition-all duration-500"
                    style={{
                      width: feedbackStatus.is_converged ? '100%' :
                        Object.values(feedbackStatus.convergence_progress || {}).length > 0
                          ? `${Object.values(feedbackStatus.convergence_progress).reduce((a, b) => a + b, 0) / Math.max(1, Object.keys(feedbackStatus.convergence_progress).length) * 100}%`
                          : '0%'
                    }}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-4 gap-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="bg-background-tertiary rounded-lg p-3 text-center">
                    <Skeleton className="h-3 w-12 mx-auto mb-2" />
                    <Skeleton className="h-6 w-16 mx-auto" />
                  </div>
                ))}
              </div>
              <Skeleton className="h-2 w-full" />
            </div>
          )}
        </div>

        {/* Active signals table */}
        <div className="col-span-12 card p-4">
          <div className="chart-header">
            <h3 className="chart-title">Active Signals</h3>
            <button className="btn-primary text-xs">Execute All</button>
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
