import { TrendingUp, TrendingDown, Star, Plus } from 'lucide-react'
import { cn } from '@/utils/cn'

const watchlistItems = [
  { symbol: 'AAPL', price: 185.92, change: 2.34, changePercent: 1.28 },
  { symbol: 'MSFT', price: 415.67, change: -1.23, changePercent: -0.29 },
  { symbol: 'GOOGL', price: 175.45, change: 3.87, changePercent: 2.25 },
  { symbol: 'TSLA', price: 248.32, change: -5.67, changePercent: -2.23 },
  { symbol: 'NVDA', price: 878.45, change: 12.34, changePercent: 1.42 },
  { symbol: 'META', price: 505.23, change: 4.56, changePercent: 0.91 },
]

export function RightPanel() {
  return (
    <aside className="w-64 bg-background-secondary border-l border-border flex flex-col overflow-hidden">
      {/* Quick Stats */}
      <div className="p-4 border-b border-border">
        <h3 className="text-xs font-medium text-foreground-muted uppercase tracking-wider mb-3">
          Portfolio
        </h3>
        <div className="space-y-3">
          <QuickStat label="Total Value" value="$125,432.67" />
          <QuickStat label="Today's P&L" value="+$2,345.89" positive />
          <QuickStat label="Open Positions" value="8" />
          <QuickStat label="Win Rate" value="68.5%" />
        </div>
      </div>

      {/* Risk Meters */}
      <div className="p-4 border-b border-border">
        <h3 className="text-xs font-medium text-foreground-muted uppercase tracking-wider mb-3">
          Risk Metrics
        </h3>
        <div className="space-y-3">
          <RiskMeter label="Portfolio Risk" value={35} />
          <RiskMeter label="Daily Drawdown" value={12} />
          <RiskMeter label="Exposure" value={65} />
        </div>
      </div>

      {/* Watchlist */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="p-4 pb-2 flex items-center justify-between">
          <h3 className="text-xs font-medium text-foreground-muted uppercase tracking-wider">
            Watchlist
          </h3>
          <button className="p-1 rounded hover:bg-background-hover transition-colors">
            <Plus className="w-4 h-4 text-foreground-muted" />
          </button>
        </div>

        <div className="flex-1 overflow-auto">
          {watchlistItems.map((item) => (
            <WatchlistItem key={item.symbol} {...item} />
          ))}
        </div>
      </div>
    </aside>
  )
}

interface QuickStatProps {
  label: string
  value: string
  positive?: boolean
  negative?: boolean
}

function QuickStat({ label, value, positive, negative }: QuickStatProps) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-xs text-foreground-muted">{label}</span>
      <span
        className={cn(
          'text-sm font-medium tabular-nums',
          positive && 'text-bullish',
          negative && 'text-bearish',
          !positive && !negative && 'text-foreground-primary'
        )}
      >
        {value}
      </span>
    </div>
  )
}

interface RiskMeterProps {
  label: string
  value: number
}

function RiskMeter({ label, value }: RiskMeterProps) {
  const getColor = (v: number) => {
    if (v < 30) return 'bg-bullish'
    if (v < 60) return 'bg-warning'
    return 'bg-bearish'
  }

  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-xs text-foreground-muted">{label}</span>
        <span className="text-xs font-medium text-foreground-primary tabular-nums">
          {value}%
        </span>
      </div>
      <div className="h-1.5 bg-background-tertiary rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', getColor(value))}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  )
}

interface WatchlistItemProps {
  symbol: string
  price: number
  change: number
  changePercent: number
}

function WatchlistItem({ symbol, price, change, changePercent }: WatchlistItemProps) {
  const isPositive = change >= 0

  return (
    <div className="group px-4 py-2 hover:bg-background-hover transition-colors cursor-pointer flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Star className="w-3.5 h-3.5 text-accent-primary opacity-0 group-hover:opacity-100 transition-opacity" />
        <span className="text-sm font-medium text-foreground-primary">{symbol}</span>
      </div>

      <div className="text-right">
        <div className="text-sm font-mono text-foreground-primary">
          ${price.toFixed(2)}
        </div>
        <div
          className={cn(
            'text-xs font-medium tabular-nums flex items-center gap-1 justify-end',
            isPositive ? 'text-bullish' : 'text-bearish'
          )}
        >
          {isPositive ? (
            <TrendingUp className="w-3 h-3" />
          ) : (
            <TrendingDown className="w-3 h-3" />
          )}
          {isPositive ? '+' : ''}{changePercent.toFixed(2)}%
        </div>
      </div>
    </div>
  )
}
