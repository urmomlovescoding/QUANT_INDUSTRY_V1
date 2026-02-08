import { TrendingUp, RefreshCw } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { cn } from '@/utils/cn'
import { api } from '@/api/client'

const models = [
  { id: 'linear', name: 'Linear Regression' },
  { id: 'ridge', name: 'Ridge Regression' },
  { id: 'rf', name: 'Random Forest' },
  { id: 'gb', name: 'Gradient Boost' },
  { id: 'arima', name: 'ARIMA' },
  { id: 'ensemble', name: 'Ensemble' },
]

const horizons = ['1d', '5d', '10d', '20d', '60d']

export function MLPredictions() {
  const [ticker, setTicker] = useState('SPY')
  const [model, setModel] = useState('ensemble')
  const [horizon, setHorizon] = useState('5d')
  const [predicting, setPredicting] = useState(false)
  const [prediction, setPrediction] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const predict = async () => {
    setPredicting(true)
    setError(null)

    try {
      // Using the base API client for ML predictions endpoint
      const { data: result, error: apiError, ok } = await api.get<any>(`/api/ml/predict/${ticker}?model=${model}&horizon=${horizon}`)

      if (!ok || apiError) {
        throw new Error(apiError?.message || 'Failed to get prediction')
      }

      if ((result as any)?.status === 'unavailable') {
        setError((result as any)?.message || 'ML predictions not available. Configure ML service to enable.')
        setPrediction(null)
        return
      }

      const data = (result as any)?.data || result
      const currentPrice = data.current_price || data.currentPrice || 0
      const predictedPrice = data.predicted_price || data.predictedPrice || currentPrice
      const change = currentPrice > 0 ? ((predictedPrice - currentPrice) / currentPrice) * 100 : 0

      setPrediction({
        currentPrice,
        predictedPrice,
        change,
        direction: change > 0.5 ? 'UP' : change < -0.5 ? 'DOWN' : 'NEUTRAL',
        confidence: data.confidence || 75,
        metrics: data.metrics || {
          r2: data.r2_score || 0,
          rmse: data.rmse || 0,
          mae: data.mae || 0,
          directional: data.directional_accuracy || 0.5,
          profit_factor: data.profit_factor || 1.0
        },
        features: data.features || data.feature_importance || []
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get prediction')
      setPrediction(null)
    } finally {
      setPredicting(false)
    }
  }

  useEffect(() => {
    if (!prediction || !canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * window.devicePixelRatio
    canvas.height = rect.height * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)

    const width = rect.width
    const height = rect.height
    const padding = 40

    ctx.fillStyle = '#0d1117'
    ctx.fillRect(0, 0, width, height)

    // Draw prediction summary on canvas (no fabricated price history)
    const chartWidth = width - 2 * padding
    const chartHeight = height - 2 * padding

    // Show current price and predicted price as reference points
    const currentY = padding + chartHeight * 0.5
    const predictedY = prediction.predictedPrice > prediction.currentPrice
      ? padding + chartHeight * 0.3
      : padding + chartHeight * 0.7
    const midX = padding + chartWidth * 0.5

    // Draw reference lines
    ctx.strokeStyle = '#1a1f2e'
    ctx.lineWidth = 1
    ctx.setLineDash([3, 3])
    ctx.beginPath()
    ctx.moveTo(padding, currentY)
    ctx.lineTo(width - padding, currentY)
    ctx.stroke()
    ctx.setLineDash([])

    // Current price marker
    ctx.fillStyle = '#00c853'
    ctx.beginPath()
    ctx.arc(padding + chartWidth * 0.3, currentY, 6, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#999'
    ctx.font = '11px monospace'
    ctx.textAlign = 'left'
    ctx.fillText(`Current: $${prediction.currentPrice.toFixed(2)}`, padding + chartWidth * 0.3 + 12, currentY + 4)

    // Predicted price marker
    ctx.fillStyle = '#f0b90b'
    ctx.beginPath()
    ctx.arc(padding + chartWidth * 0.7, predictedY, 6, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#999'
    ctx.fillText(`Predicted: $${prediction.predictedPrice.toFixed(2)}`, padding + chartWidth * 0.7 + 12, predictedY + 4)

    // Draw arrow from current to predicted
    ctx.strokeStyle = '#f0b90b'
    ctx.lineWidth = 2
    ctx.setLineDash([5, 5])
    ctx.beginPath()
    ctx.moveTo(padding + chartWidth * 0.3 + 6, currentY)
    ctx.lineTo(padding + chartWidth * 0.7 - 6, predictedY)
    ctx.stroke()
    ctx.setLineDash([])

    // Labels
    ctx.fillStyle = '#555'
    ctx.font = '10px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('No historical price data available', midX, height - 10)

  }, [prediction, horizon])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <TrendingUp className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-accent-primary">ML PRICE PREDICTIONS</h1>
          <p className="text-xs text-foreground-muted">Machine learning price forecasting</p>
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
            <label className="block text-xs text-foreground-muted mb-1">Model</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="input w-40"
            >
              {models.map(m => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Horizon</label>
            <div className="flex gap-1">
              {horizons.map(h => (
                <button
                  key={h}
                  onClick={() => setHorizon(h)}
                  className={cn(
                    'px-3 py-2 text-xs rounded transition-colors',
                    horizon === h
                      ? 'bg-accent-primary text-background-primary'
                      : 'bg-background-tertiary text-foreground-secondary'
                  )}
                >
                  {h}
                </button>
              ))}
            </div>
          </div>
          <button onClick={predict} disabled={predicting} className="btn-primary flex items-center gap-2">
            <RefreshCw className={cn('w-4 h-4', predicting && 'animate-spin')} />
            Predict
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {prediction && (
        <div className="grid grid-cols-12 gap-4">
          {/* Chart */}
          <div className="col-span-8 card p-4">
            <h3 className="text-sm font-bold text-foreground-primary mb-4">Price Prediction Chart</h3>
            <canvas ref={canvasRef} className="w-full h-[350px]" />
          </div>

          {/* Prediction Results */}
          <div className="col-span-4 space-y-4">
            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">PREDICTION</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Current Price</span>
                  <span className="text-sm font-mono">${prediction.currentPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Predicted Price</span>
                  <span className="text-sm font-mono font-bold text-accent-primary">${prediction.predictedPrice.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-foreground-muted">Expected Return</span>
                  <span className={cn(
                    'text-sm font-mono font-bold',
                    prediction.change >= 0 ? 'text-bullish' : 'text-bearish'
                  )}>
                    {prediction.change >= 0 ? '+' : ''}{prediction.change.toFixed(2)}%
                  </span>
                </div>
                <div className={cn(
                  'p-3 rounded text-center',
                  prediction.direction === 'UP' ? 'bg-bullish/10' :
                  prediction.direction === 'DOWN' ? 'bg-bearish/10' : 'bg-foreground-muted/10'
                )}>
                  <div className={cn(
                    'text-xl font-bold',
                    prediction.direction === 'UP' ? 'text-bullish' :
                    prediction.direction === 'DOWN' ? 'text-bearish' : 'text-foreground-muted'
                  )}>
                    {prediction.direction}
                  </div>
                  <div className="text-xs text-foreground-muted">
                    Confidence: {prediction.confidence.toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>

            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">MODEL METRICS</h3>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-foreground-muted">R² Score</span>
                  <span className="font-mono">{prediction.metrics.r2.toFixed(3)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">RMSE</span>
                  <span className="font-mono">{prediction.metrics.rmse.toFixed(3)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">MAE</span>
                  <span className="font-mono">{prediction.metrics.mae.toFixed(3)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Directional Accuracy</span>
                  <span className="font-mono">{(prediction.metrics.directional * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Profit Factor</span>
                  <span className="font-mono">{prediction.metrics.profit_factor.toFixed(2)}x</span>
                </div>
              </div>
            </div>

            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">FEATURE IMPORTANCE</h3>
              <div className="space-y-2">
                {prediction.features.map((f: any) => (
                  <div key={f.name}>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs">{f.name}</span>
                      <span className="text-xs font-mono">{(f.importance * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 bg-background-tertiary rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent-primary rounded-full"
                        style={{ width: `${f.importance * 400}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
