import { useEffect, useRef } from 'react'

interface GaugeChartProps {
  value: number
  maxValue: number
  label?: string
  size?: number
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
    ctx.strokeStyle = '#2a2a2a'
    ctx.lineWidth = 16
    ctx.lineCap = 'round'
    ctx.stroke()

    // Calculate value angle
    const percentage = Math.min(value / maxValue, 1)
    const valueAngle = startAngle + (percentage * Math.PI)

    // Draw gradient arc (value)
    const gradient = ctx.createLinearGradient(0, centerY, size, centerY)
    gradient.addColorStop(0, '#00c853')
    gradient.addColorStop(0.5, '#f0b90b')
    gradient.addColorStop(1, '#ff1744')

    ctx.beginPath()
    ctx.arc(centerX, centerY, radius, startAngle, valueAngle)
    ctx.strokeStyle = gradient
    ctx.lineWidth = 16
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
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.stroke()

    // Draw center circle
    ctx.beginPath()
    ctx.arc(centerX, centerY, 6, 0, 2 * Math.PI)
    ctx.fillStyle = '#ffffff'
    ctx.fill()

    // Draw value text
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 28px Inter'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(value.toString() + '%', centerX, centerY - 30)

    // Draw label
    if (label) {
      ctx.fillStyle = '#666666'
      ctx.font = '11px Inter'
      ctx.fillText(label, centerX, centerY + 30)
    }

    // Draw min/max labels
    ctx.fillStyle = '#666666'
    ctx.font = '10px Inter'
    ctx.textAlign = 'left'
    ctx.fillText('0', 15, centerY + 10)
    ctx.textAlign = 'right'
    ctx.fillText(maxValue.toString(), size - 15, centerY + 10)
  }, [value, maxValue, label, size])

  return (
    <canvas
      ref={canvasRef}
      width={size}
      height={size}
      className="mx-auto"
    />
  )
}
