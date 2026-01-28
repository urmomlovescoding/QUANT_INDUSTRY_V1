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
      { path: '/monte-carlo', icon: Dice5, label: 'Monte Carlo' },
      { path: '/correlation', icon: GitBranch, label: 'Correlation' },
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
        'flex flex-col bg-background-secondary border-r border-border transition-all duration-300 overflow-hidden',
        collapsed ? 'w-16' : 'w-52'
      )}
    >
      {/* Logo */}
      <div className="h-14 flex items-center px-3 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-accent-primary flex items-center justify-center flex-shrink-0">
            <Zap className="w-5 h-5 text-background-primary" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-bold text-sm text-foreground-primary leading-tight">
                STOCK SUITE
              </span>
              <span className="text-[10px] text-accent-primary font-medium">
                PRO v10.0 QUANT
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation - Scrollable */}
      <nav className="flex-1 overflow-y-auto py-2 scrollbar-thin">
        {navSections.map(({ title, items }) => (
          <div key={title} className="mb-1">
            {/* Section header */}
            {!collapsed && (
              <button
                onClick={() => toggleSection(title)}
                className="w-full px-3 py-1.5 text-[10px] font-bold text-accent-primary tracking-wider hover:bg-background-tertiary/50 flex items-center justify-between"
              >
                {title}
              </button>
            )}

            {/* Section items */}
            {(collapsed || expandedSections.includes(title)) && (
              <div className={cn('space-y-0.5', !collapsed && 'px-1')}>
                {items.map(({ path, icon: Icon, label }) => (
                  <NavLink
                    key={path}
                    to={path}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded transition-colors',
                        'text-foreground-secondary hover:text-foreground-primary hover:bg-background-tertiary',
                        collapsed && 'justify-center px-2',
                        isActive && 'bg-accent-primary/10 text-accent-primary border-l-2 border-accent-primary'
                      )
                    }
                    title={collapsed ? label : undefined}
                  >
                    <Icon className="w-4 h-4 flex-shrink-0" />
                    {!collapsed && <span className="truncate">{label}</span>}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-border p-2 flex-shrink-0">
        <button
          onClick={onToggle}
          className={cn(
            'flex items-center gap-2 px-3 py-2 text-xs font-medium rounded w-full transition-colors',
            'text-foreground-secondary hover:text-foreground-primary hover:bg-background-tertiary',
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
