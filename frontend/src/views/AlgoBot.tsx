import { Bot, Play, Pause, Square, RefreshCw, Activity, Zap } from 'lucide-react'
import { useState, useEffect, useCallback } from 'react'
import { cn } from '@/utils/cn'

interface BotStatus {
  status: 'STOPPED' | 'RUNNING' | 'PAUSED'
  capital: number
  open_positions: number
  mode: string
  pnl_today: number
  pnl_total: number
  trades_today: number
  win_rate: number
}

interface BotTrade {
  id: string
  timestamp: string
  symbol: string
  side: string
  quantity: number
  price: number
  exit_price?: number
  pnl: number
}

export function AlgoBot() {
  const [botStatus, setBotStatus] = useState<BotStatus>({
    status: 'STOPPED',
    capital: 100000,
    open_positions: 0,
    mode: 'PAPER',
    pnl_today: 0,
    pnl_total: 0,
    trades_today: 0,
    win_rate: 0
  })
  const [trades, setTrades] = useState<BotTrade[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [riskPerTrade, setRiskPerTrade] = useState(1)
  const [timeframe, setTimeframe] = useState('1h')
  const [maxPositions, setMaxPositions] = useState(5)
  const [trailingStop, setTrailingStop] = useState(true)

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/algobot/status')
      if (response.ok) {
        const data = await response.json()
        setBotStatus(data)
        setError(null)
      }
    } catch (err) {
      setError('Failed to connect to AlgoBot backend')
    }
  }, [])

  const fetchTrades = useCallback(async () => {
    try {
      const response = await fetch('/api/algobot/trades')
      if (response.ok) {
        const data = await response.json()
        setTrades(data)
      }
    } catch (err) {
      console.error('Failed to fetch trades:', err)
    }
  }, [])

  // Initial load
  useEffect(() => {
    const load = async () => {
      setLoading(true)
      await Promise.all([fetchStatus(), fetchTrades()])
      setLoading(false)
    }
    load()
  }, [fetchStatus, fetchTrades])

  // Auto-refresh every 10 seconds when running
  useEffect(() => {
    const interval = setInterval(() => {
      fetchStatus()
      fetchTrades()
    }, botStatus.status === 'RUNNING' ? 5000 : 15000)
    return () => clearInterval(interval)
  }, [botStatus.status, fetchStatus, fetchTrades])

  const startBot = async () => {
    try {
      const response = await fetch('/api/algobot/start', { method: 'POST' })
      if (response.ok) {
        await fetchStatus()
      }
    } catch (err) {
      setError('Failed to start bot')
    }
  }

  const pauseBot = async () => {
    try {
      const response = await fetch('/api/algobot/pause', { method: 'POST' })
      if (response.ok) {
        await fetchStatus()
      }
    } catch (err) {
      setError('Failed to pause bot')
    }
  }

  const stopBot = async () => {
    try {
      const response = await fetch('/api/algobot/stop', { method: 'POST' })
      if (response.ok) {
        await fetchStatus()
      }
    } catch (err) {
      setError('Failed to stop bot')
    }
  }

  const toggleBot = () => {
    if (botStatus.status === 'STOPPED') startBot()
    else if (botStatus.status === 'RUNNING') pauseBot()
    else startBot()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-accent-primary mx-auto mb-2" />
          <p className="text-sm text-foreground-muted">Connecting to AlgoBot...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            'p-2 rounded-lg',
            botStatus.status === 'RUNNING' ? 'bg-bullish/20' : botStatus.status === 'PAUSED' ? 'bg-warning/20' : 'bg-background-tertiary'
          )}>
            <Bot className={cn(
              'w-5 h-5',
              botStatus.status === 'RUNNING' ? 'text-bullish' : botStatus.status === 'PAUSED' ? 'text-warning' : 'text-foreground-muted'
            )} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">QUANT BRAIN v10.0</h1>
            <p className="text-xs text-foreground-muted">Algorithmic Trading Bot — Live API Connected</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => { fetchStatus(); fetchTrades() }} className="btn-ghost text-xs px-3 py-1.5 flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
          <span className={cn(
            'px-3 py-1 rounded text-xs font-bold flex items-center gap-2',
            botStatus.status === 'RUNNING' ? 'bg-bullish text-white' :
            botStatus.status === 'PAUSED' ? 'bg-warning text-background-primary' :
            'bg-foreground-muted/20 text-foreground-muted'
          )}>
            <span className={cn(
              'w-2 h-2 rounded-full',
              botStatus.status === 'RUNNING' ? 'bg-white animate-pulse' :
              botStatus.status === 'PAUSED' ? 'bg-background-primary' : 'bg-foreground-muted'
            )} />
            {botStatus.status}
          </span>
        </div>
      </div>

      {error && (
        <div className="card p-3 bg-bearish/10 border border-bearish/30">
          <p className="text-xs text-bearish">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-12 gap-4">
        {/* Controls */}
        <div className="col-span-3 card p-4 space-y-4">
          <h3 className="text-xs font-bold text-foreground-muted flex items-center gap-2">
            <Zap className="w-3 h-3" /> BOT CONTROLS
          </h3>

          <div className="flex gap-2">
            <button
              onClick={toggleBot}
              className={cn(
                'flex-1 py-2 rounded font-medium flex items-center justify-center gap-2 text-sm',
                botStatus.status === 'STOPPED' ? 'bg-bullish text-white hover:bg-bullish/90' :
                botStatus.status === 'RUNNING' ? 'bg-warning text-background-primary hover:bg-warning/90' : 'bg-bullish text-white hover:bg-bullish/90'
              )}
            >
              {botStatus.status === 'RUNNING' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              {botStatus.status === 'STOPPED' ? 'Start' : botStatus.status === 'RUNNING' ? 'Pause' : 'Resume'}
            </button>
            <button
              onClick={stopBot}
              disabled={botStatus.status === 'STOPPED'}
              className="px-4 py-2 rounded bg-bearish text-white disabled:opacity-50 hover:bg-bearish/90"
            >
              <Square className="w-4 h-4" />
            </button>
          </div>

          <div>
            <label className="block text-xs text-foreground-muted mb-1">Capital</label>
            <div className="input w-full text-sm font-mono bg-background-secondary cursor-default">
              ${botStatus.capital.toLocaleString()}
            </div>
          </div>

          <div>
            <label className="block text-xs text-foreground-muted mb-1">Execution Mode</label>
            <div className={cn(
              'input w-full text-sm font-bold cursor-default',
              botStatus.mode === 'LIVE' ? 'text-bearish' : botStatus.mode === 'PAPER' ? 'text-warning' : 'text-foreground-muted'
            )}>
              {botStatus.mode}
            </div>
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
            <label className="block text-xs text-foreground-muted mb-1">Timeframe</label>
            <div className="grid grid-cols-3 gap-1">
              {['1m', '5m', '15m', '1h', '4h', '1d'].map(tf => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={cn(
                    'py-1 text-xs rounded transition-colors',
                    timeframe === tf
                      ? 'bg-accent-primary text-background-primary'
                      : 'bg-background-tertiary text-foreground-secondary hover:text-foreground-primary'
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
              <div className="text-2xl font-bold">{botStatus.open_positions}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted">P&L Today</div>
              <div className={cn(
                'text-2xl font-bold font-mono',
                botStatus.pnl_today >= 0 ? 'text-bullish' : 'text-bearish'
              )}>
                {botStatus.pnl_today >= 0 ? '+' : ''}${botStatus.pnl_today.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted">P&L Total</div>
              <div className={cn(
                'text-2xl font-bold font-mono',
                botStatus.pnl_total >= 0 ? 'text-bullish' : 'text-bearish'
              )}>
                {botStatus.pnl_total >= 0 ? '+' : ''}${botStatus.pnl_total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Total Trades</div>
              <div className="text-xl font-bold">{botStatus.trades_today}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Win Rate</div>
              <div className={cn(
                'text-xl font-bold',
                botStatus.win_rate >= 50 ? 'text-bullish' : botStatus.win_rate > 0 ? 'text-bearish' : 'text-foreground-muted'
              )}>
                {botStatus.win_rate}%
              </div>
            </div>
          </div>

          {/* Features */}
          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3 flex items-center gap-2">
              <Activity className="w-3 h-3" /> ACTIVE FEATURES
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {[
                { name: 'HMM Regime Detection', active: true },
                { name: 'Kalman Filters', active: true },
                { name: 'Multi-Agent System', active: botStatus.status === 'RUNNING' },
                { name: 'Kelly Sizing', active: true },
                { name: 'Auto-Execution', active: botStatus.mode !== 'SIGNAL_ONLY' },
                { name: 'Evolution Engine', active: botStatus.status === 'RUNNING' },
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
          <h3 className="text-xs font-bold text-foreground-muted mb-3">TRADE LOG</h3>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {trades.length === 0 ? (
              <div className="text-center py-8 text-foreground-muted">
                <Bot className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-xs">No trades recorded yet.</p>
                <p className="text-xs mt-1">Start the bot to begin trading.</p>
              </div>
            ) : (
              trades.map(t => (
                <div key={t.id} className="p-2 bg-background-tertiary rounded flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'text-xs font-bold',
                        t.side === 'BUY' || t.side === 'LONG' ? 'text-bullish' : 'text-bearish'
                      )}>
                        {t.side}
                      </span>
                      <span className="text-sm font-medium">{t.symbol}</span>
                      <span className="text-xs text-foreground-muted">x{t.quantity}</span>
                    </div>
                    <div className="text-xs text-foreground-muted">
                      {new Date(t.timestamp).toLocaleTimeString()} @ ${t.price}
                      {t.exit_price && ` → $${t.exit_price}`}
                    </div>
                  </div>
                  <div className={cn(
                    'text-sm font-mono font-bold',
                    t.pnl >= 0 ? 'text-bullish' : 'text-bearish'
                  )}>
                    {t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
