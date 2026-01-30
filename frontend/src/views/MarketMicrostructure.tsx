import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, BarChart3, Brain, Clock, Layers, RefreshCw, Settings, Shield, TrendingUp, Waves, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/utils/cn'

interface ModuleStatus {
  order_flow: boolean
  volatility_regime: boolean
  liquidity_monitor: boolean
  signal_decay: boolean
  adaptive_sizing: boolean
  market_hours: boolean
  cross_asset: boolean
}

export function MarketMicrostructure() {
  const [symbol, setSymbol] = useState('SPY')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<any>(null)
  const [status, setStatus] = useState<any>(null)
  const [sessions, setSessions] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'flow' | 'volatility' | 'liquidity' | 'signals' | 'sizing' | 'sessions' | 'cross-asset' | 'config'>('overview')

  useEffect(() => {
    fetchStatus()
    fetchSessions()
  }, [])

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/microstructure/status')
      const data = await res.json()
      setStatus(data)
    } catch {
      // Status fetch is non-critical
    }
  }

  const fetchSessions = async () => {
    try {
      const res = await fetch('/api/microstructure/sessions')
      const data = await res.json()
      setSessions(data)
    } catch {
      // Sessions fetch is non-critical
    }
  }

  const runAnalysis = async () => {
    setAnalyzing(true)
    setError(null)
    try {
      const res = await fetch(`/api/microstructure/analyze/${symbol}`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Analysis failed')
      setAnalysis(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
      setAnalysis(null)
    } finally {
      setAnalyzing(false)
    }
  }

  const getStateColor = (state: string) => {
    const colors: Record<string, string> = {
      COMPRESSED: 'text-blue-400 bg-blue-400/10',
      NORMAL: 'text-accent-primary bg-accent-primary/10',
      EXPANDING: 'text-warning bg-warning/10',
      CRISIS: 'text-bearish bg-bearish/10',
      DEEP: 'text-bullish bg-bullish/10',
      THIN: 'text-warning bg-warning/10',
      VACUUM: 'text-bearish bg-bearish/10',
      BUYING: 'text-bullish bg-bullish/10',
      SELLING: 'text-bearish bg-bearish/10',
      NEUTRAL: 'text-foreground-muted bg-foreground-muted/10',
      MIXED: 'text-warning bg-warning/10',
      FAVORABLE: 'text-bullish bg-bullish/10',
      NEUTRAL_POSITIVE: 'text-accent-primary bg-accent-primary/10',
      NEUTRAL_NEGATIVE: 'text-warning bg-warning/10',
      UNFAVORABLE: 'text-bearish bg-bearish/10',
    }
    return colors[state] || 'text-foreground-muted bg-foreground-muted/10'
  }

  const getScoreColor = (score: number) => {
    if (score > 0.3) return 'text-bullish'
    if (score > 0) return 'text-accent-primary'
    if (score > -0.3) return 'text-warning'
    return 'text-bearish'
  }

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: Layers },
    { id: 'flow' as const, label: 'Order Flow', icon: Activity },
    { id: 'volatility' as const, label: 'Vol Regime', icon: Waves },
    { id: 'liquidity' as const, label: 'Liquidity', icon: BarChart3 },
    { id: 'signals' as const, label: 'Signals', icon: Zap },
    { id: 'sizing' as const, label: 'Sizing', icon: Shield },
    { id: 'sessions' as const, label: 'Sessions', icon: Clock },
    { id: 'cross-asset' as const, label: 'Cross-Asset', icon: TrendingUp },
    { id: 'config' as const, label: 'Config', icon: Settings },
  ]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Brain className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">MARKET MICROSTRUCTURE</h1>
            <p className="text-xs text-foreground-muted">Adaptive Market Intelligence & Flow Analysis Engine</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="w-24 px-3 py-1.5 text-sm bg-surface border border-border rounded font-mono text-foreground"
            placeholder="Symbol"
          />
          <button onClick={runAnalysis} disabled={analyzing} className="btn-primary flex items-center gap-2">
            <RefreshCw className={cn('w-4 h-4', analyzing && 'animate-spin')} />
            Analyze
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border overflow-x-auto">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 transition-colors',
              activeTab === tab.id
                ? 'border-accent-primary text-accent-primary'
                : 'border-transparent text-foreground-muted hover:text-foreground'
            )}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {/* Status Bar */}
      {status?.available && (
        <div className="card p-3 flex items-center justify-between text-xs">
          <div className="flex items-center gap-4">
            <span className="text-foreground-muted">Engine v{status.version || '1.0.0'}</span>
            <span className="text-foreground-muted">Session: <span className="text-accent-primary font-mono">{status.current_session || sessions?.current_session || 'UNKNOWN'}</span></span>
            <span className="text-foreground-muted">Active Signals: <span className="text-accent-primary font-mono">{status.active_signals || 0}</span></span>
          </div>
          <div className="flex items-center gap-2">
            {status.config?.modules && Object.entries(status.config.modules).map(([mod, enabled]) => (
              <span key={mod} className={cn('px-1.5 py-0.5 rounded text-[10px] font-mono', enabled ? 'bg-bullish/10 text-bullish' : 'bg-surface text-foreground-muted')}>
                {mod.replace('_', ' ').toUpperCase().slice(0, 8)}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Content */}
      {activeTab === 'overview' && <OverviewTab analysis={analysis} getStateColor={getStateColor} getScoreColor={getScoreColor} sessions={sessions} />}
      {activeTab === 'flow' && <OrderFlowTab analysis={analysis} getStateColor={getStateColor} />}
      {activeTab === 'volatility' && <VolatilityTab analysis={analysis} getStateColor={getStateColor} />}
      {activeTab === 'liquidity' && <LiquidityTab analysis={analysis} getStateColor={getStateColor} />}
      {activeTab === 'signals' && <SignalsTab analysis={analysis} />}
      {activeTab === 'sizing' && <SizingTab analysis={analysis} />}
      {activeTab === 'sessions' && <SessionsTab sessions={sessions} />}
      {activeTab === 'cross-asset' && <CrossAssetTab analysis={analysis} getStateColor={getStateColor} />}
      {activeTab === 'config' && <ConfigTab status={status} onRefresh={fetchStatus} />}
    </div>
  )
}

function OverviewTab({ analysis, getStateColor, getScoreColor, sessions }: any) {
  if (!analysis) {
    return (
      <div className="card p-12 text-center">
        <Brain className="w-12 h-12 text-foreground-muted mx-auto mb-4 opacity-30" />
        <p className="text-foreground-muted">Enter a symbol and click Analyze to run microstructure analysis</p>
        <p className="text-xs text-foreground-muted mt-2">All 7 intelligence modules will analyze the symbol simultaneously</p>
      </div>
    )
  }

  const modules = analysis.modules || {}
  const alerts = analysis.alerts || []

  return (
    <div className="space-y-4">
      {/* Composite Score */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 card p-6 text-center">
          <h3 className="text-xs font-bold text-foreground-muted mb-3">COMPOSITE SCORE</h3>
          <div className={cn('text-4xl font-bold mb-2', getScoreColor(analysis.composite_score))}>
            {(analysis.composite_score * 100).toFixed(1)}
          </div>
          <div className={cn('inline-block px-3 py-1 rounded-full text-sm font-bold', getStateColor(analysis.recommendation))}>
            {analysis.recommendation}
          </div>
        </div>

        <div className="col-span-4 card p-6">
          <h3 className="text-xs font-bold text-foreground-muted mb-3">SCORE BREAKDOWN</h3>
          <div className="space-y-2">
            {analysis.score_breakdown && Object.entries(analysis.score_breakdown).map(([key, val]: [string, any]) => (
              <div key={key} className="flex items-center justify-between text-xs">
                <span className="text-foreground-muted capitalize">{key.replace(/_/g, ' ')}</span>
                <div className="flex items-center gap-2">
                  <div className="w-20 h-1.5 bg-surface rounded-full overflow-hidden">
                    <div
                      className={cn('h-full rounded-full', val > 0 ? 'bg-bullish' : 'bg-bearish')}
                      style={{ width: `${Math.min(100, Math.abs(val) * 100)}%`, marginLeft: val < 0 ? 'auto' : undefined }}
                    />
                  </div>
                  <span className={cn('font-mono w-12 text-right', getScoreColor(val))}>{(val * 100).toFixed(0)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="col-span-4 card p-6">
          <h3 className="text-xs font-bold text-foreground-muted mb-3">MARKET SESSION</h3>
          {modules.market_hours ? (
            <div className="space-y-3">
              <div className="text-center">
                <span className="text-lg font-mono text-accent-primary">{modules.market_hours.session}</span>
              </div>
              <div className="flex items-center justify-center gap-2">
                <span className={cn('w-2 h-2 rounded-full', modules.market_hours.should_trade ? 'bg-bullish' : 'bg-bearish')} />
                <span className="text-xs">{modules.market_hours.should_trade ? 'Trading Active' : 'Trading Paused'}</span>
              </div>
              <p className="text-xs text-foreground-muted text-center">{modules.market_hours.reason}</p>
            </div>
          ) : (
            <p className="text-xs text-foreground-muted">Session data unavailable</p>
          )}
        </div>
      </div>

      {/* Module Summary Cards */}
      <div className="grid grid-cols-12 gap-4">
        {/* Order Flow */}
        <div className="col-span-3 card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-accent-primary" />
            <h4 className="text-xs font-bold text-foreground-muted">ORDER FLOW</h4>
          </div>
          {modules.order_flow && !modules.order_flow.error ? (
            <div className="space-y-2 text-xs">
              <div className={cn('text-center py-2 rounded', getStateColor(modules.order_flow.flow_direction))}>
                <span className="font-bold">{modules.order_flow.flow_direction}</span>
              </div>
              <div className="flex justify-between"><span className="text-foreground-muted">Imbalance</span><span className="font-mono">{(modules.order_flow.imbalance_ratio * 100).toFixed(1)}%</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">Toxicity</span><span className="font-mono">{(modules.order_flow.flow_toxicity * 100).toFixed(1)}%</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">Cum Delta</span><span className="font-mono">{modules.order_flow.cumulative_delta.toLocaleString()}</span></div>
              {modules.order_flow.absorption_detected && <span className="text-warning text-[10px]">Absorption detected</span>}
            </div>
          ) : <p className="text-xs text-foreground-muted">N/A</p>}
        </div>

        {/* Volatility Regime */}
        <div className="col-span-3 card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Waves className="w-4 h-4 text-accent-primary" />
            <h4 className="text-xs font-bold text-foreground-muted">VOL REGIME</h4>
          </div>
          {modules.volatility_regime && !modules.volatility_regime.error ? (
            <div className="space-y-2 text-xs">
              <div className={cn('text-center py-2 rounded', getStateColor(modules.volatility_regime.state))}>
                <span className="font-bold">{modules.volatility_regime.state}</span>
              </div>
              <div className="flex justify-between"><span className="text-foreground-muted">ATR %ile</span><span className="font-mono">{modules.volatility_regime.atr_percentile.toFixed(0)}%</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">BB Width %ile</span><span className="font-mono">{modules.volatility_regime.bollinger_width_percentile.toFixed(0)}%</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">VIX</span><span className="font-mono">{modules.volatility_regime.vix_level.toFixed(1)}</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">Size Mult</span><span className="font-mono">{modules.volatility_regime.position_size_multiplier.toFixed(2)}x</span></div>
            </div>
          ) : <p className="text-xs text-foreground-muted">N/A</p>}
        </div>

        {/* Liquidity */}
        <div className="col-span-3 card p-4">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 className="w-4 h-4 text-accent-primary" />
            <h4 className="text-xs font-bold text-foreground-muted">LIQUIDITY</h4>
          </div>
          {modules.liquidity && !modules.liquidity.error ? (
            <div className="space-y-2 text-xs">
              <div className={cn('text-center py-2 rounded', getStateColor(modules.liquidity.state))}>
                <span className="font-bold">{modules.liquidity.state}</span>
              </div>
              <div className="flex justify-between"><span className="text-foreground-muted">Spread</span><span className="font-mono">{modules.liquidity.spread_bps.toFixed(1)} bps</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">Rel Volume</span><span className="font-mono">{modules.liquidity.relative_volume.toFixed(2)}x</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">Depth</span><span className="font-mono">{(modules.liquidity.depth_score * 100).toFixed(0)}%</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">Est. Slippage</span><span className="font-mono">{modules.liquidity.fill_quality_estimate.toFixed(1)} bps</span></div>
            </div>
          ) : <p className="text-xs text-foreground-muted">N/A</p>}
        </div>

        {/* Cross-Asset */}
        <div className="col-span-3 card p-4">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-accent-primary" />
            <h4 className="text-xs font-bold text-foreground-muted">CROSS-ASSET</h4>
          </div>
          {modules.cross_asset && !modules.cross_asset.error ? (
            <div className="space-y-2 text-xs">
              <div className={cn('text-center py-2 rounded', modules.cross_asset.is_confirmed ? 'text-bullish bg-bullish/10' : 'text-warning bg-warning/10')}>
                <span className="font-bold">{modules.cross_asset.is_confirmed ? 'CONFIRMED' : 'UNCONFIRMED'}</span>
              </div>
              <div className="flex justify-between"><span className="text-foreground-muted">Score</span><span className={cn('font-mono', getScoreColor(modules.cross_asset.confirmation_score))}>{(modules.cross_asset.confirmation_score * 100).toFixed(0)}%</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">Sector</span><span className="font-mono">{(modules.cross_asset.sector_alignment * 100).toFixed(0)}%</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">Confirming</span><span className="text-bullish font-mono">{modules.cross_asset.confirming_assets?.length || 0}</span></div>
              <div className="flex justify-between"><span className="text-foreground-muted">Diverging</span><span className="text-bearish font-mono">{modules.cross_asset.diverging_assets?.length || 0}</span></div>
            </div>
          ) : <p className="text-xs text-foreground-muted">N/A</p>}
        </div>
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-warning" />
            <h3 className="text-xs font-bold text-foreground-muted">ACTIVE ALERTS ({alerts.length})</h3>
          </div>
          <div className="space-y-1">
            {alerts.map((alert: string, i: number) => (
              <div key={i} className="flex items-center gap-2 text-xs p-2 rounded bg-warning/5 border border-warning/20">
                <AlertTriangle className="w-3 h-3 text-warning flex-shrink-0" />
                <span className="text-warning">{alert}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Position Sizing */}
      {modules.position_sizing && !modules.position_sizing.error && (
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-4 h-4 text-accent-primary" />
            <h3 className="text-xs font-bold text-foreground-muted">ADAPTIVE POSITION SIZING</h3>
          </div>
          <div className="grid grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-foreground-muted">Base (Kelly)</span>
              <div className="font-mono text-lg">{(modules.position_sizing.base_size * 100).toFixed(2)}%</div>
            </div>
            <div>
              <span className="text-foreground-muted">Adjusted</span>
              <div className="font-mono text-lg text-accent-primary">{(modules.position_sizing.adjusted_size * 100).toFixed(2)}%</div>
            </div>
            <div>
              <span className="text-foreground-muted">Final</span>
              <div className="font-mono text-lg text-bullish">{(modules.position_sizing.final_size * 100).toFixed(2)}%</div>
            </div>
            <div>
              <span className="text-foreground-muted">Max Cap</span>
              <div className="font-mono text-lg">{(modules.position_sizing.max_size * 100).toFixed(2)}%</div>
            </div>
          </div>
          {modules.position_sizing.reasoning && (
            <div className="mt-3 pt-3 border-t border-border space-y-1">
              {modules.position_sizing.reasoning.map((r: string, i: number) => (
                <p key={i} className="text-[10px] text-foreground-muted font-mono">{r}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function OrderFlowTab({ analysis, getStateColor }: any) {
  const flow = analysis?.modules?.order_flow

  if (!flow || flow.error) {
    return <EmptyState icon={Activity} message="Run analysis to see order flow data" />
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-6 card p-6">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">FLOW DIRECTION & IMBALANCE</h3>
          <div className={cn('text-center py-4 rounded-lg mb-4', getStateColor(flow.flow_direction))}>
            <div className="text-3xl font-bold">{flow.flow_direction}</div>
            <div className="text-sm mt-1">Imbalance: {(flow.imbalance_ratio * 100).toFixed(2)}%</div>
          </div>
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div className="p-3 rounded bg-bullish/5">
              <span className="text-foreground-muted">Ask Volume (Buying)</span>
              <div className="text-bullish font-mono text-lg">{flow.ask_volume.toLocaleString()}</div>
            </div>
            <div className="p-3 rounded bg-bearish/5">
              <span className="text-foreground-muted">Bid Volume (Selling)</span>
              <div className="text-bearish font-mono text-lg">{flow.bid_volume.toLocaleString()}</div>
            </div>
          </div>
        </div>

        <div className="col-span-6 card p-6">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">FLOW METRICS</h3>
          <div className="space-y-4">
            <MetricBar label="Flow Toxicity" value={flow.flow_toxicity} max={1} color={flow.flow_toxicity > 0.7 ? 'bearish' : flow.flow_toxicity > 0.4 ? 'warning' : 'bullish'} />
            <MetricBar label="Iceberg Probability" value={flow.iceberg_probability} max={1} color={flow.iceberg_probability > 0.5 ? 'warning' : 'accent-primary'} />
            <div className="grid grid-cols-2 gap-4 text-xs mt-4">
              <div className="p-3 rounded bg-surface">
                <span className="text-foreground-muted">Net Flow</span>
                <div className={cn('font-mono text-lg', flow.net_flow > 0 ? 'text-bullish' : 'text-bearish')}>
                  {flow.net_flow > 0 ? '+' : ''}{flow.net_flow.toLocaleString()}
                </div>
              </div>
              <div className="p-3 rounded bg-surface">
                <span className="text-foreground-muted">Cumulative Delta</span>
                <div className={cn('font-mono text-lg', flow.cumulative_delta > 0 ? 'text-bullish' : 'text-bearish')}>
                  {flow.cumulative_delta > 0 ? '+' : ''}{flow.cumulative_delta.toLocaleString()}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <StatusBadge label="Absorption" active={flow.absorption_detected} />
              <StatusBadge label="Unusual Flow" active={flow.unusual_flow} />
            </div>
          </div>
        </div>
      </div>

      {flow.alerts?.length > 0 && (
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-2">FLOW ALERTS</h3>
          <div className="space-y-1">
            {flow.alerts.map((a: string, i: number) => (
              <div key={i} className="text-xs text-warning p-2 rounded bg-warning/5">{a}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function VolatilityTab({ analysis, getStateColor }: any) {
  const vol = analysis?.modules?.volatility_regime

  if (!vol || vol.error) {
    return <EmptyState icon={Waves} message="Run analysis to see volatility regime data" />
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 card p-6 text-center">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">VOLATILITY STATE</h3>
          <div className={cn('py-6 rounded-lg', getStateColor(vol.state))}>
            <div className="text-3xl font-bold">{vol.state}</div>
            <div className="text-sm mt-2">Confidence: {(vol.confidence * 100).toFixed(1)}%</div>
          </div>
          <div className="mt-4 text-xs text-foreground-muted">
            Duration: {vol.regime_duration_bars} bars
          </div>
        </div>

        <div className="col-span-8 card p-6">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">VOLATILITY METRICS</h3>
          <div className="space-y-4">
            <MetricBar label="ATR Percentile" value={vol.atr_percentile} max={100} suffix="%" color={vol.atr_percentile > 80 ? 'bearish' : vol.atr_percentile > 60 ? 'warning' : 'accent-primary'} />
            <MetricBar label="Bollinger Width Percentile" value={vol.bollinger_width_percentile} max={100} suffix="%" color={vol.bollinger_width_percentile > 80 ? 'bearish' : vol.bollinger_width_percentile > 60 ? 'warning' : 'accent-primary'} />
            <MetricBar label="Transition Probability" value={vol.transition_probability * 100} max={100} suffix="%" color="warning" />
          </div>
          <div className="grid grid-cols-3 gap-4 mt-4 text-xs">
            <div className="p-3 rounded bg-surface text-center">
              <span className="text-foreground-muted">VIX Level</span>
              <div className="font-mono text-lg">{vol.vix_level.toFixed(1)}</div>
            </div>
            <div className="p-3 rounded bg-surface text-center">
              <span className="text-foreground-muted">VIX Structure</span>
              <div className="font-mono text-lg capitalize">{vol.vix_term_structure}</div>
            </div>
            <div className="p-3 rounded bg-surface text-center">
              <span className="text-foreground-muted">Size Multiplier</span>
              <div className="font-mono text-lg text-accent-primary">{vol.position_size_multiplier.toFixed(2)}x</div>
            </div>
          </div>
        </div>
      </div>

      {vol.history?.length > 0 && (
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-3">REGIME TRANSITIONS</h3>
          <div className="space-y-1">
            {vol.history.slice(-10).map((h: any, i: number) => (
              <div key={i} className="flex items-center gap-2 text-xs p-2 rounded bg-surface">
                <span className={cn('px-2 py-0.5 rounded', getStateColor(h.from))}>{h.from}</span>
                <ArrowDownRight className="w-3 h-3 text-foreground-muted" />
                <span className={cn('px-2 py-0.5 rounded', getStateColor(h.to))}>{h.to}</span>
                <span className="text-foreground-muted ml-auto">Duration: {h.duration} bars</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function LiquidityTab({ analysis, getStateColor }: any) {
  const liq = analysis?.modules?.liquidity

  if (!liq || liq.error) {
    return <EmptyState icon={BarChart3} message="Run analysis to see liquidity data" />
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 card p-6 text-center">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">LIQUIDITY STATE</h3>
          <div className={cn('py-6 rounded-lg', getStateColor(liq.state))}>
            <div className="text-3xl font-bold">{liq.state}</div>
          </div>
          {liq.deteriorating && (
            <div className="mt-3 p-2 rounded bg-warning/10 text-warning text-xs flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> Deteriorating
            </div>
          )}
        </div>

        <div className="col-span-8 card p-6">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">LIQUIDITY METRICS</h3>
          <div className="space-y-4">
            <MetricBar label="Spread" value={liq.spread_bps} max={20} suffix=" bps" color={liq.spread_bps > 10 ? 'bearish' : liq.spread_bps > 5 ? 'warning' : 'bullish'} />
            <MetricBar label="Spread Percentile" value={liq.spread_percentile} max={100} suffix="%" color={liq.spread_percentile > 80 ? 'bearish' : 'accent-primary'} />
            <MetricBar label="Depth Score" value={liq.depth_score * 100} max={100} suffix="%" color="accent-primary" />
          </div>
          <div className="grid grid-cols-2 gap-4 mt-4 text-xs">
            <div className="p-3 rounded bg-surface">
              <span className="text-foreground-muted">Relative Volume</span>
              <div className={cn('font-mono text-lg', liq.relative_volume >= 1 ? 'text-bullish' : 'text-warning')}>{liq.relative_volume.toFixed(2)}x</div>
            </div>
            <div className="p-3 rounded bg-surface">
              <span className="text-foreground-muted">Est. Fill Slippage</span>
              <div className="font-mono text-lg">{liq.fill_quality_estimate.toFixed(1)} bps</div>
            </div>
          </div>
        </div>
      </div>

      {liq.alerts?.length > 0 && (
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-2">LIQUIDITY ALERTS</h3>
          <div className="space-y-1">
            {liq.alerts.map((a: string, i: number) => (
              <div key={i} className="text-xs text-warning p-2 rounded bg-warning/5">{a}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function SignalsTab({ analysis }: any) {
  const decay = analysis?.modules?.signal_decay

  if (!decay || decay.error) {
    return <EmptyState icon={Zap} message="Run analysis with a signal direction to see confidence decay" />
  }

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <h3 className="text-xs font-bold text-foreground-muted mb-4">SIGNAL CONFIDENCE DECAY</h3>
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="text-center p-3 rounded bg-surface">
            <span className="text-xs text-foreground-muted">Signal ID</span>
            <div className="font-mono text-sm mt-1">{decay.signal_id}</div>
          </div>
          <div className="text-center p-3 rounded bg-surface">
            <span className="text-xs text-foreground-muted">Direction</span>
            <div className={cn('font-mono text-sm mt-1 font-bold', decay.direction === 'BUY' ? 'text-bullish' : decay.direction === 'SELL' ? 'text-bearish' : 'text-foreground-muted')}>
              {decay.direction}
            </div>
          </div>
          <div className="text-center p-3 rounded bg-surface">
            <span className="text-xs text-foreground-muted">Initial Confidence</span>
            <div className="font-mono text-lg mt-1">{(decay.initial_confidence * 100).toFixed(1)}%</div>
          </div>
          <div className="text-center p-3 rounded bg-surface">
            <span className="text-xs text-foreground-muted">Current Confidence</span>
            <div className={cn('font-mono text-lg mt-1', decay.is_actionable ? 'text-accent-primary' : 'text-bearish')}>
              {(decay.current_confidence * 100).toFixed(1)}%
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <h4 className="text-xs font-bold text-foreground-muted">DECAY FACTORS</h4>
          {decay.factors && Object.entries(decay.factors).map(([key, val]: [string, any]) => (
            <div key={key} className="flex items-center justify-between text-xs">
              <span className="text-foreground-muted capitalize">{key.replace(/_/g, ' ')}</span>
              <span className="font-mono">{(val * 100).toFixed(2)}%</span>
            </div>
          ))}
        </div>

        <div className="mt-4 pt-4 border-t border-border flex items-center justify-between text-xs">
          <span className="text-foreground-muted">Age: {decay.time_alive_seconds.toFixed(0)}s</span>
          <span className="text-foreground-muted">Decay rate: {(decay.decay_rate * 100).toFixed(3)}%/min</span>
          <StatusBadge label="Actionable" active={decay.is_actionable} />
        </div>
      </div>
    </div>
  )
}

function SizingTab({ analysis }: any) {
  const sizing = analysis?.modules?.position_sizing

  if (!sizing || sizing.error) {
    return <EmptyState icon={Shield} message="Run analysis with a signal direction to see position sizing" />
  }

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <h3 className="text-xs font-bold text-foreground-muted mb-4">ADAPTIVE POSITION SIZING</h3>
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="text-center p-4 rounded bg-surface">
            <span className="text-xs text-foreground-muted">Base (Kelly)</span>
            <div className="font-mono text-2xl mt-1">{(sizing.base_size * 100).toFixed(2)}%</div>
          </div>
          <div className="text-center p-4 rounded bg-surface">
            <span className="text-xs text-foreground-muted">Adjusted</span>
            <div className="font-mono text-2xl mt-1 text-accent-primary">{(sizing.adjusted_size * 100).toFixed(2)}%</div>
          </div>
          <div className="text-center p-4 rounded bg-surface">
            <span className="text-xs text-foreground-muted">Final</span>
            <div className="font-mono text-2xl mt-1 text-bullish">{(sizing.final_size * 100).toFixed(2)}%</div>
          </div>
          <div className="text-center p-4 rounded bg-surface">
            <span className="text-xs text-foreground-muted">Max Cap</span>
            <div className="font-mono text-2xl mt-1">{(sizing.max_size * 100).toFixed(2)}%</div>
          </div>
        </div>

        <h4 className="text-xs font-bold text-foreground-muted mb-3">ADJUSTMENT FACTORS</h4>
        <div className="space-y-3">
          {sizing.adjustments && Object.entries(sizing.adjustments).map(([key, val]: [string, any]) => (
            <MetricBar key={key} label={key.replace(/_/g, ' ')} value={val * 100} max={120} suffix="%" color={val >= 0.8 ? 'bullish' : val >= 0.5 ? 'warning' : 'bearish'} />
          ))}
        </div>

        <h4 className="text-xs font-bold text-foreground-muted mt-6 mb-2">REASONING</h4>
        <div className="space-y-1">
          {sizing.reasoning?.map((r: string, i: number) => (
            <p key={i} className="text-[10px] text-foreground-muted font-mono p-1 rounded bg-surface">{r}</p>
          ))}
        </div>
      </div>
    </div>
  )
}

function SessionsTab({ sessions }: any) {
  if (!sessions) {
    return <EmptyState icon={Clock} message="Loading session profiles..." />
  }

  const getActionColor = (action: string) => {
    switch (action) {
      case 'trade_normal': return 'text-bullish bg-bullish/10'
      case 'aggressive': return 'text-accent-primary bg-accent-primary/10'
      case 'reduce_size': return 'text-warning bg-warning/10'
      case 'avoid': return 'text-bearish bg-bearish/10'
      default: return 'text-foreground-muted bg-surface'
    }
  }

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-bold text-foreground-muted">CURRENT SESSION</h3>
          <div className="flex items-center gap-2">
            <span className={cn('w-2 h-2 rounded-full', sessions.should_trade ? 'bg-bullish' : 'bg-bearish')} />
            <span className="text-xs">{sessions.should_trade ? 'Trading Active' : 'Trading Paused'}</span>
          </div>
        </div>
        <div className="text-center py-4">
          <div className="text-3xl font-bold text-accent-primary">{sessions.current_session}</div>
          <p className="text-xs text-foreground-muted mt-2">{sessions.reason}</p>
          <p className="text-xs text-foreground-muted mt-1">Size multiplier: {sessions.size_multiplier}x</p>
        </div>
      </div>

      <div className="card p-6">
        <h3 className="text-xs font-bold text-foreground-muted mb-4">ALL SESSION PROFILES</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-foreground-muted border-b border-border">
                <th className="text-left py-2 px-3">Session</th>
                <th className="text-right py-2 px-3">Volatility</th>
                <th className="text-right py-2 px-3">Volume</th>
                <th className="text-right py-2 px-3">Spread</th>
                <th className="text-right py-2 px-3">Win Rate</th>
                <th className="text-right py-2 px-3">Avg P&L</th>
                <th className="text-right py-2 px-3">Trades</th>
                <th className="text-center py-2 px-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {sessions.profiles?.map((p: any) => (
                <tr key={p.session} className={cn('border-b border-border/50', p.session === sessions.current_session && 'bg-accent-primary/5')}>
                  <td className="py-2 px-3 font-mono font-bold">{p.session}</td>
                  <td className="py-2 px-3 text-right font-mono">{p.avg_volatility.toFixed(1)}</td>
                  <td className="py-2 px-3 text-right font-mono">{p.avg_volume_ratio.toFixed(1)}x</td>
                  <td className="py-2 px-3 text-right font-mono">{p.avg_spread_bps.toFixed(1)} bps</td>
                  <td className="py-2 px-3 text-right font-mono">{(p.win_rate * 100).toFixed(0)}%</td>
                  <td className={cn('py-2 px-3 text-right font-mono', p.avg_pnl >= 0 ? 'text-bullish' : 'text-bearish')}>${p.avg_pnl.toFixed(0)}</td>
                  <td className="py-2 px-3 text-right font-mono">{p.trade_count}</td>
                  <td className="py-2 px-3 text-center">
                    <span className={cn('px-2 py-0.5 rounded text-[10px] font-bold', getActionColor(p.recommended_action))}>
                      {p.recommended_action.replace('_', ' ').toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function CrossAssetTab({ analysis, getStateColor }: any) {
  const cross = analysis?.modules?.cross_asset

  if (!cross || cross.error) {
    return <EmptyState icon={TrendingUp} message="Run analysis to see cross-asset validation" />
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-4 card p-6 text-center">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">VALIDATION RESULT</h3>
          <div className={cn('py-6 rounded-lg', cross.is_confirmed ? 'text-bullish bg-bullish/10' : 'text-bearish bg-bearish/10')}>
            <div className="text-3xl font-bold">{cross.is_confirmed ? 'CONFIRMED' : 'NOT CONFIRMED'}</div>
            <div className="text-sm mt-2">Direction: {cross.signal_direction}</div>
          </div>
          <div className="mt-4 text-2xl font-mono font-bold">
            {(cross.confirmation_score * 100).toFixed(0)}%
          </div>
          <div className="text-xs text-foreground-muted">Confirmation Score</div>
        </div>

        <div className="col-span-8 card p-6">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">COMPONENT SCORES</h3>
          <div className="space-y-4">
            <MetricBar label="Sector Alignment" value={(cross.sector_alignment + 1) * 50} max={100} suffix="%" color={cross.sector_alignment > 0 ? 'bullish' : 'bearish'} />
            <MetricBar label="Correlation Check" value={(cross.correlation_check + 1) * 50} max={100} suffix="%" color={cross.correlation_check > 0 ? 'bullish' : 'bearish'} />
            <MetricBar label="Options Flow" value={(cross.options_flow_alignment + 1) * 50} max={100} suffix="%" color={cross.options_flow_alignment > 0 ? 'bullish' : 'bearish'} />
          </div>

          <div className="grid grid-cols-2 gap-4 mt-6">
            <div>
              <h4 className="text-xs font-bold text-bullish mb-2">CONFIRMING ({cross.confirming_assets?.length || 0})</h4>
              <div className="space-y-1">
                {cross.confirming_assets?.map((a: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs p-2 rounded bg-bullish/5">
                    <ArrowUpRight className="w-3 h-3 text-bullish" />
                    <span className="font-mono">{a.asset}</span>
                    <span className="text-foreground-muted ml-auto">{(a.return * 100).toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-xs font-bold text-bearish mb-2">DIVERGING ({cross.diverging_assets?.length || 0})</h4>
              <div className="space-y-1">
                {cross.diverging_assets?.map((a: any, i: number) => (
                  <div key={i} className="flex flex-col gap-1 text-xs p-2 rounded bg-bearish/5">
                    <div className="flex items-center gap-2">
                      <ArrowDownRight className="w-3 h-3 text-bearish" />
                      <span className="font-mono">{a.asset}</span>
                      <span className="text-foreground-muted ml-auto">{(a.return * 100).toFixed(2)}%</span>
                    </div>
                    {a.warning && <span className="text-bearish text-[10px]">{a.warning}</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ConfigTab({ status, onRefresh }: any) {
  const [saving, setSaving] = useState(false)
  const [modules, setModules] = useState<ModuleStatus>({
    order_flow: true,
    volatility_regime: true,
    liquidity_monitor: true,
    signal_decay: true,
    adaptive_sizing: true,
    market_hours: true,
    cross_asset: true,
  })

  useEffect(() => {
    if (status?.config?.modules) {
      setModules(status.config.modules)
    }
  }, [status])

  const toggleModule = async (key: keyof ModuleStatus) => {
    const updated = { ...modules, [key]: !modules[key] }
    setModules(updated)
    setSaving(true)
    try {
      await fetch('/api/microstructure/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modules: updated }),
      })
      onRefresh()
    } catch {
      // Revert on failure
      setModules(modules)
    } finally {
      setSaving(false)
    }
  }

  const moduleDescriptions: Record<string, string> = {
    order_flow: 'Track bid/ask imbalance, detect absorption and iceberg orders, flow toxicity scoring',
    volatility_regime: 'Classify volatility state (Compressed/Normal/Expanding/Crisis), auto-adjust sizing',
    liquidity_monitor: 'Monitor spreads, depth, volume patterns. Detect liquidity vacuums.',
    signal_decay: 'Time-based confidence decay with regime/performance/correlation modifiers',
    adaptive_sizing: 'Kelly criterion with fractional scaling, adjusted for regime, confidence, drawdown',
    market_hours: 'Session-aware behavior profiles with time-of-day performance attribution',
    cross_asset: 'Validate signals against sector ETFs, correlated assets, and options flow',
  }

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-bold text-foreground-muted">MODULE CONFIGURATION</h3>
          {saving && <span className="text-xs text-accent-primary">Saving...</span>}
        </div>
        <div className="space-y-3">
          {Object.entries(modules).map(([key, enabled]) => (
            <div key={key} className="flex items-center justify-between p-3 rounded bg-surface">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className={cn('text-[10px] px-1.5 py-0.5 rounded font-mono', enabled ? 'bg-bullish/10 text-bullish' : 'bg-surface text-foreground-muted')}>
                    {enabled ? 'ON' : 'OFF'}
                  </span>
                </div>
                <p className="text-[10px] text-foreground-muted mt-1">{moduleDescriptions[key]}</p>
              </div>
              <button
                onClick={() => toggleModule(key as keyof ModuleStatus)}
                className={cn(
                  'w-10 h-5 rounded-full transition-colors relative',
                  enabled ? 'bg-accent-primary' : 'bg-border'
                )}
              >
                <div className={cn(
                  'w-4 h-4 rounded-full bg-white absolute top-0.5 transition-transform',
                  enabled ? 'translate-x-5' : 'translate-x-0.5'
                )} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {status?.module_stats && (
        <div className="card p-6">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">MODULE STATISTICS</h3>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(status.module_stats).map(([mod, stats]: [string, any]) => (
              <div key={mod} className="p-3 rounded bg-surface">
                <h4 className="text-xs font-bold capitalize mb-2">{mod.replace(/_/g, ' ')}</h4>
                <div className="space-y-1 text-[10px]">
                  {Object.entries(stats).map(([key, val]: [string, any]) => (
                    <div key={key} className="flex justify-between">
                      <span className="text-foreground-muted">{key.replace(/_/g, ' ')}</span>
                      <span className="font-mono">{typeof val === 'number' ? val.toLocaleString() : val}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ============== Shared Components ==============

function MetricBar({ label, value, max, suffix, color }: { label: string; value: number; max: number; suffix?: string; color: string }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const colorClass = {
    bullish: 'bg-bullish',
    bearish: 'bg-bearish',
    warning: 'bg-warning',
    'accent-primary': 'bg-accent-primary',
  }[color] || 'bg-accent-primary'

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-foreground-muted">{label}</span>
        <span className="font-mono">{value.toFixed(1)}{suffix || ''}</span>
      </div>
      <div className="w-full h-1.5 bg-surface rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', colorClass)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function StatusBadge({ label, active }: { label: string; active: boolean }) {
  return (
    <span className={cn(
      'px-2 py-0.5 rounded text-[10px] font-mono',
      active ? 'bg-warning/10 text-warning' : 'bg-surface text-foreground-muted'
    )}>
      {label}: {active ? 'YES' : 'NO'}
    </span>
  )
}

function EmptyState({ icon: Icon, message }: { icon: any; message: string }) {
  return (
    <div className="card p-12 text-center">
      <Icon className="w-10 h-10 text-foreground-muted mx-auto mb-4 opacity-30" />
      <p className="text-foreground-muted text-sm">{message}</p>
    </div>
  )
}
