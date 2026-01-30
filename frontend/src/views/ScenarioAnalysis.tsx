import { useState, useEffect } from 'react'
import { Zap, Play, RefreshCw, AlertCircle, TrendingDown, Clock, History, FlaskConical } from 'lucide-react'
import { cn } from '@/utils/cn'

interface Scenario {
  id: string
  name: string
  description: string
  type: string
  market_shock_pct: number
  vix_level: number
  duration_days: number
}

interface PositionImpact {
  symbol: string
  market_value: number
  sector: string
  shock_pct: number
  pnl: number
}

interface ScenarioResult {
  scenario_id: string
  scenario_name: string
  description: string
  timestamp: string
  portfolio_value_before: number
  portfolio_value_after: number
  total_pnl: number
  total_pnl_pct: number
  worst_position: string
  worst_position_pnl: number
  best_position: string
  best_position_pnl: number
  position_impacts: PositionImpact[]
  vix_level: number
  duration_days: number
}

interface HistoryEntry {
  scenario_id: string
  scenario_name: string
  timestamp: string
  portfolio_value_before: number
  portfolio_value_after: number
  total_pnl: number
  total_pnl_pct: number
}

export function ScenarioAnalysis() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [result, setResult] = useState<ScenarioResult | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'historical' | 'custom'>('historical')

  // Custom stress inputs
  const [customName, setCustomName] = useState('Custom Stress Test')
  const [marketShock, setMarketShock] = useState(-10)
  const [vixSpike, setVixSpike] = useState(50)
  const [rateMove, setRateMove] = useState(0)
  const [corrToOne, setCorrToOne] = useState(false)

  useEffect(() => {
    fetchScenarios()
    fetchHistory()
  }, [])

  const fetchScenarios = async () => {
    setIsLoading(true)
    try {
      const res = await fetch('/api/risk/scenarios')
      const data = await res.json()
      setScenarios(data.scenarios || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch scenarios')
    } finally {
      setIsLoading(false)
    }
  }

  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/risk/scenarios/history')
      const data = await res.json()
      setHistory(data.history || [])
    } catch {
      // silent
    }
  }

  const runScenario = async (scenarioId: string) => {
    setIsRunning(true)
    setError(null)
    try {
      const res = await fetch('/api/risk/scenarios/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId }),
      })
      if (!res.ok) throw new Error(`Scenario failed: ${res.statusText}`)
      const data = await res.json()
      setResult(data)
      fetchHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scenario run failed')
    } finally {
      setIsRunning(false)
    }
  }

  const runCustomStress = async () => {
    setIsRunning(true)
    setError(null)
    try {
      const res = await fetch('/api/risk/scenarios/custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: customName,
          market_shock_pct: marketShock,
          vix_spike_pct: vixSpike,
          rate_move_bps: rateMove,
          correlation_to_one: corrToOne,
        }),
      })
      if (!res.ok) throw new Error(`Stress test failed: ${res.statusText}`)
      const data = await res.json()
      setResult(data)
      fetchHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Custom stress test failed')
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Zap className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">SCENARIO ANALYSIS</h1>
            <p className="text-xs text-foreground-muted">Historical replay & custom stress testing</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('historical')}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded transition-colors',
              activeTab === 'historical'
                ? 'bg-accent-primary/20 text-accent-primary'
                : 'text-foreground-muted hover:text-foreground-primary'
            )}
          >
            Historical Scenarios
          </button>
          <button
            onClick={() => setActiveTab('custom')}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded transition-colors',
              activeTab === 'custom'
                ? 'bg-accent-primary/20 text-accent-primary'
                : 'text-foreground-muted hover:text-foreground-primary'
            )}
          >
            Custom Stress Test
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-12 gap-4">
        {/* Left: Scenario Selection */}
        <div className="col-span-5">
          {activeTab === 'historical' ? (
            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">HISTORICAL SCENARIOS</h3>
              {isLoading ? (
                <div className="flex justify-center py-8">
                  <RefreshCw className="w-6 h-6 animate-spin text-accent-primary" />
                </div>
              ) : scenarios.filter(s => s.type === 'historical').length === 0 ? (
                <p className="text-sm text-foreground-muted py-4">No scenarios available</p>
              ) : (
                <div className="space-y-2">
                  {scenarios.filter(s => s.type === 'historical').map((s) => (
                    <div key={s.id} className="p-3 bg-background-tertiary rounded-lg hover:bg-background-tertiary/80 transition-colors">
                      <div className="flex items-start justify-between mb-1">
                        <span className="text-sm font-medium text-foreground-primary">{s.name}</span>
                        <button
                          onClick={() => runScenario(s.id)}
                          disabled={isRunning}
                          className="flex items-center gap-1 px-2 py-1 bg-accent-primary/20 text-accent-primary text-[10px] font-bold rounded hover:bg-accent-primary/30 transition-colors"
                        >
                          <Play className="w-3 h-3" />
                          RUN
                        </button>
                      </div>
                      <p className="text-[10px] text-foreground-muted mb-2">{s.description}</p>
                      <div className="flex gap-3 text-[10px]">
                        <span className="text-bearish font-mono">MKT: {s.market_shock_pct}%</span>
                        <span className="text-warning font-mono">VIX: {s.vix_level.toFixed(0)}</span>
                        <span className="text-foreground-muted font-mono">
                          <Clock className="w-3 h-3 inline mr-0.5" />
                          {s.duration_days}d
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="card p-4">
              <div className="flex items-center gap-2 mb-3">
                <FlaskConical className="w-4 h-4 text-accent-primary" />
                <h3 className="text-xs font-bold text-foreground-muted">CUSTOM STRESS TEST</h3>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] text-foreground-muted block mb-1">Test Name</label>
                  <input
                    type="text"
                    value={customName}
                    onChange={e => setCustomName(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs bg-background-tertiary border border-border rounded text-foreground-primary"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] text-foreground-muted block mb-1">Market Shock (%)</label>
                    <input
                      type="number"
                      value={marketShock}
                      onChange={e => setMarketShock(Number(e.target.value))}
                      className="w-full px-3 py-1.5 text-xs bg-background-tertiary border border-border rounded text-foreground-primary font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-foreground-muted block mb-1">VIX Spike (%)</label>
                    <input
                      type="number"
                      value={vixSpike}
                      onChange={e => setVixSpike(Number(e.target.value))}
                      className="w-full px-3 py-1.5 text-xs bg-background-tertiary border border-border rounded text-foreground-primary font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-foreground-muted block mb-1">Rate Move (bps)</label>
                    <input
                      type="number"
                      value={rateMove}
                      onChange={e => setRateMove(Number(e.target.value))}
                      className="w-full px-3 py-1.5 text-xs bg-background-tertiary border border-border rounded text-foreground-primary font-mono"
                    />
                  </div>
                  <div className="flex items-end">
                    <label className="flex items-center gap-2 text-xs text-foreground-secondary cursor-pointer">
                      <input
                        type="checkbox"
                        checked={corrToOne}
                        onChange={e => setCorrToOne(e.target.checked)}
                        className="rounded border-border"
                      />
                      Corr → 1
                    </label>
                  </div>
                </div>
                <button
                  onClick={runCustomStress}
                  disabled={isRunning}
                  className="w-full py-2 bg-accent-primary/20 text-accent-primary text-xs font-bold rounded hover:bg-accent-primary/30 transition-colors flex items-center justify-center gap-2"
                >
                  {isRunning ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Zap className="w-4 h-4" />
                  )}
                  RUN STRESS TEST
                </button>
                {/* Presets */}
                <div className="pt-2 border-t border-border">
                  <p className="text-[10px] font-bold text-foreground-muted mb-2">QUICK PRESETS</p>
                  <div className="flex flex-wrap gap-1">
                    {[
                      { label: 'VIX +50%', fn: () => { setMarketShock(-5); setVixSpike(50); setRateMove(0); } },
                      { label: 'Rates +100bps', fn: () => { setMarketShock(0); setVixSpike(10); setRateMove(100); } },
                      { label: 'Rates -100bps', fn: () => { setMarketShock(0); setVixSpike(0); setRateMove(-100); } },
                      { label: 'Flash Crash', fn: () => { setMarketShock(-15); setVixSpike(100); setRateMove(0); } },
                      { label: 'Corr Breakdown', fn: () => { setMarketShock(-10); setVixSpike(30); setRateMove(0); setCorrToOne(true); } },
                    ].map((preset) => (
                      <button
                        key={preset.label}
                        onClick={preset.fn}
                        className="px-2 py-1 text-[10px] bg-background-tertiary text-foreground-muted rounded hover:text-accent-primary transition-colors"
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* History */}
          {history.length > 0 && (
            <div className="card p-4 mt-4">
              <div className="flex items-center gap-2 mb-3">
                <History className="w-4 h-4 text-accent-primary" />
                <h3 className="text-xs font-bold text-foreground-muted">RECENT RUNS</h3>
              </div>
              <div className="space-y-1">
                {history.slice(0, 6).map((h, i) => (
                  <div key={i} className="flex justify-between text-xs py-1">
                    <span className="text-foreground-secondary truncate w-40">{h.scenario_name}</span>
                    <span className={cn('font-mono', h.total_pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                      {h.total_pnl_pct >= 0 ? '+' : ''}{h.total_pnl_pct.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Results */}
        <div className="col-span-7">
          {result ? (
            <div className="space-y-4">
              {/* Summary */}
              <div className="card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingDown className="w-4 h-4 text-bearish" />
                  <h3 className="text-xs font-bold text-foreground-muted">SCENARIO RESULT</h3>
                  <span className="ml-auto text-[10px] text-foreground-muted">{result.scenario_name}</span>
                </div>
                <p className="text-[10px] text-foreground-muted mb-3">{result.description}</p>

                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="p-3 bg-background-tertiary rounded-lg text-center">
                    <p className="text-[10px] text-foreground-muted">Portfolio Impact</p>
                    <p className={cn('text-lg font-bold font-mono', result.total_pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                      {result.total_pnl_pct >= 0 ? '+' : ''}{result.total_pnl_pct.toFixed(1)}%
                    </p>
                    <p className={cn('text-xs font-mono', result.total_pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                      ${result.total_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </p>
                  </div>
                  <div className="p-3 bg-background-tertiary rounded-lg text-center">
                    <p className="text-[10px] text-foreground-muted">Value After</p>
                    <p className="text-lg font-bold font-mono text-foreground-primary">
                      ${result.portfolio_value_after.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </p>
                    <p className="text-xs text-foreground-muted">
                      from ${result.portfolio_value_before.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </p>
                  </div>
                  <div className="p-3 bg-background-tertiary rounded-lg text-center">
                    <p className="text-[10px] text-foreground-muted">VIX / Duration</p>
                    <p className="text-lg font-bold font-mono text-warning">
                      {result.vix_level.toFixed(0)}
                    </p>
                    <p className="text-xs text-foreground-muted">{result.duration_days} days</p>
                  </div>
                </div>

                {/* Worst / Best */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-2 bg-bearish/10 rounded">
                    <p className="text-[10px] text-bearish font-bold">WORST POSITION</p>
                    <p className="text-sm text-foreground-primary">{result.worst_position || 'N/A'}</p>
                    <p className="text-xs font-mono text-bearish">
                      ${result.worst_position_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </p>
                  </div>
                  <div className="p-2 bg-bullish/10 rounded">
                    <p className="text-[10px] text-bullish font-bold">BEST POSITION</p>
                    <p className="text-sm text-foreground-primary">{result.best_position || 'N/A'}</p>
                    <p className="text-xs font-mono text-bullish">
                      ${result.best_position_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </p>
                  </div>
                </div>
              </div>

              {/* Position Impacts Table */}
              {result.position_impacts.length > 0 && (
                <div className="card p-4">
                  <h3 className="text-xs font-bold text-foreground-muted mb-3">POSITION IMPACTS</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-foreground-muted border-b border-border">
                          <th className="text-left py-2 pr-3">Symbol</th>
                          <th className="text-left py-2 pr-3">Sector</th>
                          <th className="text-right py-2 pr-3">Value</th>
                          <th className="text-right py-2 pr-3">Shock</th>
                          <th className="text-right py-2">P&L</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.position_impacts.map((impact, i) => (
                          <tr key={i} className="border-b border-border/50">
                            <td className="py-1.5 pr-3 font-medium text-foreground-primary">{impact.symbol}</td>
                            <td className="py-1.5 pr-3 text-foreground-muted capitalize">{impact.sector.replace(/_/g, ' ')}</td>
                            <td className="py-1.5 pr-3 text-right font-mono text-foreground-secondary">
                              ${impact.market_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </td>
                            <td className={cn('py-1.5 pr-3 text-right font-mono', impact.shock_pct >= 0 ? 'text-bullish' : 'text-bearish')}>
                              {impact.shock_pct >= 0 ? '+' : ''}{impact.shock_pct.toFixed(1)}%
                            </td>
                            <td className={cn('py-1.5 text-right font-mono font-bold', impact.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                              ${impact.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="card p-8 text-center text-foreground-muted">
              <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">No Scenario Results</p>
              <p className="text-sm mt-2">Select a scenario or configure a custom stress test to see portfolio impact</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
