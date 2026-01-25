/**
 * Safety Guard Component
 * Non-negotiable risk controls and kill switches
 * Enforces prop firm rules and protects capital
 */

import { useState, useEffect, useCallback } from 'react'
import {
  Shield,
  AlertTriangle,
  AlertOctagon,
  Lock,
  Unlock,
  Power,
  TrendingDown,
  Clock,
  DollarSign,
  Activity,
  Settings,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  Bell,
  BellOff,
  Zap,
  Target,
  Gauge,
  Ban,
  RefreshCw,
} from 'lucide-react'
import { cn } from '@/utils/cn'

// ============== TYPES ==============

interface RiskRule {
  id: string
  name: string
  description: string
  type: 'hard_stop' | 'soft_limit' | 'warning'
  enabled: boolean
  triggered: boolean
  value: number
  threshold: number
  unit: string
  action: 'kill' | 'reduce' | 'alert' | 'pause'
}

interface SafetyStatus {
  isActive: boolean
  killSwitchArmed: boolean
  tradingEnabled: boolean
  currentDrawdown: number
  dailyPnL: number
  openRisk: number
  positionCount: number
  triggeredRules: string[]
  lastCheck: string
}

interface SafetyGuardProps {
  onKillSwitch?: () => void
  onTradingToggle?: (enabled: boolean) => void
  className?: string
}

// ============== COMPONENT ==============

