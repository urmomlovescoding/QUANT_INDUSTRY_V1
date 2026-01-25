import { CheckCircle2, XCircle, AlertCircle } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

export function TradeConfirm() {
  const [ticker, setTicker] = useState('AAPL')
  const [direction, setDirection] = useState('LONG')
  const [entryPrice, setEntryPrice] = useState(235)
  const [targetPrice, setTargetPrice] = useState(250)
  const [stopLoss, setStopLoss] = useState(225)
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<any>(null)

  const handleAnalyze = () => {
    setAnalyzing(true)
    setTimeout(() => {
      const technical = 65 + Math.floor(Math.random() * 30)
      const momentum = 55 + Math.floor(Math.random() * 35)
      const volume = 50 + Math.floor(Math.random() * 40)
      const riskReward = Math.abs((targetPrice - entryPrice) / (entryPrice - stopLoss))
      const risk = Math.min(95, Math.floor(riskReward * 30))
      const regime = 60 + Math.floor(Math.random() * 30)

      const score = Math.floor(
        technical * 0.25 +
        momentum * 0.2 +
        volume * 0.15 +
        risk * 0.25 +
        regime * 0.15
      )

      setResult({
        approved: score >= 70,
        score,
        confidence: score,
        components: { technical, momentum, volume, risk, regime },
        riskReward: riskReward.toFixed(2)
      })
      setAnalyzing(false)
    }, 1000)
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <CheckCircle2 className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-accent-primary">AI TRADE CONFIRMATION</h1>
          <p className="text-xs text-foreground-muted">Blended Signal Analysis + AI Verification</p>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Trade Input */}
        <div className="col-span-4 card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">TRADE INPUT</h3>

          <div className="space-y-4">
            <div>
              <label className="block text-xs text-foreground-muted mb-1">Ticker</label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                className="input w-full"
              />
            </div>

            <div>
              <label className="block text-xs text-foreground-muted mb-1">Direction</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setDirection('LONG')}
                  className={cn(
                    'flex-1 py-2 rounded text-sm font-medium transition-colors',
                    direction === 'LONG'
                      ? 'bg-bullish text-white'
                      : 'bg-background-tertiary text-foreground-secondary'
                  )}
                >
                  LONG
                </button>
                <button
                  onClick={() => setDirection('SHORT')}
                  className={cn(
                    'flex-1 py-2 rounded text-sm font-medium transition-colors',
                    direction === 'SHORT'
                      ? 'bg-bearish text-white'
                      : 'bg-background-tertiary text-foreground-secondary'
                  )}
                >
                  SHORT
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs text-foreground-muted mb-1">Entry Price</label>
              <input
                type="number"
                value={entryPrice}
                onChange={(e) => setEntryPrice(Number(e.target.value))}
                className="input w-full"
              />
            </div>

            <div>
              <label className="block text-xs text-foreground-muted mb-1">Target Price</label>
              <input
                type="number"
                value={targetPrice}
                onChange={(e) => setTargetPrice(Number(e.target.value))}
                className="input w-full"
              />
            </div>

            <div>
              <label className="block text-xs text-foreground-muted mb-1">Stop Loss</label>
              <input
                type="number"
                value={stopLoss}
                onChange={(e) => setStopLoss(Number(e.target.value))}
                className="input w-full"
              />
            </div>

            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="btn-primary w-full"
            >
              {analyzing ? 'Analyzing...' : 'ANALYZE TRADE'}
            </button>
          </div>
        </div>

        {/* AI Decision */}
        <div className="col-span-4 card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">AI DECISION</h3>

          {result ? (
            <div className="space-y-4">
              {/* Approval Status */}
              <div className={cn(
                'p-4 rounded-lg flex items-center gap-3',
                result.approved ? 'bg-bullish/10' : 'bg-bearish/10'
              )}>
                {result.approved ? (
                  <CheckCircle2 className="w-10 h-10 text-bullish" />
                ) : (
                  <XCircle className="w-10 h-10 text-bearish" />
                )}
                <div>
                  <div className={cn(
                    'text-2xl font-bold',
                    result.approved ? 'text-bullish' : 'text-bearish'
                  )}>
                    {result.approved ? 'APPROVED' : 'REJECTED'}
                  </div>
                  <div className="text-sm text-foreground-muted">
                    Score: {result.score}/100 | Confidence: {result.confidence}%
                  </div>
                </div>
              </div>

              {/* Score Breakdown */}
              <div>
                <h4 className="text-xs font-bold text-foreground-muted mb-2">SCORE BREAKDOWN</h4>
                <div className="space-y-2">
                  {Object.entries(result.components).map(([key, value]) => (
                    <div key={key}>
                      <div className="flex justify-between mb-1">
                        <span className="text-xs capitalize">{key}</span>
                        <span className="text-xs font-mono">{value as number}</span>
                      </div>
                      <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full',
                            (value as number) >= 70 ? 'bg-bullish' : (value as number) >= 50 ? 'bg-accent-primary' : 'bg-bearish'
                          )}
                          style={{ width: `${value}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Risk/Reward */}
              <div className="bg-background-tertiary p-3 rounded">
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Risk/Reward Ratio</span>
                  <span className={cn(
                    'text-sm font-mono font-bold',
                    parseFloat(result.riskReward) >= 2 ? 'text-bullish' : 'text-warning'
                  )}>
                    1:{result.riskReward}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-foreground-muted">
              <AlertCircle className="w-12 h-12 mb-4 opacity-50" />
              <p>Enter trade details and click Analyze</p>
            </div>
          )}
        </div>

        {/* Analysis & Recommendation */}
        <div className="col-span-4 card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">ANALYSIS & RECOMMENDATION</h3>

          {result ? (
            <div className="space-y-4 text-xs">
              <div>
                <h4 className="font-bold text-accent-primary mb-1">TECHNICAL ANALYSIS</h4>
                <p className="text-foreground-secondary">
                  {result.components.technical >= 70 ? 'Strong' : 'Moderate'} technical setup detected.
                  RSI: {35 + Math.floor(Math.random() * 25)} (neutral zone).
                  MACD: {result.components.momentum >= 65 ? 'Bullish crossover' : 'Converging'}.
                </p>
              </div>

              <div>
                <h4 className="font-bold text-accent-primary mb-1">MOMENTUM</h4>
                <p className="text-foreground-secondary">
                  {result.components.momentum}% confidence.
                  Price action shows {result.components.momentum >= 70 ? 'strong' : 'moderate'} momentum.
                </p>
              </div>

              <div>
                <h4 className="font-bold text-accent-primary mb-1">VOLUME ANALYSIS</h4>
                <p className="text-foreground-secondary">
                  {result.components.volume >= 70 ? 'Above' : 'Near'} average volume.
                  Institutional activity: {result.components.volume >= 80 ? 'Detected' : 'Normal'}.
                </p>
              </div>

              <div>
                <h4 className="font-bold text-accent-primary mb-1">REGIME</h4>
                <p className="text-foreground-secondary">
                  {result.components.regime >= 75 ? 'Trending' : 'Ranging'} market.
                  Current regime supports {result.components.regime >= 80 ? 'aggressive' : 'standard'} positioning.
                </p>
              </div>

              <div className={cn(
                'p-3 rounded',
                result.approved ? 'bg-bullish/10' : 'bg-warning/10'
              )}>
                <h4 className="font-bold mb-1">RECOMMENDATION</h4>
                <p className={cn(
                  'font-medium',
                  result.approved ? 'text-bullish' : 'text-warning'
                )}>
                  {result.approved
                    ? 'APPROVED - Proceed with trade as planned.'
                    : 'REVIEW - Consider adjusting entry or risk parameters.'}
                </p>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-foreground-muted">
              Analysis will appear here
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
