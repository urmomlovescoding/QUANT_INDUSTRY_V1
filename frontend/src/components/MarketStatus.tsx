/**
 * Market Status Component
 * 
 * Migrated to use apiV2 client for type-safe API calls.
 */

import { useState, useEffect, useCallback } from 'react'
import { Clock, Sun, Moon, Coffee, AlertTriangle } from 'lucide-react'
// V2 API Client
import { apiV2 } from '@/api/v2'

interface MarketStatusData {
  session: string
  is_open: boolean
  is_pre_market: boolean
  is_after_hours: boolean
  is_weekend: boolean
  is_holiday: boolean
  current_time_et: string
  reason: string
  next_open?: string
  next_close?: string
  time_until_open?: string
  time_until_close?: string
}

export function MarketStatus() {
  const [status, setStatus] = useState<MarketStatusData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      // V2: apiV2.market.getStatus() instead of raw fetch
      const response = await apiV2.market.getStatus()
      if (response.ok && response.data) {
        setStatus(response.data as unknown as MarketStatusData)
        setError(null)
        return
      }

      // Fallback to health endpoint which includes market info
      const healthResponse = await apiV2.health.check()
      if (healthResponse.ok && healthResponse.data?.market) {
        setStatus(healthResponse.data.market as unknown as MarketStatusData)
        setError(null)
        return
      }

      setError('Failed to fetch market status')
    } catch (e) {
      setError('Connection error')
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    // Refresh every 30 seconds
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  if (error) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 bg-red-500/20 rounded-lg">
        <AlertTriangle className="w-4 h-4 text-red-400" />
        <span className="text-xs text-red-400">{error}</span>
      </div>
    )
  }

  if (!status) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 bg-background-tertiary rounded-lg animate-pulse">
        <Clock className="w-4 h-4 text-foreground-muted" />
        <span className="text-xs text-foreground-muted">Loading...</span>
      </div>
    )
  }

  const getSessionIcon = () => {
    if (status.is_open) return <Sun className="w-4 h-4 text-green-400" />
    if (status.is_pre_market) return <Coffee className="w-4 h-4 text-amber-400" />
    if (status.is_after_hours) return <Moon className="w-4 h-4 text-purple-400" />
    return <Clock className="w-4 h-4 text-slate-400" />
  }

  const getSessionColor = () => {
    if (status.is_open) return 'bg-green-500/20 border-green-500/30 text-green-400'
    if (status.is_pre_market) return 'bg-amber-500/20 border-amber-500/30 text-amber-400'
    if (status.is_after_hours) return 'bg-purple-500/20 border-purple-500/30 text-purple-400'
    return 'bg-slate-500/20 border-slate-500/30 text-slate-400'
  }

  const getSessionLabel = () => {
    if (status.is_open) return 'MARKET OPEN'
    if (status.is_pre_market) return 'PRE-MARKET'
    if (status.is_after_hours) return 'AFTER-HOURS'
    if (status.is_weekend) return 'WEEKEND'
    if (status.is_holiday) return 'HOLIDAY'
    return 'MARKET CLOSED'
  }

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${getSessionColor()}`}>
      {getSessionIcon()}
      <div className="flex flex-col">
        <span className="text-xs font-semibold">{getSessionLabel()}</span>
        {status.time_until_close && status.is_open && (
          <span className="text-[10px] opacity-75">Closes in {status.time_until_close}</span>
        )}
        {status.time_until_open && status.is_pre_market && (
          <span className="text-[10px] opacity-75">Opens in {status.time_until_open}</span>
        )}
        {status.next_open && !status.is_open && !status.is_pre_market && !status.is_after_hours && (
          <span className="text-[10px] opacity-75">Next: {status.next_open.split(' ')[0]}</span>
        )}
      </div>
    </div>
  )
}

// Compact version for headers - styled as a badge with color coding
export function MarketStatusBadge() {
  const [status, setStatus] = useState<MarketStatusData | null>(null)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        // Try dedicated endpoint first, fall back to health endpoint
        let res = await fetch('/api/market/status')
        if (res.ok) {
          const data = await res.json()
          setStatus(data)
          return
        }

        // Fallback to health endpoint
        res = await fetch('/api/health')
        if (res.ok) {
          const health = await res.json()
          if (health.market) {
            setStatus(health.market)
          }
        }
      } catch {
        // Silent fail - status will remain as default
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  if (!status) return null

  const getConfig = () => {
    if (status.is_open) return {
      dot: 'bg-bullish',
      dotGlow: 'shadow-[0_0_6px_rgba(16,185,129,0.5)]',
      text: 'text-bullish',
      bg: 'bg-bullish/10',
      label: 'OPEN',
      pulse: true,
    }
    if (status.is_pre_market) return {
      dot: 'bg-amber-400',
      dotGlow: 'shadow-[0_0_6px_rgba(251,191,36,0.4)]',
      text: 'text-amber-400',
      bg: 'bg-amber-400/10',
      label: 'PRE-MKT',
      pulse: true,
    }
    if (status.is_after_hours) return {
      dot: 'bg-purple-400',
      dotGlow: 'shadow-[0_0_6px_rgba(192,132,252,0.4)]',
      text: 'text-purple-400',
      bg: 'bg-purple-400/10',
      label: 'AFTER-HRS',
      pulse: false,
    }
    return {
      dot: 'bg-foreground-muted/50',
      dotGlow: '',
      text: 'text-foreground-muted',
      bg: 'bg-background-tertiary/40',
      label: 'CLOSED',
      pulse: false,
    }
  }

  const config = getConfig()

  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md ${config.bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot} ${config.dotGlow} ${config.pulse ? 'animate-pulse' : ''}`} />
      <span className={`text-[10px] font-bold tracking-wider ${config.text}`}>{config.label}</span>
    </div>
  )
}
