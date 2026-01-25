import { useState, useEffect } from 'react'
import { Cpu, HardDrive, Activity, Server, Monitor } from 'lucide-react'
import { cn } from '@/utils/cn'
import type { SystemResources, GPUInfo } from '@/types/electron'

/**
 * System resource monitor component
 * Shows CPU, Memory, and Backend status in the header
 * Only active when running in Electron desktop environment
 */
export function SystemMonitor() {
  const [resources, setResources] = useState<SystemResources | null>(null)
  const [gpuInfo, setGpuInfo] = useState<GPUInfo | null>(null)
  const [isElectron, setIsElectron] = useState(false)

  useEffect(() => {
    // Check if running in Electron
    const electronAPI = window.electronAPI
    if (!electronAPI?.isElectron) {
      return
    }

    setIsElectron(true)

    // Get initial resources
    electronAPI.getSystemResources().then(setResources)

    // Get GPU info
    electronAPI.detectGPU().then(setGpuInfo)

    // Subscribe to system resource updates
    const unsubscribe = electronAPI.onSystemResources((data) => {
      setResources(data)
    })

    return () => {
      unsubscribe()
    }
  }, [])

  // Don't render anything if not in Electron
  if (!isElectron || !resources) {
    return null
  }

  const cpuUsage = parseFloat(resources.cpu.usage)
  const memUsage = parseFloat(resources.memory.usage)

  return (
    <div className="flex items-center gap-3 px-2 py-1 bg-background-tertiary rounded-md">
      {/* CPU */}
      <ResourceIndicator
        icon={<Cpu className="w-3 h-3" />}
        label="CPU"
        value={`${resources.cpu.usage}%`}
        usage={cpuUsage}
      />

      {/* Memory */}
      <ResourceIndicator
        icon={<HardDrive className="w-3 h-3" />}
        label="RAM"
        value={`${resources.memory.used}GB`}
        usage={memUsage}
      />

      {/* GPU (if available) */}
      {gpuInfo?.available && (
        <div className="flex items-center gap-1.5" title={gpuInfo.name}>
          <Monitor className="w-3 h-3 text-accent-primary" />
          <span className="text-[10px] font-medium text-foreground-secondary">
            {gpuInfo.cuda ? 'CUDA' : gpuInfo.type}
          </span>
        </div>
      )}

      {/* Backend Status */}
      <div className="flex items-center gap-1.5">
        <Server className={cn(
          'w-3 h-3',
          resources.backendRunning ? 'text-bullish' : 'text-bearish'
        )} />
        <span className={cn(
          'text-[10px] font-medium',
          resources.backendRunning ? 'text-bullish' : 'text-bearish'
        )}>
          {resources.backendRunning ? 'API' : 'OFFLINE'}
        </span>
      </div>
    </div>
  )
}

interface ResourceIndicatorProps {
  icon: React.ReactNode
  label: string
  value: string
  usage: number
}

function ResourceIndicator({ icon, label, value, usage }: ResourceIndicatorProps) {
  // Determine color based on usage
  const getUsageColor = (usage: number) => {
    if (usage >= 90) return 'text-bearish'
    if (usage >= 70) return 'text-yellow-500'
    return 'text-bullish'
  }

  const getBarColor = (usage: number) => {
    if (usage >= 90) return 'bg-bearish'
    if (usage >= 70) return 'bg-yellow-500'
    return 'bg-bullish'
  }

  return (
    <div className="flex items-center gap-1.5" title={`${label}: ${value}`}>
      <span className={cn('', getUsageColor(usage))}>{icon}</span>
      <div className="flex flex-col gap-0.5">
        <span className="text-[10px] font-medium text-foreground-secondary leading-none">
          {value}
        </span>
        <div className="w-12 h-1 bg-background-primary rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all duration-300', getBarColor(usage))}
            style={{ width: `${Math.min(100, usage)}%` }}
          />
        </div>
      </div>
    </div>
  )
}

/**
 * Detailed system monitor panel for settings page
 */
