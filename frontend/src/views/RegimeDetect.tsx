import { Gauge, RefreshCw, AlertTriangle, TrendingUp, TrendingDown, Clock, BarChart3 } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { cn } from '@/utils/cn'

interface RegimeTransition {
  from_regime: string
  to_regime: string
  timestamp: string
  confidence: number
}

export function RegimeDetect() {
  const [analyzing, setAnalyzing] = useState(false)
  const [regime, setRegime] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [symbol, setSymbol] = useState('SPY')
  const [transitions, setTransitions] = useState<RegimeTransition[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const timelineCanvasRef = useRef<HTMLCanvasElement>(null)

  const symbols = ['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL']

  const analyze = async () => {
    setAnalyzing(true)
    setError(null)

    try {
      const response = await fetch(`/api/regime/detect/${symbol}`, { method: 'POST' })

      if (!response.ok) {
        let detail = 'Failed to detect regime'
        try {
          const errData = await response.json()
          detail = errData.detail || detail
        } catch {}
        throw new Error(detail)
      }

      const data = await response.json()

      if (data.regime === undefined) {
        setError('Regime detection returned no data.')
        setRegime(null)
        return
      }

      const regimeMap: Record<string, string> = {
        'BULL_STRONG': 'BULL',
        'BULL_WEAK': 'BULL_WEAK',
        'NEUTRAL': 'NEUTRAL',
        'BEAR_WEAK': 'BEAR_WEAK',
        'BEAR_STRONG': 'BEAR',
        'CRISIS': 'CRISIS',
        'EUPHORIA': 'EUPHORIA'
      }

      const strategyMap: Record<string, string[]> = {
        'BULL_STRONG': ['Momentum', 'Trend Following', 'Breakout'],
        'BULL_WEAK': ['Selective Longs', 'Covered Calls', 'Sector Rotation'],
        'NEUTRAL': ['Range Trading', 'Iron Condors', 'Pairs Trading'],
        'BEAR_WEAK': ['Defensive', 'Put Spreads', 'Reduced Exposure'],
        'BEAR_STRONG': ['Mean Reversion', 'Hedging', 'Short Selling'],
        'CRISIS': ['Cash', 'Tail Hedges', 'VIX Calls'],
        'EUPHORIA': ['Take Profits', 'Trailing Stops', 'Reduce Size']
      }

      setRegime({
        current: regimeMap[data.regime] || data.regime,
        rawRegime: data.regime,
        confidence: (data.confidence || 0) * 100,
        probabilities: data.probabilities || data.metrics || {},
        indicators: {
          trend_strength: ((data.trend_strength || 0) + 1) / 2 * 100,
          volatility: data.volatility_regime?.toUpperCase() || data.volatility_level > 0.5 ? 'HIGH' : 'NORMAL',
          expected_return: data.expected_return || 0,
          expected_vol: data.expected_volatility || data.volatility_level || 0,
          regime_duration: data.regime_duration || data.duration || 0
        },
        risk_adjustments: {
          position_scalar: data.position_scalar || 1.0,
          stop_multiplier: data.stop_multiplier || 1.0,
          profit_multiplier: data.profit_multiplier || 1.0
        },
        strategies: strategyMap[data.regime] || ['Wait for Clarity'],
      })

      // Fetch history after successful detection
      fetchHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to detect regime')
      setRegime(null)
    } finally {
      setAnalyzing(false)
    }
  }

  const fetchHistory = async () => {
    setLoadingHistory(true)
    try {
      const response = await fetch(`/api/regime/history/${symbol}?limit=20`)
      if (response.ok) {
        const data = await response.json()
        setTransitions(data.transitions || [])
      }
    } catch {
      // History not available, not critical
    } finally {
      setLoadingHistory(false)
    }
  }

  // Auto-analyze on mount
  useEffect(() => {
    analyze()
  }, [])

  // Redraw timeline canvas when transitions change
  useEffect(() => {
    if (!timelineCanvasRef.current || transitions.length === 0) return

    const canvas = timelineCanvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    const width = rect.width
    const height = rect.height
    const padding = 20

    ctx.fillStyle = '#0d1117'
    ctx.fillRect(0, 0, width, height)

    const barH = 30
    const barY = height / 2 - barH / 2
    const chartW = width - padding * 2

    // Draw timeline bar segments
    const segmentW = chartW / Math.max(transitions.length, 1)
    transitions.forEach((t, i) => {
      const x = padding + i * segmentW
      const regime = t.to_regime || ''

      let color = '#6b7280' // neutral gray
      if (regime.includes('BULL')) color = '#00c853'
      else if (regime.includes('BEAR')) color = '#ff5252'
      else if (regime === 'CRISIS') color = '#ef4444'
      else if (regime === 'EUPHORIA') color = '#fbbf24'

      ctx.fillStyle = color
      ctx.fillRect(x + 1, barY, segmentW - 2, barH)

      // Label
      ctx.fillStyle = '#fff'
      ctx.font = '9px monospace'
      ctx.textAlign = 'center'
      if (segmentW > 30) {
        ctx.fillText(regime.substring(0, 4), x + segmentW / 2, barY + barH / 2 + 3)
      }

      // Timestamp below
      if (t.timestamp && segmentW > 50) {
        ctx.fillStyle = '#666'
        ctx.font = '8px monospace'
        const date = new Date(t.timestamp)
        ctx.fillText(
          `${date.getMonth() + 1}/${date.getDate()}`,
          x + segmentW / 2,
          barY + barH + 14
        )
      }
    })

    // Title
    ctx.fillStyle = '#888'
    ctx.font = '10px sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText('Regime Transitions', padding, 14)
  }, [transitions])

  const getRegimeColor = (r: string) => {
    switch (r) {
      case 'BULL':
      case 'BULL_STRONG': return 'text-bullish bg-bullish/10'
      case 'BULL_WEAK': return 'text-bullish/70 bg-bullish/5'
      case 'BEAR':
      case 'BEAR_STRONG': return 'text-bearish bg-bearish/10'
      case 'BEAR_WEAK': return 'text-bearish/70 bg-bearish/5'
      case 'CRISIS': return 'text-red-500 bg-red-500/20'
      case 'EUPHORIA': return 'text-yellow-400 bg-yellow-400/10'
      default: return 'text-warning bg-warning/10'
    }
  }

  const getRegimeIcon = (r: string) => {
    if (r.includes('BULL')) return <TrendingUp className="w-8 h-8" />
    if (r.includes('BEAR') || r === 'CRISIS') return <TrendingDown className="w-8 h-8" />
    if (r === 'EUPHORIA') return <AlertTriangle className="w-8 h-8" />
    return <Gauge className="w-8 h-8" />
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Gauge className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">REGIME DETECTION</h1>
            <p className="text-xs text-foreground-muted">Market regime classification using HMM</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            {symbols.map(s => (
              <button
                key={s}
                onClick={() => { setSymbol(s) }}
                className={cn(
                  'px-2 py-1 text-xs rounded transition-colors',
                  symbol === s ? 'bg-accent-primary text-background-primary' : 'bg-background-tertiary text-foreground-muted hover:text-white'
                )}
              >
                {s}
              </button>
            ))}
          </div>
          <button onClick={analyze} disabled={analyzing} className="btn-primary flex items-center gap-2">
            <RefreshCw className={cn('w-4 h-4', analyzing && 'animate-spin')} />
            Detect Regime
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {regime && (
        <div className="grid grid-cols-12 gap-4">
          {/* Current Regime */}
          <div className="col-span-4 card p-6">
            <h3 className="text-xs font-bold text-foreground-muted mb-4 text-center">HMM REGIME DETECTION — {symbol}</h3>
            <div className={cn(
              'p-6 rounded-lg text-center',
              getRegimeColor(regime.rawRegime)
            )}>
              {getRegimeIcon(regime.rawRegime)}
              <div className="text-3xl font-bold my-2">{regime.rawRegime}</div>
              <div className="text-sm">Confidence: {regime.confidence.toFixed(1)}%</div>
              {regime.indicators.regime_duration > 1 && (
                <div className="text-xs mt-2 opacity-70">
                  In regime for {regime.indicators.regime_duration} bars
                </div>
              )}
            </div>
          </div>

          {/* HMM Indicators */}
          <div className="col-span-4 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">HMM INDICATORS</h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs">Trend Strength</span>
                  <span className="text-xs font-mono">{regime.indicators.trend_strength.toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      regime.indicators.trend_strength > 50 ? "bg-bullish" : "bg-bearish"
                    )}
                    style={{ width: `${regime.indicators.trend_strength}%` }}
                  />
                </div>
              </div>
              <div className="flex justify-between py-2 border-b border-border">
                <span className="text-xs text-foreground-muted">Volatility Regime</span>
                <span className={cn(
                  'text-xs font-bold',
                  regime.indicators.volatility === 'HIGH' || regime.indicators.volatility === 'EXTREME'
                    ? 'text-warning'
                    : 'text-bullish'
                )}>
                  {regime.indicators.volatility}
                </span>
              </div>
              <div className="flex justify-between py-2 border-b border-border">
                <span className="text-xs text-foreground-muted">Expected Return (Ann.)</span>
                <span className={cn(
                  'text-xs font-bold',
                  regime.indicators.expected_return > 0 ? 'text-bullish' : 'text-bearish'
                )}>
                  {((regime.indicators.expected_return || 0) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-xs text-foreground-muted">Expected Volatility</span>
                <span className="text-xs font-mono">{((regime.indicators.expected_vol || 0) * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>

          {/* Risk Adjustments */}
          <div className="col-span-4 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">RISK ADJUSTMENTS</h3>
            <div className="space-y-4">
              <div className="p-3 bg-background-tertiary rounded">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-foreground-muted">Position Scalar</span>
                  <span className={cn(
                    'text-lg font-bold',
                    regime.risk_adjustments.position_scalar < 0.75 ? 'text-warning' : 'text-bullish'
                  )}>
                    {regime.risk_adjustments.position_scalar.toFixed(2)}x
                  </span>
                </div>
                <p className="text-xs text-foreground-muted mt-1">
                  {regime.risk_adjustments.position_scalar < 1 ? 'Reduce' : 'Increase'} position sizes
                </p>
              </div>
              <div className="p-3 bg-background-tertiary rounded">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-foreground-muted">Stop Multiplier</span>
                  <span className="text-lg font-bold">{regime.risk_adjustments.stop_multiplier.toFixed(2)}x</span>
                </div>
                <p className="text-xs text-foreground-muted mt-1">
                  {regime.risk_adjustments.stop_multiplier > 1 ? 'Widen' : 'Tighten'} stop losses
                </p>
              </div>
              <div className="p-3 bg-background-tertiary rounded">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-foreground-muted">Profit Multiplier</span>
                  <span className="text-lg font-bold">{regime.risk_adjustments.profit_multiplier.toFixed(2)}x</span>
                </div>
                <p className="text-xs text-foreground-muted mt-1">
                  Target multiplier for take-profit
                </p>
              </div>
            </div>
          </div>

          {/* Recommended Strategies */}
          <div className="col-span-6 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">RECOMMENDED STRATEGIES</h3>
            <div className="space-y-2">
              {regime.strategies.map((s: string) => (
                <div key={s} className="p-3 bg-background-tertiary rounded flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-accent-primary" />
                  <span className="text-sm font-medium">{s}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-foreground-muted mt-4">
              Strategies optimized for {(regime.rawRegime || '').toLowerCase().replace('_', ' ')} conditions
            </p>
          </div>

          {/* State Probabilities */}
          <div className="col-span-6 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">STATE PROBABILITIES</h3>
            <div className="space-y-2">
              {regime.probabilities && Object.entries(regime.probabilities)
                .sort(([,a], [,b]) => (b as number) - (a as number))
                .map(([state, prob]) => (
                  <div key={state} className="flex items-center gap-2">
                    <span className="text-xs w-28 truncate">{state}</span>
                    <div className="flex-1 h-2 bg-background-tertiary rounded-full overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full",
                          state.includes('BULL') ? "bg-bullish" :
                          state.includes('BEAR') ? "bg-bearish" : "bg-warning"
                        )}
                        style={{ width: `${Math.min((prob as number) * 100, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono w-16 text-right">
                      {((prob as number) * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
            </div>
          </div>

          {/* Regime Transition History */}
          <div className="col-span-12 card p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-bold text-foreground-muted flex items-center gap-2">
                <Clock className="w-3 h-3" />
                REGIME TRANSITION HISTORY
              </h3>
              {loadingHistory && <RefreshCw className="w-3 h-3 animate-spin text-foreground-muted" />}
            </div>

            {transitions.length > 0 ? (
              <>
                <canvas ref={timelineCanvasRef} className="w-full h-[80px] mb-4" />
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-2 px-3 text-foreground-muted">Timestamp</th>
                        <th className="text-left py-2 px-3 text-foreground-muted">From</th>
                        <th className="text-center py-2 px-3 text-foreground-muted"></th>
                        <th className="text-left py-2 px-3 text-foreground-muted">To</th>
                        <th className="text-right py-2 px-3 text-foreground-muted">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transitions.map((t, i) => (
                        <tr key={i} className="border-b border-border/30 hover:bg-background-tertiary">
                          <td className="py-2 px-3 font-mono">
                            {t.timestamp ? new Date(t.timestamp).toLocaleString() : '-'}
                          </td>
                          <td className="py-2 px-3">
                            <span className={cn(
                              'px-2 py-0.5 rounded',
                              getRegimeColor(t.from_regime || '')
                            )}>
                              {t.from_regime || '-'}
                            </span>
                          </td>
                          <td className="text-center py-2 px-3 text-foreground-muted">→</td>
                          <td className="py-2 px-3">
                            <span className={cn(
                              'px-2 py-0.5 rounded',
                              getRegimeColor(t.to_regime || '')
                            )}>
                              {t.to_regime || '-'}
                            </span>
                          </td>
                          <td className="text-right py-2 px-3 font-mono">
                            {((t.confidence || 0) * 100).toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-[100px] text-foreground-muted">
                <BarChart3 className="w-6 h-6 mb-2 opacity-30" />
                <p className="text-xs">No transition history available</p>
                <p className="text-xs opacity-50">Run regime detection to build history</p>
              </div>
            )}

            {/* Legend */}
            <div className="flex items-center gap-4 mt-4 justify-center">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-bullish" />
                <span className="text-xs">Bull</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-bearish" />
                <span className="text-xs">Bear</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-warning" />
                <span className="text-xs">Neutral</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-yellow-400" />
                <span className="text-xs">Euphoria</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded bg-red-500" />
                <span className="text-xs">Crisis</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* No Data State */}
      {!regime && !error && !analyzing && (
        <div className="card p-12 text-center">
          <Gauge className="w-12 h-12 mx-auto mb-4 text-foreground-muted opacity-30" />
          <p className="text-foreground-muted mb-2">Click "Detect Regime" to analyze current market conditions</p>
          <p className="text-xs text-foreground-muted opacity-50">Uses Hidden Markov Model for 7-state regime classification</p>
        </div>
      )}
    </div>
  )
}
