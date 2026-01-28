/**
 * Error Display Components for QUANT INDUSTRY
 * User-friendly error messages and recovery options
 */
import React from 'react';

// Re-export ErrorBoundary from its dedicated module to avoid duplication
export { ErrorBoundary, withErrorBoundary } from './ErrorBoundary';

interface ErrorCardProps {
  title?: string;
  message: string;
  details?: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  variant?: 'error' | 'warning' | 'info';
}

export function ErrorCard({
  title = 'Error',
  message,
  details,
  onRetry,
  onDismiss,
  variant = 'error'
}: ErrorCardProps) {
  const variantStyles = {
    error: {
      bg: 'bg-red-900/50',
      border: 'border-red-500',
      icon: 'text-red-400',
      title: 'text-red-300'
    },
    warning: {
      bg: 'bg-yellow-900/50',
      border: 'border-yellow-500',
      icon: 'text-yellow-400',
      title: 'text-yellow-300'
    },
    info: {
      bg: 'bg-blue-900/50',
      border: 'border-blue-500',
      icon: 'text-blue-400',
      title: 'text-blue-300'
    }
  };

  const styles = variantStyles[variant];

  return (
    <div className={`${styles.bg} ${styles.border} border rounded-lg p-4`}>
      <div className="flex items-start gap-3">
        <div className={`${styles.icon} mt-0.5`}>
          {variant === 'error' && (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
          {variant === 'warning' && (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          )}
          {variant === 'info' && (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
        </div>

        <div className="flex-1">
          <h3 className={`${styles.title} font-medium`}>{title}</h3>
          <p className="text-gray-300 text-sm mt-1">{message}</p>
          {details && (
            <details className="mt-2">
              <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-400">
                Technical details
              </summary>
              <pre className="text-xs text-gray-500 mt-1 p-2 bg-gray-900 rounded overflow-auto">
                {details}
              </pre>
            </details>
          )}
        </div>

        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-gray-400 hover:text-white"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {onRetry && (
        <div className="mt-4 flex gap-2">
          <button
            onClick={onRetry}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm transition-colors"
          >
            Try Again
          </button>
        </div>
      )}
    </div>
  );
}

interface InlineErrorProps {
  message: string;
  onRetry?: () => void;
}

export function InlineError({ message, onRetry }: InlineErrorProps) {
  return (
    <div className="flex items-center gap-2 text-red-400 text-sm">
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-red-300 hover:text-red-200 underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  message?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon, title, message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && (
        <div className="text-gray-500 mb-4">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-medium text-gray-300 mb-2">{title}</h3>
      {message && (
        <p className="text-gray-500 mb-4 max-w-md">{message}</p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

interface ConnectionErrorProps {
  onRetry?: () => void;
}

export function ConnectionError({ onRetry }: ConnectionErrorProps) {
  return (
    <ErrorCard
      variant="warning"
      title="Connection Issue"
      message="Unable to connect to the server. Please check your connection and try again."
      onRetry={onRetry}
    />
  );
}

interface DataUnavailableProps {
  resource: string;
  onRetry?: () => void;
}

export function DataUnavailable({ resource, onRetry }: DataUnavailableProps) {
  return (
    <ErrorCard
      variant="info"
      title="Data Unavailable"
      message={`${resource} data is currently unavailable. This may be due to market hours or temporary service issues.`}
      onRetry={onRetry}
    />
  );
}

export function MarketClosedNotice() {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 flex items-center gap-3">
      <div className="text-yellow-400">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <div>
        <p className="text-gray-300 font-medium">Market Closed</p>
        <p className="text-gray-500 text-sm">
          Displaying last known prices. Live data will resume when markets open.
        </p>
      </div>
    </div>
  );
}
