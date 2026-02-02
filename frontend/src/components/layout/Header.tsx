import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Maximize2, TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/utils/cn'
import { SystemMonitor } from './SystemMonitor'
import { NotificationBell } from '../NotificationSystem'
import { MarketRegimeIndicator } from '../MarketRegimeIndicator'
import { MarketStatusBadge } from '../MarketStatus'
import { KillSwitch } from '../KillSwitch'
import { UserMenu } from '../auth'
import { marketApi, healthApi, MarketTicker as MarketTickerType } from '@/api/client'

// Fallback data when API is not available
const fallbackMarketData = [
  { symbol: 'SPY', price: 688.98, change: 0.52 },
  { symbol: 'QQQ', price: 620.76, change: 0.73 },
  { symbol: 'DIA', price: 493.69, change: 0.59 },
  { symbol: 'IWM', price: 269.79, change: 0.75 },
]

export function Header() {
  const [time, setTime] = useState(new Date())
  const navigate = useNavigate()

  // Fetch health status to get actual data source info
  const { data: healthResponse } = useQuery({
    queryKey: ['health-status'],
    queryFn: () => healthApi.check(),
    refetchInterval: 10000,
    staleTime: 5000,
  })

  // Fetch market tickers via HTTP API with auto-refresh
  const { data: tickersResponse, isSuccess } = useQuery({
    queryKey: ['market-tickers-header'],
    queryFn: () => marketApi.getTickers('SPY,QQQ,DIA,IWM'),
    refetchInterval: 5000,
    staleTime: 3000,
  })

  // Get data status from health endpoint
  const healthData = healthResponse?.ok ? healthResponse.data : null
  const dataStatus = (healthData as any)?.data || { is_live: false, primary_source: 'none', quality_score: 0 }
  const isLiveData = dataStatus.is_live && dataStatus.quality_score >= 0.5
  const dataSource = dataStatus.primary_source || 'offline'

  // Determine connection status based on successful API calls
  const tickersData = tickersResponse?.ok ? tickersResponse.data : null
  const isConnected = isSuccess && tickersData && tickersData.length > 0

  // Use live data if available, otherwise fallback
  const marketData = isConnected
    ? tickersData.slice(0, 4).map((t: MarketTickerType) => ({
        symbol: t.symbol,
        price: t.price,
        change: t.change_pct
      }))
    : fallbackMarketData

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date())
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // Listen for navigation events from Electron menu
  useEffect(() => {
    const electronAPI = window.electronAPI
    if (!electronAPI) return

    const unsubNav = electronAPI.onNavigate((path) => {
      navigate(path)
    })

    const unsubBot = electronAPI.onBotControl((action) => {
      window.dispatchEvent(new CustomEvent('bot-control', { detail: action }))
    })

    return () => {
      unsubNav()
      unsubBot()
    }
  }, [navigate])

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', { hour12: false })
  }

  const formatDate = (date: Date) => {
    return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  }

  return (
    <header className={cn(
      'h-12 flex items-center justify-between px-5',
      'bg-background-secondary/80 backdrop-blur-glass',
      'border-b border-border/50'
    )}>
      {/* Left: Ticker tape */}
      <div className="flex items-center gap-4">
        {marketData.map((ticker, i) => (
          <div key={ticker.symbol} className="flex items-center">
            {i > 0 && <div className="w-px h-4 bg-border mx-3" />}
            <MarketTicker {...ticker} />
          </div>
        ))}
      </div>

      {/* Right: Status, time, actions */}
      <div className="flex items-center gap-5">
        {/* Market Hours Status */}
        <MarketStatusBadge />

        {/* Market Regime Indicator */}
        <MarketRegimeIndicator />

        {/* System Monitor (only shows in Electron) */}
        <SystemMonitor />

        {/* Notifications */}
        <NotificationBell />

        {/* Connection status with data source */}
        <div className="flex items-center gap-2">
          <span className={cn(
            'status-dot',
            isLiveData ? 'online' : isConnected ? 'warning' : 'offline'
          )} />
          <span className={cn(
            'text-xs font-semibold',
            isLiveData ? 'text-bullish' : isConnected ? 'text-warning' : 'text-bearish'
          )}>
            {isLiveData ? 'LIVE' : isConnected ? 'STALE' : 'OFFLINE'}
          </span>
          {isConnected && (
            <span className="text-[10px] text-foreground-muted uppercase tracking-wider">
              {dataSource}
            </span>
          )}
        </div>

        {/* Time */}
        <div className="flex items-center gap-3 px-3 py-1.5 rounded-lg bg-background-tertiary/50">
          <div className="text-sm font-mono">
            <span className="text-foreground-primary font-bold tracking-wide">{formatTime(time)}</span>
          </div>
          <div className="w-px h-4 bg-border" />
          <span className="text-xs text-foreground-muted font-medium">{formatDate(time)}</span>
        </div>

        {/* Fullscreen */}
        <button
          onClick={() => document.documentElement.requestFullscreen?.()}
          className={cn(
            'p-2 rounded-lg transition-all duration-200',
            'hover:bg-background-hover/50 text-foreground-muted hover:text-foreground-primary'
          )}
          title="Fullscreen (F11)"
        >
          <Maximize2 className="w-4 h-4" />
        </button>

        {/* Kill switch */}
        <KillSwitch compact />

        {/* User Menu */}
        <UserMenu />
      </div>
    </header>
  )
}

interface MarketTickerProps {
  symbol: string
  price: number
  change: number
}

function MarketTicker({ symbol, price, change }: MarketTickerProps) {
  const isPositive = change >= 0

  return (
    <div className="flex items-center gap-2 group">
      <span className="text-xs font-bold text-accent-primary tracking-wide group-hover:text-accent-secondary transition-colors">
        {symbol}
      </span>
      <span className="text-sm font-mono text-foreground-primary font-semibold">
        ${price.toFixed(2)}
      </span>
      <span
        className={cn(
          'flex items-center gap-0.5 text-xs font-mono font-semibold px-1.5 py-0.5 rounded',
          isPositive 
            ? 'text-bullish bg-bullish/10' 
            : 'text-bearish bg-bearish/10'
        )}
      >
        {isPositive ? (
          <TrendingUp className="w-3 h-3" />
        ) : (
          <TrendingDown className="w-3 h-3" />
        )}
        {Math.abs(change).toFixed(2)}%
      </span>
    </div>
  )
}
