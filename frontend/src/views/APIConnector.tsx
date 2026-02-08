import { useState, useEffect } from 'react'
import {
  Wifi,
  WifiOff,
  RefreshCw,
  Plus,
  Trash2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Eye,
  EyeOff,
  Settings,
  Zap,
  Database,
  Activity,
  Lock,
  Unlock,
  Clock,
  ExternalLink,
} from 'lucide-react'
import { cn } from '@/utils/cn'

interface APIConnection {
  id: string
  name: string
  type: 'broker' | 'data' | 'crypto' | 'news'
  provider: string
  status: 'connected' | 'disconnected' | 'error' | 'connecting'
  apiKey: string
  apiSecret: string
  lastPing: string | null
  latency: number | null
  requestsToday: number
  rateLimit: number
  features: string[]
  isPaper: boolean
}

interface APIProvider {
  id: string
  name: string
  type: 'broker' | 'data' | 'crypto' | 'news'
  logo: string
  description: string
  features: string[]
  docsUrl: string
}

const providers: APIProvider[] = [
  {
    id: 'alpaca',
    name: 'Alpaca',
    type: 'broker',
    logo: '🦙',
    description: 'Commission-free stock & crypto trading API',
    features: ['Stocks', 'Crypto', 'Paper Trading', 'WebSocket'],
    docsUrl: 'https://alpaca.markets/docs/',
  },
  {
    id: 'polygon',
    name: 'Polygon.io',
    type: 'data',
    logo: '📊',
    description: 'Real-time & historical market data',
    features: ['Stocks', 'Options', 'Forex', 'Crypto', 'News'],
    docsUrl: 'https://polygon.io/docs/',
  },
  {
    id: 'yahoo',
    name: 'Yahoo Finance',
    type: 'data',
    logo: '📈',
    description: 'Free market data (delayed)',
    features: ['Stocks', 'ETFs', 'Mutual Funds', 'Historical'],
    docsUrl: 'https://finance.yahoo.com/',
  },
  {
    id: 'finnhub',
    name: 'Finnhub',
    type: 'data',
    logo: '🐟',
    description: 'Real-time RESTful APIs for stocks',
    features: ['Stocks', 'Forex', 'Crypto', 'Economic Data'],
    docsUrl: 'https://finnhub.io/docs/',
  },
  {
    id: 'binance',
    name: 'Binance',
    type: 'crypto',
    logo: '🔶',
    description: 'Cryptocurrency exchange API',
    features: ['Spot Trading', 'Futures', 'WebSocket', 'Margin'],
    docsUrl: 'https://binance-docs.github.io/apidocs/',
  },
  {
    id: 'coinbase',
    name: 'Coinbase',
    type: 'crypto',
    logo: '🪙',
    description: 'Crypto trading and wallet API',
    features: ['Spot Trading', 'Staking', 'Custody', 'OAuth'],
    docsUrl: 'https://docs.cloud.coinbase.com/',
  },
  {
    id: 'newsapi',
    name: 'NewsAPI',
    type: 'news',
    logo: '📰',
    description: 'News articles and headlines',
    features: ['Headlines', 'Search', 'Sources', 'Categories'],
    docsUrl: 'https://newsapi.org/docs/',
  },
]

const mockConnections: APIConnection[] = [
  {
    id: 'conn_1',
    name: 'Alpaca Paper',
    type: 'broker',
    provider: 'alpaca',
    status: 'connected',
    apiKey: 'PK***************XYZ',
    apiSecret: 'SK***************ABC',
    lastPing: new Date().toISOString(),
    latency: 45,
    requestsToday: 1247,
    rateLimit: 200,
    features: ['trading', 'streaming', 'account'],
    isPaper: true,
  },
  {
    id: 'conn_2',
    name: 'Polygon Data',
    type: 'data',
    provider: 'polygon',
    status: 'connected',
    apiKey: 'PG***************123',
    apiSecret: '',
    lastPing: new Date().toISOString(),
    latency: 32,
    requestsToday: 8542,
    rateLimit: 5,
    features: ['stocks', 'options', 'news'],
    isPaper: false,
  },
  {
    id: 'conn_3',
    name: 'Finnhub Free',
    type: 'data',
    provider: 'finnhub',
    status: 'error',
    apiKey: 'FH***************ERR',
    apiSecret: '',
    lastPing: null,
    latency: null,
    requestsToday: 0,
    rateLimit: 60,
    features: ['stocks', 'forex'],
    isPaper: false,
  },
]

