/**
 * Command Palette (Ctrl+K)
 * Quick navigation and action execution
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
  Sun,
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
  FileText,
  Newspaper,
  Calendar,
  X,
} from 'lucide-react'
import { cn } from '@/utils/cn'

interface CommandItem {
  id: string
  title: string
  subtitle?: string
  icon: React.ComponentType<{ className?: string }>
  category: 'navigation' | 'action' | 'setting' | 'ai'
  shortcut?: string
  action: () => void
}

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const [search, setSearch] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  // Define all commands
  const commands: CommandItem[] = useMemo(() => [
    // Navigation - Markets
    { id: 'nav-dashboard', title: 'Go to Dashboard', subtitle: 'Market overview', icon: LayoutDashboard, category: 'navigation', action: () => navigate('/dashboard') },
    { id: 'nav-charts', title: 'Go to Charts', subtitle: 'Technical analysis', icon: LineChart, category: 'navigation', action: () => navigate('/charts') },
    { id: 'nav-screener', title: 'Go to Screener', subtitle: 'Stock screening', icon: Search, category: 'navigation', action: () => navigate('/screener') },

    // Navigation - Options
    { id: 'nav-options', title: 'Go to Options Lab', subtitle: 'Options analysis', icon: FlaskConical, category: 'navigation', action: () => navigate('/options-lab') },
    { id: 'nav-gex', title: 'Go to GEX Analysis', subtitle: 'Gamma exposure', icon: Activity, category: 'navigation', action: () => navigate('/gex-analysis') },
    { id: 'nav-flow', title: 'Go to Flow Scanner', subtitle: 'Smart money flow', icon: Waves, category: 'navigation', action: () => navigate('/flow-scanner') },
    { id: 'nav-strategies', title: 'Go to Strategies', subtitle: 'Option strategies', icon: Target, category: 'navigation', action: () => navigate('/strategies') },

    // Navigation - Neural AI
    { id: 'nav-unified', title: 'Go to Unified Brain', subtitle: '53+ AI strategies', icon: Layers, category: 'navigation', shortcut: 'U', action: () => navigate('/unified-brain') },
    { id: 'nav-neural', title: 'Go to Neural Analysis', subtitle: 'Deep learning', icon: Brain, category: 'navigation', action: () => navigate('/neural-analysis') },
    { id: 'nav-ml', title: 'Go to ML Predictions', subtitle: 'Machine learning', icon: TrendingUp, category: 'navigation', action: () => navigate('/ml-predictions') },
    { id: 'nav-regime', title: 'Go to Regime Detect', subtitle: 'Market regime', icon: Gauge, category: 'navigation', action: () => navigate('/regime-detect') },
    { id: 'nav-trading', title: 'Go to Trading Brain', subtitle: 'Cycle analysis', icon: Cpu, category: 'navigation', action: () => navigate('/trading-brain') },
    { id: 'nav-algobot', title: 'Go to Algo Bot', subtitle: 'Automated trading', icon: Bot, category: 'navigation', action: () => navigate('/algo-bot') },

    // Navigation - Prop Firm
    { id: 'nav-tpt', title: 'Go to TPT Dashboard', subtitle: 'Prop firm tracking', icon: Building, category: 'navigation', action: () => navigate('/tpt-dashboard') },
    { id: 'nav-futures', title: 'Go to Futures Brain', subtitle: 'Futures AI', icon: Activity, category: 'navigation', action: () => navigate('/futures-brain') },

    // Navigation - Analytics
    { id: 'nav-backtest', title: 'Go to Backtesting', subtitle: 'Strategy testing', icon: Timer, category: 'navigation', action: () => navigate('/backtesting') },
    { id: 'nav-risk', title: 'Go to Risk Engine', subtitle: 'Risk management', icon: Shield, category: 'navigation', action: () => navigate('/risk-engine') },

    // Navigation - Portfolio
    { id: 'nav-portfolio', title: 'Go to Portfolio', subtitle: 'Holdings & P&L', icon: Briefcase, category: 'navigation', action: () => navigate('/portfolio') },

    // Navigation - Research
    { id: 'nav-darkpool', title: 'Go to Dark Pool', subtitle: 'Institutional flow', icon: Moon, category: 'navigation', action: () => navigate('/dark-pool') },
    { id: 'nav-news', title: 'Go to News Center', subtitle: 'Market news', icon: Newspaper, category: 'navigation', action: () => navigate('/news') },
    { id: 'nav-earnings', title: 'Go to Earnings', subtitle: 'Earnings calendar', icon: Calendar, category: 'navigation', action: () => navigate('/earnings') },

    // Navigation - System
    { id: 'nav-settings', title: 'Go to Settings', subtitle: 'App configuration', icon: Settings, category: 'navigation', shortcut: ',', action: () => navigate('/settings') },
    { id: 'nav-api', title: 'Go to API Connector', subtitle: 'API connections', icon: Zap, category: 'navigation', action: () => navigate('/api-connector') },

    // AI Actions
    { id: 'ai-start', title: 'Start AI Brain', subtitle: 'Activate all strategies', icon: Play, category: 'ai', shortcut: 'S', action: () => window.dispatchEvent(new CustomEvent('brain-control', { detail: 'start' })) },
    { id: 'ai-stop', title: 'Stop AI Brain', subtitle: 'Pause all strategies', icon: Pause, category: 'ai', shortcut: 'P', action: () => window.dispatchEvent(new CustomEvent('brain-control', { detail: 'stop' })) },
    { id: 'ai-refresh', title: 'Refresh Signals', subtitle: 'Force signal update', icon: RefreshCw, category: 'ai', shortcut: 'R', action: () => window.dispatchEvent(new CustomEvent('brain-control', { detail: 'refresh' })) },

    // Actions
    { id: 'action-export', title: 'Export Data', subtitle: 'Download CSV/JSON', icon: Download, category: 'action', action: () => window.dispatchEvent(new CustomEvent('export-data')) },
    { id: 'action-import', title: 'Import Data', subtitle: 'Load configuration', icon: Upload, category: 'action', action: () => window.dispatchEvent(new CustomEvent('import-data')) },
    { id: 'action-fullscreen', title: 'Toggle Fullscreen', subtitle: 'F11', icon: LayoutDashboard, category: 'action', shortcut: 'F', action: () => {
      if (document.fullscreenElement) {
        document.exitFullscreen()
      } else {
        document.documentElement.requestFullscreen()
      }
    }},

    // Settings
    { id: 'setting-theme', title: 'Toggle Dark Mode', subtitle: 'Switch theme', icon: Moon, category: 'setting', shortcut: 'D', action: () => window.dispatchEvent(new CustomEvent('toggle-theme')) },
    { id: 'setting-shortcuts', title: 'Keyboard Shortcuts', subtitle: 'View all shortcuts', icon: Keyboard, category: 'setting', shortcut: '?', action: () => window.dispatchEvent(new CustomEvent('show-shortcuts')) },
  ], [navigate])

  // Filter commands based on search
  const filteredCommands = useMemo(() => {
    if (!search.trim()) return commands

    const searchLower = search.toLowerCase()
    return commands.filter(cmd =>
      cmd.title.toLowerCase().includes(searchLower) ||
      cmd.subtitle?.toLowerCase().includes(searchLower) ||
      cmd.category.toLowerCase().includes(searchLower)
    )
  }, [commands, search])

  // Group commands by category
  const groupedCommands = useMemo(() => {
    const groups: Record<string, CommandItem[]> = {
      navigation: [],
      ai: [],
      action: [],
      setting: []
    }

    filteredCommands.forEach(cmd => {
      groups[cmd.category].push(cmd)
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
        setSelectedIndex(i => Math.max(i - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        if (filteredCommands[selectedIndex]) {
          filteredCommands[selectedIndex].action()
          onClose()
        }
        break
      case 'Escape':
        onClose()
        break
    }
  }, [filteredCommands, selectedIndex, onClose])

  // Scroll selected item into view
  useEffect(() => {
    const selectedElement = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`)
    selectedElement?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  if (!isOpen) return null

  const categoryLabels: Record<string, string> = {
    navigation: 'Navigation',
    ai: 'AI Control',
    action: 'Actions',
    setting: 'Settings'
  }

  let currentIndex = 0

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Palette */}
      <div className="relative w-full max-w-xl bg-background-secondary border border-border rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
          <Search className="w-5 h-5 text-foreground-muted" />
          <input
            ref={inputRef}
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            className="flex-1 bg-transparent text-foreground-primary placeholder-foreground-muted outline-none text-sm"
          />
          <kbd className="px-2 py-0.5 text-xs text-foreground-muted bg-background-tertiary rounded">
            ESC
          </kbd>
        </div>

        {/* Command List */}
        <div ref={listRef} className="max-h-[400px] overflow-y-auto p-2">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-foreground-muted text-sm">
              No commands found
            </div>
          ) : (
            Object.entries(groupedCommands).map(([category, items]) => {
              if (items.length === 0) return null

              return (
                <div key={category} className="mb-2">
                  <div className="px-2 py-1 text-[10px] font-bold text-foreground-muted uppercase tracking-wider">
                    {categoryLabels[category]}
                  </div>
                  {items.map((cmd) => {
                    const index = currentIndex++
                    const isSelected = index === selectedIndex
                    const Icon = cmd.icon

                    return (
                      <button
                        key={cmd.id}
                        data-index={index}
                        onClick={() => {
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
                          'w-4 h-4',
                          isSelected ? 'text-accent-primary' : 'text-foreground-muted'
                        )} />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{cmd.title}</div>
                          {cmd.subtitle && (
                            <div className="text-xs text-foreground-muted truncate">{cmd.subtitle}</div>
                          )}
                        </div>
                        {cmd.shortcut && (
                          <kbd className={cn(
                            'px-1.5 py-0.5 text-[10px] rounded',
                            isSelected
                              ? 'bg-accent-primary/30 text-accent-primary'
                              : 'bg-background-tertiary text-foreground-muted'
                          )}>
                            {cmd.shortcut}
                          </kbd>
                        )}
                        <ChevronRight className={cn(
                          'w-4 h-4',
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
              <kbd className="px-1 bg-background-tertiary rounded">esc</kbd> close
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Command className="w-3 h-3" />
            <span>K</span>
          </div>
        </div>
      </div>
    </div>,
    document.body
  )
}

/**
 * Hook to manage command palette state and keyboard shortcut
 */
export function useCommandPalette() {
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+K or Cmd+K to open
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setIsOpen(prev => !prev)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
    toggle: () => setIsOpen(prev => !prev)
  }
}
