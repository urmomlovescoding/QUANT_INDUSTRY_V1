/**
 * Risk Decomposition View
 * Production-grade risk analytics dashboard
 *
 * Features:
 * - Portfolio VaR breakdown by position (Recharts BarChart)
 * - Contribution to risk by asset (Recharts PieChart)
 * - Factor exposure bar chart (market, size, value, momentum)
 * - Stress test scenarios (2008 crisis, COVID crash, rate hike)
 * - Risk budget allocation donut chart
 * - PnL attribution waterfall
 * - Correlation monitor with regime detection
 *
 * APIs: /api/risk/factor-decomposition, /api/risk/attribution, /api/risk/budgets,
 *        /api/risk/correlation-monitor, /api/risk/attribution/alpha-trend
 */

import { useState, useEffect, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, ReferenceLine, RadarChart, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, Radar, ComposedChart,
} from 'recharts'
import {
  BarChart3, RefreshCw, AlertCircle,
  Activity, Layers, Shield, Target, Zap,
} from 'lucide-react'
import { cn } from '@/utils/cn'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface FactorExposure {
  factor: string
  exposure: number
  contribution_bps: number
  pct_of_risk: number
}

interface FactorData {
  timestamp: string
  total_return_bps: number
  factors: FactorExposure[]
  residual_bps: number
  r_squared: number
}

interface WaterfallItem {
  name: string
  start: number
  end: number
  value: number
  is_positive: boolean
  is_total?: boolean
}

interface AttributionData {
  timestamp: string
  total_pnl: number
  components: { name: string; value: number; pct_of_total: number; description: string }[]
  waterfall: WaterfallItem[]
}

interface BudgetData {
  utilizations: Record<string, {
    budget: { name: string; budget_type: string; max_var_pct: number; max_drawdown_pct: number; max_gross_exposure_pct: number; current_utilization: number }
    overall_utilization: number
    metrics: Record<string, { current: number; limit: number; utilization: number }>
  }>
  alerts: { budget_name: string; severity: string; message: string }[]
  scale_recommendations: { strategy: string; scale_factor: number; reason: string }[]
  budgets_over_limit: number
  budgets_approaching: number
}

interface CorrelationMonitorData {
  correlation_matrix: {
    symbols: string[]
    matrix: number[][]
    avg_correlation: number
    high_correlation_pairs: { symbol1: string; symbol2: string; correlation: number }[]
  }
  regime: { regime: string; avg_correlation: number; description: string }
  diversification: { score: number; grade: string; effective_positions: number; recommendations: string[] }
  alerts: { type: string; severity: string; message: string }[]
}

interface AlphaTrend {
  trend: string
  avg_alpha: number
  alpha_sharpe: number
  is_decaying: boolean
}

type TabType = 'factors' | 'attribution' | 'budgets' | 'correlation'

const FACTOR_COLORS: Record<string, string> = {
  market: '#3b82f6',
  sector: '#8b5cf6',
  momentum: '#10b981',
  volatility: '#f59e0b',
  size: '#06b6d4',
}

