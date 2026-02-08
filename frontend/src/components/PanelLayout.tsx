/**
 * Multi-Panel Layout System
 * Configurable grid-based panels with save/load presets.
 * Panel types: Chart, Positions, Orders, Signals, Risk, PnL, Logs.
 * Maximize any panel with double-click. Remember layout across sessions.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  Maximize2,
  Minimize2,
  X,
  GripVertical,
  LayoutGrid,
  Save,
  FolderOpen,
  Plus,
  Trash2,
  ChevronDown,
  BarChart3,
  Briefcase,
  ClipboardList,
  Zap,
  Shield,
  DollarSign,
  ScrollText,
  Activity,
  LineChart,
  Brain,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { SignalFeed } from './SignalFeed'

// Panel type definitions
type PanelType = 'signals' | 'positions' | 'orders' | 'risk' | 'pnl' | 'logs' | 'chart' | 'brain' | 'flow'

interface PanelConfig {
  id: string
  type: PanelType
  title: string
  gridArea: string
  minimized: boolean
}

interface LayoutPreset {
  id: string
  name: string
  panels: PanelConfig[]
  gridTemplate: string
  gridRows: string
}

const panelTypeConfig: Record<PanelType, { icon: React.ComponentType<{ className?: string }>; label: string; color: string }> = {
  signals: { icon: Zap, label: 'Signal Feed', color: 'text-warning' },
  positions: { icon: Briefcase, label: 'Positions', color: 'text-info' },
  orders: { icon: ClipboardList, label: 'Orders', color: 'text-accent-primary' },
  risk: { icon: Shield, label: 'Risk Monitor', color: 'text-bearish' },
  pnl: { icon: DollarSign, label: 'P&L', color: 'text-bullish' },
  logs: { icon: ScrollText, label: 'System Logs', color: 'text-foreground-muted' },
  chart: { icon: LineChart, label: 'Chart', color: 'text-accent-primary' },
  brain: { icon: Brain, label: 'AI Brain', color: 'text-accent-primary' },
  flow: { icon: Activity, label: 'Options Flow', color: 'text-warning' },
}

// Default layout presets
const defaultPresets: LayoutPreset[] = [
  {
    id: 'trading',
    name: 'Trading',
    gridTemplate: '"signals positions" "signals orders"',
    gridRows: '1fr 1fr',
    panels: [
      { id: 'p1', type: 'signals', title: 'Signal Feed', gridArea: 'signals', minimized: false },
      { id: 'p2', type: 'positions', title: 'Positions', gridArea: 'positions', minimized: false },
      { id: 'p3', type: 'orders', title: 'Orders', gridArea: 'orders', minimized: false },
    ],
  },
  {
    id: 'analysis',
    name: 'Analysis',
    gridTemplate: '"signals brain" "risk pnl"',
    gridRows: '1fr 1fr',
    panels: [
      { id: 'p1', type: 'signals', title: 'Signal Feed', gridArea: 'signals', minimized: false },
      { id: 'p2', type: 'brain', title: 'AI Brain', gridArea: 'brain', minimized: false },
      { id: 'p3', type: 'risk', title: 'Risk Monitor', gridArea: 'risk', minimized: false },
      { id: 'p4', type: 'pnl', title: 'P&L', gridArea: 'pnl', minimized: false },
    ],
  },
  {
    id: 'risk-review',
    name: 'Risk Review',
    gridTemplate: '"risk positions" "risk pnl"',
    gridRows: '1fr 1fr',
    panels: [
      { id: 'p1', type: 'risk', title: 'Risk Monitor', gridArea: 'risk', minimized: false },
      { id: 'p2', type: 'positions', title: 'Positions', gridArea: 'positions', minimized: false },
      { id: 'p3', type: 'pnl', title: 'P&L', gridArea: 'pnl', minimized: false },
    ],
  },
  {
    id: 'full-signals',
    name: 'Full Signals',
    gridTemplate: '"signals"',
    gridRows: '1fr',
    panels: [
      { id: 'p1', type: 'signals', title: 'Signal Feed', gridArea: 'signals', minimized: false },
    ],
  },
]

const LAYOUT_STORAGE_KEY = 'quant-panel-layout'
const PRESETS_STORAGE_KEY = 'quant-panel-presets'

function loadLayout(): { presetId: string; customPresets: LayoutPreset[] } {
  try {
    const stored = localStorage.getItem(LAYOUT_STORAGE_KEY)
    const presets = localStorage.getItem(PRESETS_STORAGE_KEY)
    return {
      presetId: stored || 'trading',
      customPresets: presets ? JSON.parse(presets) : [],
    }
  } catch {
    return { presetId: 'trading', customPresets: [] }
  }
}

// Panel content renderers
function PanelContent({ type }: { type: PanelType }) {
  switch (type) {
    case 'signals':
      return <SignalFeed maxHeight="100%" className="h-full border-0 rounded-none" />
    case 'positions':
      return <PositionsPanel />
    case 'orders':
      return <OrdersPanel />
    case 'risk':
      return <RiskPanel />
    case 'pnl':
      return <PnLPanel />
    case 'logs':
      return <LogsPanel />
    case 'chart':
      return <ChartPanel />
    case 'brain':
      return <BrainPanel />
    case 'flow':
      return <FlowPanel />
    default:
      return <div className="p-4 text-foreground-muted text-sm">Unknown panel type</div>
  }
}

// Minimal panel implementations using existing API data
function PositionsPanel() {
  const { data } = useQuery({ queryKey: ['panel-positions'], queryFn: () => portfolioApi.getPositions(), refetchInterval: 5000 })
  const positions = data?.ok ? data.data || [] : []

  return (
    <div className="h-full overflow-auto p-2">
      {positions.length === 0 ? (
        <EmptyPanel icon={Briefcase} message="No open positions" />
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-foreground-muted border-b border-border">
              <th className="text-left py-1 px-2">Symbol</th>
              <th className="text-right py-1 px-2">Qty</th>
              <th className="text-right py-1 px-2">Price</th>
              <th className="text-right py-1 px-2">P&L</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p, i) => {
              const pos = p as unknown as Record<string, unknown>
              const qty = Number(pos.qty ?? pos.quantity ?? 0)
              const price = Number(pos.current_price ?? pos.market_value ?? 0)
              const pnl = Number(pos.unrealized_pl ?? pos.pnl ?? 0)
              return (
                <tr key={i} className="border-b border-border/30 hover:bg-background-hover/50">
                  <td className="py-1.5 px-2 font-bold text-accent-primary">{String(pos.symbol ?? '')}</td>
                  <td className="py-1.5 px-2 text-right font-mono">{qty}</td>
                  <td className="py-1.5 px-2 text-right font-mono">${price.toFixed(2)}</td>
                  <td className={cn('py-1.5 px-2 text-right font-mono font-bold', pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

function OrdersPanel() {
  const { data } = useQuery({ queryKey: ['panel-orders'], queryFn: () => tradingApi.getOrders(), refetchInterval: 5000 })
  const orders = data?.ok ? data.data || [] : []

  return (
    <div className="h-full overflow-auto p-2">
      {orders.length === 0 ? (
        <EmptyPanel icon={ClipboardList} message="No active orders" />
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-foreground-muted border-b border-border">
              <th className="text-left py-1 px-2">Symbol</th>
              <th className="text-left py-1 px-2">Side</th>
              <th className="text-right py-1 px-2">Qty</th>
              <th className="text-left py-1 px-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o, i) => {
              const ord = o as unknown as Record<string, unknown>
              const side = String(ord.side ?? '')
              return (
                <tr key={i} className="border-b border-border/30 hover:bg-background-hover/50">
                  <td className="py-1.5 px-2 font-bold text-accent-primary">{String(ord.symbol ?? '')}</td>
                  <td className={cn('py-1.5 px-2', side === 'buy' ? 'text-bullish' : 'text-bearish')}>{side.toUpperCase()}</td>
                  <td className="py-1.5 px-2 text-right font-mono">{Number(ord.qty ?? ord.quantity ?? 0)}</td>
                  <td className="py-1.5 px-2 text-foreground-muted">{String(ord.status ?? 'pending')}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

function RiskPanel() {
  const { data } = useQuery({ queryKey: ['panel-risk'], queryFn: () => riskApi.getMetrics(), refetchInterval: 10000 })
  const risk = data?.ok ? (data.data as PanelRiskData | null) : null

  const metrics = risk ? [
    { label: 'Risk Score', value: risk.risk_score?.toFixed(1) || '--', color: '' },
    { label: 'Exposure', value: `${(risk.exposure_pct || risk.risk_utilization || 0).toFixed(1)}%`, color: '' },
    { label: 'Max Drawdown', value: `${(risk.max_drawdown || 0).toFixed(2)}%`, color: 'text-bearish' },
    { label: 'Sharpe Ratio', value: (risk.sharpe_ratio || 0).toFixed(2), color: '' },
    { label: 'Win Rate', value: `${(risk.win_rate || 0).toFixed(1)}%`, color: '' },
    { label: 'Profit Factor', value: (risk.profit_factor || 0).toFixed(2), color: '' },
  ] : []

  return (
    <div className="h-full overflow-auto p-3">
      {!risk ? (
        <EmptyPanel icon={Shield} message="Risk data unavailable" />
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {metrics.map((m, i) => (
            <div key={i} className="bg-background-tertiary rounded p-2">
              <p className="text-[9px] text-foreground-muted uppercase">{m.label}</p>
              <p className={cn('text-sm font-mono font-bold mt-0.5', m.color || 'text-foreground-primary')}>{m.value}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function PnLPanel() {
  const { data } = useQuery({ queryKey: ['panel-portfolio'], queryFn: () => portfolioApi.getPortfolio(), refetchInterval: 5000 })
  const portfolio = data?.ok ? (data.data as PanelPortfolioData | null) : null

  const equity = portfolio?.equity || portfolio?.total_value || 0
  const pnl = portfolio?.daily_pnl || portfolio?.unrealized_pnl || 0
  const buyingPower = portfolio?.buying_power || 0

  return (
    <div className="h-full overflow-auto p-3">
      {!portfolio ? (
        <EmptyPanel icon={DollarSign} message="Portfolio data unavailable" />
      ) : (
        <div className="space-y-3">
          <div className="bg-background-tertiary rounded p-3">
            <p className="text-[9px] text-foreground-muted uppercase">Equity</p>
            <p className="text-xl font-mono font-bold text-foreground-primary">${equity.toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-background-tertiary rounded p-2">
              <p className="text-[9px] text-foreground-muted uppercase">Day P&L</p>
              <p className={cn('text-sm font-mono font-bold', pnl >= 0 ? 'text-bullish' : 'text-bearish')}>
                {pnl >= 0 ? '+' : ''}{pnl.toLocaleString('en-US', { minimumFractionDigits: 2, style: 'currency', currency: 'USD' })}
              </p>
            </div>
            <div className="bg-background-tertiary rounded p-2">
              <p className="text-[9px] text-foreground-muted uppercase">Buying Power</p>
              <p className="text-sm font-mono font-bold text-foreground-primary">
                ${buyingPower.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function LogsPanel() {
  const [logs] = useState<Array<{ time: string; level: string; message: string }>>([])

  return (
    <div className="h-full overflow-auto p-2 font-mono text-[11px]">
      {logs.length === 0 ? (
        <EmptyPanel icon={ScrollText} message="No system logs" />
      ) : (
        logs.map((log, i) => (
          <div key={i} className="flex gap-2 py-0.5">
            <span className="text-foreground-muted">{log.time}</span>
            <span className={cn(
              log.level === 'ERROR' ? 'text-bearish' :
              log.level === 'WARN' ? 'text-warning' : 'text-foreground-muted'
            )}>[{log.level}]</span>
            <span className="text-foreground-secondary">{log.message}</span>
          </div>
        ))
      )}
    </div>
  )
}

function ChartPanel() {
  return (
    <div className="h-full flex items-center justify-center p-4">
      <EmptyPanel icon={LineChart} message="Chart panel - Select a symbol to display" />
    </div>
  )
}

function BrainPanel() {
  const { data } = useQuery({ queryKey: ['panel-brain'], queryFn: () => brainApi.getStatus(), refetchInterval: 10000 })
  const brain = data?.ok ? (data.data as PanelBrainData | null) : null

  return (
    <div className="h-full overflow-auto p-3">
      {!brain ? (
        <EmptyPanel icon={Brain} message="Brain data unavailable" />
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-background-tertiary rounded p-2">
              <p className="text-[9px] text-foreground-muted uppercase">Status</p>
              <p className={cn('text-sm font-bold', brain.is_active ? 'text-bullish' : 'text-foreground-muted')}>
                {brain.is_active ? 'ACTIVE' : 'IDLE'}
              </p>
            </div>
            <div className="bg-background-tertiary rounded p-2">
              <p className="text-[9px] text-foreground-muted uppercase">Accuracy</p>
              <p className="text-sm font-mono font-bold text-accent-primary">{((brain.accuracy ?? 0) * 100).toFixed(1)}%</p>
            </div>
            <div className="bg-background-tertiary rounded p-2">
              <p className="text-[9px] text-foreground-muted uppercase">Signals</p>
              <p className="text-sm font-mono font-bold text-warning">{brain.signals_generated || 0}</p>
            </div>
            <div className="bg-background-tertiary rounded p-2">
              <p className="text-[9px] text-foreground-muted uppercase">Strategies</p>
              <p className="text-sm font-mono font-bold text-foreground-primary">{brain.active_strategies || 0}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function FlowPanel() {
  return (
    <div className="h-full flex items-center justify-center p-4">
      <EmptyPanel icon={Activity} message="Options flow data - Connect for real-time feed" />
    </div>
  )
}

function EmptyPanel({ icon: Icon, message }: { icon: React.ComponentType<{ className?: string }>; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-foreground-muted py-8">
      <Icon className="w-8 h-8 mb-2 opacity-30" />
      <p className="text-xs">{message}</p>
    </div>
  )
}

// Import API clients - using dynamic references since they're in the same project
import { useQuery } from '@tanstack/react-query'
import { portfolioApi, tradingApi, riskApi, brainApi } from '@/api/client'

/** Extended risk metrics from API for panel display */
interface PanelRiskData {
  risk_score?: number
  exposure_pct?: number
  risk_utilization?: number
  max_drawdown?: number
  sharpe_ratio?: number
  win_rate?: number
  profit_factor?: number
}

