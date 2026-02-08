/**
 * Neural Pattern Analysis
 * AI-powered pattern recognition and signal generation using real API data
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Brain, RefreshCw, Zap, Loader2 } from 'lucide-react'
import { cn } from '@/utils/cn'

const lookbackOptions = ['3M', '6M', '1Y', '2Y']

interface NeuralAnalysisResult {
  symbol: string
  overall_score: number
  technical_score: number
  sentiment_score: number
  regime_alignment: boolean
  recommendation: string
  key_factors: string[]
  confidence?: number
}

// Fetch neural analysis from backend
async function fetchNeuralAnalysis(symbol: string): Promise<NeuralAnalysisResult | null> {
  const response = await fetch(`/api/neural/analyze/${symbol}`)
  if (!response.ok) {
    // Fall back to analysis endpoint
    const fallback = await fetch(`/api/neural/analysis/${symbol}`)
    if (!fallback.ok) return null
    return fallback.json()
  }
  return response.json()
}

// Fetch brain analysis for additional signals
async function fetchBrainAnalysis(symbol: string) {
  const response = await fetch(`/api/brain-v6/analyze/${symbol}`)
  if (!response.ok) return null
  return response.json()
}

// Fetch market regime
async function fetchRegime() {
  const response = await fetch('/api/neural/regime')
  if (!response.ok) return null
  return response.json()
}

export function NeuralAnalysis() {
  const [ticker, setTicker] = useState('SPY')
  const [lookback, setLookback] = useState('6M')
  const [searchTicker, setSearchTicker] = useState('SPY')

  // Fetch neural analysis
  const { data: analysis, isLoading: analysisLoading, refetch } = useQuery({
    queryKey: ['neural-analysis', searchTicker],
    queryFn: () => fetchNeuralAnalysis(searchTicker),
    enabled: !!searchTicker,
    staleTime: 30000,
  })

  // Fetch brain analysis for additional context
  const { data: brainAnalysis } = useQuery({
    queryKey: ['brain-analysis', searchTicker],
    queryFn: () => fetchBrainAnalysis(searchTicker),
    enabled: !!searchTicker,
    staleTime: 30000,
  })

  // Fetch regime for context
  const { data: regime } = useQuery({
    queryKey: ['neural-regime'],
    queryFn: fetchRegime,
    staleTime: 60000,
  })

  const isLoading = analysisLoading

  const handleAnalyze = () => {
    setSearchTicker(ticker)
    refetch()
  }

  // Derive component scores from analysis
  const getComponents = () => {
    if (!analysis) {
      return {
        trend_score: 50,
        momentum_score: 50,
        mean_reversion: 50,
        volume_signal: 50,
        pattern_score: 50,
        regime_score: 50
      }
    }

    const overall = analysis.overall_score || 50
    const technical = analysis.technical_score || overall
    const sentiment = analysis.sentiment_score || 50

    return {
      trend_score: Math.min(100, Math.max(0, technical)),
      momentum_score: Math.min(100, Math.max(0, overall * 0.9 + sentiment * 0.1)),
      mean_reversion: Math.min(100, Math.max(0, 100 - technical)),
      volume_signal: Math.min(100, Math.max(0, technical * 0.8 + 10)),
      pattern_score: Math.min(100, Math.max(0, overall)),
      regime_score: Math.min(100, Math.max(0, analysis.regime_alignment ? 75 : 45))
    }
  }

  // Get detected patterns from key factors
  const getPatterns = () => {
    if (!analysis || !analysis.key_factors) return []
    return analysis.key_factors.slice(0, 4)
  }

  // Get model performance metrics -- only display real values from the API
  const getMetrics = () => {
    return {
      accuracy: null as number | null,
      precision: null as number | null,
      recall: null as number | null,
      f1: null as number | null,
      sharpe: null as number | null,
    }
  }

  // Get recommendation
  const getRecommendation = () => {
    if (!analysis) {
      return {
        signal: 'HOLD',
        confidence: 50,
        reasoning: 'Click Analyze to run neural pattern analysis on this symbol.'
      }
    }

    const score = analysis.overall_score || 50
    const signal = score >= 65 ? 'BUY' : score <= 35 ? 'SELL' : 'HOLD'
    const confidence = Math.min(95, Math.max(30, score))

    let reasoning = analysis.recommendation || ''
    if (!reasoning) {
      if (signal === 'BUY') {
        reasoning = `Neural analysis indicates bullish outlook for ${searchTicker} based on pattern recognition and trend analysis. Technical score: ${analysis.technical_score?.toFixed(0)}%, Sentiment: ${analysis.sentiment_score?.toFixed(0)}%.`
      } else if (signal === 'SELL') {
        reasoning = `Neural analysis indicates bearish outlook for ${searchTicker}. Consider defensive positioning. Regime alignment: ${analysis.regime_alignment ? 'Yes' : 'No'}.`
      } else {
        reasoning = `Neural analysis indicates neutral conditions for ${searchTicker}. Wait for clearer signals before major positioning changes.`
      }
    }

    return { signal, confidence, reasoning }
  }

  const components = getComponents()
  const patterns = getPatterns()
  const metrics = getMetrics()
  const recommendation = getRecommendation()

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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Brain className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">NEURAL PATTERN ANALYSIS</h1>
            <p className="text-xs text-foreground-muted">AI-powered pattern recognition and signal generation</p>
          </div>
        </div>
        {regime && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-background-tertiary">
            <span className="text-xs text-foreground-muted">Market Regime:</span>
            <span className={cn(
              'text-xs font-bold',
              regime.current_regime?.includes('bull') ? 'text-bullish' :
              regime.current_regime?.includes('bear') ? 'text-bearish' : 'text-warning'
            )}>
              {regime.current_regime || 'Unknown'}
            </span>
          </div>
        )}
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
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
              className="input w-24"
              placeholder="SPY"
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
          <button
            onClick={handleAnalyze}
            disabled={isLoading || !ticker}
            className="btn-primary flex items-center gap-2"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            {isLoading ? 'Analyzing...' : 'Analyze'}
          </button>
          <button className="btn-secondary flex items-center gap-2" disabled>
            <Zap className="w-4 h-4" />
            Train Model
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <Loader2 className="w-8 h-8 animate-spin text-accent-primary mx-auto mb-2" />
            <p className="text-sm text-foreground-muted">Running neural analysis on {searchTicker}...</p>
          </div>
        </div>
      ) : analysis || searchTicker ? (
        <div className="grid grid-cols-12 gap-4">
          {/* Signal Components */}
          <div className="col-span-4 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">SIGNAL COMPONENTS</h3>
            <div className="space-y-3">
              {Object.entries(components).map(([key, value]) => (
                <div key={key}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className={cn('text-xs font-mono font-bold', getScoreColor(value as number))}>
                      {(value as number).toFixed(0)}
                    </span>
                  </div>
                  <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                    <div
                      className={cn('h-full rounded-full transition-all', getBarColor(value as number))}
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
              <h3 className="text-xs font-bold text-foreground-muted mb-3">KEY FACTORS</h3>
              {patterns.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {patterns.map((p: string, i: number) => (
                    <span key={i} className="px-2 py-1 bg-accent-primary/20 text-accent-primary rounded text-xs">
                      {p}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-foreground-muted">Analyzing patterns for {searchTicker}...</p>
              )}
            </div>

            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">MODEL PERFORMANCE</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-background-tertiary p-2 rounded">
                  <div className="text-xs text-foreground-muted">Accuracy</div>
                  <div className="font-mono font-bold">{metrics.accuracy != null ? `${(metrics.accuracy * 100).toFixed(1)}%` : '--'}</div>
                </div>
                <div className="bg-background-tertiary p-2 rounded">
                  <div className="text-xs text-foreground-muted">Precision</div>
                  <div className="font-mono font-bold">{metrics.precision != null ? `${(metrics.precision * 100).toFixed(1)}%` : '--'}</div>
                </div>
                <div className="bg-background-tertiary p-2 rounded">
                  <div className="text-xs text-foreground-muted">Recall</div>
                  <div className="font-mono font-bold">{metrics.recall != null ? `${(metrics.recall * 100).toFixed(1)}%` : '--'}</div>
                </div>
                <div className="bg-background-tertiary p-2 rounded">
                  <div className="text-xs text-foreground-muted">F1 Score</div>
                  <div className="font-mono font-bold">{metrics.f1 != null ? `${(metrics.f1 * 100).toFixed(1)}%` : '--'}</div>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-border">
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Sharpe (Backtest)</span>
                  <span className="text-sm font-mono font-bold text-accent-primary">{metrics.sharpe != null ? metrics.sharpe.toFixed(2) : '--'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* AI Recommendation */}
          <div className="col-span-4 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">AI RECOMMENDATION</h3>
            <div className={cn(
              'p-4 rounded-lg text-center mb-4',
              recommendation.signal === 'BUY' ? 'bg-bullish/10' :
              recommendation.signal === 'SELL' ? 'bg-bearish/10' : 'bg-foreground-muted/10'
            )}>
              <div className={cn(
                'text-3xl font-bold mb-1',
                recommendation.signal === 'BUY' ? 'text-bullish' :
                recommendation.signal === 'SELL' ? 'text-bearish' : 'text-foreground-muted'
              )}>
                {recommendation.signal}
              </div>
              <div className="text-sm text-foreground-muted">
                Confidence: {recommendation.confidence.toFixed(0)}%
              </div>
            </div>
            <p className="text-xs text-foreground-secondary">
              {recommendation.reasoning}
            </p>
            {analysis && (
              <div className="mt-3 pt-3 border-t border-border text-xs text-foreground-muted">
                <div>Overall Score: {analysis.overall_score?.toFixed(1)}%</div>
                {analysis.technical_score && <div>Technical: {analysis.technical_score.toFixed(1)}%</div>}
                {analysis.sentiment_score && <div>Sentiment: {analysis.sentiment_score.toFixed(1)}%</div>}
                <div>Regime Aligned: {analysis.regime_alignment ? 'Yes' : 'No'}</div>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
