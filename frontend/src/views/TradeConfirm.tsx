/**
 * AI Trade Confirmation
 * Uses real backend AI analysis to confirm trade setups
 */
import { useState } from 'react'
import { CheckCircle2, XCircle, AlertCircle, Loader2 } from 'lucide-react'
import { cn } from '@/utils/cn'
import { tradingApi } from '@/api/client'

export function TradeConfirm() {
  const [ticker, setTicker] = useState('AAPL')
  const [direction, setDirection] = useState('LONG')
  const [entryPrice, setEntryPrice] = useState(235)
  const [targetPrice, setTargetPrice] = useState(250)
  const [stopLoss, setStopLoss] = useState(225)
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const handleAnalyze = async () => {
    setAnalyzing(true)
    setError(null)

    try {
      const response = await tradingApi.confirmTrade({
        ticker,
        direction,
        entry_price: entryPrice,
        target: targetPrice,
        stop_loss: stopLoss
      })

      if (response.ok && response.data) {
        const data = response.data
        // Map API response to component format
        setResult({
          approved: data.approved,
          score: data.score,
          confidence: data.confidence,
          components: data.components || {},
          riskReward: ((targetPrice - entryPrice) / Math.abs(entryPrice - stopLoss)).toFixed(2),
          recommendation: data.recommendation,
          analysis: data.analysis
        })
      } else {
        setError(response.error?.message || 'Failed to analyze trade')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze trade')
    } finally {
      setAnalyzing(false)
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 75) return 'text-bullish'
    if (score >= 50) return 'text-accent-primary'
    return 'text-bearish'
  }

  const getBarColor = (score: number) => {
    if (score >= 75) return 'bg-bullish'
    if (score >= 50) return 'bg-accent-primary'
    return 'bg-bearish'
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

      {error && (
        <div className="p-3 bg-bearish/10 border border-bearish/30 rounded-lg text-bearish text-sm">
          {error}
        </div>
      )}

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
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {analyzing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                'ANALYZE TRADE'
              )}
            </button>
          </div>
        </div>

        {/* AI Decision */}
        <div className="col-span-4 card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">AI DECISION</h3>

          {analyzing ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <Loader2 className="w-8 h-8 animate-spin text-accent-primary mx-auto mb-2" />
                <p className="text-sm text-foreground-muted">Analyzing trade setup...</p>
              </div>
            </div>
          ) : result ? (
            <div className="space-y-4">
              {/* Approval Status */}
              <div className={cn(
                'p-4 rounded-lg flex items-center gap-3',
                result.approved ? 'bg-bullish/10' : 'bg-bearish/10'
              )}>
                {result.approved ? (
                  <CheckCircle2 className="w-8 h-8 text-bullish" />
                ) : (
                  <XCircle className="w-8 h-8 text-bearish" />
                )}
                <div>
                  <div className={cn(
                    'text-xl font-bold',
                    result.approved ? 'text-bullish' : 'text-bearish'
                  )}>
                    {result.approved ? 'APPROVED' : 'REJECTED'}
                  </div>
                  <div className="text-xs text-foreground-muted">
                    AI Score: {result.score}/100
                  </div>
                </div>
              </div>

              {/* Confidence Meter */}
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-foreground-muted">Confidence</span>
                  <span className={cn('font-mono font-bold', getScoreColor(result.confidence))}>
                    {result.confidence}%
                  </span>
                </div>
                <div className="h-3 bg-background-tertiary rounded-full overflow-hidden">
                  <div
                    className={cn('h-full rounded-full transition-all', getBarColor(result.confidence))}
                    style={{ width: `${result.confidence}%` }}
                  />
                </div>
              </div>

              {/* Risk/Reward */}
              <div className="p-3 bg-background-tertiary rounded-lg">
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Risk/Reward</span>
                  <span className={cn(
                    'text-sm font-mono font-bold',
                    parseFloat(result.riskReward) >= 2 ? 'text-bullish' :
                    parseFloat(result.riskReward) >= 1 ? 'text-warning' : 'text-bearish'
                  )}>
                    1:{result.riskReward}
                  </span>
                </div>
              </div>

              {/* Analysis Summary */}
              {result.analysis && (
                <div className="p-3 bg-background-tertiary rounded-lg">
                  <div className="text-xs text-foreground-muted mb-1">Analysis</div>
                  <p className="text-xs text-foreground-secondary">{result.analysis}</p>
                </div>
              )}

              {/* Recommendation */}
              {result.recommendation && (
                <div className={cn(
                  'p-3 rounded-lg border',
                  result.approved
                    ? 'bg-bullish/5 border-bullish/30'
                    : 'bg-bearish/5 border-bearish/30'
                )}>
                  <div className="text-xs text-foreground-muted mb-1">Recommendation</div>
                  <p className="text-sm">{result.recommendation}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-center">
              <div>
                <AlertCircle className="w-12 h-12 text-foreground-muted mx-auto mb-3" />
                <p className="text-sm text-foreground-muted">
                  Enter trade details and click<br />Analyze to get AI confirmation
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Signal Components */}
        <div className="col-span-4 card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">SIGNAL COMPONENTS</h3>

          {result && result.components ? (
            <div className="space-y-3">
              {Object.entries(result.components).map(([key, value]) => (
                <div key={key}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className={cn('text-xs font-mono font-bold', getScoreColor(value as number))}>
                      {(value as number).toFixed ? (value as number).toFixed(0) : String(value)}
                    </span>
                  </div>
                  <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                    <div
                      className={cn('h-full rounded-full transition-all', getBarColor(value as number))}
                      style={{ width: `${Math.min(100, value as number)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-48 text-center">
              <p className="text-sm text-foreground-muted">
                Signal components will appear<br />after analysis
              </p>
            </div>
          )}

          {/* Trade Summary */}
          {result && (
            <div className="mt-6 pt-4 border-t border-border">
              <h4 className="text-xs font-bold text-foreground-muted mb-3">TRADE SUMMARY</h4>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Symbol</span>
                  <span className="font-mono font-bold">{ticker}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Direction</span>
                  <span className={cn(
                    'font-bold',
                    direction === 'LONG' ? 'text-bullish' : 'text-bearish'
                  )}>{direction}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Entry</span>
                  <span className="font-mono">${entryPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Target</span>
                  <span className="font-mono text-bullish">${targetPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Stop Loss</span>
                  <span className="font-mono text-bearish">${stopLoss.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Potential Gain</span>
                  <span className="font-mono text-bullish">
                    +{((targetPrice - entryPrice) / entryPrice * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Risk</span>
                  <span className="font-mono text-bearish">
                    -{(Math.abs(entryPrice - stopLoss) / entryPrice * 100).toFixed(2)}%
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
