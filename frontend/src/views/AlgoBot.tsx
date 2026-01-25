import { Bot, Play, Pause, Square } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

export function AlgoBot() {
  const [status, setStatus] = useState<'STOPPED' | 'RUNNING' | 'PAUSED'>('STOPPED')
  const [capital, setCapital] = useState(100000)
  const [riskPerTrade, setRiskPerTrade] = useState(1)
  const [mode, setMode] = useState<'SIGNAL_ONLY' | 'PAPER' | 'LIVE'>('PAPER')
  const [timeframe, setTimeframe] = useState('1h')
  const [maxPositions, setMaxPositions] = useState(5)
  const [trailingStop, setTrailingStop] = useState(true)

  const [stats] = useState({
    openPositions: 3,
    pnlToday: 1250.50,
    pnlTotal: 8750.25,
    tradesTotal: 156,
    winRate: 68.5
  })

  const [trades] = useState([
    { id: 'T001', time: '14:32:15', symbol: 'NVDA', side: 'BUY', qty: 50, price: 141.50, pnl: 125.00 },
    { id: 'T002', time: '13:45:22', symbol: 'AAPL', side: 'SELL', qty: 30, price: 236.20, pnl: -45.50 },
    { id: 'T003', time: '12:18:08', symbol: 'AMD', side: 'BUY', qty: 100, price: 124.80, pnl: 320.00 },
    { id: 'T004', time: '11:05:33', symbol: 'MSFT', side: 'BUY', qty: 25, price: 440.15, pnl: 87.50 },
    { id: 'T005', time: '10:22:47', symbol: 'SPY', side: 'SELL', qty: 50, price: 687.30, pnl: -112.00 },
  ])

  const toggleBot = () => {
    if (status === 'STOPPED') {
      setStatus('RUNNING')
    } else if (status === 'RUNNING') {
      setStatus('PAUSED')
    } else {
      setStatus('RUNNING')
    }
  }

  const stopBot = () => {
    setStatus('STOPPED')
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            'p-2 rounded-lg',
            status === 'RUNNING' ? 'bg-bullish/20' : status === 'PAUSED' ? 'bg-warning/20' : 'bg-background-tertiary'
          )}>
            <Bot className={cn(
              'w-5 h-5',
              status === 'RUNNING' ? 'text-bullish' : status === 'PAUSED' ? 'text-warning' : 'text-foreground-muted'
            )} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">QUANT BRAIN v10.0</h1>
            <p className="text-xs text-foreground-muted">Algorithmic Trading Bot</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn(
            'px-3 py-1 rounded text-xs font-bold flex items-center gap-2',
            status === 'RUNNING' ? 'bg-bullish text-white' :
            status === 'PAUSED' ? 'bg-warning text-background-primary' :
            'bg-foreground-muted/20 text-foreground-muted'
          )}>
            <span className={cn(
              'w-2 h-2 rounded-full',
              status === 'RUNNING' ? 'bg-white animate-pulse' :
              status === 'PAUSED' ? 'bg-background-primary' : 'bg-foreground-muted'
            )} />
            {status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Controls */}
        <div className="col-span-3 card p-4 space-y-4">
          <h3 className="text-xs font-bold text-foreground-muted">BOT CONTROLS</h3>

          <div className="flex gap-2">
            <button
              onClick={toggleBot}
              className={cn(
                'flex-1 py-2 rounded font-medium flex items-center justify-center gap-2',
                status === 'STOPPED' ? 'bg-bullish text-white' :
                status === 'RUNNING' ? 'bg-warning text-background-primary' : 'bg-bullish text-white'
              )}
            >
              {status === 'RUNNING' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              {status === 'STOPPED' ? 'Start' : status === 'RUNNING' ? 'Pause' : 'Resume'}
            </button>
            <button
              onClick={stopBot}
              disabled={status === 'STOPPED'}
              className="px-4 py-2 rounded bg-bearish text-white disabled:opacity-50"
            >
              <Square className="w-4 h-4" />
            </button>
          </div>

          <div>
            <label className="block text-xs text-foreground-muted mb-1">Capital ($)</label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="input w-full"
              disabled={status !== 'STOPPED'}
            />
          </div>

          <div>
            <label className="block text-xs text-foreground-muted mb-1">Risk per Trade (%)</label>
            <input
              type="number"
              value={riskPerTrade}
              onChange={(e) => setRiskPerTrade(Number(e.target.value))}
              className="input w-full"
              step={0.5}
              min={0.5}
              max={5}
            />
          </div>

          <div>
            <label className="block text-xs text-foreground-muted mb-1">Execution Mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as any)}
              className="input w-full"
              disabled={status !== 'STOPPED'}
            >
              <option value="SIGNAL_ONLY">Signal Only</option>
              <option value="PAPER">Paper Trading</option>
              <option value="LIVE">Live Trading</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-foreground-muted mb-1">Timeframe</label>
            <div className="grid grid-cols-4 gap-1">
              {['1m', '5m', '15m', '1h', '4h', '1d'].map(tf => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={cn(
                    'py-1 text-xs rounded transition-colors',
                    timeframe === tf
                      ? 'bg-accent-primary text-background-primary'
                      : 'bg-background-tertiary text-foreground-secondary'
                  )}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs text-foreground-muted mb-1">Max Positions</label>
            <input
              type="number"
              value={maxPositions}
              onChange={(e) => setMaxPositions(Number(e.target.value))}
              className="input w-full"
              min={1}
              max={20}
            />
          </div>

          <div className="flex items-center justify-between py-2">
            <span className="text-xs">Trailing Stop</span>
            <button
              onClick={() => setTrailingStop(!trailingStop)}
              className={cn(
                'w-10 h-6 rounded-full transition-colors relative',
                trailingStop ? 'bg-accent-primary' : 'bg-background-tertiary'
              )}
            >
              <div className={cn(
                'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                trailingStop ? 'translate-x-5' : 'translate-x-1'
              )} />
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="col-span-5 space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="card p-4">
              <div className="text-xs text-foreground-muted">Open Positions</div>
              <div className="text-2xl font-bold">{stats.openPositions}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted">P&L Today</div>
              <div className={cn(
                'text-2xl font-bold font-mono',
                stats.pnlToday >= 0 ? 'text-bullish' : 'text-bearish'
              )}>
                {stats.pnlToday >= 0 ? '+' : ''}${stats.pnlToday.toFixed(2)}
              </div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted">P&L Total</div>
              <div className={cn(
                'text-2xl font-bold font-mono',
                stats.pnlTotal >= 0 ? 'text-bullish' : 'text-bearish'
              )}>
                {stats.pnlTotal >= 0 ? '+' : ''}${stats.pnlTotal.toFixed(2)}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Total Trades</div>
              <div className="text-xl font-bold">{stats.tradesTotal}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Win Rate</div>
              <div className="text-xl font-bold text-bullish">{stats.winRate}%</div>
            </div>
          </div>

          {/* Features */}
          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">ACTIVE FEATURES</h3>
            <div className="grid grid-cols-2 gap-2">
              {[
                { name: 'HMM Regime Detection', active: true },
                { name: 'Kalman Filters', active: true },
                { name: 'Multi-Agent System', active: false },
                { name: 'Kelly Sizing', active: true },
                { name: 'Auto-Execution', active: mode !== 'SIGNAL_ONLY' },
                { name: 'Evolution Engine', active: false },
              ].map(f => (
                <div key={f.name} className={cn(
                  'p-2 rounded text-xs flex items-center gap-2',
                  f.active ? 'bg-bullish/10 text-bullish' : 'bg-background-tertiary text-foreground-muted'
                )}>
                  <div className={cn(
                    'w-2 h-2 rounded-full',
                    f.active ? 'bg-bullish' : 'bg-foreground-muted'
                  )} />
                  {f.name}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Trade Log */}
        <div className="col-span-4 card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-3">LIVE TRADE LOG</h3>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {trades.map(t => (
              <div key={t.id} className="p-2 bg-background-tertiary rounded flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      'text-xs font-bold',
                      t.side === 'BUY' ? 'text-bullish' : 'text-bearish'
                    )}>
                      {t.side}
                    </span>
                    <span className="text-sm font-medium">{t.symbol}</span>
                    <span className="text-xs text-foreground-muted">x{t.qty}</span>
                  </div>
                  <div className="text-xs text-foreground-muted">{t.time} @ ${t.price}</div>
                </div>
                <div className={cn(
                  'text-sm font-mono font-bold',
                  t.pnl >= 0 ? 'text-bullish' : 'text-bearish'
                )}>
                  {t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
