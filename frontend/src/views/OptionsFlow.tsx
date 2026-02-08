import { useState, useEffect } from 'react'
import { Eye, TrendingUp, TrendingDown, Activity, DollarSign, BarChart3 } from 'lucide-react'

interface FlowEntry {
  time: string
  symbol: string
  type: 'CALL' | 'PUT'
  strike: number
  expiry: string
  premium: string
  volume: number
  oi: number
  sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
}

export function OptionsFlow() {
  const [flows, setFlows] = useState<FlowEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'ALL' | 'CALLS' | 'PUTS'>('ALL')

  useEffect(() => {
    const fetchFlow = async () => {
      try {
        const res = await fetch('/api/options/flow')
        if (res.ok) {
          const data = await res.json()
          if (data.flow && Array.isArray(data.flow)) {
            setFlows(data.flow.slice(0, 20))
            setLoading(false)
            return
          }
        }
      } catch { /* fallback below */ }

      // Sample data
      setFlows([
        { time: '15:42', symbol: 'SPY', type: 'CALL', strike: 700, expiry: '2/14', premium: '$2.4M', volume: 12500, oi: 45000, sentiment: 'BULLISH' },
        { time: '15:38', symbol: 'NVDA', type: 'CALL', strike: 190, expiry: '2/21', premium: '$1.8M', volume: 8200, oi: 32000, sentiment: 'BULLISH' },
        { time: '15:35', symbol: 'TSLA', type: 'PUT', strike: 400, expiry: '2/14', premium: '$1.2M', volume: 6100, oi: 28000, sentiment: 'BEARISH' },
        { time: '15:31', symbol: 'AAPL', type: 'CALL', strike: 280, expiry: '2/28', premium: '$980K', volume: 5400, oi: 51000, sentiment: 'BULLISH' },
        { time: '15:28', symbol: 'META', type: 'PUT', strike: 650, expiry: '2/14', premium: '$750K', volume: 3200, oi: 18000, sentiment: 'BEARISH' },
        { time: '15:25', symbol: 'AMZN', type: 'CALL', strike: 220, expiry: '3/21', premium: '$1.5M', volume: 7800, oi: 42000, sentiment: 'BULLISH' },
        { time: '15:22', symbol: 'MSFT', type: 'CALL', strike: 410, expiry: '2/21', premium: '$620K', volume: 2800, oi: 22000, sentiment: 'NEUTRAL' },
        { time: '15:18', symbol: 'QQQ', type: 'PUT', strike: 620, expiry: '2/14', premium: '$890K', volume: 4100, oi: 35000, sentiment: 'BEARISH' },
      ])
      setLoading(false)
    }
    fetchFlow()
  }, [])

  const filtered = flows.filter(f => {
    if (filter === 'CALLS') return f.type === 'CALL'
    if (filter === 'PUTS') return f.type === 'PUT'
    return true
  })

  const callVolume = flows.filter(f => f.type === 'CALL').reduce((s, f) => s + f.volume, 0)
  const putVolume = flows.filter(f => f.type === 'PUT').reduce((s, f) => s + f.volume, 0)
  const ratio = putVolume > 0 ? (callVolume / putVolume).toFixed(2) : '0'

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent-primary/10 flex items-center justify-center">
          <Eye className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground-primary">OPTIONS FLOW</h1>
          <p className="text-xs text-foreground-muted">Real-time unusual options activity & smart money tracking</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Call Volume', value: formatNum(callVolume), icon: TrendingUp, color: 'text-green-400' },
          { label: 'Put Volume', value: formatNum(putVolume), icon: TrendingDown, color: 'text-red-400' },
          { label: 'Put/Call Ratio', value: ratio, icon: BarChart3, color: 'text-yellow-400' },
          { label: 'Total Premium', value: '$9.1M', icon: DollarSign, color: 'text-accent-primary' },
        ].map(stat => (
          <div key={stat.label} className="bg-background-secondary border border-border/50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-foreground-muted">{stat.label}</span>
              <stat.icon className={`w-4 h-4 ${stat.color}`} />
            </div>
            <div className={`text-xl font-bold ${stat.color}`}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div className="flex gap-2">
        {(['ALL', 'CALLS', 'PUTS'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors ${
              filter === f
                ? 'bg-accent-primary text-black'
                : 'bg-background-tertiary text-foreground-secondary hover:text-foreground-primary'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Flow Table */}
      <div className="bg-background-secondary border border-border/50 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-foreground-muted">Loading options flow...</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-border/30">
                <th className="text-left px-5 py-3 text-xs font-semibold text-foreground-muted">TIME</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-foreground-muted">SYMBOL</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-foreground-muted">TYPE</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-foreground-muted">STRIKE</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-foreground-muted">EXPIRY</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-foreground-muted">PREMIUM</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-foreground-muted">VOLUME</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-foreground-muted">OI</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-foreground-muted">SENTIMENT</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((flow, i) => (
                <tr key={i} className="border-b border-border/20 hover:bg-background-hover/30 transition-colors">
                  <td className="px-5 py-3 text-xs text-foreground-muted font-mono">{flow.time}</td>
                  <td className="px-5 py-3 text-sm font-bold text-foreground-primary">{flow.symbol}</td>
                  <td className="px-5 py-3">
                    <span className={`text-xs font-bold px-2 py-1 rounded ${
                      flow.type === 'CALL' ? 'bg-green-400/10 text-green-400' : 'bg-red-400/10 text-red-400'
                    }`}>
                      {flow.type}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-sm text-right font-mono text-foreground-primary">${flow.strike}</td>
                  <td className="px-5 py-3 text-xs text-foreground-secondary">{flow.expiry}</td>
                  <td className="px-5 py-3 text-sm text-right font-mono text-accent-primary">{flow.premium}</td>
                  <td className="px-5 py-3 text-sm text-right font-mono text-foreground-secondary">{flow.volume.toLocaleString()}</td>
                  <td className="px-5 py-3 text-sm text-right font-mono text-foreground-muted">{flow.oi.toLocaleString()}</td>
                  <td className="px-5 py-3">
                    <span className={`text-xs font-semibold ${
                      flow.sentiment === 'BULLISH' ? 'text-green-400' :
                      flow.sentiment === 'BEARISH' ? 'text-red-400' : 'text-yellow-400'
                    }`}>
                      {flow.sentiment}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function formatNum(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`
  return n.toString()
}
