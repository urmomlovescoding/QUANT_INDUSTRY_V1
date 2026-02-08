import { useEffect, useRef } from 'react'

interface AreaChartProps {
  data?: { date: string; value: number }[]
  color?: string
  emptyMessage?: string
}

export function AreaChart({ data, color = '#f0b90b', emptyMessage = 'No data available' }: AreaChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height
    const padding = { top: 20, right: 20, bottom: 30, left: 60 }

    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom

    // Clear
    ctx.fillStyle = '#1f1f1f'
    ctx.fillRect(0, 0, width, height)

    // If no data, show empty state
    if (!data || data.length === 0) {
      ctx.fillStyle = '#555555'
      ctx.font = '13px Inter'
      ctx.textAlign = 'center'
      ctx.fillText(emptyMessage, width / 2, height / 2)
      return
    }

    const maxValue = Math.max(...data.map((d) => d.value))
    const minValue = Math.min(...data.map((d) => d.value))
    const valueRange = maxValue - minValue || 1

    // Draw grid lines
    ctx.strokeStyle = '#2a2a2a'
    ctx.lineWidth = 1

    const numGridLines = 5
    for (let i = 0; i <= numGridLines; i++) {
      const y = padding.top + (chartHeight / numGridLines) * i
      ctx.beginPath()
      ctx.moveTo(padding.left, y)
      ctx.lineTo(width - padding.right, y)
      ctx.stroke()

      // Y-axis labels
      const value = maxValue - (valueRange / numGridLines) * i
      ctx.fillStyle = '#666666'
      ctx.font = '11px Inter'
      ctx.textAlign = 'right'
      ctx.fillText(`$${(value / 1000).toFixed(0)}K`, padding.left - 8, y + 4)
    }

    // Draw area
    const xStep = chartWidth / (data.length - 1)
    const yScale = chartHeight / valueRange

    // Create gradient
    const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom)
    gradient.addColorStop(0, color.replace(')', ', 0.3)').replace('rgb', 'rgba').replace('#', ''))

    // Parse hex color to rgba for gradient
    const hexToRgba = (hex: string, alpha: number) => {
      const r = parseInt(hex.slice(1, 3), 16)
      const g = parseInt(hex.slice(3, 5), 16)
      const b = parseInt(hex.slice(5, 7), 16)
      return `rgba(${r}, ${g}, ${b}, ${alpha})`
    }

    const gradientFill = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom)
    gradientFill.addColorStop(0, hexToRgba(color, 0.3))
    gradientFill.addColorStop(1, hexToRgba(color, 0))

    // Area fill
    ctx.beginPath()
    ctx.moveTo(padding.left, height - padding.bottom)

    data.forEach((point, i) => {
      const x = padding.left + i * xStep
      const y = padding.top + (maxValue - point.value) * yScale
      ctx.lineTo(x, y)
    })

    ctx.lineTo(padding.left + (data.length - 1) * xStep, height - padding.bottom)
    ctx.closePath()
    ctx.fillStyle = gradientFill
    ctx.fill()

    // Draw line
    ctx.beginPath()
    ctx.strokeStyle = color
    ctx.lineWidth = 2

    data.forEach((point, i) => {
      const x = padding.left + i * xStep
      const y = padding.top + (maxValue - point.value) * yScale

      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    })

    ctx.stroke()

    // X-axis labels
    ctx.fillStyle = '#666666'
    ctx.font = '10px Inter'
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
  }, [data, color, emptyMessage])

  return (
    <canvas
      ref={canvasRef}
      width={700}
      height={240}
      className="w-full"
    />
  )
}
