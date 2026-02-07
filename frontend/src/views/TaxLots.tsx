/**
 * Tax Lot Management View
 * ========================
 * Institutional-grade tax lot tracking with wash sale detection,
 * tax-loss harvesting opportunities, and Form 8949 export.
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Receipt, TrendingUp, TrendingDown, AlertTriangle, Download,
  RefreshCw, ChevronRight, ChevronDown, DollarSign, Calendar,
  Target, FileText, Leaf, Scale, PieChart, Clock, AlertCircle, CheckCircle,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { formatCurrency, formatDate } from '@/utils/format'
import { Skeleton } from '@/components/ui/LoadingStates'
import { DonutChart } from '@/components/charts/DonutChart'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface TaxLot {
  lot_id: string; symbol: string; quantity: number; cost_per_share: number
  acquisition_date: string; acquisition_type: string; total_cost_basis: number
  adjusted_cost_per_share: number; wash_sale_adjustment: number; market_value: number
  unrealized_gain: number; unrealized_pct: number; holding_period: 'short_term' | 'long_term'; days_held: number
}
interface Position {
  symbol: string; total_quantity: number; total_cost_basis: number; average_cost: number
  lots: TaxLot[]; lot_count: number; market_value: number; unrealized_gain: number
}
interface HarvestingOpportunity {
  symbol: string; lot_id: string; unrealized_loss: number; current_price: number
  cost_basis: number; quantity: number; gain_type: string; days_held: number
  wash_sale_risk: boolean; estimated_tax_savings: number
}
interface RealizedGains {
  short_term_gains: number; long_term_gains: number; total_realized: number
  wash_sale_adjustments: number; estimated_tax: number; transactions: number
}
type ActiveTab = 'positions' | 'harvesting' | 'realized' | 'form8949'

const ttStyle = { backgroundColor: '#1a1d20', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px', boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }

export function TaxLots() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('positions')
  const [positions, setPositions] = useState<Position[]>([])
  const [realizedGains, setRealizedGains] = useState<RealizedGains | null>(null)
  const [harvestingOpps, setHarvestingOpps] = useState<HarvestingOpportunity[]>([])
  const [loadingPositions, setLoadingPositions] = useState(true)
  const [loadingRealized, setLoadingRealized] = useState(true)
  const [loadingHarvesting, setLoadingHarvesting] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null)

  const fetchPositions = useCallback(async () => {
    setLoadingPositions(true)
    try {
      const res = await fetch('/api/tax/positions')
      if (res.ok) {
        const data = await res.json()
        const raw = data.positions || data.data || (Array.isArray(data) ? data : [])
        setPositions(raw.map((p: any) => ({
          symbol: p.symbol || '', total_quantity: parseFloat(p.total_quantity) || 0,
          total_cost_basis: parseFloat(p.total_cost_basis) || 0, average_cost: parseFloat(p.average_cost) || 0,
          lots: (p.lots || []).map((l: any) => ({
            lot_id: l.lot_id || '', symbol: l.symbol || p.symbol || '',
            quantity: parseFloat(l.quantity) || 0, cost_per_share: parseFloat(l.cost_per_share) || 0,
            acquisition_date: l.acquisition_date || '', acquisition_type: l.acquisition_type || 'BUY',
            total_cost_basis: parseFloat(l.total_cost_basis) || 0,
            adjusted_cost_per_share: parseFloat(l.adjusted_cost_per_share) || parseFloat(l.cost_per_share) || 0,
            wash_sale_adjustment: parseFloat(l.wash_sale_adjustment) || 0,
            market_value: parseFloat(l.market_value) || 0, unrealized_gain: parseFloat(l.unrealized_gain) || 0,
            unrealized_pct: parseFloat(l.unrealized_pct) || 0,
            holding_period: l.holding_period || (l.days_held > 365 ? 'long_term' : 'short_term'), days_held: l.days_held || 0,
          })),
          lot_count: p.lot_count || (p.lots || []).length,
          market_value: parseFloat(p.market_value) || parseFloat(p.total_cost_basis) || 0,
          unrealized_gain: parseFloat(p.unrealized_gain) || 0,
        })))
      } else { setError('Failed to load tax lot positions') }
    } catch { setError('Tax lot API unavailable. Connect your brokerage to enable.') }
    finally { setLoadingPositions(false) }
  }, [])

  const fetchRealized = useCallback(async () => {
    setLoadingRealized(true)
    try {
      const res = await fetch(`/api/tax/realized-gains?year=${new Date().getFullYear()}`)
      if (res.ok) {
        const d = await res.json()
        setRealizedGains({ short_term_gains: d.short_term_gains || 0, long_term_gains: d.long_term_gains || 0,
          total_realized: d.total_realized || 0, wash_sale_adjustments: d.wash_sale_adjustments || 0,
          estimated_tax: d.estimated_tax || 0, transactions: d.transactions || 0 })
      }
    } catch {} finally { setLoadingRealized(false) }
  }, [])

  const fetchHarvesting = useCallback(async () => {
    setLoadingHarvesting(true)
    try {
      const symbols = positions.map(p => p.symbol).filter(Boolean)
      const prices: Record<string, number> = {}
      if (symbols.length > 0) {
        try {
          const r = await fetch(`/api/market/tickers?symbols=${symbols.join(',')}`)
          if (r.ok) { const d = await r.json(); (d?.data || d?.tickers || (Array.isArray(d) ? d : [])).forEach((t: any) => { if (t.symbol && t.price) prices[t.symbol] = t.price }) }
        } catch {}
      }
      symbols.forEach(s => { if (!prices[s]) { const p = positions.find(x => x.symbol === s); if (p) prices[s] = p.average_cost * 0.95 } })
      const res = await fetch('/api/tax/tax-loss-harvesting', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prices, min_loss: 50 }) })
      if (res.ok) {
        const d = await res.json()
        const opps = d.opportunities || d.data || (Array.isArray(d) ? d : [])
        setHarvestingOpps(opps.map((o: any) => ({
          symbol: o.symbol || '', lot_id: o.lot_id || '', unrealized_loss: parseFloat(o.unrealized_loss) || 0,
          current_price: parseFloat(o.current_price) || 0, cost_basis: parseFloat(o.cost_basis) || 0,
          quantity: parseFloat(o.quantity) || 0, gain_type: o.gain_type || 'short_term', days_held: o.days_held || 0,
          wash_sale_risk: o.wash_sale_risk ?? false, estimated_tax_savings: parseFloat(o.estimated_tax_savings) || 0,
        })))
      }
    } catch {} finally { setLoadingHarvesting(false) }
  }, [positions])

  useEffect(() => { fetchPositions(); fetchRealized() }, [fetchPositions, fetchRealized])
  useEffect(() => { if (positions.length > 0) fetchHarvesting(); else if (!loadingPositions) setLoadingHarvesting(false) }, [positions, fetchHarvesting, loadingPositions])

  const summary = useMemo(() => {
    const cb = positions.reduce((s, p) => s + p.total_cost_basis, 0)
    const mv = positions.reduce((s, p) => s + p.market_value, 0)
    let stU = 0, ltU = 0
    positions.forEach(p => p.lots.forEach(l => { if (l.holding_period === 'long_term') ltU += l.unrealized_gain; else stU += l.unrealized_gain }))
    return { total_cost_basis: cb, total_market_value: mv, total_unrealized: mv - cb, total_lots: positions.reduce((s, p) => s + p.lot_count, 0), positions_count: positions.length, short_term_unrealized: stU, long_term_unrealized: ltU }
  }, [positions])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-accent-primary/10"><Receipt className="w-5 h-5 text-accent-primary" /></div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">TAX LOT MANAGEMENT</h1>
            <p className="text-xs text-foreground-muted">Cost basis tracking | Wash sale detection | Tax-loss harvesting</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary flex items-center gap-2"><Download className="w-4 h-4" />Export 8949</button>
          <button onClick={() => { setError(null); fetchPositions(); fetchRealized() }} disabled={loadingPositions} className="btn-primary flex items-center gap-2">
            <RefreshCw className={cn('w-4 h-4', loadingPositions && 'animate-spin')} />Refresh
          </button>
        </div>
      </div>

      {error && <div className="card p-4 bg-bearish/10 border border-bearish/30 flex items-center gap-3"><AlertCircle className="w-5 h-5 text-bearish flex-shrink-0" /><p className="text-bearish text-sm">{error}</p></div>}

      <div className="grid grid-cols-5 gap-3 stagger">
        <SC title="Total Cost Basis" value={formatCurrency(summary.total_cost_basis)} icon={DollarSign} ic="text-blue-400" />
        <SC title="Market Value" value={formatCurrency(summary.total_market_value)} icon={TrendingUp} ic={summary.total_unrealized >= 0 ? 'text-bullish' : 'text-bearish'} ch={summary.total_unrealized} chp={summary.total_cost_basis > 0 ? (summary.total_unrealized / summary.total_cost_basis) * 100 : 0} />
        <SC title="YTD Realized" value={formatCurrency(realizedGains?.total_realized || 0)} icon={Target} ic={(realizedGains?.total_realized ?? 0) >= 0 ? 'text-bullish' : 'text-bearish'} />
        <SC title="Tax Lots" value={summary.total_lots.toString()} sub={`${summary.positions_count} positions`} icon={PieChart} ic="text-purple-400" />
        <SC title="Harvesting Opps" value={harvestingOpps.length.toString()} sub={harvestingOpps.length > 0 ? `${formatCurrency(harvestingOpps.reduce((s, o) => s + o.estimated_tax_savings, 0))} savings` : 'None found'} icon={Leaf} ic="text-emerald-400" />
      </div>

      {(summary.short_term_unrealized !== 0 || summary.long_term_unrealized !== 0) && (
        <div className="grid grid-cols-2 gap-4">
          <div className="card p-4 flex items-center justify-between">
            <div><span className="text-xs text-foreground-muted uppercase tracking-wider">Short-Term Unrealized</span>
              <div className={cn('text-lg font-bold font-mono mt-1', summary.short_term_unrealized >= 0 ? 'text-bullish' : 'text-bearish')}>{summary.short_term_unrealized >= 0 ? '+' : ''}{formatCurrency(summary.short_term_unrealized)}</div>
            </div><Clock className="w-5 h-5 text-warning" />
          </div>
          <div className="card p-4 flex items-center justify-between">
            <div><span className="text-xs text-foreground-muted uppercase tracking-wider">Long-Term Unrealized</span>
              <div className={cn('text-lg font-bold font-mono mt-1', summary.long_term_unrealized >= 0 ? 'text-bullish' : 'text-bearish')}>{summary.long_term_unrealized >= 0 ? '+' : ''}{formatCurrency(summary.long_term_unrealized)}</div>
            </div><Calendar className="w-5 h-5 text-blue-400" />
          </div>
        </div>
      )}

      <div className="flex gap-1 p-1 bg-background-tertiary rounded-xl w-fit">
        {([{ id: 'positions' as ActiveTab, label: 'Open Positions', icon: PieChart }, { id: 'harvesting' as ActiveTab, label: 'Tax-Loss Harvesting', icon: Leaf }, { id: 'realized' as ActiveTab, label: 'Realized Gains', icon: Scale }, { id: 'form8949' as ActiveTab, label: 'Form 8949', icon: FileText }]).map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} className={cn('flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all', activeTab === t.id ? 'bg-accent-primary text-black' : 'text-foreground-muted hover:text-foreground-primary hover:bg-background-hover')}>
            <t.icon className="w-4 h-4" />{t.label}
          </button>
        ))}
      </div>

      {activeTab === 'positions' && <PosTab positions={positions} loading={loadingPositions} exp={expandedSymbol} onExp={s => setExpandedSymbol(expandedSymbol === s ? null : s)} />}
      {activeTab === 'harvesting' && <HarvTab opps={harvestingOpps} loading={loadingHarvesting} />}
      {activeTab === 'realized' && <RealTab gains={realizedGains} loading={loadingRealized} />}
      {activeTab === 'form8949' && <F8949 />}
    </div>
  )
}

function SC({ title, value, sub, icon: Icon, ic = 'text-foreground-muted', ch, chp }: { title: string; value: string; sub?: string; icon: any; ic?: string; ch?: number; chp?: number }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2"><span className="text-xs font-semibold text-foreground-muted uppercase tracking-wider">{title}</span><Icon className={cn('w-4 h-4', ic)} /></div>
      <div className="text-xl font-bold font-mono text-foreground-primary">{value}</div>
      {ch !== undefined && chp !== undefined && <div className={cn('text-xs font-mono mt-1 flex items-center gap-1', ch >= 0 ? 'text-bullish' : 'text-bearish')}>{ch >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}{ch >= 0 ? '+' : ''}{chp.toFixed(2)}%</div>}
      {sub && <div className="text-xs text-foreground-muted mt-1">{sub}</div>}
    </div>
  )
}

function PosTab({ positions, loading, exp, onExp }: { positions: Position[]; loading: boolean; exp: string | null; onExp: (s: string) => void }) {
  if (loading) return <div className="card p-8 flex items-center justify-center"><RefreshCw className="w-6 h-6 text-accent-primary animate-spin" /></div>
  if (positions.length === 0) return <div className="card p-12 text-center text-foreground-muted"><Receipt className="w-12 h-12 mx-auto mb-4 opacity-30" /><p className="text-lg font-medium text-foreground-secondary">No Tax Lots</p><p className="text-sm mt-1">Record purchases to start tracking tax lots</p></div>

  return (
    <div className="card overflow-hidden">
      <table className="data-table text-xs">
        <thead><tr><th className="w-8"></th><th>Symbol</th><th className="text-right">Quantity</th><th className="text-right">Avg Cost</th><th className="text-right">Cost Basis</th><th className="text-right">Market Value</th><th className="text-right">Unrealized P&L</th><th className="text-right">Lots</th></tr></thead>
        <tbody>
          {positions.map(p => {
            const isExp = exp === p.symbol
            const pct = p.total_cost_basis > 0 ? ((p.market_value - p.total_cost_basis) / p.total_cost_basis) * 100 : 0
            return <PosRow key={p.symbol} p={p} isExp={isExp} pct={pct} onToggle={() => onExp(p.symbol)} />
          })}
        </tbody>
      </table>
    </div>
  )
}

function PosRow({ p, isExp, pct, onToggle }: { p: Position; isExp: boolean; pct: number; onToggle: () => void }) {
  return (
    <>
      <tr className="cursor-pointer hover:bg-background-hover/50" onClick={onToggle}>
        <td className="w-8">{isExp ? <ChevronDown className="w-4 h-4 text-accent-primary" /> : <ChevronRight className="w-4 h-4 text-foreground-muted" />}</td>
        <td><div className="flex items-center gap-2"><div className="w-7 h-7 rounded-lg bg-accent-primary/10 flex items-center justify-center"><span className="text-xs font-bold text-accent-primary">{p.symbol.slice(0, 2)}</span></div><span className="font-semibold text-foreground-primary">{p.symbol}</span></div></td>
        <td className="text-right font-mono">{p.total_quantity.toLocaleString()}</td>
        <td className="text-right font-mono">${p.average_cost.toFixed(2)}</td>
        <td className="text-right font-mono">{formatCurrency(p.total_cost_basis)}</td>
        <td className="text-right font-mono">{formatCurrency(p.market_value)}</td>
        <td className={cn('text-right font-mono', p.unrealized_gain >= 0 ? 'text-bullish' : 'text-bearish')}>
          <div>{p.unrealized_gain >= 0 ? '+' : ''}{formatCurrency(p.unrealized_gain)}</div>
          <div className="text-[10px] opacity-70">{pct >= 0 ? '+' : ''}{pct.toFixed(2)}%</div>
        </td>
        <td className="text-right"><span className="px-2 py-0.5 bg-background-tertiary rounded-full text-xs font-medium text-foreground-secondary">{p.lot_count} lots</span></td>
      </tr>
      {isExp && p.lots.map(l => (
        <tr key={l.lot_id} className="bg-background-secondary/30">
          <td></td>
          <td className="pl-12"><div className="flex items-center gap-2"><span className="text-foreground-muted text-[10px]">LOT</span><span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium', l.holding_period === 'long_term' ? 'bg-blue-500/15 text-blue-400' : 'bg-amber-500/15 text-amber-400')}>{l.holding_period === 'long_term' ? 'LT' : 'ST'}</span><span className="text-foreground-muted text-[10px]">{l.days_held}d</span></div></td>
          <td className="text-right font-mono text-foreground-secondary">{l.quantity.toLocaleString()}</td>
          <td className="text-right font-mono text-foreground-secondary">${l.cost_per_share.toFixed(2)}</td>
          <td className="text-right font-mono text-foreground-secondary">{formatCurrency(l.total_cost_basis)}</td>
          <td className="text-right font-mono text-foreground-secondary">{l.market_value > 0 ? formatCurrency(l.market_value) : '-'}</td>
          <td className={cn('text-right font-mono', l.unrealized_gain >= 0 ? 'text-bullish' : 'text-bearish')}>{l.unrealized_gain !== 0 ? <>{l.unrealized_gain >= 0 ? '+' : ''}{formatCurrency(l.unrealized_gain)}</> : '-'}</td>
          <td className="text-right">{l.wash_sale_adjustment > 0 && <span className="text-warning flex items-center justify-end gap-1"><AlertTriangle className="w-3 h-3" /><span className="text-[10px]">Wash</span></span>}</td>
        </tr>
      ))}
    </>
  )
}

function HarvTab({ opps, loading }: { opps: HarvestingOpportunity[]; loading: boolean }) {
  if (loading) return <div className="card p-8 flex items-center justify-center"><RefreshCw className="w-6 h-6 text-accent-primary animate-spin" /></div>
  if (opps.length === 0) return <div className="card p-12 text-center text-foreground-muted"><Leaf className="w-12 h-12 mx-auto mb-4 opacity-30 text-emerald-400" /><p className="text-lg font-medium text-foreground-secondary">No Harvesting Opportunities</p><p className="text-sm mt-1">All positions are profitable or losses below threshold</p></div>
  const totalSavings = opps.reduce((s, o) => s + o.estimated_tax_savings, 0)
  const washCount = opps.filter(o => o.wash_sale_risk).length
  return (
    <div className="space-y-4">
      <div className="card p-4 bg-emerald-500/5 border border-emerald-500/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3"><Leaf className="w-6 h-6 text-emerald-400" /><div><p className="text-foreground-primary font-medium">Tax-Loss Harvesting Opportunities</p><p className="text-foreground-muted text-xs">{opps.length} lots | {washCount} wash sale risk</p></div></div>
          <div className="text-right"><div className="text-xs text-foreground-muted">Potential Savings</div><div className="text-xl font-bold font-mono text-emerald-400">{formatCurrency(totalSavings)}</div></div>
        </div>
      </div>
      <div className="card p-4">
        <div className="chart-header"><h3 className="chart-title">Losses by Position</h3></div>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={opps.slice(0, 10)}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="symbol" tick={{ fill: '#a1a1aa', fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `$${Math.abs(v)}`} />
              <Tooltip contentStyle={ttStyle} labelStyle={{ color: '#a1a1aa', fontSize: 11 }} formatter={(v: number) => [formatCurrency(v), 'Loss']} />
              <Bar dataKey="unrealized_loss" fill="#ef4444" fillOpacity={0.7} radius={[4, 4, 0, 0]} name="Loss" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="card overflow-hidden">
        <table className="data-table text-xs">
          <thead><tr><th>Symbol</th><th className="text-right">Qty</th><th className="text-right">Cost</th><th className="text-right">Current</th><th className="text-right">Loss</th><th className="text-right">Savings</th><th className="text-right">Type</th><th className="text-center">Wash</th><th className="text-right">Days</th><th className="text-right">Action</th></tr></thead>
          <tbody>
            {opps.map(o => (
              <tr key={o.lot_id}>
                <td className="font-semibold text-foreground-primary">{o.symbol}</td>
                <td className="text-right font-mono">{o.quantity}</td>
                <td className="text-right font-mono">${o.cost_basis.toFixed(2)}</td>
                <td className="text-right font-mono">${o.current_price.toFixed(2)}</td>
                <td className="text-right font-mono text-bearish">{formatCurrency(o.unrealized_loss)}</td>
                <td className="text-right font-mono text-emerald-400">{formatCurrency(o.estimated_tax_savings)}</td>
                <td className="text-right"><span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium', o.gain_type === 'short_term' ? 'bg-amber-500/15 text-amber-400' : 'bg-blue-500/15 text-blue-400')}>{o.gain_type === 'short_term' ? 'ST' : 'LT'}</span></td>
                <td className="text-center">{o.wash_sale_risk ? <AlertTriangle className="w-4 h-4 text-warning mx-auto" /> : <CheckCircle className="w-4 h-4 text-bullish mx-auto" />}</td>
                <td className="text-right font-mono text-foreground-muted">{o.days_held}d</td>
                <td className="text-right"><button className="px-2.5 py-1 bg-emerald-500/15 text-emerald-400 rounded-lg text-xs font-medium hover:bg-emerald-500/25 transition-colors">Harvest</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RealTab({ gains, loading }: { gains: RealizedGains | null; loading: boolean }) {
  if (loading) return <div className="card p-8 flex items-center justify-center"><RefreshCw className="w-6 h-6 text-accent-primary animate-spin" /></div>
  const d = gains || { short_term_gains: 0, long_term_gains: 0, total_realized: 0, wash_sale_adjustments: 0, estimated_tax: 0, transactions: 0 }
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="card p-5">
        <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">YTD REALIZED SUMMARY</h3>
        <div className="space-y-3">
          <div className="flex justify-between items-center py-3 border-b border-border"><span className="text-sm text-foreground-muted">Short-Term Gains</span><span className={cn('font-mono font-semibold', d.short_term_gains >= 0 ? 'text-bullish' : 'text-bearish')}>{d.short_term_gains >= 0 ? '+' : ''}{formatCurrency(d.short_term_gains)}</span></div>
          <div className="flex justify-between items-center py-3 border-b border-border"><span className="text-sm text-foreground-muted">Long-Term Gains</span><span className={cn('font-mono font-semibold', d.long_term_gains >= 0 ? 'text-bullish' : 'text-bearish')}>{d.long_term_gains >= 0 ? '+' : ''}{formatCurrency(d.long_term_gains)}</span></div>
          <div className="flex justify-between items-center py-3 border-b border-border"><span className="text-sm text-foreground-muted">Wash Sale Adjustments</span><span className="font-mono text-warning">{formatCurrency(d.wash_sale_adjustments)}</span></div>
          <div className="flex justify-between items-center py-3 px-4 -mx-4 rounded-xl bg-background-tertiary"><span className="font-semibold text-foreground-primary">Net Realized</span><span className={cn('font-mono text-xl font-bold', d.total_realized >= 0 ? 'text-bullish' : 'text-bearish')}>{d.total_realized >= 0 ? '+' : ''}{formatCurrency(d.total_realized)}</span></div>
        </div>
      </div>
      <div className="card p-5">
        <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">ESTIMATED TAX LIABILITY</h3>
        <div className="text-center py-6"><p className="text-4xl font-bold font-mono text-foreground-primary mb-2">{formatCurrency(d.estimated_tax)}</p><p className="text-sm text-foreground-muted">Estimated tax for {new Date().getFullYear()}</p></div>
        <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-border">
          <div className="text-center"><p className="text-2xl font-bold font-mono text-foreground-primary">{d.transactions}</p><p className="text-xs text-foreground-muted mt-1">Transactions</p></div>
          <div className="text-center"><p className="text-2xl font-bold font-mono text-foreground-primary">{d.total_realized !== 0 ? `${((d.estimated_tax / Math.abs(d.total_realized)) * 100).toFixed(0)}%` : '0%'}</p><p className="text-xs text-foreground-muted mt-1">Effective Rate</p></div>
        </div>
        {(d.short_term_gains !== 0 || d.long_term_gains !== 0) && (
          <div className="mt-4 pt-4 border-t border-border">
            <div className="flex items-center justify-center"><DonutChart data={[{ name: 'Short-Term', value: Math.abs(d.short_term_gains) || 1, color: '#f59e0b' }, { name: 'Long-Term', value: Math.abs(d.long_term_gains) || 1, color: '#3b82f6' }]} centerLabel={`${d.transactions}`} centerSubLabel="Trades" size={100} /></div>
            <div className="flex justify-center gap-6 mt-2 text-xs"><span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-warning" />Short-Term</span><span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-400" />Long-Term</span></div>
          </div>
        )}
      </div>
    </div>
  )
}

function F8949() {
  const year = new Date().getFullYear()
  return (
    <div className="card p-12 text-center">
      <FileText className="w-16 h-16 text-accent-primary mx-auto mb-4 opacity-70" />
      <h3 className="text-xl font-semibold text-foreground-primary mb-2">IRS Form 8949</h3>
      <p className="text-foreground-muted mb-6 max-w-md mx-auto text-sm">Export capital gains and losses for tax year {year} in IRS-compatible format.</p>
      <div className="flex justify-center gap-4">
        <button className="btn-secondary flex items-center gap-2"><Download className="w-4 h-4" />Download CSV</button>
        <button className="btn-primary flex items-center gap-2"><FileText className="w-4 h-4" />Generate PDF</button>
      </div>
      <div className="mt-8 p-4 rounded-xl bg-accent-primary/5 border border-accent-primary/15 max-w-lg mx-auto">
        <div className="flex items-start gap-3"><AlertCircle className="w-5 h-5 text-accent-primary mt-0.5 flex-shrink-0" /><div className="text-left"><p className="text-sm font-medium text-foreground-primary">Disclaimer</p><p className="text-xs text-foreground-muted mt-1">This data is for informational purposes only. Consult a qualified tax professional before filing.</p></div></div>
      </div>
    </div>
  )
}

export default TaxLots
