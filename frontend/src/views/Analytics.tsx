import { useState, useEffect } from 'react'
import { LineChart, TrendingUp, Activity, BarChart3, RefreshCw, AlertCircle } from 'lucide-react'
import { AreaChart } from '@/components/charts/AreaChart'
import { DonutChart } from '@/components/charts/DonutChart'
import { GaugeChart } from '@/components/charts/GaugeChart'
import { MetricCard } from '@/components/cards/MetricCard'
import { cn } from '@/utils/cn'

interface PerformanceMetrics {
  annual_return: number
  volatility: number
  sharpe_ratio: number
  sortino_ratio: number
  beta: number
  alpha: number
  max_drawdown: number
  var_95: number
  calmar_ratio: number
  information_ratio: number
  status?: string
}

interface Strategy {
  id: string
  name: string
  performance: {
    totalReturn: number
    sharpeRatio: number
    maxDrawdown: number
    winRate: number
    profitFactor: number
    tradesCount: number
  }
}

export function Analytics() {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null)
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [period, setPeriod] = useState('30d')

  const fetchData = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const [metricsRes, strategiesRes] = await Promise.all([
        fetch('/api/portfolio/performance'),
        fetch('/api/quant/strategies')
      ])

      const metricsData = await metricsRes.json()
      const strategiesData = await strategiesRes.json()

      if (metricsData.status === 'unavailable') {
        setMetrics(null)
      } else {
        setMetrics(metricsData)
      }

      if (Array.isArray(strategiesData)) {
        setStrategies(strategiesData)
      } else {
        setStrategies([])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch analytics')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [period])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <LineChart className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground-primary">Analytics Dashboard</h1>
            <p className="text-sm text-foreground-muted">Strategy performance and risk metrics</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="text-sm bg-background-tertiary text-foreground-secondary px-3 py-1.5 rounded border border-border"
          >
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
            <option value="ytd">YTD</option>
            <option value="all">All Time</option>
          </select>
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
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-accent-primary" />
        </div>
      ) : !metrics ? (
        <div className="card p-8 text-center text-foreground-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">No Analytics Data Available</p>
          <p className="text-sm mt-2">Analytics will populate once you have trading history</p>
        </div>
      ) : (
        <>
          {/* Key metrics */}
          <div className="grid grid-cols-5 gap-4">
            <MetricCard
              title="Sharpe Ratio"
              value={metrics.sharpe_ratio?.toFixed(2) ?? 'N/A'}
              icon={TrendingUp}
              trend={metrics.sharpe_ratio > 1 ? 'up' : 'down'}
              isLoading={isLoading}
            />
            <MetricCard
              title="Sortino Ratio"
              value={metrics.sortino_ratio?.toFixed(2) ?? 'N/A'}
              icon={Activity}
              trend={metrics.sortino_ratio > 1 ? 'up' : 'down'}
              isLoading={isLoading}
            />
            <MetricCard
              title="Max Drawdown"
              value={metrics.max_drawdown !== null ? `${metrics.max_drawdown.toFixed(1)}%` : 'N/A'}
              icon={BarChart3}
              trend="down"
              valueColor="bearish"
              isLoading={isLoading}
            />
            <MetricCard
              title="Annual Return"
              value={metrics.annual_return !== null ? `${metrics.annual_return.toFixed(1)}%` : 'N/A'}
              icon={TrendingUp}
              trend={metrics.annual_return > 0 ? 'up' : 'down'}
              isLoading={isLoading}
            />
            <MetricCard
              title="Calmar Ratio"
              value={metrics.calmar_ratio?.toFixed(2) ?? 'N/A'}
              icon={Activity}
              trend={metrics.calmar_ratio > 1 ? 'up' : 'down'}
              isLoading={isLoading}
            />
          </div>

          {/* Charts grid */}
          <div className="grid grid-cols-12 gap-4">
            {/* Equity curve */}
            <div className="col-span-8 card p-4">
              <div className="chart-header">
                <h3 className="chart-title">Cumulative Returns</h3>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-foreground-muted flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-accent-primary" />
                    Strategy
                  </span>
                  <span className="text-xs text-foreground-muted flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-foreground-muted" />
                    SPY Benchmark
                  </span>
                </div>
              </div>
              <AreaChart emptyMessage="Returns data will populate with trading history" />
            </div>

            {/* Risk metrics */}
            <div className="col-span-4 space-y-4">
              <div className="card p-4">
                <h3 className="chart-title mb-4">Risk Exposure</h3>
                <div className="flex justify-center">
                  <GaugeChart value={Math.abs(metrics.var_95 || 0) * 10} maxValue={100} label="VaR 95%" />
                </div>
              </div>
              <div className="card p-4">
                <h3 className="chart-title mb-4">Risk Metrics</h3>
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-foreground-muted">Beta</span>
                    <span className="font-mono">{metrics.beta?.toFixed(2) ?? 'N/A'}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-foreground-muted">Alpha</span>
                    <span className="font-mono">{metrics.alpha?.toFixed(2) ?? 'N/A'}%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-foreground-muted">Volatility</span>
                    <span className="font-mono">{metrics.volatility?.toFixed(1) ?? 'N/A'}%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-foreground-muted">VaR 95%</span>
                    <span className="font-mono text-bearish">{metrics.var_95?.toFixed(1) ?? 'N/A'}%</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Strategy comparison */}
            <div className="col-span-12 card p-4">
              <h3 className="chart-title mb-4">Strategy Comparison</h3>
              {strategies.length === 0 ? (
                <div className="p-8 text-center text-foreground-muted">
                  <p>No strategy data available</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Strategy</th>
                        <th>Total Return</th>
                        <th>Win Rate</th>
                        <th>Profit Factor</th>
                        <th>Sharpe</th>
                        <th>Max DD</th>
                        <th># Trades</th>
                      </tr>
                    </thead>
                    <tbody>
                      {strategies.map((strategy) => (
                        <tr key={strategy.id}>
                          <td className="font-medium">{strategy.name}</td>
                          <td className={cn(
                            'font-mono',
                            strategy.performance.totalReturn >= 0 ? 'text-bullish' : 'text-bearish'
                          )}>
                            {strategy.performance.totalReturn >= 0 ? '+' : ''}{strategy.performance.totalReturn.toFixed(1)}%
                          </td>
                          <td className="font-mono">{strategy.performance.winRate.toFixed(1)}%</td>
                          <td className="font-mono">{strategy.performance.profitFactor.toFixed(2)}x</td>
                          <td className="font-mono">{strategy.performance.sharpeRatio.toFixed(2)}</td>
                          <td className="text-bearish font-mono">{strategy.performance.maxDrawdown.toFixed(1)}%</td>
                          <td className="font-mono">{strategy.performance.tradesCount}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
