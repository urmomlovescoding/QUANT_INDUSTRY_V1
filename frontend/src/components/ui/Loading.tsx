/**
 * Loading Components
 */

import { cn } from '@/utils/cn'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function Spinner({ size = 'md', className }: SpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-6 h-6 border-2',
    lg: 'w-8 h-8 border-3',
  }

  return (
    <div
      className={cn(
        'animate-spin rounded-full border-foreground-muted border-t-accent-primary',
        sizeClasses[size],
        className
      )}
    />
  )
}

interface LoadingOverlayProps {
  message?: string
  className?: string
}

export function LoadingOverlay({
  message = 'Loading...',
  className,
}: LoadingOverlayProps) {
  return (
    <div
      className={cn(
        'absolute inset-0 flex flex-col items-center justify-center bg-background-primary/80 backdrop-blur-sm z-50',
        className
      )}
    >
      <Spinner size="lg" />
      <p className="mt-3 text-sm text-foreground-muted">{message}</p>
    </div>
  )
}

interface LoadingCardProps {
  title?: string
  className?: string
}

export function LoadingCard({ title, className }: LoadingCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center min-h-[200px] p-6 bg-background-secondary rounded-lg border border-border',
        className
      )}
    >
      <Spinner size="lg" />
      {title && (
        <p className="mt-3 text-sm text-foreground-muted">{title}</p>
      )}
    </div>
  )
}

interface SkeletonProps {
  className?: string
  animate?: boolean
}

export function Skeleton({ className, animate = true }: SkeletonProps) {
  return (
    <div
      className={cn(
        animate ? 'skeleton' : 'bg-foreground-muted/20',
        'rounded',
        className
      )}
    />
  )
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn(
            'h-4',
            i === lines - 1 ? 'w-3/4' : 'w-full'
          )}
        />
      ))}
    </div>
  )
}

export function SkeletonCard() {
  return (
    <div className="p-4 bg-background-secondary rounded-lg border border-border space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-5 w-16" />
      </div>
      <Skeleton className="h-8 w-32" />
      <div className="flex gap-4">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-20" />
      </div>
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="rounded-xl overflow-hidden border border-border/50">
      {/* Header */}
      <div className="flex gap-4 px-5 py-3.5 bg-background-tertiary/50">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-3 flex-1" />
        ))}
      </div>
      {/* Rows */}
      <div className="divide-y divide-border/50">
        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={i}
            className={cn(
              'flex gap-4 px-5 py-3.5',
              i % 2 === 1 && 'bg-background-secondary/30'
            )}
          >
            {Array.from({ length: cols }).map((_, j) => (
              <Skeleton key={j} className="h-3.5 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export function SkeletonChart() {
  return (
    <div className="p-4 bg-background-secondary rounded-lg border border-border">
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-8 w-24" />
      </div>
      <Skeleton className="h-48 w-full" />
    </div>
  )
}

export function SkeletonMetricCard() {
  return (
    <div className="p-4 bg-background-tertiary rounded-lg border border-border">
      <Skeleton className="h-4 w-24 mb-2" />
      <Skeleton className="h-8 w-32 mb-2" />
      <Skeleton className="h-4 w-16" />
    </div>
  )
}

interface LoadingStateProps {
  isLoading: boolean
  error?: string | null
  isEmpty?: boolean
  emptyMessage?: string
  children: React.ReactNode
  skeleton?: React.ReactNode
}

export function LoadingState({
  isLoading,
  error,
  isEmpty = false,
  emptyMessage = 'No data available',
  children,
  skeleton,
}: LoadingStateProps) {
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] p-8 text-center">
        <div className="w-10 h-10 rounded-2xl bg-bearish/10 flex items-center justify-center mb-3">
          <svg className="w-5 h-5 text-bearish" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <p className="text-sm font-medium text-foreground-primary mb-1">Error loading data</p>
        <p className="text-xs text-foreground-muted max-w-xs">{error}</p>
      </div>
    )
  }

  if (isLoading) {
    return skeleton || <LoadingCard />
  }

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] p-8 text-center">
        <p className="text-sm text-foreground-muted">{emptyMessage}</p>
      </div>
    )
  }

  return <>{children}</>
}
