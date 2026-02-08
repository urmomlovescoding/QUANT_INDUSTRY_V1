import { useState, useEffect } from 'react'
import {
  FileText,
  AlertCircle,
  CheckCircle,
  XCircle,
  Activity,
  RefreshCw,
  Shield,
  Brain,
  Zap,
  Clock,
  TrendingUp
} from 'lucide-react'
import { cn } from '@/utils/cn'

interface MLModel {
  id: string
  name: string
  type: string
  status: string
  features: string[]
  last_trained?: string
  performance_metrics?: {
    accuracy: number
    sharpe_ratio: number
    max_drawdown: number
  }
  compliance: {
    risk_limits: boolean
    position_sizing: boolean
    stop_loss: boolean
    audit_trail: boolean
  }
}

interface ComplianceRule {
  rule: string
  value: string
  status: string
}

interface AuditEntry {
  timestamp: string
  model: string
  action: string
  symbol: string
  decision: string
  confidence: number
  risk_check: string
}

interface SlideDoctrineData {
  status: string
  compliance_framework: string
  description: string
  models: MLModel[]
  compliance_rules: ComplianceRule[]
  audit_log_count: number
  last_compliance_check: string
}

export function SlideDoctrine() {
  const [data, setData] = useState<SlideDoctrineData | null>(null)
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'models' | 'rules' | 'audit'>('models')

  useEffect(() => {
    fetchSlideDoctrineData()
    fetchAuditLog()
  }, [])

  const fetchSlideDoctrineData = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/slide-doctrine')
      if (response.ok) {
        const result = await response.json()
        setData(result)
      }
    } catch {
      // Silent fail - data will show as null
    } finally {
      setIsLoading(false)
    }
  }

  const fetchAuditLog = async () => {
    try {
      const response = await fetch('/api/slide-doctrine/audit?limit=20')
      if (response.ok) {
        const result = await response.json()
        setAuditLog(result.audit_log || [])
      }
    } catch {
      // Silent fail - audit log will show as empty
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-accent-primary" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <FileText className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">SLIDE DOCTRINE</h1>
            <p className="text-xs text-foreground-muted">ML model compliance and documentation</p>
          </div>
        </div>
        <div className="card p-8 text-center text-foreground-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">Unable to load SLIDE Doctrine</p>
          <p className="text-sm mt-2">Please check if the backend is running</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <FileText className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">SLIDE DOCTRINE</h1>
            <p className="text-xs text-foreground-muted">{data.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn(
            "px-3 py-1 rounded-full text-xs font-medium",
            data.status === "active" ? "bg-bullish/20 text-bullish" : "bg-bearish/20 text-bearish"
          )}>
            {data.status.toUpperCase()}
          </span>
          <button
            onClick={() => { fetchSlideDoctrineData(); fetchAuditLog(); }}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-4 gap-3">
        <div className="card p-3">
          <div className="flex items-center gap-2 text-foreground-muted mb-1">
            <Brain className="w-4 h-4" />
            <span className="text-xs">ML Models</span>
          </div>
          <div className="text-lg font-bold text-foreground-primary">{data.models.length}</div>
        </div>
        <div className="card p-3">
          <div className="flex items-center gap-2 text-foreground-muted mb-1">
            <Shield className="w-4 h-4" />
            <span className="text-xs">Active Models</span>
          </div>
          <div className="text-lg font-bold text-bullish">
            {data.models.filter(m => m.status === 'active').length}
          </div>
        </div>
        <div className="card p-3">
          <div className="flex items-center gap-2 text-foreground-muted mb-1">
            <Activity className="w-4 h-4" />
            <span className="text-xs">Audit Entries</span>
          </div>
          <div className="text-lg font-bold text-foreground-primary">{data.audit_log_count}</div>
        </div>
        <div className="card p-3">
          <div className="flex items-center gap-2 text-foreground-muted mb-1">
            <Clock className="w-4 h-4" />
            <span className="text-xs">Last Check</span>
          </div>
          <div className="text-sm font-medium text-foreground-primary">
            {new Date(data.last_compliance_check).toLocaleTimeString()}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 bg-surface-secondary rounded-lg p-1">
        {(['models', 'rules', 'audit'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-4 py-2 text-sm font-medium rounded-md transition-colors flex-1',
              activeTab === tab
                ? 'bg-accent-primary text-background-primary'
                : 'text-foreground-muted hover:text-foreground-primary'
            )}
          >
            {tab === 'models' && 'ML Models'}
            {tab === 'rules' && 'Compliance Rules'}
            {tab === 'audit' && 'Audit Log'}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'models' && (
        <div className="grid grid-cols-2 gap-4">
          {data.models.map(model => (
            <div key={model.id} className="card p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-bold text-foreground-primary">{model.name}</h3>
                  <p className="text-xs text-foreground-muted">{model.type}</p>
                </div>
                <span className={cn(
                  "px-2 py-1 rounded text-xs font-medium",
                  model.status === 'active' ? "bg-bullish/20 text-bullish" : "bg-surface-secondary text-foreground-muted"
                )}>
                  {model.status.toUpperCase()}
                </span>
              </div>

              {/* Features */}
              <div className="flex flex-wrap gap-1 mb-3">
                {model.features.map(feature => (
                  <span key={feature} className="px-2 py-0.5 text-xs bg-accent-primary/10 text-accent-primary rounded">
                    {feature}
                  </span>
                ))}
              </div>

              {/* Performance Metrics */}
              {model.performance_metrics && (
                <div className="grid grid-cols-3 gap-2 mb-3 p-2 bg-surface-secondary rounded">
                  <div className="text-center">
                    <div className="text-xs text-foreground-muted">Accuracy</div>
                    <div className="text-sm font-bold text-foreground-primary">
                      {(model.performance_metrics.accuracy * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-foreground-muted">Sharpe</div>
                    <div className="text-sm font-bold text-foreground-primary">
                      {model.performance_metrics.sharpe_ratio.toFixed(2)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-foreground-muted">Max DD</div>
                    <div className="text-sm font-bold text-bearish">
                      {model.performance_metrics.max_drawdown.toFixed(1)}%
                    </div>
                  </div>
                </div>
              )}

              {/* Compliance Status */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                {Object.entries(model.compliance).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-1">
                    {value ? (
                      <CheckCircle className="w-3 h-3 text-bullish" />
                    ) : (
                      <XCircle className="w-3 h-3 text-bearish" />
                    )}
                    <span className="text-foreground-muted capitalize">
                      {key.replace(/_/g, ' ')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'rules' && (
        <div className="card divide-y divide-border">
          {data.compliance_rules.map((rule, idx) => (
            <div key={idx} className="p-4 flex items-center justify-between">
              <div>
                <div className="font-medium text-foreground-primary">{rule.rule}</div>
                <div className="text-sm text-foreground-muted">{rule.value}</div>
              </div>
              <span className={cn(
                "px-3 py-1 rounded text-xs font-medium",
                rule.status === 'enforced' ? "bg-bullish/20 text-bullish" :
                rule.status === 'active' ? "bg-accent-primary/20 text-accent-primary" :
                "bg-surface-secondary text-foreground-muted"
              )}>
                {rule.status.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'audit' && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-secondary">
              <tr>
                <th className="px-4 py-2 text-left text-foreground-muted font-medium">Time</th>
                <th className="px-4 py-2 text-left text-foreground-muted font-medium">Model</th>
                <th className="px-4 py-2 text-left text-foreground-muted font-medium">Action</th>
                <th className="px-4 py-2 text-left text-foreground-muted font-medium">Symbol</th>
                <th className="px-4 py-2 text-left text-foreground-muted font-medium">Decision</th>
                <th className="px-4 py-2 text-left text-foreground-muted font-medium">Confidence</th>
                <th className="px-4 py-2 text-left text-foreground-muted font-medium">Risk</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {auditLog.map((entry, idx) => (
                <tr key={idx} className="hover:bg-surface-secondary/50">
                  <td className="px-4 py-2 text-foreground-muted">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </td>
                  <td className="px-4 py-2 font-medium text-foreground-primary">{entry.model}</td>
                  <td className="px-4 py-2">
                    <span className="px-2 py-0.5 text-xs bg-surface-secondary rounded">
                      {entry.action}
                    </span>
                  </td>
                  <td className="px-4 py-2 font-mono text-accent-primary">{entry.symbol}</td>
                  <td className="px-4 py-2">
                    <span className={cn(
                      "px-2 py-0.5 text-xs rounded",
                      entry.decision === 'BUY' ? "bg-bullish/20 text-bullish" :
                      entry.decision === 'SELL' ? "bg-bearish/20 text-bearish" :
                      "bg-surface-secondary text-foreground-muted"
                    )}>
                      {entry.decision}
                    </span>
                  </td>
                  <td className="px-4 py-2 font-mono">
                    {(entry.confidence * 100).toFixed(0)}%
                  </td>
                  <td className="px-4 py-2">
                    <span className="px-2 py-0.5 text-xs bg-bullish/20 text-bullish rounded">
                      {entry.risk_check}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
