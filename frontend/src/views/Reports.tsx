import { useState, useMemo } from 'react'
import {
  ClipboardList,
  Download,
  FileText,
  Calendar,
  TrendingUp,
  TrendingDown,
  BarChart3,
  PieChart as PieChartIcon,
  RefreshCw,
  Filter,
  Printer,
  Share2,
  Clock,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  CartesianGrid,
  Legend,
} from 'recharts'

interface ReportData {
  summary: {
    totalPnl: number
    totalTrades: number
    winRate: number
    profitFactor: number
    sharpeRatio: number
    maxDrawdown: number
    avgWin: number
    avgLoss: number
    bestTrade: number
    worstTrade: number
  }
  equityCurve: { date: string; equity: number }[]
  tradesBySymbol: { symbol: string; pnl: number; trades: number }[]
  tradesByStrategy: { strategy: string; pnl: number; trades: number; winRate: number }[]
  monthlyReturns: { month: string; return: number }[]
  drawdownHistory: { date: string; drawdown: number }[]
}

// Generate report data
const generateReportData = (days: number): ReportData => {
  const equityCurve = []
  const drawdownHistory = []
  let equity = 100000
  let peak = equity

  for (let i = 0; i < days; i++) {
    const dailyReturn = (Math.random() - 0.45) * 0.03
    equity *= 1 + dailyReturn
    peak = Math.max(peak, equity)
    const drawdown = ((peak - equity) / peak) * 100

    equityCurve.push({
      date: new Date(Date.now() - (days - i) * 24 * 60 * 60 * 1000).toLocaleDateString(),
      equity: Math.round(equity),
    })
    drawdownHistory.push({
      date: new Date(Date.now() - (days - i) * 24 * 60 * 60 * 1000).toLocaleDateString(),
      drawdown: -drawdown,
    })
  }

  const totalPnl = equity - 100000
  const pnlPercent = (totalPnl / 100000) * 100

  return {
    summary: {
      totalPnl,
      totalTrades: Math.floor(Math.random() * 200) + 100,
      winRate: 55 + Math.random() * 15,
      profitFactor: 1.2 + Math.random() * 0.8,
      sharpeRatio: 1.0 + Math.random() * 1.0,
      maxDrawdown: Math.max(...drawdownHistory.map(d => -d.drawdown)),
      avgWin: 250 + Math.random() * 200,
      avgLoss: -(150 + Math.random() * 100),
      bestTrade: 2500 + Math.random() * 2000,
      worstTrade: -(1000 + Math.random() * 1500),
    },
    equityCurve,
    drawdownHistory,
    tradesBySymbol: [
      { symbol: 'NVDA', pnl: 4523, trades: 28 },
      { symbol: 'AAPL', pnl: 2845, trades: 35 },
      { symbol: 'TSLA', pnl: -1230, trades: 22 },
      { symbol: 'MSFT', pnl: 1890, trades: 31 },
      { symbol: 'META', pnl: 3120, trades: 19 },
      { symbol: 'AMZN', pnl: 2156, trades: 25 },
    ],
    tradesByStrategy: [
      { strategy: 'Momentum', pnl: 5420, trades: 45, winRate: 62 },
      { strategy: 'Mean Reversion', pnl: 3280, trades: 38, winRate: 58 },
      { strategy: 'Trend Following', pnl: 4150, trades: 52, winRate: 55 },
      { strategy: 'ML Ensemble', pnl: 2890, trades: 28, winRate: 68 },
    ],
    monthlyReturns: [
      { month: 'Aug', return: 3.2 },
      { month: 'Sep', return: -1.5 },
      { month: 'Oct', return: 4.8 },
      { month: 'Nov', return: 2.1 },
      { month: 'Dec', return: 5.3 },
      { month: 'Jan', return: -0.8 },
    ],
  }
}

type DateRange = '7d' | '30d' | '90d' | '1y' | 'all'

