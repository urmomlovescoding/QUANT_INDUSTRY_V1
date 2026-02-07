import { useState, useEffect, useCallback } from 'react'
import {
  Building,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  DollarSign,
  BarChart3,
  Activity,
  Loader2,
  RefreshCw,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from 'recharts'

// Prop firm rules configuration
const PROP_FIRM_RULES = {
  FTMO: {
    name: 'FTMO',
    maxDailyLoss: 5,
    maxTotalLoss: 10,
    profitTarget: 10,
    minTradingDays: 4,
    maxTradingDays: 30,
  },
  TopstepTrader: {
    name: 'TopstepTrader',
    maxDailyLoss: 4.5,
    maxTotalLoss: 9,
    profitTarget: 6,
    minTradingDays: 5,
    maxTradingDays: null,
  },
  TakeProfit: {
    name: 'TakeProfit Trader',
    maxDailyLoss: 4,
    maxTotalLoss: 8,
    profitTarget: 8,
    minTradingDays: 3,
    maxTradingDays: 45,
  },
}

interface EquityDataPoint {
  day: number
  balance: number
  dailyPnL: number
  date: string
}

interface Trade {
  id: string | number
  symbol: string
  side: string
  pnl: number
  time: string
  date: string
  strategy?: string
}

export function TPTDashboard() {
  const [selectedFirm, setSelectedFirm] = useState<keyof typeof PROP_FIRM_RULES>('FTMO')
  const [accountSize, setAccountSize] = useState(100000)
  const [equityData, setEquityData] = useState<EquityDataPoint[]>([])
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      // Fetch brain status, feedback metrics, closed trades, and performance history in parallel
      const [brainRes, feedbackRes, tradesRes, perfHistRes] = await Promise.all([
        fetch('/api/brain-v6/status').catch(() => null),
        fetch('/api/feedback/status').catch(() => null),
        fetch('/api/trades/closed?limit=50').catch(() => null),
        fetch('/api/feedback/performance-history?days=30').catch(() => null),
      ])

      // Parse brain status for account/metrics info
      let brainData: any = null
      if (brainRes?.ok) {
        brainData = await brainRes.json()
      }

      // Parse feedback status
      let feedbackData: any = null
      if (feedbackRes?.ok) {
        feedbackData = await feedbackRes.json()
      }

      // Parse closed trades
      let closedTrades: any[] = []
      if (tradesRes?.ok) {
        const tradesJson = await tradesRes.json()
        if (Array.isArray(tradesJson)) {
          closedTrades = tradesJson
        } else if (tradesJson.trades && Array.isArray(tradesJson.trades)) {
          closedTrades = tradesJson.trades
        }
      }

      // Parse performance history for equity curve
      let perfHistory: any[] = []
      if (perfHistRes?.ok) {
        const perfJson = await perfHistRes.json()
        if (Array.isArray(perfJson)) {
          perfHistory = perfJson
        }
      }

      // Determine account size from brain config or use default
      if (brainData?.config?.account_balance) {
        setAccountSize(brainData.config.account_balance)
      } else if (brainData?.ruleset?.account_size) {
        setAccountSize(brainData.ruleset.account_size)
      }

      // Build equity curve from performance history or closed trades
      const equity: EquityDataPoint[] = []
      if (perfHistory.length > 0) {
        let runningBalance = accountSize
        perfHistory.forEach((entry: any, i: number) => {
          const dailyPnL = entry.pnl || entry.daily_pnl || 0
          runningBalance += dailyPnL
          equity.push({
            day: i + 1,
            balance: runningBalance,
            dailyPnL,
            date: entry.date
              ? new Date(entry.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
              : `Day ${i + 1}`,
          })
        })
      } else if (closedTrades.length > 0) {
        // Build equity curve from trade PnLs
        let runningBalance = accountSize
        // Group trades by date
        const tradesByDate = new Map<string, number>()
        closedTrades.forEach((t: any) => {
          const dateStr = t.exitTime || t.exit_time || t.entryTime || t.entry_time || new Date().toISOString()
          const dateKey = new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
          const pnl = t.realizedPnl ?? t.pnl ?? 0
          tradesByDate.set(dateKey, (tradesByDate.get(dateKey) || 0) + pnl)
        })

        let dayIndex = 0
        tradesByDate.forEach((dailyPnL, dateKey) => {
          runningBalance += dailyPnL
          equity.push({
            day: ++dayIndex,
            balance: runningBalance,
            dailyPnL,
            date: dateKey,
          })
        })
      }

      if (equity.length === 0) {
        // Show at least the starting balance
        equity.push({
          day: 1,
          balance: accountSize,
          dailyPnL: 0,
          date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        })
      }

      setEquityData(equity)

      // Map closed trades to display format
      const mappedTrades: Trade[] = closedTrades.slice(0, 25).map((t: any, i: number) => {
        const exitTime = t.exitTime || t.exit_time || t.entryTime || t.entry_time || new Date().toISOString()
        return {
          id: t.id || i + 1,
          symbol: t.symbol || 'UNKNOWN',
          side: (t.side || t.direction || 'LONG').toUpperCase(),
          pnl: t.realizedPnl ?? t.pnl ?? 0,
          time: new Date(exitTime).toLocaleTimeString('en-US', { hour12: false }),
          date: new Date(exitTime).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
          strategy: t.strategy,
        }
      })
      setTrades(mappedTrades)

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load TPT dashboard data')
    } finally {
      setLoading(false)
    }
  }, [accountSize])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [fetchData])

  const rules = PROP_FIRM_RULES[selectedFirm]
  const currentBalance = equityData.length > 0 ? equityData[equityData.length - 1].balance : accountSize
  const totalPnL = currentBalance - accountSize
  const totalPnLPercent = (totalPnL / accountSize) * 100

  // Calculate daily P&L
  const todayPnL = equityData.length > 0 ? equityData[equityData.length - 1].dailyPnL : 0
  const todayPnLPercent = (todayPnL / accountSize) * 100

  // Calculate drawdown
  const maxBalance = equityData.length > 0 ? Math.max(...equityData.map(d => d.balance)) : accountSize
  const drawdown = ((maxBalance - currentBalance) / maxBalance) * 100

  // Calculate trading days
  const tradingDays = equityData.filter(d => Math.abs(d.dailyPnL) > 0).length

  // Check rule violations
  const dailyLossViolated = Math.abs(todayPnLPercent) > rules.maxDailyLoss && todayPnL < 0
  const totalLossViolated = Math.abs(totalPnLPercent) > rules.maxTotalLoss && totalPnL < 0
  const profitTargetReached = totalPnLPercent >= rules.profitTarget
  const minDaysReached = tradingDays >= rules.minTradingDays

  // Win/Loss breakdown
  const winningTrades = trades.filter(t => t.pnl > 0)
  const losingTrades = trades.filter(t => t.pnl < 0)
  const winRate = trades.length > 0 ? (winningTrades.length / trades.length) * 100 : 0

  if (loading && equityData.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Building className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">TPT DASHBOARD</h1>
            <p className="text-xs text-foreground-muted">Prop Firm Trading Performance</p>
          </div>
        </div>
        <div className="card p-12 flex items-center justify-center">
          <Loader2 className="w-6 h-6 text-accent-primary animate-spin" />
          <span className="ml-3 text-foreground-muted">Loading dashboard data...</span>
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
            <Building className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">TPT DASHBOARD</h1>
            <p className="text-xs text-foreground-muted">Prop Firm Trading Performance</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            className="p-2 rounded bg-background-tertiary hover:bg-background-secondary transition-colors"
            title="Refresh"
          >
            <RefreshCw className={cn('w-4 h-4 text-foreground-muted', loading && 'animate-spin')} />
          </button>
          {/* Firm Selector */}
          <select
            value={selectedFirm}
            onChange={(e) => setSelectedFirm(e.target.value as keyof typeof PROP_FIRM_RULES)}
            className="px-4 py-2 text-sm bg-background-secondary border border-border rounded-lg text-foreground-primary focus:outline-none focus:border-accent-primary"
          >
            {Object.keys(PROP_FIRM_RULES).map(firm => (
              <option key={firm} value={firm}>{PROP_FIRM_RULES[firm as keyof typeof PROP_FIRM_RULES].name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="card p-3 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {/* Status Banner */}
      {(dailyLossViolated || totalLossViolated) ? (
        <div className="p-4 bg-bearish/20 border border-bearish rounded-lg flex items-center gap-3">
          <AlertTriangle className="w-6 h-6 text-bearish" />
          <div>
            <p className="font-bold text-bearish">RULE VIOLATION DETECTED</p>
            <p className="text-sm text-bearish/80">
              {dailyLossViolated && 'Daily loss limit exceeded. '}
              {totalLossViolated && 'Total loss limit exceeded. '}
              Stop trading immediately.
            </p>
          </div>
        </div>
      ) : profitTargetReached && minDaysReached ? (
        <div className="p-4 bg-bullish/20 border border-bullish rounded-lg flex items-center gap-3">
          <CheckCircle className="w-6 h-6 text-bullish" />
          <div>
            <p className="font-bold text-bullish">CHALLENGE PASSED!</p>
            <p className="text-sm text-bullish/80">
              Congratulations! You've reached the profit target with minimum trading days.
            </p>
          </div>
        </div>
      ) : null}

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left: Equity Curve & Performance */}
        <div className="col-span-8 space-y-4">
          {/* Account Overview */}
          <div className="grid grid-cols-4 gap-4">
            <StatCard
              icon={<DollarSign className="w-5 h-5" />}
              label="Account Balance"
              value={`$${currentBalance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              trend={totalPnL >= 0 ? 'up' : 'down'}
            />
            <StatCard
              icon={<TrendingUp className="w-5 h-5" />}
              label="Total P&L"
              value={`${totalPnL >= 0 ? '+' : ''}$${totalPnL.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              subtext={`${totalPnLPercent >= 0 ? '+' : ''}${totalPnLPercent.toFixed(2)}%`}
              trend={totalPnL >= 0 ? 'up' : 'down'}
            />
            <StatCard
              icon={<Activity className="w-5 h-5" />}
              label="Today's P&L"
              value={`${todayPnL >= 0 ? '+' : ''}$${todayPnL.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              subtext={`${todayPnLPercent >= 0 ? '+' : ''}${todayPnLPercent.toFixed(2)}%`}
              trend={todayPnL >= 0 ? 'up' : 'down'}
            />
            <StatCard
              icon={<BarChart3 className="w-5 h-5" />}
              label="Win Rate"
              value={`${winRate.toFixed(1)}%`}
              subtext={`${winningTrades.length}W / ${losingTrades.length}L`}
              trend={winRate >= 50 ? 'up' : 'down'}
            />
          </div>

          {/* Equity Curve */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-4">Equity Curve</h3>
            {equityData.length <= 1 ? (
              <div className="h-64 flex items-center justify-center text-foreground-muted text-sm">
                No equity data yet. Trades will populate the chart as they are executed.
              </div>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={equityData}>
                    <defs>
                      <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={totalPnL >= 0 ? '#00c853' : '#ff5252'} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={totalPnL >= 0 ? '#00c853' : '#ff5252'} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="date"
                      tick={{ fill: '#666', fontSize: 10 }}
                      axisLine={{ stroke: '#333' }}
                      tickLine={{ stroke: '#333' }}
                    />
                    <YAxis
                      domain={['auto', 'auto']}
                      tick={{ fill: '#666', fontSize: 10 }}
                      axisLine={{ stroke: '#333' }}
                      tickLine={{ stroke: '#333' }}
                      tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`}
                      width={60}
                    />
                    <Tooltip
                      contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: '8px' }}
                      labelStyle={{ color: '#888' }}
                      formatter={(value: number) => [`$${value.toLocaleString(undefined, { minimumFractionDigits: 2 })}`, 'Balance']}
                    />
                    <Area
                      type="monotone"
                      dataKey="balance"
                      stroke={totalPnL >= 0 ? '#00c853' : '#ff5252'}
                      strokeWidth={2}
                      fill="url(#equityGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Daily P&L Chart */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-4">Daily P&L</h3>
            {equityData.length <= 1 ? (
              <div className="h-40 flex items-center justify-center text-foreground-muted text-sm">
                No daily P&L data available yet.
              </div>
            ) : (
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={equityData}>
                    <XAxis
                      dataKey="date"
                      tick={{ fill: '#666', fontSize: 10 }}
                      axisLine={{ stroke: '#333' }}
                      tickLine={{ stroke: '#333' }}
                    />
                    <YAxis
                      tick={{ fill: '#666', fontSize: 10 }}
                      axisLine={{ stroke: '#333' }}
                      tickLine={{ stroke: '#333' }}
                      tickFormatter={(v) => `$${v}`}
                      width={50}
                    />
                    <Tooltip
                      contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: '8px' }}
                      labelStyle={{ color: '#888' }}
                      formatter={(value: number) => [`$${value.toFixed(2)}`, 'P&L']}
                    />
                    <Bar dataKey="dailyPnL" radius={[4, 4, 0, 0]}>
                      {equityData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.dailyPnL >= 0 ? '#00c853' : '#ff5252'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>

        {/* Right: Rules & Progress */}
        <div className="col-span-4 space-y-4">
          {/* Rule Compliance */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-4">Rule Compliance</h3>
            <div className="space-y-4">
              {/* Daily Loss Limit */}
              <RuleProgress
                label="Daily Loss Limit"
                current={Math.abs(todayPnL < 0 ? todayPnL : 0)}
                max={accountSize * (rules.maxDailyLoss / 100)}
                unit="$"
                isViolated={dailyLossViolated}
                isLoss={true}
              />

              {/* Total Loss Limit */}
              <RuleProgress
                label="Max Drawdown"
                current={drawdown}
                max={rules.maxTotalLoss}
                unit="%"
                isViolated={totalLossViolated}
                isLoss={true}
              />

              {/* Profit Target */}
              <RuleProgress
                label="Profit Target"
                current={Math.max(0, totalPnLPercent)}
                max={rules.profitTarget}
                unit="%"
                isViolated={false}
                isLoss={false}
                isTarget={true}
              />

              {/* Trading Days */}
              <RuleProgress
                label="Trading Days"
                current={tradingDays}
                max={rules.minTradingDays}
                unit=" days"
                isViolated={false}
                isLoss={false}
                isTarget={true}
              />
            </div>
          </div>

          {/* Challenge Info */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">{rules.name} Rules</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-foreground-muted">Account Size</span>
                <span className="font-mono text-foreground-primary">${accountSize.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Max Daily Loss</span>
                <span className="font-mono text-bearish">{rules.maxDailyLoss}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Max Total Loss</span>
                <span className="font-mono text-bearish">{rules.maxTotalLoss}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Profit Target</span>
                <span className="font-mono text-bullish">{rules.profitTarget}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-foreground-muted">Min Trading Days</span>
                <span className="font-mono text-foreground-primary">{rules.minTradingDays}</span>
              </div>
              {rules.maxTradingDays && (
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Time Limit</span>
                  <span className="font-mono text-foreground-primary">{rules.maxTradingDays} days</span>
                </div>
              )}
            </div>
          </div>

          {/* Recent Trades */}
          <div className="card">
            <h3 className="text-sm font-medium text-foreground-primary mb-3">Recent Trades</h3>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {trades.length === 0 ? (
                <div className="text-xs text-foreground-muted text-center py-4">
                  No trades recorded yet.
                </div>
              ) : (
                trades.slice(0, 8).map((trade) => (
                  <div key={trade.id} className="flex items-center justify-between py-1 border-b border-border/50">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'text-[10px] font-bold px-1.5 py-0.5 rounded',
                        trade.side === 'LONG' || trade.side === 'BUY' ? 'bg-bullish/20 text-bullish' : 'bg-bearish/20 text-bearish'
                      )}>
                        {trade.side}
                      </span>
                      <span className="text-xs text-foreground-secondary">{trade.symbol}</span>
                    </div>
                    <span className={cn(
                      'text-xs font-mono font-bold',
                      trade.pnl >= 0 ? 'text-bullish' : 'text-bearish'
                    )}>
                      {trade.pnl >= 0 ? '+' : ''}{typeof trade.pnl === 'number' ? trade.pnl.toFixed(2) : trade.pnl}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string
  subtext?: string
  trend: 'up' | 'down'
}

function StatCard({ icon, label, value, subtext, trend }: StatCardProps) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-2">
        <span className={cn(trend === 'up' ? 'text-bullish' : 'text-bearish')}>{icon}</span>
        <span className="text-xs text-foreground-muted">{label}</span>
      </div>
      <div className={cn('text-xl font-bold', trend === 'up' ? 'text-bullish' : 'text-bearish')}>
        {value}
      </div>
      {subtext && (
        <div className="text-xs text-foreground-muted mt-1">{subtext}</div>
      )}
    </div>
  )
}

interface RuleProgressProps {
  label: string
  current: number
  max: number
  unit: string
  isViolated: boolean
  isLoss: boolean
  isTarget?: boolean
}

function RuleProgress({ label, current, max, unit, isViolated, isLoss, isTarget }: RuleProgressProps) {
  const percentage = Math.min(100, (current / max) * 100)
  const displayCurrent = unit === '%' ? current.toFixed(2) : current.toLocaleString(undefined, { maximumFractionDigits: 0 })
  const displayMax = unit === '%' ? max.toFixed(0) : max.toLocaleString(undefined, { maximumFractionDigits: 0 })

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-foreground-muted">{label}</span>
        <span className={cn(
          'font-mono',
          isViolated ? 'text-bearish' : isTarget && percentage >= 100 ? 'text-bullish' : 'text-foreground-primary'
        )}>
          {displayCurrent}{unit} / {displayMax}{unit}
        </span>
      </div>
      <div className="h-2 bg-background-primary rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            isViolated ? 'bg-bearish' : isTarget ? 'bg-bullish' : isLoss ? (percentage > 80 ? 'bg-yellow-500' : 'bg-accent-primary') : 'bg-accent-primary'
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {isViolated && (
        <div className="flex items-center gap-1 mt-1">
          <XCircle className="w-3 h-3 text-bearish" />
          <span className="text-[10px] text-bearish">Limit exceeded!</span>
        </div>
      )}
      {isTarget && percentage >= 100 && !isViolated && (
        <div className="flex items-center gap-1 mt-1">
          <CheckCircle className="w-3 h-3 text-bullish" />
          <span className="text-[10px] text-bullish">Target reached!</span>
        </div>
      )}
    </div>
  )
}
