/**
 * Formatting Utilities
 */

/**
 * Format number as currency
 */
export function formatCurrency(
  value: number,
  currency: string = 'USD',
  minimumFractionDigits: number = 2
): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits,
    maximumFractionDigits: 2,
  }).format(value)
}

/**
 * Format number as compact currency (e.g., $1.2M)
 */
export function formatCompactCurrency(value: number): string {
  const absValue = Math.abs(value)
  const sign = value < 0 ? '-' : ''

  if (absValue >= 1_000_000_000) {
    return `${sign}$${(absValue / 1_000_000_000).toFixed(2)}B`
  }
  if (absValue >= 1_000_000) {
    return `${sign}$${(absValue / 1_000_000).toFixed(2)}M`
  }
  if (absValue >= 1_000) {
    return `${sign}$${(absValue / 1_000).toFixed(2)}K`
  }
  return `${sign}$${absValue.toFixed(2)}`
}

/**
 * Format number as percentage
 */
export function formatPercent(
  value: number,
  decimals: number = 2,
  showSign: boolean = false
): string {
  const sign = showSign && value > 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

/**
 * Format number with thousands separators
 */
export function formatNumber(value: number, decimals: number = 0): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

/**
 * Format number as compact (e.g., 1.2M)
 */
export function formatCompact(value: number): string {
  const absValue = Math.abs(value)
  const sign = value < 0 ? '-' : ''

  if (absValue >= 1_000_000_000) {
    return `${sign}${(absValue / 1_000_000_000).toFixed(2)}B`
  }
  if (absValue >= 1_000_000) {
    return `${sign}${(absValue / 1_000_000).toFixed(2)}M`
  }
  if (absValue >= 1_000) {
    return `${sign}${(absValue / 1_000).toFixed(2)}K`
  }
  return `${sign}${absValue.toFixed(0)}`
}

/**
 * Format date/time
 */
export function formatDateTime(
  date: string | Date,
  options: Intl.DateTimeFormatOptions = {}
): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    ...options,
  })
}

/**
 * Format date only
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/**
 * Format time only
 */
export function formatTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) {
    return 'just now'
  }
  if (diffMins < 60) {
    return `${diffMins}m ago`
  }
  if (diffHours < 24) {
    return `${diffHours}h ago`
  }
  if (diffDays < 7) {
    return `${diffDays}d ago`
  }
  return formatDate(d)
}

/**
 * Format price with appropriate decimals
 */
export function formatPrice(price: number): string {
  if (price >= 1000) {
    return price.toFixed(2)
  }
  if (price >= 1) {
    return price.toFixed(2)
  }
  if (price >= 0.01) {
    return price.toFixed(4)
  }
  return price.toFixed(6)
}

/**
 * Format stock quantity
 */
export function formatQuantity(qty: number): string {
  if (Number.isInteger(qty)) {
    return formatNumber(qty)
  }
  return qty.toFixed(4)
}

/**
 * Get color class based on value
 */
export function getPnLColorClass(value: number): string {
  if (value > 0) return 'text-bullish'
  if (value < 0) return 'text-bearish'
  return 'text-foreground-secondary'
}

/**
 * Get background color class based on value
 */
export function getPnLBgClass(value: number): string {
  if (value > 0) return 'bg-bullish/10'
  if (value < 0) return 'bg-bearish/10'
  return 'bg-foreground-muted/10'
}

/**
 * Get signal direction color
 */
export function getDirectionColorClass(direction: string): string {
  const d = direction.toUpperCase()
  if (d === 'LONG' || d === 'BUY') return 'text-bullish'
  if (d === 'SHORT' || d === 'SELL') return 'text-bearish'
  return 'text-foreground-secondary'
}

/**
 * Get confidence color based on value
 */
export function getConfidenceColorClass(confidence: number): string {
  if (confidence >= 0.8) return 'text-bullish'
  if (confidence >= 0.6) return 'text-warning'
  if (confidence >= 0.4) return 'text-foreground-secondary'
  return 'text-bearish'
}

/**
 * Get status color
 */
export function getStatusColorClass(status: string): string {
  const s = status.toLowerCase()
  if (['active', 'open', 'filled', 'success', 'healthy'].includes(s)) {
    return 'text-bullish'
  }
  if (['pending', 'partial', 'warning', 'degraded'].includes(s)) {
    return 'text-warning'
  }
  if (['closed', 'cancelled', 'expired', 'dismissed'].includes(s)) {
    return 'text-foreground-muted'
  }
  if (['error', 'rejected', 'failed', 'unhealthy'].includes(s)) {
    return 'text-bearish'
  }
  return 'text-foreground-secondary'
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength - 3) + '...'
}

/**
 * Capitalize first letter
 */
export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase()
}

/**
 * Format ticker symbol
 */
export function formatTicker(symbol: string): string {
  return symbol.toUpperCase().trim()
}
