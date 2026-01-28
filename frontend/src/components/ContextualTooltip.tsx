/**
 * Contextual Tooltips
 * Hover any number to see: How calculated, Historical range, Percentile rank.
 * Hover any position to see: Entry price, Current PnL, Time held, Strategy source.
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/utils/cn'
import { formatCurrency, formatPercent, formatRelativeTime } from '@/utils/format'

// Tooltip data types
interface TooltipMetric {
  label: string
  value: string | number
  color?: string
}

interface TooltipData {
  title: string
  description?: string
  metrics?: TooltipMetric[]
  calculation?: string
  historicalRange?: { min: number; max: number; current: number }
  percentile?: number
}

interface ContextualTooltipProps {
  data: TooltipData
  children: React.ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
  className?: string
}

export function ContextualTooltip({
  data,
  children,
  position = 'top',
  delay = 300,
  className,
}: ContextualTooltipProps) {
  const [visible, setVisible] = useState(false)
  const [coords, setCoords] = useState({ x: 0, y: 0 })
  const triggerRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  const show = useCallback(() => {
    timerRef.current = setTimeout(() => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect()
        const scrollX = window.scrollX
        const scrollY = window.scrollY

        let x = rect.left + scrollX + rect.width / 2
        let y = rect.top + scrollY

        switch (position) {
          case 'bottom':
            y = rect.bottom + scrollY + 6
            break
          case 'left':
            x = rect.left + scrollX - 6
            y = rect.top + scrollY + rect.height / 2
            break
          case 'right':
            x = rect.right + scrollX + 6
            y = rect.top + scrollY + rect.height / 2
            break
          default: // top
            y = rect.top + scrollY - 6
            break
        }

        setCoords({ x, y })
        setVisible(true)
      }
    }, delay)
  }, [delay, position])

  const hide = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    setVisible(false)
  }, [])

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  // Render the range bar for historical ranges
  const renderRange = (range: NonNullable<TooltipData['historicalRange']>) => {
    const pct = ((range.current - range.min) / (range.max - range.min)) * 100
    const clampedPct = Math.max(0, Math.min(100, pct))

    return (
      <div className="mt-2">
        <div className="flex items-center justify-between text-[9px] text-foreground-muted mb-1">
          <span>Min: {typeof range.min === 'number' ? range.min.toFixed(2) : range.min}</span>
          <span>Max: {typeof range.max === 'number' ? range.max.toFixed(2) : range.max}</span>
        </div>
        <div className="h-1.5 bg-background-primary rounded-full overflow-hidden relative">
          <div
            className="absolute top-0 left-0 h-full bg-gradient-to-r from-bearish via-warning to-bullish rounded-full"
            style={{ width: '100%' }}
          />
          <div
            className="absolute top-[-1px] w-2 h-2 bg-foreground-primary rounded-full border border-background-secondary"
            style={{ left: `calc(${clampedPct}% - 4px)` }}
          />
        </div>
        <div className="text-[9px] text-center text-foreground-muted mt-1">
          Current: {typeof range.current === 'number' ? range.current.toFixed(2) : range.current}
        </div>
      </div>
    )
  }

  return (
    <>
      <div
        ref={triggerRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        className={cn('inline-block', className)}
      >
        {children}
      </div>

      {visible && createPortal(
        <div
          ref={tooltipRef}
          className={cn(
            'fixed z-[200] pointer-events-none',
            'bg-background-elevated border border-border rounded-lg shadow-elevated',
            'p-3 min-w-[200px] max-w-[320px]',
            'animate-in fade-in zoom-in-95 duration-150',
          )}
          style={{
            left: position === 'left' ? coords.x : position === 'right' ? coords.x : coords.x,
            top: position === 'top' ? coords.y : coords.y,
            transform: position === 'top' ? 'translate(-50%, -100%)'
              : position === 'bottom' ? 'translate(-50%, 0)'
              : position === 'left' ? 'translate(-100%, -50%)'
              : 'translate(0, -50%)',
          }}
        >
          {/* Title */}
          <p className="text-xs font-bold text-foreground-primary">{data.title}</p>

          {/* Description */}
          {data.description && (
            <p className="text-[10px] text-foreground-secondary mt-1">{data.description}</p>
          )}

          {/* Metrics */}
          {data.metrics && data.metrics.length > 0 && (
            <div className="mt-2 space-y-1">
              {data.metrics.map((m, i) => (
                <div key={i} className="flex items-center justify-between text-[10px]">
                  <span className="text-foreground-muted">{m.label}</span>
                  <span className={cn('font-mono font-bold', m.color || 'text-foreground-primary')}>
                    {m.value}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Calculation method */}
          {data.calculation && (
            <div className="mt-2 pt-2 border-t border-border">
              <p className="text-[9px] text-foreground-muted">
                <span className="text-accent-primary">How: </span>
                {data.calculation}
              </p>
            </div>
          )}

          {/* Historical range */}
          {data.historicalRange && renderRange(data.historicalRange)}

          {/* Percentile rank */}
          {data.percentile !== undefined && (
            <div className="mt-2 pt-2 border-t border-border flex items-center justify-between">
              <span className="text-[9px] text-foreground-muted">Percentile Rank</span>
              <span className={cn(
                'text-[10px] font-bold font-mono',
                data.percentile >= 75 ? 'text-bullish' :
                data.percentile >= 25 ? 'text-warning' : 'text-bearish'
              )}>
                {data.percentile.toFixed(0)}th
              </span>
            </div>
          )}
        </div>,
        document.body
      )}
    </>
  )
}