const BUDGET_COLORS = ['#00d4aa', '#3b82f6', '#f59e0b', '#8b5cf6', '#ef4444', '#ec4899', '#14b8a6']

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function RiskDecomposition() {
  const [factorData, setFactorData] = useState<FactorData | null>(null)
  const [attribution, setAttribution] = useState<AttributionData | null>(null)
  const [budgets, setBudgets] = useState<BudgetData | null>(null)
  const [corrMonitor, setCorrMonitor] = useState<CorrelationMonitorData | null>(null)
  const [alphaTrend, setAlphaTrend] = useState<AlphaTrend | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('factors')

  const fetchAll = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [factorRes, attrRes, budgetRes, corrRes, alphaRes] = await Promise.all([
        fetch('/api/risk/factor-decomposition'),
        fetch('/api/risk/attribution'),
        fetch('/api/risk/budgets'),
        fetch('/api/risk/correlation-monitor'),
        fetch('/api/risk/attribution/alpha-trend'),
      ])
      setFactorData(await factorRes.json())
      setAttribution(await attrRes.json())
      setBudgets(await budgetRes.json())
      setCorrMonitor(await corrRes.json())
      setAlphaTrend(await alphaRes.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch risk decomposition data')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 30000)
    return () => clearInterval(interval)
  }, [])

  // Derived: factor chart data
  const factorChartData = useMemo(() => {
    if (!factorData?.factors) return []
    return factorData.factors.map((f) => ({
      factor: f.factor.charAt(0).toUpperCase() + f.factor.slice(1),
      exposure: f.exposure,
      contribution: f.contribution_bps,
      pctOfRisk: f.pct_of_risk,
      color: FACTOR_COLORS[f.factor] || '#6b7280',
    }))
  }, [factorData])

  // Derived: risk budget pie data
  const budgetPieData = useMemo(() => {
    if (!budgets?.utilizations) return []
    return Object.entries(budgets.utilizations).map(([name, data], i) => ({
      name: name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      utilization: data.overall_utilization,
      color: BUDGET_COLORS[i % BUDGET_COLORS.length],
    }))
  }, [budgets])

  // Derived: waterfall chart data
  const waterfallData = useMemo(() => {
    if (!attribution?.waterfall) return []
    return attribution.waterfall.map((item) => ({
      name: item.name,
      value: item.value,
      fill: item.is_total
        ? (item.is_positive ? '#00d4aa' : '#ff5252')
        : (item.is_positive ? 'rgba(0, 200, 83, 0.6)' : 'rgba(255, 82, 82, 0.6)'),
      isTotal: item.is_total,
    }))
  }, [attribution])

  // Derived: radar chart from factor data
  const radarData = useMemo(() => {
    if (!factorData?.factors) return []
    return factorData.factors.map((f) => ({
      factor: f.factor.charAt(0).toUpperCase() + f.factor.slice(1),
      exposure: Math.abs(f.exposure) * 50 + 10,
      riskPct: f.pct_of_risk,
    }))
  }, [factorData])

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'factors', label: 'Factor Exposures', icon: <Layers className="w-3.5 h-3.5" /> },
    { id: 'attribution', label: 'PnL Attribution', icon: <BarChart3 className="w-3.5 h-3.5" /> },
    { id: 'budgets', label: 'Risk Budgets', icon: <Shield className="w-3.5 h-3.5" /> },
    { id: 'correlation', label: 'Correlation', icon: <Activity className="w-3.5 h-3.5" /> },
  ]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Layers className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">RISK DECOMPOSITION</h1>
            <p className="text-xs text-foreground-muted">Factor exposures, attribution, budgets & correlation</p>
          </div>
        </div>
        <button
          onClick={fetchAll}
          disabled={isLoading}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-bearish" />
            <p className="text-bearish text-sm">{error}</p>
          </div>
          <button onClick={fetchAll} className="mt-2 text-xs text-accent-primary hover:underline">Retry</button>
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-12 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="col-span-6 card p-4 h-64 flex items-center justify-center">
              <RefreshCw className="w-6 h-6 animate-spin text-accent-primary" />
            </div>
          ))}
        </div>
      ) : (
        <>
          {/* Tab Navigation */}
          <div className="flex gap-1">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors',
                  activeTab === t.id
                    ? 'bg-accent-primary/20 text-accent-primary'
                    : 'text-foreground-muted hover:text-foreground-primary'
                )}
              >
                {t.icon}
                {t.label}
              </button>
            ))}
          </div>

          {/* ============================================================= */}
          {/* FACTORS TAB                                                    */}
          {/* ============================================================= */}
          {activeTab === 'factors' && (
            <div className="grid grid-cols-12 gap-4">
              {/* Factor Bar Chart */}
              <div className="col-span-12 lg:col-span-7 card p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-bold text-foreground-muted">FACTOR EXPOSURES & CONTRIBUTIONS</h3>
                  {factorData && (
                    <span className="text-[10px] font-mono text-foreground-muted">
                      R2 = {(factorData.r_squared * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
                {factorChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={320}>
                    <ComposedChart data={factorChartData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 10 }} />
                      <YAxis
                        type="category"
                        dataKey="factor"
                        tick={{ fill: '#00d4aa', fontSize: 11, fontWeight: 700 }}
                        width={80}
                      />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
                        formatter={(v: number, name: string) => {
                          if (name === 'exposure') return [v.toFixed(3), 'Exposure']
                          if (name === 'contribution') return [`${v.toFixed(1)} bps`, 'Contribution']
                          return [v, name]
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar dataKey="exposure" name="Exposure" radius={[0, 4, 4, 0]}>
                        {factorChartData.map((entry, i) => (
                          <Cell key={i} fill={entry.color} fillOpacity={0.7} />
                        ))}
                      </Bar>
                      <ReferenceLine x={0} stroke="rgba(255,255,255,0.15)" />
                    </ComposedChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState message="No factor data available" />
                )}
                {/* Residual Alpha */}
                {factorData && (
                  <div className="mt-3 pt-3 border-t border-border flex items-center justify-between">
                    <span className="text-xs text-foreground-muted">Residual (Alpha)</span>
                    <span className={cn(
                      'text-xs font-mono font-bold',
                      factorData.residual_bps >= 0 ? 'text-bullish' : 'text-bearish'
                    )}>
                      {factorData.residual_bps >= 0 ? '+' : ''}{factorData.residual_bps.toFixed(1)} bps
                    </span>
                  </div>
                )}
              </div>

              {/* Factor Radar */}
              <div className="col-span-12 lg:col-span-5 card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">FACTOR RISK PROFILE</h3>
                {radarData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={320}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="rgba(255,255,255,0.1)" />
                      <PolarAngleAxis dataKey="factor" tick={{ fill: '#9ca3af', fontSize: 10 }} />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 9 }} />
                      <Radar
                        name="Exposure"
                        dataKey="exposure"
                        stroke="#00d4aa"
                        fill="#00d4aa"
                        fillOpacity={0.2}
                      />
                      <Radar
                        name="Risk %"
                        dataKey="riskPct"
                        stroke="#f59e0b"
                        fill="#f59e0b"
                        fillOpacity={0.15}
                      />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                    </RadarChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState message="No factor data" />
                )}
                {/* Alpha Trend */}
                {alphaTrend && alphaTrend.trend !== 'insufficient_data' && (
                  <div className="mt-3 pt-3 border-t border-border flex items-center justify-between">
                    <span className="text-xs text-foreground-muted">Alpha Trend</span>
                    <div className="flex items-center gap-3">
                      <span className={cn('text-xs font-bold',
                        alphaTrend.trend === 'improving' ? 'text-bullish' :
                        alphaTrend.trend === 'decaying' ? 'text-bearish' : 'text-foreground-secondary'
                      )}>
                        {alphaTrend.trend.toUpperCase()}
                      </span>
                      <span className="text-[10px] font-mono text-foreground-muted">
                        Sharpe: {alphaTrend.alpha_sharpe.toFixed(2)}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Factor Detail Table */}
              <div className="col-span-12 card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">FACTOR DETAIL</h3>
                {factorData?.factors && factorData.factors.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-foreground-muted border-b border-border">
                          <th className="text-left py-2 pr-4">Factor</th>
                          <th className="text-right py-2 pr-4">Exposure</th>
                          <th className="text-right py-2 pr-4">Contribution (bps)</th>
                          <th className="text-right py-2 pr-4">% of Risk</th>
                          <th className="text-left py-2">Risk Bar</th>
                        </tr>
                      </thead>
                      <tbody>
                        {factorData.factors.map((f) => (
                          <tr key={f.factor} className="border-b border-border/30">
                            <td className="py-2 pr-4 font-medium text-foreground-primary capitalize">{f.factor}</td>
                            <td className={cn('py-2 pr-4 text-right font-mono', f.exposure >= 0 ? 'text-bullish' : 'text-bearish')}>
                              {f.exposure >= 0 ? '+' : ''}{f.exposure.toFixed(3)}
                            </td>
                            <td className={cn('py-2 pr-4 text-right font-mono font-bold', f.contribution_bps >= 0 ? 'text-bullish' : 'text-bearish')}>
                              {f.contribution_bps >= 0 ? '+' : ''}{f.contribution_bps.toFixed(1)}
                            </td>
                            <td className="py-2 pr-4 text-right font-mono text-foreground-secondary">
                              {f.pct_of_risk.toFixed(1)}%
                            </td>
                            <td className="py-2 w-32">
                              <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all"
                                  style={{
                                    width: `${Math.min(100, f.pct_of_risk)}%`,
                                    backgroundColor: FACTOR_COLORS[f.factor] || '#6b7280',
                                    opacity: 0.8,
                                  }}
                                />
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <EmptyState message="No factor data available" />
                )}
              </div>
            </div>
          )}

          {/* ============================================================= */}
          {/* ATTRIBUTION TAB                                                */}
          {/* ============================================================= */}
          {activeTab === 'attribution' && (
            <div className="grid grid-cols-12 gap-4">
              {/* Waterfall Chart */}
              <div className="col-span-12 lg:col-span-8 card p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-bold text-foreground-muted">PnL ATTRIBUTION WATERFALL</h3>
                  {attribution && (
                    <span className={cn('text-xs font-mono font-bold', attribution.total_pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                      Total: ${attribution.total_pnl.toFixed(2)}
                    </span>
                  )}
                </div>
                {waterfallData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={350}>
                    <BarChart data={waterfallData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis
                        dataKey="name"
                        tick={{ fill: '#6b7280', fontSize: 10 }}
                        angle={-20}
                        textAnchor="end"
                        height={60}
                      />
                      <YAxis
                        tick={{ fill: '#6b7280', fontSize: 10 }}
                        tickFormatter={(v) => `$${v.toFixed(0)}`}
                        width={60}
                      />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
                        formatter={(v: number) => [`$${v.toFixed(2)}`, 'P&L']}
                      />
                      <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" />
                      <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        {waterfallData.map((entry, i) => (
                          <Cell key={i} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState message="No attribution data available" />
                )}
              </div>

              {/* Attribution Components */}
              <div className="col-span-12 lg:col-span-4 card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">ATTRIBUTION COMPONENTS</h3>
                {attribution?.components && attribution.components.length > 0 ? (
                  <div className="space-y-3">
                    {attribution.components.map((comp, i) => (
                      <div key={i} className="p-2.5 bg-background-tertiary rounded-lg">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-foreground-primary">{comp.name}</span>
                          <span className={cn(
                            'text-xs font-mono font-bold',
                            comp.value >= 0 ? 'text-bullish' : 'text-bearish'
                          )}>
                            ${comp.value.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-foreground-muted">{comp.description}</span>
                          <span className="text-[10px] font-mono text-foreground-muted">
                            {comp.pct_of_total.toFixed(1)}%
                          </span>
                        </div>
                        <div className="mt-1.5 h-1.5 bg-background-primary rounded-full overflow-hidden">
                          <div
                            className={cn('h-full rounded-full', comp.value >= 0 ? 'bg-bullish' : 'bg-bearish')}
                            style={{ width: `${Math.min(100, Math.abs(comp.pct_of_total))}%`, opacity: 0.6 }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState message="No component data" />
                )}
              </div>
            </div>
          )}

          {/* ============================================================= */}
          {/* BUDGETS TAB                                                    */}
          {/* ============================================================= */}
          {activeTab === 'budgets' && (
            <div className="grid grid-cols-12 gap-4">
              {/* Budget Donut */}
              <div className="col-span-12 lg:col-span-5 card p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs font-bold text-foreground-muted">RISK BUDGET UTILIZATION</h3>
                  {budgets && (
                    <div className="flex gap-2">
                      {budgets.budgets_over_limit > 0 && (
                        <span className="text-[10px] bg-bearish/20 text-bearish px-2 py-0.5 rounded font-bold">
                          {budgets.budgets_over_limit} BREACHED
                        </span>
                      )}
                      {budgets.budgets_approaching > 0 && (
                        <span className="text-[10px] bg-warning/20 text-warning px-2 py-0.5 rounded font-bold">
                          {budgets.budgets_approaching} NEAR
                        </span>
                      )}
                    </div>
                  )}
                </div>
                {budgetPieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={budgetPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={100}
                        dataKey="utilization"
                        nameKey="name"
                        paddingAngle={2}
                        stroke="none"
                      >
                        {budgetPieData.map((entry, i) => (
                          <Cell key={i} fill={entry.color} fillOpacity={0.8} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
                        formatter={(v: number) => [`${v.toFixed(1)}%`, 'Utilization']}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <EmptyState message="No budget data" />
                )}
              </div>

              {/* Budget Bars + Alerts */}
              <div className="col-span-12 lg:col-span-7 card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">BUDGET UTILIZATION DETAILS</h3>
                {budgets && Object.keys(budgets.utilizations).length > 0 ? (
                  <div className="space-y-3">
                    {Object.entries(budgets.utilizations).map(([name, data]) => {
                      const util = data.overall_utilization
                      return (
                        <div key={name}>
                          <div className="flex justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-foreground-secondary capitalize">{name.replace(/_/g, ' ')}</span>
                              <span className="text-[10px] bg-background-tertiary px-1.5 py-0.5 rounded text-foreground-muted">
                                {data.budget.budget_type}
                              </span>
                            </div>
                            <span className={cn(
                              'text-xs font-mono font-bold',
                              util >= 100 ? 'text-bearish' : util >= 80 ? 'text-warning' : 'text-bullish'
                            )}>
                              {util.toFixed(0)}%
                            </span>
                          </div>
                          <div className="h-2.5 bg-background-tertiary rounded-full overflow-hidden">
                            <div
                              className={cn(
                                'h-full rounded-full transition-all',
                                util >= 100 ? 'bg-bearish' : util >= 80 ? 'bg-warning' : 'bg-bullish'
                              )}
                              style={{ width: `${Math.min(100, util)}%` }}
                            />
                          </div>
                          {/* Sub-metrics */}
                          {data.metrics && Object.keys(data.metrics).length > 0 && (
                            <div className="flex gap-3 mt-1">
                              {Object.entries(data.metrics).map(([key, m]) => (
                                <span key={key} className="text-[10px] text-foreground-muted">
                                  {key}: <span className="font-mono">{m.current.toFixed(1)}/{m.limit.toFixed(1)}</span>
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}

                    {/* Scale Recommendations */}
                    {budgets.scale_recommendations.length > 0 && (
                      <div className="pt-3 border-t border-border">
                        <p className="text-[10px] font-bold text-warning mb-2">SCALING RECOMMENDATIONS</p>
                        {budgets.scale_recommendations.map((rec, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs text-foreground-muted mb-1">
                            <Zap className="w-3 h-3 text-warning" />
                            <span>{rec.strategy}: scale to <span className="font-mono font-bold">{(rec.scale_factor * 100).toFixed(0)}%</span> - {rec.reason}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Budget Alerts */}
                    {budgets.alerts.length > 0 && (
                      <div className="pt-3 border-t border-border space-y-1">
                        {budgets.alerts.slice(0, 4).map((alert, i) => (
                          <div key={i} className={cn(
                            'text-xs p-2 rounded',
                            alert.severity === 'critical' ? 'bg-bearish/10 text-bearish' : 'bg-warning/10 text-warning'
                          )}>
                            <AlertCircle className="w-3 h-3 inline mr-1" />
                            {alert.message}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <EmptyState message="No budget data available" />
                )}
              </div>
            </div>
          )}

          {/* ============================================================= */}
          {/* CORRELATION TAB                                                */}
          {/* ============================================================= */}
          {activeTab === 'correlation' && (
            <div className="grid grid-cols-12 gap-4">
              {/* Mini correlation matrix */}
              <div className="col-span-12 lg:col-span-7 card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">PORTFOLIO CORRELATION MATRIX</h3>
                {corrMonitor?.correlation_matrix?.symbols?.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[400px]">
                      <thead>
                        <tr>
                          <th className="p-1.5 text-[10px] text-foreground-muted"></th>
                          {corrMonitor.correlation_matrix.symbols.map((sym) => (
                            <th key={sym} className="p-1.5 text-[10px] font-bold text-accent-primary">{sym}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {corrMonitor.correlation_matrix.matrix.map((row, i) => (
                          <tr key={i}>
                            <td className="p-1.5 text-[10px] font-bold text-accent-primary">
                              {corrMonitor.correlation_matrix.symbols[i]}
                            </td>
                            {row.map((corr, j) => {
                              const isSelf = i === j
                              return (
                                <td
                                  key={j}
                                  className={cn(
                                    'p-1.5 text-center text-[10px] font-mono font-bold',
                                    isSelf ? 'bg-background-tertiary text-foreground-muted' :
                                    corr >= 0.7 ? 'bg-bullish/60 text-white' :
                                    corr >= 0.4 ? 'bg-bullish/30 text-white' :
                                    corr >= 0 ? 'bg-bullish/10 text-foreground-primary' :
                                    corr >= -0.4 ? 'bg-bearish/10 text-foreground-primary' :
                                    'bg-bearish/40 text-white'
                                  )}
                                >
                                  {corr.toFixed(2)}
                                </td>
                              )
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <EmptyState message="No correlation data" />
                )}

                {/* High Correlation Pairs */}
                {(corrMonitor?.correlation_matrix?.high_correlation_pairs?.length ?? 0) > 0 && (
                  <div className="mt-4 pt-3 border-t border-border">
                    <p className="text-[10px] font-bold text-foreground-muted mb-2">HIGH CORRELATION PAIRS</p>
                    <div className="grid grid-cols-2 gap-2">
                      {corrMonitor!.correlation_matrix.high_correlation_pairs.slice(0, 6).map((pair, i) => (
                        <div key={i} className="flex justify-between text-xs p-2 bg-background-tertiary rounded">
                          <span className="text-foreground-secondary">{pair.symbol1} / {pair.symbol2}</span>
                          <span className="font-mono text-warning font-bold">{pair.correlation.toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Regime + Diversification */}
              <div className="col-span-12 lg:col-span-5 space-y-4">
                {/* Regime */}
                {corrMonitor?.regime && (
                  <div className="card p-4">
                    <h3 className="text-[10px] font-bold text-foreground-muted mb-3">CORRELATION REGIME</h3>
                    <div className="flex items-center justify-between mb-2">
                      <span className={cn(
                        'text-lg font-bold uppercase',
                        corrMonitor.regime.regime === 'crisis' ? 'text-bearish' :
                        corrMonitor.regime.regime === 'elevated' ? 'text-warning' :
                        corrMonitor.regime.regime === 'normal' ? 'text-accent-primary' : 'text-bullish'
                      )}>
                        {corrMonitor.regime.regime}
                      </span>
                      <span className="text-xs font-mono text-foreground-muted">
                        avg: {corrMonitor.regime.avg_correlation.toFixed(2)}
                      </span>
                    </div>
                    <p className="text-[10px] text-foreground-muted">{corrMonitor.regime.description}</p>
                  </div>
                )}

                {/* Diversification */}
                {corrMonitor?.diversification && (
                  <div className="card p-4">
                    <h3 className="text-[10px] font-bold text-foreground-muted mb-3">DIVERSIFICATION SCORE</h3>
                    <div className="flex items-center gap-4 mb-3">
                      <div className={cn(
                        'text-3xl font-bold',
                        corrMonitor.diversification.grade === 'A' ? 'text-bullish' :
                        corrMonitor.diversification.grade === 'B' ? 'text-accent-primary' :
                        corrMonitor.diversification.grade === 'C' ? 'text-warning' : 'text-bearish'
                      )}>
                        {corrMonitor.diversification.grade}
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-foreground-muted">Score</span>
                          <span className="font-mono text-foreground-secondary">
                            {corrMonitor.diversification.score.toFixed(0)}/100
                          </span>
                        </div>
                        <div className="h-2.5 bg-background-tertiary rounded-full overflow-hidden">
                          <div
                            className={cn(
                              'h-full rounded-full transition-all',
                              corrMonitor.diversification.score >= 65 ? 'bg-bullish' :
                              corrMonitor.diversification.score >= 35 ? 'bg-warning' : 'bg-bearish'
                            )}
                            style={{ width: `${corrMonitor.diversification.score}%` }}
                          />
                        </div>
                        <p className="text-[10px] text-foreground-muted mt-1">
                          {corrMonitor.diversification.effective_positions.toFixed(1)} effective positions
                        </p>
                      </div>
                    </div>
                    {corrMonitor.diversification.recommendations.length > 0 && (
                      <div className="pt-2 border-t border-border space-y-1">
                        {corrMonitor.diversification.recommendations.slice(0, 3).map((rec, i) => (
                          <p key={i} className="text-[10px] text-foreground-muted flex items-start gap-1">
                            <Target className="w-3 h-3 text-accent-primary flex-shrink-0 mt-0.5" />
                            {rec}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Correlation Alerts */}
                {corrMonitor?.alerts && corrMonitor.alerts.length > 0 && (
                  <div className="card p-4">
                    <h3 className="text-[10px] font-bold text-foreground-muted mb-2">ALERTS</h3>
                    <div className="space-y-1">
                      {corrMonitor.alerts.map((alert, i) => (
                        <div key={i} className={cn(
                          'text-xs p-2 rounded',
                          alert.severity === 'critical' ? 'bg-bearish/10 text-bearish' : 'bg-warning/10 text-warning'
                        )}>
                          {alert.message}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center h-[300px] text-foreground-muted">
      <div className="text-center">
        <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">{message}</p>
      </div>
    </div>
  )
}