/** Extended portfolio data from API for panel display */
interface PanelPortfolioData {
  equity?: number
  total_value?: number
  daily_pnl?: number
  unrealized_pnl?: number
  buying_power?: number
}

/** Extended brain status from API for panel display */
interface PanelBrainData {
  is_active?: boolean
  accuracy?: number
  signals_generated?: number
  active_strategies?: number
}

// Main Panel Layout component
interface PanelLayoutProps {
  className?: string
}

export function PanelLayout({ className }: PanelLayoutProps) {
  const stored = loadLayout()
  const [allPresets, setAllPresets] = useState<LayoutPreset[]>([...defaultPresets, ...stored.customPresets])
  const [activePresetId, setActivePresetId] = useState(stored.presetId)
  const [maximizedPanel, setMaximizedPanel] = useState<string | null>(null)
  const [showPresetMenu, setShowPresetMenu] = useState(false)
  const [showAddPanel, setShowAddPanel] = useState(false)

  const activePreset = allPresets.find(p => p.id === activePresetId) || allPresets[0]

  // Persist layout selection
  useEffect(() => {
    localStorage.setItem(LAYOUT_STORAGE_KEY, activePresetId)
  }, [activePresetId])

  // Save custom presets
  useEffect(() => {
    const custom = allPresets.filter(p => !defaultPresets.find(d => d.id === p.id))
    localStorage.setItem(PRESETS_STORAGE_KEY, JSON.stringify(custom))
  }, [allPresets])

  const handleMaximize = useCallback((panelId: string) => {
    setMaximizedPanel(prev => prev === panelId ? null : panelId)
  }, [])

  const saveCurrentAsPreset = useCallback(() => {
    const name = prompt('Preset name:')
    if (!name?.trim()) return

    const newPreset: LayoutPreset = {
      ...activePreset,
      id: `custom-${Date.now()}`,
      name: name.trim(),
    }
    setAllPresets(prev => [...prev, newPreset])
    setActivePresetId(newPreset.id)
  }, [activePreset])

  const deletePreset = useCallback((id: string) => {
    if (defaultPresets.find(p => p.id === id)) return // Can't delete defaults
    setAllPresets(prev => prev.filter(p => p.id !== id))
    if (activePresetId === id) setActivePresetId('trading')
  }, [activePresetId])

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-background-secondary border-b border-border">
        <div className="flex items-center gap-2">
          <LayoutGrid className="w-4 h-4 text-accent-primary" />
          <span className="text-xs font-medium text-foreground-primary">Panels</span>

          {/* Preset selector */}
          <div className="relative">
            <button
              onClick={() => setShowPresetMenu(!showPresetMenu)}
              className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-background-tertiary text-foreground-secondary hover:bg-background-hover transition-colors"
            >
              {activePreset.name}
              <ChevronDown className="w-3 h-3" />
            </button>
            {showPresetMenu && (
              <div className="absolute top-full left-0 mt-1 bg-background-elevated border border-border rounded-lg shadow-elevated z-50 min-w-[160px] py-1">
                {allPresets.map(preset => (
                  <div key={preset.id} className="flex items-center">
                    <button
                      onClick={() => { setActivePresetId(preset.id); setShowPresetMenu(false) }}
                      className={cn(
                        'flex-1 text-left text-xs px-3 py-1.5 hover:bg-background-hover transition-colors',
                        preset.id === activePresetId ? 'text-accent-primary' : 'text-foreground-secondary'
                      )}
                    >
                      {preset.name}
                    </button>
                    {!defaultPresets.find(d => d.id === preset.id) && (
                      <button
                        onClick={(e) => { e.stopPropagation(); deletePreset(preset.id) }}
                        className="p-1 mr-1 rounded hover:bg-bearish/20 text-foreground-muted"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={saveCurrentAsPreset}
            className="flex items-center gap-1 text-[10px] px-2 py-1 rounded hover:bg-background-hover text-foreground-muted transition-colors"
            title="Save as preset"
          >
            <Save className="w-3 h-3" />
            Save
          </button>
          {maximizedPanel && (
            <button
              onClick={() => setMaximizedPanel(null)}
              className="flex items-center gap-1 text-[10px] px-2 py-1 rounded hover:bg-background-hover text-foreground-muted transition-colors"
            >
              <Minimize2 className="w-3 h-3" />
              Restore
            </button>
          )}
        </div>
      </div>

      {/* Panel grid */}
      <div
        className="flex-1 overflow-hidden p-1.5 gap-1.5"
        style={maximizedPanel ? {
          display: 'flex',
        } : {
          display: 'grid',
          gridTemplateAreas: activePreset.gridTemplate,
          gridTemplateRows: activePreset.gridRows,
          gridTemplateColumns: activePreset.panels.length <= 1 ? '1fr' : '1fr 1fr',
        }}
      >
        {activePreset.panels.map(panel => {
          if (maximizedPanel && maximizedPanel !== panel.id) return null

          const config = panelTypeConfig[panel.type]
          const Icon = config.icon

          return (
            <div
              key={panel.id}
              className={cn(
                'bg-background-secondary border border-border rounded-lg overflow-hidden flex flex-col',
                maximizedPanel === panel.id && 'flex-1',
              )}
              style={!maximizedPanel ? { gridArea: panel.gridArea } : undefined}
            >
              {/* Panel header */}
              <div className="flex items-center justify-between px-2 py-1.5 border-b border-border bg-background-tertiary/50 flex-shrink-0">
                <div className="flex items-center gap-1.5">
                  <Icon className={cn('w-3.5 h-3.5', config.color)} />
                  <span className="text-xs font-medium text-foreground-primary">{panel.title}</span>
                </div>
                <button
                  onClick={() => handleMaximize(panel.id)}
                  className="p-1 rounded hover:bg-background-hover text-foreground-muted transition-colors"
                  title={maximizedPanel === panel.id ? 'Restore' : 'Maximize'}
                >
                  {maximizedPanel === panel.id ? (
                    <Minimize2 className="w-3 h-3" />
                  ) : (
                    <Maximize2 className="w-3 h-3" />
                  )}
                </button>
              </div>

              {/* Panel content */}
              <div className="flex-1 overflow-hidden">
                <PanelContent type={panel.type} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
