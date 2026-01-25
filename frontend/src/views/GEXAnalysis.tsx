import { Activity, RefreshCw } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { cn } from '@/utils/cn'

const quickTickers = ['SPY', 'QQQ', 'IWM', 'AAPL', 'TSLA', 'NVDA']

interface GEXData {
  strike: number
  call_gex: number
  put_gex: number
  total_gex: number
}

export function GEXAnalysis() {
  const [ticker, setTicker] = useState('SPY')
  const [maxDte, setMaxDte] = useState(45)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<GEXData[]>([])
  const [summary, setSummary] = useState({
    total_call_gex: 0,
    total_put_gex: 0,
    net_gex: 0,
    gex_flip_point: 0,
    max_pain: 0
  })
  const [currentPrice, setCurrentPrice] = useState(688.98)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const analyze = () => {
    setLoading(true)
    setTimeout(() => {
      // Generate mock GEX data
      const basePrice = ticker === 'SPY' ? 688.98 : ticker === 'QQQ' ? 620.76 : 100 + Math.random() * 400
      setCurrentPrice(basePrice)

      const strikes = Array.from({ length: 21 }, (_, i) => basePrice * (0.8 + i * 0.02))
      const mockData: GEXData[] = strikes.map(strike => {
        const distance = Math.abs(strike - basePrice)
        const magnitude = Math.max(0.1, 1 - (distance / (basePrice * 0.2)))

        const call_gex = magnitude * (0.5 + Math.random() * 1.5) * 1000000000
        const put_gex = magnitude * (-0.3 - Math.random() * 1.2) * 1000000000

        return {
          strike: Math.round(strike),
          call_gex: Math.round(call_gex),
          put_gex: Math.round(put_gex),
          total_gex: Math.round(call_gex + put_gex)
        }
      })

      const totalCall = mockData.reduce((sum, d) => sum + d.call_gex, 0)
      const totalPut = mockData.reduce((sum, d) => sum + d.put_gex, 0)

      setData(mockData)
      setSummary({
        total_call_gex: totalCall / 1e9,
        total_put_gex: totalPut / 1e9,
        net_gex: (totalCall + totalPut) / 1e9,
        gex_flip_point: basePrice * (0.98 + Math.random() * 0.04),
        max_pain: basePrice * (0.97 + Math.random() * 0.06)
      })
      setLoading(false)
    }, 500)
  }

  useEffect(() => {
    analyze()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || data.length === 0) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    const width = rect.width
    const height = rect.height
    const padding = { top: 20, right: 60, bottom: 40, left: 80 }

    // Clear
    ctx.fillStyle = '#0d1117'
    ctx.fillRect(0, 0, width, height)

    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom
    const barWidth = chartWidth / data.length * 0.8

    // Find max values for scaling
    const maxGex = Math.max(...data.map(d => Math.abs(d.call_gex)), ...data.map(d => Math.abs(d.put_gex)))

    // Draw axes
    ctx.strokeStyle = '#333'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(padding.left, padding.top)
    ctx.lineTo(padding.left, height - padding.bottom)
    ctx.lineTo(width - padding.right, height - padding.bottom)
    ctx.stroke()

    // Draw zero line
    const zeroY = padding.top + chartHeight / 2
    ctx.strokeStyle = '#444'
    ctx.setLineDash([5, 5])
    ctx.beginPath()
    ctx.moveTo(padding.left, zeroY)
    ctx.lineTo(width - padding.right, zeroY)
    ctx.stroke()
    ctx.setLineDash([])

    // Draw bars
    data.forEach((d, i) => {
      const x = padding.left + (i + 0.1) * chartWidth / data.length

      // Call GEX (positive)
      const callHeight = (d.call_gex / maxGex) * (chartHeight / 2)
      ctx.fillStyle = '#00c853'
      ctx.fillRect(x, zeroY - callHeight, barWidth / 2, callHeight)

      // Put GEX (negative)
      const putHeight = (Math.abs(d.put_gex) / maxGex) * (chartHeight / 2)
      ctx.fillStyle = '#ff5252'
      ctx.fillRect(x + barWidth / 2, zeroY, barWidth / 2, putHeight)

      // Strike labels
      if (i % 3 === 0) {
        ctx.fillStyle = '#666'
        ctx.font = '10px monospace'
        ctx.textAlign = 'center'
        ctx.fillText(`$${d.strike}`, x + barWidth / 2, height - padding.bottom + 15)
      }
    })

    // Draw current price line
    const priceIndex = data.findIndex(d => d.strike >= currentPrice)
    if (priceIndex > 0) {
      const priceX = padding.left + (priceIndex - 0.5) * chartWidth / data.length
      ctx.strokeStyle = '#f0b90b'
      ctx.lineWidth = 2
      ctx.setLineDash([5, 5])
      ctx.beginPath()
      ctx.moveTo(priceX, padding.top)
      ctx.lineTo(priceX, height - padding.bottom)
      ctx.stroke()
      ctx.setLineDash([])

      ctx.fillStyle = '#f0b90b'
      ctx.font = 'bold 11px sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText(`Current: $${currentPrice.toFixed(2)}`, priceX, padding.top - 5)
    }

    // Legend
    ctx.font = '11px sans-serif'
    ctx.fillStyle = '#00c853'
    ctx.fillRect(width - padding.right - 80, padding.top, 12, 12)
    ctx.fillStyle = '#fff'
    ctx.fillText('Call GEX', width - padding.right - 65, padding.top + 10)

    ctx.fillStyle = '#ff5252'
    ctx.fillRect(width - padding.right - 80, padding.top + 20, 12, 12)
    ctx.fillStyle = '#fff'
    ctx.fillText('Put GEX', width - padding.right - 65, padding.top + 30)

  }, [data, currentPrice])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Activity className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">GEX ANALYSIS</h1>
            <p className="text-xs text-foreground-muted">Gamma Exposure by Strike</p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="card p-4">
        <div className="flex items-end gap-4 flex-wrap">
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="input w-24"
            />
          </div>
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Max DTE</label>
            <input
              type="number"
              value={maxDte}
              onChange={(e) => setMaxDte(Number(e.target.value))}
              className="input w-20"
            />
          </div>
          <button onClick={analyze} disabled={loading} className="btn-primary flex items-center gap-2">
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
            Analyze
          </button>
          <div className="flex items-center gap-1 ml-4">
            {quickTickers.map(t => (
              <button
                key={t}
                onClick={() => { setTicker(t); setTimeout(analyze, 100) }}
                className={cn(
                  'px-2 py-1 text-xs rounded transition-colors',
                  ticker === t
                    ? 'bg-accent-primary text-background-primary'
                    : 'bg-background-tertiary text-foreground-secondary hover:text-foreground-primary'
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Chart */}
        <div className="col-span-9 card p-4">
          <h3 className="text-sm font-bold text-foreground-primary mb-4">Gamma Exposure Distribution</h3>
          <canvas ref={canvasRef} className="w-full h-[400px]" />
        </div>

        {/* Summary */}
        <div className="col-span-3 space-y-4">
          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">GEX METRICS</h3>
            <div className="space-y-3">
              <div className="bg-background-tertiary p-3 rounded">
                <div className="text-xs text-foreground-muted">Net GEX</div>
                <div className={cn(
                  'text-xl font-mono font-bold',
                  summary.net_gex >= 0 ? 'text-bullish' : 'text-bearish'
                )}>
                  {summary.net_gex >= 0 ? '+' : ''}{summary.net_gex.toFixed(2)}B
                </div>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">Call GEX</span>
                <span className="text-xs font-mono text-bullish">+{summary.total_call_gex.toFixed(2)}B</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">Put GEX</span>
                <span className="text-xs font-mono text-bearish">{summary.total_put_gex.toFixed(2)}B</span>
              </div>
            </div>
          </div>

          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">KEY LEVELS</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">Current Price</span>
                <span className="text-xs font-mono font-bold text-accent-primary">${currentPrice.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">GEX Flip Point</span>
                <span className="text-xs font-mono">${summary.gex_flip_point.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-foreground-muted">Max Pain</span>
                <span className="text-xs font-mono">${summary.max_pain.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div className="card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">MARKET STRUCTURE</h3>
            <div className={cn(
              'p-3 rounded text-center',
              summary.net_gex >= 0 ? 'bg-bullish/10' : 'bg-bearish/10'
            )}>
              <div className="text-xs text-foreground-muted mb-1">Regime</div>
              <div className={cn(
                'text-lg font-bold',
                summary.net_gex >= 0 ? 'text-bullish' : 'text-bearish'
              )}>
                {summary.net_gex >= 0 ? 'POSITIVE GEX' : 'NEGATIVE GEX'}
              </div>
              <div className="text-xs text-foreground-muted mt-1">
                {summary.net_gex >= 0
                  ? 'Dealers short gamma - expect mean reversion'
                  : 'Dealers long gamma - expect volatility'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
