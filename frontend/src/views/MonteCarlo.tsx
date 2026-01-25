import { useState, useEffect } from 'react'
import {
  Dice5,
  RefreshCw,
  AlertCircle,
  Play,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Target,
  Shield,
  Percent,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  ReferenceLine,
} from 'recharts'

interface MonteCarloResult {
  summary: {
    initial_capital: number
    num_simulations: number
    days: number
    expected_return: number
    volatility: number
  }
  results: {
    mean_final_value: number
    median_final_value: number
    min_final_value: number
    max_final_value: number
    std_final_value: number
    percentiles: Record<string, number>
  }
  risk_metrics: {
    var_95: number
    cvar_95: number
    probability_profit: number
    probability_loss_10pct: number
    probability_gain_20pct: number
    expected_shortfall: number
  }
  paths: {
    sample_count: number
    samples: number[][]
    percentiles: Record<string, number[]>
  }
  distribution: {
    bins: number[]
    counts: number[]
  }
  timestamp: string
}

interface Preset {
  name: string
  expected_return: number
  volatility: number
  description: string
}

export function MonteCarlo() {
  const [result, setResult] = useState<MonteCarloResult | null>(null)
  const [presets, setPresets] = useState<Preset[]>([])
  const [isLoading, setIsLoading] = useState(false)

  // Form state
  const [initialCapital, setInitialCapital] = useState(100000)
  const [numSimulations, setNumSimulations] = useState(1000)
  const [days, setDays] = useState(252)
  const [expectedReturn, setExpectedReturn] = useState(0.10)
  const [volatility, setVolatility] = useState(0.20)

  useEffect(() => {
    // Fetch presets
    fetch('/api/monte-carlo/presets')
      .then(r => r.json())
      .then(data => setPresets(data.presets || []))
      .catch(console.error)
  }, [])

  const runSimulation = async () => {
    setIsLoading(true)
    try {
      const response = await fetch(
        `/api/monte-carlo/run?initial_capital=${initialCapital}&num_simulations=${numSimulations}&days=${days}&expected_return=${expectedReturn}&volatility=${volatility}`,
        { method: 'POST' }
      )
      if (response.ok) {
        const data = await response.json()
        setResult(data)
      }
    } catch (error) {
      console.error('Failed to run simulation:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const applyPreset = (preset: Preset) => {
    setExpectedReturn(preset.expected_return)
    setVolatility(preset.volatility)
  }

  // Prepare chart data
  const pathData = result?.paths?.percentiles ?
    result.paths.percentiles.p50?.map((_, i) => ({
      day: i * (result.summary.days / (result.paths.percentiles.p50.length - 1)),
      p5: result.paths.percentiles.p5?.[i] || 0,
      p25: result.paths.percentiles.p25?.[i] || 0,
      p50: result.paths.percentiles.p50?.[i] || 0,
      p75: result.paths.percentiles.p75?.[i] || 0,
      p95: result.paths.percentiles.p95?.[i] || 0,
    })) : []

  const distributionData = result?.distribution?.bins?.map((bin, i) => ({
    value: bin,
    count: result.distribution.counts[i] || 0,
    label: `$${(bin / 1000).toFixed(0)}k`,
  })).slice(0, -1) || []

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Dice5 className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">MONTE CARLO</h1>
            <p className="text-xs text-foreground-muted">Portfolio simulation and risk analysis</p>
          </div>
        </div>
      </div>

      {/* Configuration Panel */}
      <div className="card p-4">
        <h3 className="text-sm font-medium text-foreground-primary mb-4">Simulation Parameters</h3>

        {/* Presets */}
        <div className="flex flex-wrap gap-2 mb-4">
          {presets.map(preset => (
            <button
              key={preset.name}
              onClick={() => applyPreset(preset)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
                expectedReturn === preset.expected_return && volatility === preset.volatility
                  ? 'bg-accent-primary text-background-primary'
                  : 'bg-surface-secondary text-foreground-muted hover:text-foreground-primary'
              )}
              title={preset.description}
            >
              {preset.name}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-5 gap-4">
          <div>
            <label className="block text-xs font-medium text-foreground-muted mb-1">Initial Capital</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-foreground-primary focus:outline-none focus:border-accent-primary"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-foreground-muted mb-1">Simulations</label>
            <input
              type="number"
              value={numSimulations}
              onChange={(e) => setNumSimulations(Number(e.target.value))}
              className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-foreground-primary focus:outline-none focus:border-accent-primary"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-foreground-muted mb-1">Days</label>
            <input
              type="number"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-foreground-primary focus:outline-none focus:border-accent-primary"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-foreground-muted mb-1">Expected Return</label>
            <input
              type="number"
              step="0.01"
              value={expectedReturn}
              onChange={(e) => setExpectedReturn(Number(e.target.value))}
              className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-foreground-primary focus:outline-none focus:border-accent-primary"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-foreground-muted mb-1">Volatility</label>
            <input
              type="number"
              step="0.01"
              value={volatility}
              onChange={(e) => setVolatility(Number(e.target.value))}
              className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-foreground-primary focus:outline-none focus:border-accent-primary"
            />
          </div>
        </div>

        <button
          onClick={runSimulation}
          disabled={isLoading}
          className="btn-primary mt-4 flex items-center gap-2"
        >
          <Play className={cn('w-4 h-4', isLoading && 'animate-pulse')} />
          {isLoading ? 'Running...' : 'Run Simulation'}
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-accent-primary" />
        </div>
      ) : !result ? (
        <div className="card p-8 text-center text-foreground-muted">
          <Dice5 className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">Configure parameters and run simulation</p>
          <p className="text-sm mt-2">Analyze thousands of portfolio scenarios</p>
        </div>
      ) : (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-6 gap-3">
            <StatCard
              label="Mean Final Value"
              value={`$${(result.results.mean_final_value / 1000).toFixed(0)}k`}
              icon={<BarChart3 className="w-4 h-4" />}
            />
            <StatCard
              label="Median Final Value"
              value={`$${(result.results.median_final_value / 1000).toFixed(0)}k`}
              icon={<Target className="w-4 h-4" />}
            />
            <StatCard
              label="VaR 95%"
              value={`$${(result.risk_metrics.var_95 / 1000).toFixed(0)}k`}
              icon={<Shield className="w-4 h-4" />}
              negative
            />
            <StatCard
              label="Prob. Profit"
              value={`${result.risk_metrics.probability_profit}%`}
              icon={<TrendingUp className="w-4 h-4" />}
              positive
            />
            <StatCard
              label="Prob. Loss >10%"
              value={`${result.risk_metrics.probability_loss_10pct}%`}
              icon={<TrendingDown className="w-4 h-4" />}
              negative
            />
            <StatCard
              label="Prob. Gain >20%"
              value={`${result.risk_metrics.probability_gain_20pct}%`}
              icon={<Percent className="w-4 h-4" />}
              positive
            />
          </div>

          {/* Simulation Paths Chart */}
          <div className="card p-4">
            <h3 className="text-sm font-medium text-foreground-primary mb-4">Portfolio Value Projection</h3>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={pathData}>
                  <XAxis
                    dataKey="day"
                    tick={{ fill: '#6b7280', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `Day ${Math.round(v)}`}
                  />
                  <YAxis
                    tick={{ fill: '#6b7280', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                    labelStyle={{ color: '#9ca3af' }}
                    formatter={(value: number, name: string) => [`$${value.toLocaleString()}`, name.toUpperCase()]}
                  />
                  <Area type="monotone" dataKey="p5" stackId="1" stroke="transparent" fill="#ff5252" fillOpacity={0.1} />
                  <Area type="monotone" dataKey="p25" stackId="2" stroke="transparent" fill="#ffa726" fillOpacity={0.2} />
                  <Area type="monotone" dataKey="p75" stackId="3" stroke="transparent" fill="#66bb6a" fillOpacity={0.2} />
                  <Area type="monotone" dataKey="p95" stackId="4" stroke="transparent" fill="#42a5f5" fillOpacity={0.1} />
                  <Line type="monotone" dataKey="p50" stroke="#00d4aa" strokeWidth={2} dot={false} />
                  <ReferenceLine y={initialCapital} stroke="#6b7280" strokeDasharray="3 3" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-4 mt-2 text-xs text-foreground-muted">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#ff5252]/30" /> 5th Percentile</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#ffa726]/40" /> 25th</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-accent-primary" /> Median</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#66bb6a]/40" /> 75th</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#42a5f5]/30" /> 95th Percentile</span>
            </div>
          </div>

          {/* Distribution Chart */}
          <div className="card p-4">
            <h3 className="text-sm font-medium text-foreground-primary mb-4">Final Value Distribution</h3>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distributionData}>
                  <XAxis
                    dataKey="label"
                    tick={{ fill: '#6b7280', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#6b7280', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                    labelStyle={{ color: '#9ca3af' }}
                  />
                  <Bar dataKey="count" fill="#00d4aa" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Percentile Table */}
          <div className="card p-4">
            <h3 className="text-sm font-medium text-foreground-primary mb-4">Outcome Percentiles</h3>
            <div className="grid grid-cols-7 gap-2">
              {Object.entries(result.results.percentiles).map(([key, value]) => (
                <div key={key} className="text-center p-3 bg-surface-secondary rounded-lg">
                  <div className="text-xs text-foreground-muted mb-1">{key.toUpperCase()}</div>
                  <div className="text-sm font-bold text-foreground-primary">
                    ${(value / 1000).toFixed(0)}k
                  </div>
                  <div className={cn(
                    'text-xs font-mono',
                    value >= initialCapital ? 'text-bullish' : 'text-bearish'
                  )}>
                    {value >= initialCapital ? '+' : ''}{((value - initialCapital) / initialCapital * 100).toFixed(1)}%
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Timestamp */}
          <div className="text-xs text-foreground-muted text-center">
            Simulation completed: {new Date(result.timestamp).toLocaleString()}
          </div>
        </>
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
