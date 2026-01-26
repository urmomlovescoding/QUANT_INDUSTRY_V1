import { useState, useEffect } from 'react'
import {
  GitBranch,
  RefreshCw,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react'
import { cn } from '@/utils/cn'

interface CorrelationData {
  symbols: string[]
  matrix: number[][]
  pairs: {
    asset1: string
    asset2: string
    correlation: number
    strength: string
    direction: string
  }[]
  source: string
  timestamp: string
}

export function Correlation() {
  const [data, setData] = useState<CorrelationData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [symbols, setSymbols] = useState('SPY,QQQ,AAPL,MSFT,NVDA,TSLA,GOOGL,AMZN')

  const fetchCorrelation = async () => {
    if (!symbols.trim()) {
      setError('Please enter at least 2 symbols')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/correlation/matrix?symbols=${encodeURIComponent(symbols)}`)
      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail || 'Failed to fetch correlation data')
      }

      if (result.status === 'unavailable') {
        setError(result.message || 'Correlation data not available')
        setData(null)
        return
      }

      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch correlation')
      setData(null)
    } finally {
      setIsLoading(false)
    }
  }

  // Don't auto-fetch on mount - wait for user to click Analyze
  // useEffect(() => { fetchCorrelation() }, [])

  const getCorrelationColor = (corr: number) => {
    if (corr >= 0.7) return 'bg-bullish/80 text-white'
    if (corr >= 0.4) return 'bg-bullish/40 text-white'
    if (corr >= 0) return 'bg-bullish/20 text-foreground-primary'
    if (corr >= -0.4) return 'bg-bearish/20 text-foreground-primary'
    if (corr >= -0.7) return 'bg-bearish/40 text-white'
    return 'bg-bearish/80 text-white'
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <GitBranch className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">CORRELATION</h1>
            <p className="text-xs text-foreground-muted">Asset correlation analysis</p>
          </div>
        </div>
        <button
          onClick={fetchCorrelation}
          disabled={isLoading}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Symbol Input */}
      <div className="card p-4">
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="block text-xs font-medium text-foreground-muted mb-1">Symbols (comma-separated)</label>
            <input
              type="text"
              value={symbols}
              onChange={(e) => setSymbols(e.target.value.toUpperCase())}
              className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-foreground-primary focus:outline-none focus:border-accent-primary"
              placeholder="SPY,QQQ,AAPL..."
            />
          </div>
          <button
            onClick={fetchCorrelation}
            disabled={isLoading}
            className="btn-primary self-end"
          >
            Analyze
          </button>
        </div>
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
      ) : !data ? (
        <div className="card p-8 text-center text-foreground-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">Enter symbols and click Analyze</p>
          <p className="text-sm mt-2">Example: SPY,QQQ,AAPL,MSFT</p>
        </div>
      ) : (
        <>
          {/* Correlation Matrix */}
          <div className="card p-4 overflow-x-auto">
            <h3 className="text-sm font-medium text-foreground-primary mb-4">Correlation Matrix</h3>
            <table className="w-full min-w-[600px]">
              <thead>
                <tr>
                  <th className="p-2 text-xs text-foreground-muted"></th>
                  {data.symbols.map(sym => (
                    <th key={sym} className="p-2 text-xs font-bold text-accent-primary">{sym}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.matrix.map((row, i) => (
                  <tr key={i}>
                    <td className="p-2 text-xs font-bold text-accent-primary">{data.symbols[i]}</td>
                    {row.map((corr, j) => (
                      <td
                        key={j}
                        className={cn(
                          'p-2 text-center text-xs font-mono',
                          i === j ? 'bg-surface-secondary text-foreground-muted' : getCorrelationColor(corr)
                        )}
                      >
                        {corr.toFixed(2)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Correlation Legend */}
          <div className="card p-4">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Correlation Scale</h3>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-1">
                <div className="w-6 h-6 rounded bg-bullish/80" />
                <span className="text-xs text-foreground-muted">Strong +</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-6 h-6 rounded bg-bullish/40" />
                <span className="text-xs text-foreground-muted">Moderate +</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-6 h-6 rounded bg-bullish/20" />
                <span className="text-xs text-foreground-muted">Weak +</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-6 h-6 rounded bg-bearish/20" />
                <span className="text-xs text-foreground-muted">Weak -</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-6 h-6 rounded bg-bearish/40" />
                <span className="text-xs text-foreground-muted">Moderate -</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-6 h-6 rounded bg-bearish/80" />
                <span className="text-xs text-foreground-muted">Strong -</span>
              </div>
            </div>
          </div>

          {/* Top Pairs */}
          <div className="card p-4">
            <h3 className="text-sm font-medium text-foreground-primary mb-4">Top Correlated Pairs</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {data.pairs.slice(0, 8).map((pair, i) => (
                <div key={i} className="p-3 bg-surface-secondary rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-accent-primary">
                      {pair.asset1} / {pair.asset2}
                    </span>
                    {pair.direction === 'positive' ? (
                      <TrendingUp className="w-4 h-4 text-bullish" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-bearish" />
                    )}
                  </div>
                  <div className={cn(
                    'text-lg font-bold font-mono',
                    pair.direction === 'positive' ? 'text-bullish' : 'text-bearish'
                  )}>
                    {pair.correlation > 0 ? '+' : ''}{pair.correlation.toFixed(4)}
                  </div>
                  <div className="text-xs text-foreground-muted capitalize">{pair.strength}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Data Source */}
          <div className="text-xs text-foreground-muted text-center">
            Data source: {data.source} | Updated: {new Date(data.timestamp).toLocaleTimeString()}
          </div>
        </>
      )}
    </div>
  )
}
