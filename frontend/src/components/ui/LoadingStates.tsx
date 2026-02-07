/**
 * Loading State Components for QUANT INDUSTRY
 * Provides skeleton loaders and loading indicators
 * Uses theme-consistent glass morphism styling
 */
import React from 'react';
import { cn } from '@/utils/cn';

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  className?: string;
  rounded?: boolean;
}

export function Skeleton({
  width = '100%',
  height = '1rem',
  className = '',
  rounded = false
}: SkeletonProps) {
  return (
    <div
      className={cn(
        'skeleton',
        rounded ? 'rounded-full' : 'rounded-md',
        className
      )}
      style={{ width, height }}
    />
  );
}

export function SkeletonText({ lines = 3, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2.5 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          width={i === lines - 1 ? '75%' : '100%'}
          height="0.875rem"
        />
      ))}
    </div>
  );
}

export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={cn('card p-5', className)}>
      <Skeleton width="40%" height="1.25rem" className="mb-4" />
      <SkeletonText lines={2} />
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="rounded-xl overflow-hidden border border-border/50">
      {/* Header */}
      <div className="bg-background-tertiary/50 px-5 py-3.5 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} width={`${100 / cols}%`} height="0.75rem" />
        ))}
      </div>
      {/* Rows */}
      <div className="divide-y divide-border/50">
        {Array.from({ length: rows }).map((_, rowIdx) => (
          <div
            key={rowIdx}
            className={cn(
              'px-5 py-3.5 flex gap-4',
              rowIdx % 2 === 1 && 'bg-background-secondary/30'
            )}
          >
            {Array.from({ length: cols }).map((_, colIdx) => (
              <Skeleton
                key={colIdx}
                width={colIdx === 0 ? '60%' : `${100 / cols}%`}
                height="0.875rem"
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function SkeletonChart({ className = '' }: { className?: string }) {
  return (
    <div className={cn('card p-5', className)}>
      <div className="flex justify-between items-center mb-5 pb-4 border-b border-border">
        <Skeleton width="30%" height="1rem" />
        <div className="flex gap-2">
          <Skeleton width="60px" height="1.5rem" className="rounded-lg" />
          <Skeleton width="60px" height="1.5rem" className="rounded-lg" />
        </div>
      </div>
      <Skeleton width="100%" height="200px" className="rounded-lg" />
    </div>
  );
}

export function SkeletonQuote() {
  return (
    <div className="card p-4">
      <div className="flex justify-between items-center mb-3">
        <Skeleton width="80px" height="1.25rem" />
        <Skeleton width="60px" height="1rem" rounded />
      </div>
      <Skeleton width="120px" height="2rem" className="mb-3" />
      <div className="flex gap-4">
        <Skeleton width="80px" height="0.875rem" />
        <Skeleton width="80px" height="0.875rem" />
      </div>
    </div>
  );
}

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  color?: string;
  className?: string;
}

export function Spinner({ size = 'md', color = 'text-accent-primary', className = '' }: SpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12'
  };

  return (
    <div className={cn(sizeClasses[size], color, className)}>
      <svg className="animate-spin" viewBox="0 0 24 24" fill="none">
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    </div>
  );
}

interface LoadingOverlayProps {
  message?: string;
  fullScreen?: boolean;
}

export function LoadingOverlay({ message = 'Loading...', fullScreen = false }: LoadingOverlayProps) {
  const containerClass = fullScreen
    ? 'fixed inset-0 z-50'
    : 'absolute inset-0';

  return (
    <div className={cn(containerClass, 'bg-background-primary/80 backdrop-blur-sm flex items-center justify-center')}>
      <div className="text-center">
        <Spinner size="lg" className="mx-auto mb-4" />
        <p className="text-foreground-secondary text-sm">{message}</p>
      </div>
    </div>
  );
}

interface LoadingButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  loadingText?: string;
  children: React.ReactNode;
}

export function LoadingButton({
  loading = false,
  loadingText = 'Loading...',
  children,
  disabled,
  className = '',
  ...props
}: LoadingButtonProps) {
  return (
    <button
      {...props}
      disabled={loading || disabled}
      className={`relative ${className} ${loading ? 'cursor-wait' : ''}`}
    >
      {loading && (
        <span className="absolute inset-0 flex items-center justify-center">
          <Spinner size="sm" color="text-current" />
        </span>
      )}
      <span className={loading ? 'invisible' : ''}>
        {loading ? loadingText : children}
      </span>
    </button>
  );
}

export function PulsingDot({ className = '' }: { className?: string }) {
  return (
    <span className={cn('relative flex h-2.5 w-2.5', className)}>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-bullish opacity-75" />
      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-bullish" />
    </span>
  );
}

export function DataRefreshIndicator({
  lastUpdate,
  isRefreshing = false
}: {
  lastUpdate?: Date;
  isRefreshing?: boolean;
}) {
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="flex items-center gap-2 text-xs text-foreground-muted">
      {isRefreshing ? (
        <>
          <Spinner size="sm" />
          <span>Refreshing...</span>
        </>
      ) : (
        <>
          <PulsingDot />
          <span>
            {lastUpdate ? `Updated ${formatTime(lastUpdate)}` : 'Live'}
          </span>
        </>
      )}
    </div>
  );
}
