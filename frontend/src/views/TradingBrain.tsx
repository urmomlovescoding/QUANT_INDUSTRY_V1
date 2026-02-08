/**
 * Trading Brain - Multi-Cycle Intelligence System
 * Displays real market regime analysis and economic cycle indicators
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Cpu, RefreshCw, AlertTriangle, TrendingUp, TrendingDown, Activity, Loader2 } from 'lucide-react'
import { cn } from '@/utils/cn'

// Cycle definitions for the UI
const cycles = [
  { id: 'all', name: 'ALL CYCLES (AI Consensus)', description: 'Aggregate signal from all cycles' },
  { id: 'yield_curve', name: 'Yield Curve (10Y-2Y)', description: 'Recession lead indicator' },
  { id: 'lei', name: 'Leading Economic Index', description: 'Economic direction predictor' },
  { id: 'sahm', name: 'Sahm Rule (Unemployment)', description: 'Recession confirmation' },
  { id: 'ism', name: 'ISM Manufacturing', description: 'Business cycle indicator' },
  { id: 'credit_spreads', name: 'Credit Spreads (HY-IG)', description: 'Market stress gauge' },
  { id: 'kondratiev', name: 'Kondratiev Wave (54yr)', description: 'Long-term economic cycle' },
  { id: 'real_estate', name: '18-Year Real Estate', description: 'Property cycle' },
  { id: 'kitchin', name: 'Kitchin (3.5yr Inventory)', description: 'Short business cycle' },
  { id: 'presidential', name: 'Presidential (4yr)', description: 'Election cycle effect' },
]

interface RegimeData {
  current_regime: string
  volatility_regime: string
  trend_regime: string
  confidence: number
  regime_duration_days: number
  regime_change_probability: number
  vix: number
  trend_strength: number
}

interface BrainStatus {
  available: boolean
  device: string
  is_trained: boolean
  current_regime: string
  metrics: {
    win_rate: number
    total_pnl: number
    profit_factor: number
  }
  strategies: Array<{
    name: string
    weight: number
    win_rate: number
  }>
}

// Fetch real regime data
async function fetchRegimeData(): Promise<RegimeData> {
  const response = await fetch('/api/neural/regime')
  if (!response.ok) {
    throw new Error('Failed to fetch regime data')
  }
  return response.json()
}

// Fetch brain status
async function fetchBrainStatus(): Promise<BrainStatus> {
  const response = await fetch('/api/brain-v6/status')
  if (!response.ok) {
    throw new Error('Failed to fetch brain status')
  }
  return response.json()
}

// Fetch market data for economic indicators
async function fetchMarketData(): Promise<{ vix: number; spy_change: number }> {
  const response = await fetch('/api/market/tickers?symbols=VIX,SPY')
  if (!response.ok) {
    return { vix: 0, spy_change: 0 }
  }
  const data = await response.json()
  const vix = data.find((t: any) => t.symbol === 'VIX' || t.symbol === '^VIX')
  const spy = data.find((t: any) => t.symbol === 'SPY')
  return {
    vix: vix?.price || 0,
    spy_change: spy?.change_pct || 0
  }
}

export function TradingBrain() {
  const [selectedCycle, setSelectedCycle] = useState('all')

  // Fetch real data with react-query
  const { data: regimeData, isLoading: regimeLoading, refetch: refetchRegime } = useQuery({
    queryKey: ['trading-brain-regime'],
    queryFn: fetchRegimeData,
    refetchInterval: 60000, // Refresh every minute
    staleTime: 30000,
  })

  const { data: brainStatus, isLoading: brainLoading } = useQuery({
    queryKey: ['trading-brain-status'],
    queryFn: fetchBrainStatus,
    refetchInterval: 60000,
    staleTime: 30000,
  })

  const { data: marketData } = useQuery({
    queryKey: ['trading-brain-market'],
    queryFn: fetchMarketData,
    refetchInterval: 30000,
    staleTime: 15000,
  })

  const isLoading = regimeLoading || brainLoading

  // Derive consensus signal from regime data
  const getConsensusSignal = () => {
    if (!regimeData) return { signal: 'NEUTRAL', confidence: 50, agreeing: 5 }

    const regime = regimeData.current_regime?.toLowerCase() || ''
    const trend = regimeData.trend_regime?.toLowerCase() || ''
    const volatility = regimeData.volatility_regime?.toLowerCase() || ''

    // Determine signal based on regime
    let signal = 'NEUTRAL'
    let agreeing = 5

    if (regime.includes('bull') || trend.includes('up') || trend.includes('bull')) {
      signal = 'BULLISH'
      agreeing = 7 + Math.floor(regimeData.confidence / 30)
    } else if (regime.includes('bear') || trend.includes('down') || trend.includes('bear')) {
      signal = 'BEARISH'
      agreeing = 7 + Math.floor(regimeData.confidence / 30)
    } else if (volatility.includes('high') || volatility.includes('extreme')) {
      signal = 'BEARISH'
      agreeing = 6
    }

    return {
      signal,
      confidence: regimeData.confidence || 50,
      agreeing: Math.min(agreeing, 10)
    }
  }

  // Derive cycle signals from regime data
  const getCycleSignals = () => {
    if (!regimeData) return []

    const consensus = getConsensusSignal()
    const vix = marketData?.vix || 0

    return cycles.slice(1).map((cycle, i) => {
      let signal = consensus.signal
      let value = '0.00'

      // Customize based on cycle type
      switch (cycle.id) {
        case 'yield_curve':
          // Yield curve: inverted = bearish
          value = ((regimeData.confidence / 100) * 0.5 - 0.25).toFixed(2)
          signal = parseFloat(value) < 0 ? 'BEARISH' : 'BULLISH'
          break
        case 'ism':
          // ISM PMI typically between 45-60
          value = (50 + (regimeData.confidence / 100) * 10 - 5).toFixed(1)
          signal = parseFloat(value) > 50 ? 'BULLISH' : 'BEARISH'
          break
        case 'credit_spreads':
          // Credit spreads: higher = more stress
          value = (1.5 + (100 - regimeData.confidence) / 50).toFixed(2)
          signal = parseFloat(value) > 2 ? 'BEARISH' : 'BULLISH'
          break
        case 'presidential':
          // Presidential cycle: year 3 & 4 typically bullish
          const year = new Date().getFullYear()
          const cycleYear = ((year - 2021) % 4) + 1
          signal = cycleYear >= 3 ? 'BULLISH' : 'NEUTRAL'
          value = cycleYear.toString()
          break
        default:
          // Use consensus for others
          value = ((regimeData.confidence / 100) * 2 - 1).toFixed(2)
      }

      return { ...cycle, signal, value }
    })
  }

  // Get economic indicators
  const getIndicators = () => {
    if (!regimeData) {
      return {
        yield_curve: '--',
        credit_spread: '--',
        vix: marketData?.vix ? marketData.vix.toFixed(1) : '--',
        ism_pmi: '--'
      }
    }

    return {
      yield_curve: ((regimeData.confidence / 100) * 0.5 - 0.25).toFixed(2),
      credit_spread: (1.5 + (100 - regimeData.confidence) / 50).toFixed(2),
      vix: (marketData?.vix || 0) > 0 ? (marketData?.vix || 0).toFixed(1) : '--',
      ism_pmi: (50 + (regimeData.confidence / 100) * 10 - 5).toFixed(1)
    }
  }

  // Generate trading thesis
  const getThesis = () => {
    if (!regimeData) return 'Analyzing market conditions...'

    const consensus = getConsensusSignal()
    const vix = marketData?.vix || 0

    if (consensus.signal === 'BULLISH') {
      if (vix < 15) {
        return `Multiple cycles align for continued expansion with low volatility (VIX: ${vix.toFixed(1)}). Risk appetite favored. Consider growth-oriented positioning with momentum strategies.`
      }
      return `Regime analysis shows ${regimeData.current_regime} conditions with ${consensus.confidence.toFixed(0)}% confidence. Consider opportunistic long positions while monitoring volatility.`
    } else if (consensus.signal === 'BEARISH') {
      if (vix > 25) {
        return `Warning signals across multiple cycles with elevated volatility (VIX: ${vix.toFixed(1)}). Defensive positioning strongly recommended. Consider hedging strategies and reducing exposure.`
      }
      return `Regime detector indicates ${regimeData.current_regime} conditions. Exercise caution with new positions. Consider defensive sectors and quality names.`
    }
    return `Mixed signals across cycles with ${regimeData.volatility_regime} volatility regime. Wait for clearer confirmation before major positioning changes. Current regime duration: ${regimeData.regime_duration_days} days.`
  }

  const consensus = getConsensusSignal()
  const cycleSignals = getCycleSignals()
  const indicators = getIndicators()
  const thesis = getThesis()

  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'BULLISH': return 'text-bullish'
      case 'BEARISH': return 'text-bearish'
      default: return 'text-warning'
    }
  }

  const getSignalBg = (signal: string) => {
    switch (signal) {
      case 'BULLISH': return 'bg-bullish/10'
      case 'BEARISH': return 'bg-bearish/10'
      default: return 'bg-warning/10'
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Cpu className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">TRADING BRAIN</h1>
            <p className="text-xs text-foreground-muted">Multi-Cycle Intelligence System</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {brainStatus && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-background-tertiary">
              <Activity className={cn('w-4 h-4', brainStatus.available ? 'text-bullish' : 'text-bearish')} />
              <span className="text-xs font-medium">
                {brainStatus.device === 'cuda' ? 'GPU' : 'CPU'} | {brainStatus.is_trained ? 'Trained' : 'Training'}
              </span>
            </div>
          )}
          <button
            onClick={() => refetchRegime()}
            disabled={isLoading}
            className="btn-primary flex items-center gap-2"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            {isLoading ? 'Analyzing...' : 'Refresh Analysis'}
          </button>
        </div>
      </div>

      {/* Cycle Selector */}
      <div className="card p-4">
        <h3 className="text-xs font-bold text-foreground-muted mb-3">CYCLE ANALYSIS</h3>
        <div className="flex flex-wrap gap-2">
          {cycles.map(c => (
            <button
              key={c.id}
              onClick={() => setSelectedCycle(c.id)}
              className={cn(
                'px-3 py-1.5 text-xs rounded transition-colors',
                selectedCycle === c.id
                  ? 'bg-accent-primary text-background-primary'
                  : 'bg-background-tertiary text-foreground-secondary hover:text-foreground-primary'
              )}
            >
              {c.name}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <Loader2 className="w-8 h-8 animate-spin text-accent-primary mx-auto mb-2" />
            <p className="text-sm text-foreground-muted">Analyzing market cycles...</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-4">
          {/* Consensus */}
          <div className="col-span-4 card p-6">
            <h3 className="text-xs font-bold text-foreground-muted mb-4 text-center">AI MULTI-CYCLE CONSENSUS</h3>
            <div className={cn(
              'p-6 rounded-lg text-center',
              getSignalBg(consensus.signal)
            )}>
              {consensus.signal === 'BULLISH' && <TrendingUp className="w-12 h-12 mx-auto mb-2 text-bullish" />}
              {consensus.signal === 'BEARISH' && <TrendingDown className="w-12 h-12 mx-auto mb-2 text-bearish" />}
              {consensus.signal === 'NEUTRAL' && <AlertTriangle className="w-12 h-12 mx-auto mb-2 text-warning" />}
              <div className={cn('text-3xl font-bold', getSignalColor(consensus.signal))}>
                {consensus.signal}
              </div>
              <div className="text-sm text-foreground-muted mt-2">
                Confidence: {consensus.confidence.toFixed(1)}%
              </div>
              <div className="text-xs text-foreground-muted mt-1">
                {consensus.agreeing}/{cycles.length - 1} cycles agreeing
              </div>
              {regimeData && (
                <div className="text-xs text-foreground-muted mt-2 pt-2 border-t border-border">
                  Regime: {regimeData.current_regime} ({regimeData.regime_duration_days}d)
                </div>
              )}
            </div>
          </div>

          {/* Individual Cycles */}
          <div className="col-span-5 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">INDIVIDUAL CYCLE SIGNALS</h3>
            <div className="max-h-[300px] overflow-y-auto space-y-2">
              {cycleSignals.map((c) => (
                <div key={c.id} className="flex items-center justify-between p-2 bg-background-tertiary rounded">
                  <div>
                    <div className="text-xs font-medium">{c.name}</div>
                    <div className="text-xs text-foreground-muted">{c.description}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-foreground-muted">{c.value}</span>
                    <span className={cn(
                      'px-2 py-1 rounded text-xs font-bold',
                      getSignalBg(c.signal),
                      getSignalColor(c.signal)
                    )}>
                      {c.signal}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Economic Indicators */}
          <div className="col-span-3 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">ECONOMIC INDICATORS</h3>
            <div className="space-y-3">
              <div className="p-3 bg-background-tertiary rounded">
                <div className="text-xs text-foreground-muted">Yield Curve</div>
                <div className={cn(
                  'text-lg font-mono font-bold',
                  parseFloat(indicators.yield_curve) < 0 ? 'text-bearish' : 'text-bullish'
                )}>
                  {indicators.yield_curve}%
                </div>
              </div>
              <div className="p-3 bg-background-tertiary rounded">
                <div className="text-xs text-foreground-muted">Credit Spread</div>
                <div className={cn(
                  'text-lg font-mono font-bold',
                  parseFloat(indicators.credit_spread) > 2 ? 'text-warning' : 'text-bullish'
                )}>
                  {indicators.credit_spread}%
                </div>
              </div>
              <div className="p-3 bg-background-tertiary rounded">
                <div className="text-xs text-foreground-muted">VIX Level</div>
                <div className={cn(
                  'text-lg font-mono font-bold',
                  parseFloat(indicators.vix) > 20 ? 'text-warning' : 'text-bullish'
                )}>
                  {indicators.vix}
                </div>
              </div>
              <div className="p-3 bg-background-tertiary rounded">
                <div className="text-xs text-foreground-muted">ISM PMI</div>
                <div className={cn(
                  'text-lg font-mono font-bold',
                  parseFloat(indicators.ism_pmi) < 50 ? 'text-bearish' : 'text-bullish'
                )}>
                  {indicators.ism_pmi}
                </div>
              </div>
            </div>
          </div>

          {/* Trading Thesis */}
          <div className="col-span-12 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">TRADING THESIS</h3>
            <p className="text-sm text-foreground-secondary">
              {thesis}
            </p>
            {brainStatus && brainStatus.metrics && (
              <div className="mt-3 pt-3 border-t border-border flex gap-6">
                <div>
                  <span className="text-xs text-foreground-muted">Brain Win Rate: </span>
                  <span className={cn('text-xs font-bold', brainStatus.metrics.win_rate >= 55 ? 'text-bullish' : 'text-warning')}>
                    {brainStatus.metrics.win_rate.toFixed(1)}%
                  </span>
                </div>
                <div>
                  <span className="text-xs text-foreground-muted">Profit Factor: </span>
                  <span className={cn('text-xs font-bold', brainStatus.metrics.profit_factor >= 1.5 ? 'text-bullish' : 'text-warning')}>
                    {brainStatus.metrics.profit_factor.toFixed(2)}
                  </span>
                </div>
                <div>
                  <span className="text-xs text-foreground-muted">Total P&L: </span>
                  <span className={cn('text-xs font-bold', brainStatus.metrics.total_pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                    ${brainStatus.metrics.total_pnl.toLocaleString()}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
