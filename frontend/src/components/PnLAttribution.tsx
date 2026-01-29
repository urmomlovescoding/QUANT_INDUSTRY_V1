/**
 * Real-Time P&L Attribution Component
 * QUANT_INDUSTRY_V1 - P2 Enhancement
 * 
 * Provides detailed real-time insights into P&L drivers:
 * - Strategy-level attribution
 * - Asset-level breakdown
 * - Factor contributions
 * - Time-based analysis
 * - Risk-adjusted metrics
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  TrendingUp,
  TrendingDown,
  PieChart,
  BarChart3,
  Layers,
  Clock,
  Target,
  AlertTriangle,
  Activity,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Download,
  Filter,
  X,
} from 'lucide-react'
import { cn } from '@/utils/cn'

// =============================================================================
// TYPES
// =============================================================================

interface StrategyAttribution {
  strategyId: string
  strategyName: string
  pnl: number
  pnlPercent: number
  contribution: number  // Percentage of total P&L
  trades: number
  winRate: number
  sharpe: number
  maxDrawdown: number
  allocation: number
}

interface AssetAttribution {
  symbol: string
  pnl: number
  pnlPercent: number
  contribution: number
  position: number
  avgEntry: number
  currentPrice: number
  unrealized: number
  realized: number
}

interface FactorAttribution {
  factorName: string
  exposure: number
  contribution: number
  tStat: number
  description: string
}

interface TimeAttribution {
  period: string
  pnl: number
  pnlPercent: number
  trades: number
  winRate: number
}

interface PnLSummary {
  totalPnL: number
  totalPnLPercent: number
  unrealizedPnL: number
  realizedPnL: number
  tradingCosts: number
  netPnL: number
  alpha: number
  beta: number
  sharpeRatio: number
  maxDrawdown: number
  timestamp: string
}

interface PnLAttributionData {
  summary: PnLSummary
  byStrategy: StrategyAttribution[]
  byAsset: AssetAttribution[]
  byFactor: FactorAttribution[]
  byTime: TimeAttribution[]
}

interface PnLAttributionProps {
  data?: PnLAttributionData
  onRefresh?: () => void
  onExport?: () => void
  className?: string
  autoRefresh?: boolean
  refreshInterval?: number
}

type TabType = 'summary' | 'strategy' | 'asset' | 'factor' | 'time'

// =============================================================================
// MOCK DATA GENERATOR
// =============================================================================

function generateMockPnLData(): PnLAttributionData {
  const totalPnL = (Math.random() - 0.3) * 50000
  const strategies = [
    'Momentum Alpha',
    'Mean Reversion',
    'ML Ensemble',
    'Options Flow',
    'Trend Following',
  ]
  
  const assets = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'META', 'AMZN', 'SPY']
  
  const factors = [
    { name: 'Market', desc: 'Broad market exposure' },
    { name: 'Size', desc: 'Small vs large cap tilt' },
    { name: 'Value', desc: 'Value vs growth exposure' },
    { name: 'Momentum', desc: 'Price momentum factor' },
    { name: 'Volatility', desc: 'Low vol anomaly exposure' },
  ]
  
  // Generate strategy attribution
  const strategyPnLs = strategies.map(() => (Math.random() - 0.4) * 10000)
  const totalStratPnL = strategyPnLs.reduce((a, b) => a + b, 0)
  
  const byStrategy: StrategyAttribution[] = strategies.map((name, i) => ({
    strategyId: `strat_${i}`,
    strategyName: name,
    pnl: strategyPnLs[i],
    pnlPercent: strategyPnLs[i] / 100000 * 100,
    contribution: totalStratPnL !== 0 ? (strategyPnLs[i] / Math.abs(totalStratPnL)) * 100 : 0,
    trades: Math.floor(Math.random() * 50) + 5,
    winRate: 0.4 + Math.random() * 0.3,
    sharpe: (Math.random() - 0.3) * 3,
    maxDrawdown: Math.random() * 0.15,
    allocation: 0.2,
  }))
  
  // Generate asset attribution
  const assetPnLs = assets.map(() => (Math.random() - 0.4) * 5000)
  const totalAssetPnL = assetPnLs.reduce((a, b) => a + b, 0)
  
  const byAsset: AssetAttribution[] = assets.map((symbol, i) => {
    const basePrice = 100 + Math.random() * 400
    const position = Math.floor(Math.random() * 200) - 100
    const unrealized = position * (Math.random() - 0.5) * 10
    
    return {
      symbol,
      pnl: assetPnLs[i],
      pnlPercent: assetPnLs[i] / 10000 * 100,
      contribution: totalAssetPnL !== 0 ? (assetPnLs[i] / Math.abs(totalAssetPnL)) * 100 : 0,
      position,
      avgEntry: basePrice * (1 - Math.random() * 0.1),
      currentPrice: basePrice,
      unrealized,
      realized: assetPnLs[i] - unrealized,
    }
  })
  
  // Generate factor attribution
  const byFactor: FactorAttribution[] = factors.map(({ name, desc }) => ({
    factorName: name,
    exposure: (Math.random() - 0.5) * 2,
    contribution: (Math.random() - 0.4) * 5000,
    tStat: (Math.random() - 0.5) * 4,
    description: desc,
  }))
  
  // Generate time attribution
  const timeperiods = ['Today', 'Yesterday', 'This Week', 'This Month', 'YTD']
  const byTime: TimeAttribution[] = timeperiods.map((period, i) => ({
    period,
    pnl: totalPnL * (0.1 + Math.random() * 0.3) * (i + 1) / 3,
    pnlPercent: (Math.random() - 0.3) * 5,
    trades: Math.floor(Math.random() * 100) * (i + 1),
    winRate: 0.45 + Math.random() * 0.2,
  }))
  
  return {
    summary: {
      totalPnL,
      totalPnLPercent: totalPnL / 1000000 * 100,
      unrealizedPnL: totalPnL * 0.3,
      realizedPnL: totalPnL * 0.7,
      tradingCosts: Math.abs(totalPnL) * 0.02,
      netPnL: totalPnL * 0.98,
      alpha: (Math.random() - 0.3) * 0.1,
      beta: 0.8 + Math.random() * 0.4,
      sharpeRatio: (Math.random() - 0.2) * 2,
      maxDrawdown: Math.random() * 0.1,
      timestamp: new Date().toISOString(),
    },
    byStrategy,
    byAsset,
    byFactor,
    byTime,
  }
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function PnLAttribution({
  data: initialData,
  onRefresh,
  onExport,
  className,
  autoRefresh = true,
  refreshInterval = 30000,
}: PnLAttributionProps) {
  const [data, setData] = useState<PnLAttributionData>(initialData || generateMockPnLData())
  const [activeTab, setActiveTab] = useState<TabType>('summary')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' }>({
    key: 'pnl',
    direction: 'desc',
  })
  
  // Auto-refresh logic
  useEffect(() => {
    if (!autoRefresh) return
    
    const interval = setInterval(() => {
      setData(generateMockPnLData())
    }, refreshInterval)
    
    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval])
  
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true)
    
    if (onRefresh) {
      onRefresh()
    } else {
      setData(generateMockPnLData())
    }
    
    setTimeout(() => setIsRefreshing(false), 500)
  }, [onRefresh])
  
  const handleExport = useCallback(() => {
    if (onExport) {
      onExport()
    } else {
      // Default export as JSON
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `pnl_attribution_${new Date().toISOString().split('T')[0]}.json`
      a.click()
      URL.revokeObjectURL(url)
    }
  }, [data, onExport])
  
  const isProfitable = data.summary.totalPnL >= 0
  
  return (
    <div className={cn('card overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className={cn(
            'p-2 rounded-lg',
            isProfitable ? 'bg-bullish/20' : 'bg-bearish/20'
          )}>
            <PieChart className={cn(
              'w-5 h-5',
              isProfitable ? 'text-bullish' : 'text-bearish'
            )} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground-primary">
              P&L ATTRIBUTION
            </h3>
            <p className="text-xs text-foreground-muted">
              Real-time breakdown • {new Date(data.summary.timestamp).toLocaleTimeString()}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            className={cn(
              'p-2 rounded-lg hover:bg-background-tertiary transition-colors',
              isRefreshing && 'animate-spin'
            )}
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4 text-foreground-muted" />
          </button>
          <button
            onClick={handleExport}
            className="p-2 rounded-lg hover:bg-background-tertiary transition-colors"
            title="Export"
          >
            <Download className="w-4 h-4 text-foreground-muted" />
          </button>
        </div>
      </div>
      
      {/* Summary Bar */}
      <div className="grid grid-cols-4 gap-4 p-4 bg-background-secondary/50 border-b border-border">
        <SummaryMetric
          label="Total P&L"
          value={formatCurrency(data.summary.totalPnL)}
          subvalue={`${data.summary.totalPnLPercent >= 0 ? '+' : ''}${data.summary.totalPnLPercent.toFixed(2)}%`}
          positive={data.summary.totalPnL >= 0}
          icon={isProfitable ? TrendingUp : TrendingDown}
        />
        <SummaryMetric
          label="Unrealized"
          value={formatCurrency(data.summary.unrealizedPnL)}
          positive={data.summary.unrealizedPnL >= 0}
          icon={Activity}
        />
        <SummaryMetric
          label="Sharpe Ratio"
          value={data.summary.sharpeRatio.toFixed(2)}
          positive={data.summary.sharpeRatio > 0}
          icon={Target}
        />
        <SummaryMetric
          label="Max Drawdown"
          value={`-${(data.summary.maxDrawdown * 100).toFixed(1)}%`}
          positive={false}
          icon={AlertTriangle}
        />
      </div>
      
      {/* Tab Navigation */}
      <div className="flex border-b border-border">
        {[
          { id: 'summary' as TabType, label: 'Summary', icon: PieChart },
          { id: 'strategy' as TabType, label: 'By Strategy', icon: Layers },
          { id: 'asset' as TabType, label: 'By Asset', icon: BarChart3 },
          { id: 'factor' as TabType, label: 'By Factor', icon: Target },
          { id: 'time' as TabType, label: 'By Time', icon: Clock },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 py-3 px-4',
              'text-xs font-medium transition-colors border-b-2',
              activeTab === id
                ? 'border-accent-primary text-accent-primary bg-accent-primary/5'
                : 'border-transparent text-foreground-muted hover:text-foreground-primary hover:bg-background-tertiary/50'
            )}
          >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
          </button>
        ))}
      </div>
      
      {/* Tab Content */}
      <div className="p-4 max-h-[500px] overflow-y-auto">
        {activeTab === 'summary' && <SummaryTab data={data} />}
        {activeTab === 'strategy' && <StrategyTab data={data.byStrategy} />}
        {activeTab === 'asset' && <AssetTab data={data.byAsset} />}
        {activeTab === 'factor' && <FactorTab data={data.byFactor} />}
        {activeTab === 'time' && <TimeTab data={data.byTime} />}
      </div>
    </div>
  )
}