export function SystemMonitorPanel() {
  const [resources, setResources] = useState<SystemResources | null>(null)
  const [gpuInfo, setGpuInfo] = useState<GPUInfo | null>(null)
  const [backendLogs, setBackendLogs] = useState<string[]>([])
  const [isElectron, setIsElectron] = useState(false)

  useEffect(() => {
    const electronAPI = window.electronAPI
    if (!electronAPI?.isElectron) {
      return
    }

    setIsElectron(true)

    // Get initial data
    electronAPI.getSystemResources().then(setResources)
    electronAPI.detectGPU().then(setGpuInfo)

    // Subscribe to updates
    const unsubResources = electronAPI.onSystemResources(setResources)
    const unsubLogs = electronAPI.onBackendLog((log) => {
      setBackendLogs(prev => [...prev.slice(-50), log])
    })

    return () => {
      unsubResources()
      unsubLogs()
    }
  }, [])

  if (!isElectron) {
    return (
      <div className="p-4 bg-background-secondary rounded-lg border border-border">
        <p className="text-foreground-secondary text-sm">
          System monitoring is only available in the desktop application.
        </p>
      </div>
    )
  }

  if (!resources) {
    return (
      <div className="p-4 bg-background-secondary rounded-lg border border-border">
        <p className="text-foreground-secondary text-sm">Loading system info...</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* System Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={<Cpu className="w-5 h-5" />}
          label="CPU Usage"
          value={`${resources.cpu.usage}%`}
          subtext={`${resources.cpu.cores} cores`}
          color={parseFloat(resources.cpu.usage) > 80 ? 'red' : 'green'}
        />
        <StatCard
          icon={<HardDrive className="w-5 h-5" />}
          label="Memory"
          value={`${resources.memory.used} GB`}
          subtext={`of ${resources.memory.total} GB`}
          color={parseFloat(resources.memory.usage) > 80 ? 'red' : 'green'}
        />
        <StatCard
          icon={<Monitor className="w-5 h-5" />}
          label="GPU"
          value={gpuInfo?.available ? gpuInfo.type || 'Available' : 'None'}
          subtext={gpuInfo?.cuda ? 'CUDA Enabled' : 'No CUDA'}
          color={gpuInfo?.cuda ? 'green' : 'yellow'}
        />
        <StatCard
          icon={<Server className="w-5 h-5" />}
          label="Backend"
          value={resources.backendRunning ? 'Running' : 'Stopped'}
          subtext="FastAPI Server"
          color={resources.backendRunning ? 'green' : 'red'}
        />
      </div>

      {/* System Details */}
      <div className="p-4 bg-background-secondary rounded-lg border border-border">
        <h3 className="text-sm font-medium text-foreground-primary mb-3">System Details</h3>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex justify-between">
            <span className="text-foreground-muted">Platform:</span>
            <span className="text-foreground-secondary font-mono">{resources.platform}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-foreground-muted">Architecture:</span>
            <span className="text-foreground-secondary font-mono">{resources.arch}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-foreground-muted">Hostname:</span>
            <span className="text-foreground-secondary font-mono">{resources.hostname}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-foreground-muted">Uptime:</span>
            <span className="text-foreground-secondary font-mono">
              {Math.floor(resources.uptime / 3600)}h {Math.floor((resources.uptime % 3600) / 60)}m
            </span>
          </div>
          <div className="flex justify-between col-span-2">
            <span className="text-foreground-muted">CPU Model:</span>
            <span className="text-foreground-secondary font-mono text-right truncate max-w-[200px]">
              {resources.cpu.model}
            </span>
          </div>
          {gpuInfo && (
            <div className="flex justify-between col-span-2">
              <span className="text-foreground-muted">GPU:</span>
              <span className="text-foreground-secondary font-mono text-right truncate max-w-[200px]">
                {gpuInfo.name}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Backend Controls */}
      <div className="p-4 bg-background-secondary rounded-lg border border-border">
        <h3 className="text-sm font-medium text-foreground-primary mb-3">Backend Controls</h3>
        <div className="flex gap-2">
          <button
            onClick={() => window.electronAPI?.startBackend()}
            disabled={resources.backendRunning}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded transition-colors',
              resources.backendRunning
                ? 'bg-background-tertiary text-foreground-muted cursor-not-allowed'
                : 'bg-bullish/20 text-bullish hover:bg-bullish/30'
            )}
          >
            Start Backend
          </button>
          <button
            onClick={() => window.electronAPI?.stopBackend()}
            disabled={!resources.backendRunning}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded transition-colors',
              !resources.backendRunning
                ? 'bg-background-tertiary text-foreground-muted cursor-not-allowed'
                : 'bg-bearish/20 text-bearish hover:bg-bearish/30'
            )}
          >
            Stop Backend
          </button>
          <button
            onClick={() => window.electronAPI?.restartBackend()}
            className="px-3 py-1.5 text-xs font-medium rounded bg-yellow-500/20 text-yellow-500 hover:bg-yellow-500/30 transition-colors"
          >
            Restart Backend
          </button>
        </div>
      </div>

      {/* Backend Logs */}
      {backendLogs.length > 0 && (
        <div className="p-4 bg-background-secondary rounded-lg border border-border">
          <h3 className="text-sm font-medium text-foreground-primary mb-3">Backend Logs</h3>
          <div className="h-32 overflow-auto bg-background-primary rounded p-2 font-mono text-[10px] text-foreground-muted">
            {backendLogs.map((log, i) => (
              <div key={i} className="whitespace-pre-wrap">{log}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string
  subtext: string
  color: 'green' | 'red' | 'yellow'
}

function StatCard({ icon, label, value, subtext, color }: StatCardProps) {
  const colorClasses = {
    green: 'text-bullish',
    red: 'text-bearish',
    yellow: 'text-yellow-500'
  }

  return (
    <div className="p-3 bg-background-secondary rounded-lg border border-border">
      <div className="flex items-center gap-2 mb-2">
        <span className={colorClasses[color]}>{icon}</span>
        <span className="text-xs text-foreground-muted">{label}</span>
      </div>
      <div className={cn('text-lg font-bold', colorClasses[color])}>{value}</div>
      <div className="text-[10px] text-foreground-muted">{subtext}</div>
    </div>
  )
}
