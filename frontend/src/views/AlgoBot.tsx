import { Bot, Play, Pause, Square, RefreshCw, Loader2 } from 'lucide-react'
import { useState, useEffect, useCallback } from 'react'
import { cn } from '@/utils/cn'

interface AlgoBotStatus {
  status: 'STOPPED' | 'RUNNING' | 'PAUSED'
  capital: number
  open_positions: number
  mode: string
  pnl_today: number
  pnl_total: number
  trades_today: number
  win_rate: number
}

interface AlgoBotTrade {
  id: string
  timestamp: string
  symbol: string
  side: string
  quantity: number
  price: number
  exit_price: number | null
  pnl: number
}

export function AlgoBot() {
  const [status, setStatus] = useState<'STOPPED' | 'RUNNING' | 'PAUSED'>('STOPPED')
  const [capital, setCapital] = useState(100000)
  const [riskPerTrade, setRiskPerTrade] = useState(1)
  const [mode, setMode] = useState<'SIGNAL_ONLY' | 'PAPER' | 'LIVE'>('PAPER')
  const [timeframe, setTimeframe] = useState('1h')
  const [maxPositions, setMaxPositions] = useState(5)
  const [trailingStop, setTrailingStop] = useState(true)

  const [stats, setStats] = useState<AlgoBotStatus | null>(null)
  const [trades, setTrades] = useState<AlgoBotTrade[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/algobot/status')
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.json()
      setStats(data)
      setStatus(data.status || 'STOPPED')
      if (data.capital) setCapital(data.capital)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch bot status')
    }
  }, [])

  const fetchTrades = useCallback(async () => {
    try {
      const response = await fetch('/api/algobot/trades')
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.json()
      if (Array.isArray(data)) {
        setTrades(data)
      } else if (data.trades && Array.isArray(data.trades)) {
        setTrades(data.trades)
      }
    } catch {
      // Non-critical - trades may not be available yet
    }
  }, [])

  const fetchAll = useCallback(async () => {
    setLoading(true)
    await Promise.all([fetchStatus(), fetchTrades()])
    setLoading(false)
  }, [fetchStatus, fetchTrades])

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 10000)
    return () => clearInterval(interval)
  }, [fetchAll])

  const startBot = async () => {
    try {
      const response = await fetch('/api/algobot/start', { method: 'POST' })
      if (response.ok) {
        setStatus('RUNNING')
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
        setStatus('PAUSED')
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
        setStatus('STOPPED')
        await fetchStatus()
      }
    } catch (err) {
      setError('Failed to stop bot')
    }
  }

  const toggleBot = () => {
    if (status === 'STOPPED') {
      startBot()
    } else if (status === 'RUNNING') {
      pauseBot()
    } else {
      startBot()
    }
  }

  const pnlToday = stats?.pnl_today ?? 0
  const pnlTotal = stats?.pnl_total ?? 0
  const openPositions = stats?.open_positions ?? 0
  const tradesTotal = stats?.trades_today ?? 0
  const winRate = stats?.win_rate ?? 0

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
          <button
            onClick={fetchAll}
            className="p-2 rounded bg-background-tertiary hover:bg-background-secondary transition-colors"
            title="Refresh"
          >
            <RefreshCw className={cn('w-4 h-4 text-foreground-muted', loading && 'animate-spin')} />
          </button>
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

      {/* Error */}
      {error && (
        <div className="card p-3 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

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
          {loading && !stats ? (
            <div className="card p-8 flex items-center justify-center">
              <Loader2 className="w-6 h-6 text-accent-primary animate-spin" />
              <span className="ml-2 text-sm text-foreground-muted">Loading bot status...</span>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-4">
                <div className="card p-4">
                  <div className="text-xs text-foreground-muted">Open Positions</div>
                  <div className="text-2xl font-bold">{openPositions}</div>
                </div>
                <div className="card p-4">
                  <div className="text-xs text-foreground-muted">P&L Today</div>
                  <div className={cn(
                    'text-2xl font-bold font-mono',
                    pnlToday >= 0 ? 'text-bullish' : 'text-bearish'
                  )}>
                    {pnlToday >= 0 ? '+' : ''}${pnlToday.toFixed(2)}
                  </div>
                </div>
                <div className="card p-4">
                  <div className="text-xs text-foreground-muted">P&L Total</div>
                  <div className={cn(
                    'text-2xl font-bold font-mono',
                    pnlTotal >= 0 ? 'text-bullish' : 'text-bearish'
                  )}>
                    {pnlTotal >= 0 ? '+' : ''}${pnlTotal.toFixed(2)}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="card p-4">
                  <div className="text-xs text-foreground-muted mb-1">Total Trades</div>
                  <div className="text-xl font-bold">{tradesTotal}</div>
                </div>
                <div className="card p-4">
                  <div className="text-xs text-foreground-muted mb-1">Win Rate</div>
                  <div className={cn(
                    'text-xl font-bold',
                    winRate >= 50 ? 'text-bullish' : winRate > 0 ? 'text-warning' : 'text-foreground-muted'
                  )}>{winRate}%</div>
                </div>
              </div>
            </>
          )}

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
            {loading && trades.length === 0 ? (
              <div className="p-4 flex items-center justify-center">
                <Loader2 className="w-4 h-4 text-accent-primary animate-spin" />
                <span className="ml-2 text-xs text-foreground-muted">Loading trades...</span>
              </div>
            ) : trades.length === 0 ? (
              <div className="p-4 text-center text-xs text-foreground-muted">
                No trades yet. Start the bot to begin trading.
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
                      {t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : 'N/A'} @ ${t.price}
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
