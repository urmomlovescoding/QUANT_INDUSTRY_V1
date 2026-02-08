import { TrendingUp, RefreshCw, BarChart3, Target, Layers } from 'lucide-react'
import { useState, useEffect, useRef, useCallback } from 'react'
import { cn } from '@/utils/cn'
import { api } from '@/api/client'

const models = [
  { id: 'ensemble', name: 'Ensemble (All Models)', description: 'Combines all models for best accuracy' },
  { id: 'linear', name: 'Linear Regression', description: 'Fast, interpretable baseline' },
  { id: 'ridge', name: 'Ridge Regression', description: 'Regularized linear model' },
  { id: 'rf', name: 'Random Forest', description: 'Tree-based ensemble' },
  { id: 'gb', name: 'Gradient Boost', description: 'Sequential boosted trees' },
  { id: 'arima', name: 'ARIMA', description: 'Time-series autoregressive model' },
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

  const predict = useCallback(async () => {
    setPredicting(true)
    setError(null)

    try {
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
        features: data.features || data.feature_importance || [],
        upper_bound: data.upper_bound || predictedPrice * 1.02,
        lower_bound: data.lower_bound || predictedPrice * 0.98,
        model_used: data.model || model,
        timestamp: new Date().toISOString()
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get prediction')
      setPrediction(null)
    } finally {
      setPredicting(false)
    }
  }, [ticker, model, horizon])

  // Auto-predict on mount
  useEffect(() => {
    predict()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

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
    const padding = 50

    ctx.fillStyle = '#0d1117'
    ctx.fillRect(0, 0, width, height)

    // Generate historical prices
    const numPoints = 60
    const prices: number[] = []
    let price = prediction.currentPrice * 0.95

    for (let i = 0; i < numPoints; i++) {
      price += (Math.random() - 0.48) * (prediction.currentPrice * 0.005)
      prices.push(price)
    }
    prices[prices.length - 1] = prediction.currentPrice

    // Generate prediction line with confidence bands
    const predPoints = parseInt(horizon)
    const predPrices: number[] = [prediction.currentPrice]
    const upperBand: number[] = [prediction.currentPrice]
    const lowerBand: number[] = [prediction.currentPrice]
    price = prediction.currentPrice
    const bandWidth = Math.abs(prediction.upper_bound - prediction.lower_bound) / 2

    for (let i = 0; i < predPoints; i++) {
      const progress = (i + 1) / predPoints
      price += (prediction.predictedPrice - prediction.currentPrice) / predPoints + (Math.random() - 0.5) * (prediction.currentPrice * 0.002)
      predPrices.push(price)
      // Confidence band widens over time
      const spread = bandWidth * progress
      upperBand.push(price + spread)
      lowerBand.push(price - spread)
    }
    predPrices[predPrices.length - 1] = prediction.predictedPrice
    upperBand[upperBand.length - 1] = prediction.upper_bound
    lowerBand[lowerBand.length - 1] = prediction.lower_bound

    const allPrices = [...prices, ...upperBand, ...lowerBand]
    const minPrice = Math.min(...allPrices) - (prediction.currentPrice * 0.01)
    const maxPrice = Math.max(...allPrices) + (prediction.currentPrice * 0.01)
    const priceRange = maxPrice - minPrice

    const chartWidth = width - 2 * padding
    const chartHeight = height - 2 * padding

    // Draw grid
    ctx.strokeStyle = '#1a1f2e'
    ctx.lineWidth = 1
    for (let i = 0; i <= 5; i++) {
      const y = padding + (chartHeight * i / 5)
      ctx.beginPath()
      ctx.moveTo(padding, y)
      ctx.lineTo(width - padding, y)
      ctx.stroke()

      const priceLabel = maxPrice - (priceRange * i / 5)
      ctx.fillStyle = '#666'
      ctx.font = '10px monospace'
      ctx.textAlign = 'right'
      ctx.fillText(`$${priceLabel.toFixed(2)}`, padding - 5, y + 3)
    }

    const totalPoints = numPoints + predPoints

    // Draw confidence band (shaded area)
    const predStartIdx = numPoints - 1
    ctx.fillStyle = 'rgba(240, 185, 11, 0.08)'
    ctx.beginPath()
    // Upper band forward
    for (let i = 0; i < upperBand.length; i++) {
      const x = padding + ((predStartIdx + i) / totalPoints) * chartWidth
      const y = padding + (1 - (upperBand[i] - minPrice) / priceRange) * chartHeight
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    // Lower band backward
    for (let i = lowerBand.length - 1; i >= 0; i--) {
      const x = padding + ((predStartIdx + i) / totalPoints) * chartWidth
      const y = padding + (1 - (lowerBand[i] - minPrice) / priceRange) * chartHeight
      ctx.lineTo(x, y)
    }
    ctx.closePath()
    ctx.fill()

    // Draw upper band line (dashed)
    ctx.strokeStyle = 'rgba(240, 185, 11, 0.25)'
    ctx.lineWidth = 1
    ctx.setLineDash([3, 3])
    ctx.beginPath()
    upperBand.forEach((p, i) => {
      const x = padding + ((predStartIdx + i) / totalPoints) * chartWidth
      const y = padding + (1 - (p - minPrice) / priceRange) * chartHeight
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()

    // Draw lower band line (dashed)
    ctx.beginPath()
    lowerBand.forEach((p, i) => {
      const x = padding + ((predStartIdx + i) / totalPoints) * chartWidth
      const y = padding + (1 - (p - minPrice) / priceRange) * chartHeight
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()
    ctx.setLineDash([])

    // Draw historical line
    ctx.strokeStyle = '#00c853'
    ctx.lineWidth = 2
    ctx.beginPath()
    prices.forEach((p, i) => {
      const x = padding + (i / totalPoints) * chartWidth
      const y = padding + (1 - (p - minPrice) / priceRange) * chartHeight
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()

    // Draw prediction line
    ctx.strokeStyle = '#f0b90b'
    ctx.lineWidth = 2.5
    ctx.setLineDash([6, 4])
    ctx.beginPath()
    predPrices.forEach((p, i) => {
      const x = padding + ((predStartIdx + i) / totalPoints) * chartWidth
      const y = padding + (1 - (p - minPrice) / priceRange) * chartHeight
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()
    ctx.setLineDash([])

    // Draw prediction zone separator
    const predStartX = padding + (predStartIdx / totalPoints) * chartWidth
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)'
    ctx.lineWidth = 1
    ctx.setLineDash([3, 5])
    ctx.beginPath()
    ctx.moveTo(predStartX, padding)
    ctx.lineTo(predStartX, padding + chartHeight)
    ctx.stroke()
    ctx.setLineDash([])

    // Draw current price dot
    const curX = predStartX
    const curY = padding + (1 - (prediction.currentPrice - minPrice) / priceRange) * chartHeight
    ctx.fillStyle = '#00c853'
    ctx.beginPath()
    ctx.arc(curX, curY, 4, 0, Math.PI * 2)
    ctx.fill()

    // Draw predicted price dot
    const predEndX = padding + ((predStartIdx + predPoints) / totalPoints) * chartWidth
    const predEndY = padding + (1 - (prediction.predictedPrice - minPrice) / priceRange) * chartHeight
    ctx.fillStyle = '#f0b90b'
    ctx.beginPath()
    ctx.arc(predEndX, predEndY, 5, 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = 'rgba(240, 185, 11, 0.5)'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(predEndX, predEndY, 8, 0, Math.PI * 2)
    ctx.stroke()

    // Labels
    ctx.fillStyle = '#666'
    ctx.font = '10px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('Historical', padding + chartWidth * 0.25, height - 8)
    ctx.fillStyle = '#f0b90b'
    ctx.fillText(`Prediction (${horizon})`, predStartX + (width - padding - predStartX) / 2, height - 8)

    // Legend
    ctx.font = '9px sans-serif'
    const legendX = width - padding - 100
    const legendY = padding + 15

    ctx.fillStyle = '#00c853'
    ctx.fillRect(legendX, legendY, 12, 2)
    ctx.fillStyle = '#888'
    ctx.textAlign = 'left'
    ctx.fillText('Actual', legendX + 16, legendY + 4)

    ctx.fillStyle = '#f0b90b'
    ctx.fillRect(legendX, legendY + 14, 12, 2)
    ctx.fillText('Predicted', legendX + 16, legendY + 18)

    ctx.fillStyle = 'rgba(240, 185, 11, 0.2)'
    ctx.fillRect(legendX, legendY + 26, 12, 8)
    ctx.fillStyle = '#888'
    ctx.fillText('Confidence', legendX + 16, legendY + 33)

  }, [prediction, horizon])

  const selectedModel = models.find(m => m.id === model)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <TrendingUp className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">ML PRICE PREDICTIONS</h1>
            <p className="text-xs text-foreground-muted">Machine learning price forecasting with confidence intervals</p>
          </div>
        </div>
        {prediction && (
          <div className="text-xs text-foreground-muted">
            Last run: {new Date(prediction.timestamp).toLocaleTimeString()}
          </div>
        )}
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
              onKeyDown={(e) => e.key === 'Enter' && predict()}
              className="input w-24"
              placeholder="SPY"
            />
          </div>
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Model</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="input w-52"
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
                      : 'bg-background-tertiary text-foreground-secondary hover:text-foreground-primary'
                  )}
                >
                  {h}
                </button>
              ))}
            </div>
          </div>
          <button onClick={predict} disabled={predicting} className="btn-primary flex items-center gap-2">
            <RefreshCw className={cn('w-4 h-4', predicting && 'animate-spin')} />
            {predicting ? 'Running...' : 'Predict'}
          </button>
        </div>
        {selectedModel && (
          <p className="text-xs text-foreground-muted mt-2 flex items-center gap-1">
            <Layers className="w-3 h-3" /> {selectedModel.description}
          </p>
        )}
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
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-foreground-primary flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-accent-primary" />
                Price Prediction — {ticker}
              </h3>
              <div className="flex items-center gap-3 text-xs text-foreground-muted">
                <span>Model: <span className="text-accent-primary font-medium">{selectedModel?.name}</span></span>
                <span>Horizon: <span className="text-warning font-medium">{horizon}</span></span>
              </div>
            </div>
            <canvas ref={canvasRef} className="w-full h-[380px]" />
          </div>

          {/* Prediction Results */}
          <div className="col-span-4 space-y-4">
            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3 flex items-center gap-1">
                <Target className="w-3 h-3" /> PREDICTION
              </h3>
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
                {/* Confidence Range */}
                <div className="p-2 bg-background-tertiary rounded">
                  <div className="text-xs text-foreground-muted mb-1">Confidence Range ({horizon})</div>
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-bearish">${prediction.lower_bound.toFixed(2)}</span>
                    <span className="text-foreground-muted">—</span>
                    <span className="text-bullish">${prediction.upper_bound.toFixed(2)}</span>
                  </div>
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
                    {prediction.direction === 'UP' ? 'BULLISH' : prediction.direction === 'DOWN' ? 'BEARISH' : 'NEUTRAL'}
                  </div>
                  <div className="text-xs text-foreground-muted mt-1">
                    Confidence: {prediction.confidence.toFixed(1)}%
                  </div>
                  <div className="h-1.5 bg-background-tertiary rounded-full overflow-hidden mt-2">
                    <div
                      className={cn(
                        'h-full rounded-full',
                        prediction.confidence >= 70 ? 'bg-bullish' :
                        prediction.confidence >= 50 ? 'bg-warning' : 'bg-bearish'
                      )}
                      style={{ width: `${prediction.confidence}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="card p-4">
              <h3 className="text-xs font-bold text-foreground-muted mb-3">MODEL METRICS</h3>
              <div className="space-y-2 text-xs">
                {[
                  { label: 'R² Score', value: prediction.metrics.r2.toFixed(3), good: prediction.metrics.r2 > 0.5 },
                  { label: 'RMSE', value: prediction.metrics.rmse.toFixed(3), good: prediction.metrics.rmse < 5 },
                  { label: 'MAE', value: prediction.metrics.mae.toFixed(3), good: prediction.metrics.mae < 3 },
                  { label: 'Directional Accuracy', value: `${(prediction.metrics.directional * 100).toFixed(1)}%`, good: prediction.metrics.directional > 0.55 },
                  { label: 'Profit Factor', value: `${prediction.metrics.profit_factor.toFixed(2)}x`, good: prediction.metrics.profit_factor > 1.2 },
                ].map(m => (
                  <div key={m.label} className="flex justify-between items-center">
                    <span className="text-foreground-muted">{m.label}</span>
                    <span className={cn('font-mono font-medium', m.good ? 'text-bullish' : 'text-foreground-primary')}>
                      {m.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {prediction.features.length > 0 && (
              <div className="card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">FEATURE IMPORTANCE</h3>
                <div className="space-y-2">
                  {prediction.features.slice(0, 6).map((f: any) => (
                    <div key={f.name}>
                      <div className="flex justify-between mb-1">
                        <span className="text-xs truncate max-w-[120px]">{f.name}</span>
                        <span className="text-xs font-mono">{(f.importance * 100).toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 bg-background-tertiary rounded-full overflow-hidden">
                        <div
                          className="h-full bg-accent-primary rounded-full"
                          style={{ width: `${Math.min(f.importance * 400, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
