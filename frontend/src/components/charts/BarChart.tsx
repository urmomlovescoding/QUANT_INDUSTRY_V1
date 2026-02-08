import { useEffect, useRef } from 'react'

interface BarDataItem {
  label: string
  value: number
  color?: string
}

interface BarChartProps {
  horizontal?: boolean
  data?: BarDataItem[]
  emptyMessage?: string
}

// Default empty data - no fake data
const defaultVerticalData: BarDataItem[] = []
const defaultHorizontalData: BarDataItem[] = []

export function BarChart({ horizontal = false, data, emptyMessage = 'No data available' }: BarChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const chartData = data || (horizontal ? defaultHorizontalData : defaultVerticalData)

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

    // If no data, show empty state
    if (chartData.length === 0) {
      ctx.fillStyle = '#555555'
      ctx.font = '13px Inter'
      ctx.textAlign = 'center'
      ctx.fillText(emptyMessage, width / 2, height / 2)
      return
    }

    if (horizontal) {
      drawHorizontalBars(ctx, width, height, chartData)
    } else {
      drawVerticalBars(ctx, width, height, chartData)
    }
  }, [horizontal, chartData, emptyMessage])

  return (
    <canvas
      ref={canvasRef}
      width={horizontal ? 300 : 350}
      height={horizontal ? 180 : 200}
      className="w-full"
    />
  )
}

function drawVerticalBars(ctx: CanvasRenderingContext2D, width: number, height: number, data: BarDataItem[]) {
  const padding = { top: 20, right: 10, bottom: 40, left: 30 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const maxValue = Math.max(...data.map((d) => Math.abs(d.value)))
  if (maxValue === 0) return

  const barWidth = (chartWidth / data.length) * 0.7
  const barGap = (chartWidth / data.length) * 0.3

  // Draw bars
  data.forEach((item, i) => {
    const barHeight = (Math.abs(item.value) / maxValue) * chartHeight
    const x = padding.left + i * (barWidth + barGap) + barGap / 2
    const y = padding.top + chartHeight - barHeight

    // Default color based on value if not specified
    const barColor = item.color || (item.value >= 0 ? '#00c853' : '#ff1744')

    // Bar
    ctx.fillStyle = barColor
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

function drawHorizontalBars(ctx: CanvasRenderingContext2D, width: number, height: number, data: BarDataItem[]) {
  const padding = { top: 10, right: 40, bottom: 10, left: 70 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const maxValue = Math.max(...data.map((d) => Math.abs(d.value)))
  if (maxValue === 0) return

  const barHeight = (chartHeight / data.length) * 0.7
  const barGap = (chartHeight / data.length) * 0.3

  // Draw bars
  data.forEach((item, i) => {
    const barWidth = (Math.abs(item.value) / maxValue) * chartWidth
    const x = padding.left
    const y = padding.top + i * (barHeight + barGap) + barGap / 2

    // Default color based on value threshold
    const barColor = item.color || (item.value >= 1.5 ? '#00c853' : item.value >= 1.0 ? '#f0b90b' : '#ff9800')

    // Bar
    ctx.fillStyle = barColor
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
