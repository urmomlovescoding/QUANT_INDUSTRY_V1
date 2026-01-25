import { Settings as SettingsIcon, Bell, Shield, Database, Zap, Key, CheckCircle, XCircle, AlertCircle, RefreshCw, Eye, EyeOff, Palette } from 'lucide-react'
import { useState, useEffect } from 'react'
import { cn } from '@/utils/cn'

// API Configuration Types
interface APIProvider {
  id: string
  name: string
  description: string
  fields: { key: string; label: string; type: 'text' | 'password'; placeholder: string }[]
  status: 'connected' | 'disconnected' | 'error' | 'testing'
  lastTested?: string
}

// UI Presets
const UI_PRESETS = {
  bloomberg: {
    name: 'Bloomberg Terminal',
    description: 'Classic terminal dark theme with cyan accents',
    colors: { bg: '#0a0a12', accent: '#00d4aa', text: '#e8e8e8' }
  },
  tradingview_dark: {
    name: 'TradingView Dark',
    description: 'TradingView-inspired dark theme with blue accents',
    colors: { bg: '#131722', accent: '#2962ff', text: '#d1d4dc' }
  },
  dark_pro: {
    name: 'Dark Pro',
    description: 'Professional dark theme with purple accents',
    colors: { bg: '#1a1a2e', accent: '#7c3aed', text: '#e5e5e5' }
  },
  midnight: {
    name: 'Midnight',
    description: 'Deep midnight blue theme',
    colors: { bg: '#0f172a', accent: '#3b82f6', text: '#e2e8f0' }
  },
  cyberpunk: {
    name: 'Cyberpunk',
    description: 'Neon pink and cyan futuristic theme',
    colors: { bg: '#0d0d0d', accent: '#ff00ff', text: '#00ffff' }
  },
  forest: {
    name: 'Forest',
    description: 'Nature-inspired dark green theme',
    colors: { bg: '#0a1f0a', accent: '#22c55e', text: '#dcfce7' }
  }
}

export function Settings() {
  const [activeTab, setActiveTab] = useState('appearance')

  const tabs = [
    { id: 'appearance', label: 'Appearance', icon: Palette },
    { id: 'trading', label: 'Trading', icon: Zap },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'risk', label: 'Risk Management', icon: Shield },
    { id: 'data', label: 'Data Sources', icon: Database },
  ]

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <SettingsIcon className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground-primary">Settings</h1>
          <p className="text-sm text-foreground-muted">Configure your trading platform</p>
        </div>
      </div>

      <div className="card">
        {/* Tabs */}
        <div className="flex border-b border-border overflow-x-auto">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px whitespace-nowrap',
                activeTab === id
                  ? 'text-accent-primary border-accent-primary'
                  : 'text-foreground-secondary border-transparent hover:text-foreground-primary'
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-6">
          {activeTab === 'appearance' && <AppearanceSettings />}
          {activeTab === 'trading' && <TradingSettings />}
          {activeTab === 'notifications' && <NotificationSettings />}
          {activeTab === 'risk' && <RiskSettings />}
          {activeTab === 'data' && <DataSettings />}
        </div>
      </div>
    </div>
  )
}

