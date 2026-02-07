import { Moon, Search, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

export function DarkPool() {
  const [ticker, setTicker] = useState('AAPL')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<any>(null)

  const [error, setError] = useState<string | null>(null)

  const search = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/research/darkpool/${ticker}`)
      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail || 'Failed to fetch dark pool data')
      }

      // Check if data is unavailable
      if (result.status === 'unavailable') {
        setError(result.message || 'Dark pool data not available. Configure FINRA ATS API to enable.')
        setData(null)
        return
      }

      // Use API data or transform it
      const apiData = result.data || result
      const darkVolume = apiData.dark_pool_volume || 0
      const litVolume = apiData.lit_volume || 0
      const totalVolume = darkVolume + litVolume

      setData({
        symbol: ticker,
        dark_pool_volume: darkVolume,
        lit_volume: litVolume,
        dark_pool_pct: totalVolume > 0 ? (darkVolume / totalVolume * 100).toFixed(1) : '0',
        signal: apiData.signal || (darkVolume > litVolume * 0.4 ? 'ACCUMULATION' : 'DISTRIBUTION'),
        large_blocks: apiData.large_blocks || 0,
        avg_block_size: apiData.avg_block_size || 0,
        short_interest: apiData.short_interest || 0,
        short_ratio: apiData.short_ratio || 0,
        short_percent_float: apiData.short_percent_float || 0,
        venues: apiData.venues || [],
        _note: result._note || result.message
      })

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch dark pool data')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <Moon className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-accent-primary">DARK POOL ANALYZER</h1>
          <p className="text-xs text-foreground-muted">Off-exchange trading activity analysis</p>
        </div>
      </div>

      {/* Search */}
      <div className="card p-4">
        <div className="flex items-end gap-4">
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="input w-32"
            />
          </div>
          <button onClick={search} disabled={loading} className="btn-primary flex items-center gap-2">
            <Search className="w-4 h-4" />
            Analyze
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && !data && (
        <div className="card p-8 text-center text-foreground-muted">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
          <p className="text-sm">Analyzing dark pool activity...</p>
        </div>
      )}

      {data && (
        <div className="grid grid-cols-12 gap-4">
          {/* Summary */}
          <div className="col-span-4 space-y-4">
            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">VOLUME BREAKDOWN</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Dark Pool Volume</span>
                  <span className="text-sm font-mono font-bold text-accent-primary">
                    {(data.dark_pool_volume / 1000000).toFixed(1)}M
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Lit Volume</span>
                  <span className="text-sm font-mono">
                    {(data.lit_volume / 1000000).toFixed(1)}M
                  </span>
                </div>
                <div className="h-3 bg-background-tertiary rounded-full overflow-hidden flex">
                  <div
                    className="h-full bg-accent-primary"
                    style={{ width: `${data.dark_pool_pct}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs">
                  <span>Dark Pool: {data.dark_pool_pct}%</span>
                  <span>Lit: {(100 - parseFloat(data.dark_pool_pct)).toFixed(1)}%</span>
                </div>
              </div>
            </div>

            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">INSTITUTIONAL SIGNAL</h3>
              <div className={cn(
                'p-4 rounded-lg text-center',
                data.signal === 'ACCUMULATION' ? 'bg-bullish/10' : 'bg-bearish/10'
              )}>
                {data.signal === 'ACCUMULATION' ? (
                  <TrendingUp className="w-8 h-8 mx-auto mb-2 text-bullish" />
                ) : (
                  <TrendingDown className="w-8 h-8 mx-auto mb-2 text-bearish" />
                )}
                <div className={cn(
                  'text-xl font-bold',
                  data.signal === 'ACCUMULATION' ? 'text-bullish' : 'text-bearish'
                )}>
                  {data.signal}
                </div>
                <div className="text-xs text-foreground-muted mt-1">
                  {data.signal === 'ACCUMULATION'
                    ? 'Institutional buying detected'
                    : 'Institutional selling detected'}
                </div>
              </div>
            </div>

            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">BLOCK TRADES</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-background-tertiary p-3 rounded text-center">
                  <div className="text-xl font-bold">{data.large_blocks}</div>
                  <div className="text-xs text-foreground-muted">Large Blocks</div>
                </div>
                <div className="bg-background-tertiary p-3 rounded text-center">
                  <div className="text-xl font-bold">{(data.avg_block_size / 1000).toFixed(0)}K</div>
                  <div className="text-xs text-foreground-muted">Avg Size</div>
                </div>
              </div>
            </div>

            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">SHORT INTEREST</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Short Interest</span>
                  <span className="text-sm font-mono font-bold">
                    {data.short_interest > 1e6
                      ? `${(data.short_interest / 1e6).toFixed(1)}M`
                      : data.short_interest > 1e3
                        ? `${(data.short_interest / 1e3).toFixed(0)}K`
                        : data.short_interest}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Short Ratio</span>
                  <span className="text-sm font-mono font-bold">{data.short_ratio}x</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">% of Float Short</span>
                  <span className={cn(
                    'text-sm font-mono font-bold',
                    data.short_percent_float > 10 ? 'text-bearish' :
                    data.short_percent_float > 5 ? 'text-warning' : 'text-foreground-primary'
                  )}>
                    {data.short_percent_float}%
                  </span>
                </div>
              </div>
            </div>

            {data._note && (
              <div className="text-xs text-foreground-muted italic px-1">
                {data._note}
              </div>
            )}
          </div>

          {/* Venues */}
          <div className="col-span-8 card overflow-hidden">
            <div className="p-4 border-b border-border">
              <h3 className="text-sm font-bold">Activity by Dark Pool Venue - {data.symbol}</h3>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Venue</th>
                  <th>Volume</th>
                  <th>Share</th>
                  <th>Trades</th>
                  <th>Avg Price</th>
                </tr>
              </thead>
              <tbody>
                {data.venues.map((v: any, i: number) => {
                  const share = (v.volume / data.dark_pool_volume * 100).toFixed(1)
                  const avgPrice = v.avg_price || 0
                  return (
                    <tr key={i}>
                      <td className="font-medium">{v.name}</td>
                      <td className="font-mono">{(v.volume / 1000000).toFixed(2)}M</td>
                      <td>
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-2 bg-background-tertiary rounded-full overflow-hidden">
                            <div
                              className="h-full bg-accent-primary"
                              style={{ width: `${parseFloat(share) * 3}%` }}
                            />
                          </div>
                          <span className="text-xs font-mono">{share}%</span>
                        </div>
                      </td>
                      <td className="font-mono">{v.trades}</td>
                      <td className="font-mono">${avgPrice.toFixed(2)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
