import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/utils/cn'
import { formatNumber } from '@/utils/format'

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
      <div className="metric-card">
        <div className="flex items-start justify-between">
          <div className="space-y-3 flex-1">
            <div className="skeleton h-3 w-20 rounded" />
            <div className="skeleton h-7 w-32 rounded" />
            <div className="skeleton h-4 w-24 rounded" />
          </div>
          <div className="p-2.5 rounded-xl bg-background-tertiary/50">
            <div className="skeleton w-5 h-5 rounded" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={cn(
      'metric-card group',
      valueColor === 'bullish' && 'hover:shadow-glow-bullish',
      valueColor === 'bearish' && 'hover:shadow-glow-bearish'
    )}>
      <div className="flex items-start justify-between">
        <div className="space-y-1.5">
          <p className="metric-label">{title}</p>
          <p
            className={cn(
              'metric-value',
              valueColor === 'bullish' && '!text-bullish',
              valueColor === 'bearish' && '!text-bearish'
            )}
            style={valueColor !== 'default' ? { WebkitTextFillColor: 'unset', backgroundClip: 'unset', background: 'none' } : undefined}
          >
            {value}
          </p>
          {(change !== undefined || changePercent !== undefined) && (
            <div
              className={cn(
                'flex items-center gap-1 text-xs font-semibold',
                isPositive ? 'text-bullish' : 'text-bearish'
              )}
            >
              {isPositive ? (
                <TrendingUp className="w-3.5 h-3.5" />
              ) : (
                <TrendingDown className="w-3.5 h-3.5" />
              )}
              {change !== undefined && (
                <span className="tabular-nums font-mono">
                  {isPositive ? '+' : ''}
                  {typeof change === 'number' && Math.abs(change) >= 1000
                    ? formatNumber(change, change % 1 !== 0 ? 2 : 0)
                    : typeof change === 'number' && change % 1 !== 0
                      ? change.toFixed(2)
                      : change}
                </span>
              )}
              {changePercent !== undefined && (
                <span className={cn(
                  'tabular-nums font-mono',
                  isPositive ? 'text-bullish/70' : 'text-bearish/70'
                )}>
                  ({isPositive ? '+' : ''}{changePercent.toFixed(2)}%)
                </span>
              )}
            </div>
          )}
          {subtitle && (
            <p className="text-xs text-foreground-muted mt-1">{subtitle}</p>
          )}
        </div>
        {Icon && (
          <div className={cn(
            'p-2.5 rounded-xl transition-all duration-300',
            valueColor === 'bullish' ? 'bg-bullish/10 group-hover:bg-bullish/15' :
            valueColor === 'bearish' ? 'bg-bearish/10 group-hover:bg-bearish/15' :
            'bg-accent-primary/10 group-hover:bg-accent-primary/15'
          )}>
            <Icon className={cn(
              'w-5 h-5 transition-transform duration-300 group-hover:scale-110',
              valueColor === 'bullish' ? 'text-bullish' :
              valueColor === 'bearish' ? 'text-bearish' :
              'text-accent-primary'
            )} />
          </div>
        )}
      </div>
    </div>
  )
}