function AppearanceSettings() {
  const [theme, setTheme] = useState('bloomberg')
  const [compactMode, setCompactMode] = useState(false)
  const [showAnimations, setShowAnimations] = useState(true)
  const [chartStyle, setChartStyle] = useState('candlestick')

  return (
    <div className="space-y-6">
      <SettingSection title="UI Presets">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {Object.entries(UI_PRESETS).map(([key, preset]) => (
            <button
              key={key}
              onClick={() => setTheme(key)}
              className={cn(
                'p-4 rounded-lg border transition-all text-left group relative overflow-hidden',
                theme === key
                  ? 'border-accent-primary bg-accent-primary/10 ring-1 ring-accent-primary'
                  : 'border-border hover:border-foreground-muted'
              )}
            >
              {/* Color Preview */}
              <div className="flex gap-1 mb-3">
                <div
                  className="w-4 h-4 rounded-full border border-white/20"
                  style={{ backgroundColor: preset.colors.bg }}
                />
                <div
                  className="w-4 h-4 rounded-full border border-white/20"
                  style={{ backgroundColor: preset.colors.accent }}
                />
                <div
                  className="w-4 h-4 rounded-full border border-white/20"
                  style={{ backgroundColor: preset.colors.text }}
                />
              </div>
              <div className="font-medium text-sm mb-1">{preset.name}</div>
              <div className="text-xs text-foreground-muted line-clamp-2">
                {preset.description}
              </div>
              {theme === key && (
                <div className="absolute top-2 right-2">
                  <CheckCircle className="w-4 h-4 text-accent-primary" />
                </div>
              )}
            </button>
          ))}
        </div>
      </SettingSection>

      <SettingSection title="Chart Settings">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground-primary mb-2">
              Default Chart Type
            </label>
            <select
              value={chartStyle}
              onChange={(e) => setChartStyle(e.target.value)}
              className="input w-48"
            >
              <option value="candlestick">Candlestick</option>
              <option value="line">Line</option>
              <option value="area">Area</option>
              <option value="bar">Bar</option>
              <option value="heikin_ashi">Heikin Ashi</option>
            </select>
          </div>
        </div>
      </SettingSection>

      <SettingSection title="Interface">
        <ToggleSetting
          label="Compact Mode"
          description="Use smaller fonts and tighter spacing"
          checked={compactMode}
          onChange={setCompactMode}
        />
        <ToggleSetting
          label="Enable Animations"
          description="Show smooth transitions and animations"
          checked={showAnimations}
          onChange={setShowAnimations}
        />
        <ToggleSetting
          label="Show Tooltips"
          description="Display helpful tooltips on hover"
          checked={true}
          onChange={() => {}}
        />
        <ToggleSetting
          label="Show Grid Lines"
          description="Display grid lines on charts"
          checked={true}
          onChange={() => {}}
        />
      </SettingSection>
    </div>
  )
}

function TradingSettings() {
  return (
    <div className="space-y-6">
      <SettingSection title="Confirmations">
        <ToggleSetting
          label="Confirm before executing trades"
          description="Show confirmation dialog before placing orders"
          checked={true}
          onChange={() => {}}
        />
        <ToggleSetting
          label="Confirm before closing all positions"
          description="Require confirmation for bulk position closure"
          checked={true}
          onChange={() => {}}
        />
      </SettingSection>

      <SettingSection title="Defaults">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground-primary mb-2">
              Default Order Quantity
            </label>
            <input
              type="number"
              defaultValue={100}
              className="input w-32"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground-primary mb-2">
              Default Order Type
            </label>
            <select className="input w-48">
              <option>Market</option>
              <option>Limit</option>
              <option>Stop</option>
              <option>Stop Limit</option>
            </select>
          </div>
        </div>
      </SettingSection>
    </div>
  )
}

function NotificationSettings() {
  return (
    <div className="space-y-6">
      <SettingSection title="Alerts">
        <ToggleSetting
          label="Enable sound alerts"
          description="Play sound for important notifications"
          checked={true}
          onChange={() => {}}
        />
      </SettingSection>

      <SettingSection title="Toast Notifications">
        <ToggleSetting
          label="Trade execution notifications"
          description="Show notification when orders are filled"
          checked={true}
          onChange={() => {}}
        />
        <ToggleSetting
          label="New signal notifications"
          description="Alert when new trading signals are generated"
          checked={true}
          onChange={() => {}}
        />
        <ToggleSetting
          label="Error notifications"
          description="Show notifications for errors and warnings"
          checked={true}
          onChange={() => {}}
        />
      </SettingSection>
    </div>
  )
}

function RiskSettings() {
  return (
    <div className="space-y-6">
      <SettingSection title="Position Limits">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground-primary mb-2">
              Max Position Size (%)
            </label>
            <input
              type="number"
              defaultValue={10}
              className="input w-32"
            />
            <p className="text-xs text-foreground-muted mt-1">
              Maximum size of a single position as % of portfolio
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground-primary mb-2">
              Max Daily Loss ($)
            </label>
            <input
              type="number"
              defaultValue={5000}
              className="input w-32"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground-primary mb-2">
              Max Drawdown (%)
            </label>
            <input
              type="number"
              defaultValue={15}
              className="input w-32"
            />
          </div>
        </div>
      </SettingSection>

      <SettingSection title="Auto Stop">
        <ToggleSetting
          label="Auto-stop on daily loss limit"
          description="Automatically halt trading when daily loss limit is reached"
          checked={true}
          onChange={() => {}}
        />
        <ToggleSetting
          label="Auto-stop on max drawdown"
          description="Halt trading when maximum drawdown is exceeded"
          checked={true}
          onChange={() => {}}
        />
      </SettingSection>
    </div>
  )
}

