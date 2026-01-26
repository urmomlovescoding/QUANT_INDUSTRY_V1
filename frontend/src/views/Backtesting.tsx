import { Timer, Play } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { cn } from '@/utils/cn'

const strategies = [
  { id: 'sma_cross', name: 'SMA Crossover', category: 'TREND' },
  { id: 'rsi_oversold', name: 'RSI Oversold', category: 'REVERSION' },
  { id: 'macd_cross', name: 'MACD Crossover', category: 'MOMENTUM' },
  { id: 'bb_breakout', name: 'Bollinger Breakout', category: 'VOLATILITY' },
  { id: 'momentum', name: 'Price Momentum', category: 'MOMENTUM' },
  { id: 'mean_rev', name: 'Mean Reversion', category: 'REVERSION' },
]

const periods = ['6M', '1Y', '2Y', '5Y', 'MAX']

export function Backtesting() {
  const [ticker, setTicker] = useState('SPY')
  const [strategy, setStrategy] = useState('sma_cross')
  const [period, setPeriod] = useState('1Y')
  const [capital, setCapital] = useState(100000)
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('equity')
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const runBacktest = async () => {
    setRunning(true)
    setError(null)

    try {
      const response = await fetch(`/api/backtest/run?strategy=${strategy}&symbol=${ticker}&period=${period}&capital=${capital}`, {
        method: 'POST',
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to run backtest')
      }

      if (data.status === 'unavailable') {
        setError(data.message || 'Backtesting not available. Configure backtest service to enable.')
        setResults(null)
        return
      }

      const result = data.data || data
      setResults({
        totalReturn: result.total_return || result.totalReturn || 0,
        sharpe: result.sharpe_ratio || result.sharpe || 0,
        maxDD: result.max_drawdown || result.maxDD || 0,
        winRate: result.win_rate || result.winRate || 0,
        trades: result.total_trades || result.trades || 0,
        profitFactor: result.profit_factor || result.profitFactor || 1,
        equityCurve: result.equity_curve || result.equityCurve || [],
        recentTrades: result.trades_list || result.recentTrades || [],
        finalEquity: result.final_equity || result.finalEquity || capital,
        buyHoldReturn: result.buy_hold_return || result.buyHoldReturn || 0
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run backtest')
      setResults(null)
    } finally {
      setRunning(false)
    }
  }

  useEffect(() => {
    if (!results || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    const width = rect.width
    const height = rect.height
    const padding = { top: 20, right: 20, bottom: 30, left: 60 }

    // Clear
    ctx.fillStyle = '#0d1117'
    ctx.fillRect(0, 0, width, height)

    const data = results.equityCurve
    const minVal = Math.min(...data.map((d: any) => Math.min(d.equity, d.buyHold)))
    const maxVal = Math.max(...data.map((d: any) => Math.max(d.equity, d.buyHold)))
    const range = maxVal - minVal

    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom

    // Draw grid
    ctx.strokeStyle = '#1a1f2e'
    ctx.lineWidth = 1
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartHeight * i / 4)
      ctx.beginPath()
      ctx.moveTo(padding.left, y)
      ctx.lineTo(width - padding.right, y)
      ctx.stroke()

      const value = maxVal - (range * i / 4)
      ctx.fillStyle = '#666'
      ctx.font = '10px monospace'
      ctx.textAlign = 'right'
      ctx.fillText(`$${(value / 1000).toFixed(0)}k`, padding.left - 5, y + 3)
    }

    // Draw strategy equity curve
    ctx.strokeStyle = '#00c853'
    ctx.lineWidth = 2
    ctx.beginPath()
    data.forEach((d: any, i: number) => {
      const x = padding.left + (i / data.length) * chartWidth
      const y = padding.top + (1 - (d.equity - minVal) / range) * chartHeight
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()

    // Draw buy & hold curve
    ctx.strokeStyle = '#666'
    ctx.lineWidth = 1.5
    ctx.setLineDash([5, 5])
    ctx.beginPath()
    data.forEach((d: any, i: number) => {
      const x = padding.left + (i / data.length) * chartWidth
      const y = padding.top + (1 - (d.buyHold - minVal) / range) * chartHeight
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()
    ctx.setLineDash([])

    // Legend
    ctx.fillStyle = '#00c853'
    ctx.fillRect(padding.left + 10, padding.top + 10, 20, 3)
    ctx.fillStyle = '#fff'
    ctx.font = '11px sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText('Strategy', padding.left + 35, padding.top + 14)

    ctx.fillStyle = '#666'
    ctx.fillRect(padding.left + 100, padding.top + 10, 20, 3)
    ctx.fillStyle = '#fff'
    ctx.fillText('Buy & Hold', padding.left + 125, padding.top + 14)

  }, [results, activeTab])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Timer className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">INSTITUTIONAL BACKTESTER</h1>
          </div>
        </div>
        {results && (
          <span className="text-xs text-bullish flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-bullish" />
            BACKTEST COMPLETE
          </span>
        )}
      </div>

      {/* Controls */}
      <div className="card p-4">
        <div className="flex items-end gap-4 flex-wrap">
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="input w-24"
            />
          </div>
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Strategy</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="input w-48"
            >
              {strategies.map(s => (
                <option key={s.id} value={s.id}>{s.name} ({s.category})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Period</label>
            <div className="flex gap-1">
              {periods.map(p => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={cn(
                    'px-3 py-2 text-xs rounded transition-colors',
                    period === p
                      ? 'bg-accent-primary text-background-primary'
                      : 'bg-background-tertiary text-foreground-secondary hover:text-foreground-primary'
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Capital</label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="input w-28"
            />
          </div>
          <button
            onClick={runBacktest}
            disabled={running}
            className="btn-primary flex items-center gap-2"
          >
            <Play className={cn('w-4 h-4', running && 'animate-spin')} />
            {running ? 'Running...' : 'Run Backtest'}
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {results && (
        <div className="grid grid-cols-12 gap-4">
          {/* Chart */}
          <div className="col-span-9 card p-4">
            {/* Tabs */}
            <div className="flex gap-2 mb-4">
              {['equity', 'drawdown', 'trades'].map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    'px-3 py-1.5 text-xs font-medium rounded transition-colors capitalize',
                    activeTab === tab
                      ? 'bg-accent-primary text-background-primary'
                      : 'bg-background-tertiary text-foreground-secondary'
                  )}
                >
                  {tab === 'equity' ? 'Equity Curve' : tab === 'drawdown' ? 'Drawdown' : 'Trades'}
                </button>
              ))}
            </div>

            {activeTab === 'equity' && (
              <canvas ref={canvasRef} className="w-full h-[350px]" />
            )}

            {activeTab === 'trades' && (
              <div className="max-h-[350px] overflow-y-auto">
                <table className="data-table">
                  <thead className="sticky top-0 bg-background-secondary">
                    <tr>
                      <th>Symbol</th>
                      <th>Entry Date</th>
                      <th>Exit Date</th>
                      <th>Entry Price</th>
                      <th>Exit Price</th>
                      <th>P&L</th>
                      <th>P&L %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.recentTrades.map((t: any, i: number) => (
                      <tr key={i}>
                        <td className="font-medium">{t.symbol}</td>
                        <td className="text-xs">{t.entry_date}</td>
                        <td className="text-xs">{t.exit_date}</td>
                        <td className="font-mono">${t.entry_price.toFixed(2)}</td>
                        <td className="font-mono">${t.exit_price.toFixed(2)}</td>
                        <td className={cn('font-mono', t.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                          {t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}
                        </td>
                        <td className={cn('font-mono', t.pnl_pct >= 0 ? 'text-bullish' : 'text-bearish')}>
                          {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct.toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Performance Metrics */}
          <div className="col-span-3 space-y-4">
            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">PERFORMANCE METRICS</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Total Return</span>
                  <span className="text-sm font-mono font-bold text-bullish">+{results.totalReturn.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Buy & Hold</span>
                  <span className="text-sm font-mono">{results.buyHoldReturn >= 0 ? '+' : ''}{results.buyHoldReturn.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Sharpe Ratio</span>
                  <span className="text-sm font-mono font-bold text-accent-primary">{results.sharpe.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Max Drawdown</span>
                  <span className="text-sm font-mono text-bearish">{results.maxDD.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Win Rate</span>
                  <span className="text-sm font-mono">{results.winRate.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Profit Factor</span>
                  <span className="text-sm font-mono">{results.profitFactor.toFixed(2)}x</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Total Trades</span>
                  <span className="text-sm font-mono">{results.trades}</span>
                </div>
              </div>
            </div>

            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">STRATEGY INFO</h3>
              <div className="text-xs text-foreground-secondary">
                <p className="mb-2">
                  <strong>{strategies.find(s => s.id === strategy)?.name}</strong>
                </p>
                <p>
                  Category: {strategies.find(s => s.id === strategy)?.category}
                </p>
                <p className="mt-2">
                  Period: {period} | Ticker: {ticker}
                </p>
              </div>
            </div>

            <div className="bg-background-tertiary p-4 rounded">
              <div className="text-xs text-foreground-muted mb-1">Final Equity</div>
              <div className="text-2xl font-mono font-bold text-bullish">
                ${(results.finalEquity).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