export function SafetyGuard({ onKillSwitch, onTradingToggle, className }: SafetyGuardProps) {
  const [status, setStatus] = useState<SafetyStatus>({
    isActive: true,
    killSwitchArmed: false,
    tradingEnabled: true,
    currentDrawdown: -2.3,
    dailyPnL: -450,
    openRisk: 1.8,
    positionCount: 3,
    triggeredRules: [],
    lastCheck: new Date().toISOString()
  })

  const [rules, setRules] = useState<RiskRule[]>([
    {
      id: 'max_daily_loss',
      name: 'Max Daily Loss',
      description: 'Hard stop on daily losses - non-negotiable',
      type: 'hard_stop',
      enabled: true,
      triggered: false,
      value: -450,
      threshold: -1000,
      unit: '$',
      action: 'kill'
    },
    {
      id: 'max_drawdown',
      name: 'Max Drawdown',
      description: 'Account drawdown limit',
      type: 'hard_stop',
      enabled: true,
      triggered: false,
      value: -2.3,
      threshold: -5,
      unit: '%',
      action: 'kill'
    },
    {
      id: 'max_position_size',
      name: 'Max Position Size',
      description: 'Single position risk limit',
      type: 'hard_stop',
      enabled: true,
      triggered: false,
      value: 1.5,
      threshold: 2,
      unit: '%',
      action: 'reduce'
    },
    {
      id: 'max_open_positions',
      name: 'Max Open Positions',
      description: 'Concurrent position limit',
      type: 'soft_limit',
      enabled: true,
      triggered: false,
      value: 3,
      threshold: 5,
      unit: '',
      action: 'pause'
    },
    {
      id: 'max_correlation',
      name: 'Max Correlation',
      description: 'Correlated position exposure',
      type: 'soft_limit',
      enabled: true,
      triggered: false,
      value: 0.6,
      threshold: 0.8,
      unit: '',
      action: 'alert'
    },
    {
      id: 'trading_hours',
      name: 'Trading Hours',
      description: 'Only trade during market hours',
      type: 'soft_limit',
      enabled: true,
      triggered: false,
      value: 1,
      threshold: 1,
      unit: '',
      action: 'pause'
    },
    {
      id: 'consecutive_losses',
      name: 'Consecutive Losses',
      description: 'Pause after consecutive losing trades',
      type: 'warning',
      enabled: true,
      triggered: false,
      value: 2,
      threshold: 3,
      unit: '',
      action: 'pause'
    },
    {
      id: 'high_volatility',
      name: 'High Volatility Guard',
      description: 'Reduce size in volatile markets',
      type: 'warning',
      enabled: true,
      triggered: false,
      value: 22,
      threshold: 30,
      unit: 'VIX',
      action: 'reduce'
    }
  ])

  const [showSettings, setShowSettings] = useState(false)
  const [alertsEnabled, setAlertsEnabled] = useState(true)

  // Simulate real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      setStatus(prev => ({
        ...prev,
        currentDrawdown: prev.currentDrawdown + (Math.random() - 0.52) * 0.1,
        dailyPnL: prev.dailyPnL + (Math.random() - 0.48) * 50,
        openRisk: Math.max(0, prev.openRisk + (Math.random() - 0.5) * 0.1),
        lastCheck: new Date().toISOString()
      }))

      // Check rules
      setRules(prev => prev.map(rule => {
        let triggered = false
        if (rule.id === 'max_daily_loss' && status.dailyPnL < rule.threshold) triggered = true
        if (rule.id === 'max_drawdown' && status.currentDrawdown < rule.threshold) triggered = true
        return { ...rule, triggered }
      }))
    }, 2000)

    return () => clearInterval(interval)
  }, [status.dailyPnL, status.currentDrawdown])

  const handleKillSwitch = useCallback(() => {
    setStatus(prev => ({
      ...prev,
      killSwitchArmed: true,
      tradingEnabled: false
    }))
    onKillSwitch?.()
  }, [onKillSwitch])

  const handleTradingToggle = useCallback(() => {
    const newEnabled = !status.tradingEnabled
    setStatus(prev => ({ ...prev, tradingEnabled: newEnabled }))
    onTradingToggle?.(newEnabled)
  }, [status.tradingEnabled, onTradingToggle])

  const resetKillSwitch = useCallback(() => {
    setStatus(prev => ({
      ...prev,
      killSwitchArmed: false,
      tradingEnabled: true
    }))
  }, [])

  const toggleRule = useCallback((id: string) => {
    setRules(prev => prev.map(rule =>
      rule.id === id ? { ...rule, enabled: !rule.enabled } : rule
    ))
  }, [])

  const hardStopRules = rules.filter(r => r.type === 'hard_stop')
  const softLimitRules = rules.filter(r => r.type === 'soft_limit')
  const warningRules = rules.filter(r => r.type === 'warning')
  const triggeredCount = rules.filter(r => r.triggered && r.enabled).length

  const getHealthStatus = () => {
    if (status.killSwitchArmed || triggeredCount > 0) return 'critical'
    if (status.currentDrawdown < -3 || status.dailyPnL < -700) return 'warning'
    return 'healthy'
  }

  const healthStatus = getHealthStatus()

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            'p-2 rounded-lg',
            healthStatus === 'healthy' ? 'bg-bullish/20' :
            healthStatus === 'warning' ? 'bg-warning/20' : 'bg-bearish/20'
          )}>
            <Shield className={cn(
              'w-5 h-5',
              healthStatus === 'healthy' ? 'text-bullish' :
              healthStatus === 'warning' ? 'text-warning' : 'text-bearish'
            )} />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground-primary flex items-center gap-2">
              SAFETY GUARD
              <span className={cn(
                'px-2 py-0.5 rounded text-[10px] font-bold uppercase',
                healthStatus === 'healthy' ? 'bg-bullish/20 text-bullish' :
                healthStatus === 'warning' ? 'bg-warning/20 text-warning' :
                'bg-bearish/20 text-bearish'
              )}>
                {healthStatus}
              </span>
            </h2>
            <p className="text-xs text-foreground-muted">
              {triggeredCount} rules triggered | Last check: {new Date(status.lastCheck).toLocaleTimeString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setAlertsEnabled(!alertsEnabled)}
            className={cn(
              'p-2 rounded-lg transition-colors',
              alertsEnabled ? 'bg-accent-primary/20 text-accent-primary' : 'bg-background-tertiary text-foreground-muted'
            )}
            title={alertsEnabled ? 'Alerts On' : 'Alerts Off'}
          >
            {alertsEnabled ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 rounded-lg bg-background-tertiary text-foreground-muted hover:text-foreground-secondary transition-colors"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-4 gap-3">
        <StatusCard
          icon={<TrendingDown className="w-4 h-4" />}
          label="Daily P&L"
          value={`$${status.dailyPnL.toFixed(0)}`}
          status={status.dailyPnL < -500 ? 'danger' : status.dailyPnL < 0 ? 'warning' : 'good'}
        />
        <StatusCard
          icon={<Activity className="w-4 h-4" />}
          label="Drawdown"
          value={`${status.currentDrawdown.toFixed(1)}%`}
          status={status.currentDrawdown < -3 ? 'danger' : status.currentDrawdown < -1 ? 'warning' : 'good'}
        />
        <StatusCard
          icon={<Target className="w-4 h-4" />}
          label="Open Risk"
          value={`${status.openRisk.toFixed(1)}%`}
          status={status.openRisk > 1.5 ? 'warning' : 'good'}
        />
        <StatusCard
          icon={<Gauge className="w-4 h-4" />}
          label="Positions"
          value={status.positionCount.toString()}
          status={status.positionCount > 4 ? 'warning' : 'good'}
        />
      </div>

      {/* Kill Switch & Trading Toggle */}
      <div className="grid grid-cols-2 gap-4">
        {/* Kill Switch */}
        <div className={cn(
          'p-4 rounded-lg border-2 transition-all',
          status.killSwitchArmed
            ? 'bg-bearish/20 border-bearish'
            : 'bg-background-secondary border-border hover:border-bearish/50'
        )}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <AlertOctagon className={cn(
                'w-5 h-5',
                status.killSwitchArmed ? 'text-bearish' : 'text-foreground-muted'
              )} />
              <span className="font-bold text-sm">KILL SWITCH</span>
            </div>
            {status.killSwitchArmed && (
              <span className="text-xs text-bearish font-bold animate-pulse">ARMED</span>
            )}
          </div>
          <p className="text-xs text-foreground-muted mb-3">
            Emergency stop - closes all positions immediately
          </p>
          {status.killSwitchArmed ? (
            <button
              onClick={resetKillSwitch}
              className="w-full py-2 bg-background-tertiary text-foreground-secondary rounded-lg text-sm font-medium hover:bg-background-primary transition-colors flex items-center justify-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Reset Kill Switch
            </button>
          ) : (
            <button
              onClick={handleKillSwitch}
              className="w-full py-2 bg-bearish text-white rounded-lg text-sm font-bold hover:bg-bearish/80 transition-colors flex items-center justify-center gap-2"
            >
              <Power className="w-4 h-4" />
              ARM KILL SWITCH
            </button>
          )}
        </div>

        {/* Trading Toggle */}
        <div className={cn(
          'p-4 rounded-lg border-2 transition-all',
          status.tradingEnabled
            ? 'bg-bullish/10 border-bullish/50'
            : 'bg-background-secondary border-border'
        )}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              {status.tradingEnabled ? (
                <Unlock className="w-5 h-5 text-bullish" />
              ) : (
                <Lock className="w-5 h-5 text-foreground-muted" />
              )}
              <span className="font-bold text-sm">TRADING STATUS</span>
            </div>
            <span className={cn(
              'text-xs font-bold',
              status.tradingEnabled ? 'text-bullish' : 'text-foreground-muted'
            )}>
              {status.tradingEnabled ? 'ENABLED' : 'DISABLED'}
            </span>
          </div>
          <p className="text-xs text-foreground-muted mb-3">
            {status.tradingEnabled
              ? 'AI can open new positions'
              : 'All new trades blocked'}
          </p>
          <button
            onClick={handleTradingToggle}
            disabled={status.killSwitchArmed}
            className={cn(
              'w-full py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2',
              status.tradingEnabled
                ? 'bg-bearish/20 text-bearish hover:bg-bearish/30'
                : 'bg-bullish text-white hover:bg-bullish/80',
              status.killSwitchArmed && 'opacity-50 cursor-not-allowed'
            )}
          >
            {status.tradingEnabled ? (
              <>
                <Ban className="w-4 h-4" />
                Disable Trading
              </>
            ) : (
              <>
                <Zap className="w-4 h-4" />
                Enable Trading
              </>
            )}
          </button>
        </div>
      </div>

      {/* Risk Rules */}
      <div className="space-y-4">
        {/* Hard Stops */}
        <RuleSection
          title="Hard Stops"
          subtitle="Non-negotiable - will kill trading"
          icon={<AlertOctagon className="w-4 h-4 text-bearish" />}
          rules={hardStopRules}
          onToggle={toggleRule}
        />

        {/* Soft Limits */}
        <RuleSection
          title="Soft Limits"
          subtitle="Will pause or reduce activity"
          icon={<AlertTriangle className="w-4 h-4 text-warning" />}
          rules={softLimitRules}
          onToggle={toggleRule}
        />

        {/* Warnings */}
        <RuleSection
          title="Warnings"
          subtitle="Alert only - manual action needed"
          icon={<Bell className="w-4 h-4 text-accent-primary" />}
          rules={warningRules}
          onToggle={toggleRule}
        />
      </div>
    </div>
  )
}

