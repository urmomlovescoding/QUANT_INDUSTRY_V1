import { useState, useEffect } from 'react'
import {
  Activity,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Zap,
  Target,
  Shield,
  RefreshCw,
  Play,
  Pause,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  AreaChart,
  Area,
} from 'recharts'

// Futures contracts
const FUTURES_CONTRACTS = [
  { symbol: 'ES', name: 'E-mini S&P 500', multiplier: 50, tickSize: 0.25 },
  { symbol: 'NQ', name: 'E-mini Nasdaq 100', multiplier: 20, tickSize: 0.25 },
  { symbol: 'YM', name: 'E-mini Dow', multiplier: 5, tickSize: 1 },
  { symbol: 'RTY', name: 'E-mini Russell 2000', multiplier: 50, tickSize: 0.1 },
  { symbol: 'CL', name: 'Crude Oil', multiplier: 1000, tickSize: 0.01 },
  { symbol: 'GC', name: 'Gold', multiplier: 100, tickSize: 0.1 },
]

// Transform API price data
const transformPriceData = (apiData: any[]) => {
  return apiData.map((item: any) => ({
    time: item.time || new Date(item.timestamp || item.t).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
    price: item.price || item.close || item.c || 0,
    volume: item.volume || item.v || 0,
  }))
}

// Transform API signals
const transformSignals = (apiData: any[]) => {
  return apiData.map((item: any) => ({
    time: item.time || new Date(item.timestamp).toLocaleTimeString('en-US', { hour12: false }),
    type: item.type || item.signal || 'FLAT',
    confidence: item.confidence || 0.5,
    target: item.target || null,
    stop: item.stop || item.stop_loss || null,
  }))
}

