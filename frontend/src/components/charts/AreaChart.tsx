import { useEffect, useRef, useState, useCallback } from 'react'
import { formatNumber } from '@/utils/format'

// Sample data for area chart
const generateData = () => {
  const data = []
  let value = 100000

  const now = new Date()
  for (let i = 30; i >= 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    value += (Math.random() - 0.45) * 2000
    data.push({
      date: date.toISOString().split('T')[0],
      value: Math.max(value, 90000),
    })
  }
  return data
}

const data = generateData()
const maxValue = Math.max(...data.map((d) => d.value))
const minValue = Math.min(...data.map((d) => d.value))

// Theme colors - matching CSS variables
const COLORS = {
  line: '#f59e0b',         // accent-primary
  lineGlow: 'rgba(245, 158, 11, 0.3)',
  areaTop: 'rgba(245, 158, 11, 0.25)',
  areaBottom: 'rgba(245, 158, 11, 0)',
  grid: 'rgba(255, 255, 255, 0.04)',
  axisLabel: 'rgba(113, 113, 122, 0.8)', // foreground-muted
  background: 'transparent',
  tooltipBg: 'rgba(26, 29, 32, 0.95)',
  tooltipBorder: 'rgba(255, 255, 255, 0.1)',
  tooltipText: '#f4f4f5',
  crosshair: 'rgba(255, 255, 255, 0.15)',
}