// Helper Components
function StatusCard({
  icon,
  label,
  value,
  status
}: {
  icon: React.ReactNode
  label: string
  value: string
  status: 'good' | 'warning' | 'danger'
}) {
  const colors = {
    good: 'text-bullish',
    warning: 'text-warning',
    danger: 'text-bearish'
  }

  return (
    <div className="card p-3">
      <div className="flex items-center gap-2 mb-1">
        <span className={colors[status]}>{icon}</span>
        <span className="text-[10px] text-foreground-muted uppercase">{label}</span>
      </div>
      <div className={cn('text-lg font-bold font-mono', colors[status])}>
        {value}
      </div>
    </div>
  )
}

function RuleSection({
  title,
  subtitle,
  icon,
  rules,
  onToggle
}: {
  title: string
  subtitle: string
  icon: React.ReactNode
  rules: RiskRule[]
  onToggle: (id: string) => void
}) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <div>
          <span className="text-sm font-medium text-foreground-primary">{title}</span>
          <span className="text-xs text-foreground-muted ml-2">{subtitle}</span>
        </div>
      </div>
      <div className="space-y-2">
        {rules.map(rule => (
          <RuleCard key={rule.id} rule={rule} onToggle={onToggle} />
        ))}
      </div>
    </div>
  )
}

