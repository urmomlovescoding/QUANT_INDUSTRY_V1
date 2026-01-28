import { useState, useEffect } from 'react'
import { Shield, AlertTriangle, CheckCircle, RefreshCw, AlertCircle, Info } from 'lucide-react'
import { cn } from '@/utils/cn'
import { GaugeChart } from '@/components/charts/GaugeChart'

interface RiskLimit {
  name: string
  current: number
  limit: number
  unit: string
}

interface RiskAlert {
  type: 'warning' | 'info' | 'success' | 'error'
  message: string
}

interface RiskMetrics {
  riskScore: number
  limits: RiskLimit[]
  alerts: RiskAlert[]
  status?: string
}

export function RiskEngine() {
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchRiskMetrics = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/risk/metrics')
      const data = await response.json()

      if (data.status === 'unavailable') {
        setMetrics(null)
      } else {
        // Transform API response
        const riskScore = data.overall_risk || data.riskScore || 0
        const limits: RiskLimit[] = [
          { name: 'Max Position Size', current: data.position_concentration || 0, limit: 15, unit: '%' },
          { name: 'Sector Concentration', current: data.sector_concentration || 0, limit: 40, unit: '%' },
          { name: 'Max Drawdown', current: Math.abs(data.max_drawdown || 0), limit: 15, unit: '%' },
          { name: 'Daily Loss', current: Math.abs(data.daily_loss || 0), limit: 3, unit: '%' },
          { name: 'VaR 95%', current: Math.abs(data.var_95 || 0), limit: 5, unit: '%' },
        ]

        const alerts: RiskAlert[] = data.alerts || []

        setMetrics({ riskScore, limits, alerts })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch risk metrics')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchRiskMetrics()
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchRiskMetrics, 30000)
    return () => clearInterval(interval)
  }, [])

  const getStatusColor = (current: number, limit: number) => {
    const ratio = current / limit
    if (ratio >= 0.9) return 'text-bearish'
    if (ratio >= 0.7) return 'text-warning'
    return 'text-bullish'
  }

  const getBarColor = (current: number, limit: number) => {
    const ratio = current / limit
    if (ratio >= 0.9) return 'bg-bearish'
    if (ratio >= 0.7) return 'bg-warning'
    return 'bg-bullish'
  }

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'warning': return <AlertTriangle className="w-4 h-4 text-warning" />
      case 'error': return <AlertCircle className="w-4 h-4 text-bearish" />
      case 'success': return <CheckCircle className="w-4 h-4 text-bullish" />
      default: return <Info className="w-4 h-4 text-accent-primary" />
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Shield className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">RISK ENGINE DASHBOARD</h1>
            <p className="text-xs text-foreground-muted">Real-time risk monitoring and alerts</p>
          </div>
        </div>
        <button
          onClick={fetchRiskMetrics}
          disabled={isLoading}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-accent-primary" />
        </div>
      ) : !metrics ? (
        <div className="card p-8 text-center text-foreground-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">No Risk Data Available</p>
          <p className="text-sm mt-2">Risk metrics will appear once you have positions or trading history</p>
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-4">
          {/* Risk Score */}
          <div className="col-span-4 card p-6">
            <h3 className="text-xs font-bold text-foreground-muted mb-4 text-center">OVERALL RISK SCORE</h3>
            <div className="flex justify-center">
              <GaugeChart value={metrics.riskScore} maxValue={100} label="Risk Level" />
            </div>
            <div className="text-center mt-4">
              <span className={cn(
                'text-lg font-bold',
                metrics.riskScore < 30 ? 'text-bullish' : metrics.riskScore < 60 ? 'text-warning' : 'text-bearish'
              )}>
                {metrics.riskScore < 30 ? 'LOW RISK' : metrics.riskScore < 60 ? 'MODERATE RISK' : 'HIGH RISK'}
              </span>
            </div>
          </div>

          {/* Risk Limits */}
          <div className="col-span-5 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">RISK LIMITS</h3>
            <div className="space-y-4">
              {metrics.limits.map((limit, i) => (
                <div key={i}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs text-foreground-secondary">{limit.name}</span>
                    <span className={cn('text-xs font-mono font-bold', getStatusColor(limit.current, limit.limit))}>
                      {limit.current.toFixed(1)}{limit.unit} / {limit.limit}{limit.unit}
                    </span>
                  </div>
                  <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
                    <div
                      className={cn('h-full rounded-full transition-all', getBarColor(limit.current, limit.limit))}
                      style={{ width: `${Math.min(100, (limit.current / limit.limit) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Alerts */}
          <div className="col-span-3 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-4">ALERTS</h3>
            {metrics.alerts.length === 0 ? (
              <div className="text-center text-foreground-muted py-8">
                <CheckCircle className="w-8 h-8 mx-auto mb-2 text-bullish opacity-50" />
                <p className="text-sm">No active alerts</p>
              </div>
            ) : (
              <div className="space-y-2">
                {metrics.alerts.map((alert, i) => (
                  <div key={i} className={cn(
                    'p-2 rounded-lg flex items-start gap-2',
                    alert.type === 'warning' && 'bg-warning/10',
                    alert.type === 'error' && 'bg-bearish/10',
                    alert.type === 'success' && 'bg-bullish/10',
                    alert.type === 'info' && 'bg-accent-primary/10'
                  )}>
                    {getAlertIcon(alert.type)}
                    <span className="text-xs">{alert.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