// =============================================================================
// TAB COMPONENTS
// =============================================================================

function SummaryTab({ data }: { data: PnLAttributionData }) {
  const { summary, byStrategy, byFactor } = data
  
  return (
    <div className="space-y-6">
      {/* P&L Breakdown */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-3">
          P&L Breakdown
        </h4>
        <div className="grid grid-cols-2 gap-3">
          <MetricCard label="Realized P&L" value={formatCurrency(summary.realizedPnL)} />
          <MetricCard label="Unrealized P&L" value={formatCurrency(summary.unrealizedPnL)} />
          <MetricCard label="Trading Costs" value={formatCurrency(-summary.tradingCosts)} negative />
          <MetricCard label="Net P&L" value={formatCurrency(summary.netPnL)} highlight />
        </div>
      </div>
      
      {/* Risk Metrics */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-3">
          Risk Metrics
        </h4>
        <div className="grid grid-cols-4 gap-3">
          <MetricCard label="Alpha" value={`${(summary.alpha * 100).toFixed(2)}%`} />
          <MetricCard label="Beta" value={summary.beta.toFixed(2)} />
          <MetricCard label="Sharpe" value={summary.sharpeRatio.toFixed(2)} />
          <MetricCard label="Max DD" value={`${(summary.maxDrawdown * 100).toFixed(1)}%`} />
        </div>
      </div>
      
      {/* Top Contributors */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-3">
          Top Strategy Contributors
        </h4>
        <div className="space-y-2">
          {byStrategy
            .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))
            .slice(0, 3)
            .map((strat) => (
              <ContributionBar
                key={strat.strategyId}
                label={strat.strategyName}
                value={strat.pnl}
                contribution={strat.contribution}
              />
            ))}
        </div>
      </div>
    </div>
  )
}

function StrategyTab({ data }: { data: StrategyAttribution[] }) {
  const sorted = useMemo(() => {
    return [...data].sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))
  }, [data])
  
  return (
    <div className="space-y-3">
      {sorted.map((strat) => (
        <StrategyCard key={strat.strategyId} strategy={strat} />
      ))}
    </div>
  )
}