export function AreaChart() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [tooltip, setTooltip] = useState<{
    x: number
    y: number
    date: string
    value: number
    visible: boolean
  }>({ x: 0, y: 0, date: '', value: 0, visible: false })

  const padding = { top: 20, right: 20, bottom: 30, left: 65 }

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Handle high-DPI displays
    const rect = canvas.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)

    const width = rect.width
    const height = rect.height
    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom

    // Clear with transparent background (card handles the bg)
    ctx.clearRect(0, 0, width, height)

    // Draw subtle grid lines
    ctx.strokeStyle = COLORS.grid
    ctx.lineWidth = 1

    const numGridLines = 5
    for (let i = 0; i <= numGridLines; i++) {
      const y = padding.top + (chartHeight / numGridLines) * i
      ctx.beginPath()
      ctx.moveTo(padding.left, y)
      ctx.lineTo(width - padding.right, y)
      ctx.stroke()

      // Y-axis labels
      const value = maxValue - ((maxValue - minValue) / numGridLines) * i
      ctx.fillStyle = COLORS.axisLabel
      ctx.font = '10px "JetBrains Mono", monospace'
      ctx.textAlign = 'right'
      ctx.fillText(`$${formatNumber(value / 1000, 1)}K`, padding.left - 10, y + 4)
    }

    // Calculate line points
    const xStep = chartWidth / (data.length - 1)
    const yScale = chartHeight / (maxValue - minValue)

    const points = data.map((point, i) => ({
      x: padding.left + i * xStep,
      y: padding.top + (maxValue - point.value) * yScale,
    }))

    // Create gradient for area fill
    const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom)
    gradient.addColorStop(0, COLORS.areaTop)
    gradient.addColorStop(1, COLORS.areaBottom)

    // Draw area fill with smooth curves
    ctx.beginPath()
    ctx.moveTo(points[0].x, height - padding.bottom)
    ctx.lineTo(points[0].x, points[0].y)

    for (let i = 1; i < points.length; i++) {
      const cpx = (points[i - 1].x + points[i].x) / 2
      ctx.bezierCurveTo(cpx, points[i - 1].y, cpx, points[i].y, points[i].x, points[i].y)
    }

    ctx.lineTo(points[points.length - 1].x, height - padding.bottom)
    ctx.closePath()
    ctx.fillStyle = gradient
    ctx.fill()

    // Draw line with glow effect
    ctx.shadowColor = COLORS.lineGlow
    ctx.shadowBlur = 8
    ctx.beginPath()
    ctx.strokeStyle = COLORS.line
    ctx.lineWidth = 2

    ctx.moveTo(points[0].x, points[0].y)
    for (let i = 1; i < points.length; i++) {
      const cpx = (points[i - 1].x + points[i].x) / 2
      ctx.bezierCurveTo(cpx, points[i - 1].y, cpx, points[i].y, points[i].x, points[i].y)
    }
    ctx.stroke()
    ctx.shadowBlur = 0

    // Draw end point dot
    const lastPoint = points[points.length - 1]
    ctx.beginPath()
    ctx.arc(lastPoint.x, lastPoint.y, 4, 0, Math.PI * 2)
    ctx.fillStyle = COLORS.line
    ctx.fill()
    ctx.beginPath()
    ctx.arc(lastPoint.x, lastPoint.y, 6, 0, Math.PI * 2)
    ctx.strokeStyle = COLORS.lineGlow
    ctx.lineWidth = 2
    ctx.stroke()

    // X-axis labels
    ctx.fillStyle = COLORS.axisLabel
    ctx.font = '10px "JetBrains Mono", monospace'
    ctx.textAlign = 'center'

    const labelInterval = Math.ceil(data.length / 6)
    data.forEach((point, i) => {
      if (i % labelInterval === 0 || i === data.length - 1) {
        const x = padding.left + i * xStep
        const date = new Date(point.date)
        ctx.fillText(
          `${date.getMonth() + 1}/${date.getDate()}`,
          x,
          height - 8
        )
      }
    })
  }, [])

  useEffect(() => {
    draw()

    // Redraw on resize
    const observer = new ResizeObserver(() => draw())
    if (containerRef.current) {
      observer.observe(containerRef.current)
    }
    return () => observer.disconnect()
  }, [draw])

  // Handle mouse hover for tooltip
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const chartWidth = rect.width - padding.left - padding.right
    const xStep = chartWidth / (data.length - 1)

    // Find closest data point
    const index = Math.round((mouseX - padding.left) / xStep)
    if (index >= 0 && index < data.length) {
      const point = data[index]
      const x = padding.left + index * xStep
      const yScale = (rect.height - padding.top - padding.bottom) / (maxValue - minValue)
      const y = padding.top + (maxValue - point.value) * yScale

      setTooltip({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        date: point.date,
        value: point.value,
        visible: true,
      })

      // Redraw with crosshair
      draw()
      const ctx = canvas.getContext('2d')
      if (ctx) {
        const dpr = window.devicePixelRatio || 1
        ctx.save()
        ctx.scale(1 / dpr, 1 / dpr)
        ctx.scale(dpr, dpr)

        // Vertical crosshair
        ctx.strokeStyle = COLORS.crosshair
        ctx.lineWidth = 1
        ctx.setLineDash([4, 4])
        ctx.beginPath()
        ctx.moveTo(x, padding.top)
        ctx.lineTo(x, rect.height - padding.bottom)
        ctx.stroke()
        ctx.setLineDash([])

        // Highlight dot
        ctx.beginPath()
        ctx.arc(x, y, 5, 0, Math.PI * 2)
        ctx.fillStyle = COLORS.line
        ctx.fill()
        ctx.beginPath()
        ctx.arc(x, y, 8, 0, Math.PI * 2)
        ctx.strokeStyle = COLORS.lineGlow
        ctx.lineWidth = 2
        ctx.stroke()

        ctx.restore()
      }
    }
  }, [draw])

  const handleMouseLeave = useCallback(() => {
    setTooltip(prev => ({ ...prev, visible: false }))
    draw()
  }, [draw])

  return (
    <div ref={containerRef} className="relative w-full h-[240px]">
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />
      {/* Tooltip overlay */}
      {tooltip.visible && (
        <div
          className="absolute pointer-events-none z-10 px-3 py-2 rounded-lg text-xs border"
          style={{
            left: Math.min(tooltip.x + 12, (containerRef.current?.clientWidth ?? 300) - 140),
            top: Math.max(tooltip.y - 50, 0),
            background: COLORS.tooltipBg,
            borderColor: COLORS.tooltipBorder,
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          }}
        >
          <div className="text-foreground-muted font-mono text-[10px] mb-1">
            {new Date(tooltip.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          </div>
          <div className="text-foreground-primary font-mono font-bold tabular-nums">
            ${formatNumber(tooltip.value, 2)}
          </div>
        </div>
      )}
    </div>
  )
}
