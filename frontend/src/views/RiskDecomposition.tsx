import { useState, useEffect } from 'react'
import { PieChart, BarChart3, TrendingUp, RefreshCw, AlertCircle, Activity, DollarSign, Layers } from 'lucide-react'
import { cn } from '@/utils/cn'

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
  correlation_matrix: { symbols: string[]; matrix: number[][]; avg_correlation: number; high_correlation_pairs: { symbol1: string; symbol2: string; correlation: number }[] }
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

export function RiskDecomposition() {
  const [factorData, setFactorData] = useState<FactorData | null>(null)
  const [attribution, setAttribution] = useState<AttributionData | null>(null)
  const [budgets, setBudgets] = useState<BudgetData | null>(null)
  const [corrMonitor, setCorrMonitor] = useState<CorrelationMonitorData | null>(null)
  const [alphaTrend, setAlphaTrend] = useState<AlphaTrend | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
      if (factorRes.ok) setFactorData(await factorRes.json())
      if (attrRes.ok) setAttribution(await attrRes.json())
      if (budgetRes.ok) setBudgets(await budgetRes.json())
      if (corrRes.ok) setCorrMonitor(await corrRes.json())
      if (alphaRes.ok) setAlphaTrend(await alphaRes.json())
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

  const getFactorColor = (factor: string) => {
    const colors: Record<string, string> = {
      market: 'bg-blue-500',
      sector: 'bg-purple-500',
      momentum: 'bg-emerald-500',
      volatility: 'bg-orange-500',
      size: 'bg-cyan-500',
    }
    return colors[factor] || 'bg-gray-500'
  }

  const getFactorLabel = (factor: string) => {
    const labels: Record<string, string> = {
      market: 'Market Beta',
      sector: 'Sector Tilt',
      momentum: 'Momentum',
      volatility: 'Volatility',
      size: 'Size',
    }
    return labels[factor] || factor
  }

  const getSeverityColor = (severity: string) => {
    if (severity === 'critical') return 'text-bearish'
    if (severity === 'warning') return 'text-warning'
    return 'text-foreground-muted'
  }

  const getRegimeColor = (regime: string) => {
    if (regime === 'crisis') return 'text-bearish'
    if (regime === 'elevated') return 'text-warning'
    if (regime === 'normal') return 'text-accent-primary'
    return 'text-bullish'
  }

  const getGradeColor = (grade: string) => {
    if (grade === 'A') return 'text-bullish'
    if (grade === 'B') return 'text-accent-primary'
    if (grade === 'C') return 'text-warning'
    return 'text-bearish'
  }

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
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-accent-primary" />
        </div>
      ) : (
        <>
          {/* Row 1: Factor Decomposition + Attribution Waterfall */}
          <div className="grid grid-cols-12 gap-4">
            {/* Factor Exposures */}
            <div className="col-span-6 card p-4">
              <div className="flex items-center gap-2 mb-4">
                <PieChart className="w-4 h-4 text-accent-primary" />
                <h3 className="text-xs font-bold text-foreground-muted">FACTOR EXPOSURES</h3>
                {factorData && (
                  <span className="ml-auto text-xs text-foreground-muted font-mono">
                    R² = {(factorData.r_squared * 100).toFixed(1)}%
                  </span>
                )}
              </div>
              {factorData && factorData.factors && factorData.factors.length > 0 ? (
                <div className="space-y-3">
                  {factorData.factors.map((f) => (
                    <div key={f.factor}>
                      <div className="flex justify-between mb-1">
                        <span className="text-xs text-foreground-secondary">{getFactorLabel(f.factor)}</span>
                        <div className="flex gap-3">
                          <span className="text-xs font-mono text-foreground-muted">
                            exp: {f.exposure >= 0 ? '+' : ''}{f.exposure.toFixed(2)}
                          </span>
                          <span className={cn('text-xs font-mono font-bold', f.contribution_bps >= 0 ? 'text-bullish' : 'text-bearish')}>
                            {f.contribution_bps >= 0 ? '+' : ''}{f.contribution_bps.toFixed(1)} bps
                          </span>
                          <span className="text-xs font-mono text-foreground-muted">
                            {f.pct_of_risk.toFixed(0)}%
                          </span>
                        </div>
                      </div>
                      <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                        <div
                          className={cn('h-full rounded-full', getFactorColor(f.factor))}
                          style={{ width: `${Math.min(100, Math.abs(f.exposure) * 50 + 10)}%`, opacity: 0.8 }}
                        />
                      </div>
                    </div>
                  ))}
                  {/* Residual / Alpha */}
                  <div className="pt-2 border-t border-border">
                    <div className="flex justify-between">
                      <span className="text-xs font-bold text-foreground-secondary">Residual (Alpha)</span>
                      <span className={cn('text-xs font-mono font-bold', factorData.residual_bps >= 0 ? 'text-bullish' : 'text-bearish')}>
                        {factorData.residual_bps >= 0 ? '+' : ''}{factorData.residual_bps.toFixed(1)} bps
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center text-foreground-muted py-8">
                  <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No factor data available</p>
                </div>
              )}
            </div>

            {/* Attribution Waterfall */}
            <div className="col-span-6 card p-4">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="w-4 h-4 text-accent-primary" />
                <h3 className="text-xs font-bold text-foreground-muted">PnL ATTRIBUTION WATERFALL</h3>
                {attribution && (
                  <span className={cn('ml-auto text-xs font-mono font-bold', attribution.total_pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                    Total: ${attribution.total_pnl.toFixed(2)}
                  </span>
                )}
              </div>
              {attribution && attribution.waterfall && attribution.waterfall.length > 0 ? (
                <div className="space-y-2">
                  {attribution.waterfall.map((item, i) => {
                    const maxVal = Math.max(...attribution.waterfall.map(w => Math.abs(w.value)), 1)
                    const barWidth = Math.min(100, (Math.abs(item.value) / maxVal) * 100)
                    return (
                      <div key={i} className="flex items-center gap-2">
                        <span className={cn('text-xs w-28 truncate', item.is_total ? 'font-bold text-foreground-primary' : 'text-foreground-secondary')}>
                          {item.name}
                        </span>
                        <div className="flex-1 h-5 bg-background-tertiary rounded overflow-hidden relative">
                          <div
                            className={cn(
                              'h-full rounded',
                              item.is_total
                                ? (item.is_positive ? 'bg-accent-primary' : 'bg-bearish')
                                : (item.is_positive ? 'bg-bullish/70' : 'bg-bearish/70')
                            )}
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                        <span className={cn(
                          'text-xs font-mono w-20 text-right',
                          item.is_total ? 'font-bold' : '',
                          item.value >= 0 ? 'text-bullish' : 'text-bearish'
                        )}>
                          ${item.value.toFixed(2)}
                        </span>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="text-center text-foreground-muted py-8">
                  <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No attribution data available</p>
                </div>
              )}
              {/* Alpha Trend */}
              {alphaTrend && alphaTrend.trend !== 'insufficient_data' && (
                <div className="mt-3 pt-3 border-t border-border">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-foreground-muted">Alpha Trend</span>
                    <div className="flex items-center gap-2">
                      <span className={cn('text-xs font-bold',
                        alphaTrend.trend === 'improving' ? 'text-bullish' :
                        alphaTrend.trend === 'decaying' ? 'text-bearish' : 'text-foreground-secondary'
                      )}>
                        {alphaTrend.trend.toUpperCase()}
                      </span>
                      <span className="text-xs font-mono text-foreground-muted">
                        Sharpe: {alphaTrend.alpha_sharpe?.toFixed(2) ?? '—'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Row 2: Risk Budgets + Correlation Monitor */}
          <div className="grid grid-cols-12 gap-4">
            {/* Risk Budgets */}
            <div className="col-span-7 card p-4">
              <div className="flex items-center gap-2 mb-4">
                <DollarSign className="w-4 h-4 text-accent-primary" />
                <h3 className="text-xs font-bold text-foreground-muted">RISK BUDGETS</h3>
                {budgets && (
                  <div className="ml-auto flex gap-2">
                    {budgets.budgets_over_limit > 0 && (
                      <span className="text-xs bg-bearish/20 text-bearish px-2 py-0.5 rounded">
                        {budgets.budgets_over_limit} breached
                      </span>
                    )}
                    {budgets.budgets_approaching > 0 && (
                      <span className="text-xs bg-warning/20 text-warning px-2 py-0.5 rounded">
                        {budgets.budgets_approaching} approaching
                      </span>
                    )}
                  </div>
                )}
              </div>
              {budgets?.utilizations && Object.keys(budgets.utilizations).length > 0 ? (
                <div className="space-y-3">
                  {Object.entries(budgets.utilizations).map(([name, data]) => {
                    const util = data?.overall_utilization ?? 0
                    return (
                      <div key={name}>
                        <div className="flex justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-foreground-secondary capitalize">{name.replace(/_/g, ' ')}</span>
                            <span className="text-[10px] bg-background-tertiary px-1.5 py-0.5 rounded text-foreground-muted">
                              {data?.budget?.budget_type}
                            </span>
                          </div>
                          <span className={cn(
                            'text-xs font-mono font-bold',
                            util >= 100 ? 'text-bearish' : util >= 80 ? 'text-warning' : 'text-bullish'
                          )}>
                            {util.toFixed(0)}%
                          </span>
                        </div>
                        <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                          <div
                            className={cn(
                              'h-full rounded-full transition-all',
                              util >= 100 ? 'bg-bearish' : util >= 80 ? 'bg-warning' : 'bg-bullish'
                            )}
                            style={{ width: `${Math.min(100, util)}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                  {/* Scale Recommendations */}
                  {budgets.scale_recommendations.length > 0 && (
                    <div className="pt-2 border-t border-border">
                      <p className="text-[10px] font-bold text-warning mb-1">SCALING RECOMMENDATIONS</p>
                      {budgets.scale_recommendations.map((rec, i) => (
                        <p key={i} className="text-xs text-foreground-muted">
                          {rec.strategy}: scale to {(rec.scale_factor * 100).toFixed(0)}% - {rec.reason}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center text-foreground-muted py-8">
                  <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No budget data available</p>
                </div>
              )}
              {/* Budget Alerts */}
              {budgets && budgets.alerts.length > 0 && (
                <div className="mt-3 pt-3 border-t border-border space-y-1">
                  {budgets.alerts.slice(0, 3).map((alert, i) => (
                    <div key={i} className={cn('text-xs', getSeverityColor(alert.severity))}>
                      {alert.message}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Correlation Monitor */}
            <div className="col-span-5 card p-4">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="w-4 h-4 text-accent-primary" />
                <h3 className="text-xs font-bold text-foreground-muted">CORRELATION MONITOR</h3>
              </div>
              {corrMonitor ? (
                <div className="space-y-4">
                  {/* Regime */}
                  <div>
                    <p className="text-[10px] font-bold text-foreground-muted mb-1">REGIME</p>
                    <div className="flex items-center justify-between">
                      <span className={cn('text-sm font-bold uppercase', getRegimeColor(corrMonitor.regime?.regime))}>
                        {corrMonitor.regime?.regime}
                      </span>
                      <span className="text-xs font-mono text-foreground-muted">
                        avg corr: {corrMonitor.regime?.avg_correlation?.toFixed(2) ?? '—'}
                      </span>
                    </div>
                    <p className="text-[10px] text-foreground-muted mt-1">{corrMonitor.regime?.description}</p>
                  </div>

                  {/* Diversification Score */}
                  <div>
                    <p className="text-[10px] font-bold text-foreground-muted mb-1">DIVERSIFICATION</p>
                    <div className="flex items-center gap-3">
                      <div className={cn('text-2xl font-bold', getGradeColor(corrMonitor.diversification?.grade))}>
                        {corrMonitor.diversification?.grade ?? '—'}
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between text-xs">
                          <span className="text-foreground-muted">Score</span>
                          <span className="font-mono">{corrMonitor.diversification?.score?.toFixed(0) ?? '—'}/100</span>
                        </div>
                        <div className="h-2 bg-background-tertiary rounded-full overflow-hidden mt-1">
                          <div
                            className={cn(
                              'h-full rounded-full',
                              (corrMonitor.diversification?.score ?? 0) >= 65 ? 'bg-bullish' :
                              (corrMonitor.diversification?.score ?? 0) >= 35 ? 'bg-warning' : 'bg-bearish'
                            )}
                            style={{ width: `${corrMonitor.diversification?.score ?? 0}%` }}
                          />
                        </div>
                        <div className="text-[10px] text-foreground-muted mt-1">
                          {corrMonitor.diversification?.effective_positions?.toFixed(1) ?? '0.0'} effective positions
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* High Correlation Pairs */}
                  {corrMonitor.correlation_matrix?.high_correlation_pairs?.length > 0 && (
                    <div>
                      <p className="text-[10px] font-bold text-foreground-muted mb-1">HIGH CORRELATION PAIRS</p>
                      <div className="space-y-1">
                        {corrMonitor.correlation_matrix.high_correlation_pairs.slice(0, 4).map((pair, i) => (
                          <div key={i} className="flex justify-between text-xs">
                            <span className="text-foreground-secondary">{pair.symbol1} / {pair.symbol2}</span>
                            <span className="font-mono text-warning">{pair.correlation.toFixed(2)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Recommendations */}
                  {corrMonitor.diversification.recommendations.length > 0 && (
                    <div className="pt-2 border-t border-border">
                      {corrMonitor.diversification.recommendations.slice(0, 2).map((rec, i) => (
                        <p key={i} className="text-[10px] text-foreground-muted">
                          {rec}
                        </p>
                      ))}
                    </div>
                  )}

                  {/* Alerts */}
                  {corrMonitor.alerts.length > 0 && (
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
                  )}
                </div>
              ) : (
                <div className="text-center text-foreground-muted py-8">
                  <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No correlation data</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