export function APIConnector() {
  const [connections, setConnections] = useState<APIConnection[]>(mockConnections)
  const [selectedConnection, setSelectedConnection] = useState<APIConnection | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
  const [testingConnection, setTestingConnection] = useState<string | null>(null)

  // Fetch connections from API
  useEffect(() => {
    const fetchConnections = async () => {
      try {
        const response = await fetch('/api/connections')
        if (response.ok) {
          const data = await response.json()
          if (Array.isArray(data) && data.length > 0) {
            // Normalize the data to ensure all required fields exist
            const normalizedConnections = data.map((conn: any) => ({
              ...conn,
              requestsToday: conn.requestsToday ?? 0,
              latency: conn.latency ?? null,
              apiSecret: conn.apiSecret || '',
            }))
            setConnections(normalizedConnections)
          }
        }
      } catch (error) {
        console.error('Failed to fetch connections:', error)
      }
    }
    fetchConnections()
  }, [])

  const testConnection = async (id: string) => {
    setTestingConnection(id)
    try {
      const response = await fetch(`/api/connections/${id}/test`, { method: 'POST' })
      if (response.ok) {
        const result = await response.json()
        setConnections(prev => prev.map(c =>
          c.id === id ? { ...c, status: result.success ? 'connected' : 'error', latency: result.latency } : c
        ))
      }
    } catch (error) {
      setConnections(prev => prev.map(c =>
        c.id === id ? { ...c, status: 'error' } : c
      ))
    } finally {
      setTestingConnection(null)
    }
  }

  const deleteConnection = async (id: string) => {
    setConnections(prev => prev.filter(c => c.id !== id))
  }

  const toggleSecret = (id: string) => {
    setShowSecrets(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const getStatusColor = (status: APIConnection['status']) => {
    switch (status) {
      case 'connected': return 'text-bullish bg-bullish/10'
      case 'disconnected': return 'text-foreground-muted bg-surface-secondary'
      case 'error': return 'text-bearish bg-bearish/10'
      case 'connecting': return 'text-warning bg-warning/10'
    }
  }

  const getStatusIcon = (status: APIConnection['status']) => {
    switch (status) {
      case 'connected': return <CheckCircle className="w-4 h-4" />
      case 'disconnected': return <WifiOff className="w-4 h-4" />
      case 'error': return <XCircle className="w-4 h-4" />
      case 'connecting': return <RefreshCw className="w-4 h-4 animate-spin" />
    }
  }

  const getTypeColor = (type: APIConnection['type']) => {
    switch (type) {
      case 'broker': return 'bg-blue-500/20 text-blue-400'
      case 'data': return 'bg-purple-500/20 text-purple-400'
      case 'crypto': return 'bg-orange-500/20 text-orange-400'
      case 'news': return 'bg-green-500/20 text-green-400'
    }
  }

  const connectedCount = connections.filter(c => c.status === 'connected').length

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Wifi className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">API CONNECTOR</h1>
            <p className="text-xs text-foreground-muted">
              {connectedCount}/{connections.length} connected • Manage broker & data connections
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Connection
        </button>
      </div>

      {/* Status Overview */}
      <div className="grid grid-cols-4 gap-3">
        <StatusCard
          label="Connected"
          value={connections.filter(c => c.status === 'connected').length.toString()}
          icon={<CheckCircle className="w-4 h-4" />}
          color="text-bullish"
        />
        <StatusCard
          label="Disconnected"
          value={connections.filter(c => c.status === 'disconnected').length.toString()}
          icon={<WifiOff className="w-4 h-4" />}
          color="text-foreground-muted"
        />
        <StatusCard
          label="Errors"
          value={connections.filter(c => c.status === 'error').length.toString()}
          icon={<XCircle className="w-4 h-4" />}
          color="text-bearish"
        />
        <StatusCard
          label="Total Requests"
          value={connections.reduce((sum, c) => sum + c.requestsToday, 0).toLocaleString()}
          icon={<Activity className="w-4 h-4" />}
          color="text-accent-primary"
        />
      </div>

      {/* Connections List */}
      <div className="space-y-3">
        {connections.map(connection => (
          <ConnectionCard
            key={connection.id}
            connection={connection}
            showSecret={showSecrets[connection.id]}
            onToggleSecret={() => toggleSecret(connection.id)}
            onTest={() => testConnection(connection.id)}
            onDelete={() => deleteConnection(connection.id)}
            onSelect={() => setSelectedConnection(connection)}
            isTesting={testingConnection === connection.id}
          />
        ))}

        {connections.length === 0 && (
          <div className="card p-8 text-center text-foreground-muted">
            <Wifi className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">No Connections</p>
            <p className="text-sm mt-2">Add your first API connection to get started</p>
          </div>
        )}
      </div>

      {/* Available Providers */}
      <div className="card p-4">
        <h3 className="text-sm font-medium text-foreground-primary mb-4">Available Providers</h3>
        <div className="grid grid-cols-4 gap-3">
          {providers.map(provider => (
            <ProviderCard
              key={provider.id}
              provider={provider}
              isConnected={connections.some(c => c.provider === provider.id && c.status === 'connected')}
              onClick={() => setShowAddModal(true)}
            />
          ))}
        </div>
      </div>

      {/* Add Connection Modal */}
      {showAddModal && (
        <AddConnectionModal
          providers={providers}
          onClose={() => setShowAddModal(false)}
          onAdd={(connection) => {
            setConnections(prev => [...prev, connection])
            setShowAddModal(false)
          }}
        />
      )}
    </div>
  )
}

function StatusCard({
  label,
  value,
  icon,
  color
}: {
  label: string
  value: string
  icon: React.ReactNode
  color: string
}) {
  return (
    <div className="card p-3">
      <div className="flex items-center gap-2 text-foreground-muted mb-1">
        <span className={color}>{icon}</span>
        <span className="text-xs">{label}</span>
      </div>
      <div className={cn('text-lg font-bold', color)}>{value}</div>
    </div>
  )
}

function ConnectionCard({
  connection,
  showSecret,
  onToggleSecret,
  onTest,
  onDelete,
  onSelect,
  isTesting,
}: {
  connection: APIConnection
  showSecret: boolean
  onToggleSecret: () => void
  onTest: () => void
  onDelete: () => void
  onSelect: () => void
  isTesting: boolean
}) {
  const provider = providers.find(p => p.id === connection.provider)

  return (
    <div className="card p-4 hover:border-accent-primary/50 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <div className="text-3xl">{provider?.logo || '🔌'}</div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-foreground-primary">{connection.name}</h3>
              <span className={cn('text-xs px-2 py-0.5 rounded-full', getTypeColor(connection.type))}>
                {connection.type}
              </span>
              {connection.isPaper && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-warning/20 text-warning">
                  Paper
                </span>
              )}
            </div>
            <p className="text-xs text-foreground-muted mb-2">{provider?.description}</p>

            {/* API Keys */}
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-2">
                <Lock className="w-3 h-3 text-foreground-muted" />
                <span className="font-mono text-foreground-muted">
                  {showSecret ? connection.apiKey : connection.apiKey.replace(/./g, '•')}
                </span>
                <button onClick={onToggleSecret} className="text-foreground-muted hover:text-foreground-primary">
                  {showSecret ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Stats */}
          <div className="text-right text-xs">
            {connection.latency !== null && (
              <div className="text-foreground-muted mb-1">
                <span className="font-mono">{connection.latency}ms</span> latency
              </div>
            )}
            <div className="text-foreground-muted">
              <span className="font-mono">{connection.requestsToday.toLocaleString()}</span> requests today
            </div>
          </div>

          {/* Status */}
          <div className={cn('px-3 py-1.5 rounded-lg flex items-center gap-2', getStatusColor(connection.status))}>
            {isTesting ? <RefreshCw className="w-4 h-4 animate-spin" /> : getStatusIcon(connection.status)}
            <span className="text-sm font-medium capitalize">{isTesting ? 'Testing...' : connection.status}</span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1">
            <button
              onClick={onTest}
              disabled={isTesting}
              className="p-2 rounded-lg text-foreground-muted hover:text-foreground-primary hover:bg-surface-secondary transition-colors"
              title="Test Connection"
            >
              <RefreshCw className={cn('w-4 h-4', isTesting && 'animate-spin')} />
            </button>
            <button
              onClick={onDelete}
              className="p-2 rounded-lg text-foreground-muted hover:text-bearish hover:bg-bearish/10 transition-colors"
              title="Delete"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Features */}
      <div className="mt-3 pt-3 border-t border-border flex items-center gap-2">
        <span className="text-xs text-foreground-muted">Features:</span>
        {connection.features.map(feature => (
          <span key={feature} className="text-xs px-2 py-0.5 rounded-full bg-surface-secondary text-foreground-primary">
            {feature}
          </span>
        ))}
      </div>
    </div>
  )
}

