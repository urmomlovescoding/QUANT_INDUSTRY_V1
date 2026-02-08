/**
 * Error Boundary Component
 *
 * Provides error isolation at multiple levels:
 * - Top-level: catches fatal app errors
 * - View-level: isolates crashes to individual views/sections
 * - Component-level: via withErrorBoundary HOC
 */

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  /** Section name shown in error UI (e.g., "Trading Brain", "Analytics") */
  section?: string
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
    this.props.onError?.(error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  handleGoHome = () => {
    window.location.href = '/dashboard'
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      const sectionLabel = this.props.section
        ? ` in ${this.props.section}`
        : ''

      return (
        <div className="flex flex-col items-center justify-center min-h-[200px] p-6 bg-background-secondary rounded-lg border border-border">
          <AlertTriangle className="w-12 h-12 text-error mb-4" />
          <h3 className="text-lg font-semibold text-foreground-primary mb-2">
            Something went wrong{sectionLabel}
          </h3>
          <p className="text-sm text-foreground-muted text-center max-w-md mb-4">
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <div className="flex gap-3">
            <button
              onClick={this.handleReset}
              className="flex items-center gap-2 px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/90 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </button>
            {this.props.section && (
              <button
                onClick={this.handleGoHome}
                className="flex items-center gap-2 px-4 py-2 bg-background-tertiary text-foreground-secondary rounded-lg hover:bg-background-tertiary/80 transition-colors"
              >
                <Home className="w-4 h-4" />
                Dashboard
              </button>
            )}
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

/**
 * View-level error boundary that isolates crashes to individual views.
 * Shows section name and a "Go to Dashboard" fallback button.
 */
export function ViewErrorBoundary({
  children,
  section,
}: {
  children: ReactNode
  section: string
}) {
  return (
    <ErrorBoundary section={section}>
      {children}
    </ErrorBoundary>
  )
}

/**
 * HOC for wrapping components with error boundary
 */
export function withErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  fallback?: ReactNode
) {
  return function WithErrorBoundaryWrapper(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <WrappedComponent {...props} />
      </ErrorBoundary>
    )
  }
}