function RuleCard({ rule, onToggle }: { rule: RiskRule; onToggle: (id: string) => void }) {
  const progress = Math.min(100, Math.abs(rule.value / rule.threshold) * 100)
  const isNearThreshold = progress > 70

  return (
    <div className={cn(
      'p-3 rounded-lg border transition-all',
      rule.triggered
        ? 'bg-bearish/10 border-bearish/50'
        : rule.enabled
          ? 'bg-background-tertiary border-border'
          : 'bg-background-tertiary/50 border-border/50 opacity-50'
    )}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onToggle(rule.id)}
            className={cn(
              'w-8 h-4 rounded-full transition-colors relative',
              rule.enabled ? 'bg-bullish' : 'bg-background-secondary'
            )}
          >
            <div className={cn(
              'absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all',
              rule.enabled ? 'right-0.5' : 'left-0.5'
            )} />
          </button>
          <span className="text-sm font-medium">{rule.name}</span>
          {rule.triggered && (
            <span className="px-1.5 py-0.5 bg-bearish/20 text-bearish text-[10px] font-bold rounded animate-pulse">
              TRIGGERED
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={cn(
            'text-xs font-mono',
            isNearThreshold ? 'text-warning' : 'text-foreground-secondary'
          )}>
            {rule.value}{rule.unit} / {rule.threshold}{rule.unit}
          </span>
          <span className={cn(
            'px-1.5 py-0.5 text-[10px] font-bold rounded uppercase',
            rule.action === 'kill' ? 'bg-bearish/20 text-bearish' :
            rule.action === 'reduce' ? 'bg-warning/20 text-warning' :
            rule.action === 'pause' ? 'bg-orange-500/20 text-orange-500' :
            'bg-accent-primary/20 text-accent-primary'
          )}>
            {rule.action}
          </span>
        </div>
      </div>
      <p className="text-xs text-foreground-muted mb-2">{rule.description}</p>
      <div className="h-1.5 bg-background-secondary rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all',
            progress > 90 ? 'bg-bearish' :
            progress > 70 ? 'bg-warning' : 'bg-bullish'
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}

// Export a compact version for embedding in other views
export function SafetyGuardCompact({ className }: { className?: string }) {
  const [status] = useState({
    isHealthy: true,
    dailyPnL: -450,
    drawdown: -2.3,
    tradingEnabled: true
  })

  const healthStatus = status.dailyPnL < -700 || status.drawdown < -4 ? 'danger' :
    status.dailyPnL < -300 || status.drawdown < -2 ? 'warning' : 'healthy'

  return (
    <div className={cn(
      'flex items-center gap-3 px-3 py-2 rounded-lg',
      healthStatus === 'healthy' ? 'bg-bullish/10' :
      healthStatus === 'warning' ? 'bg-warning/10' : 'bg-bearish/10',
      className
    )}>
      <Shield className={cn(
        'w-4 h-4',
        healthStatus === 'healthy' ? 'text-bullish' :
        healthStatus === 'warning' ? 'text-warning' : 'text-bearish'
      )} />
      <div className="flex items-center gap-4 text-xs">
        <span className="text-foreground-muted">
          P&L: <span className={status.dailyPnL < 0 ? 'text-bearish' : 'text-bullish'}>
            ${status.dailyPnL}
          </span>
        </span>
        <span className="text-foreground-muted">
          DD: <span className={status.drawdown < -3 ? 'text-bearish' : 'text-warning'}>
            {status.drawdown}%
          </span>
        </span>
        <span className={cn(
          'font-bold',
          status.tradingEnabled ? 'text-bullish' : 'text-bearish'
        )}>
          {status.tradingEnabled ? 'TRADING' : 'STOPPED'}
        </span>
      </div>
    </div>
  )
}
