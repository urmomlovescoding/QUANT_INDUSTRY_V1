import { useEffect, useRef } from 'react'

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

export function AreaChart() {
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
      const value = maxValue - ((maxValue - minValue) / numGridLines) * i
      ctx.fillStyle = '#666666'
      ctx.font = '11px Inter'
      ctx.textAlign = 'right'
      ctx.fillText(`$${(value / 1000).toFixed(0)}K`, padding.left - 8, y + 4)
    }

    // Draw area
    const xStep = chartWidth / (data.length - 1)
    const yScale = chartHeight / (maxValue - minValue)

    // Create gradient
    const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom)
    gradient.addColorStop(0, 'rgba(240, 185, 11, 0.3)')
    gradient.addColorStop(1, 'rgba(240, 185, 11, 0)')

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
    ctx.fillStyle = gradient
    ctx.fill()

    // Draw line
    ctx.beginPath()
    ctx.strokeStyle = '#f0b90b'
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
  }, [])

  return (
    <canvas
      ref={canvasRef}
      width={700}
      height={240}
      className="w-full"
    />
  )
}