function getTypeColor(type: APIConnection['type']) {
  switch (type) {
    case 'broker': return 'bg-blue-500/20 text-blue-400'
    case 'data': return 'bg-purple-500/20 text-purple-400'
    case 'crypto': return 'bg-orange-500/20 text-orange-400'
    case 'news': return 'bg-green-500/20 text-green-400'
  }
}

function getStatusColor(status: APIConnection['status']) {
  switch (status) {
    case 'connected': return 'text-bullish bg-bullish/10'
    case 'disconnected': return 'text-foreground-muted bg-surface-secondary'
    case 'error': return 'text-bearish bg-bearish/10'
    case 'connecting': return 'text-warning bg-warning/10'
  }
}

function getStatusIcon(status: APIConnection['status']) {
  switch (status) {
    case 'connected': return <CheckCircle className="w-4 h-4" />
    case 'disconnected': return <WifiOff className="w-4 h-4" />
    case 'error': return <XCircle className="w-4 h-4" />
    case 'connecting': return <RefreshCw className="w-4 h-4 animate-spin" />
  }
}

function ProviderCard({
  provider,
  isConnected,
  onClick
}: {
  provider: APIProvider
  isConnected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'p-3 rounded-lg border transition-all text-left',
        isConnected
          ? 'border-bullish/30 bg-bullish/5'
          : 'border-border bg-surface-secondary hover:border-accent-primary/50'
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{provider.logo}</span>
        {isConnected && <CheckCircle className="w-4 h-4 text-bullish" />}
      </div>
      <h4 className="font-medium text-foreground-primary text-sm">{provider.name}</h4>
      <p className="text-xs text-foreground-muted mt-1 line-clamp-2">{provider.description}</p>
      <div className="flex items-center gap-1 mt-2">
        <span className={cn('text-[10px] px-1.5 py-0.5 rounded', getTypeColor(provider.type))}>
          {provider.type}
        </span>
      </div>
    </button>
  )
}

