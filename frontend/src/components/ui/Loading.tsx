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
        'bg-foreground-muted/20 rounded',
        animate && 'animate-pulse',
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
    <div className="space-y-2">
      {/* Header */}
      <div className="flex gap-4 p-3 bg-background-tertiary rounded">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 p-3">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-4 flex-1" />
          ))}
        </div>
      ))}
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
      <div className="flex flex-col items-center justify-center min-h-[200px] p-6 text-center">
        <p className="text-error mb-2">Error loading data</p>
        <p className="text-sm text-foreground-muted">{error}</p>
      </div>
    )
  }

  if (isLoading) {
    return skeleton || <LoadingCard />
  }

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] p-6 text-center">
        <p className="text-foreground-muted">{emptyMessage}</p>
      </div>
    )
  }

  return <>{children}</>
}
