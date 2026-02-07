import { useEffect, useRef } from 'react'

interface GaugeChartProps {
  value: number
  maxValue: number
  label?: string
  size?: number
}

// Theme colors
const COLORS = {
  track: 'rgba(255, 255, 255, 0.05)',
  bullish: '#10b981',
  accent: '#f59e0b',
  bearish: '#ef4444',
  needle: '#f4f4f5',
  centerDot: '#f4f4f5',
  text: '#f4f4f5',
  labelText: 'rgba(113, 113, 122, 0.8)',
  minMax: 'rgba(113, 113, 122, 0.6)',
}

export function GaugeChart({
  value,
  maxValue,
  label,
  size = 160,
}: GaugeChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // High DPI
    const dpr = window.devicePixelRatio || 1
    canvas.width = size * dpr
    canvas.height = size * dpr
    ctx.scale(dpr, dpr)

    const centerX = size / 2
    const centerY = size / 2 + 20
    const radius = (size / 2) - 20

    // Clear
    ctx.clearRect(0, 0, size, size)

    // Arc angles (180 degree arc, from left to right)
    const startAngle = Math.PI
    const endAngle = 2 * Math.PI

    // Draw background arc (track)
    ctx.beginPath()
    ctx.arc(centerX, centerY, radius, startAngle, endAngle)
    ctx.strokeStyle = COLORS.track
    ctx.lineWidth = 14
    ctx.lineCap = 'round'
    ctx.stroke()

    // Calculate value angle
    const percentage = Math.min(value / maxValue, 1)
    const valueAngle = startAngle + (percentage * Math.PI)

    // Draw gradient arc (value) - green to yellow to red
    const gradient = ctx.createLinearGradient(0, centerY, size, centerY)
    gradient.addColorStop(0, COLORS.bullish)
    gradient.addColorStop(0.5, COLORS.accent)
    gradient.addColorStop(1, COLORS.bearish)

    ctx.beginPath()
    ctx.arc(centerX, centerY, radius, startAngle, valueAngle)
    ctx.strokeStyle = gradient
    ctx.lineWidth = 14
    ctx.lineCap = 'round'
    ctx.stroke()

    // Draw needle
    const needleLength = radius - 25
    const needleAngle = startAngle + (percentage * Math.PI)
    const needleX = centerX + Math.cos(needleAngle) * needleLength
    const needleY = centerY + Math.sin(needleAngle) * needleLength

    ctx.beginPath()
    ctx.moveTo(centerX, centerY)
    ctx.lineTo(needleX, needleY)
    ctx.strokeStyle = COLORS.needle
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.stroke()

    // Draw center circle
    ctx.beginPath()
    ctx.arc(centerX, centerY, 5, 0, 2 * Math.PI)
    ctx.fillStyle = COLORS.centerDot
    ctx.fill()

    // Draw value text
    ctx.fillStyle = COLORS.text
    ctx.font = 'bold 24px "JetBrains Mono", monospace'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(value.toString() + '%', centerX, centerY - 28)

    // Draw label
    if (label) {
      ctx.fillStyle = COLORS.labelText
      ctx.font = '500 10px Inter, sans-serif'
      ctx.fillText(label.toUpperCase(), centerX, centerY + 28)
    }

    // Draw min/max labels
    ctx.fillStyle = COLORS.minMax
    ctx.font = '9px "JetBrains Mono", monospace'
    ctx.textAlign = 'left'
    ctx.fillText('0', 18, centerY + 10)
    ctx.textAlign = 'right'
    ctx.fillText(maxValue.toString(), size - 18, centerY + 10)
  }, [value, maxValue, label, size])

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
