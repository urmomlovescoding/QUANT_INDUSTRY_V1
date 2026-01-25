import { Building2, Search, TrendingUp, TrendingDown } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

export function Holdings13F() {
  const [ticker, setTicker] = useState('AAPL')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<any>(null)

  const search = () => {
    setLoading(true)
    setTimeout(() => {
      setData({
        symbol: ticker,
        institutional_ownership: 78.5,
        holders: [
          { name: 'Vanguard Group', shares: 185000000, value: 43500000000, change: 5200000, pct: 4.2 },
          { name: 'BlackRock', shares: 152000000, value: 35800000000, change: -2100000, pct: 3.5 },
          { name: 'State Street', shares: 68000000, value: 16000000000, change: 1800000, pct: 1.6 },
          { name: 'Fidelity', shares: 52000000, value: 12200000000, change: 3400000, pct: 1.2 },
          { name: 'Berkshire Hathaway', shares: 25000000, value: 5900000000, change: 0, pct: 0.6 },
          { name: 'Geode Capital', shares: 42000000, value: 9900000000, change: 1100000, pct: 1.0 },
          { name: 'Morgan Stanley', shares: 38000000, value: 8900000000, change: -800000, pct: 0.9 },
          { name: 'Northern Trust', shares: 31000000, value: 7300000000, change: 600000, pct: 0.7 },
        ],
        quarterly_change: {
          new: 145,
          increased: 312,
          decreased: 189,
          closed: 67
        }
      })
      setLoading(false)
    }, 500)
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <Building2 className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-accent-primary">13F HOLDINGS</h1>
          <p className="text-xs text-foreground-muted">Institutional investor holdings tracker</p>
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
            Search
          </button>
        </div>
      </div>

      {data && (
        <div className="grid grid-cols-12 gap-4">
          {/* Summary */}
          <div className="col-span-4 space-y-4">
            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">OWNERSHIP SUMMARY</h3>
              <div className="text-center">
                <div className="text-4xl font-bold text-accent-primary mb-1">
                  {data.institutional_ownership}%
                </div>
                <div className="text-xs text-foreground-muted">Institutional Ownership</div>
              </div>
            </div>

            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">QUARTERLY CHANGES</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-bullish/10 p-3 rounded text-center">
                  <div className="text-lg font-bold text-bullish">{data.quarterly_change.new}</div>
                  <div className="text-xs text-foreground-muted">New Positions</div>
                </div>
                <div className="bg-bullish/10 p-3 rounded text-center">
                  <div className="text-lg font-bold text-bullish">{data.quarterly_change.increased}</div>
                  <div className="text-xs text-foreground-muted">Increased</div>
                </div>
                <div className="bg-bearish/10 p-3 rounded text-center">
                  <div className="text-lg font-bold text-bearish">{data.quarterly_change.decreased}</div>
                  <div className="text-xs text-foreground-muted">Decreased</div>
                </div>
                <div className="bg-bearish/10 p-3 rounded text-center">
                  <div className="text-lg font-bold text-bearish">{data.quarterly_change.closed}</div>
                  <div className="text-xs text-foreground-muted">Closed</div>
                </div>
              </div>
            </div>
          </div>

          {/* Holders Table */}
          <div className="col-span-8 card overflow-hidden">
            <div className="p-4 border-b border-border">
              <h3 className="text-sm font-bold">Top Institutional Holders - {data.symbol}</h3>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Institution</th>
                  <th>Shares</th>
                  <th>Value</th>
                  <th>Change</th>
                  <th>% Portfolio</th>
                </tr>
              </thead>
              <tbody>
                {data.holders.map((h: any, i: number) => (
                  <tr key={i}>
                    <td className="font-medium">{h.name}</td>
                    <td className="font-mono">{(h.shares / 1000000).toFixed(1)}M</td>
                    <td className="font-mono">${(h.value / 1000000000).toFixed(1)}B</td>
                    <td>
                      <span className={cn(
                        'flex items-center gap-1 font-mono',
                        h.change > 0 ? 'text-bullish' : h.change < 0 ? 'text-bearish' : 'text-foreground-muted'
                      )}>
                        {h.change > 0 && <TrendingUp className="w-3 h-3" />}
                        {h.change < 0 && <TrendingDown className="w-3 h-3" />}
                        {h.change !== 0 ? `${(Math.abs(h.change) / 1000000).toFixed(1)}M` : '-'}
                      </span>
                    </td>
                    <td className="font-mono">{h.pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
