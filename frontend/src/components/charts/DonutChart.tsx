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

    // High DPI support
    const dpr = window.devicePixelRatio || 1
    canvas.width = size * dpr
    canvas.height = size * dpr
    ctx.scale(dpr, dpr)

    const centerX = size / 2
    const centerY = size / 2
    const outerRadius = (size / 2) - 10
    const innerRadius = outerRadius * 0.68

    // Clear
    ctx.clearRect(0, 0, size, size)

    // Calculate total
    const total = data.reduce((sum, item) => sum + item.value, 0)

    // Draw segments with small gap between them
    let startAngle = -Math.PI / 2 // Start from top
    const segmentGap = 0.03 // Small gap in radians

    data.forEach((item) => {
      const sliceAngle = (item.value / total) * 2 * Math.PI

      // Only draw if the segment has meaningful size
      if (sliceAngle > segmentGap * 2) {
        ctx.beginPath()
        ctx.arc(centerX, centerY, outerRadius, startAngle + segmentGap / 2, startAngle + sliceAngle - segmentGap / 2)
        ctx.arc(centerX, centerY, innerRadius, startAngle + sliceAngle - segmentGap / 2, startAngle + segmentGap / 2, true)
        ctx.closePath()
        ctx.fillStyle = item.color
        ctx.fill()
      }

      startAngle += sliceAngle
    })

    // Draw center text
    if (centerLabel) {
      ctx.fillStyle = '#f4f4f5' // foreground-primary
      ctx.font = 'bold 22px "JetBrains Mono", monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(centerLabel, centerX, centerY - (centerSubLabel ? 8 : 0))

      if (centerSubLabel) {
        ctx.fillStyle = 'rgba(113, 113, 122, 0.8)' // foreground-muted
        ctx.font = '500 10px Inter, sans-serif'
        ctx.letterSpacing = '0.05em'
        ctx.fillText(centerSubLabel.toUpperCase(), centerX, centerY + 14)
      }
    }
  }, [data, centerLabel, centerSubLabel, size])

  return (
    <canvas
      ref={canvasRef}
      width={size}
      height={size}
      style={{ width: size, height: size }}
      className="mx-auto"
    />
  )
}
