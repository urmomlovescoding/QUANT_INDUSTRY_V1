/**
 * UnifiedBrain - AI Trading System Dashboard
 * Connected to real backend Brain V6 APIs
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Brain,
  Zap,
  Activity,
  Target,
  TrendingUp,
  TrendingDown,
  Layers,
  GitBranch,
  Cpu,
  BarChart3,
  RefreshCw,
  Play,
  Pause,
  AlertTriangle,
  CheckCircle,
  Loader2,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { brainApi, neuralApi } from '@/api/client'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts'

// ============== TYPES ==============

interface BrainStatus {
  available: boolean
  device?: string
  is_trained?: boolean
  current_regime?: string
  auto_train_enabled?: boolean
  training_step?: number
  total_trades?: number
  error?: string
  metrics?: {
    win_rate: number
    total_pnl: number
    profit_factor: number
  }
  strategies?: Array<{
    name: string
    weight: number
    win_rate: number
  }>
}

interface ModuleStatus {
  available: boolean
  trained?: boolean
  device?: string
  error?: string
  models?: Record<string, boolean>
  algorithm?: string
}

interface SignalData {
  symbol: string
  direction: string
  confidence: number
  strategy?: string
  entry_price?: number
  stop_loss?: number
  take_profit?: number
}

// ============== API FUNCTIONS ==============

const fetchBrainStatus = async (): Promise<BrainStatus> => {
  const response = await brainApi.getStatus()
  if (response.ok && response.data) {
    return response.data as BrainStatus
  }
  throw new Error(response.error?.message || 'Failed to fetch brain status')
}

const fetchModules = async () => {
  const [beast, rl, dl, evolution] = await Promise.all([
    fetch('/api/beast/status').then(r => r.json()).catch(() => ({ available: false })),
    fetch('/api/rl/status').then(r => r.json()).catch(() => ({ available: false })),
    fetch('/api/dl/status').then(r => r.json()).catch(() => ({ available: false })),
    fetch('/api/evolution/status').then(r => r.json()).catch(() => ({ available: false })),
  ])
  return { beast, rl, dl, evolution }
}

const fetchSignal = async (symbol: string): Promise<SignalData | null> => {
  try {
    const response = await fetch(`/api/brain-v6/signal/${symbol}`)
    if (response.ok) {
      return await response.json()
    }
    return null
  } catch {
    return null
  }
}

const fetchRegime = async () => {
  const response = await neuralApi.getRegime()
  if (response.ok && response.data) {
    return response.data
  }
  return null
}

// ============== COMPONENT ==============

export function UnifiedBrain() {
  const queryClient = useQueryClient()
  const [isAutoRefresh, setIsAutoRefresh] = useState(true)
  const [selectedSymbol, setSelectedSymbol] = useState('SPY')
  const watchlist = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA']

  // Fetch brain status
  const { data: brainStatus, isLoading: brainLoading, error: brainError } = useQuery({
    queryKey: ['brain-v6-status'],
    queryFn: fetchBrainStatus,
    refetchInterval: isAutoRefresh ? 5000 : false,
    retry: 2,
  })

  // Fetch module status
  const { data: modules } = useQuery({
    queryKey: ['brain-modules'],
    queryFn: fetchModules,
    refetchInterval: isAutoRefresh ? 10000 : false,
  })

  // Fetch regime
  const { data: regime } = useQuery({
    queryKey: ['market-regime'],
    queryFn: fetchRegime,
    refetchInterval: isAutoRefresh ? 30000 : false,
  })

  // Fetch signal for selected symbol
  const { data: currentSignal, isLoading: signalLoading } = useQuery({
    queryKey: ['brain-signal', selectedSymbol],
    queryFn: () => fetchSignal(selectedSymbol),
    refetchInterval: isAutoRefresh ? 10000 : false,
    enabled: !!selectedSymbol,
  })

  // Train mutation
  const trainMutation = useMutation({
    mutationFn: () => brainApi.train(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brain-v6-status'] })
    },
  })

  const isAvailable = brainStatus?.available ?? false
  const strategies = brainStatus?.strategies || []
  const metrics = brainStatus?.metrics || { win_rate: 0, total_pnl: 0, profit_factor: 0 }

  // Calculate module counts
  const moduleCount = {
    total: 4,
    active: [modules?.beast, modules?.rl, modules?.dl, modules?.evolution]
      .filter(m => m?.available).length
  }

  // Radar data for module performance
  const radarData = [
    { module: 'ML', value: modules?.beast?.available ? 85 : 0 },
    { module: 'RL', value: modules?.rl?.available ? 78 : 0 },
    { module: 'DL', value: modules?.dl?.available ? 82 : 0 },
    { module: 'Evo', value: modules?.evolution?.available ? 70 : 0 },
    { module: 'Neural', value: isAvailable ? 88 : 0 },
  ]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-cyan-500/20">
            <Brain className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-cyan-400 bg-clip-text text-transparent">
              UNIFIED BRAIN V6
            </h1>
            <p className="text-xs text-foreground-muted">
              {moduleCount.active}/{moduleCount.total} Modules Active | Real-Time AI Trading System
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Connection Status */}
          <div className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium',
            isAvailable
              ? 'bg-bullish/20 text-bullish'
              : 'bg-bearish/20 text-bearish'
          )}>
            {isAvailable ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {isAvailable ? 'CONNECTED' : 'OFFLINE'}
          </div>

          {/* Auto Refresh Toggle */}
          <button
            onClick={() => setIsAutoRefresh(!isAutoRefresh)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all',
              isAutoRefresh
                ? 'bg-bullish/20 text-bullish border border-bullish/30'
                : 'bg-background-tertiary text-foreground-secondary hover:bg-background-secondary'
            )}
          >
            {isAutoRefresh ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {isAutoRefresh ? 'LIVE' : 'PAUSED'}
          </button>

          {/* Train Button */}
          <button
            onClick={() => trainMutation.mutate()}
            disabled={!isAvailable || trainMutation.isPending}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all',
              'bg-accent-primary/20 text-accent-primary border border-accent-primary/30',
              'hover:bg-accent-primary/30 disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {trainMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            TRAIN
          </button>
        </div>
      </div>

      {/* Error State */}
      {brainError && (
        <div className="p-4 rounded-xl bg-bearish/10 border border-bearish/20 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-bearish" />
          <div>
            <p className="text-sm font-medium text-bearish">Brain Connection Error</p>
            <p className="text-xs text-foreground-muted">{(brainError as Error).message}</p>
          </div>
        </div>
      )}

      {/* Loading State */}
      {brainLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-accent-primary animate-spin" />
        </div>
      )}

      {/* Main Content */}
      {!brainLoading && (
        <div className="grid grid-cols-12 gap-4">
          {/* Left: Stats & Modules */}
          <div className="col-span-4 space-y-4">
            {/* Brain Status Card */}
            <div className="bg-background-secondary rounded-xl border border-border p-4">
              <h3 className="text-sm font-semibold text-foreground-primary mb-3 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-purple-400" />
                Brain Status
              </h3>

              <div className="space-y-3">
                <StatusRow label="Device" value={brainStatus?.device || 'CPU'} />
                <StatusRow label="Trained" value={brainStatus?.is_trained ? 'Yes' : 'No'} positive={brainStatus?.is_trained} />
                <StatusRow label="Training Step" value={brainStatus?.training_step?.toString() || '0'} />
                <StatusRow label="Total Trades" value={brainStatus?.total_trades?.toString() || '0'} />
                <StatusRow label="Auto-Train" value={brainStatus?.auto_train_enabled ? 'Enabled' : 'Disabled'} positive={brainStatus?.auto_train_enabled} />
              </div>
            </div>

            {/* Performance Metrics */}
            <div className="bg-background-secondary rounded-xl border border-border p-4">
              <h3 className="text-sm font-semibold text-foreground-primary mb-3 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-cyan-400" />
                Performance Metrics
              </h3>

              <div className="grid grid-cols-3 gap-3">
                <MetricCard
                  label="Win Rate"
                  value={`${(metrics.win_rate * 100).toFixed(1)}%`}
                  icon={<Target className="w-4 h-4" />}
                  color={metrics.win_rate > 0.5 ? 'bullish' : 'bearish'}
                />
                <MetricCard
                  label="Total P&L"
                  value={`$${metrics.total_pnl.toLocaleString()}`}
                  icon={<TrendingUp className="w-4 h-4" />}
                  color={metrics.total_pnl > 0 ? 'bullish' : 'bearish'}
                />
                <MetricCard
                  label="Profit Factor"
                  value={metrics.profit_factor.toFixed(2)}
                  icon={<Activity className="w-4 h-4" />}
                  color={metrics.profit_factor > 1 ? 'bullish' : 'bearish'}
                />
              </div>
            </div>

            {/* Module Status */}
            <div className="bg-background-secondary rounded-xl border border-border p-4">
              <h3 className="text-sm font-semibold text-foreground-primary mb-3 flex items-center gap-2">
                <Layers className="w-4 h-4 text-yellow-400" />
                AI Modules
              </h3>

              <div className="space-y-2">
                <ModuleRow name="BEAST ML" icon={Brain} status={modules?.beast} color="purple" />
                <ModuleRow name="Reinforcement Learning" icon={GitBranch} status={modules?.rl} color="blue" />
                <ModuleRow name="Deep Learning" icon={Layers} status={modules?.dl} color="cyan" />
                <ModuleRow name="Evolution Engine" icon={Zap} status={modules?.evolution} color="yellow" />
              </div>
            </div>
          </div>

          {/* Center: Signal Generation */}
          <div className="col-span-5 space-y-4">
            {/* Symbol Selector */}
            <div className="bg-background-secondary rounded-xl border border-border p-4">
              <h3 className="text-sm font-semibold text-foreground-primary mb-3 flex items-center gap-2">
                <Target className="w-4 h-4 text-accent-primary" />
                Signal Generator
              </h3>

              <div className="flex gap-2 mb-4">
                {watchlist.map(symbol => (
                  <button
                    key={symbol}
                    onClick={() => setSelectedSymbol(symbol)}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                      selectedSymbol === symbol
                        ? 'bg-accent-primary text-black'
                        : 'bg-background-tertiary text-foreground-secondary hover:bg-background-hover'
                    )}
                  >
                    {symbol}
                  </button>
                ))}
              </div>

              {/* Current Signal */}
              <div className={cn(
                'p-4 rounded-xl border',
                currentSignal?.direction === 'LONG' ? 'bg-bullish/10 border-bullish/30' :
                currentSignal?.direction === 'SHORT' ? 'bg-bearish/10 border-bearish/30' :
                'bg-background-tertiary border-border'
              )}>
                {signalLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="w-6 h-6 animate-spin text-foreground-muted" />
                  </div>
                ) : currentSignal ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-bold text-foreground-primary">{currentSignal.symbol}</span>
                      <span className={cn(
                        'px-3 py-1 rounded-lg text-sm font-bold',
                        currentSignal.direction === 'LONG' ? 'bg-bullish text-black' :
                        currentSignal.direction === 'SHORT' ? 'bg-bearish text-white' :
                        'bg-warning text-black'
                      )}>
                        {currentSignal.direction || 'NEUTRAL'}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <span className="text-foreground-muted">Confidence</span>
                        <p className="font-semibold text-foreground-primary">
                          {((currentSignal.confidence || 0) * 100).toFixed(1)}%
                        </p>
                      </div>
                      <div>
                        <span className="text-foreground-muted">Strategy</span>
                        <p className="font-semibold text-foreground-primary">
                          {currentSignal.strategy || 'Ensemble'}
                        </p>
                      </div>
                      {currentSignal.entry_price && (
                        <div>
                          <span className="text-foreground-muted">Entry</span>
                          <p className="font-semibold text-foreground-primary">
                            ${currentSignal.entry_price.toFixed(2)}
                          </p>
                        </div>
                      )}
                      {currentSignal.stop_loss && (
                        <div>
                          <span className="text-foreground-muted">Stop Loss</span>
                          <p className="font-semibold text-bearish">
                            ${currentSignal.stop_loss.toFixed(2)}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <p className="text-foreground-muted">No signal available for {selectedSymbol}</p>
                    <p className="text-xs text-foreground-muted mt-1">Brain may need training or market data</p>
                  </div>
                )}
              </div>
            </div>

            {/* Strategy Ensemble */}
            <div className="bg-background-secondary rounded-xl border border-border p-4">
              <h3 className="text-sm font-semibold text-foreground-primary mb-3 flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-blue-400" />
                Strategy Ensemble ({strategies.length})
              </h3>

              {strategies.length > 0 ? (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {strategies.map((strategy, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between p-2 rounded-lg bg-background-tertiary"
                    >
                      <span className="text-sm font-medium text-foreground-primary">{strategy.name}</span>
                      <div className="flex items-center gap-3 text-xs">
                        <span className="text-foreground-muted">
                          W: {(strategy.win_rate * 100).toFixed(0)}%
                        </span>
                        <span className={cn(
                          'px-2 py-0.5 rounded font-semibold',
                          strategy.weight > 5 ? 'bg-accent-primary/20 text-accent-primary' : 'bg-background-secondary text-foreground-muted'
                        )}>
                          {strategy.weight.toFixed(1)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-foreground-muted text-center py-4">
                  No strategies loaded. Train the brain to generate strategies.
                </p>
              )}
            </div>
          </div>

          {/* Right: Regime & Radar */}
          <div className="col-span-3 space-y-4">
            {/* Market Regime */}
            <div className="bg-background-secondary rounded-xl border border-border p-4">
              <h3 className="text-sm font-semibold text-foreground-primary mb-3 flex items-center gap-2">
                <Activity className="w-4 h-4 text-teal-400" />
                Market Regime
              </h3>

              <div className={cn(
                'p-3 rounded-lg text-center',
                regime?.regime === 'trending' ? 'bg-bullish/20' :
                regime?.regime === 'volatile' ? 'bg-bearish/20' :
                regime?.regime === 'ranging' ? 'bg-warning/20' :
                'bg-background-tertiary'
              )}>
                <p className="text-lg font-bold text-foreground-primary uppercase">
                  {regime?.regime || brainStatus?.current_regime || 'Unknown'}
                </p>
                <p className="text-xs text-foreground-muted mt-1">
                  Confidence: {((regime?.confidence || 0) * 100).toFixed(0)}%
                </p>
              </div>

              {regime?.recommended_strategies && (
                <div className="mt-3">
                  <p className="text-xs text-foreground-muted mb-2">Recommended:</p>
                  <div className="flex flex-wrap gap-1">
                    {regime.recommended_strategies.slice(0, 3).map((s: string, i: number) => (
                      <span key={i} className="px-2 py-0.5 rounded bg-background-tertiary text-xs text-foreground-secondary">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Module Radar */}
            <div className="bg-background-secondary rounded-xl border border-border p-4">
              <h3 className="text-sm font-semibold text-foreground-primary mb-3">
                Module Performance
              </h3>

              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#333" />
                    <PolarAngleAxis dataKey="module" tick={{ fill: '#888', fontSize: 10 }} />
                    <PolarRadiusAxis tick={{ fill: '#666', fontSize: 8 }} domain={[0, 100]} />
                    <Radar
                      name="Performance"
                      dataKey="value"
                      stroke="#8b5cf6"
                      fill="#8b5cf6"
                      fillOpacity={0.3}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ============== SUB-COMPONENTS ==============

function StatusRow({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-foreground-muted">{label}</span>
      <span className={cn(
        'font-medium',
        positive === true ? 'text-bullish' :
        positive === false ? 'text-foreground-secondary' :
        'text-foreground-primary'
      )}>
        {value}
      </span>
    </div>
  )
}

function MetricCard({ label, value, icon, color }: { label: string; value: string; icon: React.ReactNode; color: string }) {
  return (
    <div className={cn(
      'p-3 rounded-lg',
      color === 'bullish' ? 'bg-bullish/10' :
      color === 'bearish' ? 'bg-bearish/10' :
      'bg-background-tertiary'
    )}>
      <div className={cn(
        'mb-1',
        color === 'bullish' ? 'text-bullish' :
        color === 'bearish' ? 'text-bearish' :
        'text-foreground-muted'
      )}>
        {icon}
      </div>
      <p className="text-lg font-bold text-foreground-primary">{value}</p>
      <p className="text-[10px] text-foreground-muted">{label}</p>
    </div>
  )
}

function ModuleRow({ name, icon: Icon, status, color }: {
  name: string
  icon: any
  status?: ModuleStatus
  color: string
}) {
  const isAvailable = status?.available ?? false

  return (
    <div className="flex items-center justify-between p-2 rounded-lg bg-background-tertiary">
      <div className="flex items-center gap-2">
        <Icon className={cn('w-4 h-4', `text-${color}-400`)} />
        <span className="text-sm font-medium text-foreground-primary">{name}</span>
      </div>
      <div className="flex items-center gap-2">
        {isAvailable ? (
          <CheckCircle className="w-4 h-4 text-bullish" />
        ) : (
          <AlertTriangle className="w-4 h-4 text-foreground-muted" />
        )}
        <span className={cn(
          'text-xs font-medium',
          isAvailable ? 'text-bullish' : 'text-foreground-muted'
        )}>
          {isAvailable ? 'Active' : 'Inactive'}
        </span>
      </div>
    </div>
  )
}

export default UnifiedBrain
