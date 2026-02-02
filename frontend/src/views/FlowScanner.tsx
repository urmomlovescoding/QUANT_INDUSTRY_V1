import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Waves,
  TrendingUp,
  TrendingDown,
  Activity,
  RefreshCw,
  Zap,
  Wifi,
  WifiOff,
  Bell,
  BellOff,
  Filter,
  Download,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  AreaChart,
  Area,
} from 'recharts'
import { useWebSocket } from '@/hooks/useWebSocket'

// Flow update type from WebSocket
interface FlowUpdate {
  id: string
  symbol: string
  type: 'CALL' | 'PUT'
  side: 'BUY' | 'SELL'
  sentiment: 'BULLISH' | 'BEARISH'
  strike: number
  expiry: string
  premium: number
  contracts: number
  is_unusual: boolean
  is_sweep: boolean
  timestamp: string
}
import { useNotifications } from '@/components/NotificationSystem'

// Types
interface Flow {
  id: string | number
  time: string
  symbol: string
  type: 'CALL' | 'PUT'
  side: 'BUY' | 'SELL'
  sentiment: 'BULLISH' | 'BEARISH'
  strike: number
  expiry: string
  premium: number
  contracts: number
  openInterest?: number
  volume?: number
  isUnusual: boolean
  isSweep: boolean
}

interface SymbolFlow {
  symbol: string
  bullish: number
  bearish: number
  net: number
}

// Fetch initial flow data from API
const fetchInitialFlows = async (): Promise<Flow[]> => {
  try {
    const response = await fetch('/api/options/flow')
    if (!response.ok) return []
    const data = await response.json()

    if (data.status === 'unavailable') return []

    // Handle both array response and nested response formats
    const flowData = Array.isArray(data) ? data : (data.data?.flows || data.flows || [])
    return flowData.map((f: any, i: number) => {
      // Map sentiment - neutral becomes based on option type (call=bullish, put=bearish)
      let sentiment = (f.sentiment || 'bullish').toUpperCase()
      if (sentiment === 'NEUTRAL') {
        sentiment = (f.type || 'call').toUpperCase() === 'CALL' ? 'BULLISH' : 'BEARISH'
      }

      return {
        id: f.id || `flow_${i}`,
        time: f.time || new Date(f.timestamp || Date.now()).toLocaleTimeString('en-US', { hour12: false }),
        symbol: f.symbol,
        type: (f.type || f.option_type || 'call').toUpperCase() === 'CALL' ? 'CALL' : 'PUT',
        side: (f.side || 'buy').toUpperCase() as 'BUY' | 'SELL',
        sentiment: sentiment as 'BULLISH' | 'BEARISH',
        strike: f.strike || 0,
        expiry: f.expiry || f.expiration || 'N/A',
        premium: f.premium || f.total_value || 0,
        contracts: f.contracts || f.volume || 0,
        openInterest: f.open_interest || f.openInterest || 0,
        volume: f.volume || 0,
        isUnusual: f.is_unusual || f.isUnusual || f.premium > 200000,
        isSweep: f.is_sweep || f.isSweep || false,
      }
    })
  } catch {
    return []
  }
}

