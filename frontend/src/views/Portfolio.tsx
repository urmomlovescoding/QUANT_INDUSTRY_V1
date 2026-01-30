import { Briefcase, Plus, Trash2, Save, Upload, RefreshCw } from 'lucide-react'
import { useState, useEffect, useMemo } from 'react'
import { cn } from '@/utils/cn'
import { DonutChart } from '@/components/charts/DonutChart'
import { apiV2 } from '@/api/v2'

interface Holding {
  symbol: string
  shares: number
  costBasis: number
  currentPrice: number
}

export function Portfolio() {
  // Start with empty portfolio - user enters their own data
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [newTicker, setNewTicker] = useState('')
  const [newShares, setNewShares] = useState('')
  const [newCost, setNewCost] = useState('')

  // Fetch current price when adding a position
  const addPosition = async () => {
    if (!newTicker || !newShares || !newCost) return

    setLoading(true)
    setError(null)

    try {
      // Fetch current price from API using v2 client
      const { data, error: apiError, ok } = await apiV2.market.getQuote(newTicker.toUpperCase())

      if (!ok || apiError) {
        throw new Error(apiError?.message || 'Failed to fetch price')
      }

      const currentPrice = data?.price || parseFloat(newCost)

      setHoldings([...holdings, {
        symbol: newTicker.toUpperCase(),
        shares: parseInt(newShares),
        costBasis: parseFloat(newCost),
        currentPrice
      }])
      setNewTicker('')
      setNewShares('')
      setNewCost('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add position')
    } finally {
      setLoading(false)
    }
  }

  // Refresh all prices
  const refreshPrices = async () => {
    if (holdings.length === 0) return

    setLoading(true)
    setError(null)

    try {
      const updatedHoldings = await Promise.all(
        holdings.map(async (h) => {
          try {
            const { data, ok } = await apiV2.market.getQuote(h.symbol)
            return { ...h, currentPrice: ok && data?.price ? data.price : h.currentPrice }
          } catch {
            return h
          }
        })
      )
      setHoldings(updatedHoldings)
    } catch (err) {
      setError('Failed to refresh prices')
    } finally {
      setLoading(false)
    }
  }

  const removePosition = (symbol: string) => {
    setHoldings(holdings.filter(h => h.symbol !== symbol))
  }

  // Calculate totals only if we have holdings
  const totalValue = holdings.reduce((sum, h) => sum + h.shares * h.currentPrice, 0)
  const totalCost = holdings.reduce((sum, h) => sum + h.shares * h.costBasis, 0)
  const totalPnL = totalValue - totalCost
  const totalPnLPct = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0

  // Calculate sector breakdown dynamically from holdings
  const sectorData = useMemo(() => {
    if (holdings.length === 0) return []

    // Group by symbol for now (could integrate sector data from API)
    return holdings.map(h => ({
      name: h.symbol,
      value: totalValue > 0 ? (h.shares * h.currentPrice / totalValue) * 100 : 0,
      color: ['#f0b90b', '#00c853', '#ff5252', '#2196f3', '#9c27b0', '#ff9800'][holdings.indexOf(h) % 6]
    }))
  }, [holdings, totalValue])

  // Save portfolio to localStorage
  const savePortfolio = () => {
    localStorage.setItem('portfolio_holdings', JSON.stringify(holdings))
    alert('Portfolio saved!')
  }

  // Load portfolio from localStorage
  const loadPortfolio = () => {
    const saved = localStorage.getItem('portfolio_holdings')
    if (saved) {
      try {
        setHoldings(JSON.parse(saved))
      } catch {
        setError('Failed to load saved portfolio')
      }
    }
  }

  // Load saved portfolio on mount
  useEffect(() => {
    loadPortfolio()
  }, [])

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
          <button onClick={refreshPrices} disabled={loading || holdings.length === 0} className="btn-secondary flex items-center gap-2">
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
            Refresh
          </button>
          <button onClick={savePortfolio} className="btn-secondary flex items-center gap-2">
            <Save className="w-4 h-4" />
            Save
          </button>
          <button onClick={loadPortfolio} className="btn-secondary flex items-center gap-2">
            <Upload className="w-4 h-4" />
            Load
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

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
            <button onClick={addPosition} disabled={loading} className="btn-primary flex items-center gap-2">
              <Plus className={cn('w-4 h-4', loading && 'animate-spin')} />
              {loading ? 'Adding...' : 'Add'}
            </button>
          </div>
        </div>

        {/* Holdings Table */}
        <div className="col-span-8 card overflow-hidden">
          <div className="p-4 border-b border-border">
            <h3 className="text-sm font-bold">Holdings</h3>
          </div>
          {holdings.length === 0 ? (
            <div className="p-8 text-center text-foreground-muted">
              <p className="text-sm">No holdings yet</p>
              <p className="text-xs mt-1">Add your first position above to get started</p>
            </div>
          ) : (
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
                  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0
                  const weight = totalValue > 0 ? (value / totalValue) * 100 : 0

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
          )}
        </div>

        {/* Summary */}
        <div className="col-span-4 space-y-4">
          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">PORTFOLIO SUMMARY</h3>
            {holdings.length === 0 ? (
              <p className="text-xs text-foreground-muted text-center py-4">Add positions to see summary</p>
            ) : (
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
            )}
          </div>

          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">ALLOCATION</h3>
            {sectorData.length === 0 ? (
              <p className="text-xs text-foreground-muted text-center py-4">Add positions to see allocation</p>
            ) : (
              <div className="flex justify-center">
                <DonutChart data={sectorData} size={120} />
              </div>
            )}
          </div>

          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">RISK METRICS</h3>
            {holdings.length === 0 ? (
              <p className="text-xs text-foreground-muted text-center py-4">Add positions to calculate metrics</p>
            ) : (
              <div className="space-y-2 text-xs">
                <p className="text-foreground-muted text-center">
                  Risk metrics require historical data.
                  <br />
                  Connect to a data provider to calculate.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
