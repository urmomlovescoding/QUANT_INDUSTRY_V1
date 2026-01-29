/**
 * Connection Status Component
 * Shows backend API and WebSocket connection status
 */

import { useEffect, useState } from 'react'
import { Wifi, WifiOff, Server, ServerOff, AlertCircle, CheckCircle } from 'lucide-react'
import { healthApi } from '@/api'

interface ConnectionState {
  api: 'connected' | 'disconnected' | 'checking'
  websocket: 'connected' | 'disconnected' | 'connecting'
  dataMode: string | null
  lastCheck: Date | null
  error: string | null
}

interface ConnectionStatusProps {
  wsConnected: boolean
  compact?: boolean
  className?: string
}

export function ConnectionStatus({ wsConnected, compact = false, className = '' }: ConnectionStatusProps) {
  const [state, setState] = useState<ConnectionState>({
    api: 'checking',
    websocket: wsConnected ? 'connected' : 'disconnected',
    dataMode: null,
    lastCheck: null,
    error: null,
  })

  // Check API health on mount and periodically
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await healthApi.check()
        if (response.ok && response.data) {
          setState(prev => ({
            ...prev,
            api: 'connected',
            dataMode: response.data?.market?.session || null,
            lastCheck: new Date(),
            error: null,
          }))
        } else {
          setState(prev => ({
            ...prev,
            api: 'disconnected',
            error: response.error?.message || 'Connection failed',
            lastCheck: new Date(),
          }))
        }
      } catch (e) {
        setState(prev => ({
          ...prev,
          api: 'disconnected',
          error: e instanceof Error ? e.message : 'Unknown error',
          lastCheck: new Date(),
        }))
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000) // Check every 30s

    return () => clearInterval(interval)
  }, [])

  // Update WebSocket state when prop changes
  useEffect(() => {
    setState(prev => ({
      ...prev,
      websocket: wsConnected ? 'connected' : 'disconnected',
    }))
  }, [wsConnected])

  if (compact) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <StatusDot status={state.api} label="API" />
        <StatusDot status={state.websocket} label="WS" />
      </div>
    )
  }

  return (
    <div className={`bg-background-secondary rounded-lg p-3 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-foreground-muted">Connection Status</span>
        {state.lastCheck && (
          <span className="text-xs text-foreground-muted">
            {state.lastCheck.toLocaleTimeString()}
          </span>
        )}
      </div>
      
      <div className="space-y-2">
        <ConnectionRow
          icon={state.api === 'connected' ? Server : ServerOff}
          label="Backend API"
          status={state.api}
          detail={state.dataMode ? `${state.dataMode}` : undefined}
        />
        <ConnectionRow
          icon={state.websocket === 'connected' ? Wifi : WifiOff}
          label="WebSocket"
          status={state.websocket}
          detail={state.websocket === 'connected' ? 'Real-time' : 'Polling'}
        />
      </div>

      {state.error && (
        <div className="mt-2 flex items-center gap-2 text-xs text-red-400">
          <AlertCircle className="w-3 h-3" />
          <span>{state.error}</span>
        </div>
      )}
    </div>
  )
}

function StatusDot({ status, label }: { status: string; label: string }) {
  const colors = {
    connected: 'bg-green-500',
    disconnected: 'bg-red-500',
    checking: 'bg-yellow-500 animate-pulse',
    connecting: 'bg-yellow-500 animate-pulse',
  }

  return (
    <div className="flex items-center gap-1" title={`${label}: ${status}`}>
      <span className={`w-2 h-2 rounded-full ${colors[status as keyof typeof colors] || 'bg-gray-500'}`} />
      <span className="text-xs text-foreground-muted">{label}</span>
    </div>
  )
}

function ConnectionRow({
  icon: Icon,
  label,
  status,
  detail,
}: {
  icon: React.ElementType
  label: string
  status: string
  detail?: string
}) {
  const isConnected = status === 'connected'
  const isChecking = status === 'checking' || status === 'connecting'

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Icon className={`w-4 h-4 ${isConnected ? 'text-green-400' : isChecking ? 'text-yellow-400' : 'text-red-400'}`} />
        <span className="text-sm text-foreground-primary">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        {detail && (
          <span className="text-xs text-foreground-muted">{detail}</span>
        )}
        {isConnected ? (
          <CheckCircle className="w-4 h-4 text-green-400" />
        ) : isChecking ? (
          <div className="w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
        ) : (
          <AlertCircle className="w-4 h-4 text-red-400" />
        )}
      </div>
    </div>
  )
}

/**
 * Inline connection indicator for headers/toolbars
 */
export function ConnectionIndicator({ wsConnected }: { wsConnected: boolean }) {
  const [apiConnected, setApiConnected] = useState(true)

  useEffect(() => {
    const check = async () => {
      try {
        const response = await healthApi.check()
        setApiConnected(response.ok)
      } catch {
        setApiConnected(false)
      }
    }
    check()
    const interval = setInterval(check, 30000)
    return () => clearInterval(interval)
  }, [])

  const allConnected = apiConnected && wsConnected

  return (
    <div 
      className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs ${
        allConnected 
          ? 'bg-green-900/30 text-green-400' 
          : 'bg-red-900/30 text-red-400'
      }`}
      title={`API: ${apiConnected ? 'Connected' : 'Disconnected'}, WS: ${wsConnected ? 'Connected' : 'Disconnected'}`}
    >
      <span className={`w-2 h-2 rounded-full ${allConnected ? 'bg-green-500' : 'bg-red-500'}`} />
      <span>{allConnected ? 'Connected' : 'Offline'}</span>
    </div>
  )
}

export default ConnectionStatus
