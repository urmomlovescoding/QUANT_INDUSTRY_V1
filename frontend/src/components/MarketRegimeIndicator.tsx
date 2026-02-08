/**
 * Market Regime Indicator
 * Displays current market state in the header with visual cues
 */

import { useState, useEffect } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Minus,
  AlertTriangle,
  Zap,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { useAppStore } from '@/store'

export type MarketRegime = 'TRENDING_UP' | 'TRENDING_DOWN' | 'RANGING' | 'VOLATILE' | 'QUIET'
export type VolatilityRegime = 'LOW' | 'NORMAL' | 'HIGH' | 'EXTREME'

interface RegimeData {
  regime: MarketRegime
  volatility: VolatilityRegime
  vix: number
  confidence: number
  trend_strength: number
}

const REGIME_CONFIG: Record<MarketRegime, {
  label: string
  icon: typeof TrendingUp
  color: string
  bg: string
  description: string
}> = {
  TRENDING_UP: {
    label: 'TREND ↑',
    icon: TrendingUp,
    color: 'text-bullish',
    bg: 'bg-bullish/20',
    description: 'Strong upward momentum'
  },
  TRENDING_DOWN: {
    label: 'TREND ↓',
    icon: TrendingDown,
    color: 'text-bearish',
    bg: 'bg-bearish/20',
    description: 'Strong downward momentum'
  },
  RANGING: {
    label: 'RANGING',
    icon: Minus,
    color: 'text-warning',
    bg: 'bg-warning/20',
    description: 'Sideways consolidation'
  },
  VOLATILE: {
    label: 'VOLATILE',
    icon: Zap,
    color: 'text-bearish',
    bg: 'bg-bearish/20',
    description: 'High volatility detected'
  },
  QUIET: {
    label: 'QUIET',
    icon: Activity,
    color: 'text-foreground-muted',
    bg: 'bg-background-tertiary',
    description: 'Low activity period'
  }
}

const VOLATILITY_CONFIG: Record<VolatilityRegime, {
  color: string
  label: string
}> = {
  LOW: { color: 'text-bullish', label: 'Low Vol' },
  NORMAL: { color: 'text-foreground-secondary', label: 'Normal' },
  HIGH: { color: 'text-warning', label: 'High Vol' },
  EXTREME: { color: 'text-bearish', label: 'Extreme!' }
}

