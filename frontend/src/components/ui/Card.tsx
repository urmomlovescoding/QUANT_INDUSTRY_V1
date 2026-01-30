/**
 * Card Component - Organic glass-morphism styling
 */

import { forwardRef, HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/utils/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'glass' | 'gradient'
  padding?: 'none' | 'sm' | 'md' | 'lg'
  hover?: boolean
  glow?: 'none' | 'accent' | 'bullish' | 'bearish'
}

const variantStyles = {
  default: 'bg-background-elevated border border-border',
  elevated: 'bg-background-elevated border border-border shadow-elevated',
  glass: cn(
    'bg-gradient-to-br from-background-elevated/90 to-background-tertiary/80',
    'backdrop-blur-glass border border-border/50',
    'shadow-card'
  ),
  gradient: cn(
    'bg-gradient-to-br from-background-elevated to-background-tertiary',
    'border border-border/50 shadow-lg'
  ),
}

const paddingStyles = {
  none: '',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
}

const glowStyles = {
  none: '',
  accent: 'shadow-glow-accent',
  bullish: 'shadow-glow-bullish',
  bearish: 'shadow-glow-bearish',
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    {
      variant = 'glass',
      padding = 'md',
      hover = true,
      glow = 'none',
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
          'rounded-2xl transition-all duration-300 ease-smooth',
          variantStyles[variant],
          paddingStyles[padding],
          glowStyles[glow],
          hover && [
            'hover:border-border-light',
            'hover:shadow-elevated',
            'hover:-translate-y-0.5',
          ],
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
  icon?: ReactNode
}

export function CardHeader({
  title,
  subtitle,
  action,
  icon,
  className,
  ...props
}: CardHeaderProps) {
  return (
    <div
      className={cn(
        'flex items-start justify-between mb-5 pb-4 border-b border-border/50',
        className
      )}
      {...props}
    >
      <div className="flex items-start gap-3">
        {icon && (
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-accent-primary/20 to-accent-secondary/10">
            {icon}
          </div>
        )}
        <div>
          <h3 className="text-sm font-semibold text-foreground-primary">{title}</h3>
          {subtitle && (
            <p className="text-xs text-foreground-muted mt-1">{subtitle}</p>
          )}
        </div>
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
        'mt-5',
        separator && 'pt-4 border-t border-border/50',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

// Stat Card - specialized card for metrics with organic styling
interface StatCardProps {
  title: string
  value: string | number
  change?: number
  changeLabel?: string
  icon?: ReactNode
  trend?: 'up' | 'down' | 'neutral'
  className?: string
  accentColor?: 'gold' | 'green' | 'blue' | 'purple' | 'red'
}

const accentColors = {
  gold: {
    bg: 'from-amber-500/20 to-orange-500/10',
    icon: 'text-amber-400',
    glow: 'group-hover:shadow-[0_0_30px_rgba(245,158,11,0.15)]',
  },
  green: {
    bg: 'from-emerald-500/20 to-green-500/10',
    icon: 'text-emerald-400',
    glow: 'group-hover:shadow-[0_0_30px_rgba(16,185,129,0.15)]',
  },
  blue: {
    bg: 'from-blue-500/20 to-cyan-500/10',
    icon: 'text-blue-400',
    glow: 'group-hover:shadow-[0_0_30px_rgba(59,130,246,0.15)]',
  },
  purple: {
    bg: 'from-purple-500/20 to-violet-500/10',
    icon: 'text-purple-400',
    glow: 'group-hover:shadow-[0_0_30px_rgba(147,51,234,0.15)]',
  },
  red: {
    bg: 'from-red-500/20 to-rose-500/10',
    icon: 'text-red-400',
    glow: 'group-hover:shadow-[0_0_30px_rgba(239,68,68,0.15)]',
  },
}

export function StatCard({
  title,
  value,
  change,
  changeLabel,
  icon,
  trend,
  className,
  accentColor = 'gold',
}: StatCardProps) {
  const colors = accentColors[accentColor]
  
  const trendColor =
    trend === 'up'
      ? 'text-bullish bg-bullish/10'
      : trend === 'down'
      ? 'text-bearish bg-bearish/10'
      : 'text-foreground-muted bg-background-tertiary'

  return (
    <Card className={cn('group relative overflow-hidden', colors.glow, className)}>
      {/* Subtle gradient overlay on hover */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none">
        <div className={cn('absolute inset-0 bg-gradient-to-br', colors.bg, 'opacity-30')} />
      </div>
      
      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold text-foreground-muted uppercase tracking-widest mb-2">
            {title}
          </p>
          <p className="text-2xl font-bold text-foreground-primary tabular-nums">
            {value}
          </p>
          {(change !== undefined || changeLabel) && (
            <div className={cn(
              'inline-flex items-center gap-1 text-xs font-semibold mt-2 px-2 py-1 rounded-lg',
              trendColor
            )}>
              {change !== undefined && (
                <span className="tabular-nums">
                  {change >= 0 ? '+' : ''}
                  {typeof change === 'number' ? change.toFixed(2) : change}%
                </span>
              )}
              {changeLabel && (
                <span className="text-foreground-muted ml-1">
                  {changeLabel}
                </span>
              )}
            </div>
          )}
        </div>
        {icon && (
          <div className={cn(
            'p-3 rounded-xl bg-gradient-to-br transition-transform duration-300',
            'group-hover:scale-110',
            colors.bg,
            colors.icon
          )}>
            {icon}
          </div>
        )}
      </div>
    </Card>
  )
}
