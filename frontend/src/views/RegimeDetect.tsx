import { Gauge, RefreshCw } from 'lucide-react'
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
      const response = await fetch('/api/market/regime')
      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail || 'Failed to detect regime')
      }

      if (result.status === 'unavailable') {
        setError(result.message || 'Regime detection not available. Configure market data API to enable.')
        setRegime(null)
        return
      }

      const data = result.data || result
      const current = data.regime || data.current || 'RANGING'

      setRegime({
        current: current.toUpperCase(),
        confidence: data.confidence || 75,
        indicators: data.indicators || {
          trend_strength: data.trend_strength || 50,
          volatility: data.volatility || 'LOW',
          momentum: data.momentum || 'NEUTRAL',
          mean_reversion_prob: data.mean_reversion_prob || 0.3
        },
        history: data.history || [],
        strategies: data.strategies || (
          current === 'BULL' || current === 'bull'
            ? ['Momentum', 'Trend Following', 'Breakout']
            : current === 'BEAR' || current === 'bear'
            ? ['Mean Reversion', 'Hedging', 'Short Selling']
            : ['Range Trading', 'Iron Condors', 'Pairs Trading']
        )
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
      case 'BULL': return 'text-bullish bg-bullish/10'
      case 'BEAR': return 'text-bearish bg-bearish/10'
      default: return 'text-warning bg-warning/10'
    }
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
            <h3 className="text-xs font-bold text-foreground-muted mb-4 text-center">CURRENT REGIME</h3>
            <div className={cn(
              'p-6 rounded-lg text-center',
              getRegimeColor(regime.current)
            )}>
              <div className="text-4xl font-bold mb-2">{regime.current}</div>
              <div className="text-sm">Confidence: {regime.confidence.toFixed(1)}%</div>
            </div>
          </div>

          {/* Indicators */}
          <div className="col-span-4 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">REGIME INDICATORS</h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs">Trend Strength</span>
                  <span className="text-xs font-mono">{regime.indicators.trend_strength.toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent-primary rounded-full"
                    style={{ width: `${regime.indicators.trend_strength}%` }}
                  />
                </div>
              </div>
              <div className="flex justify-between py-2 border-b border-border">
                <span className="text-xs text-foreground-muted">Volatility Regime</span>
                <span className={cn(
                  'text-xs font-bold',
                  regime.indicators.volatility === 'HIGH' ? 'text-warning' : 'text-bullish'
                )}>
                  {regime.indicators.volatility}
                </span>
              </div>
              <div className="flex justify-between py-2 border-b border-border">
                <span className="text-xs text-foreground-muted">Momentum State</span>
                <span className={cn(
                  'text-xs font-bold',
                  regime.indicators.momentum === 'POSITIVE' ? 'text-bullish' : 'text-bearish'
                )}>
                  {regime.indicators.momentum}
                </span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-xs text-foreground-muted">Mean Reversion Prob</span>
                <span className="text-xs font-mono">{(regime.indicators.mean_reversion_prob * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>

          {/* Recommended Strategies */}
          <div className="col-span-4 card p-4">
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
              Strategies optimized for {regime.current.toLowerCase()} market conditions
            </p>
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
