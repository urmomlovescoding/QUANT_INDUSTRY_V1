import { useState } from 'react'
import { Activity, TrendingUp, TrendingDown, DollarSign, BarChart3, PieChart } from 'lucide-react'

interface AttributionEntry {
  strategy: string
  pnl: number
  trades: number
  winRate: number
  contribution: number
}

export function PnlAttribution() {
  const [period, setPeriod] = useState<'1D' | '1W' | '1M' | 'YTD'>('1M')

  const attributions: AttributionEntry[] = [
    { strategy: 'Trend Following', pnl: 4250, trades: 18, winRate: 72.2, contribution: 38.5 },
    { strategy: 'Mean Reversion', pnl: 2180, trades: 25, winRate: 64.0, contribution: 19.7 },
    { strategy: 'Momentum', pnl: 1890, trades: 12, winRate: 66.7, contribution: 17.1 },
    { strategy: 'Breakout', pnl: 1420, trades: 8, winRate: 62.5, contribution: 12.9 },
    { strategy: 'Scalping', pnl: 780, trades: 45, winRate: 55.6, contribution: 7.1 },
    { strategy: 'Options Flow', pnl: 520, trades: 5, winRate: 80.0, contribution: 4.7 },
  ]

  const totalPnl = attributions.reduce((s, a) => s + a.pnl, 0)
  const totalTrades = attributions.reduce((s, a) => s + a.trades, 0)
  const avgWinRate = attributions.reduce((s, a) => s + a.winRate, 0) / attributions.length

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent-primary/10 flex items-center justify-center">
            <PieChart className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground-primary">P&L ATTRIBUTION</h1>
            <p className="text-xs text-foreground-muted">Strategy-level performance breakdown & contribution analysis</p>
          </div>
        </div>
        <div className="flex gap-1 bg-background-tertiary rounded-lg p-1">
          {(['1D', '1W', '1M', 'YTD'] as const).map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                period === p ? 'bg-accent-primary text-black' : 'text-foreground-muted hover:text-foreground-primary'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total P&L', value: `$${totalPnl.toLocaleString()}`, icon: DollarSign, color: 'text-green-400' },
          { label: 'Total Trades', value: totalTrades.toString(), icon: Activity, color: 'text-accent-primary' },
          { label: 'Avg Win Rate', value: `${avgWinRate.toFixed(1)}%`, icon: TrendingUp, color: 'text-yellow-400' },
          { label: 'Best Strategy', value: 'Trend Following', icon: BarChart3, color: 'text-blue-400' },
        ].map(stat => (
          <div key={stat.label} className="bg-background-secondary border border-border/50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-foreground-muted">{stat.label}</span>
              <stat.icon className={`w-4 h-4 ${stat.color}`} />
            </div>
            <div className={`text-lg font-bold ${stat.color}`}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Attribution Table */}
      <div className="bg-background-secondary border border-border/50 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-border/50 flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-accent-primary" />
          <span className="text-sm font-semibold text-foreground-primary">Strategy Attribution</span>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-border/30">
              <th className="text-left px-5 py-3 text-xs font-semibold text-foreground-muted">STRATEGY</th>
              <th className="text-right px-5 py-3 text-xs font-semibold text-foreground-muted">P&L</th>
              <th className="text-right px-5 py-3 text-xs font-semibold text-foreground-muted">TRADES</th>
              <th className="text-right px-5 py-3 text-xs font-semibold text-foreground-muted">WIN RATE</th>
              <th className="text-right px-5 py-3 text-xs font-semibold text-foreground-muted">CONTRIBUTION</th>
              <th className="px-5 py-3 text-xs font-semibold text-foreground-muted w-48">BREAKDOWN</th>
            </tr>
          </thead>
          <tbody>
            {attributions.map(a => (
              <tr key={a.strategy} className="border-b border-border/20 hover:bg-background-hover/30 transition-colors">
                <td className="px-5 py-3 text-sm font-semibold text-foreground-primary">{a.strategy}</td>
                <td className={`px-5 py-3 text-sm text-right font-mono ${a.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  <span className="inline-flex items-center gap-1">
                    {a.pnl >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    ${Math.abs(a.pnl).toLocaleString()}
                  </span>
                </td>
                <td className="px-5 py-3 text-sm text-right text-foreground-secondary">{a.trades}</td>
                <td className="px-5 py-3 text-sm text-right font-mono text-foreground-primary">{a.winRate.toFixed(1)}%</td>
                <td className="px-5 py-3 text-sm text-right font-mono text-accent-primary">{a.contribution.toFixed(1)}%</td>
                <td className="px-5 py-3">
                  <div className="h-2 bg-background-hover rounded-full overflow-hidden">
                    <div
                      className="h-full bg-accent-primary rounded-full transition-all"
                      style={{ width: `${a.contribution}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
