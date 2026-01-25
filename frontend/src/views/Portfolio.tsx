import { Briefcase, Plus, Trash2, Save, Upload } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'
import { DonutChart } from '@/components/charts/DonutChart'

interface Holding {
  symbol: string
  shares: number
  costBasis: number
  currentPrice: number
}

export function Portfolio() {
  const [holdings, setHoldings] = useState<Holding[]>([
    { symbol: 'NVDA', shares: 100, costBasis: 135.00, currentPrice: 142.85 },
    { symbol: 'AAPL', shares: 80, costBasis: 225.00, currentPrice: 235.48 },
    { symbol: 'MSFT', shares: 40, costBasis: 420.00, currentPrice: 442.35 },
    { symbol: 'AMD', shares: 100, costBasis: 130.00, currentPrice: 125.30 },
  ])

  const [newTicker, setNewTicker] = useState('')
  const [newShares, setNewShares] = useState('')
  const [newCost, setNewCost] = useState('')

  const addPosition = () => {
    if (newTicker && newShares && newCost) {
      setHoldings([...holdings, {
        symbol: newTicker.toUpperCase(),
        shares: parseInt(newShares),
        costBasis: parseFloat(newCost),
        currentPrice: parseFloat(newCost) * (0.9 + Math.random() * 0.2)
      }])
      setNewTicker('')
      setNewShares('')
      setNewCost('')
    }
  }

  const removePosition = (symbol: string) => {
    setHoldings(holdings.filter(h => h.symbol !== symbol))
  }

  const totalValue = holdings.reduce((sum, h) => sum + h.shares * h.currentPrice, 0)
  const totalCost = holdings.reduce((sum, h) => sum + h.shares * h.costBasis, 0)
  const totalPnL = totalValue - totalCost
  const totalPnLPct = (totalPnL / totalCost) * 100

  const sectorData = [
    { name: 'Technology', value: 65, color: '#f0b90b' },
    { name: 'Semis', value: 35, color: '#00c853' },
  ]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Briefcase className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">PORTFOLIO MANAGEMENT</h1>
            <p className="text-xs text-foreground-muted">Track and manage your holdings</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary flex items-center gap-2">
            <Save className="w-4 h-4" />
            Save
          </button>
          <button className="btn-secondary flex items-center gap-2">
            <Upload className="w-4 h-4" />
            Load
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Add Position */}
        <div className="col-span-12 card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-3">ADD POSITION</h3>
          <div className="flex items-end gap-4">
            <div>
              <label className="block text-xs text-foreground-muted mb-1">Ticker</label>
              <input
                type="text"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
                className="input w-24"
                placeholder="AAPL"
              />
            </div>
            <div>
              <label className="block text-xs text-foreground-muted mb-1">Shares</label>
              <input
                type="number"
                value={newShares}
                onChange={(e) => setNewShares(e.target.value)}
                className="input w-24"
                placeholder="100"
              />
            </div>
            <div>
              <label className="block text-xs text-foreground-muted mb-1">Cost Basis</label>
              <input
                type="number"
                value={newCost}
                onChange={(e) => setNewCost(e.target.value)}
                className="input w-28"
                placeholder="150.00"
                step={0.01}
              />
            </div>
            <button onClick={addPosition} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" />
              Add
            </button>
          </div>
        </div>

        {/* Holdings Table */}
        <div className="col-span-8 card overflow-hidden">
          <div className="p-4 border-b border-border">
            <h3 className="text-sm font-bold">Holdings</h3>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Shares</th>
                <th>Cost</th>
                <th>Price</th>
                <th>Value</th>
                <th>P&L $</th>
                <th>P&L %</th>
                <th>Weight</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => {
                const value = h.shares * h.currentPrice
                const cost = h.shares * h.costBasis
                const pnl = value - cost
                const pnlPct = (pnl / cost) * 100
                const weight = (value / totalValue) * 100

                return (
                  <tr key={h.symbol}>
                    <td className="font-medium">{h.symbol}</td>
                    <td className="font-mono">{h.shares}</td>
                    <td className="font-mono">${h.costBasis.toFixed(2)}</td>
                    <td className="font-mono">${h.currentPrice.toFixed(2)}</td>
                    <td className="font-mono">${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                    <td className={cn('font-mono', pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                      {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                    </td>
                    <td className={cn('font-mono', pnlPct >= 0 ? 'text-bullish' : 'text-bearish')}>
                      {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                    </td>
                    <td className="font-mono">{weight.toFixed(1)}%</td>
                    <td>
                      <button
                        onClick={() => removePosition(h.symbol)}
                        className="p-1 text-foreground-muted hover:text-bearish transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Summary */}
        <div className="col-span-4 space-y-4">
          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">PORTFOLIO SUMMARY</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">Total Value</span>
                <span className="text-lg font-mono font-bold">
                  ${totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">Total Cost</span>
                <span className="text-sm font-mono">
                  ${totalCost.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
              </div>
              <div className="border-t border-border pt-3">
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Total P&L</span>
                  <span className={cn(
                    'text-lg font-mono font-bold',
                    totalPnL >= 0 ? 'text-bullish' : 'text-bearish'
                  )}>
                    {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-xs text-foreground-muted">Return</span>
                  <span className={cn(
                    'text-sm font-mono font-bold',
                    totalPnLPct >= 0 ? 'text-bullish' : 'text-bearish'
                  )}>
                    {totalPnLPct >= 0 ? '+' : ''}{totalPnLPct.toFixed(2)}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">SECTOR BREAKDOWN</h3>
            <div className="flex justify-center">
              <DonutChart data={sectorData} size={120} />
            </div>
          </div>

          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">RISK METRICS</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-foreground-muted">Sharpe Ratio</span>
                <span className="font-mono">1.85</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Sortino Ratio</span>
                <span className="font-mono">2.34</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Beta</span>
                <span className="font-mono">1.15</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Max Drawdown</span>
                <span className="font-mono text-bearish">-8.5%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">VaR 95%</span>
                <span className="font-mono">3.2%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
