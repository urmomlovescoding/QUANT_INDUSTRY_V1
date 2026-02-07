import { useEffect, useRef, useCallback } from 'react'

interface BarChartProps {
  horizontal?: boolean
}

// Theme colors matching CSS variables
const COLORS = {
  bullish: '#10b981',
  bearish: '#ef4444',
  accent: '#f59e0b',
  accentSoft: '#d97706',
  neutral: 'rgba(113, 113, 122, 0.5)',
  axisLabel: 'rgba(113, 113, 122, 0.8)',
  valueLabel: '#f4f4f5',
  grid: 'rgba(255, 255, 255, 0.04)',
}

// P&L distribution data
const pnlData = [
  { label: '-5K+', value: 2, color: COLORS.bearish },
  { label: '-4K', value: 3, color: COLORS.bearish },
  { label: '-3K', value: 4, color: COLORS.bearish },
  { label: '-2K', value: 6, color: COLORS.bearish },
  { label: '-1K', value: 8, color: COLORS.bearish },
  { label: '0', value: 4, color: COLORS.neutral },
  { label: '+1K', value: 12, color: COLORS.bullish },
  { label: '+2K', value: 10, color: COLORS.bullish },
  { label: '+3K', value: 7, color: COLORS.bullish },
  { label: '+4K', value: 5, color: COLORS.bullish },
  { label: '+5K+', value: 3, color: COLORS.bullish },
]

// Strategy performance data
const strategyData = [
  { label: 'Momentum', value: 2.4, color: COLORS.bullish },
  { label: 'Mean Rev', value: 1.8, color: COLORS.bullish },
  { label: 'Breakout', value: 1.5, color: COLORS.accent },
  { label: 'Trend', value: 1.2, color: COLORS.accent },
  { label: 'Scalping', value: 0.9, color: COLORS.accentSoft },
]

export function BarChart({ horizontal = false }: BarChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Handle high-DPI
    const rect = canvas.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)

    const width = rect.width
    const height = rect.height

    // Clear
    ctx.clearRect(0, 0, width, height)

    if (horizontal) {
      drawHorizontalBars(ctx, width, height)
    } else {
      drawVerticalBars(ctx, width, height)
    }
  }, [horizontal])

  useEffect(() => {
    draw()

    const observer = new ResizeObserver(() => draw())
    if (containerRef.current) {
      observer.observe(containerRef.current)
    }
    return () => observer.disconnect()
  }, [draw])

  return (
    <div ref={containerRef} className={horizontal ? 'w-full h-[180px]' : 'w-full h-[200px]'}>
      <canvas
        ref={canvasRef}
        className="w-full h-full"
      />
    </div>
  )
}

function drawVerticalBars(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const padding = { top: 20, right: 10, bottom: 36, left: 30 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const data = pnlData
  const maxValue = Math.max(...data.map((d) => d.value))
  const barWidth = (chartWidth / data.length) * 0.65
  const barGap = (chartWidth / data.length) * 0.35

  // Subtle grid
  ctx.strokeStyle = COLORS.grid
  ctx.lineWidth = 1
  for (let i = 0; i <= 4; i++) {
    const y = padding.top + (chartHeight / 4) * i
    ctx.beginPath()
    ctx.moveTo(padding.left, y)
    ctx.lineTo(width - padding.right, y)
    ctx.stroke()
  }

  // Draw bars with rounded tops
  data.forEach((item, i) => {
    const barHeight = (item.value / maxValue) * chartHeight
    const x = padding.left + i * (barWidth + barGap) + barGap / 2
    const y = padding.top + chartHeight - barHeight

    // Bar with subtle gradient
    const gradient = ctx.createLinearGradient(x, y, x, y + barHeight)
    gradient.addColorStop(0, item.color)
    gradient.addColorStop(1, item.color + '80')

    ctx.fillStyle = gradient
    ctx.beginPath()
    ctx.roundRect(x, y, barWidth, barHeight, [4, 4, 0, 0])
    ctx.fill()

    // Label
    ctx.fillStyle = COLORS.axisLabel
    ctx.font = '9px "JetBrains Mono", monospace'
    ctx.textAlign = 'center'
    ctx.fillText(item.label, x + barWidth / 2, height - 10)
  })

  // Y-axis labels
  ctx.fillStyle = COLORS.axisLabel
  ctx.font = '9px "JetBrains Mono", monospace'
  ctx.textAlign = 'right'

  for (let i = 0; i <= 4; i++) {
    const value = (maxValue / 4) * i
    const y = padding.top + chartHeight - (value / maxValue) * chartHeight
    ctx.fillText(value.toFixed(0), padding.left - 6, y + 3)
  }
}

function drawHorizontalBars(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const padding = { top: 10, right: 45, bottom: 10, left: 72 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const data = strategyData
  const maxValue = Math.max(...data.map((d) => d.value))
  const barHeight = (chartHeight / data.length) * 0.65
  const barGap = (chartHeight / data.length) * 0.35

  // Draw bars
  data.forEach((item, i) => {
    const barWidth = (item.value / maxValue) * chartWidth
    const x = padding.left
    const y = padding.top + i * (barHeight + barGap) + barGap / 2

    // Bar with horizontal gradient
    const gradient = ctx.createLinearGradient(x, y, x + barWidth, y)
    gradient.addColorStop(0, item.color + 'CC')
    gradient.addColorStop(1, item.color)

    ctx.fillStyle = gradient
    ctx.beginPath()
    ctx.roundRect(x, y, barWidth, barHeight, [0, 5, 5, 0])
    ctx.fill()

    // Label (left)
    ctx.fillStyle = COLORS.axisLabel
    ctx.font = '11px Inter, sans-serif'
    ctx.textAlign = 'right'
    ctx.fillText(item.label, padding.left - 10, y + barHeight / 2 + 4)

    // Value (right of bar)
    ctx.fillStyle = COLORS.valueLabel
    ctx.font = 'bold 11px "JetBrains Mono", monospace'
    ctx.textAlign = 'left'
    ctx.fillText(item.value.toFixed(1) + 'x', x + barWidth + 8, y + barHeight / 2 + 4)
  })
}
