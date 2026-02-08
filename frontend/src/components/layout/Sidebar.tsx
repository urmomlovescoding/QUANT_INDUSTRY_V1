import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Search,
  LineChart,
  FlaskConical,
  Activity,
  Waves,
  Target,
  Building2,
  CheckCircle2,
  Scale,
  Shield,
  FileText,
  Timer,
  Dice5,
  GitBranch,
  Brain,
  TrendingUp,
  Gauge,
  Cpu,
  Bot,
  Building,
  Newspaper,
  FileSearch,
  Moon,
  Calendar,
  Briefcase,
  Repeat,
  ClipboardList,
  Wifi,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
  Layers,
  GraduationCap,
  BarChart3,
  Shuffle,
  Eye,
  Calculator,
  Network,
  Sparkles,
  LayoutGrid,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { useState } from 'react'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

interface NavSection {
  title: string
  items: {
    path: string
    icon: React.ComponentType<{ className?: string }>
    label: string
  }[]
}

const navSections: NavSection[] = [
  {
    title: 'MARKETS',
    items: [
      { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
      { path: '/command-center', icon: LayoutGrid, label: 'Command Center' },
      { path: '/screener', icon: Search, label: 'Screener' },
      { path: '/charts', icon: LineChart, label: 'Charts' },
    ],
  },
  {
    title: 'ADVANCED TRADING',
    items: [
      { path: '/market-microstructure', icon: BarChart3, label: 'Microstructure' },
      { path: '/pairs-trading', icon: Shuffle, label: 'Pairs Trading' },
      { path: '/flow-scanner', icon: Eye, label: 'Options Flow' },
      { path: '/unified-brain', icon: Sparkles, label: 'Brain Dashboard' },
    ],
  },
  {
    title: 'OPTIONS',
    items: [
      { path: '/options-lab', icon: FlaskConical, label: 'Options Lab' },
      { path: '/gex-analysis', icon: Activity, label: 'GEX Analysis' },
      { path: '/flow-scanner', icon: Waves, label: 'Flow Scanner' },
      { path: '/strategies', icon: Target, label: 'Strategies' },
    ],
  },
  {
    title: 'QUANT',
    items: [
      { path: '/quant-platform', icon: Building2, label: 'Quant Platform' },
      { path: '/trade-confirm', icon: CheckCircle2, label: 'Trade Confirm' },
      { path: '/benchmark', icon: Scale, label: 'Benchmark' },
      { path: '/risk-engine', icon: Shield, label: 'Risk Engine' },
      { path: '/slide-doctrine', icon: FileText, label: 'Slide Doctrine' },
    ],
  },
  {
    title: 'ANALYTICS',
    items: [
      { path: '/backtesting', icon: Timer, label: 'Backtesting' },
      { path: '/backtest-viz', icon: LineChart, label: 'Backtest Viz' },
      { path: '/monte-carlo', icon: Dice5, label: 'Monte Carlo' },
      { path: '/correlation', icon: GitBranch, label: 'Correlation' },
      { path: '/risk-decomposition', icon: Layers, label: 'Risk Decomposition' },
      { path: '/scenario-analysis', icon: Zap, label: 'Scenario Analysis' },
    ],
  },
  {
    title: 'NEURAL AI',
    items: [
      { path: '/unified-brain', icon: Layers, label: 'Unified Brain' },
      { path: '/ml-training', icon: GraduationCap, label: 'ML Training' },
      { path: '/neural-analysis', icon: Brain, label: 'Neural Analysis' },
      { path: '/ml-predictions', icon: TrendingUp, label: 'ML Predictions' },
      { path: '/regime-detect', icon: Gauge, label: 'Regime Detect' },
      { path: '/trading-brain', icon: Cpu, label: 'Trading Brain' },
      { path: '/algo-bot', icon: Bot, label: 'Algo Bot' },
    ],
  },
  {
    title: 'PROP FIRM',
    items: [
      { path: '/tpt-dashboard', icon: Building, label: 'TPT Dashboard' },
      { path: '/futures-brain', icon: Activity, label: 'Futures Brain' },
    ],
  },
  {
    title: 'RESEARCH',
    items: [
      { path: '/13f-holdings', icon: Building2, label: '13F Holdings' },
      { path: '/sec-filings', icon: FileSearch, label: 'SEC Filings' },
      { path: '/dark-pool', icon: Moon, label: 'Dark Pool' },
      { path: '/earnings', icon: Calendar, label: 'Earnings' },
      { path: '/news', icon: Newspaper, label: 'News Center' },
    ],
  },
  {
    title: 'PORTFOLIO',
    items: [
      { path: '/portfolio', icon: Briefcase, label: 'Holdings' },
      { path: '/pairs-trading', icon: Repeat, label: 'Pairs Trading' },
      { path: '/tax-lots', icon: Calculator, label: 'Tax Lots' },
      { path: '/reports', icon: ClipboardList, label: 'Reports' },
    ],
  },
  {
    title: 'SYSTEM',
    items: [
      { path: '/api-connector', icon: Wifi, label: 'API Connector' },
      { path: '/settings', icon: Settings, label: 'Settings' },
    ],
  },
]

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const [expandedSections, setExpandedSections] = useState<string[]>(
    navSections.map(s => s.title)
  )

  const toggleSection = (title: string) => {
    setExpandedSections(prev =>
      prev.includes(title)
        ? prev.filter(t => t !== title)
        : [...prev, title]
    )
  }

  return (
    <aside
      className={cn(
        'flex flex-col transition-all duration-300 ease-smooth overflow-hidden',
        'bg-gradient-to-b from-background-secondary to-background-primary',
        'border-r border-border/50',
        collapsed ? 'w-16' : 'w-56'
      )}
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-border/50 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className={cn(
            'w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0',
            'bg-gradient-to-br from-accent-secondary to-accent-primary',
            'shadow-lg shadow-accent-primary/20'
          )}>
            <Zap className="w-5 h-5 text-black" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-bold text-sm text-foreground-primary leading-tight tracking-tight">
                STOCK SUITE
              </span>
              <span className="text-[10px] text-accent-primary font-semibold tracking-wider">
                PRO v10.0 QUANT
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation - Scrollable */}
      <nav className="flex-1 overflow-y-auto py-3 scrollbar-thin">
        {navSections.map(({ title, items }) => (
          <div key={title} className="mb-2">
            {/* Section header */}
            {!collapsed && (
              <button
                onClick={() => toggleSection(title)}
                className={cn(
                  'w-full px-4 py-2 text-[10px] font-bold tracking-widest',
                  'text-foreground-muted/70 hover:text-foreground-muted',
                  'transition-colors flex items-center justify-between'
                )}
              >
                {title}
              </button>
            )}

            {/* Section items */}
            {(collapsed || expandedSections.includes(title)) && (
              <div className={cn('space-y-0.5', !collapsed && 'px-2')}>
                {items.map(({ path, icon: Icon, label }) => (
                  <NavLink
                    key={path}
                    to={path}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-xl',
                        'transition-all duration-200 ease-smooth',
                        'text-foreground-secondary hover:text-foreground-primary',
                        collapsed && 'justify-center px-2',
                        isActive 
                          ? 'bg-gradient-to-r from-accent-primary/15 to-accent-primary/5 text-accent-primary shadow-inner-light' 
                          : 'hover:bg-background-hover/50'
                      )
                    }
                    title={collapsed ? label : undefined}
                  >
                    <Icon className={cn(
                      'w-4 h-4 flex-shrink-0 transition-transform duration-200',
                      'group-hover:scale-110'
                    )} />
                    {!collapsed && <span className="truncate">{label}</span>}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-border/50 p-3 flex-shrink-0">
        <button
          onClick={onToggle}
          className={cn(
            'flex items-center gap-2 px-3 py-2.5 text-xs font-medium rounded-xl w-full',
            'transition-all duration-200 ease-smooth',
            'text-foreground-muted hover:text-foreground-primary',
            'hover:bg-background-hover/50',
            collapsed && 'justify-center px-2'
          )}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