export function Reports() {
  const [dateRange, setDateRange] = useState<DateRange>('30d')
  const [isGenerating, setIsGenerating] = useState(false)

  const days = dateRange === '7d' ? 7 : dateRange === '30d' ? 30 : dateRange === '90d' ? 90 : dateRange === '1y' ? 365 : 365
  const reportData = useMemo(() => generateReportData(days), [days])

  const generateReport = async (format: 'pdf' | 'csv' | 'json') => {
    setIsGenerating(true)
    try {
      const response = await fetch(`/api/reports/generate?format=${format}&range=${dateRange}`, {
        method: 'POST',
      })
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `trading_report_${dateRange}.${format}`
        a.click()
      }
    } catch (error) {
      console.error('Failed to generate report:', error)
    } finally {
      setIsGenerating(false)
    }
  }

  const pieColors = ['#00c853', '#ff5252', '#00d4aa', '#ffc107', '#2196f3', '#9c27b0']

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <ClipboardList className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">PERFORMANCE REPORTS</h1>
            <p className="text-xs text-foreground-muted">Generate and export trading reports</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => generateReport('pdf')}
            className="btn-primary flex items-center gap-2"
            disabled={isGenerating}
          >
            <Download className={cn('w-4 h-4', isGenerating && 'animate-bounce')} />
            Export PDF
          </button>
          <button
            onClick={() => generateReport('csv')}
            className="btn-secondary flex items-center gap-2"
          >
            <FileText className="w-4 h-4" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Date Range Filter */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1 bg-surface-secondary rounded-lg p-1">
          {(['7d', '30d', '90d', '1y', 'all'] as const).map(range => (
            <button
              key={range}
              onClick={() => setDateRange(range)}
              className={cn(
                'px-4 py-1.5 text-xs font-medium rounded-md transition-colors',
                dateRange === range ? 'bg-accent-primary text-background-primary' : 'text-foreground-muted hover:text-foreground-primary'
              )}
            >
              {range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : range === '90d' ? '90 Days' : range === '1y' ? '1 Year' : 'All Time'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs text-foreground-muted">
          <Calendar className="w-4 h-4" />
          <span>Report Period: {days} days</span>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-5 gap-3">
        <SummaryCard
          label="Total P&L"
          value={`$${reportData.summary.totalPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
          positive={reportData.summary.totalPnl >= 0}
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <SummaryCard
          label="Win Rate"
          value={`${reportData.summary.winRate.toFixed(1)}%`}
          icon={<CheckCircle className="w-4 h-4" />}
        />
        <SummaryCard
          label="Profit Factor"
          value={reportData.summary.profitFactor.toFixed(2)}
          icon={<BarChart3 className="w-4 h-4" />}
        />
        <SummaryCard
          label="Sharpe Ratio"
          value={reportData.summary.sharpeRatio.toFixed(2)}
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <SummaryCard
          label="Max Drawdown"
          value={`-${reportData.summary.maxDrawdown.toFixed(1)}%`}
          negative
          icon={<TrendingDown className="w-4 h-4" />}
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-2 gap-4">
        {/* Equity Curve */}
        <div className="card p-4">
          <h3 className="text-sm font-medium text-foreground-primary mb-3">Equity Curve</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={reportData.equityCurve}>
                <defs>
                  <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00d4aa" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#00d4aa" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                  labelStyle={{ color: '#9ca3af' }}
                  formatter={(value: number) => [`$${value.toLocaleString()}`, 'Equity']}
                />
                <Area type="monotone" dataKey="equity" stroke="#00d4aa" fill="url(#equityGradient)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Drawdown */}
        <div className="card p-4">
          <h3 className="text-sm font-medium text-foreground-primary mb-3">Drawdown</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={reportData.drawdownHistory}>
                <defs>
                  <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ff5252" stopOpacity={0} />
                    <stop offset="100%" stopColor="#ff5252" stopOpacity={0.3} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                  labelStyle={{ color: '#9ca3af' }}
                  formatter={(value: number) => [`${value.toFixed(2)}%`, 'Drawdown']}
                />
                <Area type="monotone" dataKey="drawdown" stroke="#ff5252" fill="url(#drawdownGradient)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-3 gap-4">
        {/* Monthly Returns */}
        <div className="card p-4">
          <h3 className="text-sm font-medium text-foreground-primary mb-3">Monthly Returns</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={reportData.monthlyReturns}>
                <XAxis dataKey="month" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                  labelStyle={{ color: '#9ca3af' }}
                  formatter={(value: number) => [`${value.toFixed(1)}%`, 'Return']}
                />
                <Bar dataKey="return" radius={[4, 4, 0, 0]}>
                  {reportData.monthlyReturns.map((entry, index) => (
                    <Cell key={index} fill={entry.return >= 0 ? '#00c853' : '#ff5252'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* P&L by Symbol */}
        <div className="card p-4">
          <h3 className="text-sm font-medium text-foreground-primary mb-3">P&L by Symbol</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={reportData.tradesBySymbol.filter(s => s.pnl > 0)}
                  innerRadius={40}
                  outerRadius={60}
                  paddingAngle={2}
                  dataKey="pnl"
                  nameKey="symbol"
                >
                  {reportData.tradesBySymbol.filter(s => s.pnl > 0).map((_, index) => (
                    <Cell key={index} fill={pieColors[index % pieColors.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                  formatter={(value: number) => [`$${value.toLocaleString()}`, 'P&L']}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-2 justify-center mt-2">
            {reportData.tradesBySymbol.slice(0, 4).map((item, i) => (
              <span key={item.symbol} className="text-xs flex items-center gap-1">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: pieColors[i] }} />
                {item.symbol}
              </span>
            ))}
          </div>
        </div>

        {/* Strategy Performance */}
        <div className="card p-4">
          <h3 className="text-sm font-medium text-foreground-primary mb-3">Strategy Performance</h3>
          <div className="space-y-3">
            {reportData.tradesByStrategy.map((strategy, i) => (
              <div key={strategy.strategy} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: pieColors[i] }} />
                  <span className="text-sm text-foreground-primary">{strategy.strategy}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className={cn('text-sm font-mono', strategy.pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                    ${strategy.pnl.toLocaleString()}
                  </span>
                  <span className="text-xs text-foreground-muted">{strategy.winRate}% WR</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Detailed Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="card p-4">
          <h3 className="text-sm font-medium text-foreground-primary mb-4">Trade Statistics</h3>
          <div className="grid grid-cols-2 gap-4">
            <StatRow label="Total Trades" value={reportData.summary.totalTrades.toString()} />
            <StatRow label="Win Rate" value={`${reportData.summary.winRate.toFixed(1)}%`} />
            <StatRow label="Avg Win" value={`$${reportData.summary.avgWin.toFixed(0)}`} positive />
            <StatRow label="Avg Loss" value={`$${reportData.summary.avgLoss.toFixed(0)}`} negative />
            <StatRow label="Best Trade" value={`$${reportData.summary.bestTrade.toFixed(0)}`} positive />
            <StatRow label="Worst Trade" value={`$${reportData.summary.worstTrade.toFixed(0)}`} negative />
          </div>
        </div>

        <div className="card p-4">
          <h3 className="text-sm font-medium text-foreground-primary mb-4">Risk Metrics</h3>
          <div className="grid grid-cols-2 gap-4">
            <StatRow label="Sharpe Ratio" value={reportData.summary.sharpeRatio.toFixed(2)} />
            <StatRow label="Profit Factor" value={reportData.summary.profitFactor.toFixed(2)} />
            <StatRow label="Max Drawdown" value={`-${reportData.summary.maxDrawdown.toFixed(1)}%`} negative />
            <StatRow label="Recovery Factor" value={(reportData.summary.totalPnl / 100000 / (reportData.summary.maxDrawdown / 100)).toFixed(2)} />
            <StatRow label="Expectancy" value={`$${((reportData.summary.winRate / 100 * reportData.summary.avgWin) + ((100 - reportData.summary.winRate) / 100 * reportData.summary.avgLoss)).toFixed(0)}`} />
            <StatRow label="Risk/Reward" value={(Math.abs(reportData.summary.avgWin / reportData.summary.avgLoss)).toFixed(2)} />
          </div>
        </div>
      </div>

      {/* Export Actions */}
      <div className="card p-4">
        <h3 className="text-sm font-medium text-foreground-primary mb-4">Export Options</h3>
        <div className="flex items-center gap-3">
          <button
            onClick={() => generateReport('pdf')}
            className="flex-1 py-3 rounded-lg bg-surface-secondary hover:bg-surface-secondary/80 transition-colors flex items-center justify-center gap-2 text-foreground-primary"
          >
            <FileText className="w-4 h-4" />
            PDF Report
          </button>
          <button
            onClick={() => generateReport('csv')}
            className="flex-1 py-3 rounded-lg bg-surface-secondary hover:bg-surface-secondary/80 transition-colors flex items-center justify-center gap-2 text-foreground-primary"
          >
            <Download className="w-4 h-4" />
            CSV Data
          </button>
          <button
            onClick={() => generateReport('json')}
            className="flex-1 py-3 rounded-lg bg-surface-secondary hover:bg-surface-secondary/80 transition-colors flex items-center justify-center gap-2 text-foreground-primary"
          >
            <FileText className="w-4 h-4" />
            JSON Export
          </button>
          <button
            onClick={() => window.print()}
            className="flex-1 py-3 rounded-lg bg-surface-secondary hover:bg-surface-secondary/80 transition-colors flex items-center justify-center gap-2 text-foreground-primary"
          >
            <Printer className="w-4 h-4" />
            Print Report
          </button>
        </div>
      </div>
    </div>
  )
}

function SummaryCard({
  label,
  value,
  icon,
  positive,
  negative
}: {
  label: string
  value: string
  icon: React.ReactNode
  positive?: boolean
  negative?: boolean
}) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 text-foreground-muted mb-2">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className={cn(
        'text-xl font-bold',
        positive && 'text-bullish',
        negative && 'text-bearish',
        !positive && !negative && 'text-foreground-primary'
      )}>
        {value}
      </div>
    </div>
  )
}

function StatRow({
  label,
  value,
  positive,
  negative
}: {
  label: string
  value: string
  positive?: boolean
  negative?: boolean
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">
      <span className="text-sm text-foreground-muted">{label}</span>
      <span className={cn(
        'text-sm font-bold font-mono',
        positive && 'text-bullish',
        negative && 'text-bearish',
        !positive && !negative && 'text-foreground-primary'
      )}>
        {value}
      </span>
    </div>
  )
}
