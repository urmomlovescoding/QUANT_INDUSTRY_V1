import { LineChart, TrendingUp, Activity, BarChart3 } from 'lucide-react'
import { AreaChart } from '@/components/charts/AreaChart'
import { BarChart } from '@/components/charts/BarChart'
import { DonutChart } from '@/components/charts/DonutChart'
import { GaugeChart } from '@/components/charts/GaugeChart'
import { MetricCard } from '@/components/cards/MetricCard'

export function Analytics() {
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
          <select className="text-sm bg-background-tertiary text-foreground-secondary px-3 py-1.5 rounded border border-border">
            <option>All Strategies</option>
            <option>Momentum</option>
            <option>Mean Reversion</option>
            <option>Breakout</option>
          </select>
          <select className="text-sm bg-background-tertiary text-foreground-secondary px-3 py-1.5 rounded border border-border">
            <option>Last 30 Days</option>
            <option>Last 90 Days</option>
            <option>YTD</option>
            <option>All Time</option>
          </select>
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-5 gap-4">
        <MetricCard
          title="Sharpe Ratio"
          value="1.85"
          change={0.12}
          icon={TrendingUp}
          trend="up"
        />
        <MetricCard
          title="Sortino Ratio"
          value="2.34"
          change={0.08}
          icon={Activity}
          trend="up"
        />
        <MetricCard
          title="Max Drawdown"
          value="-8.5%"
          change={-1.2}
          icon={BarChart3}
          trend="up"
          valueColor="bearish"
        />
        <MetricCard
          title="Profit Factor"
          value="2.1x"
          change={0.3}
          icon={TrendingUp}
          trend="up"
        />
        <MetricCard
          title="Calmar Ratio"
          value="3.2"
          change={0.5}
          icon={Activity}
          trend="up"
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
          <AreaChart />
        </div>

        {/* Risk metrics */}
        <div className="col-span-4 space-y-4">
          <div className="card p-4">
            <h3 className="chart-title mb-4">Risk Exposure</h3>
            <div className="flex justify-center">
              <GaugeChart value={42} maxValue={100} label="Current Risk" />
            </div>
          </div>
          <div className="card p-4">
            <h3 className="chart-title mb-4">Sector Allocation</h3>
            <DonutChart
              data={[
                { name: 'Technology', value: 35, color: '#f0b90b' },
                { name: 'Healthcare', value: 20, color: '#00c853' },
                { name: 'Finance', value: 18, color: '#2196f3' },
                { name: 'Consumer', value: 15, color: '#ff9800' },
                { name: 'Other', value: 12, color: '#666666' },
              ]}
              size={140}
            />
          </div>
        </div>

        {/* Monthly returns heatmap */}
        <div className="col-span-6 card p-4">
          <h3 className="chart-title mb-4">Monthly Returns Heatmap</h3>
          <MonthlyHeatmap />
        </div>

        {/* Drawdown chart */}
        <div className="col-span-6 card p-4">
          <h3 className="chart-title mb-4">Drawdown Analysis</h3>
          <BarChart />
        </div>

        {/* Strategy comparison */}
        <div className="col-span-12 card p-4">
          <h3 className="chart-title mb-4">Strategy Comparison</h3>
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
                  <th>Avg Trade</th>
                  <th># Trades</th>
                </tr>
              </thead>
              <tbody>
                <StrategyRow name="Momentum" totalReturn={24.5} winRate={68} profitFactor={2.4} sharpe={1.9} maxDD={-6.2} avgTrade={125} trades={156} />
                <StrategyRow name="Mean Reversion" totalReturn={18.2} winRate={72} profitFactor={1.8} sharpe={1.5} maxDD={-8.5} avgTrade={85} trades={234} />
                <StrategyRow name="Breakout" totalReturn={15.8} winRate={55} profitFactor={1.5} sharpe={1.2} maxDD={-12.1} avgTrade={210} trades={89} />
                <StrategyRow name="Trend Following" totalReturn={12.4} winRate={48} profitFactor={1.3} sharpe={0.9} maxDD={-15.3} avgTrade={320} trades={45} />
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

function MonthlyHeatmap() {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const years = ['2024', '2023', '2022']

  const data = [
    [3.2, -1.5, 4.8, 2.1, -0.8, 3.5, 1.2, -2.3, 4.1, 2.8, -1.1, 3.9],
    [2.1, 3.5, -2.1, 1.8, 4.2, -1.2, 2.9, 3.1, -0.5, 2.4, 1.8, 4.5],
    [-1.2, 2.8, 3.9, -0.3, 1.5, 2.2, -1.8, 3.4, 2.1, -0.9, 3.2, 1.7],
  ]

  const getColor = (value: number) => {
    if (value >= 3) return 'bg-bullish'
    if (value >= 1) return 'bg-bullish/50'
    if (value >= 0) return 'bg-bullish/20'
    if (value >= -1) return 'bg-bearish/20'
    if (value >= -2) return 'bg-bearish/50'
    return 'bg-bearish'
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th className="p-2 text-left text-foreground-muted"></th>
            {months.map((month) => (
              <th key={month} className="p-2 text-center text-foreground-muted font-normal">
                {month}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {years.map((year, yi) => (
            <tr key={year}>
              <td className="p-2 text-foreground-muted">{year}</td>
              {data[yi].map((value, mi) => (
                <td key={mi} className="p-1">
                  <div
                    className={`w-full h-8 rounded flex items-center justify-center font-mono ${getColor(value)}`}
                  >
                    {value > 0 ? '+' : ''}{value.toFixed(1)}%
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface StrategyRowProps {
  name: string
  totalReturn: number
  winRate: number
  profitFactor: number
  sharpe: number
  maxDD: number
  avgTrade: number
  trades: number
}

function StrategyRow({ name, totalReturn, winRate, profitFactor, sharpe, maxDD, avgTrade, trades }: StrategyRowProps) {
  return (
    <tr>
      <td className="font-medium">{name}</td>
      <td className="text-bullish font-mono">+{totalReturn.toFixed(1)}%</td>
      <td className="font-mono">{winRate}%</td>
      <td className="font-mono">{profitFactor.toFixed(1)}x</td>
      <td className="font-mono">{sharpe.toFixed(2)}</td>
      <td className="text-bearish font-mono">{maxDD.toFixed(1)}%</td>
      <td className="font-mono">${avgTrade}</td>
      <td className="font-mono">{trades}</td>
    </tr>
  )
}
