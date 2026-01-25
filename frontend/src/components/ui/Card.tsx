/**
 * Card Component - Consistent card styling
 */

import { forwardRef, HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/utils/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'bordered'
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const variantStyles = {
  default: 'bg-background-secondary',
  elevated: 'bg-background-elevated shadow-lg',
  bordered: 'bg-background-secondary border border-border',
}

const paddingStyles = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    {
      variant = 'bordered',
      padding = 'md',
      className,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <div
        ref={ref}
        className={cn(
          'rounded-lg',
          variantStyles[variant],
          paddingStyles[padding],
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Card.displayName = 'Card'

// Card Header
interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
  title: string
  subtitle?: string
  action?: ReactNode
}

export function CardHeader({
  title,
  subtitle,
  action,
  className,
  ...props
}: CardHeaderProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between mb-4',
        className
      )}
      {...props}
    >
      <div>
        <h3 className="text-sm font-medium text-foreground-primary">{title}</h3>
        {subtitle && (
          <p className="text-xs text-foreground-muted mt-0.5">{subtitle}</p>
        )}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  )
}

// Card Content
interface CardContentProps extends HTMLAttributes<HTMLDivElement> {}

export function CardContent({
  className,
  children,
  ...props
}: CardContentProps) {
  return (
    <div className={cn('', className)} {...props}>
      {children}
    </div>
  )
}

// Card Footer
interface CardFooterProps extends HTMLAttributes<HTMLDivElement> {
  separator?: boolean
}

export function CardFooter({
  separator = true,
  className,
  children,
  ...props
}: CardFooterProps) {
  return (
    <div
      className={cn(
        'mt-4',
        separator && 'pt-4 border-t border-border',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

// Stat Card - specialized card for metrics
interface StatCardProps {
  title: string
  value: string | number
  change?: number
  changeLabel?: string
  icon?: ReactNode
  trend?: 'up' | 'down' | 'neutral'
  className?: string
}

export function StatCard({
  title,
  value,
  change,
  changeLabel,
  icon,
  trend,
  className,
}: StatCardProps) {
  const trendColor =
    trend === 'up'
      ? 'text-bullish'
      : trend === 'down'
      ? 'text-bearish'
      : 'text-foreground-muted'

  return (
    <Card className={className}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-foreground-muted uppercase tracking-wider">
            {title}
          </p>
          <p className="text-2xl font-bold text-foreground-primary mt-1">
            {value}
          </p>
          {(change !== undefined || changeLabel) && (
            <p className={cn('text-xs mt-1', trendColor)}>
              {change !== undefined && (
                <span>
                  {change >= 0 ? '+' : ''}
                  {typeof change === 'number' ? change.toFixed(2) : change}%
                </span>
              )}
              {changeLabel && (
                <span className="text-foreground-muted ml-1">
                  {changeLabel}
                </span>
              )}
            </p>
          )}
        </div>
        {icon && (
          <div className="p-2 rounded-lg bg-accent-primary/10 text-accent-primary">
            {icon}
          </div>
        )}
      </div>
    </Card>
  )
}
