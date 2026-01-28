/**
 * Real-Time Indicators Strip
 * Persistent bar showing key portfolio metrics with flash-on-change animations.
 * Click any metric to drill down to the relevant page.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Briefcase,
  Zap,
  Shield,
  Activity,
  Brain,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { portfolioApi, signalsApi, riskApi, brainApi } from '@/api/client'
import { formatCurrency, formatPercent, formatCompact } from '@/utils/format'

interface MetricData {
  label: string
  value: string
  subValue?: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  flashColor: string
  route: string
  rawValue?: number
}

function useFlashOnChange(value: string) {
  const [flash, setFlash] = useState(false)
  const prevRef = useRef(value)

  useEffect(() => {
    if (prevRef.current !== value && prevRef.current !== '') {
      setFlash(true)
      const timer = setTimeout(() => setFlash(false), 800)
      prevRef.current = value
      return () => clearTimeout(timer)
    }
    prevRef.current = value
  }, [value])

  return flash
}

function StripMetric({ metric }: { metric: MetricData }) {
  const navigate = useNavigate()
  const flash = useFlashOnChange(metric.value)
  const Icon = metric.icon

  return (
    <button
      onClick={() => navigate(metric.route)}
      className={cn(
        'flex items-center gap-1.5 px-3 py-1 rounded transition-all duration-200',
        'hover:bg-background-hover cursor-pointer group',
        flash && metric.flashColor
      )}
      title={`Click to view ${metric.label}`}
    >
      <Icon className={cn('w-3 h-3', metric.color)} />
      <span className="text-[10px] text-foreground-muted uppercase tracking-wider whitespace-nowrap">
        {metric.label}
      </span>
      <span className={cn(
        'text-xs font-mono font-bold whitespace-nowrap transition-colors',
        metric.color
      )}>
        {metric.value}
      </span>
      {metric.subValue && (
        <span className="text-[10px] font-mono text-foreground-muted whitespace-nowrap">
          {metric.subValue}
        </span>
      )}
    </button>
  )
}

export function IndicatorStrip() {
  // Fetch portfolio data
  const { data: portfolioRes } = useQuery({
    queryKey: ['indicator-portfolio'],
    queryFn: () => portfolioApi.getPortfolio(),
    refetchInterval: 5000,
    staleTime: 3000,
  })

  // Fetch positions
  const { data: positionsRes } = useQuery({
    queryKey: ['indicator-positions'],
    queryFn: () => portfolioApi.getPositions(),
    refetchInterval: 5000,
    staleTime: 3000,
  })

  // Fetch active signals
  const { data: signalsRes } = useQuery({
    queryKey: ['indicator-signals'],
    queryFn: () => signalsApi.getActive(),
    refetchInterval: 5000,
    staleTime: 3000,
  })

  // Fetch risk metrics
  const { data: riskRes } = useQuery({
    queryKey: ['indicator-risk'],
    queryFn: () => riskApi.getMetrics(),
    refetchInterval: 10000,
    staleTime: 5000,
  })

  // Fetch brain status
  const { data: brainRes } = useQuery({
    queryKey: ['indicator-brain'],
    queryFn: () => brainApi.getStatus(),
    refetchInterval: 10000,
    staleTime: 5000,
  })

  const portfolio = portfolioRes?.ok ? portfolioRes.data : null
  const positions = positionsRes?.ok ? positionsRes.data : null
  const signals = signalsRes?.ok ? signalsRes.data : null
  const risk = riskRes?.ok ? riskRes.data : null
  const brain = brainRes?.ok ? brainRes.data : null

  const portfolioValue = (portfolio as any)?.total_value ?? (portfolio as any)?.equity ?? 0
  const dailyPnl = (portfolio as any)?.daily_pnl ?? (portfolio as any)?.unrealized_pnl ?? 0
  const dailyPnlPct = (portfolio as any)?.daily_pnl_pct ?? (portfolioValue > 0 ? (dailyPnl / portfolioValue) * 100 : 0)
  const openPositions = positions?.length ?? 0
  const activeSignals = signals?.length ?? 0
  const riskUtilization = (risk as any)?.risk_utilization ?? (risk as any)?.exposure_pct ?? 0
  const brainAccuracy = (brain as any)?.accuracy ?? (brain as any)?.recent_accuracy ?? 0
  const winRate = (brain as any)?.win_rate ?? (brain as any)?.winning_signals ?? 0

  const metrics: MetricData[] = [
    {
      label: 'Portfolio',
      value: portfolioValue ? formatCompact(portfolioValue) : '--',
      icon: DollarSign,
      color: 'text-accent-primary',
      flashColor: 'bg-accent-primary/10',
      route: '/portfolio',
      rawValue: portfolioValue,
    },
    {
      label: 'Day P&L',
      value: dailyPnl !== 0 ? `${dailyPnl >= 0 ? '+' : ''}${formatCurrency(dailyPnl)}` : '--',
      subValue: dailyPnlPct !== 0 ? formatPercent(dailyPnlPct, 2, true) : undefined,
      icon: dailyPnl >= 0 ? TrendingUp : TrendingDown,
      color: dailyPnl >= 0 ? 'text-bullish' : 'text-bearish',
      flashColor: dailyPnl >= 0 ? 'bg-bullish/10' : 'bg-bearish/10',
      route: '/portfolio',
      rawValue: dailyPnl,
    },
    {
      label: 'Positions',
      value: String(openPositions),
      icon: Briefcase,
      color: openPositions > 0 ? 'text-info' : 'text-foreground-muted',
      flashColor: 'bg-info/10',
      route: '/portfolio',
    },
    {
      label: 'Signals',
      value: String(activeSignals),
      icon: Zap,
      color: activeSignals > 0 ? 'text-warning' : 'text-foreground-muted',
      flashColor: 'bg-warning/10',
      route: '/signals',
    },
    {
      label: 'Risk',
      value: riskUtilization ? formatPercent(riskUtilization, 0) : '--',
      icon: Shield,
      color: riskUtilization > 80 ? 'text-bearish' : riskUtilization > 50 ? 'text-warning' : 'text-bullish',
      flashColor: riskUtilization > 80 ? 'bg-bearish/10' : 'bg-bullish/10',
      route: '/risk-engine',
    },
    {
      label: 'Brain',
      value: brainAccuracy ? formatPercent(brainAccuracy * 100, 0) : '--',
      subValue: winRate ? `W:${typeof winRate === 'number' && winRate < 1 ? formatPercent(winRate * 100, 0) : winRate}` : undefined,
      icon: Brain,
      color: 'text-accent-primary',
      flashColor: 'bg-accent-primary/10',
      route: '/unified-brain',
    },
  ]

  return (
    <div className="h-8 bg-background-primary border-b border-border flex items-center px-2 overflow-x-auto scrollbar-hide">
      <div className="flex items-center gap-0.5">
        <Activity className="w-3 h-3 text-accent-primary mr-1 animate-pulse-slow" />
        {metrics.map((metric, i) => (
          <div key={metric.label} className="flex items-center">
            {i > 0 && <div className="w-px h-4 bg-border mx-0.5" />}
            <StripMetric metric={metric} />
          </div>
        ))}
      </div>
    </div>
  )
}