export function MarketRegimeIndicator() {
  // Pull real data from the store instead of simulating
  const brainStatus = useAppStore((s) => s.brainStatus)
  const tickers = useAppStore((s) => s.tickers)
  const [showTooltip, setShowTooltip] = useState(false)

  // Derive regime data from real brain status and market data
  const vixTicker = tickers.find(t => t.symbol === 'VIX' || t.symbol === '^VIX')
  const vixValue = vixTicker?.price ?? 0

  // Map brain regime string to our MarketRegime type
  const mapRegime = (regime?: string): MarketRegime => {
    if (!regime) return 'QUIET'
    const r = regime.toUpperCase()
    if (r.includes('TREND') && r.includes('UP')) return 'TRENDING_UP'
    if (r.includes('TREND') && r.includes('DOWN')) return 'TRENDING_DOWN'
    if (r.includes('BULL')) return 'TRENDING_UP'
    if (r.includes('BEAR')) return 'TRENDING_DOWN'
    if (r.includes('VOLATIL')) return 'VOLATILE'
    if (r.includes('RANG') || r.includes('SIDE')) return 'RANGING'
    return 'QUIET'
  }

  const getVolatilityRegime = (vix: number): VolatilityRegime => {
    if (vix <= 0) return 'NORMAL' // No data
    if (vix < 15) return 'LOW'
    if (vix < 22) return 'NORMAL'
    if (vix < 30) return 'HIGH'
    return 'EXTREME'
  }

  const regimeData: RegimeData = {
    regime: mapRegime(brainStatus?.current_regime),
    volatility: getVolatilityRegime(vixValue),
    vix: vixValue,
    confidence: brainStatus?.metrics?.win_rate ?? 0,
    trend_strength: brainStatus?.is_trained ? 0.75 : 0.4,
  }

  const regimeConfig = REGIME_CONFIG[regimeData.regime]
  const volatilityConfig = VOLATILITY_CONFIG[regimeData.volatility]
  const Icon = regimeConfig.icon

  return (
    <div
      className="relative"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className={cn(
        'flex items-center gap-2 px-2 py-1 rounded-lg cursor-pointer transition-all',
        regimeConfig.bg,
        'hover:opacity-80'
      )}>
        <Icon className={cn('w-3.5 h-3.5', regimeConfig.color)} />
        <span className={cn('text-xs font-bold', regimeConfig.color)}>
          {regimeConfig.label}
        </span>
        <span className="text-[10px] text-foreground-muted">|</span>
        <span className={cn('text-[10px] font-medium', volatilityConfig.color)}>
          VIX {regimeData.vix.toFixed(1)}
        </span>
      </div>

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute top-full right-0 mt-2 w-64 p-3 bg-background-secondary border border-border rounded-lg shadow-xl z-50">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-foreground-primary">Market Regime</span>
            <span className={cn(
              'px-2 py-0.5 rounded text-[10px] font-bold',
              regimeConfig.bg,
              regimeConfig.color
            )}>
              {regimeConfig.label}
            </span>
          </div>

          <p className="text-xs text-foreground-muted mb-3">{regimeConfig.description}</p>

          <div className="space-y-2">
            {/* Confidence */}
            <div>
              <div className="flex justify-between text-[10px] mb-1">
                <span className="text-foreground-muted">Confidence</span>
                <span className="font-mono">{(regimeData.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 bg-background-tertiary rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent-primary rounded-full transition-all"
                  style={{ width: `${regimeData.confidence * 100}%` }}
                />
              </div>
            </div>

            {/* Trend Strength */}
            <div>
              <div className="flex justify-between text-[10px] mb-1">
                <span className="text-foreground-muted">Trend Strength</span>
                <span className="font-mono">{(regimeData.trend_strength * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 bg-background-tertiary rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    regimeData.regime.includes('UP') ? 'bg-bullish' :
                    regimeData.regime.includes('DOWN') ? 'bg-bearish' : 'bg-warning'
                  )}
                  style={{ width: `${regimeData.trend_strength * 100}%` }}
                />
              </div>
            </div>

            {/* Volatility */}
            <div className="flex items-center justify-between pt-2 border-t border-border">
              <span className="text-[10px] text-foreground-muted">Volatility</span>
              <div className="flex items-center gap-2">
                <span className={cn('text-xs font-bold', volatilityConfig.color)}>
                  {volatilityConfig.label}
                </span>
                {regimeData.volatility === 'HIGH' || regimeData.volatility === 'EXTREME' ? (
                  <AlertTriangle className={cn('w-3 h-3', volatilityConfig.color)} />
                ) : null}
              </div>
            </div>

            {/* VIX */}
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-foreground-muted">VIX Index</span>
              <span className={cn('text-xs font-mono font-bold', volatilityConfig.color)}>
                {regimeData.vix.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Trading Implications */}
          <div className="mt-3 pt-3 border-t border-border">
            <span className="text-[10px] font-bold text-foreground-primary">Trading Implications</span>
            <p className="text-[10px] text-foreground-muted mt-1">
              {regimeData.regime === 'TRENDING_UP' && 'Favor long positions. Momentum strategies preferred.'}
              {regimeData.regime === 'TRENDING_DOWN' && 'Consider short positions or hedging. Risk-off environment.'}
              {regimeData.regime === 'RANGING' && 'Mean reversion strategies may work. Avoid breakout trades.'}
              {regimeData.regime === 'VOLATILE' && 'Reduce position sizes. Consider volatility strategies.'}
              {regimeData.regime === 'QUIET' && 'Low opportunity. Wait for clearer signals.'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// Compact version for tight spaces
export function MarketRegimeCompact() {
  const brainStatus = useAppStore((s) => s.brainStatus)

  // Map brain regime string to our type
  const mapRegime = (r?: string): MarketRegime => {
    if (!r) return 'QUIET'
    const u = r.toUpperCase()
    if (u.includes('TREND') && u.includes('UP')) return 'TRENDING_UP'
    if (u.includes('TREND') && u.includes('DOWN')) return 'TRENDING_DOWN'
    if (u.includes('BULL')) return 'TRENDING_UP'
    if (u.includes('BEAR')) return 'TRENDING_DOWN'
    if (u.includes('VOLATIL')) return 'VOLATILE'
    if (u.includes('RANG') || u.includes('SIDE')) return 'RANGING'
    return 'QUIET'
  }

  const regime = mapRegime(brainStatus?.current_regime)
  const config = REGIME_CONFIG[regime]
  const Icon = config.icon

  return (
    <div className={cn(
      'flex items-center gap-1.5 px-2 py-0.5 rounded',
      config.bg
    )}>
      <Icon className={cn('w-3 h-3', config.color)} />
      <span className={cn('text-[10px] font-bold', config.color)}>
        {config.label}
      </span>
    </div>
  )
}
