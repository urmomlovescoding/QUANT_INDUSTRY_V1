import { Shield, AlertTriangle, CheckCircle } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'
import { GaugeChart } from '@/components/charts/GaugeChart'

interface RiskLimit {
  name: string
  current: number
  limit: number
  unit: string
}

export function RiskEngine() {
  const [riskScore] = useState(42)
  const [limits] = useState<RiskLimit[]>([
    { name: 'Max Position Size', current: 12, limit: 15, unit: '%' },
    { name: 'Sector Concentration', current: 38, limit: 40, unit: '%' },
    { name: 'Max Drawdown', current: 8.5, limit: 15, unit: '%' },
    { name: 'Daily Loss', current: 1.2, limit: 3, unit: '%' },
    { name: 'VaR 95%', current: 3.2, limit: 5, unit: '%' },
  ])

  const [alerts] = useState([
    { type: 'warning', message: 'Sector concentration approaching limit (38%)' },
    { type: 'info', message: 'VaR within acceptable range (3.2%)' },
    { type: 'success', message: 'Daily loss well under limit' },
  ])

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

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <Shield className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-accent-primary">RISK ENGINE DASHBOARD</h1>
          <p className="text-xs text-foreground-muted">Real-time risk monitoring and alerts</p>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Risk Score */}
        <div className="col-span-4 card p-6">
          <h3 className="text-xs font-bold text-foreground-muted mb-4 text-center">OVERALL RISK SCORE</h3>
          <div className="flex justify-center">
            <GaugeChart value={riskScore} maxValue={100} label="Risk Level" />
          </div>
          <div className="text-center mt-4">
            <span className={cn(
              'text-lg font-bold',
              riskScore < 30 ? 'text-bullish' : riskScore < 60 ? 'text-warning' : 'text-bearish'
            )}>
              {riskScore < 30 ? 'LOW RISK' : riskScore < 60 ? 'MODERATE RISK' : 'HIGH RISK'}
            </span>
          </div>
        </div>

        {/* Risk Limits */}
        <div className="col-span-5 card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">RISK LIMITS</h3>
          <div className="space-y-4">
            {limits.map((limit, i) => (
              <div key={i}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-foreground-secondary">{limit.name}</span>
                  <span className={cn('text-xs font-mono font-bold', getStatusColor(limit.current, limit.limit))}>
                    {limit.current}{limit.unit} / {limit.limit}{limit.unit}
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
          <div className="space-y-2">
            {alerts.map((alert, i) => (
              <div
                key={i}
                className={cn(
                  'p-2 rounded flex items-start gap-2',
                  alert.type === 'warning' ? 'bg-warning/10' :
                  alert.type === 'success' ? 'bg-bullish/10' : 'bg-accent-primary/10'
                )}
              >
                {alert.type === 'warning' && <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0 mt-0.5" />}
                {alert.type === 'success' && <CheckCircle className="w-4 h-4 text-bullish flex-shrink-0 mt-0.5" />}
                {alert.type === 'info' && <Shield className="w-4 h-4 text-accent-primary flex-shrink-0 mt-0.5" />}
                <span className="text-xs">{alert.message}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Position Heat Map */}
        <div className="col-span-6 card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">POSITION HEAT MAP</h3>
          <div className="grid grid-cols-5 gap-2">
            {['NVDA', 'AAPL', 'MSFT', 'AMD', 'GOOGL', 'META', 'AMZN', 'TSLA', 'QQQ', 'SPY'].map((symbol) => {
              const pnl = (Math.random() - 0.4) * 10
              return (
                <div
                  key={symbol}
                  className={cn(
                    'p-3 rounded text-center',
                    pnl >= 2 ? 'bg-bullish' : pnl >= 0 ? 'bg-bullish/50' : pnl >= -2 ? 'bg-bearish/50' : 'bg-bearish'
                  )}
                >
                  <div className="text-xs font-bold">{symbol}</div>
                  <div className="text-sm font-mono">{pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%</div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Correlation Matrix */}
        <div className="col-span-6 card p-4">
          <h3 className="text-xs font-bold text-foreground-muted mb-4">CORRELATION MONITOR</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr>
                  <th className="p-1"></th>
                  {['SPY', 'QQQ', 'IWM', 'TLT', 'GLD'].map(s => (
                    <th key={s} className="p-1 text-center">{s}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {['SPY', 'QQQ', 'IWM', 'TLT', 'GLD'].map((s1, i) => (
                  <tr key={s1}>
                    <td className="p-1 font-medium">{s1}</td>
                    {['SPY', 'QQQ', 'IWM', 'TLT', 'GLD'].map((s2, j) => {
                      const corr = i === j ? 1 : (
                        (s1 === 'TLT' || s2 === 'TLT') ? -0.3 + Math.random() * 0.2 :
                        (s1 === 'GLD' || s2 === 'GLD') ? 0.1 + Math.random() * 0.3 :
                        0.7 + Math.random() * 0.25
                      )
                      return (
                        <td
                          key={s2}
                          className={cn(
                            'p-1 text-center font-mono',
                            corr > 0.8 ? 'bg-bearish/30' :
                            corr > 0.5 ? 'bg-warning/30' :
                            corr < 0 ? 'bg-bullish/30' : ''
                          )}
                        >
                          {corr.toFixed(2)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-foreground-muted mt-2">
            High correlation detected between equity positions. Consider diversification.
          </p>
        </div>
      </div>
    </div>
  )
}