export function FlowScanner() {
  const [flows, setFlows] = useState<Flow[]>([])
  const [filter, setFilter] = useState<'ALL' | 'BULLISH' | 'BEARISH' | 'UNUSUAL' | 'SWEEPS'>('ALL')

  // Fetch initial flows on mount
  useEffect(() => {
    fetchInitialFlows().then(initialFlows => {
      if (initialFlows.length > 0) {
        setFlows(initialFlows)
      }
    })
  }, [])
  const [alertsEnabled, setAlertsEnabled] = useState(true)
  const [flowHistory, setFlowHistory] = useState<{ time: string; bullish: number; bearish: number }[]>([])

  // WebSocket connection
  const { isConnected, lastMessage, subscribe } = useWebSocket({
    autoConnect: true,
  })

  // Notifications
  const { addNotification } = useNotifications()

  // Subscribe to flow channel when connected
  useEffect(() => {
    if (isConnected) {
      subscribe('alerts')
    }
  }, [isConnected, subscribe])

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (lastMessage?.channel === 'alerts' && lastMessage.type === 'data') {
      const wsFlow = lastMessage.data as FlowUpdate

      const newFlow: Flow = {
        id: wsFlow.id,
        time: new Date(wsFlow.timestamp).toLocaleTimeString('en-US', { hour12: false }),
        symbol: wsFlow.symbol,
        type: wsFlow.type,
        side: wsFlow.side,
        sentiment: wsFlow.sentiment,
        strike: wsFlow.strike,
        expiry: wsFlow.expiry,
        premium: wsFlow.premium,
        contracts: wsFlow.contracts,
        isUnusual: wsFlow.is_unusual,
        isSweep: wsFlow.is_sweep,
      }

      setFlows(prev => [newFlow, ...prev.slice(0, 99)])

      // Send notification for unusual activity
      if (alertsEnabled && newFlow.isUnusual) {
        addNotification({
          type: 'signal',
          priority: newFlow.premium > 300000 ? 'high' : 'medium',
          title: `Unusual ${newFlow.type} Activity`,
          message: `${newFlow.symbol} ${newFlow.strike}${newFlow.type[0]} ${newFlow.expiry} - $${(newFlow.premium / 1000).toFixed(0)}K ${newFlow.sentiment}`,
          data: newFlow,
          action: {
            label: 'View Flow',
            onClick: () => setFilter('UNUSUAL')
          }
        })
      }
    }
  }, [lastMessage, alertsEnabled, addNotification])

  // Calculate symbol flow aggregates
  const symbolFlow = useMemo<SymbolFlow[]>(() => {
    const aggregates: Record<string, { bullish: number; bearish: number }> = {}

    flows.forEach(flow => {
      if (!aggregates[flow.symbol]) {
        aggregates[flow.symbol] = { bullish: 0, bearish: 0 }
      }
      if (flow.sentiment === 'BULLISH') {
        aggregates[flow.symbol].bullish += flow.premium
      } else {
        aggregates[flow.symbol].bearish += flow.premium
      }
    })

    return Object.entries(aggregates)
      .map(([symbol, data]) => ({
        symbol,
        bullish: data.bullish,
        bearish: -data.bearish,
        net: data.bullish - data.bearish
      }))
      .sort((a, b) => Math.abs(b.net) - Math.abs(a.net))
      .slice(0, 8)
  }, [flows])

  // Update flow history for mini chart
  useEffect(() => {
    const interval = setInterval(() => {
      const bullish = flows.filter(f => f.sentiment === 'BULLISH').slice(0, 10).reduce((sum, f) => sum + f.premium, 0)
      const bearish = flows.filter(f => f.sentiment === 'BEARISH').slice(0, 10).reduce((sum, f) => sum + f.premium, 0)

      setFlowHistory(prev => [
        ...prev.slice(-29),
        {
          time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
          bullish: bullish / 1000000,
          bearish: bearish / 1000000
        }
      ])
    }, 5000)

    return () => clearInterval(interval)
  }, [flows])

  // Filtered flows
  const filteredFlows = useMemo(() => {
    return flows.filter(flow => {
      if (filter === 'ALL') return true
      if (filter === 'BULLISH') return flow.sentiment === 'BULLISH'
      if (filter === 'BEARISH') return flow.sentiment === 'BEARISH'
      if (filter === 'UNUSUAL') return flow.isUnusual
      if (filter === 'SWEEPS') return flow.isSweep
      return true
    })
  }, [flows, filter])

  // Statistics
  const stats = useMemo(() => {
    const totalBullish = flows.filter(f => f.sentiment === 'BULLISH').reduce((sum, f) => sum + f.premium, 0)
    const totalBearish = flows.filter(f => f.sentiment === 'BEARISH').reduce((sum, f) => sum + f.premium, 0)
    const totalUnusual = flows.filter(f => f.isUnusual).length
    const totalSweeps = flows.filter(f => f.isSweep).length

    return {
      totalBullish,
      totalBearish,
      totalUnusual,
      totalSweeps,
      netSentiment: totalBullish > totalBearish ? 'BULLISH' : 'BEARISH',
      ratio: totalBearish > 0 ? (totalBullish / totalBearish).toFixed(2) : '∞'
    }
  }, [flows])

  // Export data
  const handleExport = useCallback(() => {
    const csv = [
      ['Time', 'Symbol', 'Type', 'Side', 'Sentiment', 'Strike', 'Expiry', 'Premium', 'Contracts', 'Unusual', 'Sweep'],
      ...flows.map(f => [
        f.time, f.symbol, f.type, f.side, f.sentiment, f.strike, f.expiry, f.premium, f.contracts, f.isUnusual, f.isSweep
      ])
    ].map(row => row.join(',')).join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `flow_data_${new Date().toISOString().split('T')[0]}.csv`
    a.click()
  }, [flows])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Waves className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary flex items-center gap-2">
              FLOW SCANNER
              {isConnected ? (
                <span className="flex items-center gap-1 px-2 py-0.5 bg-bullish/20 text-bullish text-xs rounded">
                  <Wifi className="w-3 h-3" />
                  LIVE
                </span>
              ) : (
                <span className="flex items-center gap-1 px-2 py-0.5 bg-foreground-muted/20 text-foreground-muted text-xs rounded">
                  <WifiOff className="w-3 h-3" />
                  OFFLINE
                </span>
              )}
            </h1>
            <p className="text-xs text-foreground-muted">Real-time smart money options flow</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Filter */}
          <div className="flex gap-1">
            {(['ALL', 'BULLISH', 'BEARISH', 'UNUSUAL', 'SWEEPS'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  'px-3 py-1 text-xs font-medium rounded transition-colors',
                  filter === f
                    ? f === 'BULLISH' ? 'bg-bullish/20 text-bullish'
                    : f === 'BEARISH' ? 'bg-bearish/20 text-bearish'
                    : f === 'UNUSUAL' ? 'bg-yellow-500/20 text-yellow-500'
                    : f === 'SWEEPS' ? 'bg-purple-500/20 text-purple-500'
                    : 'bg-accent-primary/20 text-accent-primary'
                    : 'bg-background-tertiary text-foreground-muted hover:text-foreground-secondary'
                )}
              >
                {f}
              </button>
            ))}
          </div>

          {/* Alert Toggle */}
          <button
            onClick={() => setAlertsEnabled(!alertsEnabled)}
            className={cn(
              'p-2 rounded-lg transition-colors',
              alertsEnabled ? 'bg-accent-primary/20 text-accent-primary' : 'bg-background-tertiary text-foreground-muted'
            )}
            title={alertsEnabled ? 'Alerts On' : 'Alerts Off'}
          >
            {alertsEnabled ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
          </button>

          {/* Export */}
          <button
            onClick={handleExport}
            className="p-2 rounded-lg bg-background-tertiary text-foreground-muted hover:text-foreground-secondary transition-colors"
            title="Export CSV"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          icon={<TrendingUp className="w-5 h-5 text-bullish" />}
          label="Bullish Flow"
          value={`$${(stats.totalBullish / 1000000).toFixed(2)}M`}
          color="bullish"
        />
        <StatCard
          icon={<TrendingDown className="w-5 h-5 text-bearish" />}
          label="Bearish Flow"
          value={`$${(stats.totalBearish / 1000000).toFixed(2)}M`}
          color="bearish"
        />
        <StatCard
          icon={<Zap className="w-5 h-5 text-yellow-500" />}
          label="Unusual Activity"
          value={stats.totalUnusual.toString()}
          color="yellow"
        />
        <StatCard
          icon={<Activity className="w-5 h-5 text-purple-500" />}
          label="Sweeps Detected"
          value={stats.totalSweeps.toString()}
          color="purple"
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Flow Table */}
        <div className="col-span-8 card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-foreground-primary">Live Options Flow</h3>
            <span className="text-xs text-foreground-muted">{filteredFlows.length} flows</span>
          </div>
          <div className="overflow-auto max-h-[500px]">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-background-secondary z-10">
                <tr className="text-foreground-muted border-b border-border">
                  <th className="text-left py-2 px-2">Time</th>
                  <th className="text-left py-2 px-2">Symbol</th>
                  <th className="text-left py-2 px-2">Type</th>
                  <th className="text-left py-2 px-2">Side</th>
                  <th className="text-right py-2 px-2">Strike</th>
                  <th className="text-right py-2 px-2">Expiry</th>
                  <th className="text-right py-2 px-2">Premium</th>
                  <th className="text-right py-2 px-2">Contracts</th>
                  <th className="text-center py-2 px-2">Flags</th>
                </tr>
              </thead>
              <tbody>
                {filteredFlows.slice(0, 40).map((flow, i) => (
                  <tr
                    key={flow.id}
                    className={cn(
                      'border-b border-border/50 transition-colors hover:bg-background-tertiary/50',
                      flow.isUnusual && 'bg-yellow-500/5',
                      i === 0 && isConnected && 'animate-pulse'
                    )}
                  >
                    <td className="py-2 px-2 text-foreground-muted font-mono">{flow.time}</td>
                    <td className="py-2 px-2 font-bold text-accent-primary">{flow.symbol}</td>
                    <td className="py-2 px-2">
                      <span className={cn(
                        'px-1.5 py-0.5 rounded text-[10px] font-bold',
                        flow.type === 'CALL' ? 'bg-bullish/20 text-bullish' : 'bg-bearish/20 text-bearish'
                      )}>
                        {flow.type}
                      </span>
                    </td>
                    <td className="py-2 px-2">
                      <span className={cn(
                        'text-[10px] font-medium',
                        flow.sentiment === 'BULLISH' ? 'text-bullish' : 'text-bearish'
                      )}>
                        {flow.side}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-right font-mono text-foreground-primary">${flow.strike}</td>
                    <td className="py-2 px-2 text-right text-foreground-secondary">{flow.expiry}</td>
                    <td className="py-2 px-2 text-right font-mono font-bold text-foreground-primary">
                      ${(flow.premium / 1000).toFixed(0)}K
                    </td>
                    <td className="py-2 px-2 text-right font-mono text-foreground-secondary">
                      {flow.contracts.toLocaleString()}
                    </td>
                    <td className="py-2 px-2 text-center">
                      <div className="flex justify-center gap-1">
                        {flow.isUnusual && (
                          <span className="px-1 py-0.5 rounded text-[8px] font-bold bg-yellow-500/20 text-yellow-500">
                            UOA
                          </span>
                        )}
                        {flow.isSweep && (
                          <span className="px-1 py-0.5 rounded text-[8px] font-bold bg-purple-500/20 text-purple-500">
                            SWEEP
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Panel */}
        <div className="col-span-4 space-y-4">
          {/* Flow Trend Mini Chart */}
          {flowHistory.length > 5 && (
            <div className="card">
              <h3 className="text-sm font-medium text-foreground-primary mb-3">Flow Trend</h3>
              <div className="h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={flowHistory}>
                    <defs>
                      <linearGradient id="bullishGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00c853" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#00c853" stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="bearishGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ff5252" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#ff5252" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" hide />
                    <YAxis hide />
                    <Tooltip
                      contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: '8px' }}
                      formatter={(value: number) => [`$${value.toFixed(2)}M`]}
                    />
                    <Area type="monotone" dataKey="bullish" stroke="#00c853" fill="url(#bullishGrad)" />
                    <Area type="monotone" dataKey="bearish" stroke="#ff5252" fill="url(#bearishGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Net Flow by Symbol */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Net Flow by Symbol</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={symbolFlow} layout="vertical">
                  <XAxis
                    type="number"
                    tick={{ fill: '#666', fontSize: 10 }}
                    axisLine={{ stroke: '#333' }}
                    tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`}
                  />
                  <YAxis
                    dataKey="symbol"
                    type="category"
                    tick={{ fill: '#00d4aa', fontSize: 11, fontWeight: 'bold' }}
                    axisLine={{ stroke: '#333' }}
                    width={45}
                  />
                  <Tooltip
                    contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: '8px' }}
                    formatter={(value: number) => [`$${(Math.abs(value) / 1000000).toFixed(2)}M`, 'Net Flow']}
                  />
                  <Bar dataKey="net" radius={[0, 4, 4, 0]}>
                    {symbolFlow.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.net >= 0 ? '#00c853' : '#ff5252'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Flow Summary */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Flow Analysis</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-xs text-foreground-muted">Net Sentiment</span>
                <span className={cn(
                  'text-sm font-bold',
                  stats.netSentiment === 'BULLISH' ? 'text-bullish' : 'text-bearish'
                )}>
                  {stats.netSentiment}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-foreground-muted">Bull/Bear Ratio</span>
                <span className="text-sm font-mono text-foreground-primary">
                  {stats.ratio}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-foreground-muted">Unusual %</span>
                <span className="text-sm font-mono text-yellow-500">
                  {((stats.totalUnusual / flows.length) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-foreground-muted">Sweep %</span>
                <span className="text-sm font-mono text-purple-500">
                  {((stats.totalSweeps / flows.length) * 100).toFixed(1)}%
                </span>
              </div>

              {/* Sentiment Bar */}
              <div className="pt-2">
                <div className="text-xs text-foreground-muted mb-1">Sentiment Distribution</div>
                <div className="h-2 bg-background-tertiary rounded-full overflow-hidden flex">
                  <div
                    className="bg-bullish"
                    style={{ width: `${(stats.totalBullish / (stats.totalBullish + stats.totalBearish)) * 100}%` }}
                  />
                  <div
                    className="bg-bearish"
                    style={{ width: `${(stats.totalBearish / (stats.totalBullish + stats.totalBearish)) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Top Unusual */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Top Unusual Activity</h3>
            <div className="space-y-2">
              {flows.filter(f => f.isUnusual).slice(0, 5).map((flow) => (
                <div key={flow.id} className="flex items-center justify-between py-1 border-b border-border/50">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-xs text-accent-primary">{flow.symbol}</span>
                    <span className={cn(
                      'text-[10px] px-1 rounded',
                      flow.type === 'CALL' ? 'text-bullish' : 'text-bearish'
                    )}>
                      {flow.type}
                    </span>
                    <span className="text-[10px] text-foreground-muted">${flow.strike}</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-foreground-primary">
                    ${(flow.premium / 1000).toFixed(0)}K
                  </span>
                </div>
              ))}
              {flows.filter(f => f.isUnusual).length === 0 && (
                <div className="text-xs text-foreground-muted text-center py-4">
                  No unusual activity detected
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string
  color: 'bullish' | 'bearish' | 'yellow' | 'purple'
}

function StatCard({ icon, label, value, color }: StatCardProps) {
  const colorClasses = {
    bullish: 'text-bullish',
    bearish: 'text-bearish',
    yellow: 'text-yellow-500',
    purple: 'text-purple-500',
  }

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs text-foreground-muted">{label}</span>
      </div>
      <div className={cn('text-2xl font-bold', colorClasses[color])}>{value}</div>
    </div>
  )
}
