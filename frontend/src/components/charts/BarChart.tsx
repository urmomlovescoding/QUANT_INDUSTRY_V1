import { useEffect, useRef } from 'react'

interface BarChartProps {
  horizontal?: boolean
}

// Sample P&L distribution data
const pnlData = [
  { label: '-5K+', value: 2, color: '#ff1744' },
  { label: '-4K', value: 3, color: '#ff1744' },
  { label: '-3K', value: 4, color: '#ff1744' },
  { label: '-2K', value: 6, color: '#ff1744' },
  { label: '-1K', value: 8, color: '#ff1744' },
  { label: '0', value: 4, color: '#666666' },
  { label: '+1K', value: 12, color: '#00c853' },
  { label: '+2K', value: 10, color: '#00c853' },
  { label: '+3K', value: 7, color: '#00c853' },
  { label: '+4K', value: 5, color: '#00c853' },
  { label: '+5K+', value: 3, color: '#00c853' },
]

// Sample horizontal bar data (strategy performance)
const strategyData = [
  { label: 'Momentum', value: 2.4, color: '#00c853' },
  { label: 'Mean Rev', value: 1.8, color: '#00c853' },
  { label: 'Breakout', value: 1.5, color: '#00c853' },
  { label: 'Trend', value: 1.2, color: '#f0b90b' },
  { label: 'Scalping', value: 0.9, color: '#ff9800' },
]

export function BarChart({ horizontal = false }: BarChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height

    // Clear
    ctx.fillStyle = '#1f1f1f'
    ctx.fillRect(0, 0, width, height)

    if (horizontal) {
      drawHorizontalBars(ctx, width, height)
    } else {
      drawVerticalBars(ctx, width, height)
    }
  }, [horizontal])

  return (
    <canvas
      ref={canvasRef}
      width={horizontal ? 300 : 350}
      height={horizontal ? 180 : 200}
      className="w-full"
    />
  )
}

function drawVerticalBars(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const padding = { top: 20, right: 10, bottom: 40, left: 30 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const data = pnlData
  const maxValue = Math.max(...data.map((d) => d.value))
  const barWidth = (chartWidth / data.length) * 0.7
  const barGap = (chartWidth / data.length) * 0.3

  // Draw bars
  data.forEach((item, i) => {
    const barHeight = (item.value / maxValue) * chartHeight
    const x = padding.left + i * (barWidth + barGap) + barGap / 2
    const y = padding.top + chartHeight - barHeight

    // Bar
    ctx.fillStyle = item.color
    ctx.beginPath()
    ctx.roundRect(x, y, barWidth, barHeight, [3, 3, 0, 0])
    ctx.fill()

    // Label
    ctx.fillStyle = '#666666'
    ctx.font = '9px Inter'
    ctx.textAlign = 'center'
    ctx.fillText(item.label, x + barWidth / 2, height - 8)
  })

  // Y-axis labels
  ctx.fillStyle = '#666666'
  ctx.font = '10px Inter'
  ctx.textAlign = 'right'

  for (let i = 0; i <= 4; i++) {
    const value = (maxValue / 4) * i
    const y = padding.top + chartHeight - (value / maxValue) * chartHeight
    ctx.fillText(value.toFixed(0), padding.left - 5, y + 4)
  }
}

function drawHorizontalBars(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const padding = { top: 10, right: 40, bottom: 10, left: 70 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const data = strategyData
  const maxValue = Math.max(...data.map((d) => d.value))
  const barHeight = (chartHeight / data.length) * 0.7
  const barGap = (chartHeight / data.length) * 0.3

  // Draw bars
  data.forEach((item, i) => {
    const barWidth = (item.value / maxValue) * chartWidth
    const x = padding.left
    const y = padding.top + i * (barHeight + barGap) + barGap / 2

    // Bar
    ctx.fillStyle = item.color
    ctx.beginPath()
    ctx.roundRect(x, y, barWidth, barHeight, [0, 4, 4, 0])
    ctx.fill()

    // Label (left)
    ctx.fillStyle = '#a0a0a0'
    ctx.font = '11px Inter'
    ctx.textAlign = 'right'
    ctx.fillText(item.label, padding.left - 8, y + barHeight / 2 + 4)

    // Value (right)
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 11px Inter'
    ctx.textAlign = 'left'
    ctx.fillText(item.value.toFixed(1) + 'x', x + barWidth + 8, y + barHeight / 2 + 4)
  })
}
