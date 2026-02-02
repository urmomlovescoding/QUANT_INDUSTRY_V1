import { useState, useEffect } from 'react'
import {
  Scale,
  AlertCircle,
  RefreshCw,
  Plus,
  Trash2,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Target,
  CheckCircle,
  XCircle
} from 'lucide-react'
import { cn } from '@/utils/cn'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'

interface BenchmarkItem {
  symbol: string
  name: string
  weight: number
  enabled: boolean
  price: number
  change: number
  change_pct: number
  ytd_return: number
  source: string
}

interface BenchmarkData {
  benchmarks: BenchmarkItem[]
  composite_return: number
  total_weight: number
}

interface BenchmarkReturn {
  symbol: string
  name: string
  returns: { date: string; return: number }[]
}

export function Benchmark() {
  const [data, setData] = useState<BenchmarkData | null>(null)
  const [comparison, setComparison] = useState<BenchmarkReturn[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newSymbol, setNewSymbol] = useState('')
  const [newWeight, setNewWeight] = useState(10)

  useEffect(() => {
    fetchBenchmarks()
    fetchComparison()
  }, [])

  const fetchBenchmarks = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/benchmark')
      if (response.ok) {
        const result = await response.json()
        setData(result)
      }
    } catch {
      // Silent fail - data will show as null
    } finally {
      setIsLoading(false)
    }
  }

  const fetchComparison = async () => {
    try {
      const response = await fetch('/api/benchmark/comparison')
      if (response.ok) {
        const result = await response.json()
        setComparison(result.benchmarks || [])
      }
    } catch {
      // Silent fail - comparison will show as empty
    }
  }

  const addBenchmark = async () => {
    if (!newSymbol) return
    try {
      await fetch(`/api/benchmark/add?symbol=${newSymbol}&weight=${newWeight}`, { method: 'POST' })
      setShowAddModal(false)
      setNewSymbol('')
      setNewWeight(10)
      fetchBenchmarks()
      fetchComparison()
    } catch {
      // Silent fail - modal will close without adding
    }
  }

  const toggleBenchmark = async (symbol: string, enabled: boolean) => {
    try {
      await fetch(`/api/benchmark/update?symbol=${symbol}&enabled=${!enabled}`, { method: 'POST' })
      fetchBenchmarks()
    } catch {
      // Silent fail - state will refresh on next poll
    }
  }

  const removeBenchmark = async (symbol: string) => {
    try {
      await fetch(`/api/benchmark/${symbol}`, { method: 'DELETE' })
      fetchBenchmarks()
      fetchComparison()
    } catch {
      // Silent fail - list will refresh on next poll
    }
  }

  // Prepare chart data
  const chartData = comparison.length > 0
    ? comparison[0].returns.map((_, idx) => {
        const point: any = { date: comparison[0].returns[idx].date }
        comparison.forEach(b => {
          if (b.returns[idx]) {
            point[b.symbol] = b.returns[idx].return
          }
        })
        return point
      })
    : []

  const colors = ['#00d4aa', '#ff6b6b', '#4dabf7', '#ffd43b', '#a78bfa']

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-accent-primary" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Scale className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">BENCHMARK</h1>
            <p className="text-xs text-foreground-muted">Portfolio benchmark management</p>
          </div>
        </div>
        <div className="card p-8 text-center text-foreground-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg font-medium">Unable to load benchmarks</p>
          <p className="text-sm mt-2">Please check if the backend is running</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Scale className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">BENCHMARK</h1>
            <p className="text-xs text-foreground-muted">Portfolio benchmark management</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Benchmark
          </button>
          <button
            onClick={() => { fetchBenchmarks(); fetchComparison(); }}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-4 gap-3">
        <div className="card p-3">
          <div className="flex items-center gap-2 text-foreground-muted mb-1">
            <BarChart3 className="w-4 h-4" />
            <span className="text-xs">Benchmarks</span>
          </div>
          <div className="text-lg font-bold text-foreground-primary">{data.benchmarks.length}</div>
        </div>
        <div className="card p-3">
          <div className="flex items-center gap-2 text-foreground-muted mb-1">
            <CheckCircle className="w-4 h-4" />
            <span className="text-xs">Active</span>
          </div>
          <div className="text-lg font-bold text-bullish">
            {data.benchmarks.filter(b => b.enabled).length}
          </div>
        </div>
        <div className="card p-3">
          <div className="flex items-center gap-2 text-foreground-muted mb-1">
            <Target className="w-4 h-4" />
            <span className="text-xs">Total Weight</span>
          </div>
          <div className="text-lg font-bold text-foreground-primary">{data.total_weight}%</div>
        </div>
        <div className="card p-3">
          <div className="flex items-center gap-2 text-foreground-muted mb-1">
            <TrendingUp className="w-4 h-4" />
            <span className="text-xs">Composite YTD</span>
          </div>
          <div className={cn(
            "text-lg font-bold",
            data.composite_return >= 0 ? "text-bullish" : "text-bearish"
          )}>
            {data.composite_return >= 0 ? '+' : ''}{data.composite_return}%
          </div>
        </div>
      </div>

      {/* Benchmark Chart */}
      {chartData.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-medium text-foreground-primary mb-3">Benchmark Performance (60 Days)</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#6b7280', fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fill: '#6b7280', fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1a1a2e',
                    border: '1px solid #2a2a3e',
                    borderRadius: '8px'
                  }}
                  labelStyle={{ color: '#9ca3af' }}
                  formatter={(value: number) => [`${value.toFixed(2)}%`, '']}
                />
                <Legend />
                {comparison.map((b, idx) => (
                  <Line
                    key={b.symbol}
                    type="monotone"
                    dataKey={b.symbol}
                    name={b.name}
                    stroke={colors[idx % colors.length]}
                    dot={false}
                    strokeWidth={2}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Benchmark List */}
      <div className="card overflow-hidden">
        <table className="w-full">
          <thead className="bg-surface-secondary">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted">Symbol</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted">Name</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-foreground-muted">Weight</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-foreground-muted">Price</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-foreground-muted">Change</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-foreground-muted">YTD Return</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-foreground-muted">Status</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-foreground-muted">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.benchmarks.map(benchmark => (
              <tr key={benchmark.symbol} className={cn(
                "hover:bg-surface-secondary/50",
                !benchmark.enabled && "opacity-50"
              )}>
                <td className="px-4 py-3 font-mono font-bold text-accent-primary">
                  {benchmark.symbol}
                </td>
                <td className="px-4 py-3 text-foreground-primary">
                  {benchmark.name}
                </td>
                <td className="px-4 py-3 text-right font-mono text-foreground-primary">
                  {benchmark.weight}%
                </td>
                <td className="px-4 py-3 text-right font-mono text-foreground-primary">
                  ${benchmark.price.toFixed(2)}
                </td>
                <td className={cn(
                  "px-4 py-3 text-right font-mono",
                  benchmark.change_pct >= 0 ? "text-bullish" : "text-bearish"
                )}>
                  <div className="flex items-center justify-end gap-1">
                    {benchmark.change_pct >= 0 ? (
                      <TrendingUp className="w-3 h-3" />
                    ) : (
                      <TrendingDown className="w-3 h-3" />
                    )}
                    {benchmark.change_pct >= 0 ? '+' : ''}{benchmark.change_pct.toFixed(2)}%
                  </div>
                </td>
                <td className={cn(
                  "px-4 py-3 text-right font-mono font-bold",
                  benchmark.ytd_return >= 0 ? "text-bullish" : "text-bearish"
                )}>
                  {benchmark.ytd_return >= 0 ? '+' : ''}{benchmark.ytd_return.toFixed(2)}%
                </td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={() => toggleBenchmark(benchmark.symbol, benchmark.enabled)}
                    className={cn(
                      "px-3 py-1 rounded text-xs font-medium",
                      benchmark.enabled
                        ? "bg-bullish/20 text-bullish"
                        : "bg-surface-secondary text-foreground-muted"
                    )}
                  >
                    {benchmark.enabled ? 'Enabled' : 'Disabled'}
                  </button>
                </td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={() => removeBenchmark(benchmark.symbol)}
                    className="p-1 text-bearish hover:bg-bearish/20 rounded"
                    title="Remove benchmark"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Data Source Info */}
      <div className="text-xs text-foreground-muted text-center">
        Data source: {data.benchmarks[0]?.source || 'unknown'} | Last updated: {new Date().toLocaleTimeString()}
      </div>

      {/* Add Benchmark Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowAddModal(false)}>
          <div className="bg-surface-primary border border-border rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-foreground-primary mb-4">Add Benchmark</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground-muted mb-1">Symbol</label>
                <input
                  type="text"
                  value={newSymbol}
                  onChange={e => setNewSymbol(e.target.value.toUpperCase())}
                  placeholder="e.g., VTI, DIA, EFA"
                  className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-foreground-primary placeholder:text-foreground-muted focus:outline-none focus:border-accent-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground-muted mb-1">Weight (%)</label>
                <input
                  type="number"
                  value={newWeight}
                  onChange={e => setNewWeight(parseInt(e.target.value) || 0)}
                  min={1}
                  max={100}
                  className="w-full px-3 py-2 bg-surface-secondary border border-border rounded-lg text-foreground-primary focus:outline-none focus:border-accent-primary"
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 py-2 rounded-lg border border-border text-foreground-muted hover:text-foreground-primary"
                >
                  Cancel
                </button>
                <button
                  onClick={addBenchmark}
                  disabled={!newSymbol}
                  className="flex-1 py-2 rounded-lg bg-accent-primary text-background-primary font-medium disabled:opacity-50"
                >
                  Add Benchmark
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
