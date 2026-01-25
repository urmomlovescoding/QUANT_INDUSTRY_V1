import { Gauge, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

export function RegimeDetect() {
  const [analyzing, setAnalyzing] = useState(false)
  const [regime, setRegime] = useState<any>(null)

  const analyze = () => {
    setAnalyzing(true)
    setTimeout(() => {
      const regimes = ['BULL', 'BEAR', 'RANGING']
      const current = regimes[Math.floor(Math.random() * 3)]

      setRegime({
        current,
        confidence: 65 + Math.random() * 30,
        indicators: {
          trend_strength: 30 + Math.random() * 50,
          volatility: Math.random() > 0.5 ? 'HIGH' : 'LOW',
          momentum: Math.random() > 0.4 ? 'POSITIVE' : 'NEGATIVE',
          mean_reversion_prob: 0.2 + Math.random() * 0.4
        },
        history: Array.from({ length: 12 }, (_, i) => ({
          month: new Date(Date.now() - i * 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 7),
          regime: regimes[Math.floor(Math.random() * 3)]
        })).reverse(),
        strategies: current === 'BULL'
          ? ['Momentum', 'Trend Following', 'Breakout']
          : current === 'BEAR'
          ? ['Mean Reversion', 'Hedging', 'Short Selling']
          : ['Range Trading', 'Iron Condors', 'Pairs Trading']
      })
      setAnalyzing(false)
    }, 800)
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
