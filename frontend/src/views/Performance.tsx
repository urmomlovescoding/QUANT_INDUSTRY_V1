import { useState, useEffect } from 'react'
import { BarChart3, RefreshCw, AlertCircle } from 'lucide-react'
import { cn } from '@/utils/cn'
import { DonutChart } from '@/components/charts/DonutChart'

interface TradeStats {
  totalTrades: number
  winners: number
  losers: number
  winRate: number | null
  totalPnl: number
  avgWin: number | null
  avgLoss: number | null
  profitFactor: number | null
  largestWin: number | null
  largestLoss: number | null
  source: string
  is_real: boolean
  status?: string
}

interface ClosedTrade {
  id: string
  symbol: string
  side: string
  entry_price: number
  exit_price: number
  quantity: number
  pnl: number
  pnl_pct: number
  entry_time: string
  exit_time: string
}

export function Performance() {
  const [stats, setStats] = useState<TradeStats | null>(null)
  const [trades, setTrades] = useState<ClosedTrade[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [period, setPeriod] = useState('30d')

  const fetchData = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Fetch trade stats and closed trades in parallel
      const [statsRes, tradesRes] = await Promise.all([
        fetch(`/api/trades/stats?range=${period}`),
        fetch('/api/trades/closed')
      ])

      const statsData = await statsRes.json()
      const tradesData = await tradesRes.json()

      if (statsData.status === 'unavailable') {
        setStats(null)
      } else {
        setStats(statsData)
      }

      if (Array.isArray(tradesData)) {
        setTrades(tradesData)
      } else if (tradesData.trades) {
        setTrades(tradesData.trades)
      } else {
        setTrades([])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch performance data')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [period])

  const winRate = stats?.winRate ?? 0
  const lossRate = 100 - winRate

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <BarChart3 className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground-primary">Performance Center</h1>
            <p className="text-sm text-foreground-muted">Trading Performance Analytics</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="text-sm bg-background-tertiary text-foreground-secondary px-3 py-1.5 rounded border border-border"
          >
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
            <option value="all">All Time</option>
          </select>
          <button
            onClick={fetchData}
            disabled={isLoading}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            Refresh
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
      ) : !stats ? (
        <div className="card p-8 text-center text-foreground-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">No Trading Data Available</p>
          <p className="text-sm mt-2">Performance stats will appear once you execute trades</p>
        </div>
      ) : (
        <>
          {/* Stats grid */}
          <div className="grid grid-cols-4 gap-4">
            {/* All Trades */}
            <StatsCard title="ALL TRADES">
              <StatRow label="Net P&L" value={`$${stats.totalPnl.toFixed(2)}`} positive={stats.totalPnl >= 0} negative={stats.totalPnl < 0} />
              <StatRow label="# of Trades" value={stats.totalTrades.toString()} />
              <StatRow label="Win Rate" value={stats.winRate !== null ? `${stats.winRate.toFixed(1)}%` : 'N/A'} />
              <StatRow label="Profit Factor" value={stats.profitFactor !== null ? stats.profitFactor.toFixed(2) : 'N/A'} />
              <StatRow label="Data Source" value={stats.source} />
            </StatsCard>

            {/* Profit Trades */}
            <StatsCard title="WINNING TRADES" highlight="bullish">
              <StatRow label="Winning Trades" value={stats.winners.toString()} />
              <StatRow label="Avg. Win" value={stats.avgWin !== null ? `$${stats.avgWin.toFixed(2)}` : 'N/A'} positive />
              <StatRow label="Largest Win" value={stats.largestWin !== null ? `$${stats.largestWin.toFixed(2)}` : 'N/A'} positive />
            </StatsCard>

            {/* Losing Trades */}
            <StatsCard title="LOSING TRADES" highlight="bearish">
              <StatRow label="Losing Trades" value={stats.losers.toString()} />
              <StatRow label="Avg. Loss" value={stats.avgLoss !== null ? `$${stats.avgLoss.toFixed(2)}` : 'N/A'} negative />
              <StatRow label="Largest Loss" value={stats.largestLoss !== null ? `$${stats.largestLoss.toFixed(2)}` : 'N/A'} negative />
            </StatsCard>

            {/* Win vs Loss Chart */}
            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">
                WIN RATE
              </h3>
              {stats.totalTrades > 0 ? (
                <>
                  <div className="flex items-center justify-center h-40">
                    <DonutChart
                      data={[
                        { name: 'Winning', value: winRate, color: '#00c853' },
                        { name: 'Losing', value: lossRate, color: '#ff1744' },
                      ]}
                      centerLabel={`${winRate.toFixed(1)}%`}
                      centerSubLabel="Win Rate"
                      size={140}
                    />
                  </div>
                  <div className="flex justify-around mt-4 text-xs">
                    <div className="text-center">
                      <div className="flex items-center gap-1 justify-center">
                        <span className="w-2 h-2 rounded-full bg-bullish" />
                        <span className="text-foreground-muted">WINNING</span>
                      </div>
                      <span className="font-bold text-bullish">{winRate.toFixed(1)}%</span>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center gap-1 justify-center">
                        <span className="w-2 h-2 rounded-full bg-bearish" />
                        <span className="text-foreground-muted">LOSING</span>
                      </div>
                      <span className="font-bold text-bearish">{lossRate.toFixed(1)}%</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-40 text-foreground-muted">
                  No trades yet
                </div>
              )}
            </div>
          </div>

          {/* Trades table */}
          <div className="card">
            <div className="p-4 border-b border-border">
              <h2 className="text-sm font-medium text-foreground-primary">RECENT TRADES</h2>
            </div>
            {trades.length === 0 ? (
              <div className="p-8 text-center text-foreground-muted">
                <p>No closed trades to display</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table text-xs">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Side</th>
                      <th>Qty</th>
                      <th>Entry</th>
                      <th>Exit</th>
                      <th>P&L</th>
                      <th>P&L %</th>
                      <th>Exit Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.slice(0, 20).map((trade) => (
                      <tr key={trade.id}>
                        <td className="font-medium">{trade.symbol}</td>
                        <td className={trade.side === 'LONG' ? 'text-bullish' : 'text-bearish'}>{trade.side}</td>
                        <td>{trade.quantity}</td>
                        <td className="font-mono">${trade.entry_price.toFixed(2)}</td>
                        <td className="font-mono">${trade.exit_price.toFixed(2)}</td>
                        <td className={cn('font-mono font-medium', trade.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                          {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                        </td>
                        <td className={cn('font-mono', trade.pnl_pct >= 0 ? 'text-bullish' : 'text-bearish')}>
                          {trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct.toFixed(2)}%
                        </td>
                        <td className="text-foreground-muted">{new Date(trade.exit_time).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

interface StatsCardProps {
  title: string
  children: React.ReactNode
  highlight?: 'bullish' | 'bearish'
}

function StatsCard({ title, children, highlight }: StatsCardProps) {
  return (
    <div className={cn(
      'card p-4',
      highlight === 'bullish' && 'border-bullish/30',
      highlight === 'bearish' && 'border-bearish/30'
    )}>
      <h3 className={cn(
        'text-xs font-bold uppercase tracking-wider mb-4',
        highlight === 'bullish' ? 'text-bullish' : highlight === 'bearish' ? 'text-bearish' : 'text-foreground-muted'
      )}>
        {title}
      </h3>
      <div className="space-y-2">
        {children}
      </div>
    </div>
  )
}

interface StatRowProps {
  label: string
  value: string
  positive?: boolean
  negative?: boolean
}

function StatRow({ label, value, positive, negative }: StatRowProps) {
  return (
    <div className="flex justify-between items-center text-xs">
      <span className="text-foreground-muted">{label}</span>
      <span className={cn(
        'font-mono font-medium',
        positive && 'text-bullish',
        negative && 'text-bearish',
        !positive && !negative && 'text-foreground-primary'
      )}>
        {value}
      </span>
    </div>
  )
}
