import { Search, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

interface ScreenerResult {
  symbol: string
  price: number
  change_pct: number
  volume: number
  rsi: number
  trend: string
  signal: string
}

export function Screener() {
  const [tickers, setTickers] = useState('AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, AMD')
  const [results, setResults] = useState<ScreenerResult[]>([])
  const [loading, setLoading] = useState(false)

  const [error, setError] = useState<string | null>(null)

  const handleScan = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/screener/scan?tickers=${encodeURIComponent(tickers)}`)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to scan stocks')
      }

      // Transform API data to our format
      const scanResults: ScreenerResult[] = (data || []).map((item: any) => ({
        symbol: item.symbol,
        price: item.price || 0,
        change_pct: item.change_pct || item.change_percent || 0,
        volume: item.volume || 0,
        rsi: item.rsi || 50,
        trend: item.trend || (item.change_pct > 0 ? 'UP' : item.change_pct < 0 ? 'DOWN' : 'FLAT'),
        signal: item.signal || 'HOLD',
      }))

      setResults(scanResults)

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to scan stocks')
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const getTrendColor = (trend: string) => {
    switch (trend) {
      case 'UP': return 'text-bullish'
      case 'DOWN': return 'text-bearish'
      default: return 'text-foreground-muted'
    }
  }

  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'BUY': return 'bg-bullish/20 text-bullish'
      case 'SELL': return 'bg-bearish/20 text-bearish'
      case 'OVERBOUGHT': return 'bg-warning/20 text-warning'
      case 'OVERSOLD': return 'bg-accent-primary/20 text-accent-primary'
      default: return 'bg-foreground-muted/20 text-foreground-muted'
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <Search className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-accent-primary">STOCK SCREENER</h1>
        </div>
      </div>

      {/* Search bar */}
      <div className="card p-4">
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <label className="block text-xs text-foreground-muted mb-1">Tickers:</label>
            <input
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              className="input w-full"
              placeholder="AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, AMD"
            />
          </div>
          <button
            onClick={handleScan}
            disabled={loading}
            className="btn-primary flex items-center gap-2 mt-4"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
            SCAN
          </button>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {/* Results table */}
      <div className="card overflow-hidden">
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Price</th>
              <th>Change%</th>
              <th>Volume</th>
              <th>RSI</th>
              <th>Trend</th>
              <th>Signal</th>
            </tr>
          </thead>
          <tbody>
            {results.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-12 text-foreground-muted">
                  {loading ? 'Scanning stocks...' : 'Enter tickers and click SCAN to analyze'}
                </td>
              </tr>
            ) : (
              results.map((row) => (
                <tr key={row.symbol}>
                  <td className="font-medium text-foreground-primary">{row.symbol}</td>
                  <td className="font-mono">${row.price.toFixed(2)}</td>
                  <td className={cn('font-mono', row.change_pct >= 0 ? 'text-bullish' : 'text-bearish')}>
                    {row.change_pct >= 0 ? '+' : ''}{row.change_pct.toFixed(2)}%
                  </td>
                  <td className="font-mono">{(row.volume / 1000000).toFixed(1)}M</td>
                  <td className="font-mono">{row.rsi.toFixed(1)}</td>
                  <td className={cn('font-medium', getTrendColor(row.trend))}>{row.trend}</td>
                  <td>
                    <span className={cn('px-2 py-1 rounded text-xs font-medium', getSignalColor(row.signal))}>
                      {row.signal}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
