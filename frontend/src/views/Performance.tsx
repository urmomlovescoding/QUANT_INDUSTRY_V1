import { BarChart3 } from 'lucide-react'
import { cn } from '@/utils/cn'
import { AreaChart } from '@/components/charts/AreaChart'
import { BarChart } from '@/components/charts/BarChart'
import { DonutChart } from '@/components/charts/DonutChart'

export function Performance() {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <BarChart3 className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground-primary">Performance Center</h1>
            <p className="text-sm text-foreground-muted">Current Trading Session Data</p>
          </div>
        </div>
        <select className="text-sm bg-background-tertiary text-foreground-secondary px-3 py-1.5 rounded border border-border">
          <option>Today</option>
          <option>This Week</option>
          <option>This Month</option>
          <option>All Time</option>
        </select>
      </div>

      {/* Stats grid - matches second reference image */}
      <div className="grid grid-cols-4 gap-4">
        {/* All Trades */}
        <StatsCard title="ALL TRADES">
          <StatRow label="Net P&L" value="$475.00" positive />
          <StatRow label="# of Trades" value="33" />
          <StatRow label="# of Contracts" value="104" />
          <StatRow label="Avg. Trade Time" value="6min 29sec" />
          <StatRow label="Longest Trade" value="18min 33sec" />
          <StatRow label="% Profitable Trades" value="87.88%" />
          <StatRow label="Trade Fees & Comm" value="($91.52)" negative />
          <StatRow label="Total P&L" value="$383.48" positive />
        </StatsCard>

        {/* Profit Trades */}
        <StatsCard title="PROFIT TRADES" highlight="bullish">
          <StatRow label="Total Profit" value="$530.00" positive />
          <StatRow label="# of Winning Trades" value="29" />
          <StatRow label="# of Winning Contracts" value="42" />
          <StatRow label="Largest Winning Trade" value="$55.00" />
          <StatRow label="Avg. Winning Trade" value="$18.28" />
          <StatRow label="Std. Dev. Winning Trade" value="$12.40" />
          <StatRow label="Avg. Winning Trade Time" value="5min 40sec" />
          <StatRow label="Longest Winning Trade" value="11min 43sec" />
          <StatRow label="Max Run-up" value="$477.20" />
        </StatsCard>

        {/* Losing Trades */}
        <StatsCard title="LOSING TRADES" highlight="bearish">
          <StatRow label="Total Loss" value="($55.00)" negative />
          <StatRow label="# of Losing Trades" value="4" />
          <StatRow label="# of Losing Contracts" value="10" />
          <StatRow label="Largest Losing Trade" value="($13.75)" />
          <StatRow label="Avg. Losing Trade" value="$71.18" />
          <StatRow label="Std. Dev. Losing Trade" value="$7.71" />
          <StatRow label="Avg. Losing Trade Time" value="12min 25sec" />
          <StatRow label="Longest Losing Trade" value="18min 33sec" />
          <StatRow label="Max Drawdown" value="($93.54)" />
        </StatsCard>

        {/* Win vs Loss Chart */}
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">
            WINNING VS LOSING TRADES
          </h3>
          <div className="flex items-center justify-center h-40">
            <DonutChart
              data={[
                { name: 'Winning', value: 87.88, color: '#00c853' },
                { name: 'Losing', value: 12.12, color: '#ff1744' },
              ]}
              centerLabel="87.9%"
              centerSubLabel="Win Rate"
              size={140}
            />
          </div>
          <div className="flex justify-around mt-4 text-xs">
            <div className="text-center">
              <div className="flex items-center gap-1 justify-center">
                <span className="w-2 h-2 rounded-full bg-bullish" />
                <span className="text-foreground-muted">WINNING</span>
              </div>
              <span className="font-bold text-bullish">87.88%</span>
            </div>
            <div className="text-center">
              <div className="flex items-center gap-1 justify-center">
                <span className="w-2 h-2 rounded-full bg-bearish" />
                <span className="text-foreground-muted">LOSING</span>
              </div>
              <span className="font-bold text-bearish">12.12%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">
            P&L HISTORY
          </h3>
          <BarChart />
        </div>
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">
            P&L HISTORY (CUMULATIVE WITHOUT FEES)
          </h3>
          <AreaChart />
        </div>
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">
            P&L HISTORY (CUMULATIVE WITH FEES)
          </h3>
          <AreaChart />
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">
            P&L DISTRIBUTION
          </h3>
          <BarChart />
        </div>
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">
            P/L PER TIME OF DAY
          </h3>
          <BarChart />
        </div>
        <div className="card p-4">
          <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">
            GROSS LOSS BREAKDOWN
          </h3>
          <div className="flex items-center justify-center h-40">
            <DonutChart
              data={[
                { name: 'Commission', value: 56.67, color: '#2196f3' },
                { name: 'Trade', value: 37.34, color: '#ff9800' },
                { name: 'Clearing', value: 5.99, color: '#9c27b0' },
              ]}
              centerLabel="$91.52"
              centerSubLabel="Total Fees"
              size={140}
            />
          </div>
        </div>
      </div>

      {/* Trades table */}
      <div className="card">
        <div className="p-4 border-b border-border">
          <h2 className="text-sm font-medium text-foreground-primary">TRADES</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table text-xs">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Account</th>
                <th>Qty</th>
                <th>Buy Price</th>
                <th>Buy Time</th>
                <th>Duration</th>
                <th>Sell Time</th>
                <th>Sell Price</th>
                <th>P&L</th>
              </tr>
            </thead>
            <tbody>
              <TradeRow symbol="MESZ9" account="DEMO07914" qty={2} buyPrice={3082.50} buyTime="11/08/2019 8:39:28 AM" duration="8sec" sellTime="11/08/2019 8:39:20 AM" sellPrice={3082.00} pnl={-5.00} />
              <TradeRow symbol="MESZ9" account="DEMO07914" qty={2} buyPrice={3083.25} buyTime="11/08/2019 8:58:54 AM" duration="18min 33sec" sellTime="11/08/2019 8:40:20 AM" sellPrice={3082.00} pnl={12.50} />
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

interface StatsCardProps {
  title: string
  children: React.ReactNode
  highlight?: 'bullish' | 'bearish'
}

function StatsCard({ title, children, highlight }: StatsCardProps) {
  return (
    <div className={cn(
      'card p-4',
      highlight === 'bullish' && 'border-bullish/30',
      highlight === 'bearish' && 'border-bearish/30'
    )}>
      <h3 className={cn(
        'text-xs font-bold uppercase tracking-wider mb-4',
        highlight === 'bullish' ? 'text-bullish' : highlight === 'bearish' ? 'text-bearish' : 'text-foreground-muted'
      )}>
        {title}
      </h3>
      <div className="space-y-2">
        {children}
      </div>
    </div>
  )
}

interface StatRowProps {
  label: string
  value: string
  positive?: boolean
  negative?: boolean
}

function StatRow({ label, value, positive, negative }: StatRowProps) {
  return (
    <div className="flex justify-between items-center text-xs">
      <span className="text-foreground-muted">{label}</span>
      <span className={cn(
        'font-mono font-medium',
        positive && 'text-bullish',
        negative && 'text-bearish',
        !positive && !negative && 'text-foreground-primary'
      )}>
        {value}
      </span>
    </div>
  )
}

interface TradeRowProps {
  symbol: string
  account: string
  qty: number
  buyPrice: number
  buyTime: string
  duration: string
  sellTime: string
  sellPrice: number
  pnl: number
}

function TradeRow({ symbol, account, qty, buyPrice, buyTime, duration, sellTime, sellPrice, pnl }: TradeRowProps) {
  return (
    <tr>
      <td className="font-medium">{symbol}</td>
      <td>{account}</td>
      <td>{qty}</td>
      <td className="font-mono">{buyPrice.toFixed(2)}</td>
      <td className="text-foreground-muted">{buyTime}</td>
      <td>{duration}</td>
      <td className="text-foreground-muted">{sellTime}</td>
      <td className="font-mono">{sellPrice.toFixed(2)}</td>
      <td className={cn('font-mono font-medium', pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
        ${pnl.toFixed(2)}
      </td>
    </tr>
  )
}
