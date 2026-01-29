/**
 * Tax Lot Management View
 * ========================
 * Institutional-grade tax lot tracking with wash sale detection,
 * tax-loss harvesting, and Form 8949 export.
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Receipt,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Download,
  RefreshCw,
  ChevronRight,
  DollarSign,
  Calendar,
  Target,
  Percent,
  FileText,
  Leaf,
  Scale,
  PieChart,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { formatCurrency, formatPercent, formatDate } from '@/utils/format'

interface TaxLot {
  lot_id: string
  symbol: string
  quantity: string
  cost_per_share: string
  acquisition_date: string
  acquisition_type: string
  total_cost_basis: string
  adjusted_cost_per_share: string
  wash_sale_adjustment: string
  market_value?: string
  unrealized_gain?: string
  unrealized_pct?: string
}

interface Position {
  symbol: string
  total_quantity: string
  total_cost_basis: string
  average_cost: string
  lots: TaxLot[]
  lot_count: number
  market_value?: string
  unrealized_gain?: string
}

interface HarvestingOpportunity {
  symbol: string
  lot_id: string
  unrealized_loss: string
  current_price: string
  cost_basis: string
  quantity: string
  gain_type: string
  days_held: number
  wash_sale_risk: boolean
  estimated_tax_savings: string
}

interface RealizedGains {
  short_term_gains: number
  long_term_gains: number
  total_realized: number
  wash_sale_adjustments: number
  estimated_tax: number
  transactions: number
}

const API_BASE = 'http://localhost:8000'

export function TaxLots() {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'positions' | 'harvesting' | 'realized' | 'form8949'>('positions')
  const queryClient = useQueryClient()

  // Fetch positions
  const { data: positions, isLoading: loadingPositions } = useQuery({
    queryKey: ['tax-positions'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/tax/positions`)
      const data = await res.json()
      return data.positions as Position[]
    },
    refetchInterval: 30000,
  })

  // Fetch realized gains
  const { data: realizedGains } = useQuery({
    queryKey: ['tax-realized', new Date().getFullYear()],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/tax/realized-gains?year=${new Date().getFullYear()}`)
      return res.json() as Promise<RealizedGains>
    },
  })

  // Fetch harvesting opportunities
  const { data: harvestingOpps } = useQuery({
    queryKey: ['tax-harvesting'],
    queryFn: async () => {
      // Mock prices for demo
      const prices = { AAPL: 240, MSFT: 440, NVDA: 140, TSLA: 420 }
      const res = await fetch(`${API_BASE}/tax/tax-loss-harvesting`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prices, min_loss: 100 }),
      })
      const data = await res.json()
      return data.opportunities as HarvestingOpportunity[]
    },
  })

  // Calculate totals
  const totalCostBasis = positions?.reduce((sum, p) => sum + parseFloat(p.total_cost_basis || '0'), 0) || 0
  const totalMarketValue = positions?.reduce((sum, p) => sum + parseFloat(p.market_value || p.total_cost_basis || '0'), 0) || 0
  const totalUnrealized = totalMarketValue - totalCostBasis
  const totalLots = positions?.reduce((sum, p) => sum + p.lot_count, 0) || 0

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground-primary flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-xl">
              <Receipt className="w-6 h-6 text-emerald-400" />
            </div>
            Tax Lot Management
          </h1>
          <p className="text-foreground-muted mt-1">Track cost basis, wash sales, and optimize tax efficiency</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn-secondary flex items-center gap-2">
            <Download className="w-4 h-4" />
            Export 8949
          </button>
          <button 
            onClick={() => queryClient.invalidateQueries({ queryKey: ['tax-positions'] })}
            className="btn-primary flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <SummaryCard
          title="Total Cost Basis"
          value={formatCurrency(totalCostBasis)}
          icon={DollarSign}
          color="blue"
        />
        <SummaryCard
          title="Market Value"
          value={formatCurrency(totalMarketValue)}
          icon={TrendingUp}
          color="green"
          change={totalUnrealized}
          changePercent={(totalUnrealized / totalCostBasis) * 100}
        />
        <SummaryCard
          title="YTD Realized"
          value={formatCurrency(realizedGains?.total_realized || 0)}
          icon={Target}
          color={(realizedGains?.total_realized ?? 0) >= 0 ? 'green' : 'red'}
        />
        <SummaryCard
          title="Tax Lots"
          value={totalLots.toString()}
          subtitle={`${positions?.length || 0} positions`}
          icon={PieChart}
          color="purple"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-background-secondary rounded-xl w-fit">
        {[
          { id: 'positions', label: 'Open Positions', icon: PieChart },
          { id: 'harvesting', label: 'Tax-Loss Harvesting', icon: Leaf },
          { id: 'realized', label: 'Realized Gains', icon: Scale },
          { id: 'form8949', label: 'Form 8949', icon: FileText },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
              activeTab === tab.id
                ? 'bg-accent-primary text-white shadow-lg'
                : 'text-foreground-muted hover:text-foreground-primary hover:bg-background-tertiary'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === 'positions' && (
        <PositionsTable positions={positions || []} loading={loadingPositions} />
      )}

      {activeTab === 'harvesting' && (
        <HarvestingTable opportunities={harvestingOpps || []} />
      )}

      {activeTab === 'realized' && (
        <RealizedGainsPanel gains={realizedGains} />
      )}

      {activeTab === 'form8949' && (
        <Form8949Panel />
      )}
    </div>
  )
}

function SummaryCard({ 
  title, 
  value, 
  subtitle,
  icon: Icon, 
  color,
  change,
  changePercent 
}: {
  title: string
  value: string
  subtitle?: string
  icon: any
  color: 'blue' | 'green' | 'red' | 'purple'
  change?: number
  changePercent?: number
}) {
  const colors = {
    blue: 'from-blue-500/20 to-cyan-500/20 text-blue-400',
    green: 'from-emerald-500/20 to-green-500/20 text-emerald-400',
    red: 'from-red-500/20 to-rose-500/20 text-red-400',
    purple: 'from-purple-500/20 to-violet-500/20 text-purple-400',
  }

  return (
    <div className="bg-background-elevated rounded-2xl p-5 border border-border hover:border-border-light transition-all group">
      <div className="flex items-start justify-between mb-3">
        <div className={cn('p-2.5 rounded-xl bg-gradient-to-br', colors[color])}>
          <Icon className="w-5 h-5" />
        </div>
        {change !== undefined && (
          <div className={cn(
            'flex items-center gap-1 text-sm font-medium',
            change >= 0 ? 'text-bullish' : 'text-bearish'
          )}>
            {change >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            {changePercent?.toFixed(2)}%
          </div>
        )}
      </div>
      <p className="text-foreground-muted text-xs font-medium uppercase tracking-wider mb-1">{title}</p>
      <p className="text-2xl font-bold text-foreground-primary">{value}</p>
      {subtitle && <p className="text-foreground-muted text-xs mt-1">{subtitle}</p>}
    </div>
  )
}

function PositionsTable({ positions, loading }: { positions: Position[], loading: boolean }) {
  if (loading) {
    return (
      <div className="bg-background-elevated rounded-2xl border border-border p-8">
        <div className="flex items-center justify-center">
          <RefreshCw className="w-6 h-6 text-accent-primary animate-spin" />
        </div>
      </div>
    )
  }

  if (positions.length === 0) {
    return (
      <div className="bg-background-elevated rounded-2xl border border-border p-12 text-center">
        <Receipt className="w-12 h-12 text-foreground-muted mx-auto mb-4" />
        <h3 className="text-lg font-medium text-foreground-primary mb-2">No Tax Lots</h3>
        <p className="text-foreground-muted">Record purchases to start tracking tax lots</p>
      </div>
    )
  }

  return (
    <div className="bg-background-elevated rounded-2xl border border-border overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border bg-background-tertiary/50">
            <th className="text-left py-4 px-5 text-xs font-semibold text-foreground-muted uppercase tracking-wider">Symbol</th>
            <th className="text-right py-4 px-5 text-xs font-semibold text-foreground-muted uppercase tracking-wider">Quantity</th>
            <th className="text-right py-4 px-5 text-xs font-semibold text-foreground-muted uppercase tracking-wider">Avg Cost</th>
            <th className="text-right py-4 px-5 text-xs font-semibold text-foreground-muted uppercase tracking-wider">Cost Basis</th>
            <th className="text-right py-4 px-5 text-xs font-semibold text-foreground-muted uppercase tracking-wider">Lots</th>
            <th className="text-right py-4 px-5 text-xs font-semibold text-foreground-muted uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {positions.map((position) => (
            <tr key={position.symbol} className="hover:bg-background-tertiary/30 transition-colors">
              <td className="py-4 px-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-primary/20 to-accent-secondary/20 flex items-center justify-center">
                    <span className="text-sm font-bold text-accent-primary">{position.symbol.slice(0, 2)}</span>
                  </div>
                  <span className="font-semibold text-foreground-primary">{position.symbol}</span>
                </div>
              </td>
              <td className="py-4 px-5 text-right font-mono text-foreground-primary">
                {parseFloat(position.total_quantity).toLocaleString()}
              </td>
              <td className="py-4 px-5 text-right font-mono text-foreground-primary">
                ${parseFloat(position.average_cost).toFixed(2)}
              </td>
              <td className="py-4 px-5 text-right font-mono text-foreground-primary">
                {formatCurrency(parseFloat(position.total_cost_basis))}
              </td>
              <td className="py-4 px-5 text-right">
                <span className="px-2.5 py-1 bg-background-tertiary rounded-full text-xs font-medium text-foreground-secondary">
                  {position.lot_count} lots
                </span>
              </td>
              <td className="py-4 px-5 text-right">
                <button className="p-2 hover:bg-background-tertiary rounded-lg transition-colors">
                  <ChevronRight className="w-4 h-4 text-foreground-muted" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function HarvestingTable({ opportunities }: { opportunities: HarvestingOpportunity[] }) {
  if (opportunities.length === 0) {
    return (
      <div className="bg-background-elevated rounded-2xl border border-border p-12 text-center">
        <Leaf className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-foreground-primary mb-2">No Harvesting Opportunities</h3>
        <p className="text-foreground-muted">All positions are currently profitable</p>
      </div>
    )
  }

  const totalSavings = opportunities.reduce((sum, o) => sum + parseFloat(o.estimated_tax_savings), 0)

  return (
    <div className="space-y-4">
      <div className="bg-gradient-to-r from-emerald-500/10 to-teal-500/10 rounded-2xl border border-emerald-500/20 p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Leaf className="w-6 h-6 text-emerald-400" />
            <div>
              <p className="text-foreground-primary font-medium">Potential Tax Savings</p>
              <p className="text-foreground-muted text-sm">{opportunities.length} opportunities found</p>
            </div>
          </div>
          <p className="text-2xl font-bold text-emerald-400">{formatCurrency(totalSavings)}</p>
        </div>
      </div>

      <div className="bg-background-elevated rounded-2xl border border-border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-background-tertiary/50">
              <th className="text-left py-4 px-5 text-xs font-semibold text-foreground-muted uppercase">Symbol</th>
              <th className="text-right py-4 px-5 text-xs font-semibold text-foreground-muted uppercase">Loss</th>
              <th className="text-right py-4 px-5 text-xs font-semibold text-foreground-muted uppercase">Tax Savings</th>
              <th className="text-right py-4 px-5 text-xs font-semibold text-foreground-muted uppercase">Type</th>
              <th className="text-center py-4 px-5 text-xs font-semibold text-foreground-muted uppercase">Wash Risk</th>
              <th className="text-right py-4 px-5 text-xs font-semibold text-foreground-muted uppercase">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {opportunities.map((opp) => (
              <tr key={opp.lot_id} className="hover:bg-background-tertiary/30">
                <td className="py-4 px-5 font-semibold text-foreground-primary">{opp.symbol}</td>
                <td className="py-4 px-5 text-right font-mono text-bearish">
                  {formatCurrency(parseFloat(opp.unrealized_loss))}
                </td>
                <td className="py-4 px-5 text-right font-mono text-emerald-400">
                  {formatCurrency(parseFloat(opp.estimated_tax_savings))}
                </td>
                <td className="py-4 px-5 text-right">
                  <span className={cn(
                    'px-2 py-1 rounded-full text-xs font-medium',
                    opp.gain_type === 'short_term' 
                      ? 'bg-amber-500/20 text-amber-400'
                      : 'bg-blue-500/20 text-blue-400'
                  )}>
                    {opp.gain_type === 'short_term' ? 'Short-Term' : 'Long-Term'}
                  </span>
                </td>
                <td className="py-4 px-5 text-center">
                  {opp.wash_sale_risk ? (
                    <AlertTriangle className="w-4 h-4 text-warning mx-auto" />
                  ) : (
                    <span className="text-bullish">✓</span>
                  )}
                </td>
                <td className="py-4 px-5 text-right">
                  <button className="px-3 py-1.5 bg-emerald-500/20 text-emerald-400 rounded-lg text-xs font-medium hover:bg-emerald-500/30 transition-colors">
                    Harvest
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RealizedGainsPanel({ gains }: { gains?: RealizedGains }) {
  return (
    <div className="grid grid-cols-2 gap-6">
      <div className="bg-background-elevated rounded-2xl border border-border p-6">
        <h3 className="text-lg font-semibold text-foreground-primary mb-6">YTD Summary</h3>
        <div className="space-y-4">
          <div className="flex justify-between items-center py-3 border-b border-border">
            <span className="text-foreground-muted">Short-Term Gains</span>
            <span className={cn('font-mono font-semibold', (gains?.short_term_gains || 0) >= 0 ? 'text-bullish' : 'text-bearish')}>
              {formatCurrency(gains?.short_term_gains || 0)}
            </span>
          </div>
          <div className="flex justify-between items-center py-3 border-b border-border">
            <span className="text-foreground-muted">Long-Term Gains</span>
            <span className={cn('font-mono font-semibold', (gains?.long_term_gains || 0) >= 0 ? 'text-bullish' : 'text-bearish')}>
              {formatCurrency(gains?.long_term_gains || 0)}
            </span>
          </div>
          <div className="flex justify-between items-center py-3 border-b border-border">
            <span className="text-foreground-muted">Wash Sale Adjustments</span>
            <span className="font-mono text-warning">
              {formatCurrency(gains?.wash_sale_adjustments || 0)}
            </span>
          </div>
          <div className="flex justify-between items-center py-3 bg-background-tertiary -mx-6 px-6 rounded-xl">
            <span className="font-semibold text-foreground-primary">Net Realized</span>
            <span className={cn('font-mono text-xl font-bold', (gains?.total_realized || 0) >= 0 ? 'text-bullish' : 'text-bearish')}>
              {formatCurrency(gains?.total_realized || 0)}
            </span>
          </div>
        </div>
      </div>

      <div className="bg-background-elevated rounded-2xl border border-border p-6">
        <h3 className="text-lg font-semibold text-foreground-primary mb-6">Estimated Tax</h3>
        <div className="text-center py-8">
          <p className="text-4xl font-bold text-foreground-primary mb-2">
            {formatCurrency(gains?.estimated_tax || 0)}
          </p>
          <p className="text-foreground-muted">Estimated tax liability</p>
        </div>
        <div className="flex justify-center gap-8 mt-6 pt-6 border-t border-border">
          <div className="text-center">
            <p className="text-2xl font-bold text-foreground-primary">{gains?.transactions || 0}</p>
            <p className="text-foreground-muted text-sm">Transactions</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function Form8949Panel() {
  const year = new Date().getFullYear()
  
  return (
    <div className="bg-background-elevated rounded-2xl border border-border p-8 text-center">
      <FileText className="w-16 h-16 text-accent-primary mx-auto mb-4" />
      <h3 className="text-xl font-semibold text-foreground-primary mb-2">IRS Form 8949</h3>
      <p className="text-foreground-muted mb-6 max-w-md mx-auto">
        Export your capital gains and losses for tax year {year} in IRS-compatible format
      </p>
      <div className="flex justify-center gap-4">
        <button className="btn-secondary flex items-center gap-2">
          <Download className="w-4 h-4" />
          Download CSV
        </button>
        <button className="btn-primary flex items-center gap-2">
          <FileText className="w-4 h-4" />
          Generate PDF
        </button>
      </div>
    </div>
  )
}

export default TaxLots
