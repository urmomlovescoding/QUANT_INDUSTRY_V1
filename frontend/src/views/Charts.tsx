import { LineChart, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { cn } from '@/utils/cn'

const intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1D', '1W', '1M', '3M', '1Y', 'ALL']

export function Charts() {
  const [ticker, setTicker] = useState('SPY')
  const [interval, setInterval] = useState('1D')
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [indicators, setIndicators] = useState({
    sma_20: 0,
    sma_50: 0,
    rsi: 0,
    macd: 0,
    adx: 0,
    atr: 0,
    trend: 'UP' as 'UP' | 'DOWN' | 'FLAT'
  })

  useEffect(() => {
    // Simulate indicator data
    setIndicators({
      sma_20: 680 + Math.random() * 20,
      sma_50: 670 + Math.random() * 20,
      rsi: 40 + Math.random() * 30,
      macd: (Math.random() - 0.5) * 5,
      adx: 20 + Math.random() * 30,
      atr: 5 + Math.random() * 10,
      trend: ['UP', 'DOWN', 'FLAT'][Math.floor(Math.random() * 3)] as 'UP' | 'DOWN' | 'FLAT'
    })
  }, [ticker, interval])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Set canvas size
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    const width = rect.width
    const height = rect.height

    // Clear
    ctx.fillStyle = '#0d1117'
    ctx.fillRect(0, 0, width, height)

    // Generate candlestick data
    const numCandles = 100
    const candleWidth = (width - 60) / numCandles
    const padding = 40

    let prices: number[] = []
    let price = 680
    for (let i = 0; i < numCandles; i++) {
      price += (Math.random() - 0.48) * 5
      prices.push(price)
    }

    const minPrice = Math.min(...prices) - 10
    const maxPrice = Math.max(...prices) + 10
    const priceRange = maxPrice - minPrice

    // Draw grid
    ctx.strokeStyle = '#1a1f2e'
    ctx.lineWidth = 1
    for (let i = 0; i < 5; i++) {
      const y = padding + (height - 2 * padding) * i / 4
      ctx.beginPath()
      ctx.moveTo(padding, y)
      ctx.lineTo(width - padding, y)
      ctx.stroke()

      // Price labels
      const labelPrice = maxPrice - (priceRange * i / 4)
      ctx.fillStyle = '#666'
      ctx.font = '10px monospace'
      ctx.fillText(`$${labelPrice.toFixed(2)}`, 5, y + 3)
    }

    // Draw candlesticks
    let prevClose = prices[0]
    for (let i = 0; i < numCandles; i++) {
      const x = padding + i * candleWidth
      const close = prices[i]
      const open = prevClose
      const high = Math.max(open, close) + Math.random() * 3
      const low = Math.min(open, close) - Math.random() * 3

      const isGreen = close >= open

      // Wick
      ctx.strokeStyle = isGreen ? '#00c853' : '#ff5252'
      ctx.beginPath()
      ctx.moveTo(x + candleWidth / 2, padding + (1 - (high - minPrice) / priceRange) * (height - 2 * padding))
      ctx.lineTo(x + candleWidth / 2, padding + (1 - (low - minPrice) / priceRange) * (height - 2 * padding))
      ctx.stroke()

      // Body
      ctx.fillStyle = isGreen ? '#00c853' : '#ff5252'
      const bodyTop = padding + (1 - (Math.max(open, close) - minPrice) / priceRange) * (height - 2 * padding)
      const bodyBottom = padding + (1 - (Math.min(open, close) - minPrice) / priceRange) * (height - 2 * padding)
      ctx.fillRect(x + 2, bodyTop, candleWidth - 4, Math.max(1, bodyBottom - bodyTop))

      prevClose = close
    }

    // Draw SMA lines
    ctx.strokeStyle = '#f0b90b'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    for (let i = 0; i < numCandles; i++) {
      const x = padding + i * candleWidth + candleWidth / 2
      const smaValue = prices.slice(Math.max(0, i - 20), i + 1).reduce((a, b) => a + b, 0) / Math.min(i + 1, 20)
      const y = padding + (1 - (smaValue - minPrice) / priceRange) * (height - 2 * padding)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.stroke()

  }, [ticker, interval])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <LineChart className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">CHARTS & TECHNICALS</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            className="input w-24 text-center font-bold"
          />
        </div>
      </div>

      {/* Interval selector */}
      <div className="flex items-center gap-1 bg-background-secondary p-1 rounded-lg w-fit">
        {intervals.map((int) => (
          <button
            key={int}
            onClick={() => setInterval(int)}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded transition-colors',
              interval === int
                ? 'bg-accent-primary text-background-primary'
                : 'text-foreground-secondary hover:text-foreground-primary'
            )}
          >
            {int}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Chart */}
        <div className="col-span-9 card p-4">
          <canvas
            ref={canvasRef}
            className="w-full h-[500px]"
          />
        </div>

        {/* Indicators panel */}
        <div className="col-span-3 space-y-4">
          {/* Trend */}
          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">TREND</h3>
            <div className="flex items-center gap-2">
              {indicators.trend === 'UP' && <TrendingUp className="w-6 h-6 text-bullish" />}
              {indicators.trend === 'DOWN' && <TrendingDown className="w-6 h-6 text-bearish" />}
              {indicators.trend === 'FLAT' && <Minus className="w-6 h-6 text-foreground-muted" />}
              <span className={cn(
                'text-2xl font-bold',
                indicators.trend === 'UP' ? 'text-bullish' : indicators.trend === 'DOWN' ? 'text-bearish' : 'text-foreground-muted'
              )}>
                {indicators.trend}
              </span>
            </div>
          </div>

          {/* Moving Averages */}
          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">MOVING AVERAGES</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">SMA 20</span>
                <span className="text-xs font-mono text-accent-primary">${indicators.sma_20.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">SMA 50</span>
                <span className="text-xs font-mono text-foreground-primary">${indicators.sma_50.toFixed(2)}</span>
              </div>
            </div>
          </div>

          {/* Oscillators */}
          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">OSCILLATORS</h3>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-foreground-muted">RSI (14)</span>
                  <span className="text-xs font-mono">{indicators.rsi.toFixed(1)}</span>
                </div>
                <div className="h-1.5 bg-background-tertiary rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full',
                      indicators.rsi > 70 ? 'bg-bearish' : indicators.rsi < 30 ? 'bg-bullish' : 'bg-accent-primary'
                    )}
                    style={{ width: `${indicators.rsi}%` }}
                  />
                </div>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">MACD</span>
                <span className={cn('text-xs font-mono', indicators.macd >= 0 ? 'text-bullish' : 'text-bearish')}>
                  {indicators.macd >= 0 ? '+' : ''}{indicators.macd.toFixed(3)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">ADX</span>
                <span className="text-xs font-mono">{indicators.adx.toFixed(1)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">ATR</span>
                <span className="text-xs font-mono">{indicators.atr.toFixed(2)}</span>
              </div>
            </div>
          </div>

          {/* Signals */}
          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">SIGNALS</h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs">SMA Cross</span>
                <span className="text-xs px-2 py-0.5 rounded bg-bullish/20 text-bullish">BUY</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs">RSI</span>
                <span className="text-xs px-2 py-0.5 rounded bg-foreground-muted/20 text-foreground-muted">NEUTRAL</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs">MACD</span>
                <span className="text-xs px-2 py-0.5 rounded bg-bullish/20 text-bullish">BULLISH</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
