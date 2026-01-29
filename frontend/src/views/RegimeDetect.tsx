import { Gauge, RefreshCw, AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

export function RegimeDetect() {
  const [analyzing, setAnalyzing] = useState(false)
  const [regime, setRegime] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const analyze = async () => {
    setAnalyzing(true)
    setError(null)

    try {
      // Use the new HMM-based regime detection endpoint
      const response = await fetch('/api/regime/detect?symbol=SPY')
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to detect regime')
      }

      if (!data.fitted) {
        setError(data.message || 'HMM not fitted yet. Need more market data.')
        setRegime(null)
        return
      }

      // Map HMM regime to display format
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
        confidence: (data.confidence * 100),
        probabilities: data.probabilities,
        indicators: {
          trend_strength: ((data.trend_strength + 1) / 2 * 100), // Convert -1,1 to 0-100
          volatility: data.volatility_regime?.toUpperCase() || 'NORMAL',
          expected_return: data.expected_return,
          expected_vol: data.expected_volatility,
          regime_duration: data.regime_duration
        },
        risk_adjustments: {
          position_scalar: data.position_scalar,
          stop_multiplier: data.stop_multiplier,
          profit_multiplier: data.profit_multiplier
        },
        strategies: strategyMap[data.regime] || ['Wait for Clarity'],
        history: [] // Would need historical data
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to detect regime')
      setRegime(null)
    } finally {
      setAnalyzing(false)
    }
  }

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
        <button onClick={analyze} disabled={analyzing} className="btn-primary flex items-center gap-2">
          <RefreshCw className={cn('w-4 h-4', analyzing && 'animate-spin')} />
          Detect Regime
        </button>
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
            <h3 className="text-xs font-bold text-foreground-muted mb-4 text-center">HMM REGIME DETECTION</h3>
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
                  {(regime.indicators.expected_return * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-xs text-foreground-muted">Expected Volatility</span>
                <span className="text-xs font-mono">{(regime.indicators.expected_vol * 100).toFixed(1)}%</span>
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
              Strategies optimized for {regime.rawRegime.toLowerCase().replace('_', ' ')} conditions
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
                    <span className="text-xs w-24">{state}</span>
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

          {/* Regime History */}
          <div className="col-span-12 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">REGIME HISTORY (12 MONTHS)</h3>
            <div className="flex gap-1">
              {regime.history.map((h: any, i: number) => (
                <div key={i} className="flex-1 text-center">
                  <div
                    className={cn(
                      'h-16 rounded flex items-center justify-center text-xs font-bold',
                      getRegimeColor(h.regime)
                    )}
                  >
                    {h.regime.charAt(0)}
                  </div>
                  <div className="text-xs text-foreground-muted mt-1">{h.month.slice(5)}</div>
                </div>
              ))}
            </div>
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
                <span className="text-xs">Ranging</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