// Pre-built tooltip wrappers for common data types

interface PnLTooltipProps {
  value: number
  label?: string
  dailyHigh?: number
  dailyLow?: number
  children: React.ReactNode
}

export function PnLTooltip({ value, label = 'P&L', dailyHigh, dailyLow, children }: PnLTooltipProps) {
  return (
    <ContextualTooltip
      data={{
        title: label,
        metrics: [
          { label: 'Current', value: formatCurrency(value), color: value >= 0 ? 'text-bullish' : 'text-bearish' },
        ],
        calculation: 'Unrealized: (current price - entry price) x quantity. Realized: sum of closed trade PnLs.',
        historicalRange: dailyHigh !== undefined && dailyLow !== undefined
          ? { min: dailyLow, max: dailyHigh, current: value }
          : undefined,
      }}
    >
      {children}
    </ContextualTooltip>
  )
}

interface PositionTooltipProps {
  symbol: string
  entryPrice: number
  currentPrice: number
  quantity: number
  pnl: number
  pnlPct: number
  entryTime?: string
  strategy?: string
  children: React.ReactNode
}

export function PositionTooltip({
  symbol,
  entryPrice,
  currentPrice,
  quantity,
  pnl,
  pnlPct,
  entryTime,
  strategy,
  children,
}: PositionTooltipProps) {
  return (
    <ContextualTooltip
      data={{
        title: `${symbol} Position`,
        metrics: [
          { label: 'Entry Price', value: `$${entryPrice.toFixed(2)}` },
          { label: 'Current Price', value: `$${currentPrice.toFixed(2)}` },
          { label: 'Quantity', value: String(quantity) },
          { label: 'P&L', value: formatCurrency(pnl), color: pnl >= 0 ? 'text-bullish' : 'text-bearish' },
          { label: 'P&L %', value: formatPercent(pnlPct, 2, true), color: pnlPct >= 0 ? 'text-bullish' : 'text-bearish' },
          ...(entryTime ? [{ label: 'Time Held', value: formatRelativeTime(entryTime) }] : []),
          ...(strategy ? [{ label: 'Strategy', value: strategy, color: 'text-accent-primary' }] : []),
        ],
      }}
      position="bottom"
    >
      {children}
    </ContextualTooltip>
  )
}

interface ConfidenceTooltipProps {
  confidence: number
  factors?: Array<{ name: string; contribution: number }>
  children: React.ReactNode
}

export function ConfidenceTooltip({ confidence, factors, children }: ConfidenceTooltipProps) {
  return (
    <ContextualTooltip
      data={{
        title: 'Signal Confidence',
        description: 'Composite score from multiple model outputs and regime alignment.',
        metrics: [
          {
            label: 'Confidence',
            value: formatPercent(confidence * 100, 1),
            color: confidence >= 0.7 ? 'text-bullish' : confidence >= 0.4 ? 'text-warning' : 'text-bearish'
          },
          ...(factors || []).map(f => ({
            label: f.name,
            value: formatPercent(f.contribution * 100, 1),
            color: f.contribution >= 0 ? 'text-bullish' : 'text-bearish'
          })),
        ],
        calculation: 'Weighted average of transformer attention, PPO policy, ensemble voting, and regime alignment scores.',
        percentile: confidence * 100,
      }}
    >
      {children}
    </ContextualTooltip>
  )
}

interface MetricTooltipProps {
  title: string
  value: number
  format?: 'currency' | 'percent' | 'number'
  description?: string
  calculation?: string
  min?: number
  max?: number
  percentile?: number
  children: React.ReactNode
}

export function MetricTooltip({
  title,
  value,
  format = 'number',
  description,
  calculation,
  min,
  max,
  percentile,
  children,
}: MetricTooltipProps) {
  const formattedValue = format === 'currency' ? formatCurrency(value)
    : format === 'percent' ? formatPercent(value, 2)
    : value.toFixed(2)

  return (
    <ContextualTooltip
      data={{
        title,
        description,
        metrics: [{ label: 'Value', value: formattedValue }],
        calculation,
        historicalRange: min !== undefined && max !== undefined
          ? { min, max, current: value }
          : undefined,
        percentile,
      }}
    >
      {children}
    </ContextualTooltip>
  )
}
