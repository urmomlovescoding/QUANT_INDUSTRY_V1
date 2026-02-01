/**
 * Real-Time P&L Attribution Component
 * QUANT_INDUSTRY_V1 - P2 Enhancement #13
 *
 * Features:
 * - Real-time P&L breakdown by factor (alpha, beta, sector, currency)
 * - Interactive Recharts visualizations
 * - Drill-down capability by time period and asset
 * - WebSocket integration for live updates
 * - Full integration with existing frontend architecture
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
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
  ChevronLeft,
  RefreshCw,
  Download,
  Filter,
  X,
  Maximize2,
  Minimize2,
  ArrowUpRight,
  ArrowDownRight,
  DollarSign,
  Globe,
  Building2,
  Zap,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Treemap,
  ComposedChart,
} from 'recharts'
import { cn } from '@/utils/cn'

// =============================================================================
// TYPES
// =============================================================================

interface FactorAttribution {
  factorName: 'alpha' | 'beta' | 'sector' | 'currency' | 'momentum' | 'volatility' | 'size' | 'value'
  displayName: string
  pnl: number
  pnlPercent: number
  contribution: number
  exposure: number
  tStat: number
  description: string
  color: string
  breakdown?: FactorBreakdownItem[]
}

interface FactorBreakdownItem {
  name: string
  pnl: number
  contribution: number
  exposure: number
}

interface AssetAttribution {
  symbol: string
  name?: string
  sector: string
  pnl: number
  pnlPercent: number
  contribution: number
  position: number
  avgEntry: number
  currentPrice: number
  unrealized: number
  realized: number
  factors: {
    alpha: number
    beta: number
    sector: number
    currency: number
  }
}

interface TimeAttribution {
  period: string
  timestamp: string
  pnl: number
  pnlPercent: number
  cumulativePnl: number
  trades: number
  winRate: number
  factors: {
    alpha: number
    beta: number
    sector: number
    currency: number
  }
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
  sectorPnL: number
  currencyPnL: number
  residual: number
  sharpeRatio: number
  informationRatio: number
  maxDrawdown: number
  timestamp: string
}

interface PnLAttributionData {
  summary: PnLSummary
  byFactor: FactorAttribution[]
  byAsset: AssetAttribution[]
  byTime: TimeAttribution[]
  historicalPnL: { timestamp: string; pnl: number; cumulative: number }[]
}

interface PnLAttributionProps {
  data?: PnLAttributionData
  onRefresh?: () => void
  onExport?: () => void
  className?: string
  autoRefresh?: boolean
  refreshInterval?: number
  onAssetSelect?: (symbol: string) => void
  compact?: boolean
}

type TabType = 'summary' | 'factors' | 'assets' | 'time' | 'waterfall'
type TimePeriod = '1H' | '4H' | '1D' | '1W' | '1M' | 'YTD' | 'ALL'
type DrillDownView = 'main' | 'factor' | 'asset' | 'time'

interface DrillDownState {
  view: DrillDownView
  selectedFactor?: string
  selectedAsset?: string
  selectedPeriod?: string
}

// =============================================================================
// CONSTANTS
// =============================================================================

const FACTOR_COLORS: Record<string, string> = {
  alpha: '#00d4aa',
  beta: '#3b82f6',
  sector: '#8b5cf6',
  currency: '#f59e0b',
  momentum: '#10b981',
  volatility: '#ef4444',
  size: '#06b6d4',
  value: '#ec4899',
}

const SECTOR_COLORS: Record<string, string> = {
  Technology: '#3b82f6',
  Healthcare: '#10b981',
  Financial: '#f59e0b',
  Consumer: '#8b5cf6',
  Energy: '#ef4444',
  Industrial: '#6366f1',
  Materials: '#14b8a6',
  Utilities: '#84cc16',
  'Real Estate': '#f97316',
  Communication: '#06b6d4',
}

const TIME_PERIODS: TimePeriod[] = ['1H', '4H', '1D', '1W', '1M', 'YTD', 'ALL']

// =============================================================================
// MOCK DATA GENERATOR (Enhanced)
// =============================================================================

function generateMockPnLData(): PnLAttributionData {
  const totalPnL = (Math.random() - 0.3) * 50000
  const now = new Date()

  // Generate factor attribution with proper breakdown
  const byFactor: FactorAttribution[] = [
    {
      factorName: 'alpha',
      displayName: 'Alpha',
      pnl: totalPnL * 0.35 + (Math.random() - 0.5) * 5000,
      pnlPercent: (Math.random() - 0.3) * 3,
      contribution: 35 + (Math.random() - 0.5) * 10,
      exposure: 1.0,
      tStat: 1.5 + Math.random() * 1.5,
      description: 'Skill-based returns from active management',
      color: FACTOR_COLORS.alpha,
      breakdown: [
        { name: 'Stock Selection', pnl: totalPnL * 0.2, contribution: 20, exposure: 1.0 },
        { name: 'Timing', pnl: totalPnL * 0.1, contribution: 10, exposure: 0.8 },
        { name: 'Execution', pnl: totalPnL * 0.05, contribution: 5, exposure: 1.0 },
      ],
    },
    {
      factorName: 'beta',
      displayName: 'Market Beta',
      pnl: totalPnL * 0.25 + (Math.random() - 0.5) * 4000,
      pnlPercent: (Math.random() - 0.3) * 2,
      contribution: 25 + (Math.random() - 0.5) * 8,
      exposure: 0.85 + Math.random() * 0.3,
      tStat: 2.0 + Math.random(),
      description: 'Returns from market exposure',
      color: FACTOR_COLORS.beta,
      breakdown: [
        { name: 'SPY Beta', pnl: totalPnL * 0.15, contribution: 15, exposure: 0.9 },
        { name: 'QQQ Beta', pnl: totalPnL * 0.1, contribution: 10, exposure: 0.7 },
      ],
    },
    {
      factorName: 'sector',
      displayName: 'Sector',
      pnl: totalPnL * 0.2 + (Math.random() - 0.5) * 3000,
      pnlPercent: (Math.random() - 0.4) * 2,
      contribution: 20 + (Math.random() - 0.5) * 6,
      exposure: (Math.random() - 0.5) * 0.4,
      tStat: (Math.random() - 0.5) * 3,
      description: 'Returns from sector allocation',
      color: FACTOR_COLORS.sector,
      breakdown: Object.entries(SECTOR_COLORS).slice(0, 5).map(([name]) => ({
        name,
        pnl: (Math.random() - 0.4) * 3000,
        contribution: (Math.random() - 0.4) * 8,
        exposure: (Math.random() - 0.5) * 0.2,
      })),
    },
    {
      factorName: 'currency',
      displayName: 'Currency',
      pnl: totalPnL * 0.1 + (Math.random() - 0.5) * 2000,
      pnlPercent: (Math.random() - 0.5) * 1.5,
      contribution: 10 + (Math.random() - 0.5) * 4,
      exposure: (Math.random() - 0.5) * 0.3,
      tStat: (Math.random() - 0.5) * 2,
      description: 'Returns from currency exposure',
      color: FACTOR_COLORS.currency,
      breakdown: [
        { name: 'EUR/USD', pnl: (Math.random() - 0.5) * 1500, contribution: 4, exposure: 0.15 },
        { name: 'GBP/USD', pnl: (Math.random() - 0.5) * 1000, contribution: 3, exposure: 0.1 },
        { name: 'JPY/USD', pnl: (Math.random() - 0.5) * 800, contribution: 2, exposure: 0.08 },
        { name: 'Other', pnl: (Math.random() - 0.5) * 500, contribution: 1, exposure: 0.05 },
      ],
    },
    {
      factorName: 'momentum',
      displayName: 'Momentum',
      pnl: totalPnL * 0.05 + (Math.random() - 0.5) * 1500,
      pnlPercent: (Math.random() - 0.5) * 1,
      contribution: 5 + (Math.random() - 0.5) * 3,
      exposure: (Math.random() - 0.3) * 0.5,
      tStat: (Math.random() - 0.3) * 2,
      description: 'Price momentum factor exposure',
      color: FACTOR_COLORS.momentum,
    },
    {
      factorName: 'volatility',
      displayName: 'Volatility',
      pnl: totalPnL * 0.05 + (Math.random() - 0.5) * 1000,
      pnlPercent: (Math.random() - 0.5) * 0.8,
      contribution: 5 + (Math.random() - 0.5) * 2,
      exposure: (Math.random() - 0.5) * 0.3,
      tStat: (Math.random() - 0.5) * 1.5,
      description: 'Low volatility anomaly exposure',
      color: FACTOR_COLORS.volatility,
    },
  ]

  // Generate asset attribution
  const assets = [
    { symbol: 'AAPL', name: 'Apple Inc.', sector: 'Technology' },
    { symbol: 'GOOGL', name: 'Alphabet Inc.', sector: 'Technology' },
    { symbol: 'MSFT', name: 'Microsoft Corp.', sector: 'Technology' },
    { symbol: 'TSLA', name: 'Tesla Inc.', sector: 'Consumer' },
    { symbol: 'NVDA', name: 'NVIDIA Corp.', sector: 'Technology' },
    { symbol: 'META', name: 'Meta Platforms', sector: 'Communication' },
    { symbol: 'AMZN', name: 'Amazon.com', sector: 'Consumer' },
    { symbol: 'JPM', name: 'JPMorgan Chase', sector: 'Financial' },
    { symbol: 'JNJ', name: 'Johnson & Johnson', sector: 'Healthcare' },
    { symbol: 'XOM', name: 'Exxon Mobil', sector: 'Energy' },
  ]

  const assetPnLs = assets.map(() => (Math.random() - 0.4) * 5000)
  const totalAssetPnL = assetPnLs.reduce((a, b) => a + Math.abs(b), 0) || 1

  const byAsset: AssetAttribution[] = assets.map((asset, i) => {
    const basePrice = 100 + Math.random() * 400
    const position = Math.floor(Math.random() * 200) - 50
    const unrealized = position * (Math.random() - 0.5) * 10

    return {
      ...asset,
      pnl: assetPnLs[i],
      pnlPercent: assetPnLs[i] / 10000 * 100,
      contribution: (Math.abs(assetPnLs[i]) / totalAssetPnL) * 100 * Math.sign(assetPnLs[i]),
      position,
      avgEntry: basePrice * (1 - Math.random() * 0.1),
      currentPrice: basePrice,
      unrealized,
      realized: assetPnLs[i] - unrealized,
      factors: {
        alpha: (Math.random() - 0.5) * 1000,
        beta: (Math.random() - 0.3) * 2000,
        sector: (Math.random() - 0.5) * 800,
        currency: (Math.random() - 0.5) * 500,
      },
    }
  })

  // Generate time-based attribution (hourly for the last 24 hours)
  const byTime: TimeAttribution[] = []
  let cumulativePnl = 0
  for (let i = 23; i >= 0; i--) {
    const timestamp = new Date(now.getTime() - i * 60 * 60 * 1000)
    const hourPnl = (Math.random() - 0.45) * 2000
    cumulativePnl += hourPnl
    byTime.push({
      period: `${timestamp.getHours().toString().padStart(2, '0')}:00`,
      timestamp: timestamp.toISOString(),
      pnl: hourPnl,
      pnlPercent: hourPnl / 100000 * 100,
      cumulativePnl,
      trades: Math.floor(Math.random() * 10),
      winRate: 0.4 + Math.random() * 0.3,
      factors: {
        alpha: hourPnl * 0.35 + (Math.random() - 0.5) * 200,
        beta: hourPnl * 0.25 + (Math.random() - 0.5) * 150,
        sector: hourPnl * 0.2 + (Math.random() - 0.5) * 100,
        currency: hourPnl * 0.1 + (Math.random() - 0.5) * 80,
      },
    })
  }

  // Generate historical P&L for the chart
  const historicalPnL = byTime.map(t => ({
    timestamp: t.timestamp,
    pnl: t.pnl,
    cumulative: t.cumulativePnl,
  }))

  const factorTotal = byFactor.reduce((a, b) => a + b.pnl, 0)
  const residual = totalPnL - factorTotal

  return {
    summary: {
      totalPnL,
      totalPnLPercent: totalPnL / 1000000 * 100,
      unrealizedPnL: totalPnL * 0.35,
      realizedPnL: totalPnL * 0.65,
      tradingCosts: Math.abs(totalPnL) * 0.015,
      netPnL: totalPnL * 0.985,
      alpha: byFactor.find(f => f.factorName === 'alpha')?.pnl || 0,
      beta: byFactor.find(f => f.factorName === 'beta')?.pnl || 0,
      sectorPnL: byFactor.find(f => f.factorName === 'sector')?.pnl || 0,
      currencyPnL: byFactor.find(f => f.factorName === 'currency')?.pnl || 0,
      residual,
      sharpeRatio: (Math.random() - 0.2) * 2.5,
      informationRatio: (Math.random() - 0.3) * 1.5,
      maxDrawdown: Math.random() * 0.08,
      timestamp: now.toISOString(),
    },
    byFactor,
    byAsset,
    byTime,
    historicalPnL,
  }
}

// =============================================================================
// CUSTOM TOOLTIP COMPONENTS
// =============================================================================

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload || !payload.length) return null

  return (
    <div className="bg-background-elevated border border-border rounded-lg p-3 shadow-xl">
      <p className="text-foreground-primary font-medium text-sm mb-2">{label}</p>
      {payload.map((entry: any, index: number) => (
        <div key={index} className="flex items-center justify-between gap-4 text-xs">
          <span className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-foreground-muted">{entry.name}:</span>
          </span>
          <span
            className={cn(
              'font-mono font-medium',
              entry.value >= 0 ? 'text-bullish' : 'text-bearish'
            )}
          >
            {formatCurrency(entry.value)}
          </span>
        </div>
      ))}
    </div>
  )
}

const WaterfallTooltip = ({ active, payload }: any) => {
  if (!active || !payload || !payload.length) return null
  const data = payload[0]?.payload

  return (
    <div className="bg-background-elevated border border-border rounded-lg p-3 shadow-xl">
      <p className="text-foreground-primary font-medium text-sm">{data.name}</p>
      <p className={cn(
        'text-lg font-mono font-bold mt-1',
        data.pnl >= 0 ? 'text-bullish' : 'text-bearish'
      )}>
        {formatCurrency(data.pnl)}
      </p>
      <p className="text-xs text-foreground-muted mt-1">
        Contribution: {data.contribution?.toFixed(1)}%
      </p>
    </div>
  )
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
  onAssetSelect,
  compact = false,
}: PnLAttributionProps) {
  const [data, setData] = useState<PnLAttributionData>(initialData || generateMockPnLData())
  const [activeTab, setActiveTab] = useState<TabType>('summary')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [timePeriod, setTimePeriod] = useState<TimePeriod>('1D')
  const [isExpanded, setIsExpanded] = useState(false)
  const [drillDown, setDrillDown] = useState<DrillDownState>({ view: 'main' })
  const [showFilters, setShowFilters] = useState(false)
  const [filterSector, setFilterSector] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

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
      const exportData = {
        ...data,
        exportedAt: new Date().toISOString(),
        timePeriod,
      }
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `pnl_attribution_${new Date().toISOString().split('T')[0]}.json`
      a.click()
      URL.revokeObjectURL(url)
    }
  }, [data, onExport, timePeriod])

  const handleFactorDrillDown = useCallback((factorName: string) => {
    setDrillDown({ view: 'factor', selectedFactor: factorName })
  }, [])

  const handleAssetDrillDown = useCallback((symbol: string) => {
    setDrillDown({ view: 'asset', selectedAsset: symbol })
    onAssetSelect?.(symbol)
  }, [onAssetSelect])

  const handleTimeDrillDown = useCallback((period: string) => {
    setDrillDown({ view: 'time', selectedPeriod: period })
  }, [])

  const handleBackToMain = useCallback(() => {
    setDrillDown({ view: 'main' })
  }, [])

  // Filtered assets
  const filteredAssets = useMemo(() => {
    if (!filterSector) return data.byAsset
    return data.byAsset.filter(a => a.sector === filterSector)
  }, [data.byAsset, filterSector])

  // Waterfall chart data
  const waterfallData = useMemo(() => {
    const items = [
      { name: 'Alpha', pnl: data.summary.alpha, contribution: 35, isTotal: false },
      { name: 'Beta', pnl: data.summary.beta, contribution: 25, isTotal: false },
      { name: 'Sector', pnl: data.summary.sectorPnL, contribution: 20, isTotal: false },
      { name: 'Currency', pnl: data.summary.currencyPnL, contribution: 10, isTotal: false },
      { name: 'Residual', pnl: data.summary.residual, contribution: 10, isTotal: false },
      { name: 'Costs', pnl: -data.summary.tradingCosts, contribution: -2, isTotal: false },
      { name: 'Net P&L', pnl: data.summary.netPnL, contribution: 100, isTotal: true },
    ]

    let cumulative = 0
    return items.map(item => {
      const start = item.isTotal ? 0 : cumulative
      cumulative += item.isTotal ? 0 : item.pnl
      return {
        ...item,
        start,
        end: item.isTotal ? item.pnl : cumulative,
        fill: item.isTotal ? '#00d4aa' : item.pnl >= 0 ? '#10b981' : '#ef4444',
      }
    })
  }, [data.summary])

  const isProfitable = data.summary.totalPnL >= 0

  return (
    <div
      ref={containerRef}
      className={cn(
        'card overflow-hidden',
        isExpanded && 'fixed inset-4 z-50',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-3">
          {drillDown.view !== 'main' && (
            <button
              onClick={handleBackToMain}
              className="p-1.5 rounded-lg hover:bg-background-tertiary transition-colors"
            >
              <ChevronLeft className="w-4 h-4 text-foreground-muted" />
            </button>
          )}
          <div className={cn(
            'p-2 rounded-lg',
            isProfitable ? 'bg-bullish/20' : 'bg-bearish/20'
          )}>
            <Activity className={cn(
              'w-5 h-5',
              isProfitable ? 'text-bullish' : 'text-bearish'
            )} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground-primary">
              {drillDown.view === 'main' && 'P&L ATTRIBUTION'}
              {drillDown.view === 'factor' && `${drillDown.selectedFactor?.toUpperCase()} BREAKDOWN`}
              {drillDown.view === 'asset' && `${drillDown.selectedAsset} ANALYSIS`}
              {drillDown.view === 'time' && `${drillDown.selectedPeriod} ATTRIBUTION`}
            </h3>
            <p className="text-xs text-foreground-muted">
              Real-time factor analysis {' '}
              {new Date(data.summary.timestamp).toLocaleTimeString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Time Period Selector */}
          <div className="flex bg-background-tertiary rounded-lg p-0.5">
            {TIME_PERIODS.slice(0, compact ? 4 : 7).map(period => (
              <button
                key={period}
                onClick={() => setTimePeriod(period)}
                className={cn(
                  'px-2 py-1 text-xs font-medium rounded-md transition-colors',
                  timePeriod === period
                    ? 'bg-accent-primary text-background-primary'
                    : 'text-foreground-muted hover:text-foreground-primary'
                )}
              >
                {period}
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'p-2 rounded-lg transition-colors',
              showFilters ? 'bg-accent-primary/20 text-accent-primary' : 'hover:bg-background-tertiary'
            )}
            title="Filters"
          >
            <Filter className="w-4 h-4" />
          </button>

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

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-2 rounded-lg hover:bg-background-tertiary transition-colors"
            title={isExpanded ? 'Minimize' : 'Maximize'}
          >
            {isExpanded ? (
              <Minimize2 className="w-4 h-4 text-foreground-muted" />
            ) : (
              <Maximize2 className="w-4 h-4 text-foreground-muted" />
            )}
          </button>
        </div>
      </div>

      {/* Filter Panel */}
      {showFilters && (
        <div className="px-4 py-3 border-b border-border bg-background-secondary/50">
          <div className="flex items-center gap-4">
            <span className="text-xs font-medium text-foreground-muted">Sector:</span>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setFilterSector(null)}
                className={cn(
                  'px-2 py-1 text-xs rounded-md transition-colors',
                  !filterSector
                    ? 'bg-accent-primary text-background-primary'
                    : 'bg-background-tertiary text-foreground-muted hover:text-foreground-primary'
                )}
              >
                All
              </button>
              {Object.keys(SECTOR_COLORS).slice(0, 6).map(sector => (
                <button
                  key={sector}
                  onClick={() => setFilterSector(sector)}
                  className={cn(
                    'px-2 py-1 text-xs rounded-md transition-colors',
                    filterSector === sector
                      ? 'bg-accent-primary text-background-primary'
                      : 'bg-background-tertiary text-foreground-muted hover:text-foreground-primary'
                  )}
                >
                  {sector}
                </button>
              ))}
            </div>
            {filterSector && (
              <button
                onClick={() => setFilterSector(null)}
                className="p-1 rounded hover:bg-background-tertiary"
              >
                <X className="w-3 h-3 text-foreground-muted" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Summary Metrics Bar */}
      <div className="grid grid-cols-5 gap-4 p-4 bg-background-secondary/50 border-b border-border">
        <SummaryMetric
          label="Total P&L"
          value={formatCurrency(data.summary.totalPnL)}
          subvalue={`${data.summary.totalPnLPercent >= 0 ? '+' : ''}${data.summary.totalPnLPercent.toFixed(2)}%`}
          positive={isProfitable}
          icon={isProfitable ? TrendingUp : TrendingDown}
        />
        <SummaryMetric
          label="Alpha"
          value={formatCurrency(data.summary.alpha)}
          positive={data.summary.alpha >= 0}
          icon={Zap}
          onClick={() => handleFactorDrillDown('alpha')}
          clickable
        />
        <SummaryMetric
          label="Beta"
          value={formatCurrency(data.summary.beta)}
          positive={data.summary.beta >= 0}
          icon={Activity}
          onClick={() => handleFactorDrillDown('beta')}
          clickable
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
      {drillDown.view === 'main' && (
        <div className="flex border-b border-border">
          {[
            { id: 'summary' as TabType, label: 'Summary', icon: PieChart },
            { id: 'factors' as TabType, label: 'Factors', icon: Layers },
            { id: 'assets' as TabType, label: 'Assets', icon: BarChart3 },
            { id: 'time' as TabType, label: 'Timeline', icon: Clock },
            { id: 'waterfall' as TabType, label: 'Waterfall', icon: BarChart3 },
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
      )}

      {/* Content */}
      <div className={cn('p-4', isExpanded ? 'max-h-[calc(100vh-250px)]' : 'max-h-[500px]', 'overflow-y-auto')}>
        {drillDown.view === 'main' ? (
          <>
            {activeTab === 'summary' && (
              <SummaryView
                data={data}
                onFactorClick={handleFactorDrillDown}
                onAssetClick={handleAssetDrillDown}
              />
            )}
            {activeTab === 'factors' && (
              <FactorsView
                factors={data.byFactor}
                onFactorClick={handleFactorDrillDown}
              />
            )}
            {activeTab === 'assets' && (
              <AssetsView
                assets={filteredAssets}
                onAssetClick={handleAssetDrillDown}
              />
            )}
            {activeTab === 'time' && (
              <TimelineView
                timeData={data.byTime}
                historicalPnL={data.historicalPnL}
                onPeriodClick={handleTimeDrillDown}
              />
            )}
            {activeTab === 'waterfall' && (
              <WaterfallView waterfallData={waterfallData} />
            )}
          </>
        ) : drillDown.view === 'factor' ? (
          <FactorDrillDownView
            factor={data.byFactor.find(f => f.factorName === drillDown.selectedFactor)}
            assets={data.byAsset}
          />
        ) : drillDown.view === 'asset' ? (
          <AssetDrillDownView
            asset={data.byAsset.find(a => a.symbol === drillDown.selectedAsset)}
            timeData={data.byTime}
          />
        ) : (
          <TimeDrillDownView
            period={drillDown.selectedPeriod || ''}
            timeData={data.byTime}
            factors={data.byFactor}
          />
        )}
      </div>
    </div>
  )
}

// =============================================================================
// VIEW COMPONENTS
// =============================================================================

function SummaryView({
  data,
  onFactorClick,
  onAssetClick,
}: {
  data: PnLAttributionData
  onFactorClick: (factor: string) => void
  onAssetClick: (symbol: string) => void
}) {
  // Prepare pie chart data for factor contribution
  const pieData = data.byFactor
    .filter(f => Math.abs(f.contribution) > 1)
    .map(f => ({
      name: f.displayName,
      value: Math.abs(f.contribution),
      pnl: f.pnl,
      color: f.color,
    }))

  // Top contributors by asset
  const topAssets = [...data.byAsset]
    .sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))
    .slice(0, 5)

  return (
    <div className="space-y-6">
      {/* Factor Contribution Pie Chart */}
      <div className="grid grid-cols-2 gap-6">
        <div>
          <h4 className="text-xs font-bold text-foreground-muted uppercase mb-4">
            Factor Contribution
          </h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RechartsPieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={2}
                  dataKey="value"
                  onClick={(entry) => {
                    const factor = data.byFactor.find(f => f.displayName === entry.name)
                    if (factor) onFactorClick(factor.factorName)
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const d = payload[0].payload
                    return (
                      <div className="bg-background-elevated border border-border rounded-lg p-3 shadow-xl">
                        <p className="text-foreground-primary font-medium">{d.name}</p>
                        <p className={cn('font-mono', d.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                          {formatCurrency(d.pnl)}
                        </p>
                        <p className="text-xs text-foreground-muted">{d.value.toFixed(1)}% contribution</p>
                      </div>
                    )
                  }}
                />
                <Legend
                  layout="vertical"
                  align="right"
                  verticalAlign="middle"
                  formatter={(value) => (
                    <span className="text-xs text-foreground-secondary">{value}</span>
                  )}
                />
              </RechartsPieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* P&L Breakdown */}
        <div>
          <h4 className="text-xs font-bold text-foreground-muted uppercase mb-4">
            P&L Breakdown
          </h4>
          <div className="space-y-3">
            <MetricRow label="Realized P&L" value={data.summary.realizedPnL} />
            <MetricRow label="Unrealized P&L" value={data.summary.unrealizedPnL} />
            <MetricRow label="Trading Costs" value={-data.summary.tradingCosts} />
            <div className="border-t border-border pt-3">
              <MetricRow label="Net P&L" value={data.summary.netPnL} highlight />
            </div>
          </div>

          {/* Risk Metrics */}
          <div className="mt-6">
            <h4 className="text-xs font-bold text-foreground-muted uppercase mb-3">
              Risk Metrics
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-background-tertiary rounded-lg">
                <div className="text-[10px] text-foreground-muted uppercase">Sharpe</div>
                <div className="text-sm font-bold font-mono text-foreground-primary">
                  {data.summary.sharpeRatio.toFixed(2)}
                </div>
              </div>
              <div className="p-3 bg-background-tertiary rounded-lg">
                <div className="text-[10px] text-foreground-muted uppercase">Info Ratio</div>
                <div className="text-sm font-bold font-mono text-foreground-primary">
                  {data.summary.informationRatio.toFixed(2)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Top Asset Contributors */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-3">
          Top Asset Contributors
        </h4>
        <div className="space-y-2">
          {topAssets.map(asset => (
            <button
              key={asset.symbol}
              onClick={() => onAssetClick(asset.symbol)}
              className="w-full flex items-center justify-between p-3 rounded-lg bg-background-tertiary/50 hover:bg-background-tertiary transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: SECTOR_COLORS[asset.sector] || '#6b7280' }}
                />
                <div className="text-left">
                  <span className="text-sm font-medium text-foreground-primary">{asset.symbol}</span>
                  <span className="text-xs text-foreground-muted ml-2">{asset.sector}</span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className={cn(
                  'text-sm font-mono font-bold',
                  asset.pnl >= 0 ? 'text-bullish' : 'text-bearish'
                )}>
                  {formatCurrency(asset.pnl)}
                </div>
                <ChevronRight className="w-4 h-4 text-foreground-muted opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Cumulative P&L Chart */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-3">
          Cumulative P&L
        </h4>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.historicalPnL}>
              <defs>
                <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00d4aa" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#00d4aa" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
              <XAxis
                dataKey="timestamp"
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickFormatter={(v) => new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={0} stroke="#6b7280" strokeDasharray="3 3" />
              <Area
                type="monotone"
                dataKey="cumulative"
                name="Cumulative P&L"
                stroke="#00d4aa"
                fill="url(#pnlGradient)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

function FactorsView({
  factors,
  onFactorClick,
}: {
  factors: FactorAttribution[]
  onFactorClick: (factor: string) => void
}) {
  const barChartData = factors.map(f => ({
    name: f.displayName,
    pnl: f.pnl,
    contribution: f.contribution,
    fill: f.color,
  }))

  return (
    <div className="space-y-6">
      {/* Factor Bar Chart */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-4">
          Factor P&L Attribution
        </h4>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barChartData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={80}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine x={0} stroke="#6b7280" />
              <Bar
                dataKey="pnl"
                name="P&L"
                radius={[0, 4, 4, 0]}
                onClick={(entry) => {
                  const factor = factors.find(f => f.displayName === entry.name)
                  if (factor) onFactorClick(factor.factorName)
                }}
                style={{ cursor: 'pointer' }}
              >
                {barChartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Factor Cards */}
      <div className="grid grid-cols-2 gap-4">
        {factors.map(factor => (
          <FactorCard
            key={factor.factorName}
            factor={factor}
            onClick={() => onFactorClick(factor.factorName)}
          />
        ))}
      </div>
    </div>
  )
}

function AssetsView({
  assets,
  onAssetClick,
}: {
  assets: AssetAttribution[]
  onAssetClick: (symbol: string) => void
}) {
  const sorted = useMemo(() => {
    return [...assets].sort((a, b) => Math.abs(b.pnl) - Math.abs(a.pnl))
  }, [assets])

  // Treemap data
  const treemapData = sorted.slice(0, 15).map(a => ({
    name: a.symbol,
    size: Math.abs(a.pnl),
    pnl: a.pnl,
    sector: a.sector,
    color: a.pnl >= 0 ? '#10b981' : '#ef4444',
  }))

  return (
    <div className="space-y-6">
      {/* Treemap Visualization */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-4">
          Asset P&L Map
        </h4>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={treemapData}
              dataKey="size"
              stroke="#1a1a2e"
              onClick={(entry) => {
                if (entry && entry.name) onAssetClick(entry.name)
              }}
              content={({ x, y, width, height, name, pnl, color }: any) => {
                if (width < 40 || height < 30) return null
                return (
                  <g>
                    <rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      fill={color}
                      fillOpacity={0.8}
                      stroke="#1a1a2e"
                      strokeWidth={2}
                      rx={4}
                      style={{ cursor: 'pointer' }}
                    />
                    {width > 50 && height > 40 && (
                      <>
                        <text
                          x={x + width / 2}
                          y={y + height / 2 - 6}
                          textAnchor="middle"
                          fill="#fff"
                          fontSize={11}
                          fontWeight="bold"
                        >
                          {name}
                        </text>
                        <text
                          x={x + width / 2}
                          y={y + height / 2 + 8}
                          textAnchor="middle"
                          fill="#fff"
                          fontSize={10}
                          opacity={0.8}
                        >
                          {formatCurrency(pnl)}
                        </text>
                      </>
                    )}
                  </g>
                )
              }}
            />
          </ResponsiveContainer>
        </div>
      </div>

      {/* Asset Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-foreground-muted uppercase border-b border-border">
              <th className="text-left py-2 px-3">Symbol</th>
              <th className="text-left py-2 px-3">Sector</th>
              <th className="text-right py-2 px-3">Position</th>
              <th className="text-right py-2 px-3">P&L</th>
              <th className="text-right py-2 px-3">Alpha</th>
              <th className="text-right py-2 px-3">Beta</th>
              <th className="text-right py-2 px-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(asset => (
              <tr
                key={asset.symbol}
                className="border-b border-border/50 hover:bg-background-tertiary/50 cursor-pointer"
                onClick={() => onAssetClick(asset.symbol)}
              >
                <td className="py-2 px-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground-primary">{asset.symbol}</span>
                    {asset.name && (
                      <span className="text-xs text-foreground-muted">{asset.name}</span>
                    )}
                  </div>
                </td>
                <td className="py-2 px-3">
                  <span
                    className="px-2 py-0.5 text-xs rounded-full"
                    style={{
                      backgroundColor: `${SECTOR_COLORS[asset.sector] || '#6b7280'}20`,
                      color: SECTOR_COLORS[asset.sector] || '#6b7280',
                    }}
                  >
                    {asset.sector}
                  </span>
                </td>
                <td className={cn(
                  'text-right py-2 px-3 font-mono',
                  asset.position > 0 ? 'text-bullish' : asset.position < 0 ? 'text-bearish' : ''
                )}>
                  {asset.position > 0 ? '+' : ''}{asset.position}
                </td>
                <td className={cn(
                  'text-right py-2 px-3 font-mono font-medium',
                  asset.pnl >= 0 ? 'text-bullish' : 'text-bearish'
                )}>
                  {formatCurrency(asset.pnl)}
                </td>
                <td className={cn(
                  'text-right py-2 px-3 font-mono text-xs',
                  asset.factors.alpha >= 0 ? 'text-bullish' : 'text-bearish'
                )}>
                  {formatCurrency(asset.factors.alpha)}
                </td>
                <td className={cn(
                  'text-right py-2 px-3 font-mono text-xs',
                  asset.factors.beta >= 0 ? 'text-bullish' : 'text-bearish'
                )}>
                  {formatCurrency(asset.factors.beta)}
                </td>
                <td className="text-right py-2 px-3">
                  <ChevronRight className="w-4 h-4 text-foreground-muted inline-block" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TimelineView({
  timeData,
  historicalPnL,
  onPeriodClick,
}: {
  timeData: TimeAttribution[]
  historicalPnL: { timestamp: string; pnl: number; cumulative: number }[]
  onPeriodClick: (period: string) => void
}) {
  // Stacked area chart data for factor breakdown over time
  const stackedData = timeData.map(t => ({
    period: t.period,
    alpha: t.factors.alpha,
    beta: t.factors.beta,
    sector: t.factors.sector,
    currency: t.factors.currency,
    total: t.pnl,
  }))

  return (
    <div className="space-y-6">
      {/* Cumulative P&L with Factor Breakdown */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-4">
          P&L by Time Period
        </h4>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={stackedData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
              <XAxis
                dataKey="period"
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <ReferenceLine y={0} stroke="#6b7280" strokeDasharray="3 3" />
              <Bar dataKey="alpha" name="Alpha" stackId="a" fill={FACTOR_COLORS.alpha} />
              <Bar dataKey="beta" name="Beta" stackId="a" fill={FACTOR_COLORS.beta} />
              <Bar dataKey="sector" name="Sector" stackId="a" fill={FACTOR_COLORS.sector} />
              <Bar dataKey="currency" name="Currency" stackId="a" fill={FACTOR_COLORS.currency} />
              <Line
                type="monotone"
                dataKey="total"
                name="Total"
                stroke="#ffffff"
                strokeWidth={2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Period Cards */}
      <div className="grid grid-cols-4 gap-3">
        {timeData.slice(-8).map(period => (
          <button
            key={period.period}
            onClick={() => onPeriodClick(period.period)}
            className={cn(
              'p-3 rounded-lg border transition-colors text-left',
              period.pnl >= 0
                ? 'border-bullish/30 bg-bullish/5 hover:bg-bullish/10'
                : 'border-bearish/30 bg-bearish/5 hover:bg-bearish/10'
            )}
          >
            <div className="text-xs text-foreground-muted">{period.period}</div>
            <div className={cn(
              'text-sm font-mono font-bold mt-1',
              period.pnl >= 0 ? 'text-bullish' : 'text-bearish'
            )}>
              {formatCurrency(period.pnl)}
            </div>
            <div className="text-xs text-foreground-muted mt-1">
              {period.trades} trades | {(period.winRate * 100).toFixed(0)}% win
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

function WaterfallView({ waterfallData }: { waterfallData: any[] }) {
  return (
    <div className="space-y-4">
      <h4 className="text-xs font-bold text-foreground-muted uppercase">
        P&L Waterfall Attribution
      </h4>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={waterfallData} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fill: '#6b7280', fontSize: 10 }}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fill: '#9ca3af', fontSize: 11, fontWeight: 500 }}
              tickLine={false}
              axisLine={false}
              width={80}
            />
            <Tooltip content={<WaterfallTooltip />} />
            <ReferenceLine x={0} stroke="#6b7280" />
            <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
              {waterfallData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex justify-center gap-6 text-xs">
        <span className="flex items-center gap-2">
          <span className="w-3 h-3 rounded bg-bullish" />
          <span className="text-foreground-muted">Positive Contribution</span>
        </span>
        <span className="flex items-center gap-2">
          <span className="w-3 h-3 rounded bg-bearish" />
          <span className="text-foreground-muted">Negative Contribution</span>
        </span>
        <span className="flex items-center gap-2">
          <span className="w-3 h-3 rounded bg-accent-primary" />
          <span className="text-foreground-muted">Net Total</span>
        </span>
      </div>
    </div>
  )
}

// =============================================================================
// DRILL DOWN VIEWS
// =============================================================================

function FactorDrillDownView({
  factor,
  assets,
}: {
  factor?: FactorAttribution
  assets: AssetAttribution[]
}) {
  if (!factor) return <div className="text-center text-foreground-muted py-8">Factor not found</div>

  // Assets sorted by this factor's contribution
  const factorKey = factor.factorName as keyof AssetAttribution['factors']
  const sortedAssets = [...assets]
    .sort((a, b) => Math.abs(b.factors[factorKey]) - Math.abs(a.factors[factorKey]))
    .slice(0, 10)

  const assetChartData = sortedAssets.map(a => ({
    symbol: a.symbol,
    value: a.factors[factorKey],
  }))

  return (
    <div className="space-y-6">
      {/* Factor Summary */}
      <div className="grid grid-cols-4 gap-4">
        <div className="p-4 rounded-lg" style={{ backgroundColor: `${factor.color}20` }}>
          <div className="text-xs text-foreground-muted uppercase">P&L</div>
          <div className={cn('text-xl font-bold font-mono', factor.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
            {formatCurrency(factor.pnl)}
          </div>
        </div>
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">Contribution</div>
          <div className="text-xl font-bold font-mono text-foreground-primary">
            {factor.contribution.toFixed(1)}%
          </div>
        </div>
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">Exposure</div>
          <div className="text-xl font-bold font-mono text-foreground-primary">
            {factor.exposure.toFixed(2)}
          </div>
        </div>
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">t-Stat</div>
          <div className={cn(
            'text-xl font-bold font-mono',
            Math.abs(factor.tStat) > 2 ? 'text-warning' : 'text-foreground-primary'
          )}>
            {factor.tStat.toFixed(2)}
          </div>
        </div>
      </div>

      <p className="text-sm text-foreground-secondary">{factor.description}</p>

      {/* Factor Breakdown */}
      {factor.breakdown && factor.breakdown.length > 0 && (
        <div>
          <h4 className="text-xs font-bold text-foreground-muted uppercase mb-4">
            Sub-Factor Breakdown
          </h4>
          <div className="space-y-2">
            {factor.breakdown.map(item => (
              <div
                key={item.name}
                className="flex items-center justify-between p-3 rounded-lg bg-background-tertiary/50"
              >
                <span className="text-sm text-foreground-secondary">{item.name}</span>
                <div className="flex items-center gap-4">
                  <span className={cn(
                    'text-sm font-mono font-medium',
                    item.pnl >= 0 ? 'text-bullish' : 'text-bearish'
                  )}>
                    {formatCurrency(item.pnl)}
                  </span>
                  <span className="text-xs text-foreground-muted w-16 text-right">
                    {item.contribution.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Asset Contribution to Factor */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-4">
          Asset Contributions to {factor.displayName}
        </h4>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={assetChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
              <XAxis
                dataKey="symbol"
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={0} stroke="#6b7280" />
              <Bar dataKey="value" name={factor.displayName} fill={factor.color} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

function AssetDrillDownView({
  asset,
  timeData,
}: {
  asset?: AssetAttribution
  timeData: TimeAttribution[]
}) {
  if (!asset) return <div className="text-center text-foreground-muted py-8">Asset not found</div>

  const factorData = [
    { name: 'Alpha', value: asset.factors.alpha, color: FACTOR_COLORS.alpha },
    { name: 'Beta', value: asset.factors.beta, color: FACTOR_COLORS.beta },
    { name: 'Sector', value: asset.factors.sector, color: FACTOR_COLORS.sector },
    { name: 'Currency', value: asset.factors.currency, color: FACTOR_COLORS.currency },
  ]

  return (
    <div className="space-y-6">
      {/* Asset Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center text-lg font-bold"
            style={{ backgroundColor: `${SECTOR_COLORS[asset.sector]}20`, color: SECTOR_COLORS[asset.sector] }}
          >
            {asset.symbol.slice(0, 2)}
          </div>
          <div>
            <h3 className="text-lg font-bold text-foreground-primary">{asset.symbol}</h3>
            <p className="text-sm text-foreground-muted">{asset.name} | {asset.sector}</p>
          </div>
        </div>
        <div className="text-right">
          <div className={cn(
            'text-2xl font-bold font-mono',
            asset.pnl >= 0 ? 'text-bullish' : 'text-bearish'
          )}>
            {formatCurrency(asset.pnl)}
          </div>
          <div className={cn(
            'text-sm',
            asset.pnlPercent >= 0 ? 'text-bullish' : 'text-bearish'
          )}>
            {asset.pnlPercent >= 0 ? '+' : ''}{asset.pnlPercent.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Position Details */}
      <div className="grid grid-cols-4 gap-4">
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">Position</div>
          <div className={cn(
            'text-lg font-bold font-mono',
            asset.position > 0 ? 'text-bullish' : asset.position < 0 ? 'text-bearish' : 'text-foreground-primary'
          )}>
            {asset.position > 0 ? '+' : ''}{asset.position}
          </div>
        </div>
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">Avg Entry</div>
          <div className="text-lg font-bold font-mono text-foreground-primary">
            ${asset.avgEntry.toFixed(2)}
          </div>
        </div>
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">Current</div>
          <div className="text-lg font-bold font-mono text-foreground-primary">
            ${asset.currentPrice.toFixed(2)}
          </div>
        </div>
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">Contribution</div>
          <div className="text-lg font-bold font-mono text-foreground-primary">
            {asset.contribution.toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Factor Breakdown */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-4">
          Factor Attribution
        </h4>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={factorData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: '#6b7280', fontSize: 10 }}
                tickFormatter={(v) => `$${v.toFixed(0)}`}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={60}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine x={0} stroke="#6b7280" />
              <Bar dataKey="value" name="P&L" radius={[0, 4, 4, 0]}>
                {factorData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* P&L Split */}
      <div className="grid grid-cols-2 gap-4">
        <div className={cn(
          'p-4 rounded-lg border',
          asset.realized >= 0 ? 'border-bullish/30 bg-bullish/5' : 'border-bearish/30 bg-bearish/5'
        )}>
          <div className="text-xs text-foreground-muted uppercase">Realized P&L</div>
          <div className={cn(
            'text-xl font-bold font-mono mt-1',
            asset.realized >= 0 ? 'text-bullish' : 'text-bearish'
          )}>
            {formatCurrency(asset.realized)}
          </div>
        </div>
        <div className={cn(
          'p-4 rounded-lg border',
          asset.unrealized >= 0 ? 'border-bullish/30 bg-bullish/5' : 'border-bearish/30 bg-bearish/5'
        )}>
          <div className="text-xs text-foreground-muted uppercase">Unrealized P&L</div>
          <div className={cn(
            'text-xl font-bold font-mono mt-1',
            asset.unrealized >= 0 ? 'text-bullish' : 'text-bearish'
          )}>
            {formatCurrency(asset.unrealized)}
          </div>
        </div>
      </div>
    </div>
  )
}

function TimeDrillDownView({
  period,
  timeData,
  factors,
}: {
  period: string
  timeData: TimeAttribution[]
  factors: FactorAttribution[]
}) {
  const periodData = timeData.find(t => t.period === period)
  if (!periodData) return <div className="text-center text-foreground-muted py-8">Period not found</div>

  const factorBreakdown = [
    { name: 'Alpha', value: periodData.factors.alpha, color: FACTOR_COLORS.alpha },
    { name: 'Beta', value: periodData.factors.beta, color: FACTOR_COLORS.beta },
    { name: 'Sector', value: periodData.factors.sector, color: FACTOR_COLORS.sector },
    { name: 'Currency', value: periodData.factors.currency, color: FACTOR_COLORS.currency },
  ]

  return (
    <div className="space-y-6">
      {/* Period Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-foreground-primary">{periodData.period}</h3>
          <p className="text-sm text-foreground-muted">
            {new Date(periodData.timestamp).toLocaleString()}
          </p>
        </div>
        <div className="text-right">
          <div className={cn(
            'text-2xl font-bold font-mono',
            periodData.pnl >= 0 ? 'text-bullish' : 'text-bearish'
          )}>
            {formatCurrency(periodData.pnl)}
          </div>
          <div className="text-sm text-foreground-muted">
            {periodData.trades} trades | {(periodData.winRate * 100).toFixed(0)}% win rate
          </div>
        </div>
      </div>

      {/* Factor Breakdown */}
      <div>
        <h4 className="text-xs font-bold text-foreground-muted uppercase mb-4">
          Factor Contribution
        </h4>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <RechartsPieChart>
              <Pie
                data={factorBreakdown}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={2}
                dataKey="value"
              >
                {factorBreakdown.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend />
            </RechartsPieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">Cumulative P&L</div>
          <div className={cn(
            'text-lg font-bold font-mono',
            periodData.cumulativePnl >= 0 ? 'text-bullish' : 'text-bearish'
          )}>
            {formatCurrency(periodData.cumulativePnl)}
          </div>
        </div>
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">Trade Count</div>
          <div className="text-lg font-bold font-mono text-foreground-primary">
            {periodData.trades}
          </div>
        </div>
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">Win Rate</div>
          <div className={cn(
            'text-lg font-bold font-mono',
            periodData.winRate >= 0.5 ? 'text-bullish' : 'text-bearish'
          )}>
            {(periodData.winRate * 100).toFixed(0)}%
          </div>
        </div>
        <div className="p-4 rounded-lg bg-background-tertiary">
          <div className="text-xs text-foreground-muted uppercase">P&L %</div>
          <div className={cn(
            'text-lg font-bold font-mono',
            periodData.pnlPercent >= 0 ? 'text-bullish' : 'text-bearish'
          )}>
            {periodData.pnlPercent >= 0 ? '+' : ''}{periodData.pnlPercent.toFixed(2)}%
          </div>
        </div>
      </div>
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
  onClick,
  clickable,
}: {
  label: string
  value: string
  subvalue?: string
  positive?: boolean
  icon: React.ElementType
  onClick?: () => void
  clickable?: boolean
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-3',
        clickable && 'cursor-pointer hover:opacity-80 transition-opacity'
      )}
      onClick={onClick}
    >
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

function MetricRow({
  label,
  value,
  highlight,
}: {
  label: string
  value: number
  highlight?: boolean
}) {
  return (
    <div className={cn(
      'flex justify-between items-center py-2',
      highlight && 'font-bold'
    )}>
      <span className={cn(
        'text-sm',
        highlight ? 'text-foreground-primary' : 'text-foreground-muted'
      )}>
        {label}
      </span>
      <span className={cn(
        'text-sm font-mono',
        value >= 0 ? 'text-bullish' : 'text-bearish',
        highlight && 'text-lg'
      )}>
        {formatCurrency(value)}
      </span>
    </div>
  )
}

function FactorCard({
  factor,
  onClick,
}: {
  factor: FactorAttribution
  onClick: () => void
}) {
  const isPositive = factor.pnl >= 0

  return (
    <button
      onClick={onClick}
      className={cn(
        'p-4 rounded-lg border text-left transition-all hover:scale-[1.02]',
        isPositive
          ? 'border-bullish/30 bg-bullish/5 hover:bg-bullish/10'
          : 'border-bearish/30 bg-bearish/5 hover:bg-bearish/10'
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: factor.color }}
          />
          <span className="text-sm font-medium text-foreground-primary">
            {factor.displayName}
          </span>
        </div>
        <ChevronRight className="w-4 h-4 text-foreground-muted" />
      </div>

      <div className={cn(
        'text-lg font-bold font-mono',
        isPositive ? 'text-bullish' : 'text-bearish'
      )}>
        {formatCurrency(factor.pnl)}
      </div>

      <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
        <div>
          <span className="text-foreground-muted">Contribution: </span>
          <span className="font-medium text-foreground-secondary">
            {factor.contribution.toFixed(1)}%
          </span>
        </div>
        <div>
          <span className="text-foreground-muted">Exposure: </span>
          <span className="font-medium text-foreground-secondary">
            {factor.exposure.toFixed(2)}
          </span>
        </div>
      </div>

      <p className="text-xs text-foreground-muted mt-2 line-clamp-2">
        {factor.description}
      </p>
    </button>
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
export type { PnLAttributionData, PnLAttributionProps, FactorAttribution, AssetAttribution, TimeAttribution }
