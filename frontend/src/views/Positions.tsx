import { useState, useEffect, useMemo } from 'react'
import {
  Briefcase,
  X,
  Plus,
  TrendingUp,
  TrendingDown,
  Clock,
  Filter,
  Download,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/utils/cn'

interface Position {
  id: string
  symbol: string
  side: 'long' | 'short'
  qty: number
  entryPrice: number
  currentPrice: number
  unrealizedPnl: number
  unrealizedPnlPercent: number
  stopLoss: number | null
  takeProfit: number | null
}

interface ClosedTrade {
  id: string
  symbol: string
  side: 'long' | 'short'
  qty: number
  entryPrice: number
  exitPrice: number
  realizedPnl: number
  realizedPnlPercent: number
  entryTime: string
  exitTime: string
  duration: string
  strategy: string
}

const positions: Position[] = [
  { id: '1', symbol: 'AAPL', side: 'long', qty: 100, entryPrice: 182.50, currentPrice: 185.92, unrealizedPnl: 342.00, unrealizedPnlPercent: 1.87, stopLoss: 178.00, takeProfit: 195.00 },
  { id: '2', symbol: 'NVDA', side: 'long', qty: 25, entryPrice: 865.00, currentPrice: 878.45, unrealizedPnl: 336.25, unrealizedPnlPercent: 1.56, stopLoss: 840.00, takeProfit: 920.00 },
  { id: '3', symbol: 'TSLA', side: 'short', qty: 50, entryPrice: 255.00, currentPrice: 248.32, unrealizedPnl: 334.00, unrealizedPnlPercent: 2.62, stopLoss: 265.00, takeProfit: 230.00 },
  { id: '4', symbol: 'META', side: 'long', qty: 40, entryPrice: 498.00, currentPrice: 505.23, unrealizedPnl: 289.20, unrealizedPnlPercent: 1.45, stopLoss: 485.00, takeProfit: 530.00 },
  { id: '5', symbol: 'MSFT', side: 'long', qty: 30, entryPrice: 420.00, currentPrice: 415.67, unrealizedPnl: -129.90, unrealizedPnlPercent: -1.03, stopLoss: 405.00, takeProfit: 445.00 },
]

// Generate mock closed trades
const generateClosedTrades = (): ClosedTrade[] => {
  const symbols = ['AAPL', 'NVDA', 'TSLA', 'META', 'MSFT', 'GOOGL', 'AMZN', 'AMD', 'SPY', 'QQQ']
  const strategies = ['Momentum', 'Mean Reversion', 'Trend Following', 'ML Ensemble', 'RSI Divergence']
  const trades: ClosedTrade[] = []

  for (let i = 0; i < 20; i++) {
    const symbol = symbols[Math.floor(Math.random() * symbols.length)]
    const side = Math.random() > 0.5 ? 'long' : 'short'
    const qty = Math.floor(Math.random() * 100) + 10
    const entryPrice = 100 + Math.random() * 400
    const pnlPercent = (Math.random() - 0.4) * 10
    const exitPrice = entryPrice * (1 + (side === 'long' ? pnlPercent : -pnlPercent) / 100)
    const pnl = (exitPrice - entryPrice) * qty * (side === 'long' ? 1 : -1)
    const hoursAgo = Math.floor(Math.random() * 168) + 1
    const durationMinutes = Math.floor(Math.random() * 480) + 5

    trades.push({
      id: `trade_${i}`,
      symbol,
      side,
      qty,
      entryPrice,
      exitPrice,
      realizedPnl: pnl,
      realizedPnlPercent: pnlPercent,
      entryTime: new Date(Date.now() - hoursAgo * 3600000 - durationMinutes * 60000).toISOString(),
      exitTime: new Date(Date.now() - hoursAgo * 3600000).toISOString(),
      duration: durationMinutes < 60 ? `${durationMinutes}m` : `${Math.floor(durationMinutes / 60)}h ${durationMinutes % 60}m`,
      strategy: strategies[Math.floor(Math.random() * strategies.length)],
    })
  }

  return trades.sort((a, b) => new Date(b.exitTime).getTime() - new Date(a.exitTime).getTime())
}

export function Positions() {
  const [closedTrades, setClosedTrades] = useState<ClosedTrade[]>(() => generateClosedTrades())
  const [activeTab, setActiveTab] = useState<'open' | 'closed'>('open')
  const [tradeFilter, setTradeFilter] = useState<'all' | 'winners' | 'losers'>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const tradesPerPage = 10

  const totalPnl = positions.reduce((sum, p) => sum + p.unrealizedPnl, 0)
  const totalValue = positions.reduce((sum, p) => sum + (p.qty * p.currentPrice), 0)

  // Fetch closed trades from API
  useEffect(() => {
    const fetchTrades = async () => {
      try {
        const response = await fetch('/api/trades/closed')
        if (response.ok) {
          const data = await response.json()
          if (Array.isArray(data) && data.length > 0) {
            setClosedTrades(data)
          }
        }
      } catch (error) {
        console.error('Failed to fetch closed trades:', error)
      }
    }
    fetchTrades()
  }, [])

  const filteredTrades = useMemo(() => {
    return closedTrades.filter(trade => {
      if (tradeFilter === 'winners' && trade.realizedPnl < 0) return false
      if (tradeFilter === 'losers' && trade.realizedPnl >= 0) return false
      return true
    })
  }, [closedTrades, tradeFilter])

  const paginatedTrades = useMemo(() => {
    const start = (currentPage - 1) * tradesPerPage
    return filteredTrades.slice(start, start + tradesPerPage)
  }, [filteredTrades, currentPage])

  const totalPages = Math.ceil(filteredTrades.length / tradesPerPage)

  const tradeStats = useMemo(() => {
    const winners = closedTrades.filter(t => t.realizedPnl >= 0)
    const losers = closedTrades.filter(t => t.realizedPnl < 0)
    const totalRealizedPnl = closedTrades.reduce((sum, t) => sum + t.realizedPnl, 0)
    const avgWin = winners.length > 0 ? winners.reduce((sum, t) => sum + t.realizedPnl, 0) / winners.length : 0
    const avgLoss = losers.length > 0 ? losers.reduce((sum, t) => sum + t.realizedPnl, 0) / losers.length : 0

    return {
      total: closedTrades.length,
      winners: winners.length,
      losers: losers.length,
      winRate: closedTrades.length > 0 ? (winners.length / closedTrades.length) * 100 : 0,
      totalRealizedPnl,
      avgWin,
      avgLoss,
    }
  }, [closedTrades])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Briefcase className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground-primary">Position Management</h1>
            <p className="text-sm text-foreground-muted">
              {positions.length} positions • ${totalValue.toLocaleString()} value •{' '}
              <span className={totalPnl >= 0 ? 'text-bullish' : 'text-bearish'}>
                {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)} P&L
              </span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Add Position
          </button>
          <button className="btn-danger flex items-center gap-2">
            <X className="w-4 h-4" />
            Close All
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1 bg-surface-secondary rounded-lg p-1">
          <button
            onClick={() => setActiveTab('open')}
            className={cn(
              'px-4 py-1.5 text-sm font-medium rounded-md transition-colors',
              activeTab === 'open' ? 'bg-accent-primary text-background-primary' : 'text-foreground-muted hover:text-foreground-primary'
            )}
          >
            Open Positions ({positions.length})
          </button>
          <button
            onClick={() => setActiveTab('closed')}
            className={cn(
              'px-4 py-1.5 text-sm font-medium rounded-md transition-colors',
              activeTab === 'closed' ? 'bg-accent-primary text-background-primary' : 'text-foreground-muted hover:text-foreground-primary'
            )}
          >
            Closed Trades ({closedTrades.length})
          </button>
        </div>
      </div>

      {activeTab === 'open' ? (
        /* Open Positions */
        <div className="card">
          <div className="p-4 border-b border-border">
            <h2 className="text-sm font-medium text-foreground-primary">Open Positions</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Quantity</th>
                  <th>Entry Price</th>
                  <th>Current Price</th>
                  <th>Unrealized P&L</th>
                  <th>Stop Loss</th>
                  <th>Take Profit</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((position) => (
                  <PositionRow key={position.id} position={position} />
                ))}
              </tbody>
            </table>
          </div>
          <div className="p-4 border-t border-border flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div>
                <span className="text-xs text-foreground-muted">Total Unrealized:</span>
                <span className={cn(
                  'ml-2 font-bold',
                  totalPnl >= 0 ? 'text-bullish' : 'text-bearish'
                )}>
                  {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
                </span>
              </div>
              <div>
                <span className="text-xs text-foreground-muted">Positions:</span>
                <span className="ml-2 font-bold text-foreground-primary">{positions.length}</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Closed Trades */
        <>
          {/* Trade Stats */}
          <div className="grid grid-cols-6 gap-3">
            <div className="card p-3">
              <div className="text-xs text-foreground-muted mb-1">Total Trades</div>
              <div className="text-lg font-bold text-foreground-primary">{tradeStats.total}</div>
            </div>
            <div className="card p-3">
              <div className="text-xs text-foreground-muted mb-1">Win Rate</div>
              <div className={cn('text-lg font-bold', tradeStats.winRate >= 50 ? 'text-bullish' : 'text-bearish')}>
                {tradeStats.winRate.toFixed(1)}%
              </div>
            </div>
            <div className="card p-3">
              <div className="text-xs text-foreground-muted mb-1">Winners</div>
              <div className="text-lg font-bold text-bullish">{tradeStats.winners}</div>
            </div>
            <div className="card p-3">
              <div className="text-xs text-foreground-muted mb-1">Losers</div>
              <div className="text-lg font-bold text-bearish">{tradeStats.losers}</div>
            </div>
            <div className="card p-3">
              <div className="text-xs text-foreground-muted mb-1">Avg Win</div>
              <div className="text-lg font-bold text-bullish">${tradeStats.avgWin.toFixed(0)}</div>
            </div>
            <div className="card p-3">
              <div className="text-xs text-foreground-muted mb-1">Total P&L</div>
              <div className={cn('text-lg font-bold', tradeStats.totalRealizedPnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                {tradeStats.totalRealizedPnl >= 0 ? '+' : ''}${tradeStats.totalRealizedPnl.toFixed(0)}
              </div>
            </div>
          </div>

          {/* Filters */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1 bg-surface-secondary rounded-lg p-1">
              {(['all', 'winners', 'losers'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => { setTradeFilter(f); setCurrentPage(1); }}
                  className={cn(
                    'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                    tradeFilter === f
                      ? f === 'winners' ? 'bg-bullish/20 text-bullish' :
                        f === 'losers' ? 'bg-bearish/20 text-bearish' :
                        'bg-accent-primary text-background-primary'
                      : 'text-foreground-muted hover:text-foreground-primary'
                  )}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
            <button className="btn-secondary flex items-center gap-2 text-xs">
              <Download className="w-3 h-3" />
              Export CSV
            </button>
          </div>

          {/* Trades Table */}
          <div className="card">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <h2 className="text-sm font-medium text-foreground-primary">Closed Trades</h2>
              <span className="text-xs text-foreground-muted">{filteredTrades.length} trades</span>
            </div>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Qty</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>Realized P&L</th>
                    <th>Duration</th>
                    <th>Strategy</th>
                    <th>Exit Time</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedTrades.map((trade) => (
                    <TradeRow key={trade.id} trade={trade} />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="p-4 border-t border-border flex items-center justify-between">
              <div className="text-xs text-foreground-muted">
                Showing {(currentPage - 1) * tradesPerPage + 1} - {Math.min(currentPage * tradesPerPage, filteredTrades.length)} of {filteredTrades.length}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="p-1 rounded hover:bg-surface-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-sm text-foreground-primary">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="p-1 rounded hover:bg-surface-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function PositionRow({ position }: { position: Position }) {
  const isProfit = position.unrealizedPnl >= 0

  return (
    <tr>
      <td>
        <span className="font-medium text-foreground-primary">{position.symbol}</span>
      </td>
      <td>
        <span className={cn(
          'badge inline-flex items-center gap-1',
          position.side === 'long' ? 'badge-bullish' : 'badge-bearish'
        )}>
          {position.side === 'long' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {position.side.toUpperCase()}
        </span>
      </td>
      <td className="font-mono">{position.qty}</td>
      <td className="font-mono">${position.entryPrice.toFixed(2)}</td>
      <td className="font-mono">${position.currentPrice.toFixed(2)}</td>
      <td>
        <div className={cn('font-mono font-medium', isProfit ? 'text-bullish' : 'text-bearish')}>
          {isProfit ? '+' : ''}${position.unrealizedPnl.toFixed(2)}
          <span className="text-xs ml-1">({isProfit ? '+' : ''}{position.unrealizedPnlPercent.toFixed(2)}%)</span>
        </div>
      </td>
      <td className="font-mono text-bearish">
        {position.stopLoss ? `$${position.stopLoss.toFixed(2)}` : '-'}
      </td>
      <td className="font-mono text-bullish">
        {position.takeProfit ? `$${position.takeProfit.toFixed(2)}` : '-'}
      </td>
      <td>
        <button className="btn-danger text-xs py-1 px-2">Close</button>
      </td>
    </tr>
  )
}

function TradeRow({ trade }: { trade: ClosedTrade }) {
  const isProfit = trade.realizedPnl >= 0

  return (
    <tr>
      <td>
        <span className="font-medium text-foreground-primary">{trade.symbol}</span>
      </td>
      <td>
        <span className={cn(
          'badge inline-flex items-center gap-1 text-xs',
          trade.side === 'long' ? 'badge-bullish' : 'badge-bearish'
        )}>
          {trade.side === 'long' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {trade.side.toUpperCase()}
        </span>
      </td>
      <td className="font-mono text-sm">{trade.qty}</td>
      <td className="font-mono text-sm">${trade.entryPrice.toFixed(2)}</td>
      <td className="font-mono text-sm">${trade.exitPrice.toFixed(2)}</td>
      <td>
        <div className={cn('font-mono font-medium', isProfit ? 'text-bullish' : 'text-bearish')}>
          {isProfit ? '+' : ''}${trade.realizedPnl.toFixed(2)}
          <span className="text-xs ml-1">({isProfit ? '+' : ''}{trade.realizedPnlPercent.toFixed(1)}%)</span>
        </div>
      </td>
      <td className="text-sm text-foreground-muted">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {trade.duration}
        </span>
      </td>
      <td>
        <span className="text-xs px-2 py-0.5 rounded-full bg-surface-secondary text-foreground-primary">
          {trade.strategy}
        </span>
      </td>
      <td className="text-xs text-foreground-muted">
        {new Date(trade.exitTime).toLocaleString()}
      </td>
    </tr>
  )
}
