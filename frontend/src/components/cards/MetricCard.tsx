import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/utils/cn'

interface MetricCardProps {
  title: string
  value: string
  change?: number
  changePercent?: number
  icon?: LucideIcon
  trend?: 'up' | 'down' | 'neutral'
  valueColor?: 'default' | 'bullish' | 'bearish'
  subtitle?: string
  isLoading?: boolean
}

export function MetricCard({
  title,
  value,
  change,
  changePercent,
  icon: Icon,
  trend,
  valueColor = 'default',
  subtitle,
  isLoading = false,
}: MetricCardProps) {
  const isPositive = trend === 'up' || (change !== undefined && change > 0)

  if (isLoading) {
    return (
      <div className="card p-4">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <div className="h-3 w-20 bg-foreground-muted/20 rounded animate-pulse" />
            <div className="h-8 w-32 bg-foreground-muted/20 rounded animate-pulse" />
            <div className="h-4 w-24 bg-foreground-muted/20 rounded animate-pulse" />
          </div>
          <div className="p-2 rounded-lg bg-foreground-muted/10">
            <div className="w-5 h-5 bg-foreground-muted/20 rounded animate-pulse" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card p-4 hover:shadow-elevated transition-shadow">
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="metric-label">{title}</p>
          <p
            className={cn(
              'metric-value',
              valueColor === 'bullish' && 'text-bullish',
              valueColor === 'bearish' && 'text-bearish'
            )}
          >
            {value}
          </p>
          {(change !== undefined || changePercent !== undefined) && (
            <div
              className={cn(
                'flex items-center gap-1 text-sm font-medium',
                isPositive ? 'text-bullish' : 'text-bearish'
              )}
            >
              {isPositive ? (
                <TrendingUp className="w-4 h-4" />
              ) : (
                <TrendingDown className="w-4 h-4" />
              )}
              {change !== undefined && (
                <span className="tabular-nums">
                  {isPositive ? '+' : ''}
                  {typeof change === 'number' && change % 1 !== 0
                    ? change.toFixed(2)
                    : change}
                </span>
              )}
              {changePercent !== undefined && (
                <span className="text-foreground-muted">
                  ({isPositive ? '+' : ''}{changePercent.toFixed(2)}%)
                </span>
              )}
            </div>
          )}
          {subtitle && (
            <p className="text-xs text-foreground-muted">{subtitle}</p>
          )}
        </div>
        {Icon && (
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Icon className="w-5 h-5 text-accent-primary" />
          </div>
        )}
      </div>
    </div>
  )
}