function DataSettings() {
  const [providers, setProviders] = useState<APIProvider[]>([
    {
      id: 'alpaca',
      name: 'Alpaca Markets',
      description: 'Stock & crypto trading API with real-time market data',
      fields: [
        { key: 'api_key', label: 'API Key', type: 'text', placeholder: 'AKXXXXXXXXXXXXXXXXXX' },
        { key: 'secret_key', label: 'Secret Key', type: 'password', placeholder: 'Your secret key' },
      ],
      status: 'disconnected'
    },
    {
      id: 'tradier',
      name: 'Tradier',
      description: 'Options and equities trading with sandbox support',
      fields: [
        { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Your API token' },
        { key: 'account_id', label: 'Account ID', type: 'text', placeholder: 'VAXXXXXXXX' },
      ],
      status: 'disconnected'
    },
    {
      id: 'finnhub',
      name: 'Finnhub',
      description: 'Real-time stock data and market news',
      fields: [
        { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Your API key' },
      ],
      status: 'disconnected'
    },
    {
      id: 'news_api',
      name: 'News API',
      description: 'Financial news and sentiment analysis',
      fields: [
        { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Your API key' },
      ],
      status: 'disconnected'
    },
    {
      id: 'finra',
      name: 'FINRA',
      description: 'Dark pool and short interest data',
      fields: [
        { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Your API key' },
      ],
      status: 'disconnected'
    },
  ])

  const [apiValues, setApiValues] = useState<Record<string, Record<string, string>>>({})
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshInterval, setRefreshInterval] = useState(5)

  // Load saved API keys on mount
  useEffect(() => {
    loadApiKeys()
  }, [])

  const loadApiKeys = async () => {
    try {
      const response = await fetch('/api/settings/api-keys')
      if (response.ok) {
        const data = await response.json()
        setApiValues(data.keys || {})
        // Update provider statuses
        setProviders(prev => prev.map(p => ({
          ...p,
          status: data.keys?.[p.id] ? 'connected' : 'disconnected'
        })))
      }
    } catch (error) {
      console.error('Failed to load API keys:', error)
    }
  }

  const saveApiKey = async (providerId: string) => {
    const values = apiValues[providerId]
    if (!values) return

    setProviders(prev => prev.map(p =>
      p.id === providerId ? { ...p, status: 'testing' } : p
    ))

    try {
      const response = await fetch('/api/settings/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: providerId, keys: values })
      })

      if (response.ok) {
        setProviders(prev => prev.map(p =>
          p.id === providerId ? { ...p, status: 'connected', lastTested: new Date().toISOString() } : p
        ))
      } else {
        setProviders(prev => prev.map(p =>
          p.id === providerId ? { ...p, status: 'error' } : p
        ))
      }
    } catch (error) {
      setProviders(prev => prev.map(p =>
        p.id === providerId ? { ...p, status: 'error' } : p
      ))
    }
  }

  const testConnection = async (providerId: string) => {
    setProviders(prev => prev.map(p =>
      p.id === providerId ? { ...p, status: 'testing' } : p
    ))

    try {
      const response = await fetch(`/api/settings/test-connection/${providerId}`)
      if (response.ok) {
        setProviders(prev => prev.map(p =>
          p.id === providerId ? { ...p, status: 'connected', lastTested: new Date().toISOString() } : p
        ))
      } else {
        setProviders(prev => prev.map(p =>
          p.id === providerId ? { ...p, status: 'error' } : p
        ))
      }
    } catch (error) {
      setProviders(prev => prev.map(p =>
        p.id === providerId ? { ...p, status: 'error' } : p
      ))
    }
  }

  const updateApiValue = (providerId: string, key: string, value: string) => {
    setApiValues(prev => ({
      ...prev,
      [providerId]: {
        ...prev[providerId],
        [key]: value
      }
    }))
  }

  const getStatusIcon = (status: APIProvider['status']) => {
    switch (status) {
      case 'connected':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />
      case 'testing':
        return <RefreshCw className="w-5 h-5 text-yellow-500 animate-spin" />
      default:
        return <AlertCircle className="w-5 h-5 text-foreground-muted" />
    }
  }

  const getStatusText = (status: APIProvider['status']) => {
    switch (status) {
      case 'connected': return 'Connected'
      case 'error': return 'Connection Failed'
      case 'testing': return 'Testing...'
      default: return 'Not Configured'
    }
  }

  return (
    <div className="space-y-6">
      <SettingSection title="Auto Refresh">
        <ToggleSetting
          label="Enable auto-refresh"
          description="Automatically refresh data at set intervals"
          checked={autoRefresh}
          onChange={setAutoRefresh}
        />
        <div className="mt-4">
          <label className="block text-sm font-medium text-foreground-primary mb-2">
            Refresh interval (seconds)
          </label>
          <input
            type="number"
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            min={1}
            max={60}
            className="input w-32"
          />
        </div>
      </SettingSection>

      <SettingSection title="API Providers">
        <div className="space-y-4">
          {providers.map((provider) => (
            <div
              key={provider.id}
              className="border border-border rounded-lg overflow-hidden"
            >
              {/* Provider Header */}
              <div className="flex items-center justify-between p-4 bg-background-secondary">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-accent-primary/10">
                    <Key className="w-4 h-4 text-accent-primary" />
                  </div>
                  <div>
                    <div className="font-medium text-foreground-primary">{provider.name}</div>
                    <div className="text-xs text-foreground-muted">{provider.description}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusIcon(provider.status)}
                  <span className={cn(
                    'text-xs font-medium',
                    provider.status === 'connected' && 'text-green-500',
                    provider.status === 'error' && 'text-red-500',
                    provider.status === 'testing' && 'text-yellow-500',
                    provider.status === 'disconnected' && 'text-foreground-muted'
                  )}>
                    {getStatusText(provider.status)}
                  </span>
                </div>
              </div>

              {/* Provider Fields */}
              <div className="p-4 space-y-4">
                {provider.fields.map((field) => (
                  <div key={field.key}>
                    <label className="block text-sm font-medium text-foreground-primary mb-2">
                      {field.label}
                    </label>
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <input
                          type={field.type === 'password' && !showKeys[`${provider.id}-${field.key}`] ? 'password' : 'text'}
                          value={apiValues[provider.id]?.[field.key] || ''}
                          onChange={(e) => updateApiValue(provider.id, field.key, e.target.value)}
                          placeholder={field.placeholder}
                          className="input w-full pr-10"
                        />
                        {field.type === 'password' && (
                          <button
                            type="button"
                            onClick={() => setShowKeys(prev => ({
                              ...prev,
                              [`${provider.id}-${field.key}`]: !prev[`${provider.id}-${field.key}`]
                            }))}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground-primary"
                          >
                            {showKeys[`${provider.id}-${field.key}`] ? (
                              <EyeOff className="w-4 h-4" />
                            ) : (
                              <Eye className="w-4 h-4" />
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {/* Action Buttons */}
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={() => saveApiKey(provider.id)}
                    disabled={provider.status === 'testing'}
                    className="btn-primary text-sm px-4 py-2"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => testConnection(provider.id)}
                    disabled={provider.status === 'testing'}
                    className="btn-ghost text-sm px-4 py-2"
                  >
                    Test Connection
                  </button>
                </div>

                {provider.lastTested && (
                  <p className="text-xs text-foreground-muted">
                    Last tested: {new Date(provider.lastTested).toLocaleString()}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </SettingSection>

      <SettingSection title="Data Priority">
        <p className="text-sm text-foreground-muted mb-4">
          Configure the order in which data sources are queried. The system will automatically failover to the next source if the primary fails.
        </p>
        <div className="space-y-2">
          {['Alpaca Markets', 'Yahoo Finance', 'Tradier', 'Finnhub'].map((source, index) => (
            <div
              key={source}
              className="flex items-center gap-3 p-3 bg-background-secondary rounded-lg"
            >
              <span className="w-6 h-6 flex items-center justify-center bg-accent-primary/20 text-accent-primary text-sm font-medium rounded">
                {index + 1}
              </span>
              <span className="text-sm text-foreground-primary">{source}</span>
            </div>
          ))}
        </div>
      </SettingSection>
    </div>
  )
}

interface SettingSectionProps {
  title: string
  children: React.ReactNode
}

function SettingSection({ title, children }: SettingSectionProps) {
  return (
    <div>
      <h3 className="text-xs font-bold text-foreground-muted uppercase tracking-wider mb-4">
        {title}
      </h3>
      {children}
    </div>
  )
}

interface ToggleSettingProps {
  label: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}

function ToggleSetting({ label, description, checked, onChange }: ToggleSettingProps) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border last:border-0">
      <div>
        <div className="text-sm font-medium text-foreground-primary">{label}</div>
        <div className="text-xs text-foreground-muted">{description}</div>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={cn(
          'relative w-10 h-6 rounded-full transition-colors',
          checked ? 'bg-accent-primary' : 'bg-background-tertiary'
        )}
      >
        <div
          className={cn(
            'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
            checked ? 'translate-x-5' : 'translate-x-1'
          )}
        />
      </button>
    </div>
  )
}
