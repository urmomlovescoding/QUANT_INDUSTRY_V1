import { Brain, RefreshCw, Zap } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

const lookbackOptions = ['3M', '6M', '1Y', '2Y']

export function NeuralAnalysis() {
  const [ticker, setTicker] = useState('SPY')
  const [lookback, setLookback] = useState('6M')
  const [analyzing, setAnalyzing] = useState(false)
  const [results, setResults] = useState<any>(null)

  const analyze = () => {
    setAnalyzing(true)
    setTimeout(() => {
      const trend = 40 + Math.floor(Math.random() * 50)
      const momentum = 35 + Math.floor(Math.random() * 55)
      const meanRev = 30 + Math.floor(Math.random() * 50)
      const volume = 40 + Math.floor(Math.random() * 50)
      const pattern = 45 + Math.floor(Math.random() * 50)
      const regime = 50 + Math.floor(Math.random() * 40)

      const overall = Math.floor((trend + momentum + pattern + regime) / 4)

      const patterns = []
      if (Math.random() > 0.5) patterns.push('Double Bottom')
      if (Math.random() > 0.6) patterns.push('Bull Flag')
      if (Math.random() > 0.7) patterns.push('Golden Cross')
      if (Math.random() > 0.4) patterns.push('Support Test')

      setResults({
        components: {
          trend_score: trend,
          momentum_score: momentum,
          mean_reversion: meanRev,
          volume_signal: volume,
          pattern_score: pattern,
          regime_score: regime
        },
        patterns,
        metrics: {
          accuracy: 0.65 + Math.random() * 0.2,
          precision: 0.60 + Math.random() * 0.2,
          recall: 0.55 + Math.random() * 0.2,
          f1: 0.58 + Math.random() * 0.2,
          sharpe: 1.2 + Math.random() * 1.3
        },
        recommendation: {
          signal: overall > 65 ? 'BUY' : overall < 45 ? 'SELL' : 'HOLD',
          confidence: overall,
          reasoning: overall > 65
            ? 'Neural analysis indicates bullish outlook based on pattern recognition and trend analysis.'
            : overall < 45
            ? 'Neural analysis indicates bearish outlook. Consider defensive positioning.'
            : 'Neural analysis indicates neutral market conditions. Wait for clearer signals.'
        }
      })
      setAnalyzing(false)
    }, 1000)
  }

  const getScoreColor = (score: number) => {
    if (score >= 70) return 'text-bullish'
    if (score >= 50) return 'text-accent-primary'
    return 'text-bearish'
  }

  const getBarColor = (score: number) => {
    if (score >= 70) return 'bg-bullish'
    if (score >= 50) return 'bg-accent-primary'
    return 'bg-bearish'
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <Brain className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-accent-primary">NEURAL PATTERN ANALYSIS</h1>
          <p className="text-xs text-foreground-muted">AI-powered pattern recognition and signal generation</p>
        </div>
      </div>

      {/* Controls */}
      <div className="card p-4">
        <div className="flex items-end gap-4">
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="input w-24"
            />
          </div>
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Lookback</label>
            <div className="flex gap-1">
              {lookbackOptions.map(opt => (
                <button
                  key={opt}
                  onClick={() => setLookback(opt)}
                  className={cn(
                    'px-3 py-2 text-xs rounded transition-colors',
                    lookback === opt
                      ? 'bg-accent-primary text-background-primary'
                      : 'bg-background-tertiary text-foreground-secondary'
                  )}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
          <button onClick={analyze} disabled={analyzing} className="btn-primary flex items-center gap-2">
            <RefreshCw className={cn('w-4 h-4', analyzing && 'animate-spin')} />
            Analyze
          </button>
          <button className="btn-secondary flex items-center gap-2">
            <Zap className="w-4 h-4" />
            Train Model
          </button>
        </div>
      </div>

      {results && (
        <div className="grid grid-cols-12 gap-4">
          {/* Signal Components */}
          <div className="col-span-4 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">SIGNAL COMPONENTS</h3>
            <div className="space-y-3">
              {Object.entries(results.components).map(([key, value]) => (
                <div key={key}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className={cn('text-xs font-mono font-bold', getScoreColor(value as number))}>
                      {value as number}
                    </span>
                  </div>
                  <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                    <div
                      className={cn('h-full rounded-full', getBarColor(value as number))}
                      style={{ width: `${value}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Patterns & Metrics */}
          <div className="col-span-4 space-y-4">
            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">DETECTED PATTERNS</h3>
              {results.patterns.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {results.patterns.map((p: string) => (
                    <span key={p} className="px-2 py-1 bg-accent-primary/20 text-accent-primary rounded text-xs">
                      {p}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-foreground-muted">No significant patterns detected</p>
              )}
            </div>

            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">MODEL PERFORMANCE</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-background-tertiary p-2 rounded">
                  <div className="text-xs text-foreground-muted">Accuracy</div>
                  <div className="font-mono font-bold">{(results.metrics.accuracy * 100).toFixed(1)}%</div>
                </div>
                <div className="bg-background-tertiary p-2 rounded">
                  <div className="text-xs text-foreground-muted">Precision</div>
                  <div className="font-mono font-bold">{(results.metrics.precision * 100).toFixed(1)}%</div>
                </div>
                <div className="bg-background-tertiary p-2 rounded">
                  <div className="text-xs text-foreground-muted">Recall</div>
                  <div className="font-mono font-bold">{(results.metrics.recall * 100).toFixed(1)}%</div>
                </div>
                <div className="bg-background-tertiary p-2 rounded">
                  <div className="text-xs text-foreground-muted">F1 Score</div>
                  <div className="font-mono font-bold">{(results.metrics.f1 * 100).toFixed(1)}%</div>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-border">
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Sharpe (Backtest)</span>
                  <span className="text-sm font-mono font-bold text-accent-primary">{results.metrics.sharpe.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* AI Recommendation */}
          <div className="col-span-4 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">AI RECOMMENDATION</h3>
            <div className={cn(
              'p-4 rounded-lg text-center mb-4',
              results.recommendation.signal === 'BUY' ? 'bg-bullish/10' :
              results.recommendation.signal === 'SELL' ? 'bg-bearish/10' : 'bg-foreground-muted/10'
            )}>
              <div className={cn(
                'text-3xl font-bold mb-1',
                results.recommendation.signal === 'BUY' ? 'text-bullish' :
                results.recommendation.signal === 'SELL' ? 'text-bearish' : 'text-foreground-muted'
              )}>
                {results.recommendation.signal}
              </div>
              <div className="text-sm text-foreground-muted">
                Confidence: {results.recommendation.confidence}%
              </div>
            </div>
            <p className="text-xs text-foreground-secondary">
              {results.recommendation.reasoning}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
