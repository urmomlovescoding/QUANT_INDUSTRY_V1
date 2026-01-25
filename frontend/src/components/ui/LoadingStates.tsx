/**
 * Loading State Components for QUANT INDUSTRY
 * Provides skeleton loaders and loading indicators
 */
import React from 'react';

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
      className={`animate-pulse bg-gray-700 ${rounded ? 'rounded-full' : 'rounded'} ${className}`}
      style={{ width, height }}
    />
  );
}

export function SkeletonText({ lines = 3, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
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
    <div className={`bg-gray-800 rounded-lg p-4 ${className}`}>
      <Skeleton width="40%" height="1.25rem" className="mb-3" />
      <SkeletonText lines={2} />
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      <div className="bg-gray-700 p-3 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} width={`${100 / cols}%`} height="1rem" />
        ))}
      </div>
      <div className="divide-y divide-gray-700">
        {Array.from({ length: rows }).map((_, rowIdx) => (
          <div key={rowIdx} className="p-3 flex gap-4">
            {Array.from({ length: cols }).map((_, colIdx) => (
              <Skeleton key={colIdx} width={`${100 / cols}%`} height="1rem" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function SkeletonChart({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-gray-800 rounded-lg p-4 ${className}`}>
      <div className="flex justify-between mb-4">
        <Skeleton width="30%" height="1.5rem" />
        <div className="flex gap-2">
          <Skeleton width="60px" height="1.5rem" />
          <Skeleton width="60px" height="1.5rem" />
        </div>
      </div>
      <Skeleton width="100%" height="200px" />
    </div>
  );
}

export function SkeletonQuote() {
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex justify-between items-center mb-2">
        <Skeleton width="80px" height="1.5rem" />
        <Skeleton width="60px" height="1rem" rounded />
      </div>
      <Skeleton width="120px" height="2rem" className="mb-2" />
      <div className="flex gap-4">
        <Skeleton width="80px" height="1rem" />
        <Skeleton width="80px" height="1rem" />
      </div>
    </div>
  );
}

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  color?: string;
  className?: string;
}

export function Spinner({ size = 'md', color = 'text-blue-500', className = '' }: SpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12'
  };

  return (
    <div className={`${sizeClasses[size]} ${color} ${className}`}>
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
    <div className={`${containerClass} bg-gray-900/80 flex items-center justify-center`}>
      <div className="text-center">
        <Spinner size="lg" className="mx-auto mb-4" />
        <p className="text-gray-300">{message}</p>
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
    <span className={`relative flex h-3 w-3 ${className}`}>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
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
    <div className="flex items-center gap-2 text-xs text-gray-400">
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
