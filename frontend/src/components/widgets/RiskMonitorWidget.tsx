/**
 * Risk Monitor Widget - Real-time risk metrics display
 */

import { useEffect, useState } from 'react'
import { 
  AlertTriangle, 
  Shield, 
  TrendingDown, 
  Activity,
  Bell,
  CheckCircle,
  XCircle
} from 'lucide-react'

interface RiskAlert {
  timestamp: string
  type: string
  severity: 'info' | 'warning' | 'critical' | 'emergency'
  message: string
  metric: string
  current: number
  threshold: number
  acknowledged: boolean
}

interface RiskSummary {
  status: string
  portfolio: {
    equity: number
    drawdown_pct: number
    daily_pnl: number
    daily_loss_pct: number
  }
  risk_metrics: {
    var_95_pct: number
    position_count: number
  }
  alerts: {
    active_count: number
    total_generated: number
    critical_count: number
  }
}

export function RiskMonitorWidget() {
  const [riskData, setRiskData] = useState<RiskSummary | null>(null)
  const [alerts, setAlerts] = useState<RiskAlert[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchRiskData = async () => {
      try {
        const [summaryRes, alertsRes] = await Promise.all([
          fetch('/api/risk/summary'),
          fetch('/api/risk/alerts')
        ])
        
        if (summaryRes.ok) {
          setRiskData(await summaryRes.json())
        }
        if (alertsRes.ok) {
          setAlerts(await alertsRes.json())
        }
      } catch (error) {
        console.error('Failed to fetch risk data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchRiskData()
    const interval = setInterval(fetchRiskData, 5000) // Refresh every 5s
    return () => clearInterval(interval)
  }, [])

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'emergency': return 'text-red-500 bg-red-500/20'
      case 'critical': return 'text-orange-500 bg-orange-500/20'
      case 'warning': return 'text-yellow-500 bg-yellow-500/20'
      default: return 'text-blue-500 bg-blue-500/20'
    }
  }

  const getHealthStatus = () => {
    if (!riskData) return { color: 'text-slate-400', label: 'Unknown', icon: Activity }
    
    const { drawdown_pct, daily_loss_pct } = riskData.portfolio
    const { active_count } = riskData.alerts
    
    if (active_count > 0 && alerts.some(a => a.severity === 'critical' || a.severity === 'emergency')) {
      return { color: 'text-red-500', label: 'CRITICAL', icon: XCircle }
    }
    if (drawdown_pct > 5 || daily_loss_pct > 2) {
      return { color: 'text-yellow-500', label: 'Warning', icon: AlertTriangle }
    }
    return { color: 'text-green-500', label: 'Healthy', icon: CheckCircle }
  }

  const health = getHealthStatus()
  const HealthIcon = health.icon

  if (isLoading) {
    return (
      <div className="card p-4 animate-pulse">
        <div className="h-4 bg-background-tertiary rounded w-1/3 mb-4"></div>
        <div className="space-y-3">
          <div className="h-8 bg-background-tertiary rounded"></div>
          <div className="h-8 bg-background-tertiary rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium flex items-center gap-2">
          <Shield className="w-4 h-4 text-cyan-400" />
          Risk Monitor
        </h3>
        <div className={`flex items-center gap-1.5 text-xs font-medium ${health.color}`}>
          <HealthIcon className="w-3.5 h-3.5" />
          {health.label}
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-background-tertiary rounded-lg p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-foreground-muted">Drawdown</span>
            <TrendingDown className="w-3 h-3 text-foreground-muted" />
          </div>
          <div className={`text-lg font-bold ${
            (riskData?.portfolio.drawdown_pct ?? 0) > 5 ? 'text-red-400' : 'text-foreground-primary'
          }`}>
            {(riskData?.portfolio.drawdown_pct ?? 0).toFixed(1)}%
          </div>
        </div>
        
        <div className="bg-background-tertiary rounded-lg p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-foreground-muted">VaR 95%</span>
            <Activity className="w-3 h-3 text-foreground-muted" />
          </div>
          <div className={`text-lg font-bold ${
            (riskData?.risk_metrics.var_95_pct ?? 0) > 5 ? 'text-yellow-400' : 'text-foreground-primary'
          }`}>
            {(riskData?.risk_metrics.var_95_pct ?? 0).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Alert Summary */}
      <div className="flex items-center justify-between text-xs mb-3">
        <span className="text-foreground-muted">Active Alerts</span>
        <div className="flex items-center gap-2">
          <Bell className="w-3 h-3" />
          <span className={riskData?.alerts.active_count ? 'text-yellow-400 font-medium' : 'text-foreground-muted'}>
            {riskData?.alerts.active_count ?? 0}
          </span>
        </div>
      </div>

      {/* Recent Alerts */}
      {alerts.length > 0 && (
        <div className="space-y-2 max-h-32 overflow-y-auto">
          {alerts.slice(0, 3).map((alert, idx) => (
            <div
              key={idx}
              className={`text-xs p-2 rounded flex items-start gap-2 ${getSeverityColor(alert.severity)}`}
            >
              <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{alert.message}</div>
                <div className="text-[10px] opacity-70">
                  {new Date(alert.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {alerts.length === 0 && (
        <div className="text-center text-xs text-foreground-muted py-4">
          <CheckCircle className="w-5 h-5 mx-auto mb-1 text-green-400" />
          No active alerts
        </div>
      )}
    </div>
  )
}