export function FuturesBrain() {
  const [selectedContract, setSelectedContract] = useState(FUTURES_CONTRACTS[0])
  const [priceData, setPriceData] = useState<any[]>([])
  const [signals, setSignals] = useState<any[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [brainStatus, setBrainStatus] = useState<'IDLE' | 'ANALYZING' | 'READY'>('IDLE')
  const [currentSignal, setCurrentSignal] = useState<'LONG' | 'SHORT' | 'FLAT'>('FLAT')
  const [confidence, setConfidence] = useState(0.72)
  const [error, setError] = useState<string | null>(null)
  const [brainMetrics, setBrainMetrics] = useState<any>(null)
  const [todayPerf, setTodayPerf] = useState<any>(null)

  // Fetch initial data from API
  const fetchData = async () => {
    setError(null)
    try {
      // Fetch price data, signals, brain status, and trade stats in parallel
      const [priceRes, signalRes, brainRes, statsRes, riskRes] = await Promise.all([
        fetch(`/api/futures/${selectedContract.symbol}/prices`).catch(() => null),
        fetch(`/api/futures/${selectedContract.symbol}/signals`).catch(() => null),
        fetch('/api/brain-v6/status').catch(() => null),
        fetch('/api/trades/stats').catch(() => null),
        fetch('/api/risk/metrics').catch(() => null),
      ])

      // Process price data
      if (priceRes?.ok) {
        const priceResult = await priceRes.json()
        if (priceResult.status !== 'unavailable') {
          const prices = priceResult.data?.prices || priceResult.prices || []
          if (prices.length > 0) {
            setPriceData(transformPriceData(prices))
          }
        }
      }

      // Process signals
      if (signalRes?.ok) {
        const signalResult = await signalRes.json()
        if (signalResult.status !== 'unavailable') {
          const sigs = signalResult.data?.signals || signalResult.signals || []
          if (sigs.length > 0) {
            setSignals(transformSignals(sigs))
            const latestSignal = sigs[sigs.length - 1]
            setCurrentSignal(latestSignal.type || latestSignal.signal || 'FLAT')
            setConfidence(latestSignal.confidence || 0.5)
          }
        }
      }

      // Process brain metrics
      if (brainRes?.ok) {
        const brainData = await brainRes.json()
        setBrainMetrics({
          neuralStrength: brainData.metrics?.win_rate ? Math.round(brainData.metrics.win_rate) : 0,
          patternMatch: brainData.confidence ? Math.round(brainData.confidence * 100) : 0,
          riskScore: brainData.metrics?.profit_factor >= 1.5 ? 'Low' : brainData.metrics?.profit_factor >= 1.0 ? 'Medium' : 'High',
          regime: brainData.current_regime || 'Unknown',
          isTrained: brainData.is_trained ?? false,
        })
      }

      // Process today's performance
      if (statsRes?.ok) {
        const statsData = await statsRes.json()
        setTodayPerf({
          trades: statsData.totalTrades ?? 0,
          winRate: statsData.winRate ?? 0,
          pnl: statsData.totalPnl ?? 0,
          sharpe: statsData.sharpeRatio ?? 0,
        })
      }

      // Fallback: get risk score from risk metrics
      if (riskRes?.ok && !brainMetrics) {
        const riskData = await riskRes.json()
        setBrainMetrics((prev: any) => ({
          ...(prev || {}),
          riskScore: riskData.risk_score < 40 ? 'Low' : riskData.risk_score < 70 ? 'Medium' : 'High',
        }))
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch futures data')
    }
  }

  useEffect(() => {
    fetchData()
  }, [selectedContract])

  // Real-time updates when running - fetch from WebSocket or polling
  useEffect(() => {
    if (!isRunning) return

    const interval = setInterval(async () => {
      setBrainStatus('ANALYZING')

      try {
        // Fetch latest price
        const res = await fetch(`/api/futures/${selectedContract.symbol}/latest`)
        const data = await res.json()

        if (res.ok && data.price) {
          setPriceData(prev => {
            if (prev.length === 0) return prev
            return [
              ...prev.slice(1),
              {
                time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
                price: data.price,
                volume: data.volume || 0,
              }
            ]
          })

          // Update signal if provided
          if (data.signal) {
            setCurrentSignal(data.signal.type || 'FLAT')
            setConfidence(data.signal.confidence || 0.5)
            if (data.signal.type !== currentSignal) {
              setSignals(prev => [
                ...prev.slice(1),
                {
                  time: new Date().toLocaleTimeString('en-US', { hour12: false }),
                  type: data.signal.type,
                  confidence: data.signal.confidence || 0.5,
                  target: data.signal.target || null,
                  stop: data.signal.stop || null,
                }
              ])
            }
          }
        }
      } catch {
        // Silently handle errors during real-time updates
      }

      setBrainStatus('READY')
    }, 3000)

    return () => clearInterval(interval)
  }, [isRunning])

  const currentPrice = priceData[priceData.length - 1]?.price || 0
  const prevPrice = priceData[priceData.length - 2]?.price || currentPrice
  const priceChange = currentPrice - prevPrice
  const priceChangePercent = ((priceChange / prevPrice) * 100)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Activity className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">FUTURES BRAIN</h1>
            <p className="text-xs text-foreground-muted">AI-Powered Futures Trading Intelligence</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Contract Selector */}
          <select
            value={selectedContract.symbol}
            onChange={(e) => setSelectedContract(FUTURES_CONTRACTS.find(c => c.symbol === e.target.value)!)}
            className="px-3 py-1.5 text-sm bg-background-secondary border border-border rounded-lg text-foreground-primary focus:outline-none focus:border-accent-primary"
          >
            {FUTURES_CONTRACTS.map(contract => (
              <option key={contract.symbol} value={contract.symbol}>
                {contract.symbol} - {contract.name}
              </option>
            ))}
          </select>

          {/* Start/Stop Brain */}
          <button
            onClick={() => setIsRunning(!isRunning)}
            className={cn(
              'flex items-center gap-2 px-4 py-1.5 rounded-lg font-medium text-sm transition-colors',
              isRunning
                ? 'bg-bearish/20 text-bearish hover:bg-bearish/30'
                : 'bg-bullish/20 text-bullish hover:bg-bullish/30'
            )}
          >
            {isRunning ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {isRunning ? 'Stop Brain' : 'Start Brain'}
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left: Price Chart and Analysis */}
        <div className="col-span-8 space-y-4">
          {/* Price Chart */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold text-foreground-primary">
                    {selectedContract.symbol}
                  </span>
                  <span className="text-3xl font-bold text-accent-primary">
                    {currentPrice.toFixed(2)}
                  </span>
                  <span className={cn(
                    'flex items-center gap-1 text-sm font-medium',
                    priceChange >= 0 ? 'text-bullish' : 'text-bearish'
                  )}>
                    {priceChange >= 0 ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    {Math.abs(priceChange).toFixed(2)} ({priceChangePercent.toFixed(2)}%)
                  </span>
                </div>
                <p className="text-xs text-foreground-muted mt-1">{selectedContract.name}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className={cn(
                  'flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold',
                  brainStatus === 'ANALYZING' && 'bg-yellow-500/20 text-yellow-500',
                  brainStatus === 'READY' && 'bg-bullish/20 text-bullish',
                  brainStatus === 'IDLE' && 'bg-foreground-muted/20 text-foreground-muted'
                )}>
                  <RefreshCw className={cn('w-3 h-3', brainStatus === 'ANALYZING' && 'animate-spin')} />
                  {brainStatus}
                </span>
              </div>
            </div>

            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={priceData}>
                  <defs>
                    <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00d4aa" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#00d4aa" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="time"
                    tick={{ fill: '#666', fontSize: 10 }}
                    axisLine={{ stroke: '#333' }}
                    tickLine={{ stroke: '#333' }}
                  />
                  <YAxis
                    domain={['auto', 'auto']}
                    tick={{ fill: '#666', fontSize: 10 }}
                    axisLine={{ stroke: '#333' }}
                    tickLine={{ stroke: '#333' }}
                    tickFormatter={(v) => v.toFixed(0)}
                    width={50}
                  />
                  <Tooltip
                    contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: '8px' }}
                    labelStyle={{ color: '#888' }}
                    formatter={(value: number) => [value.toFixed(2), 'Price']}
                  />
                  <Area
                    type="monotone"
                    dataKey="price"
                    stroke="#00d4aa"
                    strokeWidth={2}
                    fill="url(#priceGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Signal History */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Signal History</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-foreground-muted border-b border-border">
                    <th className="text-left py-2 px-2">Time</th>
                    <th className="text-left py-2 px-2">Signal</th>
                    <th className="text-right py-2 px-2">Confidence</th>
                    <th className="text-right py-2 px-2">Target</th>
                    <th className="text-right py-2 px-2">Stop</th>
                  </tr>
                </thead>
                <tbody>
                  {signals.slice(-8).map((signal, i) => (
                    <tr key={i} className="border-b border-border/50">
                      <td className="py-2 px-2 text-foreground-secondary font-mono">{signal.time}</td>
                      <td className="py-2 px-2">
                        <span className={cn(
                          'px-2 py-0.5 rounded text-[10px] font-bold',
                          signal.type === 'LONG' && 'bg-bullish/20 text-bullish',
                          signal.type === 'SHORT' && 'bg-bearish/20 text-bearish',
                          signal.type === 'FLAT' && 'bg-foreground-muted/20 text-foreground-muted'
                        )}>
                          {signal.type}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-foreground-primary">
                        {(signal.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-bullish">
                        {signal.target ? `+${signal.target}` : '-'}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-bearish">
                        {signal.stop ? `-${signal.stop}` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right: Brain Status & Controls */}
        <div className="col-span-4 space-y-4">
          {/* Current Signal */}
          <div className={cn(
            'card border-2',
            currentSignal === 'LONG' && 'border-bullish',
            currentSignal === 'SHORT' && 'border-bearish',
            currentSignal === 'FLAT' && 'border-foreground-muted'
          )}>
            <div className="text-center">
              <p className="text-xs text-foreground-muted mb-2">CURRENT SIGNAL</p>
              <div className={cn(
                'text-4xl font-bold mb-2',
                currentSignal === 'LONG' && 'text-bullish',
                currentSignal === 'SHORT' && 'text-bearish',
                currentSignal === 'FLAT' && 'text-foreground-muted'
              )}>
                {currentSignal === 'LONG' && <TrendingUp className="w-12 h-12 mx-auto mb-2" />}
                {currentSignal === 'SHORT' && <TrendingDown className="w-12 h-12 mx-auto mb-2" />}
                {currentSignal === 'FLAT' && <AlertTriangle className="w-12 h-12 mx-auto mb-2 opacity-50" />}
                {currentSignal}
              </div>
              <p className="text-sm text-foreground-secondary">
                Confidence: <span className="font-bold text-foreground-primary">{(confidence * 100).toFixed(0)}%</span>
              </p>
            </div>
          </div>

          {/* Brain Metrics */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Brain Metrics</h3>
            <div className="space-y-3">
              <MetricRow
                icon={<Zap className="w-4 h-4 text-yellow-500" />}
                label="Neural Strength"
                value={brainMetrics?.neuralStrength ? `${brainMetrics.neuralStrength}%` : '--'}
              />
              <MetricRow
                icon={<Target className="w-4 h-4 text-accent-primary" />}
                label="Pattern Match"
                value={brainMetrics?.patternMatch ? `${brainMetrics.patternMatch}%` : '--'}
              />
              <MetricRow
                icon={<Shield className="w-4 h-4 text-bullish" />}
                label="Risk Score"
                value={brainMetrics?.riskScore || '--'}
                valueColor={brainMetrics?.riskScore === 'Low' ? 'text-bullish' : brainMetrics?.riskScore === 'High' ? 'text-bearish' : 'text-warning'}
              />
              <MetricRow
                icon={<Activity className="w-4 h-4 text-purple-500" />}
                label="Market Regime"
                value={brainMetrics?.regime || '--'}
              />
            </div>
          </div>

          {/* Risk Parameters */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Risk Parameters</h3>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between">
                <span className="text-foreground-muted">Max Position Size</span>
                <span className="font-mono text-foreground-primary">2 contracts</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Daily Loss Limit</span>
                <span className="font-mono text-bearish">$500</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Max Drawdown</span>
                <span className="font-mono text-foreground-primary">5%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Trailing Stop</span>
                <span className="font-mono text-foreground-primary">8 ticks</span>
              </div>
            </div>
          </div>

          {/* Performance Today */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Today's Performance</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="text-center p-2 bg-background-secondary rounded">
                <p className="text-xs text-foreground-muted">Trades</p>
                <p className="text-lg font-bold text-foreground-primary">{todayPerf?.trades ?? '--'}</p>
              </div>
              <div className="text-center p-2 bg-background-secondary rounded">
                <p className="text-xs text-foreground-muted">Win Rate</p>
                <p className={cn('text-lg font-bold', (todayPerf?.winRate ?? 0) >= 50 ? 'text-bullish' : 'text-bearish')}>
                  {todayPerf?.winRate != null ? `${todayPerf.winRate.toFixed(1)}%` : '--'}
                </p>
              </div>
              <div className="text-center p-2 bg-background-secondary rounded">
                <p className="text-xs text-foreground-muted">P&L</p>
                <p className={cn('text-lg font-bold', (todayPerf?.pnl ?? 0) >= 0 ? 'text-bullish' : 'text-bearish')}>
                  {todayPerf?.pnl != null ? `${todayPerf.pnl >= 0 ? '+' : ''}$${todayPerf.pnl.toFixed(0)}` : '--'}
                </p>
              </div>
              <div className="text-center p-2 bg-background-secondary rounded">
                <p className="text-xs text-foreground-muted">Sharpe</p>
                <p className="text-lg font-bold text-foreground-primary">
                  {todayPerf?.sharpe != null ? todayPerf.sharpe.toFixed(2) : '--'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

interface MetricRowProps {
  icon: React.ReactNode
  label: string
  value: string
  valueColor?: string
}

function MetricRow({ icon, label, value, valueColor = 'text-foreground-primary' }: MetricRowProps) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-xs text-foreground-muted">{label}</span>
      </div>
      <span className={cn('text-sm font-bold', valueColor)}>{value}</span>
    </div>
  )
}
