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

  const handleSearch = () => {
    // Generate mock options chain
    const basePrice = 688.98
    const strikes = Array.from({ length: 15 }, (_, i) => basePrice - 30 + i * 5)
    const mockChain: OptionRow[] = []

    strikes.forEach(strike => {
      ['CALL', 'PUT'].forEach(type => {
        if (activeFilter !== 'ALL' && activeFilter !== type + 'S') {
          if (activeFilter === 'CALLS' && type !== 'CALL') return
          if (activeFilter === 'PUTS' && type !== 'PUT') return
        }

        const iv = 15 + Math.random() * 35
        const score = Math.floor(50 + Math.random() * 50)
        mockChain.push({
          expiration: '2026-02-21',
          strike,
          type,
          bid: Math.max(0.01, (type === 'CALL' ? Math.max(0, basePrice - strike) : Math.max(0, strike - basePrice)) + Math.random() * 5),
          ask: Math.max(0.05, (type === 'CALL' ? Math.max(0, basePrice - strike) : Math.max(0, strike - basePrice)) + Math.random() * 5 + 0.05),
          iv,
          delta: type === 'CALL' ? 0.5 - (strike - basePrice) / 100 : -0.5 + (strike - basePrice) / 100,
          gamma: 0.01 + Math.random() * 0.04,
          theta: -(0.05 + Math.random() * 0.15),
          vega: 0.1 + Math.random() * 0.3,
          oi: Math.floor(100 + Math.random() * 10000),
          rating: score >= 90 ? 'A+' : score >= 80 ? 'A' : score >= 70 ? 'B+' : 'B',
          score
        })
      })
    })

    setChain(mockChain)
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
          <button onClick={handleSearch} className="btn-primary flex items-center gap-2">
            <Search className="w-4 h-4" />
            Analyze
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
                {chain.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="text-center py-12 text-foreground-muted">
                      Enter a ticker and click Analyze
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
                    <span className="text-xs font-mono">{Math.floor(Math.random() * 100)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-foreground-muted">IV Percentile</span>
                    <span className="text-xs font-mono">{Math.floor(Math.random() * 100)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-foreground-muted">HV 20d</span>
                    <span className="text-xs font-mono">{(selectedOption.iv * 0.8 + Math.random() * 5).toFixed(1)}%</span>
                  </div>
                </div>
              </div>

              {/* Score Breakdown */}
              <div className="card p-4">
                <h3 className="text-xs font-bold text-foreground-muted mb-3">SCORE BREAKDOWN</h3>
                <div className="space-y-2">
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs">Liquidity</span>
                      <span className="text-xs font-mono">{Math.floor(70 + Math.random() * 30)}</span>
                    </div>
                    <div className="h-1 bg-background-tertiary rounded-full">
                      <div className="h-full bg-accent-primary rounded-full" style={{ width: '85%' }} />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs">IV Value</span>
                      <span className="text-xs font-mono">{Math.floor(60 + Math.random() * 40)}</span>
                    </div>
                    <div className="h-1 bg-background-tertiary rounded-full">
                      <div className="h-full bg-bullish rounded-full" style={{ width: '75%' }} />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs">Risk/Reward</span>
                      <span className="text-xs font-mono">{Math.floor(50 + Math.random() * 50)}</span>
                    </div>
                    <div className="h-1 bg-background-tertiary rounded-full">
                      <div className="h-full bg-warning rounded-full" style={{ width: '65%' }} />
                    </div>
                  </div>
                </div>
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
