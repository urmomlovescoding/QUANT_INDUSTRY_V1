/**
 * Enhanced Command Palette (Ctrl+K or /)
 * Quick navigation, fuzzy search, command history, asset quick-jump.
 * "go AAPL" jumps to asset, "risk" shows risk panel, "pnl today" shows daily PnL.
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { createPortal } from 'react-dom'
import {
  Search,
  LayoutDashboard,
  Brain,
  Activity,
  Waves,
  Shield,
  Settings,
  Moon,
  Zap,
  Play,
  Pause,
  RefreshCw,
  Download,
  Upload,
  Keyboard,
  ChevronRight,
  Command,
  Layers,
  Target,
  Building,
  Briefcase,
  LineChart,
  FlaskConical,
  Bot,
  Timer,
  Cpu,
  TrendingUp,
  Gauge,
  Newspaper,
  Calendar,
  X,
  Clock,
  Bell,
  LayoutGrid,
  ArrowRight,
  Hash,
} from 'lucide-react'
import { cn } from '@/utils/cn'

interface CommandItem {
  id: string
  title: string
  subtitle?: string
  icon: React.ComponentType<{ className?: string }>
  category: 'navigation' | 'action' | 'setting' | 'ai' | 'quick' | 'recent'
  shortcut?: string
  keywords?: string[]
  action: () => void
}

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
}

// Simple fuzzy scoring: matches characters in order, rewards consecutive matches
function fuzzyScore(query: string, target: string): number {
  const q = query.toLowerCase()
  const t = target.toLowerCase()

  if (t.includes(q)) return 100 + (q.length / t.length) * 50
  if (t.startsWith(q)) return 200

  let score = 0
  let qi = 0
  let consecutive = 0
  let lastMatch = -2

  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      score += 10
      if (ti === lastMatch + 1) {
        consecutive++
        score += consecutive * 5
      } else {
        consecutive = 0
      }
      if (ti === 0) score += 15
      lastMatch = ti
      qi++
    }
  }

  return qi === q.length ? score : 0
}

// Command history
const HISTORY_KEY = 'quant-command-history'
const MAX_HISTORY = 10

function getHistory(): string[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
  } catch { return [] }
}

function addToHistory(id: string) {
  const history = getHistory().filter(h => h !== id)
  history.unshift(id)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)))
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const [search, setSearch] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [searchHistory] = useState<string[]>(() => getHistory())
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  // Quick-action: detect "go SYMBOL" pattern
  const quickAssetMatch = search.match(/^go\s+([A-Za-z]{1,5})$/i)
  const quickAssetSymbol = quickAssetMatch?.[1]?.toUpperCase()

  // Define all commands
  const commands: CommandItem[] = useMemo(() => [
    // Quick Actions (contextual based on search)
    ...(quickAssetSymbol ? [{
      id: `quick-go-${quickAssetSymbol}`,
      title: `Jump to ${quickAssetSymbol}`,
      subtitle: `View ${quickAssetSymbol} chart and analysis`,
      icon: ArrowRight,
      category: 'quick' as const,
      action: () => navigate(`/charts?symbol=${quickAssetSymbol}`),
    }] : []),

    // Navigation - Markets
    { id: 'nav-dashboard', title: 'Dashboard', subtitle: 'Market overview', icon: LayoutDashboard, category: 'navigation', keywords: ['home', 'main', 'overview'], action: () => navigate('/dashboard') },
    { id: 'nav-charts', title: 'Charts', subtitle: 'Technical analysis', icon: LineChart, category: 'navigation', keywords: ['chart', 'candle', 'technical'], action: () => navigate('/charts') },
    { id: 'nav-screener', title: 'Screener', subtitle: 'Stock screening', icon: Search, category: 'navigation', keywords: ['scan', 'filter', 'screen'], action: () => navigate('/screener') },
    { id: 'nav-command-center', title: 'Command Center', subtitle: 'Trading panels & signal feed', icon: LayoutGrid, category: 'navigation', keywords: ['panels', 'trading', 'center', 'layout'], action: () => navigate('/command-center') },

    // Navigation - Options
    { id: 'nav-options', title: 'Options Lab', subtitle: 'Options analysis', icon: FlaskConical, category: 'navigation', keywords: ['options', 'puts', 'calls'], action: () => navigate('/options-lab') },
    { id: 'nav-gex', title: 'GEX Analysis', subtitle: 'Gamma exposure', icon: Activity, category: 'navigation', keywords: ['gamma', 'gex', 'exposure'], action: () => navigate('/gex-analysis') },
    { id: 'nav-flow', title: 'Flow Scanner', subtitle: 'Smart money flow', icon: Waves, category: 'navigation', keywords: ['flow', 'smart money', 'unusual'], action: () => navigate('/flow-scanner') },
    { id: 'nav-strategies', title: 'Strategies', subtitle: 'Option strategies', icon: Target, category: 'navigation', keywords: ['strategy', 'spread', 'iron condor'], action: () => navigate('/strategies') },

    // Navigation - Neural AI
    { id: 'nav-unified', title: 'Unified Brain', subtitle: '53+ AI strategies', icon: Layers, category: 'navigation', shortcut: 'U', keywords: ['brain', 'ai', 'unified', 'ml'], action: () => navigate('/unified-brain') },
    { id: 'nav-neural', title: 'Neural Analysis', subtitle: 'Deep learning', icon: Brain, category: 'navigation', keywords: ['neural', 'deep learning', 'ai'], action: () => navigate('/neural-analysis') },
    { id: 'nav-ml', title: 'ML Predictions', subtitle: 'Machine learning', icon: TrendingUp, category: 'navigation', keywords: ['prediction', 'forecast', 'ml'], action: () => navigate('/ml-predictions') },
    { id: 'nav-regime', title: 'Regime Detect', subtitle: 'Market regime', icon: Gauge, category: 'navigation', keywords: ['regime', 'volatility', 'trend'], action: () => navigate('/regime-detect') },
    { id: 'nav-trading', title: 'Trading Brain', subtitle: 'Cycle analysis', icon: Cpu, category: 'navigation', keywords: ['trading', 'cycle', 'brain'], action: () => navigate('/trading-brain') },
    { id: 'nav-algobot', title: 'Algo Bot', subtitle: 'Automated trading', icon: Bot, category: 'navigation', keywords: ['algo', 'bot', 'automated'], action: () => navigate('/algo-bot') },
    { id: 'nav-ml-training', title: 'ML Training', subtitle: 'Model training', icon: Brain, category: 'navigation', keywords: ['training', 'model', 'learn'], action: () => navigate('/ml-training') },

    // Navigation - Prop Firm
    { id: 'nav-tpt', title: 'TPT Dashboard', subtitle: 'Prop firm tracking', icon: Building, category: 'navigation', keywords: ['prop', 'firm', 'tpt'], action: () => navigate('/tpt-dashboard') },
    { id: 'nav-futures', title: 'Futures Brain', subtitle: 'Futures AI', icon: Activity, category: 'navigation', keywords: ['futures', 'es', 'nq'], action: () => navigate('/futures-brain') },

    // Navigation - Analytics
    { id: 'nav-backtest', title: 'Backtesting', subtitle: 'Strategy testing', icon: Timer, category: 'navigation', keywords: ['backtest', 'historical', 'test'], action: () => navigate('/backtesting') },
    { id: 'nav-risk', title: 'Risk Engine', subtitle: 'Risk management', icon: Shield, category: 'navigation', keywords: ['risk', 'exposure', 'drawdown'], action: () => navigate('/risk-engine') },
    { id: 'nav-monte', title: 'Monte Carlo', subtitle: 'Simulation analysis', icon: Activity, category: 'navigation', keywords: ['monte', 'carlo', 'simulation'], action: () => navigate('/monte-carlo') },
    { id: 'nav-correlation', title: 'Correlation', subtitle: 'Asset correlation', icon: Activity, category: 'navigation', keywords: ['correlation', 'matrix'], action: () => navigate('/correlation') },

    // Navigation - Portfolio
    { id: 'nav-portfolio', title: 'Portfolio', subtitle: 'Holdings & P&L', icon: Briefcase, category: 'navigation', keywords: ['portfolio', 'holdings', 'pnl', 'profit', 'loss'], action: () => navigate('/portfolio') },
    { id: 'nav-pairs', title: 'Pairs Trading', subtitle: 'Pairs analysis', icon: Activity, category: 'navigation', keywords: ['pairs', 'cointegration'], action: () => navigate('/pairs-trading') },
    { id: 'nav-reports', title: 'Reports', subtitle: 'Performance reports', icon: Newspaper, category: 'navigation', keywords: ['report', 'performance', 'summary'], action: () => navigate('/reports') },

    // Navigation - Research
    { id: 'nav-darkpool', title: 'Dark Pool', subtitle: 'Institutional flow', icon: Moon, category: 'navigation', keywords: ['dark pool', 'institutional'], action: () => navigate('/dark-pool') },
    { id: 'nav-news', title: 'News Center', subtitle: 'Market news', icon: Newspaper, category: 'navigation', keywords: ['news', 'headlines', 'sentiment'], action: () => navigate('/news') },
    { id: 'nav-earnings', title: 'Earnings', subtitle: 'Earnings calendar', icon: Calendar, category: 'navigation', keywords: ['earnings', 'calendar', 'report'], action: () => navigate('/earnings') },
    { id: 'nav-13f', title: '13F Holdings', subtitle: 'Institutional holdings', icon: Building, category: 'navigation', keywords: ['13f', 'institutional', 'holdings'], action: () => navigate('/13f-holdings') },
    { id: 'nav-sec', title: 'SEC Filings', subtitle: 'SEC documents', icon: Newspaper, category: 'navigation', keywords: ['sec', 'filing', 'document'], action: () => navigate('/sec-filings') },

    // Navigation - System
    { id: 'nav-settings', title: 'Settings', subtitle: 'App configuration', icon: Settings, category: 'navigation', shortcut: ',', keywords: ['settings', 'config', 'preferences'], action: () => navigate('/settings') },
    { id: 'nav-api', title: 'API Connector', subtitle: 'API connections', icon: Zap, category: 'navigation', keywords: ['api', 'connect', 'key'], action: () => navigate('/api-connector') },

    // AI Actions
    { id: 'ai-start', title: 'Start AI Brain', subtitle: 'Activate all strategies', icon: Play, category: 'ai', shortcut: 'S', keywords: ['start', 'activate', 'run'], action: () => window.dispatchEvent(new CustomEvent('brain-control', { detail: 'start' })) },
    { id: 'ai-stop', title: 'Stop AI Brain', subtitle: 'Pause all strategies', icon: Pause, category: 'ai', shortcut: 'P', keywords: ['stop', 'pause', 'halt'], action: () => window.dispatchEvent(new CustomEvent('brain-control', { detail: 'stop' })) },
    { id: 'ai-refresh', title: 'Refresh Signals', subtitle: 'Force signal update', icon: RefreshCw, category: 'ai', shortcut: 'R', keywords: ['refresh', 'update', 'reload'], action: () => window.dispatchEvent(new CustomEvent('brain-control', { detail: 'refresh' })) },

    // Actions
    { id: 'action-alerts', title: 'Manage Alerts', subtitle: 'Create and manage custom alerts', icon: Bell, category: 'action', shortcut: 'A', keywords: ['alert', 'notification', 'alarm'], action: () => window.dispatchEvent(new CustomEvent('open-alert-manager')) },
    { id: 'action-export', title: 'Export Data', subtitle: 'Download CSV/JSON', icon: Download, category: 'action', keywords: ['export', 'download', 'csv'], action: () => window.dispatchEvent(new CustomEvent('export-data')) },
    { id: 'action-import', title: 'Import Data', subtitle: 'Load configuration', icon: Upload, category: 'action', keywords: ['import', 'upload', 'load'], action: () => window.dispatchEvent(new CustomEvent('import-data')) },
    { id: 'action-fullscreen', title: 'Toggle Fullscreen', subtitle: 'F11', icon: LayoutDashboard, category: 'action', shortcut: 'F', keywords: ['fullscreen', 'maximize'], action: () => {
      if (document.fullscreenElement) {
        document.exitFullscreen()
      } else {
        document.documentElement.requestFullscreen()
      }
    }},
    { id: 'action-quick-trade', title: 'Quick Trade', subtitle: 'Open quick trade dialog', icon: Zap, category: 'action', shortcut: 'T', keywords: ['trade', 'buy', 'sell', 'order'], action: () => window.dispatchEvent(new CustomEvent('open-quick-trade')) },

    // Settings
    { id: 'setting-theme', title: 'Toggle Dark Mode', subtitle: 'Switch theme', icon: Moon, category: 'setting', shortcut: 'D', keywords: ['theme', 'dark', 'light'], action: () => window.dispatchEvent(new CustomEvent('toggle-theme')) },
    { id: 'setting-shortcuts', title: 'Keyboard Shortcuts', subtitle: 'View all shortcuts', icon: Keyboard, category: 'setting', shortcut: '?', keywords: ['keyboard', 'shortcuts', 'hotkey'], action: () => window.dispatchEvent(new CustomEvent('show-shortcuts')) },
  ], [navigate, quickAssetSymbol])

  // Filter and score commands with fuzzy matching
  const filteredCommands = useMemo(() => {
    if (!search.trim()) {
      // Show recent commands first, then all commands
      const history = getHistory()
      const recentCommands = history
        .map(id => commands.find(c => c.id === id))
        .filter(Boolean)
        .map(cmd => ({ ...cmd!, category: 'recent' as const }))
        .slice(0, 3)

      if (recentCommands.length > 0) {
        const recentIds = new Set(recentCommands.map(c => c.id))
        return [...recentCommands, ...commands.filter(c => !recentIds.has(c.id))]
      }
      return commands
    }

    const searchLower = search.toLowerCase().trim()

    // Check for special prefixes
    if (searchLower.startsWith('go ')) {
      return commands.filter(c => c.category === 'quick')
    }

    // Score each command
    const scored = commands.map(cmd => {
      const titleScore = fuzzyScore(searchLower, cmd.title)
      const subtitleScore = cmd.subtitle ? fuzzyScore(searchLower, cmd.subtitle) * 0.7 : 0
      const keywordScore = cmd.keywords
        ? Math.max(...cmd.keywords.map(k => fuzzyScore(searchLower, k))) * 0.8
        : 0
      const categoryScore = fuzzyScore(searchLower, cmd.category) * 0.3
      const bestScore = Math.max(titleScore, subtitleScore, keywordScore, categoryScore)

      return { cmd, score: bestScore }
    })

    return scored
      .filter(s => s.score > 0)
      .sort((a, b) => b.score - a.score)
      .map(s => s.cmd)
  }, [commands, search])

  // Group commands by category
  const groupedCommands = useMemo(() => {
    const groups: Record<string, CommandItem[]> = {
      quick: [],
      recent: [],
      navigation: [],
      ai: [],
      action: [],
      setting: [],
    }

    filteredCommands.forEach(cmd => {
      if (groups[cmd.category]) {
        groups[cmd.category].push(cmd)
      }
    })

    return groups
  }, [filteredCommands])

  // Reset selection when search changes
  useEffect(() => {
    setSelectedIndex(0)
  }, [search])

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setSearch('')
      setSelectedIndex(0)
      setHistoryIndex(-1)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, filteredCommands.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        if (selectedIndex === 0 && !search) {
          // Navigate command history
          const history = getHistory()
          if (history.length > 0) {
            const nextIdx = Math.min(historyIndex + 1, history.length - 1)
            setHistoryIndex(nextIdx)
            const cmd = commands.find(c => c.id === history[nextIdx])
            if (cmd) setSearch(cmd.title)
          }
        } else {
          setSelectedIndex(i => Math.max(i - 1, 0))
        }
        break
      case 'Enter':
        e.preventDefault()
        if (filteredCommands[selectedIndex]) {
          const cmd = filteredCommands[selectedIndex]
          addToHistory(cmd.id)
          cmd.action()
          onClose()
        }
        break
      case 'Escape':
        onClose()
        break
      case 'Tab':
        e.preventDefault()
        // Tab to autocomplete first suggestion
        if (filteredCommands[0]) {
          setSearch(filteredCommands[0].title)
        }
        break
    }
  }, [filteredCommands, selectedIndex, onClose, search, historyIndex, commands])

  // Scroll selected item into view
  useEffect(() => {
    const selectedElement = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`)
    selectedElement?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  if (!isOpen) return null

  const categoryLabels: Record<string, string> = {
    quick: 'Quick Actions',
    recent: 'Recent',
    navigation: 'Navigation',
    ai: 'AI Control',
    action: 'Actions',
    setting: 'Settings',
  }

  const categoryIcons: Record<string, React.ComponentType<{ className?: string }>> = {
    quick: ArrowRight,
    recent: Clock,
    navigation: Hash,
    ai: Brain,
    action: Zap,
    setting: Settings,
  }

  let currentIndex = 0

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Palette */}
      <div className="relative w-full max-w-xl bg-background-secondary border border-border rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
          <Search className="w-5 h-5 text-foreground-muted flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setHistoryIndex(-1) }}
            onKeyDown={handleKeyDown}
            placeholder='Type a command... (try "go AAPL" or "risk")'
            className="flex-1 bg-transparent text-foreground-primary placeholder-foreground-muted outline-none text-sm"
          />
          <kbd className="px-2 py-0.5 text-xs text-foreground-muted bg-background-tertiary rounded flex-shrink-0">
            ESC
          </kbd>
        </div>

        {/* Quick hints when empty */}
        {!search && (
          <div className="flex items-center gap-3 px-4 py-1.5 bg-background-tertiary/30 border-b border-border text-[10px] text-foreground-muted">
            <span><kbd className="px-1 bg-background-tertiary rounded">go AAPL</kbd> jump to asset</span>
            <span><kbd className="px-1 bg-background-tertiary rounded">risk</kbd> risk panel</span>
            <span><kbd className="px-1 bg-background-tertiary rounded">pnl</kbd> portfolio</span>
            <span><kbd className="px-1 bg-background-tertiary rounded">Tab</kbd> autocomplete</span>
          </div>
        )}

        {/* Command List */}
        <div ref={listRef} className="max-h-[420px] overflow-y-auto p-2">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-foreground-muted">
              <Search className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No commands found for "{search}"</p>
              <p className="text-xs mt-1">Try "go AAPL" to jump to a symbol</p>
            </div>
          ) : (
            Object.entries(groupedCommands).map(([category, items]) => {
              if (items.length === 0) return null
              const CategoryIcon = categoryIcons[category] || Hash

              return (
                <div key={category} className="mb-2">
                  <div className="flex items-center gap-1 px-2 py-1">
                    <CategoryIcon className="w-3 h-3 text-foreground-muted" />
                    <span className="text-[10px] font-bold text-foreground-muted uppercase tracking-wider">
                      {categoryLabels[category]}
                    </span>
                    <span className="text-[9px] text-foreground-muted/50">({items.length})</span>
                  </div>
                  {items.map((cmd) => {
                    const index = currentIndex++
                    const isSelected = index === selectedIndex
                    const Icon = cmd.icon

                    return (
                      <button
                        key={`${cmd.id}-${category}`}
                        data-index={index}
                        onClick={() => {
                          addToHistory(cmd.id)
                          cmd.action()
                          onClose()
                        }}
                        onMouseEnter={() => setSelectedIndex(index)}
                        className={cn(
                          'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors',
                          isSelected
                            ? 'bg-accent-primary/20 text-accent-primary'
                            : 'text-foreground-secondary hover:bg-background-tertiary'
                        )}
                      >
                        <Icon className={cn(
                          'w-4 h-4 flex-shrink-0',
                          isSelected ? 'text-accent-primary' : 'text-foreground-muted'
                        )} />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">
                            {cmd.title}
                            {cmd.category === 'recent' && (
                              <span className="text-[9px] text-foreground-muted ml-2">recent</span>
                            )}
                          </div>
                          {cmd.subtitle && (
                            <div className="text-xs text-foreground-muted truncate">{cmd.subtitle}</div>
                          )}
                        </div>
                        {cmd.shortcut && (
                          <kbd className={cn(
                            'px-1.5 py-0.5 text-[10px] rounded flex-shrink-0',
                            isSelected
                              ? 'bg-accent-primary/30 text-accent-primary'
                              : 'bg-background-tertiary text-foreground-muted'
                          )}>
                            {cmd.shortcut}
                          </kbd>
                        )}
                        <ChevronRight className={cn(
                          'w-4 h-4 flex-shrink-0',
                          isSelected ? 'text-accent-primary' : 'text-foreground-muted/50'
                        )} />
                      </button>
                    )
                  })}
                </div>
              )
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-border bg-background-tertiary/50 text-xs text-foreground-muted">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <kbd className="px-1 bg-background-tertiary rounded">↑↓</kbd> navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1 bg-background-tertiary rounded">↵</kbd> select
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1 bg-background-tertiary rounded">Tab</kbd> complete
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1 bg-background-tertiary rounded">esc</kbd> close
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Command className="w-3 h-3" />
            <span>K</span>
            <span className="mx-1 text-foreground-muted/50">|</span>
            <span>/</span>
          </div>
        </div>
      </div>
    </div>,
    document.body
  )
}

/**
 * Hook to manage command palette state and keyboard shortcut
 * Supports Ctrl+K, Cmd+K, and "/" to open
 */
export function useCommandPalette() {
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+K or Cmd+K to open
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setIsOpen(prev => !prev)
        return
      }

      // "/" to open (when not focused on an input)
      if (e.key === '/' && !isOpen) {
        const target = e.target as HTMLElement
        const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
        if (!isInput) {
          e.preventDefault()
          setIsOpen(true)
        }
      }

      // Ctrl+Shift+A for alert manager
      if (e.ctrlKey && e.shiftKey && e.key === 'A') {
        e.preventDefault()
        window.dispatchEvent(new CustomEvent('open-alert-manager'))
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])

  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
    toggle: () => setIsOpen(prev => !prev)
  }
}
