import { Moon, Search, TrendingUp, TrendingDown } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

export function DarkPool() {
  const [ticker, setTicker] = useState('AAPL')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<any>(null)

  const search = () => {
    setLoading(true)
    setTimeout(() => {
      const darkVolume = Math.floor(5000000 + Math.random() * 20000000)
      const litVolume = Math.floor(30000000 + Math.random() * 70000000)

      setData({
        symbol: ticker,
        dark_pool_volume: darkVolume,
        lit_volume: litVolume,
        dark_pool_pct: (darkVolume / (darkVolume + litVolume) * 100).toFixed(1),
        signal: Math.random() > 0.5 ? 'ACCUMULATION' : 'DISTRIBUTION',
        large_blocks: Math.floor(10 + Math.random() * 40),
        avg_block_size: Math.floor(10000 + Math.random() * 50000),
        venues: [
          { name: 'UBSS', volume: Math.floor(1000000 + Math.random() * 3000000), trades: Math.floor(100 + Math.random() * 400) },
          { name: 'CODA', volume: Math.floor(800000 + Math.random() * 2500000), trades: Math.floor(80 + Math.random() * 350) },
          { name: 'JPMX', volume: Math.floor(700000 + Math.random() * 2000000), trades: Math.floor(70 + Math.random() * 300) },
          { name: 'MSPL', volume: Math.floor(600000 + Math.random() * 1800000), trades: Math.floor(60 + Math.random() * 280) },
          { name: 'GSES', volume: Math.floor(500000 + Math.random() * 1500000), trades: Math.floor(50 + Math.random() * 250) },
          { name: 'SGMT', volume: Math.floor(400000 + Math.random() * 1200000), trades: Math.floor(40 + Math.random() * 200) },
          { name: 'BTCH', volume: Math.floor(300000 + Math.random() * 1000000), trades: Math.floor(30 + Math.random() * 180) },
          { name: 'ARCA', volume: Math.floor(200000 + Math.random() * 800000), trades: Math.floor(20 + Math.random() * 150) },
        ]
      })
      setLoading(false)
    }, 500)
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
                  const avgPrice = 230 + Math.random() * 10
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
