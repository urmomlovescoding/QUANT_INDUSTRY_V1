import { Signal, Filter, RefreshCw, Play } from 'lucide-react'
import { SignalsTable } from '@/components/tables/SignalsTable'

export function Signals() {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Signal className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground-primary">Signal Analysis</h1>
            <p className="text-sm text-foreground-muted">12 active signals • 8 long • 4 short</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary flex items-center gap-2">
            <Filter className="w-4 h-4" />
            Filter
          </button>
          <button className="btn-secondary flex items-center gap-2">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button className="btn-primary flex items-center gap-2">
            <Play className="w-4 h-4" />
            Execute All
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        <SummaryCard label="Total Signals" value="12" />
        <SummaryCard label="High Confidence" value="5" subLabel=">80%" />
        <SummaryCard label="Avg Expected Return" value="+4.8%" positive />
        <SummaryCard label="Avg Confidence" value="76%" />
      </div>

      {/* Main table */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-medium text-foreground-primary">All Signals</h2>
          <div className="flex items-center gap-2">
            <select className="text-xs bg-background-tertiary text-foreground-secondary px-3 py-1.5 rounded border border-border">
              <option>All Directions</option>
              <option>Long Only</option>
              <option>Short Only</option>
            </select>
            <select className="text-xs bg-background-tertiary text-foreground-secondary px-3 py-1.5 rounded border border-border">
              <option>All Regimes</option>
              <option>Trending</option>
              <option>Mean Rev</option>
              <option>Breakout</option>
            </select>
          </div>
        </div>
        <SignalsTable />
      </div>
    </div>
  )
}

interface SummaryCardProps {
  label: string
  value: string
  subLabel?: string
  positive?: boolean
}

function SummaryCard({ label, value, subLabel, positive }: SummaryCardProps) {
  return (
    <div className="card p-4">
      <p className="text-xs text-foreground-muted uppercase tracking-wider">{label}</p>
      <div className="flex items-baseline gap-2 mt-1">
        <p className={`text-2xl font-bold ${positive ? 'text-bullish' : 'text-foreground-primary'}`}>
          {value}
        </p>
        {subLabel && (
          <span className="text-xs text-foreground-muted">{subLabel}</span>
        )}
      </div>
    </div>
  )
}
