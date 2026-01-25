/**
 * Electron API type definitions
 * These types define the API exposed by the Electron preload script
 */

export interface SystemResources {
  cpu: {
    usage: string
    cores: number
    model: string
  }
  memory: {
    total: string
    used: string
    free: string
    usage: string
  }
  platform: string
  arch: string
  hostname: string
  uptime: number
  backendRunning: boolean
}

export interface GPUInfo {
  available: boolean
  name: string
  cuda?: boolean
  type?: 'NVIDIA' | 'AMD' | 'Integrated'
  error?: string
}

export interface BackendStatus {
  status: 'running' | 'stopped' | 'restarted'
  port?: number
  code?: number
}

export interface ElectronAPI {
  // System Resources
  getSystemResources: () => Promise<SystemResources>
  onSystemResources: (callback: (data: SystemResources) => void) => () => void

  // Configuration
  getConfig: (key: string) => Promise<any>
  setConfig: (key: string, value: any) => Promise<boolean>
  getAllConfig: () => Promise<Record<string, any>>

  // Backend Control
  startBackend: () => Promise<void>
  stopBackend: () => Promise<void>
  restartBackend: () => Promise<void>
  getBackendStatus: () => Promise<{ running: boolean }>

  onBackendLog: (callback: (data: string) => void) => () => void
  onBackendError: (callback: (data: string) => void) => () => void
  onBackendStatus: (callback: (data: BackendStatus) => void) => () => void

  // Python Script Execution
  runPythonScript: (scriptName: string, args?: string[]) => Promise<{ success: boolean; output?: string; error?: string }>

  // GPU Detection
  detectGPU: () => Promise<GPUInfo>

  // Navigation
  onNavigate: (callback: (path: string) => void) => () => void

  // Bot Control
  onBotControl: (callback: (action: 'start' | 'stop' | 'kill') => void) => () => void

  // External Links
  openExternal: (url: string) => Promise<void>

  // Notifications
  showNotification: (title: string, body: string) => Promise<void>

  // Platform Info
  platform: string
  arch: string
  electronVersion: string
  nodeVersion: string
  chromeVersion: string

  // Desktop Detection
  isElectron: boolean
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}

export {}
