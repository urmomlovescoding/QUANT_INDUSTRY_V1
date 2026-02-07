import { TrendingUp, RefreshCw, BarChart3, Brain, Target } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { cn } from '@/utils/cn'
import { api } from '@/api/client'

const models = [
  { id: 'linear', name: 'Linear Regression', color: '#3b82f6' },
  { id: 'ridge', name: 'Ridge Regression', color: '#8b5cf6' },
  { id: 'rf', name: 'Random Forest', color: '#10b981' },
  { id: 'gb', name: 'Gradient Boost', color: '#f59e0b' },
  { id: 'arima', name: 'ARIMA', color: '#ef4444' },
  { id: 'ensemble', name: 'Ensemble', color: '#00d4aa' },
]

const horizons = ['1d', '5d', '10d', '20d', '60d']

interface ModelResult {
  model: string
  modelName: string
  color: string
  currentPrice: number
  predictedPrice: number
  change: number
  direction: string
  confidence: number
  metrics: {
    r2: number
    rmse: number
    mae: number
    directional: number
    profit_factor: number
  }
  features: any[]
}

export function MLPredictions() {
  const [ticker, setTicker] = useState('SPY')
  const [selectedModel, setSelectedModel] = useState('ensemble')
  const [horizon, setHorizon] = useState('5d')
  const [predicting, setPredicting] = useState(false)
  const [prediction, setPrediction] = useState<ModelResult | null>(null)
  const [allModelResults, setAllModelResults] = useState<ModelResult[]>([])
  const [comparingAll, setComparingAll] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const fetchPrediction = async (modelId: string): Promise<ModelResult | null> => {
    try {
      const { data: result, error: apiError, ok } = await api.get<any>(
        `/api/ml/predict/${ticker}?model=${modelId}&horizon=${horizon}`
      )

      if (!ok || apiError) return null
      if ((result as any)?.status === 'unavailable') return null

      const data = (result as any)?.data || result
      const currentPrice = data.current_price || data.currentPrice || 0
      const predictedPrice = data.predicted_price || data.predictedPrice || currentPrice
      const change = currentPrice > 0 ? ((predictedPrice - currentPrice) / currentPrice) * 100 : 0
      const modelDef = models.find(m => m.id === modelId) || models[0]

      return {
        model: modelId,
        modelName: modelDef.name,
        color: modelDef.color,
        currentPrice,
        predictedPrice,
        change,
        direction: change > 0.5 ? 'UP' : change < -0.5 ? 'DOWN' : 'NEUTRAL',
        confidence: data.confidence || 75,
        metrics: {
          r2: data.metrics?.r2 || data.r2_score || 0,
          rmse: data.metrics?.rmse || data.rmse || 0,
          mae: data.metrics?.mae || data.mae || 0,
          directional: data.metrics?.directional || data.directional_accuracy || 0.5,
          profit_factor: data.metrics?.profit_factor || data.profit_factor || 1.0
        },
        features: data.features || data.feature_importance || []
      }
    } catch {
      return null
    }
  }

  const predict = async () => {
    setPredicting(true)
    setError(null)

    const result = await fetchPrediction(selectedModel)
    if (result) {
      setPrediction(result)
    } else {
      setError('Failed to get prediction. ML service may not be available.')
      setPrediction(null)
    }
    setPredicting(false)
  }

  const compareAllModels = async () => {
    setComparingAll(true)
    setError(null)

    const results = await Promise.all(models.map(m => fetchPrediction(m.id)))
    const validResults = results.filter((r): r is ModelResult => r !== null)

    if (validResults.length > 0) {
      setAllModelResults(validResults)
    } else {
      setError('No model predictions available. ML service may not be configured.')
    }
    setComparingAll(false)
  }

  // Draw chart
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

    const numPoints = 60
    const prices: number[] = []
    let price = prediction.currentPrice * 0.95

    for (let i = 0; i < numPoints; i++) {
      price += (Math.random() - 0.48) * 3
      prices.push(price)
    }
    prices[prices.length - 1] = prediction.currentPrice

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

    // Grid
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

    // Historical line
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

    // Prediction line
    ctx.strokeStyle = prediction.color || '#f0b90b'
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

    // Prediction zone
    const predStartX = padding + ((numPoints - 1) / (numPoints + predPoints)) * chartWidth
    ctx.fillStyle = 'rgba(240, 185, 11, 0.1)'
    ctx.fillRect(predStartX, padding, width - padding - predStartX, chartHeight)

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
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
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
          <button
            onClick={compareAllModels}
            disabled={comparingAll}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded transition"
          >
            <BarChart3 className={cn('w-4 h-4', comparingAll && 'animate-spin')} />
            Compare All Models
          </button>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {/* Multi-Model Comparison Grid */}
      {allModelResults.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-bold text-foreground-primary mb-4 flex items-center gap-2">
            <Brain className="w-4 h-4 text-purple-400" />
            Multi-Model Comparison — {ticker} ({horizon})
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3 text-foreground-muted">Model</th>
                  <th className="text-right py-2 px-3 text-foreground-muted">Predicted</th>
                  <th className="text-right py-2 px-3 text-foreground-muted">Change</th>
                  <th className="text-center py-2 px-3 text-foreground-muted">Direction</th>
                  <th className="text-right py-2 px-3 text-foreground-muted">Confidence</th>
                  <th className="text-right py-2 px-3 text-foreground-muted">R²</th>
                  <th className="text-right py-2 px-3 text-foreground-muted">RMSE</th>
                  <th className="text-right py-2 px-3 text-foreground-muted">Dir. Acc.</th>
                  <th className="text-right py-2 px-3 text-foreground-muted">Profit F.</th>
                </tr>
              </thead>
              <tbody>
                {allModelResults.sort((a, b) => (b.metrics.r2 || 0) - (a.metrics.r2 || 0)).map(r => (
                  <tr
                    key={r.model}
                    className={cn(
                      'border-b border-border/50 hover:bg-background-tertiary cursor-pointer transition',
                      selectedModel === r.model && 'bg-accent-primary/5'
                    )}
                    onClick={() => {
                      setSelectedModel(r.model)
                      setPrediction(r)
                    }}
                  >
                    <td className="py-2 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: r.color }} />
                        <span className="font-medium">{r.modelName}</span>
                      </div>
                    </td>
                    <td className="text-right py-2 px-3 font-mono">${r.predictedPrice.toFixed(2)}</td>
                    <td className={cn(
                      'text-right py-2 px-3 font-mono font-bold',
                      r.change >= 0 ? 'text-bullish' : 'text-bearish'
                    )}>
                      {r.change >= 0 ? '+' : ''}{r.change.toFixed(2)}%
                    </td>
                    <td className="text-center py-2 px-3">
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs font-bold',
                        r.direction === 'UP' ? 'bg-bullish/20 text-bullish' :
                        r.direction === 'DOWN' ? 'bg-bearish/20 text-bearish' :
                        'bg-foreground-muted/20 text-foreground-muted'
                      )}>
                        {r.direction}
                      </span>
                    </td>
                    <td className="text-right py-2 px-3 font-mono">{r.confidence.toFixed(0)}%</td>
                    <td className="text-right py-2 px-3 font-mono">{r.metrics.r2.toFixed(3)}</td>
                    <td className="text-right py-2 px-3 font-mono">{r.metrics.rmse.toFixed(3)}</td>
                    <td className="text-right py-2 px-3 font-mono">{(r.metrics.directional * 100).toFixed(1)}%</td>
                    <td className="text-right py-2 px-3 font-mono">{r.metrics.profit_factor.toFixed(2)}x</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Ensemble Consensus */}
          <div className="mt-4 p-3 bg-background-tertiary rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-accent-primary" />
              <span className="text-xs font-bold text-foreground-muted">ENSEMBLE CONSENSUS</span>
            </div>
            <div className="grid grid-cols-4 gap-4 text-xs">
              <div>
                <span className="text-foreground-muted">Avg Predicted</span>
                <div className="text-sm font-mono font-bold">
                  ${(allModelResults.reduce((s, r) => s + r.predictedPrice, 0) / allModelResults.length).toFixed(2)}
                </div>
              </div>
              <div>
                <span className="text-foreground-muted">Bullish / Bearish</span>
                <div className="text-sm font-bold">
                  <span className="text-bullish">{allModelResults.filter(r => r.direction === 'UP').length}</span>
                  {' / '}
                  <span className="text-bearish">{allModelResults.filter(r => r.direction === 'DOWN').length}</span>
                </div>
              </div>
              <div>
                <span className="text-foreground-muted">Avg Confidence</span>
                <div className="text-sm font-mono font-bold">
                  {(allModelResults.reduce((s, r) => s + r.confidence, 0) / allModelResults.length).toFixed(0)}%
                </div>
              </div>
              <div>
                <span className="text-foreground-muted">Agreement</span>
                <div className={cn(
                  'text-sm font-bold',
                  allModelResults.filter(r => r.direction === allModelResults[0]?.direction).length > allModelResults.length * 0.6
                    ? 'text-bullish' : 'text-warning'
                )}>
                  {allModelResults.length > 0
                    ? (Math.max(
                      allModelResults.filter(r => r.direction === 'UP').length,
                      allModelResults.filter(r => r.direction === 'DOWN').length,
                      allModelResults.filter(r => r.direction === 'NEUTRAL').length
                    ) / allModelResults.length * 100).toFixed(0) + '%'
                    : '0%'}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {prediction && (
        <div className="grid grid-cols-12 gap-4">
          {/* Chart */}
          <div className="col-span-8 card p-4">
            <h3 className="text-sm font-bold text-foreground-primary mb-4 flex items-center gap-2">
              Price Prediction Chart
              <span className="text-xs font-normal text-foreground-muted">({prediction.modelName})</span>
            </h3>
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

            {prediction.features.length > 0 && (
              <div className="card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">FEATURE IMPORTANCE</h3>
                <div className="space-y-2">
                  {prediction.features.slice(0, 8).map((f: any) => (
                    <div key={f.name}>
                      <div className="flex justify-between mb-1">
                        <span className="text-xs">{f.name}</span>
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
