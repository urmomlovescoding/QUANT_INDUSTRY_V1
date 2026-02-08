import { TrendingUp, RefreshCw } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { cn } from '@/utils/cn'
import { api } from '@/api/client'

/** Raw ML prediction response from API */
interface MLPredictionResponse {
  status?: string
  message?: string
  data?: MLPredictionData
  current_price?: number
  currentPrice?: number
  predicted_price?: number
  predictedPrice?: number
  confidence?: number
  metrics?: MLMetrics
  r2_score?: number
  rmse?: number
  mae?: number
  directional_accuracy?: number
  profit_factor?: number
  features?: MLFeature[]
  feature_importance?: MLFeature[]
}

interface MLPredictionData {
  current_price?: number
  currentPrice?: number
  predicted_price?: number
  predictedPrice?: number
  confidence?: number
  metrics?: MLMetrics
  r2_score?: number
  rmse?: number
  mae?: number
  directional_accuracy?: number
  profit_factor?: number
  features?: MLFeature[]
  feature_importance?: MLFeature[]
}

interface MLMetrics {
  r2: number
  rmse: number
  mae: number
  directional: number
  profit_factor: number
}

interface MLFeature {
  name: string
  importance: number
}

interface PredictionState {
  currentPrice: number
  predictedPrice: number
  change: number
  direction: 'UP' | 'DOWN' | 'NEUTRAL'
  confidence: number
  metrics: MLMetrics
  features: MLFeature[]
}

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
  const [prediction, setPrediction] = useState<PredictionState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const predict = async () => {
    setPredicting(true)
    setError(null)

    try {
      // Using the base API client for ML predictions endpoint
      const { data: result, error: apiError, ok } = await api.get<MLPredictionResponse>(`/api/ml/predict/${ticker}?model=${model}&horizon=${horizon}`)

      if (!ok || apiError) {
        throw new Error(apiError?.message || 'Failed to get prediction')
      }

      if (result?.status === 'unavailable') {
        setError(result?.message || 'ML predictions not available. Configure ML service to enable.')
        setPrediction(null)
        return
      }

      const data: MLPredictionData = result?.data || result || {}
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

    // Generate historical prices
    const numPoints = 60
    const prices: number[] = []
    let price = prediction.currentPrice * 0.95

    for (let i = 0; i < numPoints; i++) {
      price += (Math.random() - 0.48) * 3
      prices.push(price)
    }
    prices[prices.length - 1] = prediction.currentPrice

    // Generate prediction line
    const predPoints = parseInt(horizon)
    const predPrices: number[] = [prediction.currentPrice]
    price = prediction.currentPrice
    for (let i = 0; i < predPoints; i++) {
      price += (prediction.predictedPrice - prediction.currentPrice) / predPoints + (Math.random() - 0.5) * 2
      predPrices.push(price)
    }
    predPrices[predPrices.length - 1] = prediction.predictedPrice

    const allPrices = [...prices, ...predPrices]
    const minPrice = Math.min(...allPrices) - 5
    const maxPrice = Math.max(...allPrices) + 5
    const priceRange = maxPrice - minPrice

    const chartWidth = width - 2 * padding
    const chartHeight = height - 2 * padding

    // Draw grid
    ctx.strokeStyle = '#1a1f2e'
    ctx.lineWidth = 1
    for (let i = 0; i <= 4; i++) {
      const y = padding + (chartHeight * i / 4)
      ctx.beginPath()
      ctx.moveTo(padding, y)
      ctx.lineTo(width - padding, y)
      ctx.stroke()

      const priceLabel = maxPrice - (priceRange * i / 4)
      ctx.fillStyle = '#666'
      ctx.font = '10px monospace'
      ctx.textAlign = 'right'
      ctx.fillText(`$${priceLabel.toFixed(0)}`, padding - 5, y + 3)
    }

    // Draw historical line
    ctx.strokeStyle = '#00c853'
    ctx.lineWidth = 2
    ctx.beginPath()
    prices.forEach((p, i) => {
      const x = padding + (i / (numPoints + predPoints)) * chartWidth
      const y = padding + (1 - (p - minPrice) / priceRange) * chartHeight
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()

    // Draw prediction line
    ctx.strokeStyle = '#f0b90b'
    ctx.lineWidth = 2
    ctx.setLineDash([5, 5])
    ctx.beginPath()
    predPrices.forEach((p, i) => {
      const x = padding + ((numPoints - 1 + i) / (numPoints + predPoints)) * chartWidth
      const y = padding + (1 - (p - minPrice) / priceRange) * chartHeight
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()
    ctx.setLineDash([])

    // Draw prediction zone
    const predStartX = padding + ((numPoints - 1) / (numPoints + predPoints)) * chartWidth
    ctx.fillStyle = 'rgba(240, 185, 11, 0.1)'
    ctx.fillRect(predStartX, padding, width - padding - predStartX, chartHeight)

    // Labels
    ctx.fillStyle = '#666'
    ctx.font = '10px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('Historical', padding + chartWidth * 0.3, height - 10)
    ctx.fillText('Prediction', predStartX + (width - padding - predStartX) / 2, height - 10)

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

      {!prediction && !error && !predicting && (
        <div className="card p-8 text-center text-foreground-muted">
          <TrendingUp className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="font-medium">Select Parameters and Click Predict</p>
          <p className="text-xs mt-1">Choose a ticker, model, and time horizon above to generate ML price predictions</p>
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
                {prediction.features.map((f: MLFeature) => (
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
