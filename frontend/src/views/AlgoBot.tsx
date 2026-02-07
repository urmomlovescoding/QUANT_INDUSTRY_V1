import { Bot, Play, Pause, Square, RefreshCw, TrendingUp, TrendingDown, Activity, Zap } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { cn } from '@/utils/cn'

interface BotStatus {
  status: string
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

interface Strategy {
  name: string
  weight: number
  enabled: boolean
  win_rate: number
  pnl: number
  trades: number
}

export function AlgoBot() {
  const [botStatus, setBotStatus] = useState<BotStatus>({
    status: 'STOPPED', capital: 100000, open_positions: 0,
    mode: 'PAPER', pnl_today: 0, pnl_total: 0, trades_today: 0, win_rate: 0
  })
  const [trades, setTrades] = useState<BotTrade[]>([])
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [riskPerTrade, setRiskPerTrade] = useState(1)
  const [mode, setMode] = useState<'SIGNAL_ONLY' | 'PAPER' | 'LIVE'>('PAPER')
  const [timeframe, setTimeframe] = useState('1h')
  const [maxPositions, setMaxPositions] = useState(5)
  const [trailingStop, setTrailingStop] = useState(true)
  const equityCanvasRef = useRef<HTMLCanvasElement>(null)
  const pollRef = useRef<NodeJS.Timeout | null>(null)

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/algobot/status')
      if (res.ok) {
        const data = await res.json()
        setBotStatus(data)
      }
    } catch (err) {
      // Silent fail for polling
    }
  }

  const fetchTrades = async () => {
    try {
      const res = await fetch('/api/algobot/trades')
      if (res.ok) {
        const data = await res.json()
        setTrades(Array.isArray(data) ? data : [])
      }
    } catch (err) {
      // Silent fail
    }
  }

  const fetchStrategies = async () => {
    try {
      const res = await fetch('/api/brain-v6/strategies')
      if (res.ok) {
        const data = await res.json()
        setStrategies(data.strategies || [])
      }
    } catch (err) {
      // Silent fail - strategies not required
    }
  }

  const fetchAll = async () => {
    setLoading(true)
    await Promise.all([fetchStatus(), fetchTrades(), fetchStrategies()])
    setLoading(false)
  }

  useEffect(() => {
    fetchAll()
    pollRef.current = setInterval(() => {
      fetchStatus()
      fetchTrades()
    }, 10000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  // Draw equity curve
  useEffect(() => {
    if (!equityCanvasRef.current) return
    const canvas = equityCanvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    const width = rect.width
    const height = rect.height
    const padding = 30

    // Background
    ctx.fillStyle = '#0d1117'
    ctx.fillRect(0, 0, width, height)

    // Generate equity curve from trades or fallback
    const capital = botStatus.capital || 100000
    const points: number[] = [capital - (botStatus.pnl_total || 0)]
    let runningPnl = capital - (botStatus.pnl_total || 0)

    if (trades.length > 0) {
      for (const t of [...trades].reverse()) {
        runningPnl += t.pnl
        points.push(runningPnl)
      }
    } else {
      // Generate sample data
      let v = capital * 0.97
      for (let i = 0; i < 60; i++) {
        v += (Math.random() - 0.45) * capital * 0.005
        points.push(v)
      }
      points.push(capital)
    }

    const minVal = Math.min(...points) * 0.999
    const maxVal = Math.max(...points) * 1.001
    const range = maxVal - minVal || 1

    const chartW = width - padding * 2
    const chartH = height - padding * 2

    // Grid
    ctx.strokeStyle = '#1a1f2e'
    ctx.lineWidth = 1
    for (let i = 0; i <= 4; i++) {
      const y = padding + (chartH * i / 4)
      ctx.beginPath()
      ctx.moveTo(padding, y)
      ctx.lineTo(width - padding, y)
      ctx.stroke()

      const val = maxVal - (range * i / 4)
      ctx.fillStyle = '#666'
      ctx.font = '9px monospace'
      ctx.textAlign = 'right'
      ctx.fillText(`$${(val / 1000).toFixed(1)}k`, padding - 4, y + 3)
    }

    // Equity line
    const isPositive = points[points.length - 1] >= points[0]
    ctx.strokeStyle = isPositive ? '#00c853' : '#ff5252'
    ctx.lineWidth = 2
    ctx.beginPath()
    points.forEach((p, i) => {
      const x = padding + (i / Math.max(points.length - 1, 1)) * chartW
      const y = padding + (1 - (p - minVal) / range) * chartH
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()

    // Fill
    const lastX = padding + chartW
    const lastY = padding + (1 - (points[points.length - 1] - minVal) / range) * chartH
    ctx.lineTo(lastX, padding + chartH)
    ctx.lineTo(padding, padding + chartH)
    ctx.closePath()
    ctx.fillStyle = isPositive ? 'rgba(0,200,83,0.08)' : 'rgba(255,82,82,0.08)'
    ctx.fill()

    // Label
    ctx.fillStyle = '#888'
    ctx.font = '10px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('Equity Curve', width / 2, height - 4)
  }, [trades, botStatus])

  const startBot = async () => {
    try {
      const res = await fetch('/api/algobot/start', { method: 'POST' })
      if (res.ok) await fetchStatus()
    } catch {}
  }

  const stopBot = async () => {
    try {
      const res = await fetch('/api/algobot/stop', { method: 'POST' })
      if (res.ok) await fetchStatus()
    } catch {}
  }

  const pauseBot = async () => {
    try {
      const res = await fetch('/api/algobot/pause', { method: 'POST' })
      if (res.ok) await fetchStatus()
    } catch {}
  }

  const handleToggle = () => {
    if (botStatus.status === 'STOPPED') startBot()
    else if (botStatus.status === 'RUNNING') pauseBot()
    else startBot()
  }

  const status = botStatus.status || 'STOPPED'

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
        <div className="flex items-center gap-3">
          <button onClick={fetchAll} className="p-2 bg-background-tertiary hover:bg-background-secondary rounded-lg transition">
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
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
              onClick={handleToggle}
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
            <div className="input w-full text-sm font-mono py-2 px-3">${(botStatus.capital || 0).toLocaleString()}</div>
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
            <div className="grid grid-cols-3 gap-1">
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

        {/* Center - Stats + Equity Curve */}
        <div className="col-span-5 space-y-4">
          {/* Stat Cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="card p-3">
              <div className="text-xs text-foreground-muted">Open Positions</div>
              <div className="text-2xl font-bold">{botStatus.open_positions}</div>
            </div>
            <div className="card p-3">
              <div className="text-xs text-foreground-muted">P&L Today</div>
              <div className={cn(
                'text-2xl font-bold font-mono',
                botStatus.pnl_today >= 0 ? 'text-bullish' : 'text-bearish'
              )}>
                {botStatus.pnl_today >= 0 ? '+' : ''}${(botStatus.pnl_today || 0).toFixed(2)}
              </div>
            </div>
            <div className="card p-3">
              <div className="text-xs text-foreground-muted">P&L Total</div>
              <div className={cn(
                'text-2xl font-bold font-mono',
                botStatus.pnl_total >= 0 ? 'text-bullish' : 'text-bearish'
              )}>
                {botStatus.pnl_total >= 0 ? '+' : ''}${(botStatus.pnl_total || 0).toFixed(2)}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="card p-3">
              <div className="text-xs text-foreground-muted mb-1">Total Trades</div>
              <div className="text-xl font-bold">{botStatus.trades_today}</div>
            </div>
            <div className="card p-3">
              <div className="text-xs text-foreground-muted mb-1">Win Rate</div>
              <div className={cn(
                'text-xl font-bold',
                (botStatus.win_rate || 0) >= 50 ? 'text-bullish' : 'text-bearish'
              )}>{(botStatus.win_rate || 0).toFixed(1)}%</div>
            </div>
          </div>

          {/* Equity Curve */}
          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-2">EQUITY CURVE</h3>
            <canvas ref={equityCanvasRef} className="w-full h-[180px]" />
          </div>

          {/* Strategy Performance */}
          {strategies.length > 0 && (
            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">
                STRATEGY ENSEMBLE ({strategies.length})
              </h3>
              <div className="space-y-2 max-h-[200px] overflow-y-auto">
                {strategies
                  .sort((a, b) => b.pnl - a.pnl)
                  .slice(0, 10)
                  .map(s => (
                    <div key={s.name} className="flex items-center justify-between p-2 bg-background-tertiary rounded text-xs">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <Zap className="w-3 h-3 text-accent-primary flex-shrink-0" />
                        <span className="truncate">{s.name}</span>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0">
                        <span className="text-foreground-muted">W: {(s.win_rate || 0).toFixed(0)}%</span>
                        <span className="font-mono w-10 text-right">{(s.weight || 0).toFixed(2)}</span>
                        <span className={cn(
                          'font-mono w-16 text-right',
                          s.pnl >= 0 ? 'text-bullish' : 'text-bearish'
                        )}>
                          ${(s.pnl || 0).toFixed(0)}
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Active Features */}
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
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-foreground-muted">LIVE TRADE LOG</h3>
            <span className="text-xs text-foreground-muted">{trades.length} trades</span>
          </div>
          {trades.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[200px] text-foreground-muted">
              <Activity className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-xs">No trades yet</p>
              <p className="text-xs opacity-50">Start the bot to generate signals</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {trades.map(t => (
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
                      {t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : ''} @ ${(t.price || 0).toFixed(2)}
                      {t.exit_price ? ` → $${t.exit_price.toFixed(2)}` : ''}
                    </div>
                  </div>
                  <div className={cn(
                    'text-sm font-mono font-bold',
                    t.pnl >= 0 ? 'text-bullish' : 'text-bearish'
                  )}>
                    {t.pnl >= 0 ? '+' : ''}${(t.pnl || 0).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Quick Stats Summary */}
          <div className="mt-4 pt-3 border-t border-border">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex justify-between">
                <span className="text-foreground-muted">Avg Win</span>
                <span className="font-mono text-bullish">
                  ${trades.length > 0
                    ? (trades.filter(t => t.pnl > 0).reduce((s, t) => s + t.pnl, 0) / Math.max(1, trades.filter(t => t.pnl > 0).length)).toFixed(0)
                    : '0'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Avg Loss</span>
                <span className="font-mono text-bearish">
                  ${trades.length > 0
                    ? (trades.filter(t => t.pnl < 0).reduce((s, t) => s + t.pnl, 0) / Math.max(1, trades.filter(t => t.pnl < 0).length)).toFixed(0)
                    : '0'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Best Trade</span>
                <span className="font-mono text-bullish">
                  ${trades.length > 0 ? Math.max(...trades.map(t => t.pnl)).toFixed(0) : '0'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Worst Trade</span>
                <span className="font-mono text-bearish">
                  ${trades.length > 0 ? Math.min(...trades.map(t => t.pnl)).toFixed(0) : '0'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
