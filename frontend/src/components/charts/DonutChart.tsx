import { useEffect, useRef } from 'react'

interface DonutChartProps {
  data: Array<{
    name: string
    value: number
    color: string
  }>
  centerLabel?: string
  centerSubLabel?: string
  size?: number
}

export function DonutChart({
  data,
  centerLabel,
  centerSubLabel,
  size = 160,
}: DonutChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const centerX = size / 2
    const centerY = size / 2
    const outerRadius = (size / 2) - 10
    const innerRadius = outerRadius * 0.65

    // Clear
    ctx.clearRect(0, 0, size, size)

    // Calculate total
    const total = data.reduce((sum, item) => sum + item.value, 0)

    // Draw segments
    let startAngle = -Math.PI / 2 // Start from top

    data.forEach((item) => {
      const sliceAngle = (item.value / total) * 2 * Math.PI

      ctx.beginPath()
      ctx.arc(centerX, centerY, outerRadius, startAngle, startAngle + sliceAngle)
      ctx.arc(centerX, centerY, innerRadius, startAngle + sliceAngle, startAngle, true)
      ctx.closePath()
      ctx.fillStyle = item.color
      ctx.fill()

      startAngle += sliceAngle
    })

    // Draw center text
    if (centerLabel) {
      ctx.fillStyle = '#ffffff'
      ctx.font = 'bold 24px Inter'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(centerLabel, centerX, centerY - (centerSubLabel ? 8 : 0))

      if (centerSubLabel) {
        ctx.fillStyle = '#666666'
        ctx.font = '11px Inter'
        ctx.fillText(centerSubLabel, centerX, centerY + 16)
      }
    }
  }, [data, centerLabel, centerSubLabel, size])

  return (
    <canvas
      ref={canvasRef}
      width={size}
      height={size}
      className="mx-auto"
    />
  )
}