function AssetTab({ data }: { data: AssetAttribution[] }) {
  const sorted = useMemo(() => {
    return [...data].sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))
  }, [data])
  
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-foreground-muted uppercase border-b border-border">
            <th className="text-left py-2 px-3">Symbol</th>
            <th className="text-right py-2 px-3">Position</th>
            <th className="text-right py-2 px-3">P&L</th>
            <th className="text-right py-2 px-3">%</th>
            <th className="text-right py-2 px-3">Contribution</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((asset) => (
            <tr key={asset.symbol} className="border-b border-border/50 hover:bg-background-tertiary/50">
              <td className="py-2 px-3 font-medium">{asset.symbol}</td>
              <td className={cn(
                'text-right py-2 px-3',
                asset.position > 0 ? 'text-bullish' : asset.position < 0 ? 'text-bearish' : ''
              )}>
                {asset.position > 0 ? '+' : ''}{asset.position}
              </td>
              <td className={cn(
                'text-right py-2 px-3 font-mono',
                asset.pnl >= 0 ? 'text-bullish' : 'text-bearish'
              )}>
                {formatCurrency(asset.pnl)}
              </td>
              <td className={cn(
                'text-right py-2 px-3',
                asset.pnlPercent >= 0 ? 'text-bullish' : 'text-bearish'
              )}>
                {asset.pnlPercent >= 0 ? '+' : ''}{asset.pnlPercent.toFixed(2)}%
              </td>
              <td className="text-right py-2 px-3">
                <ContributionBadge value={asset.contribution} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FactorTab({ data }: { data: FactorAttribution[] }) {
  return (
    <div className="space-y-4">
      {data.map((factor) => (
        <div
          key={factor.factorName}
          className="p-3 rounded-lg bg-background-tertiary/50 border border-border"
        >
          <div className="flex items-center justify-between mb-2">
            <div>
              <span className="text-sm font-medium text-foreground-primary">
                {factor.factorName}
              </span>
              <p className="text-xs text-foreground-muted">{factor.description}</p>
            </div>
            <div className={cn(
              'text-sm font-mono font-bold',
              factor.contribution >= 0 ? 'text-bullish' : 'text-bearish'
            )}>
              {formatCurrency(factor.contribution)}
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-3 mt-3">
            <div className="text-xs">
              <span className="text-foreground-muted">Exposure: </span>
              <span className={cn(
                'font-medium',
                factor.exposure >= 0 ? 'text-bullish' : 'text-bearish'
              )}>
                {factor.exposure >= 0 ? '+' : ''}{factor.exposure.toFixed(2)}
              </span>
            </div>
            <div className="text-xs">
              <span className="text-foreground-muted">t-stat: </span>
              <span className={cn(
                'font-medium',
                Math.abs(factor.tStat) > 2 ? 'text-warning' : ''
              )}>
                {factor.tStat.toFixed(2)}
              </span>
            </div>
          </div>
          
          {/* Exposure Bar */}
          <div className="mt-2 h-2 bg-background-tertiary rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full',
                factor.exposure >= 0 ? 'bg-bullish' : 'bg-bearish'
              )}
              style={{
                width: `${Math.min(Math.abs(factor.exposure) * 50, 100)}%`,
                marginLeft: factor.exposure < 0 ? 'auto' : 0,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function TimeTab({ data }: { data: TimeAttribution[] }) {
  return (
    <div className="space-y-3">
      {data.map((period) => (
        <div
          key={period.period}
          className="flex items-center justify-between p-3 rounded-lg bg-background-tertiary/50 border border-border"
        >
          <div>
            <div className="text-sm font-medium text-foreground-primary">
              {period.period}
            </div>
            <div className="text-xs text-foreground-muted">
              {period.trades} trades • {(period.winRate * 100).toFixed(0)}% win rate
            </div>
          </div>
          
          <div className="text-right">
            <div className={cn(
              'text-sm font-mono font-bold',
              period.pnl >= 0 ? 'text-bullish' : 'text-bearish'
            )}>
              {formatCurrency(period.pnl)}
            </div>
            <div className={cn(
              'text-xs',
              period.pnlPercent >= 0 ? 'text-bullish' : 'text-bearish'
            )}>
              {period.pnlPercent >= 0 ? '+' : ''}{period.pnlPercent.toFixed(2)}%
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

function SummaryMetric({
  label,
  value,
  subvalue,
  positive,
  icon: Icon,
}: {
  label: string
  value: string
  subvalue?: string
  positive?: boolean
  icon: React.ElementType
}) {
  return (
    <div className="flex items-center gap-3">
      <div className={cn(
        'p-2 rounded-lg',
        positive ? 'bg-bullish/10' : 'bg-bearish/10'
      )}>
        <Icon className={cn(
          'w-4 h-4',
          positive ? 'text-bullish' : 'text-bearish'
        )} />
      </div>
      <div>
        <div className="text-[10px] text-foreground-muted uppercase">{label}</div>
        <div className={cn(
          'text-sm font-bold font-mono',
          positive ? 'text-bullish' : 'text-bearish'
        )}>
          {value}
        </div>
        {subvalue && (
          <div className={cn(
            'text-xs',
            positive ? 'text-bullish' : 'text-bearish'
          )}>
            {subvalue}
          </div>
        )}
      </div>
    </div>
  )
}

function MetricCard({
  label,
  value,
  negative,
  highlight,
}: {
  label: string
  value: string
  negative?: boolean
  highlight?: boolean
}) {
  return (
    <div className={cn(
      'p-3 rounded-lg',
      highlight ? 'bg-accent-primary/10 border border-accent-primary/30' : 'bg-background-tertiary'
    )}>
      <div className="text-[10px] text-foreground-muted uppercase">{label}</div>
      <div className={cn(
        'text-sm font-bold font-mono',
        negative ? 'text-bearish' : highlight ? 'text-accent-primary' : 'text-foreground-primary'
      )}>
        {value}
      </div>
    </div>
  )
}

function ContributionBar({
  label,
  value,
  contribution,
}: {
  label: string
  value: number
  contribution: number
}) {
  const isPositive = value >= 0
  
  return (
    <div className="flex items-center gap-3">
      <div className="w-24 text-xs text-foreground-secondary truncate">{label}</div>
      <div className="flex-1 relative h-5 bg-background-tertiary rounded-full overflow-hidden">
        <div
          className={cn(
            'absolute top-0 h-full rounded-full',
            isPositive ? 'bg-bullish' : 'bg-bearish'
          )}
          style={{
            width: `${Math.min(Math.abs(contribution), 100)}%`,
            left: isPositive ? '50%' : `${50 - Math.min(Math.abs(contribution), 50)}%`,
          }}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[10px] font-medium text-foreground-primary">
            {formatCurrency(value)}
          </span>
        </div>
      </div>
      <div className={cn(
        'w-12 text-xs text-right',
        isPositive ? 'text-bullish' : 'text-bearish'
      )}>
        {contribution >= 0 ? '+' : ''}{contribution.toFixed(1)}%
      </div>
    </div>
  )
}

function ContributionBadge({ value }: { value: number }) {
  const absValue = Math.abs(value)
  const isPositive = value >= 0
  
  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
      isPositive ? 'bg-bullish/10 text-bullish' : 'bg-bearish/10 text-bearish'
    )}>
      {value >= 0 ? '+' : ''}{value.toFixed(1)}%
    </span>
  )
}

function StrategyCard({ strategy }: { strategy: StrategyAttribution }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const isPositive = strategy.pnl >= 0
  
  return (
    <div className={cn(
      'rounded-lg border overflow-hidden',
      isPositive ? 'border-bullish/30 bg-bullish/5' : 'border-bearish/30 bg-bearish/5'
    )}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3"
      >
        <div className="flex items-center gap-3">
          <div className={cn(
            'w-2 h-2 rounded-full',
            isPositive ? 'bg-bullish' : 'bg-bearish'
          )} />
          <span className="text-sm font-medium text-foreground-primary">
            {strategy.strategyName}
          </span>
        </div>
        
        <div className="flex items-center gap-4">
          <div className={cn(
            'text-sm font-mono font-bold',
            isPositive ? 'text-bullish' : 'text-bearish'
          )}>
            {formatCurrency(strategy.pnl)}
          </div>
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-foreground-muted" />
          ) : (
            <ChevronRight className="w-4 h-4 text-foreground-muted" />
          )}
        </div>
      </button>
      
      {isExpanded && (
        <div className="px-3 pb-3 grid grid-cols-4 gap-3">
          <div className="text-center">
            <div className="text-[10px] text-foreground-muted">Trades</div>
            <div className="text-xs font-medium">{strategy.trades}</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-foreground-muted">Win Rate</div>
            <div className="text-xs font-medium">{(strategy.winRate * 100).toFixed(0)}%</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-foreground-muted">Sharpe</div>
            <div className="text-xs font-medium">{strategy.sharpe.toFixed(2)}</div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-foreground-muted">Allocation</div>
            <div className="text-xs font-medium">{(strategy.allocation * 100).toFixed(0)}%</div>
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// UTILITIES
// =============================================================================

function formatCurrency(value: number): string {
  const absValue = Math.abs(value)
  const sign = value >= 0 ? '' : '-'
  
  if (absValue >= 1000000) {
    return `${sign}$${(absValue / 1000000).toFixed(2)}M`
  } else if (absValue >= 1000) {
    return `${sign}$${(absValue / 1000).toFixed(1)}K`
  } else {
    return `${sign}$${absValue.toFixed(2)}`
  }
}

// =============================================================================
// EXPORTS
// =============================================================================

export { generateMockPnLData }
export type { PnLAttributionData, PnLAttributionProps }
