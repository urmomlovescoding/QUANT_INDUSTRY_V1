/**
 * Scenario Analysis View
 * Production-grade scenario/stress testing dashboard
 *
 * Features:
 * - What-if scenarios (bull/bear/crash/recovery)
 * - Custom scenario builder (set % changes for each position)
 * - Impact on portfolio value (Recharts BarChart)
 * - Tail risk analysis
 * - Historical scenario comparison (Recharts ComposedChart)
 * - Position impact waterfall chart
 *
 * APIs: /api/risk/scenarios, /api/risk/scenarios/run, /api/risk/scenarios/custom,
 *        /api/risk/scenarios/history
 */

import { useState, useEffect, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell,
} from 'recharts'
import {
  Zap, Play, RefreshCw, AlertCircle, TrendingDown,
  Clock, History, FlaskConical, Activity,
} from 'lucide-react'
import { cn } from '@/utils/cn'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
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

type TabType = 'historical' | 'custom'
type ResultTab = 'overview' | 'impacts' | 'comparison'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function ScenarioAnalysis() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [result, setResult] = useState<ScenarioResult | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('historical')
  const [resultTab, setResultTab] = useState<ResultTab>('overview')

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
      setResultTab('overview')
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
      setResultTab('overview')
      fetchHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Custom stress test failed')
    } finally {
      setIsRunning(false)
    }
  }

  // ----- Derived: position impact chart data -----
  const impactChartData = useMemo(() => {
    if (!result?.position_impacts?.length) return []
    return [...result.position_impacts]
      .sort((a, b) => a.pnl - b.pnl)
      .map((p) => ({
        symbol: p.symbol,
        pnl: p.pnl,
        pnlPct: p.shock_pct,
        sector: p.sector,
        value: p.market_value,
      }))
  }, [result])

  // ----- Derived: sector impact aggregation -----
  const sectorImpactData = useMemo(() => {
    if (!result?.position_impacts?.length) return []
    const sectorMap: Record<string, number> = {}
    result.position_impacts.forEach((p) => {
      const sector = (p.sector || 'Unknown').replace(/_/g, ' ')
      sectorMap[sector] = (sectorMap[sector] || 0) + p.pnl
    })
    return Object.entries(sectorMap)
      .map(([name, pnl]) => ({ name, pnl }))
      .sort((a, b) => a.pnl - b.pnl)
  }, [result])

  // ----- Derived: history chart data -----
  const historyChartData = useMemo(() => {
    return history.slice(0, 12).reverse().map((h) => ({
      name: h.scenario_name.length > 15 ? h.scenario_name.slice(0, 15) + '...' : h.scenario_name,
      fullName: h.scenario_name,
      pnlPct: h.total_pnl_pct,
      pnl: h.total_pnl,
    }))
  }, [history])

  const resultTabs: { id: ResultTab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'impacts', label: 'Position Impacts' },
    { id: 'comparison', label: 'History' },
  ]

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
        <div className="flex gap-1">
          <button
            onClick={() => setActiveTab('historical')}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded transition-colors',
              activeTab === 'historical'
                ? 'bg-accent-primary/20 text-accent-primary'
                : 'text-foreground-muted hover:text-foreground-primary'
            )}
          >
            Historical
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
            Custom Stress
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-bearish" />
            <p className="text-bearish text-sm">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="mt-2 text-xs text-accent-primary hover:underline">Dismiss</button>
        </div>
      )}

      <div className="grid grid-cols-12 gap-4">
        {/* ---- Left Panel: Scenario Selection ---- */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          {activeTab === 'historical' ? (
            <div className="card p-4">
              <h3 className="text-[10px] font-bold text-foreground-muted mb-3">HISTORICAL SCENARIOS</h3>
              {isLoading ? (
                <div className="flex justify-center py-8">
                  <RefreshCw className="w-6 h-6 animate-spin text-accent-primary" />
                </div>
              ) : scenarios.filter((s) => s.type === 'historical').length === 0 ? (
                <div className="text-center py-8 text-foreground-muted">
                  <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No scenarios available</p>
                  <button onClick={fetchScenarios} className="mt-2 text-xs text-accent-primary hover:underline">Retry</button>
                </div>
              ) : (
                <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                  {scenarios.filter((s) => s.type === 'historical').map((s) => (
                    <div
                      key={s.id}
                      className="p-3 bg-background-tertiary rounded-lg hover:ring-1 hover:ring-accent-primary/30 transition-all"
                    >
                      <div className="flex items-start justify-between mb-1">
                        <span className="text-sm font-medium text-foreground-primary">{s.name}</span>
                        <button
                          onClick={() => runScenario(s.id)}
                          disabled={isRunning}
                          className="flex items-center gap-1 px-2 py-1 bg-accent-primary/20 text-accent-primary text-[10px] font-bold rounded hover:bg-accent-primary/30 transition-colors"
                        >
                          {isRunning ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                          RUN
                        </button>
                      </div>
                      <p className="text-[10px] text-foreground-muted mb-2">{s.description}</p>
                      <div className="flex gap-3 text-[10px]">
                        <span className="text-bearish font-mono flex items-center gap-0.5">
                          <TrendingDown className="w-3 h-3" />
                          MKT: {s.market_shock_pct}%
                        </span>
                        <span className="text-warning font-mono flex items-center gap-0.5">
                          <Activity className="w-3 h-3" />
                          VIX: {s.vix_level.toFixed(0)}
                        </span>
                        <span className="text-foreground-muted font-mono flex items-center gap-0.5">
                          <Clock className="w-3 h-3" />
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
                <h3 className="text-[10px] font-bold text-foreground-muted">CUSTOM STRESS TEST</h3>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] text-foreground-muted block mb-1">Test Name</label>
                  <input
                    type="text"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs bg-background-tertiary border border-border rounded text-foreground-primary focus:outline-none focus:border-accent-primary"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] text-foreground-muted block mb-1">Market Shock (%)</label>
                    <input
                      type="number"
                      value={marketShock}
                      onChange={(e) => setMarketShock(Number(e.target.value))}
                      className="w-full px-3 py-1.5 text-xs bg-background-tertiary border border-border rounded text-foreground-primary font-mono focus:outline-none focus:border-accent-primary"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-foreground-muted block mb-1">VIX Spike (%)</label>
                    <input
                      type="number"
                      value={vixSpike}
                      onChange={(e) => setVixSpike(Number(e.target.value))}
                      className="w-full px-3 py-1.5 text-xs bg-background-tertiary border border-border rounded text-foreground-primary font-mono focus:outline-none focus:border-accent-primary"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-foreground-muted block mb-1">Rate Move (bps)</label>
                    <input
                      type="number"
                      value={rateMove}
                      onChange={(e) => setRateMove(Number(e.target.value))}
                      className="w-full px-3 py-1.5 text-xs bg-background-tertiary border border-border rounded text-foreground-primary font-mono focus:outline-none focus:border-accent-primary"
                    />
                  </div>
                  <div className="flex items-end">
                    <label className="flex items-center gap-2 text-xs text-foreground-secondary cursor-pointer">
                      <input
                        type="checkbox"
                        checked={corrToOne}
                        onChange={(e) => setCorrToOne(e.target.checked)}
                        className="rounded border-border"
                      />
                      Corr -{'>'} 1
                    </label>
                  </div>
                </div>

                {/* Visual indicator of stress severity */}
                <div className="p-3 bg-background-tertiary rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold text-foreground-muted">STRESS SEVERITY</span>
                    <span className={cn(
                      'text-[10px] font-bold',
                      Math.abs(marketShock) >= 20 ? 'text-bearish' :
                      Math.abs(marketShock) >= 10 ? 'text-warning' : 'text-foreground-secondary'
                    )}>
                      {Math.abs(marketShock) >= 20 ? 'EXTREME' :
                       Math.abs(marketShock) >= 10 ? 'SEVERE' :
                       Math.abs(marketShock) >= 5 ? 'MODERATE' : 'MILD'}
                    </span>
                  </div>
                  <div className="h-2 bg-background-primary rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all',
                        Math.abs(marketShock) >= 20 ? 'bg-bearish' :
                        Math.abs(marketShock) >= 10 ? 'bg-warning' : 'bg-bullish'
                      )}
                      style={{ width: `${Math.min(100, Math.abs(marketShock) * 3)}%` }}
                    />
                  </div>
                </div>

                <button
                  onClick={runCustomStress}
                  disabled={isRunning}
                  className="w-full py-2.5 bg-accent-primary/20 text-accent-primary text-xs font-bold rounded-lg hover:bg-accent-primary/30 transition-colors flex items-center justify-center gap-2"
                >
                  {isRunning ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Zap className="w-4 h-4" />
                  )}
                  RUN STRESS TEST
                </button>

                {/* Quick Presets */}
                <div className="pt-3 border-t border-border">
                  <p className="text-[10px] font-bold text-foreground-muted mb-2">QUICK PRESETS</p>
                  <div className="flex flex-wrap gap-1">
                    {[
                      { label: 'VIX +50%', fn: () => { setMarketShock(-5); setVixSpike(50); setRateMove(0); setCorrToOne(false) } },
                      { label: 'Rates +100bps', fn: () => { setMarketShock(0); setVixSpike(10); setRateMove(100); setCorrToOne(false) } },
                      { label: 'Rates -100bps', fn: () => { setMarketShock(0); setVixSpike(0); setRateMove(-100); setCorrToOne(false) } },
                      { label: 'Flash Crash', fn: () => { setMarketShock(-15); setVixSpike(100); setRateMove(0); setCorrToOne(false) } },
                      { label: 'Black Swan', fn: () => { setMarketShock(-25); setVixSpike(150); setRateMove(50); setCorrToOne(true) } },
                      { label: 'Corr Breakdown', fn: () => { setMarketShock(-10); setVixSpike(30); setRateMove(0); setCorrToOne(true) } },
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

          {/* Run History */}
          {history.length > 0 && (
            <div className="card p-4">
              <div className="flex items-center gap-2 mb-3">
                <History className="w-4 h-4 text-accent-primary" />
                <h3 className="text-[10px] font-bold text-foreground-muted">RECENT RUNS</h3>
              </div>
              <div className="space-y-1 max-h-[200px] overflow-y-auto">
                {history.slice(0, 8).map((h, i) => (
                  <div key={i} className="flex justify-between items-center text-xs py-1.5 px-2 bg-background-tertiary/50 rounded hover:bg-background-tertiary transition-colors">
                    <span className="text-foreground-secondary truncate max-w-[160px]">{h.scenario_name}</span>
                    <span className={cn('font-mono font-bold', h.total_pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                      {h.total_pnl_pct >= 0 ? '+' : ''}{h.total_pnl_pct.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ---- Right Panel: Results ---- */}
        <div className="col-span-12 lg:col-span-8">
          {result ? (
            <div className="space-y-4">
              {/* Result Tabs */}
              <div className="flex gap-1">
                {resultTabs.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setResultTab(t.id)}
                    className={cn(
                      'px-3 py-1.5 text-xs font-medium rounded transition-colors',
                      resultTab === t.id
                        ? 'bg-accent-primary/20 text-accent-primary'
                        : 'text-foreground-muted hover:text-foreground-primary'
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {/* ===== OVERVIEW ===== */}
              {resultTab === 'overview' && (
                <div className="space-y-4">
                  {/* Summary Cards */}
                  <div className="card p-4">
                    <div className="flex items-center gap-2 mb-4">
                      <TrendingDown className="w-4 h-4 text-bearish" />
                      <h3 className="text-xs font-bold text-foreground-muted">SCENARIO RESULT</h3>
                      <span className="ml-auto text-[10px] text-foreground-muted">{result.scenario_name}</span>
                    </div>
                    <p className="text-[10px] text-foreground-muted mb-4">{result.description}</p>

                    <div className="grid grid-cols-3 gap-3 mb-4">
                      <div className="p-3 bg-background-tertiary rounded-lg text-center">
                        <p className="text-[10px] text-foreground-muted">Portfolio Impact</p>
                        <p className={cn('text-2xl font-bold font-mono', result.total_pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                          {result.total_pnl_pct >= 0 ? '+' : ''}{result.total_pnl_pct.toFixed(1)}%
                        </p>
                        <p className={cn('text-xs font-mono', result.total_pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                          ${result.total_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </p>
                      </div>
                      <div className="p-3 bg-background-tertiary rounded-lg text-center">
                        <p className="text-[10px] text-foreground-muted">Value After</p>
                        <p className="text-2xl font-bold font-mono text-foreground-primary">
                          ${(result.portfolio_value_after / 1000).toFixed(1)}K
                        </p>
                        <p className="text-[10px] text-foreground-muted">
                          from ${(result.portfolio_value_before / 1000).toFixed(1)}K
                        </p>
                      </div>
                      <div className="p-3 bg-background-tertiary rounded-lg text-center">
                        <p className="text-[10px] text-foreground-muted">VIX / Duration</p>
                        <p className="text-2xl font-bold font-mono text-warning">
                          {result.vix_level.toFixed(0)}
                        </p>
                        <p className="text-[10px] text-foreground-muted">{result.duration_days} days</p>
                      </div>
                    </div>

                    {/* Worst/Best */}
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 bg-bearish/10 rounded-lg">
                        <p className="text-[10px] text-bearish font-bold mb-1">WORST POSITION</p>
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-bold text-foreground-primary">{result.worst_position || 'N/A'}</span>
                          <span className="text-xs font-mono text-bearish font-bold">
                            ${result.worst_position_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                          </span>
                        </div>
                      </div>
                      <div className="p-3 bg-bullish/10 rounded-lg">
                        <p className="text-[10px] text-bullish font-bold mb-1">BEST POSITION</p>
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-bold text-foreground-primary">{result.best_position || 'N/A'}</span>
                          <span className="text-xs font-mono text-bullish font-bold">
                            ${result.best_position_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Sector Impact Chart */}
                  {sectorImpactData.length > 0 && (
                    <div className="card p-4">
                      <h3 className="text-xs font-bold text-foreground-muted mb-3">SECTOR IMPACT</h3>
                      <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={sectorImpactData} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                          <XAxis
                            type="number"
                            tick={{ fill: '#6b7280', fontSize: 10 }}
                            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
                          />
                          <YAxis
                            type="category"
                            dataKey="name"
                            tick={{ fill: '#9ca3af', fontSize: 10 }}
                            width={90}
                          />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
                            formatter={(v: number) => [`$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 'P&L']}
                          />
                          <ReferenceLine x={0} stroke="rgba(255,255,255,0.15)" />
                          <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
                            {sectorImpactData.map((entry, i) => (
                              <Cell key={i} fill={entry.pnl >= 0 ? 'rgba(0, 200, 83, 0.6)' : 'rgba(255, 82, 82, 0.6)'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              )}

              {/* ===== POSITION IMPACTS ===== */}
              {resultTab === 'impacts' && (
                <div className="space-y-4">
                  {/* Position Impact Waterfall Chart */}
                  {impactChartData.length > 0 && (
                    <div className="card p-4">
                      <h3 className="text-xs font-bold text-foreground-muted mb-3">POSITION P&L IMPACT</h3>
                      <ResponsiveContainer width="100%" height={Math.max(250, impactChartData.length * 32)}>
                        <BarChart data={impactChartData} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                          <XAxis
                            type="number"
                            tick={{ fill: '#6b7280', fontSize: 10 }}
                            tickFormatter={(v) => `$${(v / 1000).toFixed(1)}K`}
                          />
                          <YAxis
                            type="category"
                            dataKey="symbol"
                            tick={{ fill: '#00d4aa', fontSize: 11, fontWeight: 700 }}
                            width={55}
                          />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
                            formatter={(v: number, name: string) => {
                              if (name === 'pnl') return [`$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, 'P&L']
                              return [v, name]
                            }}
                          />
                          <ReferenceLine x={0} stroke="rgba(255,255,255,0.15)" />
                          <Bar dataKey="pnl" name="P&L" radius={[0, 4, 4, 0]}>
                            {impactChartData.map((entry, i) => (
                              <Cell
                                key={i}
                                fill={entry.pnl >= 0 ? 'rgba(0, 200, 83, 0.7)' : 'rgba(255, 82, 82, 0.7)'}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Position Table */}
                  {result.position_impacts.length > 0 && (
                    <div className="card p-4">
                      <h3 className="text-xs font-bold text-foreground-muted mb-3">POSITION IMPACT DETAILS</h3>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-foreground-muted border-b border-border">
                              <th className="text-left py-2 pr-3">Symbol</th>
                              <th className="text-left py-2 pr-3">Sector</th>
                              <th className="text-right py-2 pr-3">Market Value</th>
                              <th className="text-right py-2 pr-3">Shock %</th>
                              <th className="text-right py-2">P&L</th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.position_impacts.map((impact, i) => (
                              <tr key={i} className="border-b border-border/30 hover:bg-background-tertiary/50 transition-colors">
                                <td className="py-2 pr-3 font-bold text-accent-primary">{impact.symbol}</td>
                                <td className="py-2 pr-3 text-foreground-muted capitalize">{impact.sector.replace(/_/g, ' ')}</td>
                                <td className="py-2 pr-3 text-right font-mono text-foreground-secondary">
                                  ${impact.market_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                </td>
                                <td className={cn('py-2 pr-3 text-right font-mono font-bold', impact.shock_pct >= 0 ? 'text-bullish' : 'text-bearish')}>
                                  {impact.shock_pct >= 0 ? '+' : ''}{impact.shock_pct.toFixed(1)}%
                                </td>
                                <td className={cn('py-2 text-right font-mono font-bold', impact.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
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
              )}

              {/* ===== HISTORY COMPARISON ===== */}
              {resultTab === 'comparison' && (
                <div className="space-y-4">
                  {historyChartData.length > 0 ? (
                    <div className="card p-4">
                      <h3 className="text-xs font-bold text-foreground-muted mb-3">SCENARIO COMPARISON (RECENT RUNS)</h3>
                      <ResponsiveContainer width="100%" height={380}>
                        <BarChart data={historyChartData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                          <XAxis
                            dataKey="name"
                            tick={{ fill: '#6b7280', fontSize: 9 }}
                            angle={-25}
                            textAnchor="end"
                            height={80}
                          />
                          <YAxis
                            tick={{ fill: '#6b7280', fontSize: 10 }}
                            tickFormatter={(v) => `${v.toFixed(0)}%`}
                            width={45}
                          />
                          <Tooltip
                            contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
                            labelFormatter={(label, payload) => {
                              const item = payload?.[0]?.payload
                              return item?.fullName || label
                            }}
                            formatter={(v: number, name: string) => {
                              if (name === 'pnlPct') return [`${v.toFixed(1)}%`, 'P&L %']
                              return [v, name]
                            }}
                          />
                          <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" />
                          <Bar dataKey="pnlPct" name="P&L %" radius={[4, 4, 0, 0]}>
                            {historyChartData.map((entry, i) => (
                              <Cell
                                key={i}
                                fill={entry.pnlPct >= 0 ? 'rgba(0, 200, 83, 0.6)' : 'rgba(255, 82, 82, 0.6)'}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="card p-8 text-center text-foreground-muted">
                      <History className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">No historical runs to compare</p>
                      <p className="text-[10px] mt-1">Run multiple scenarios to see them compared here</p>
                    </div>
                  )}

                  {/* Tail Risk Summary */}
                  {history.length >= 3 && (
                    <div className="card p-4">
                      <h3 className="text-xs font-bold text-foreground-muted mb-3">TAIL RISK SUMMARY</h3>
                      <div className="grid grid-cols-4 gap-3">
                        <TailStat
                          label="Worst Case"
                          value={`${Math.min(...history.map((h) => h.total_pnl_pct)).toFixed(1)}%`}
                          scenario={history.reduce((worst, h) => h.total_pnl_pct < worst.total_pnl_pct ? h : worst, history[0]).scenario_name}
                          negative
                        />
                        <TailStat
                          label="Best Case"
                          value={`${Math.max(...history.map((h) => h.total_pnl_pct)).toFixed(1)}%`}
                          scenario={history.reduce((best, h) => h.total_pnl_pct > best.total_pnl_pct ? h : best, history[0]).scenario_name}
                          positive
                        />
                        <TailStat
                          label="Average Impact"
                          value={`${(history.reduce((s, h) => s + h.total_pnl_pct, 0) / history.length).toFixed(1)}%`}
                          scenario={`across ${history.length} scenarios`}
                        />
                        <TailStat
                          label="Max $ Loss"
                          value={`$${Math.abs(Math.min(...history.map((h) => h.total_pnl))).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                          scenario="single scenario"
                          negative
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            /* Empty State */
            <div className="card p-12 text-center text-foreground-muted">
              <div className="w-16 h-16 bg-background-tertiary rounded-full flex items-center justify-center mx-auto mb-4">
                <Zap className="w-8 h-8 text-foreground-muted" />
              </div>
              <h3 className="text-lg font-bold text-foreground-primary mb-2">No Scenario Results</h3>
              <p className="text-sm text-foreground-muted max-w-md mx-auto">
                Select a historical scenario or configure a custom stress test to see the impact on your portfolio positions and risk metrics.
              </p>
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
function TailStat({ label, value, scenario, positive, negative }: {
  label: string
  value: string
  scenario: string
  positive?: boolean
  negative?: boolean
}) {
  return (
    <div className="p-3 bg-background-tertiary rounded-lg">
      <p className="text-[10px] text-foreground-muted font-bold mb-1">{label}</p>
      <p className={cn(
        'text-lg font-bold font-mono',
        positive ? 'text-bullish' : negative ? 'text-bearish' : 'text-foreground-primary'
      )}>
        {value}
      </p>
      <p className="text-[10px] text-foreground-muted truncate" title={scenario}>{scenario}</p>
    </div>
  )
}
