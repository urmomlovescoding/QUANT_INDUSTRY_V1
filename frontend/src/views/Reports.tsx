import { useState, useEffect } from 'react'
import {
  ClipboardList,
  Download,
  FileText,
  Calendar,
  TrendingUp,
  TrendingDown,
  BarChart3,
  RefreshCw,
  CheckCircle,
  AlertCircle,
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

interface ReportSummary {
  totalPnl: number
  totalTrades: number
  winRate: number
  profitFactor: number
  sharpeRatio: number
  maxDrawdown: number
  avgWin: number
  avgLoss: number
}

interface ReportData {
  period: string
  summary: ReportSummary
  generatedAt: string
}

type DateRange = '7d' | '30d' | '90d' | '1y' | 'all'

export function Reports() {
  const [dateRange, setDateRange] = useState<DateRange>('30d')
  const [reportData, setReportData] = useState<ReportData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchReport = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/reports/summary?range=${dateRange}`)
      const data = await response.json()

      if (response.ok) {
        setReportData(data)
      } else {
        setError(data.detail || 'Failed to fetch report')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch report')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchReport()
  }, [dateRange])

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

  const days = dateRange === '7d' ? 7 : dateRange === '30d' ? 30 : dateRange === '90d' ? 90 : dateRange === '1y' ? 365 : 365

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
            onClick={fetchReport}
            disabled={isLoading}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            Refresh
          </button>
          <button
            onClick={() => generateReport('pdf')}
            className="btn-primary flex items-center gap-2"
            disabled={isGenerating || !reportData || reportData.summary.totalTrades === 0}
          >
            <Download className={cn('w-4 h-4', isGenerating && 'animate-bounce')} />
            Export PDF
          </button>
          <button
            onClick={() => generateReport('csv')}
            className="btn-secondary flex items-center gap-2"
            disabled={!reportData || reportData.summary.totalTrades === 0}
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

      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-accent-primary" />
        </div>
      ) : !reportData || reportData.summary.totalTrades === 0 ? (
        <div className="card p-8 text-center text-foreground-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">No Trading Data Available</p>
          <p className="text-sm mt-2">Reports will be generated once you have trading history</p>
          {reportData && (
            <p className="text-xs mt-4 text-foreground-muted">
              Generated at: {new Date(reportData.generatedAt).toLocaleString()}
            </p>
          )}
        </div>
      ) : (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-5 gap-3">
            <SummaryCard
              label="Total P&L"
              value={`$${reportData.summary.totalPnl.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}
              positive={reportData.summary.totalPnl >= 0}
              icon={<TrendingUp className="w-4 h-4" />}
            />
            <SummaryCard
              label="Win Rate"
              value={reportData.summary.winRate > 0 ? `${reportData.summary.winRate.toFixed(1)}%` : 'N/A'}
              icon={<CheckCircle className="w-4 h-4" />}
            />
            <SummaryCard
              label="Profit Factor"
              value={reportData.summary.profitFactor > 0 ? reportData.summary.profitFactor.toFixed(2) : 'N/A'}
              icon={<BarChart3 className="w-4 h-4" />}
            />
            <SummaryCard
              label="Sharpe Ratio"
              value={reportData.summary.sharpeRatio !== 0 ? reportData.summary.sharpeRatio.toFixed(2) : 'N/A'}
              icon={<TrendingUp className="w-4 h-4" />}
            />
            <SummaryCard
              label="Max Drawdown"
              value={reportData.summary.maxDrawdown !== 0 ? `${reportData.summary.maxDrawdown.toFixed(1)}%` : 'N/A'}
              negative={reportData.summary.maxDrawdown < 0}
              icon={<TrendingDown className="w-4 h-4" />}
            />
          </div>

          {/* Trade Stats */}
          <div className="grid grid-cols-4 gap-4">
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Total Trades</div>
              <div className="text-2xl font-bold font-mono">{reportData.summary.totalTrades}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Average Win</div>
              <div className="text-2xl font-bold font-mono text-bullish">
                {reportData.summary.avgWin > 0 ? `$${reportData.summary.avgWin.toFixed(2)}` : 'N/A'}
              </div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Average Loss</div>
              <div className="text-2xl font-bold font-mono text-bearish">
                {reportData.summary.avgLoss !== 0 ? `$${reportData.summary.avgLoss.toFixed(2)}` : 'N/A'}
              </div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-foreground-muted mb-1">Report Generated</div>
              <div className="text-sm font-mono">{new Date(reportData.generatedAt).toLocaleString()}</div>
            </div>
          </div>

          {/* Info Card */}
          <div className="card p-4 bg-accent-primary/5 border border-accent-primary/20">
            <div className="flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-accent-primary mt-0.5" />
              <div>
                <p className="text-sm font-medium text-foreground-primary">Report Data Source</p>
                <p className="text-xs text-foreground-muted mt-1">
                  This report is generated from your actual trading history. All metrics are calculated from real executed trades.
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

interface SummaryCardProps {
  label: string
  value: string
  positive?: boolean
  negative?: boolean
  icon: React.ReactNode
}

function SummaryCard({ label, value, positive, negative, icon }: SummaryCardProps) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-foreground-muted">{label}</span>
        <span className={cn(
          positive && 'text-bullish',
          negative && 'text-bearish',
          !positive && !negative && 'text-foreground-muted'
        )}>
          {icon}
        </span>
      </div>
      <div className={cn(
        'text-xl font-bold font-mono',
        positive && 'text-bullish',
        negative && 'text-bearish'
      )}>
        {value}
      </div>
    </div>
  )
}
