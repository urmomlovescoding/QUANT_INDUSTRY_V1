/**
 * Portfolio Management View
 * =========================
 * Institutional-grade portfolio management with real-time pricing,
 * holdings table, allocation charts, performance tracking, and position management.
 * Inspired by Bloomberg PORT, FactSet, and Black Diamond.
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Briefcase,
  Plus,
  Trash2,
  Save,
  Upload,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  DollarSign,
  PieChart,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
  AlertCircle,
  Wallet,
  ShieldCheck,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  CartesianGrid,
  Legend,
  Area,
  AreaChart,
} from 'recharts'
import { cn } from '@/utils/cn'
import { formatCurrency, formatPercent, formatNumber } from '@/utils/format'
import { DonutChart } from '@/components/charts/DonutChart'
import { Skeleton } from '@/components/ui/LoadingStates'

// ─── Types ────────────────────────────────────────────────────────────────────

interface Holding {
  symbol: string
  shares: number
  costBasis: number
  currentPrice: number
  previousClose: number
  sector: string
  dayChange: number
  dayChangePct: number
}

interface PortfolioSummary {
  equity: number
  cash: number
  buyingPower: number
  dayPnl: number
  dayPnlPct: number
  totalPnl: number
  totalPnlPct: number
  positionsCount: number
}

interface PerformancePoint {
  date: string
  value: number
  benchmark: number
}

type TimePeriod = '1D' | '1W' | '1M' | '3M' | '6M' | 'YTD' | '1Y'

// ─── Color Palette ────────────────────────────────────────────────────────────

const SECTOR_COLORS = [
  '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899',
  '#06b6d4', '#84cc16', '#f97316', '#6366f1', '#14b8a6',
  '#e11d48', '#a855f7',
]

const SECTOR_MAP: Record<string, string> = {
  AAPL: 'Technology', MSFT: 'Technology', GOOGL: 'Technology', GOOG: 'Technology',
  META: 'Technology', NVDA: 'Technology', AMD: 'Technology', INTC: 'Technology',
  TSLA: 'Consumer Disc.', AMZN: 'Consumer Disc.', HD: 'Consumer Disc.',
  JPM: 'Financials', BAC: 'Financials', GS: 'Financials', MS: 'Financials',
  JNJ: 'Healthcare', UNH: 'Healthcare', PFE: 'Healthcare', ABBV: 'Healthcare',
  XOM: 'Energy', CVX: 'Energy', COP: 'Energy',
  PG: 'Consumer Staples', KO: 'Consumer Staples', PEP: 'Consumer Staples',
  SPY: 'ETF', QQQ: 'ETF', DIA: 'ETF', IWM: 'ETF', VOO: 'ETF',
  VTI: 'ETF', ARKK: 'ETF',
  NEE: 'Utilities', DUK: 'Utilities',
  PLD: 'Real Estate', AMT: 'Real Estate',
  LMT: 'Industrials', CAT: 'Industrials', BA: 'Industrials',
  T: 'Communication', VZ: 'Communication', DIS: 'Communication',
  LIN: 'Materials', APD: 'Materials',
}

function getSector(symbol: string): string {
  return SECTOR_MAP[symbol.toUpperCase()] || 'Other'
}

// ─── Tooltip Styles ───────────────────────────────────────────────────────────

const chartTooltipStyle = {
  backgroundColor: '#1a1d20',
  border: '1px solid rgba(255,255,255,0.06)',
  borderRadius: '12px',
  boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function Portfolio() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [livePortfolio, setLivePortfolio] = useState<PortfolioSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [timePeriod, setTimePeriod] = useState<TimePeriod>('1M')
  const [perfData, setPerfData] = useState<PerformancePoint[]>([])
  const [allocationView, setAllocationView] = useState<'sector' | 'position'>('sector')
  const [sortField, setSortField] = useState<string>('value')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  // Add position form
  const [newTicker, setNewTicker] = useState('')
  const [newShares, setNewShares] = useState('')
  const [newCost, setNewCost] = useState('')
  const [addingPosition, setAddingPosition] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)

  // ─── Fetch live portfolio from API ────────────────────────────────────

  const fetchLivePortfolio = useCallback(async () => {
    try {
      const response = await fetch('/api/portfolio/live')
      if (response.ok) {
        const data = await response.json()
        if (data && data.equity !== undefined) {
          setLivePortfolio({
            equity: data.equity ?? 0,
            cash: data.cash ?? 0,
            buyingPower: data.buying_power ?? 0,
            dayPnl: data.day_pnl ?? 0,
            dayPnlPct: data.day_pnl_pct ?? 0,
            totalPnl: data.total_pnl ?? 0,
            totalPnlPct: data.total_pnl_pct ?? 0,
            positionsCount: data.positions_count ?? 0,
          })
        }
      }
    } catch {
      // Silently fail for live portfolio - we still have local holdings
    }
  }, [])

  // ─── Fetch positions from API ─────────────────────────────────────────

  const fetchPositions = useCallback(async () => {
    try {
      const response = await fetch('/api/portfolio/positions')
      if (response.ok) {
        const data = await response.json()
        const positions = data?.positions || data?.data || (Array.isArray(data) ? data : [])
        if (positions.length > 0) {
          const apiHoldings: Holding[] = positions.map((p: any) => ({
            symbol: p.symbol || p.ticker || '',
            shares: p.quantity || p.shares || p.qty || 0,
            costBasis: p.avg_entry_price || p.cost_basis || p.avg_cost || p.entry_price || 0,
            currentPrice: p.current_price || p.market_price || p.price || 0,
            previousClose: p.previous_close || p.prev_close || (p.current_price || 0) - (p.day_change || 0),
            sector: p.sector || getSector(p.symbol || ''),
            dayChange: p.day_change || p.unrealized_intraday_pl || 0,
            dayChangePct: p.day_change_pct || p.unrealized_intraday_plpc || 0,
          }))
          setHoldings(apiHoldings)
          return true
        }
      }
    } catch {
      // Fall through to localStorage
    }
    return false
  }, [])

  // ─── Generate performance data ────────────────────────────────────────

  // Performance data is only populated from real API data -- no fabricated data
  const generatePerfData = useCallback((_period: TimePeriod) => {
    // Only show real equity data from the API. No simulated data.
    // perfData remains empty until the backend provides actual equity history.
    setPerfData([])
  }, [])

  // ─── Initial load ─────────────────────────────────────────────────────

  useEffect(() => {
    const init = async () => {
      setLoading(true)

      // Try API first
      const [hasApiPositions] = await Promise.all([
        fetchPositions(),
        fetchLivePortfolio(),
      ])

      // Fall back to localStorage
      if (!hasApiPositions) {
        const saved = localStorage.getItem('portfolio_holdings')
        if (saved) {
          try {
            const parsed = JSON.parse(saved)
            setHoldings(parsed.map((h: any) => ({
              ...h,
              previousClose: h.previousClose || h.currentPrice,
              sector: h.sector || getSector(h.symbol),
              dayChange: h.dayChange || 0,
              dayChangePct: h.dayChangePct || 0,
            })))
          } catch {
            // ignore
          }
        }
      }

      setLoading(false)
    }
    init()
  }, [])

  // ─── Generate perf data when period or value changes ──────────────────

  useEffect(() => {
    generatePerfData(timePeriod)
  }, [timePeriod, generatePerfData])

  // ─── Auto-refresh prices every 30s ────────────────────────────────────

  useEffect(() => {
    const interval = setInterval(() => {
      if (holdings.length > 0) {
        refreshPrices(true)
      }
      fetchLivePortfolio()
    }, 30000)
    return () => clearInterval(interval)
  }, [holdings.length])

  // ─── Calculations ─────────────────────────────────────────────────────

  const totalValue = useMemo(
    () => holdings.reduce((sum, h) => sum + h.shares * h.currentPrice, 0),
    [holdings]
  )
  const totalCost = useMemo(
    () => holdings.reduce((sum, h) => sum + h.shares * h.costBasis, 0),
    [holdings]
  )
  const totalPnL = totalValue - totalCost
  const totalPnLPct = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0
  const totalDayPnL = useMemo(
    () => holdings.reduce((sum, h) => sum + h.dayChange * h.shares, 0),
    [holdings]
  )
  const totalDayPnLPct = totalValue > 0
    ? (totalDayPnL / (totalValue - totalDayPnL)) * 100
    : 0

  // ─── Sector allocation data ───────────────────────────────────────────

  const sectorAllocation = useMemo(() => {
    if (holdings.length === 0) return []
    const sectorMap: Record<string, number> = {}
    holdings.forEach(h => {
      const sector = h.sector || 'Other'
      sectorMap[sector] = (sectorMap[sector] || 0) + h.shares * h.currentPrice
    })
    return Object.entries(sectorMap)
      .map(([name, value], i) => ({
        name,
        value: totalValue > 0 ? (value / totalValue) * 100 : 0,
        rawValue: value,
        color: SECTOR_COLORS[i % SECTOR_COLORS.length],
      }))
      .sort((a, b) => b.value - a.value)
  }, [holdings, totalValue])

  // ─── Position allocation data ─────────────────────────────────────────

  const positionAllocation = useMemo(() => {
    if (holdings.length === 0) return []
    return holdings
      .map((h, i) => ({
        name: h.symbol,
        value: totalValue > 0 ? (h.shares * h.currentPrice / totalValue) * 100 : 0,
        rawValue: h.shares * h.currentPrice,
        color: SECTOR_COLORS[i % SECTOR_COLORS.length],
      }))
      .sort((a, b) => b.value - a.value)
  }, [holdings, totalValue])

  const allocationData = allocationView === 'sector' ? sectorAllocation : positionAllocation

  // ─── Sorted holdings ──────────────────────────────────────────────────

  const sortedHoldings = useMemo(() => {
    return [...holdings].sort((a, b) => {
      let aVal = 0, bVal = 0
      switch (sortField) {
        case 'symbol': return sortDir === 'asc' ? a.symbol.localeCompare(b.symbol) : b.symbol.localeCompare(a.symbol)
        case 'shares': aVal = a.shares; bVal = b.shares; break
        case 'cost': aVal = a.costBasis; bVal = b.costBasis; break
        case 'price': aVal = a.currentPrice; bVal = b.currentPrice; break
        case 'value': aVal = a.shares * a.currentPrice; bVal = b.shares * b.currentPrice; break
        case 'dayPnl': aVal = a.dayChange * a.shares; bVal = b.dayChange * b.shares; break
        case 'totalPnl': aVal = (a.currentPrice - a.costBasis) * a.shares; bVal = (b.currentPrice - b.costBasis) * b.shares; break
        case 'weight': aVal = a.shares * a.currentPrice; bVal = b.shares * b.currentPrice; break
        case 'sector': return sortDir === 'asc' ? a.sector.localeCompare(b.sector) : b.sector.localeCompare(a.sector)
        default: aVal = a.shares * a.currentPrice; bVal = b.shares * b.currentPrice
      }
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    })
  }, [holdings, sortField, sortDir])

  // ─── Actions ──────────────────────────────────────────────────────────

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  const addPosition = async () => {
    if (!newTicker || !newShares || !newCost) return
    setAddingPosition(true)
    setError(null)

    try {
      const response = await fetch(`/api/market/quote/${newTicker.toUpperCase()}`)
      let currentPrice = parseFloat(newCost)
      let dayChange = 0
      let dayChangePct = 0
      let prevClose = currentPrice

      if (response.ok) {
        const data = await response.json()
        const quoteData = data?.data || data
        if (quoteData?.price) {
          currentPrice = quoteData.price
          dayChange = quoteData.change || 0
          dayChangePct = quoteData.change_pct || 0
          prevClose = quoteData.prev_close || currentPrice - dayChange
        }
      }

      const symbol = newTicker.toUpperCase()
      setHoldings(prev => [...prev, {
        symbol,
        shares: parseFloat(newShares),
        costBasis: parseFloat(newCost),
        currentPrice,
        previousClose: prevClose,
        sector: getSector(symbol),
        dayChange,
        dayChangePct,
      }])
      setNewTicker('')
      setNewShares('')
      setNewCost('')
      setShowAddForm(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add position')
    } finally {
      setAddingPosition(false)
    }
  }

  const refreshPrices = async (silent = false) => {
    if (holdings.length === 0) return
    if (!silent) setRefreshing(true)
    setError(null)

    try {
      const symbols = holdings.map(h => h.symbol).join(',')
      const response = await fetch(`/api/market/tickers?symbols=${symbols}`)

      if (response.ok) {
        const data = await response.json()
        const tickers = data?.data || data?.tickers || (Array.isArray(data) ? data : [])
        const priceMap: Record<string, any> = {}
        tickers.forEach((t: any) => {
          priceMap[t.symbol] = t
        })

        setHoldings(prev => prev.map(h => {
          const ticker = priceMap[h.symbol]
          if (ticker) {
            return {
              ...h,
              currentPrice: ticker.price || h.currentPrice,
              dayChange: ticker.change || h.dayChange,
              dayChangePct: ticker.change_pct || h.dayChangePct,
              previousClose: ticker.prev_close || h.previousClose,
            }
          }
          return h
        }))
      } else {
        // Try individual quotes as fallback
        const updatedHoldings = await Promise.all(
          holdings.map(async (h) => {
            try {
              const res = await fetch(`/api/market/quote/${h.symbol}`)
              if (res.ok) {
                const qData = await res.json()
                const q = qData?.data || qData
                return {
                  ...h,
                  currentPrice: q?.price || h.currentPrice,
                  dayChange: q?.change || h.dayChange,
                  dayChangePct: q?.change_pct || h.dayChangePct,
                  previousClose: q?.prev_close || h.previousClose,
                }
              }
              return h
            } catch {
              return h
            }
          })
        )
        setHoldings(updatedHoldings)
      }
    } catch (err) {
      if (!silent) setError('Failed to refresh prices')
    } finally {
      if (!silent) setRefreshing(false)
    }
  }

  const removePosition = (symbol: string) => {
    setHoldings(prev => prev.filter(h => h.symbol !== symbol))
  }

  const savePortfolio = () => {
    localStorage.setItem('portfolio_holdings', JSON.stringify(holdings))
  }

  const loadPortfolio = () => {
    const saved = localStorage.getItem('portfolio_holdings')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        setHoldings(parsed.map((h: any) => ({
          ...h,
          previousClose: h.previousClose || h.currentPrice,
          sector: h.sector || getSector(h.symbol),
          dayChange: h.dayChange || 0,
          dayChangePct: h.dayChangePct || 0,
        })))
      } catch {
        setError('Failed to load saved portfolio')
      }
    }
  }

  // ─── Use live portfolio data if available ─────────────────────────────

  const displayEquity = livePortfolio?.equity || totalValue
  const displayCash = livePortfolio?.cash ?? 0
  const displayBuyingPower = livePortfolio?.buyingPower ?? 0
  const displayDayPnl = livePortfolio?.dayPnl ?? totalDayPnL
  const displayDayPnlPct = livePortfolio?.dayPnlPct ?? totalDayPnLPct
  const displayTotalPnl = livePortfolio?.totalPnl ?? totalPnL
  const displayTotalPnlPct = livePortfolio?.totalPnlPct ?? totalPnLPct

  // ─── Render ───────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-10 w-48" />
        </div>
        <div className="grid grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="card p-5">
              <Skeleton className="h-3 w-20 mb-3" />
              <Skeleton className="h-7 w-28 mb-2" />
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-8 card p-4"><Skeleton className="h-64 w-full" /></div>
          <div className="col-span-4 card p-4"><Skeleton className="h-64 w-full" /></div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-accent-primary/10">
            <Briefcase className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">PORTFOLIO MANAGEMENT</h1>
            <p className="text-xs text-foreground-muted">
              {holdings.length} positions | Real-time tracking
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Position
          </button>
          <button
            onClick={() => refreshPrices()}
            disabled={refreshing || holdings.length === 0}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin')} />
            Refresh
          </button>
          <button onClick={savePortfolio} className="btn-secondary flex items-center gap-2">
            <Save className="w-4 h-4" />
            Save
          </button>
          <button onClick={loadPortfolio} className="btn-secondary flex items-center gap-2">
            <Upload className="w-4 h-4" />
            Load
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-bearish flex-shrink-0" />
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {/* Add Position Form */}
      {showAddForm && (
        <div className="card p-4 animate-fade-in">
          <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-3">ADD POSITION</h3>
          <div className="flex items-end gap-4">
            <div className="flex-1 max-w-[120px]">
              <label className="block text-xs text-foreground-muted mb-1">Ticker</label>
              <input
                type="text"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === 'Enter' && addPosition()}
                className="input"
                placeholder="AAPL"
              />
            </div>
            <div className="flex-1 max-w-[120px]">
              <label className="block text-xs text-foreground-muted mb-1">Shares</label>
              <input
                type="number"
                value={newShares}
                onChange={(e) => setNewShares(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addPosition()}
                className="input"
                placeholder="100"
              />
            </div>
            <div className="flex-1 max-w-[140px]">
              <label className="block text-xs text-foreground-muted mb-1">Avg Cost ($)</label>
              <input
                type="number"
                value={newCost}
                onChange={(e) => setNewCost(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addPosition()}
                className="input"
                placeholder="150.00"
                step={0.01}
              />
            </div>
            <button
              onClick={addPosition}
              disabled={addingPosition || !newTicker || !newShares || !newCost}
              className="btn-primary flex items-center gap-2"
            >
              <Plus className={cn('w-4 h-4', addingPosition && 'animate-spin')} />
              {addingPosition ? 'Adding...' : 'Add'}
            </button>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-5 gap-4 stagger">
        <SummaryCard
          title="Total Value"
          value={formatCurrency(displayEquity)}
          icon={DollarSign}
          iconColor="text-accent-primary"
        />
        <SummaryCard
          title="Day P&L"
          value={`${displayDayPnl >= 0 ? '+' : ''}${formatCurrency(displayDayPnl)}`}
          subtitle={`${displayDayPnlPct >= 0 ? '+' : ''}${displayDayPnlPct.toFixed(2)}%`}
          icon={displayDayPnl >= 0 ? TrendingUp : TrendingDown}
          iconColor={displayDayPnl >= 0 ? 'text-bullish' : 'text-bearish'}
          valueColor={displayDayPnl >= 0 ? 'text-bullish' : 'text-bearish'}
        />
        <SummaryCard
          title="Total P&L"
          value={`${displayTotalPnl >= 0 ? '+' : ''}${formatCurrency(displayTotalPnl)}`}
          subtitle={`${displayTotalPnlPct >= 0 ? '+' : ''}${displayTotalPnlPct.toFixed(2)}%`}
          icon={displayTotalPnl >= 0 ? ArrowUpRight : ArrowDownRight}
          iconColor={displayTotalPnl >= 0 ? 'text-bullish' : 'text-bearish'}
          valueColor={displayTotalPnl >= 0 ? 'text-bullish' : 'text-bearish'}
        />
        <SummaryCard
          title="Cash"
          value={formatCurrency(displayCash)}
          icon={Wallet}
          iconColor="text-blue-400"
        />
        <SummaryCard
          title="Buying Power"
          value={formatCurrency(displayBuyingPower)}
          icon={ShieldCheck}
          iconColor="text-purple-400"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Performance Chart */}
        <div className="col-span-8 card p-4">
          <div className="chart-header">
            <h3 className="chart-title flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-accent-primary" />
              Portfolio Performance
            </h3>
            <div className="flex items-center gap-1 bg-background-tertiary rounded-lg p-1">
              {(['1D', '1W', '1M', '3M', '6M', 'YTD', '1Y'] as TimePeriod[]).map((period) => (
                <button
                  key={period}
                  onClick={() => setTimePeriod(period)}
                  className={cn(
                    'px-3 py-1 text-xs font-medium rounded-md transition-colors',
                    timePeriod === period
                      ? 'bg-accent-primary text-black'
                      : 'text-foreground-muted hover:text-foreground-primary'
                  )}
                >
                  {period}
                </button>
              ))}
            </div>
          </div>
          <div className="h-72">
            <div className="flex flex-col items-center justify-center h-full text-center">
              <BarChart3 className="w-10 h-10 text-foreground-muted/30 mb-3" />
              <p className="text-sm font-medium text-foreground-secondary mb-1">No Performance History</p>
              <p className="text-xs text-foreground-muted max-w-[280px]">Connect a broker to view real equity performance data over time</p>
            </div>
          </div>
          <div className="flex items-center gap-6 mt-2 text-xs text-foreground-muted">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-accent-primary rounded" />
              Portfolio
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-gray-500 rounded" />
              Benchmark (S&P 500)
            </span>
          </div>
        </div>

        {/* Allocation Chart */}
        <div className="col-span-4 card p-4">
          <div className="chart-header">
            <h3 className="chart-title flex items-center gap-2">
              <PieChart className="w-4 h-4 text-accent-primary" />
              Allocation
            </h3>
            <div className="flex items-center gap-1 bg-background-tertiary rounded-lg p-1">
              <button
                onClick={() => setAllocationView('sector')}
                className={cn(
                  'px-2 py-1 text-xs rounded-md transition-colors',
                  allocationView === 'sector'
                    ? 'bg-accent-primary text-black'
                    : 'text-foreground-muted hover:text-foreground-primary'
                )}
              >
                Sector
              </button>
              <button
                onClick={() => setAllocationView('position')}
                className={cn(
                  'px-2 py-1 text-xs rounded-md transition-colors',
                  allocationView === 'position'
                    ? 'bg-accent-primary text-black'
                    : 'text-foreground-muted hover:text-foreground-primary'
                )}
              >
                Position
              </button>
            </div>
          </div>

          {allocationData.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-foreground-muted text-sm">
              Add positions to see allocation
            </div>
          ) : (
            <>
              <div className="flex items-center justify-center h-40">
                <DonutChart
                  data={allocationData.map(d => ({
                    name: d.name,
                    value: d.value,
                    color: d.color,
                  }))}
                  centerLabel={holdings.length.toString()}
                  centerSubLabel={allocationView === 'sector' ? 'Sectors' : 'Positions'}
                  size={140}
                />
              </div>
              <div className="space-y-1.5 mt-3 max-h-40 overflow-y-auto scrollbar-thin">
                {allocationData.map((item) => (
                  <div key={item.name} className="flex items-center justify-between text-xs px-1">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                      <span className="text-foreground-secondary truncate max-w-[100px]">{item.name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-foreground-muted">{formatCurrency(item.rawValue)}</span>
                      <span className="font-mono font-medium text-foreground-primary w-12 text-right">
                        {item.value.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Holdings Table */}
      <div className="card overflow-hidden">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground-primary">
            Holdings ({holdings.length})
          </h3>
          <span className="text-xs text-foreground-muted">
            Click column headers to sort
          </span>
        </div>
        {holdings.length === 0 ? (
          <div className="p-12 text-center text-foreground-muted">
            <Briefcase className="w-12 h-12 mx-auto mb-4 opacity-30" />
            <p className="text-lg font-medium text-foreground-secondary mb-1">No Holdings</p>
            <p className="text-sm">Click "Add Position" to build your portfolio</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table text-xs">
              <thead>
                <tr>
                  <SortHeader field="symbol" label="Symbol" current={sortField} dir={sortDir} onClick={handleSort} />
                  <SortHeader field="shares" label="Shares" current={sortField} dir={sortDir} onClick={handleSort} align="right" />
                  <SortHeader field="cost" label="Avg Cost" current={sortField} dir={sortDir} onClick={handleSort} align="right" />
                  <SortHeader field="price" label="Price" current={sortField} dir={sortDir} onClick={handleSort} align="right" />
                  <SortHeader field="value" label="Mkt Value" current={sortField} dir={sortDir} onClick={handleSort} align="right" />
                  <SortHeader field="dayPnl" label="Day P&L" current={sortField} dir={sortDir} onClick={handleSort} align="right" />
                  <SortHeader field="totalPnl" label="Total P&L" current={sortField} dir={sortDir} onClick={handleSort} align="right" />
                  <SortHeader field="weight" label="% Port" current={sortField} dir={sortDir} onClick={handleSort} align="right" />
                  <SortHeader field="sector" label="Sector" current={sortField} dir={sortDir} onClick={handleSort} />
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedHoldings.map((h) => {
                  const value = h.shares * h.currentPrice
                  const cost = h.shares * h.costBasis
                  const pnl = value - cost
                  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0
                  const dayPnlTotal = h.dayChange * h.shares
                  const weight = totalValue > 0 ? (value / totalValue) * 100 : 0

                  return (
                    <tr key={h.symbol}>
                      <td>
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-lg bg-accent-primary/10 flex items-center justify-center text-xs font-bold text-accent-primary">
                            {h.symbol.slice(0, 2)}
                          </div>
                          <span className="font-semibold text-foreground-primary">{h.symbol}</span>
                        </div>
                      </td>
                      <td className="text-right font-mono">{formatNumber(h.shares)}</td>
                      <td className="text-right font-mono">${h.costBasis.toFixed(2)}</td>
                      <td className="text-right font-mono font-medium">${h.currentPrice.toFixed(2)}</td>
                      <td className="text-right font-mono font-medium">{formatCurrency(value)}</td>
                      <td className={cn('text-right font-mono', dayPnlTotal >= 0 ? 'text-bullish' : 'text-bearish')}>
                        <div>
                          {dayPnlTotal >= 0 ? '+' : ''}{formatCurrency(dayPnlTotal)}
                        </div>
                        <div className="text-[10px] opacity-70">
                          {h.dayChangePct >= 0 ? '+' : ''}{h.dayChangePct.toFixed(2)}%
                        </div>
                      </td>
                      <td className={cn('text-right font-mono', pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                        <div>
                          {pnl >= 0 ? '+' : ''}{formatCurrency(pnl)}
                        </div>
                        <div className="text-[10px] opacity-70">
                          {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                        </div>
                      </td>
                      <td className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 h-1.5 bg-background-tertiary rounded-full overflow-hidden">
                            <div
                              className="h-full bg-accent-primary rounded-full transition-all"
                              style={{ width: `${Math.min(weight, 100)}%` }}
                            />
                          </div>
                          <span className="font-mono w-10 text-right">{weight.toFixed(1)}%</span>
                        </div>
                      </td>
                      <td>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-background-tertiary text-foreground-secondary">
                          {h.sector}
                        </span>
                      </td>
                      <td className="text-right">
                        <button
                          onClick={() => removePosition(h.symbol)}
                          className="p-1.5 rounded-lg text-foreground-muted hover:text-bearish hover:bg-bearish/10 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
              {/* Totals Row */}
              <tfoot>
                <tr className="border-t-2 border-border">
                  <td className="font-bold text-foreground-primary">TOTAL</td>
                  <td className="text-right font-mono font-bold">
                    {formatNumber(holdings.reduce((s, h) => s + h.shares, 0))}
                  </td>
                  <td />
                  <td />
                  <td className="text-right font-mono font-bold">{formatCurrency(totalValue)}</td>
                  <td className={cn('text-right font-mono font-bold', totalDayPnL >= 0 ? 'text-bullish' : 'text-bearish')}>
                    {totalDayPnL >= 0 ? '+' : ''}{formatCurrency(totalDayPnL)}
                  </td>
                  <td className={cn('text-right font-mono font-bold', totalPnL >= 0 ? 'text-bullish' : 'text-bearish')}>
                    {totalPnL >= 0 ? '+' : ''}{formatCurrency(totalPnL)}
                  </td>
                  <td className="text-right font-mono font-bold">100.0%</td>
                  <td />
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Subcomponents ────────────────────────────────────────────────────────────

function SummaryCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconColor = 'text-foreground-muted',
  valueColor,
}: {
  title: string
  value: string
  subtitle?: string
  icon: any
  iconColor?: string
  valueColor?: string
}) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-foreground-muted uppercase tracking-wider">{title}</span>
        <Icon className={cn('w-4 h-4', iconColor)} />
      </div>
      <div className={cn('text-xl font-bold font-mono', valueColor || 'text-foreground-primary')}>
        {value}
      </div>
      {subtitle && (
        <div className={cn('text-xs font-mono mt-0.5', valueColor || 'text-foreground-muted')}>
          {subtitle}
        </div>
      )}
    </div>
  )
}

function SortHeader({
  field,
  label,
  current,
  dir,
  onClick,
  align = 'left',
}: {
  field: string
  label: string
  current: string
  dir: 'asc' | 'desc'
  onClick: (field: string) => void
  align?: 'left' | 'right'
}) {
  const isActive = current === field
  return (
    <th
      className={cn('cursor-pointer select-none hover:text-foreground-primary transition-colors', align === 'right' && 'text-right')}
      onClick={() => onClick(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {isActive && (
          <span className="text-accent-primary">{dir === 'asc' ? '\u2191' : '\u2193'}</span>
        )}
      </span>
    </th>
  )
}
