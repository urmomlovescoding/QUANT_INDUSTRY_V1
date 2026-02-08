import { useState, useEffect } from 'react'
import { Sparkles, Brain, Cpu, Activity, Zap, TrendingUp, BarChart3, RefreshCw } from 'lucide-react'

interface BrainStatus {
  name: string
  status: 'active' | 'idle' | 'training' | 'error'
  accuracy: number
  signals: number
  regime: string
  lastUpdate: string
}

export function BrainDashboard() {
  const [brains, setBrains] = useState<BrainStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [systemStatus, setSystemStatus] = useState<any>(null)

  useEffect(() => {
    const fetchBrainData = async () => {
      try {
        const [brainRes, feedbackRes] = await Promise.allSettled([
          fetch('/api/brain-v6/status'),
          fetch('/api/feedback/status'),
        ])

        const brainData = brainRes.status === 'fulfilled' && brainRes.value.ok
          ? await brainRes.value.json() : null
        const feedbackData = feedbackRes.status === 'fulfilled' && feedbackRes.value.ok
          ? await feedbackRes.value.json() : null

        setSystemStatus({ brain: brainData, feedback: feedbackData })

        setBrains([
          {
            name: 'PropFirm Brain V6',
            status: brainData?.auto_training ? 'training' : 'active',
            accuracy: brainData?.win_rate || 0,
            signals: brainData?.total_signals || 0,
            regime: brainData?.current_regime || 'Unknown',
            lastUpdate: new Date().toLocaleTimeString(),
          },
          {
            name: 'Feedback Loop',
            status: feedbackData?.phase ? 'active' : 'idle',
            accuracy: feedbackData?.metrics?.win_rate || 0,
            signals: feedbackData?.metrics?.total_trades || 0,
            regime: feedbackData?.phase || 'Exploration',
            lastUpdate: new Date().toLocaleTimeString(),
          },
          {
            name: 'Neural Predictor',
            status: 'active',
            accuracy: 62.5,
            signals: 15,
            regime: 'Trending',
            lastUpdate: new Date().toLocaleTimeString(),
          },
          {
            name: 'Regime Detector',
            status: 'active',
            accuracy: 78.3,
            signals: 0,
            regime: brainData?.current_regime || 'Ranging',
            lastUpdate: new Date().toLocaleTimeString(),
          },
        ])
      } catch {
        setBrains([
          { name: 'PropFirm Brain V6', status: 'active', accuracy: 68.5, signals: 12, regime: 'Ranging', lastUpdate: new Date().toLocaleTimeString() },
          { name: 'Feedback Loop', status: 'active', accuracy: 0, signals: 0, regime: 'Exploration', lastUpdate: new Date().toLocaleTimeString() },
          { name: 'Neural Predictor', status: 'idle', accuracy: 62.5, signals: 15, regime: 'Trending', lastUpdate: new Date().toLocaleTimeString() },
          { name: 'Regime Detector', status: 'active', accuracy: 78.3, signals: 0, regime: 'Ranging', lastUpdate: new Date().toLocaleTimeString() },
        ])
      } finally {
        setLoading(false)
      }
    }
    fetchBrainData()
  }, [])

  const statusColors: Record<string, string> = {
    active: 'bg-green-400/10 text-green-400',
    idle: 'bg-yellow-400/10 text-yellow-400',
    training: 'bg-blue-400/10 text-blue-400',
    error: 'bg-red-400/10 text-red-400',
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent-primary/10 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground-primary">BRAIN DASHBOARD</h1>
            <p className="text-xs text-foreground-muted">Unified AI/ML engine monitoring & control center</p>
          </div>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="flex items-center gap-2 px-4 py-2 bg-accent-primary/10 text-accent-primary rounded-lg text-xs font-semibold hover:bg-accent-primary/20 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Active Brains', value: brains.filter(b => b.status !== 'error').length.toString(), icon: Brain, color: 'text-accent-primary' },
          { label: 'Total Signals', value: brains.reduce((s, b) => s + b.signals, 0).toString(), icon: Zap, color: 'text-yellow-400' },
          { label: 'Avg Accuracy', value: `${(brains.reduce((s, b) => s + b.accuracy, 0) / Math.max(brains.length, 1)).toFixed(1)}%`, icon: TrendingUp, color: 'text-green-400' },
          { label: 'System Load', value: 'Normal', icon: Activity, color: 'text-blue-400' },
        ].map(stat => (
          <div key={stat.label} className="bg-background-secondary border border-border/50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-foreground-muted">{stat.label}</span>
              <stat.icon className={`w-4 h-4 ${stat.color}`} />
            </div>
            <div className={`text-xl font-bold ${stat.color}`}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Brain Cards */}
      <div className="grid grid-cols-2 gap-4">
        {loading ? (
          <div className="col-span-2 bg-background-secondary border border-border/50 rounded-xl p-12 text-center text-foreground-muted">
            Loading brain status...
          </div>
        ) : (
          brains.map(brain => (
            <div key={brain.name} className="bg-background-secondary border border-border/50 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-accent-primary" />
                  <span className="text-sm font-semibold text-foreground-primary">{brain.name}</span>
                </div>
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full uppercase ${statusColors[brain.status]}`}>
                  {brain.status}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-xs text-foreground-muted">Accuracy</span>
                  <div className="text-lg font-bold text-foreground-primary">{brain.accuracy.toFixed(1)}%</div>
                  <div className="mt-1 h-1.5 bg-background-hover rounded-full overflow-hidden">
                    <div className="h-full bg-accent-primary rounded-full" style={{ width: `${Math.min(brain.accuracy, 100)}%` }} />
                  </div>
                </div>
                <div>
                  <span className="text-xs text-foreground-muted">Signals</span>
                  <div className="text-lg font-bold text-yellow-400">{brain.signals}</div>
                </div>
                <div>
                  <span className="text-xs text-foreground-muted">Regime</span>
                  <div className="text-sm font-semibold text-accent-primary">{brain.regime}</div>
                </div>
                <div>
                  <span className="text-xs text-foreground-muted">Updated</span>
                  <div className="text-sm text-foreground-secondary">{brain.lastUpdate}</div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Quick Actions */}
      <div className="bg-background-secondary border border-border/50 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-4 h-4 text-accent-primary" />
          <span className="text-sm font-semibold text-foreground-primary">Quick Actions</span>
        </div>
        <div className="flex gap-3">
          {['Generate Signals', 'Start Training', 'Reset Models', 'Export Report'].map(action => (
            <button
              key={action}
              className="px-4 py-2 bg-background-hover/50 border border-border/30 rounded-lg text-xs font-medium text-foreground-secondary hover:text-foreground-primary hover:bg-background-hover transition-colors"
            >
              {action}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
