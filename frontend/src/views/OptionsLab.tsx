import { FlaskConical, Search } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

interface OptionRow {
  expiration: string
  strike: number
  type: string
  bid: number
  ask: number
  iv: number
  delta: number
  gamma: number
  theta: number
  vega: number
  oi: number
  rating: string
  score: number
}

const filters = ['ALL', 'CALLS', 'PUTS', 'HIGH RATED', 'WEEKLY', 'MONTHLY']
const strategyHints = ['Any', 'Income (Sell)', 'Directional (Buy)', 'Hedge', 'Earnings Play']

export function OptionsLab() {
  const [ticker, setTicker] = useState('SPY')
  const [expiration, setExpiration] = useState('')
  const [activeFilter, setActiveFilter] = useState('ALL')
  const [strategyHint, setStrategyHint] = useState('Any')
  const [chain, setChain] = useState<OptionRow[]>([])
  const [selectedOption, setSelectedOption] = useState<OptionRow | null>(null)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/options/chain/${ticker}`)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to fetch options chain')
      }

      // Transform API data to our format
      const optionsChain: OptionRow[] = []

      // API returns data in 'chain' array with option_type field
      const chainData = data.chain || data.calls || data.puts || []

      chainData.forEach((opt: any) => {
        const optType = (opt.option_type || opt.type || 'CALL').toUpperCase()

        // Apply filter
        if (activeFilter === 'CALLS' && optType !== 'CALL') return
        if (activeFilter === 'PUTS' && optType !== 'PUT') return

        const score = Math.floor((opt.volume || 0) / 100 + (opt.oi || opt.open_interest || 0) / 1000)
        optionsChain.push({
          expiration: opt.expiration || 'N/A',
          strike: opt.strike,
          type: optType,
          bid: opt.bid || 0,
          ask: opt.ask || 0,
          iv: opt.iv || (opt.implied_volatility || 0) * 100,
          delta: opt.delta || 0,
          gamma: opt.gamma || 0,
          theta: opt.theta || 0,
          vega: opt.vega || 0,
          oi: opt.oi || opt.open_interest || 0,
          rating: score >= 90 ? 'A+' : score >= 70 ? 'A' : score >= 50 ? 'B+' : 'B',
          score: Math.min(100, score)
        })
      })

      // Also handle legacy format with separate calls/puts arrays
      if (data.calls && Array.isArray(data.calls)) {
        data.calls.forEach((opt: any) => {
          if (activeFilter !== 'ALL' && activeFilter !== 'CALLS') return
          const score = Math.floor((opt.volume || 0) / 100 + (opt.open_interest || 0) / 1000)
          optionsChain.push({
            expiration: opt.expiration || 'N/A',
            strike: opt.strike,
            type: 'CALL',
            bid: opt.bid || 0,
            ask: opt.ask || 0,
            iv: opt.iv || (opt.implied_volatility || 0) * 100,
            delta: opt.delta || 0,
            gamma: opt.gamma || 0,
            theta: opt.theta || 0,
            vega: opt.vega || 0,
            oi: opt.open_interest || 0,
            rating: score >= 90 ? 'A+' : score >= 70 ? 'A' : score >= 50 ? 'B+' : 'B',
            score: Math.min(100, score)
          })
        })
      }

      if (data.puts && Array.isArray(data.puts)) {
        data.puts.forEach((opt: any) => {
          if (activeFilter !== 'ALL' && activeFilter !== 'PUTS') return
          const score = Math.floor((opt.volume || 0) / 100 + (opt.open_interest || 0) / 1000)
          optionsChain.push({
            expiration: opt.expiration || 'N/A',
            strike: opt.strike,
            type: 'PUT',
            bid: opt.bid || 0,
            ask: opt.ask || 0,
            iv: opt.iv || (opt.implied_volatility || 0) * 100,
            delta: opt.delta || 0,
            gamma: opt.gamma || 0,
            theta: opt.theta || 0,
            vega: opt.vega || 0,
            oi: opt.open_interest || 0,
            rating: score >= 90 ? 'A+' : score >= 70 ? 'A' : score >= 50 ? 'B+' : 'B',
            score: Math.min(100, score)
          })
        })
      }

      // Sort by strike price
      optionsChain.sort((a, b) => a.strike - b.strike)
      setChain(optionsChain)

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch options data')
      setChain([])
    } finally {
      setLoading(false)
    }
  }

  const getRatingColor = (rating: string) => {
    switch (rating) {
      case 'A+': return 'bg-bullish text-white'
      case 'A': return 'bg-bullish/70 text-white'
      case 'B+': return 'bg-accent-primary text-background-primary'
      default: return 'bg-foreground-muted/30 text-foreground-primary'
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <FlaskConical className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-accent-primary">OPTIONS LAB</h1>
          <p className="text-xs text-foreground-muted">Smart options analysis and rating</p>
        </div>
      </div>

      {/* Controls */}
      <div className="card p-4">
        <div className="flex items-end gap-4 flex-wrap">
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="input w-24"
            />
          </div>
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Expiration</label>
            <select
              value={expiration}
              onChange={(e) => setExpiration(e.target.value)}
              className="input w-40"
            >
              <option value="">All Expirations</option>
              <option value="2026-01-31">Jan 31, 2026</option>
              <option value="2026-02-07">Feb 7, 2026</option>
              <option value="2026-02-14">Feb 14, 2026</option>
              <option value="2026-02-21">Feb 21, 2026</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Strategy Hint</label>
            <select
              value={strategyHint}
              onChange={(e) => setStrategyHint(e.target.value)}
              className="input w-40"
            >
              {strategyHints.map(hint => (
                <option key={hint} value={hint}>{hint}</option>
              ))}
            </select>
          </div>
          <button onClick={handleSearch} disabled={loading} className="btn-primary flex items-center gap-2">
            <Search className={cn('w-4 h-4', loading && 'animate-spin')} />
            {loading ? 'Loading...' : 'Analyze'}
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 mt-4">
          {filters.map(filter => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={cn(
                'px-3 py-1 text-xs font-medium rounded transition-colors',
                activeFilter === filter
                  ? 'bg-accent-primary text-background-primary'
                  : 'bg-background-tertiary text-foreground-secondary hover:text-foreground-primary'
              )}
            >
              {filter}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Options Chain */}
        <div className="col-span-8 card overflow-hidden">
          <div className="max-h-[600px] overflow-y-auto">
            <table className="data-table">
              <thead className="sticky top-0 bg-background-secondary">
                <tr>
                  <th>Exp</th>
                  <th>Strike</th>
                  <th>Type</th>
                  <th>Bid</th>
                  <th>Ask</th>
                  <th>IV%</th>
                  <th>Delta</th>
                  <th>OI</th>
                  <th>Rating</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {error ? (
                  <tr>
                    <td colSpan={10} className="text-center py-12 text-bearish">
                      {error}
                    </td>
                  </tr>
                ) : chain.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="text-center py-12 text-foreground-muted">
                      {loading ? 'Loading options chain...' : 'Enter a ticker and click Analyze'}
                    </td>
                  </tr>
                ) : (
                  chain.map((opt, i) => (
                    <tr
                      key={i}
                      onClick={() => setSelectedOption(opt)}
                      className={cn(
                        'cursor-pointer',
                        selectedOption === opt && 'bg-accent-primary/10'
                      )}
                    >
                      <td className="text-xs">{opt.expiration}</td>
                      <td className="font-mono">${opt.strike.toFixed(0)}</td>
                      <td className={cn(
                        'font-medium',
                        opt.type === 'CALL' ? 'text-bullish' : 'text-bearish'
                      )}>
                        {opt.type}
                      </td>
                      <td className="font-mono">${opt.bid.toFixed(2)}</td>
                      <td className="font-mono">${opt.ask.toFixed(2)}</td>
                      <td className="font-mono">{opt.iv.toFixed(1)}%</td>
                      <td className="font-mono">{opt.delta.toFixed(3)}</td>
                      <td className="font-mono">{opt.oi.toLocaleString()}</td>
                      <td>
                        <span className={cn('px-2 py-0.5 rounded text-xs font-bold', getRatingColor(opt.rating))}>
                          {opt.rating}
                        </span>
                      </td>
                      <td className="font-mono font-bold text-accent-primary">{opt.score}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Option Detail */}
        <div className="col-span-4 space-y-4">
          {selectedOption ? (
            <>
              {/* Greeks */}
              <div className="card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">GREEKS</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-background-tertiary p-3 rounded">
                    <div className="text-xs text-foreground-muted">Delta</div>
                    <div className="text-lg font-mono font-bold">{selectedOption.delta.toFixed(4)}</div>
                  </div>
                  <div className="bg-background-tertiary p-3 rounded">
                    <div className="text-xs text-foreground-muted">Gamma</div>
                    <div className="text-lg font-mono font-bold">{selectedOption.gamma.toFixed(4)}</div>
                  </div>
                  <div className="bg-background-tertiary p-3 rounded">
                    <div className="text-xs text-foreground-muted">Theta</div>
                    <div className="text-lg font-mono font-bold text-bearish">{selectedOption.theta.toFixed(4)}</div>
                  </div>
                  <div className="bg-background-tertiary p-3 rounded">
                    <div className="text-xs text-foreground-muted">Vega</div>
                    <div className="text-lg font-mono font-bold">{selectedOption.vega.toFixed(4)}</div>
                  </div>
                </div>
              </div>

              {/* IV Analysis */}
              <div className="card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">IV ANALYSIS</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-xs text-foreground-muted">Current IV</span>
                    <span className="text-xs font-mono font-bold">{selectedOption.iv.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-foreground-muted">IV Rank</span>
                    <span className="text-xs font-mono">--</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-foreground-muted">IV Percentile</span>
                    <span className="text-xs font-mono">--</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-foreground-muted">HV 20d</span>
                    <span className="text-xs font-mono">--</span>
                  </div>
                </div>
              </div>

              {/* Score Breakdown */}
              <div className="card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">SCORE BREAKDOWN</h3>
                {(() => {
                  const liquidityScore = Math.min(100, Math.floor((selectedOption.volume / 500 + selectedOption.oi / 5000) * 50))
                  const ivScore = Math.min(100, Math.floor(selectedOption.iv > 0 ? (selectedOption.iv < 50 ? selectedOption.iv * 2 : 100 - (selectedOption.iv - 50)) : 0))
                  const rrScore = Math.min(100, selectedOption.score)
                  return (
                    <div className="space-y-2">
                      <div>
                        <div className="flex justify-between mb-1">
                          <span className="text-xs">Liquidity</span>
                          <span className="text-xs font-mono">{liquidityScore}</span>
                        </div>
                        <div className="h-1 bg-background-tertiary rounded-full">
                          <div className="h-full bg-accent-primary rounded-full" style={{ width: `${liquidityScore}%` }} />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between mb-1">
                          <span className="text-xs">IV Value</span>
                          <span className="text-xs font-mono">{ivScore}</span>
                        </div>
                        <div className="h-1 bg-background-tertiary rounded-full">
                          <div className="h-full bg-bullish rounded-full" style={{ width: `${ivScore}%` }} />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between mb-1">
                          <span className="text-xs">Overall</span>
                          <span className="text-xs font-mono">{rrScore}</span>
                        </div>
                        <div className="h-1 bg-background-tertiary rounded-full">
                          <div className="h-full bg-warning rounded-full" style={{ width: `${rrScore}%` }} />
                        </div>
                      </div>
                    </div>
                  )
                })()}
              </div>
            </>
          ) : (
            <div className="card p-8 text-center text-foreground-muted">
              Select an option to view details
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
