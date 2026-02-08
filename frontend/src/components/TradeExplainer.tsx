/**
 * Trade Explainer Component
 * Provides detailed explanations for AI trading decisions
 * Shows reasoning, contributing factors, and confidence breakdown
 */

import { useState } from 'react'
import {
  Brain,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  ChevronDown,
  ChevronRight,
  Target,
  Shield,
  Activity,
  Layers,
  X,
} from 'lucide-react'
import { cn } from '@/utils/cn'

interface ContributingFactor {
  name: string
  weight: number
  signal: 'bullish' | 'bearish' | 'neutral'
  confidence: number
  explanation: string
}

interface TradeExplanation {
  id: string
  symbol: string
  direction: 'LONG' | 'SHORT'
  confidence: number
  timestamp: string
  entry_price: number
  stop_loss: number
  take_profit: number
  risk_reward: number
  position_size: number
  account_risk_pct: number
  timeframe: string
  regime: string
  factors: ContributingFactor[]
  strategies_agreeing: string[]
  strategies_disagreeing: string[]
  warnings: string[]
  thesis: string
}

interface TradeExplainerProps {
  explanation: TradeExplanation
  onClose?: () => void
  className?: string
}

export function TradeExplainer({ explanation, onClose, className }: TradeExplainerProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['overview', 'factors', 'strategies'])
  )

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  const isLong = explanation.direction === 'LONG'
  const directionColor = isLong ? 'text-bullish' : 'text-bearish'
  const directionBg = isLong ? 'bg-bullish/20' : 'bg-bearish/20'

  // Calculate factor distribution
  const bullishFactors = explanation.factors.filter(f => f.signal === 'bullish')
  const bearishFactors = explanation.factors.filter(f => f.signal === 'bearish')
  const neutralFactors = explanation.factors.filter(f => f.signal === 'neutral')

  const totalWeight = explanation.factors.reduce((sum, f) => sum + f.weight, 0)
  const bullishWeight = bullishFactors.reduce((sum, f) => sum + f.weight, 0)
  const bearishWeight = bearishFactors.reduce((sum, f) => sum + f.weight, 0)

  return (
    <div className={cn('card overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className={cn('p-2 rounded-lg', directionBg)}>
            <Brain className={cn('w-5 h-5', directionColor)} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground-primary flex items-center gap-2">
              TRADE EXPLAINER
              <span className={cn(
                'px-2 py-0.5 rounded text-xs font-bold',
                directionBg,
                directionColor
              )}>
                {explanation.direction}
              </span>
            </h3>
            <p className="text-xs text-foreground-muted">
              {explanation.symbol} | {explanation.timestamp}
            </p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-background-tertiary transition-colors"
          >
            <X className="w-4 h-4 text-foreground-muted" />
          </button>
        )}
      </div>

      {/* Content */}
      <div className="max-h-[600px] overflow-y-auto">
        {/* Trade Overview Section */}
        <Section
          title="Trade Overview"
          icon={<Target className="w-4 h-4 text-accent-primary" />}
          isExpanded={expandedSections.has('overview')}
          onToggle={() => toggleSection('overview')}
        >
          <div className="grid grid-cols-3 gap-3">
            <MetricCard label="Entry Price" value={`$${explanation.entry_price.toFixed(2)}`} />
            <MetricCard label="Stop Loss" value={`$${explanation.stop_loss.toFixed(2)}`} color="text-bearish" />
            <MetricCard label="Take Profit" value={`$${explanation.take_profit.toFixed(2)}`} color="text-bullish" />
            <MetricCard label="Risk/Reward" value={`${explanation.risk_reward.toFixed(1)}:1`} />
            <MetricCard label="Position Size" value={explanation.position_size.toString()} />
            <MetricCard label="Account Risk" value={`${explanation.account_risk_pct.toFixed(1)}%`} />
          </div>

          {/* Confidence Gauge */}
          <div className="mt-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs text-foreground-muted">AI Confidence</span>
              <span className={cn(
                'text-sm font-bold',
                explanation.confidence > 0.7 ? 'text-bullish' :
                explanation.confidence > 0.5 ? 'text-warning' : 'text-bearish'
              )}>
                {(explanation.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-3 bg-background-tertiary rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  explanation.confidence > 0.7 ? 'bg-bullish' :
                  explanation.confidence > 0.5 ? 'bg-warning' : 'bg-bearish'
                )}
                style={{ width: `${explanation.confidence * 100}%` }}
              />
            </div>
          </div>

          {/* Thesis */}
          <div className="mt-4 p-3 bg-background-tertiary/50 rounded-lg">
            <div className="flex items-start gap-2">
              <Info className="w-4 h-4 text-accent-primary mt-0.5 flex-shrink-0" />
              <p className="text-sm text-foreground-secondary leading-relaxed">
                {explanation.thesis}
              </p>
            </div>
          </div>
        </Section>

        {/* Contributing Factors Section */}
        <Section
          title="Contributing Factors"
          icon={<Layers className="w-4 h-4 text-purple-400" />}
          isExpanded={expandedSections.has('factors')}
          onToggle={() => toggleSection('factors')}
        >
          {/* Factor Distribution Bar */}
          <div className="mb-4">
            <div className="flex justify-between text-xs text-foreground-muted mb-1">
              <span>Bullish ({bullishFactors.length})</span>
              <span>Bearish ({bearishFactors.length})</span>
            </div>
            <div className="h-3 bg-background-tertiary rounded-full overflow-hidden flex">
              <div
                className="bg-bullish"
                style={{ width: `${(bullishWeight / totalWeight) * 100}%` }}
              />
              <div
                className="bg-warning"
                style={{ width: `${((totalWeight - bullishWeight - bearishWeight) / totalWeight) * 100}%` }}
              />
              <div
                className="bg-bearish"
                style={{ width: `${(bearishWeight / totalWeight) * 100}%` }}
              />
            </div>
          </div>

          {/* Factor List */}
          <div className="space-y-2">
            {explanation.factors.map((factor, i) => (
              <FactorCard key={i} factor={factor} />
            ))}
          </div>
        </Section>

        {/* Strategy Agreement Section */}
        <Section
          title="Strategy Consensus"
          icon={<Activity className="w-4 h-4 text-cyan-400" />}
          isExpanded={expandedSections.has('strategies')}
          onToggle={() => toggleSection('strategies')}
        >
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-bullish" />
                <span className="text-xs font-medium text-bullish">
                  Agreeing ({explanation.strategies_agreeing.length})
                </span>
              </div>
              <div className="space-y-1">
                {explanation.strategies_agreeing.map((strategy, i) => (
                  <div
                    key={i}
                    className="px-2 py-1 bg-bullish/10 text-bullish text-xs rounded"
                  >
                    {strategy}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="w-4 h-4 text-bearish" />
                <span className="text-xs font-medium text-bearish">
                  Disagreeing ({explanation.strategies_disagreeing.length})
                </span>
              </div>
              <div className="space-y-1">
                {explanation.strategies_disagreeing.map((strategy, i) => (
                  <div
                    key={i}
                    className="px-2 py-1 bg-bearish/10 text-bearish text-xs rounded"
                  >
                    {strategy}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Section>

        {/* Risk & Context Section */}
        <Section
          title="Risk & Market Context"
          icon={<Shield className="w-4 h-4 text-yellow-400" />}
          isExpanded={expandedSections.has('risk')}
          onToggle={() => toggleSection('risk')}
        >
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-background-tertiary rounded-lg">
              <div className="text-xs text-foreground-muted mb-1">Market Regime</div>
              <div className="text-sm font-bold text-accent-primary">
                {explanation.regime}
              </div>
            </div>
            <div className="p-3 bg-background-tertiary rounded-lg">
              <div className="text-xs text-foreground-muted mb-1">Timeframe</div>
              <div className="text-sm font-bold text-foreground-primary">
                {explanation.timeframe}
              </div>
            </div>
          </div>

          {/* Warnings */}
          {explanation.warnings.length > 0 && (
            <div className="mt-4 space-y-2">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-warning" />
                <span className="text-xs font-medium text-warning">Risk Warnings</span>
              </div>
              {explanation.warnings.map((warning, i) => (
                <div
                  key={i}
                  className="px-3 py-2 bg-warning/10 border border-warning/20 rounded-lg text-xs text-warning"
                >
                  {warning}
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>
    </div>
  )
}

// Helper Components
function Section({
  title,
  icon,
  isExpanded,
  onToggle,
  children
}: {
  title: string
  icon: React.ReactNode
  isExpanded: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <div className="border-b border-border last:border-0">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-background-tertiary/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm font-medium text-foreground-primary">{title}</span>
        </div>
        {isExpanded ? (
          <ChevronDown className="w-4 h-4 text-foreground-muted" />
        ) : (
          <ChevronRight className="w-4 h-4 text-foreground-muted" />
        )}
      </button>
      {isExpanded && (
        <div className="px-4 pb-4">
          {children}
        </div>
      )}
    </div>
  )
}

function MetricCard({
  label,
  value,
  color = 'text-foreground-primary'
}: {
  label: string
  value: string
  color?: string
}) {
  return (
    <div className="p-3 bg-background-tertiary rounded-lg">
      <div className="text-[10px] text-foreground-muted uppercase">{label}</div>
      <div className={cn('text-sm font-bold font-mono', color)}>{value}</div>
    </div>
  )
}

function FactorCard({ factor }: { factor: ContributingFactor }) {
  const [isExpanded, setIsExpanded] = useState(false)

  const signalColor = factor.signal === 'bullish' ? 'text-bullish' :
    factor.signal === 'bearish' ? 'text-bearish' : 'text-warning'
  const signalBg = factor.signal === 'bullish' ? 'bg-bullish/10' :
    factor.signal === 'bearish' ? 'bg-bearish/10' : 'bg-warning/10'

  return (
    <div className={cn('rounded-lg border border-border overflow-hidden', signalBg)}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3"
      >
        <div className="flex items-center gap-3">
          <div className={cn(
            'w-2 h-2 rounded-full',
            factor.signal === 'bullish' ? 'bg-bullish' :
            factor.signal === 'bearish' ? 'bg-bearish' : 'bg-warning'
          )} />
          <span className="text-sm font-medium text-foreground-primary">{factor.name}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className={cn('text-xs font-bold', signalColor)}>
            {(factor.confidence * 100).toFixed(0)}%
          </span>
          <span className="text-xs text-foreground-muted">
            Weight: {factor.weight}
          </span>
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-foreground-muted" />
          ) : (
            <ChevronRight className="w-4 h-4 text-foreground-muted" />
          )}
        </div>
      </button>
      {isExpanded && (
        <div className="px-3 pb-3 pt-0">
          <p className="text-xs text-foreground-secondary leading-relaxed pl-5">
            {factor.explanation}
          </p>
        </div>
      )}
    </div>
  )
}

/**
 * Returns null - no mock data.
 * Use real trade explanations from the API instead.
 * @deprecated Do not use mock explanations. Fetch real data from /api/brain-v6/explain endpoint.
 */
export function generateMockExplanation(_symbol: string = 'AAPL'): TradeExplanation | null {
  return null
}