function AddConnectionModal({
  providers,
  onClose,
  onAdd
}: {
  providers: APIProvider[]
  onClose: () => void
  onAdd: (connection: APIConnection) => void
}) {
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const [name, setName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [isPaper, setIsPaper] = useState(true)

  const provider = providers.find(p => p.id === selectedProvider)

  const handleSubmit = () => {
    if (!selectedProvider || !name || !apiKey) return

    const newConnection: APIConnection = {
      id: `conn_${Date.now()}`,
      name,
      type: provider?.type || 'data',
      provider: selectedProvider,
      status: 'disconnected',
      apiKey: apiKey.slice(0, 4) + '*'.repeat(apiKey.length - 7) + apiKey.slice(-3),
      apiSecret: apiSecret ? apiSecret.slice(0, 4) + '*'.repeat(apiSecret.length - 7) + apiSecret.slice(-3) : '',
      lastPing: null,
      latency: null,
      requestsToday: 0,
      rateLimit: 100,
      features: provider?.features || [],
      isPaper,
    }

    onAdd(newConnection)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-surface-primary border border-border rounded-xl w-full max-w-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          <h2 className="text-xl font-bold text-foreground-primary mb-4">Add API Connection</h2>

          {/* Provider Selection */}
          <div className="mb-4">
            <label className="text-sm text-foreground-muted mb-2 block">Provider</label>
            <div className="grid grid-cols-4 gap-2">
              {providers.map(p => (
                <button
                  key={p.id}
                  onClick={() => setSelectedProvider(p.id)}
                  className={cn(
                    'p-2 rounded-lg border text-center transition-colors',
                    selectedProvider === p.id
                      ? 'border-accent-primary bg-accent-primary/10'
                      : 'border-border hover:border-accent-primary/50'
                  )}
                >
                  <span className="text-xl">{p.logo}</span>
                  <p className="text-xs text-foreground-primary mt-1">{p.name}</p>
                </button>
              ))}
            </div>
          </div>

          {selectedProvider && (
            <>
              {/* Name */}
              <div className="mb-4">
                <label className="text-sm text-foreground-muted mb-2 block">Connection Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., My Trading Account"
                  className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-foreground-primary placeholder:text-foreground-muted focus:outline-none focus:border-accent-primary"
                />
              </div>

              {/* API Key */}
              <div className="mb-4">
                <label className="text-sm text-foreground-muted mb-2 block">API Key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter your API key"
                  className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-foreground-primary placeholder:text-foreground-muted focus:outline-none focus:border-accent-primary font-mono"
                />
              </div>

              {/* API Secret */}
              <div className="mb-4">
                <label className="text-sm text-foreground-muted mb-2 block">API Secret (optional)</label>
                <input
                  type="password"
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  placeholder="Enter your API secret"
                  className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-foreground-primary placeholder:text-foreground-muted focus:outline-none focus:border-accent-primary font-mono"
                />
              </div>

              {/* Paper Trading Toggle */}
              {provider?.type === 'broker' && (
                <div className="mb-4">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isPaper}
                      onChange={(e) => setIsPaper(e.target.checked)}
                      className="w-4 h-4 rounded border-border bg-surface-secondary text-accent-primary focus:ring-accent-primary"
                    />
                    <span className="text-sm text-foreground-primary">Paper Trading (Sandbox)</span>
                  </label>
                </div>
              )}

              {/* Docs Link */}
              <a
                href={provider?.docsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-xs text-accent-primary hover:underline mb-4"
              >
                <ExternalLink className="w-3 h-3" />
                View {provider?.name} Documentation
              </a>
            </>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-border">
            <button
              onClick={onClose}
              className="flex-1 py-2 rounded-lg bg-surface-secondary text-foreground-primary hover:bg-surface-secondary/80 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!selectedProvider || !name || !apiKey}
              className={cn(
                'flex-1 py-2 rounded-lg font-medium transition-colors',
                selectedProvider && name && apiKey
                  ? 'bg-accent-primary text-background-primary hover:bg-accent-primary/90'
                  : 'bg-surface-secondary text-foreground-muted cursor-not-allowed'
              )}
            >
              Add Connection
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
