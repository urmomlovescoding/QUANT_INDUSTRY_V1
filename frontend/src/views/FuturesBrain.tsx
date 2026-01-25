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

// Generate mock price data
const generatePriceData = (basePrice: number, count: number) => {
  const data = []
  let price = basePrice
  for (let i = 0; i < count; i++) {
    price = price + (Math.random() - 0.48) * basePrice * 0.001
    data.push({
      time: new Date(Date.now() - (count - i) * 60000).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
      price: price,
      volume: Math.floor(Math.random() * 1000) + 500,
    })
  }
  return data
}

// Generate signal history
const generateSignals = () => {
  const signals = []
  const types = ['LONG', 'SHORT', 'FLAT'] as const
  for (let i = 0; i < 10; i++) {
    const type = types[Math.floor(Math.random() * types.length)]
    signals.push({
      time: new Date(Date.now() - i * 300000).toLocaleTimeString('en-US', { hour12: false }),
      type,
      confidence: 0.65 + Math.random() * 0.3,
      target: type !== 'FLAT' ? (Math.random() * 20).toFixed(2) : null,
      stop: type !== 'FLAT' ? (Math.random() * 10).toFixed(2) : null,
    })
  }
  return signals.reverse()
}

export function FuturesBrain() {
  const [selectedContract, setSelectedContract] = useState(FUTURES_CONTRACTS[0])
  const [priceData, setPriceData] = useState(() => generatePriceData(5800, 60))
  const [signals, setSignals] = useState(() => generateSignals())
  const [isRunning, setIsRunning] = useState(false)
  const [brainStatus, setBrainStatus] = useState<'IDLE' | 'ANALYZING' | 'READY'>('IDLE')
  const [currentSignal, setCurrentSignal] = useState<'LONG' | 'SHORT' | 'FLAT'>('FLAT')
  const [confidence, setConfidence] = useState(0.72)

  // Simulated real-time updates
  useEffect(() => {
    if (!isRunning) return

    const interval = setInterval(() => {
      setBrainStatus('ANALYZING')

      setTimeout(() => {
        setPriceData(prev => {
          const lastPrice = prev[prev.length - 1].price
          const newPrice = lastPrice + (Math.random() - 0.48) * lastPrice * 0.0005
          return [
            ...prev.slice(1),
            {
              time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
              price: newPrice,
              volume: Math.floor(Math.random() * 1000) + 500,
            }
          ]
        })

        // Random signal change
        if (Math.random() > 0.85) {
          const types = ['LONG', 'SHORT', 'FLAT'] as const
          const newSignal = types[Math.floor(Math.random() * types.length)]
          setCurrentSignal(newSignal)
          setConfidence(0.65 + Math.random() * 0.3)
          setSignals(prev => [
            ...prev.slice(1),
            {
              time: new Date().toLocaleTimeString('en-US', { hour12: false }),
              type: newSignal,
              confidence: 0.65 + Math.random() * 0.3,
              target: newSignal !== 'FLAT' ? (Math.random() * 20).toFixed(2) : null,
              stop: newSignal !== 'FLAT' ? (Math.random() * 10).toFixed(2) : null,
            }
          ])
        }

        setBrainStatus('READY')
      }, 500)
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
                value="87%"
              />
              <MetricRow
                icon={<Target className="w-4 h-4 text-accent-primary" />}
                label="Pattern Match"
                value="94%"
              />
              <MetricRow
                icon={<Shield className="w-4 h-4 text-bullish" />}
                label="Risk Score"
                value="Low"
                valueColor="text-bullish"
              />
              <MetricRow
                icon={<Activity className="w-4 h-4 text-purple-500" />}
                label="Market Regime"
                value="Trending"
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
                <p className="text-lg font-bold text-foreground-primary">12</p>
              </div>
              <div className="text-center p-2 bg-background-secondary rounded">
                <p className="text-xs text-foreground-muted">Win Rate</p>
                <p className="text-lg font-bold text-bullish">67%</p>
              </div>
              <div className="text-center p-2 bg-background-secondary rounded">
                <p className="text-xs text-foreground-muted">P&L</p>
                <p className="text-lg font-bold text-bullish">+$847</p>
              </div>
              <div className="text-center p-2 bg-background-secondary rounded">
                <p className="text-xs text-foreground-muted">Sharpe</p>
                <p className="text-lg font-bold text-foreground-primary">1.82</p>
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
