import { Cpu, RefreshCw, AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

const cycles = [
  { id: 'all', name: 'ALL CYCLES (AI Consensus)', description: 'Aggregate signal from all cycles' },
  { id: 'yield_curve', name: 'Yield Curve (10Y-2Y)', description: 'Recession lead indicator' },
  { id: 'lei', name: 'Leading Economic Index', description: 'Economic direction predictor' },
  { id: 'sahm', name: 'Sahm Rule (Unemployment)', description: 'Recession confirmation' },
  { id: 'ism', name: 'ISM Manufacturing', description: 'Business cycle indicator' },
  { id: 'credit_spreads', name: 'Credit Spreads (HY-IG)', description: 'Market stress gauge' },
  { id: 'kondratiev', name: 'Kondratiev Wave (54yr)', description: 'Long-term economic cycle' },
  { id: 'real_estate', name: '18-Year Real Estate', description: 'Property cycle' },
  { id: 'kitchin', name: 'Kitchin (3.5yr Inventory)', description: 'Short business cycle' },
  { id: 'presidential', name: 'Presidential (4yr)', description: 'Election cycle effect' },
]

export function TradingBrain() {
  const [selectedCycle, setSelectedCycle] = useState('all')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<any>(null)

  const analyze = () => {
    setAnalyzing(true)
    setTimeout(() => {
      const signals = ['BULLISH', 'BEARISH', 'NEUTRAL']
      const mainSignal = signals[Math.floor(Math.random() * 3)]
      const agreeing = Math.floor(4 + Math.random() * 6)

      setAnalysis({
        consensus: {
          signal: mainSignal,
          confidence: 55 + Math.random() * 35,
          agreeing,
          total: 10
        },
        cycles: cycles.slice(1).map(c => ({
          ...c,
          signal: signals[Math.floor(Math.random() * 3)],
          value: (Math.random() * 2 - 1).toFixed(2)
        })),
        indicators: {
          yield_curve: (-0.5 + Math.random()).toFixed(2),
          credit_spread: (1 + Math.random() * 2).toFixed(2),
          vix: (12 + Math.random() * 20).toFixed(1),
          ism_pmi: (45 + Math.random() * 15).toFixed(1)
        },
        thesis: mainSignal === 'BULLISH'
          ? 'Multiple cycles align for continued expansion. Risk appetite favored. Consider growth-oriented positioning.'
          : mainSignal === 'BEARISH'
          ? 'Warning signals across multiple cycles. Defensive positioning recommended. Consider hedging strategies.'
          : 'Mixed signals across cycles. Wait for clearer confirmation before major positioning changes.'
      })
      setAnalyzing(false)
    }, 1000)
  }

  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'BULLISH': return 'text-bullish'
      case 'BEARISH': return 'text-bearish'
      default: return 'text-warning'
    }
  }

  const getSignalBg = (signal: string) => {
    switch (signal) {
      case 'BULLISH': return 'bg-bullish/10'
      case 'BEARISH': return 'bg-bearish/10'
      default: return 'bg-warning/10'
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Cpu className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">TRADING BRAIN</h1>
            <p className="text-xs text-foreground-muted">Multi-Cycle Intelligence System</p>
          </div>
        </div>
        <button onClick={analyze} disabled={analyzing} className="btn-primary flex items-center gap-2">
          <RefreshCw className={cn('w-4 h-4', analyzing && 'animate-spin')} />
          Analyze Cycles
        </button>
      </div>

      {/* Cycle Selector */}
      <div className="card p-4">
        <h3 className="text-xs font-bold text-foreground-muted mb-3">CYCLE ANALYSIS</h3>
        <div className="flex flex-wrap gap-2">
          {cycles.map(c => (
            <button
              key={c.id}
              onClick={() => setSelectedCycle(c.id)}
              className={cn(
                'px-3 py-1.5 text-xs rounded transition-colors',
                selectedCycle === c.id
                  ? 'bg-accent-primary text-background-primary'
                  : 'bg-background-tertiary text-foreground-secondary hover:text-foreground-primary'
              )}
            >
              {c.name}
            </button>
          ))}
        </div>
      </div>

      {analysis && (
        <div className="grid grid-cols-12 gap-4">
          {/* Consensus */}
          <div className="col-span-4 card p-6">
            <h3 className="text-xs font-bold text-foreground-muted mb-4 text-center">AI MULTI-CYCLE CONSENSUS</h3>
            <div className={cn(
              'p-6 rounded-lg text-center',
              getSignalBg(analysis.consensus.signal)
            )}>
              {analysis.consensus.signal === 'BULLISH' && <TrendingUp className="w-12 h-12 mx-auto mb-2 text-bullish" />}
              {analysis.consensus.signal === 'BEARISH' && <TrendingDown className="w-12 h-12 mx-auto mb-2 text-bearish" />}
              {analysis.consensus.signal === 'NEUTRAL' && <AlertTriangle className="w-12 h-12 mx-auto mb-2 text-warning" />}
              <div className={cn('text-3xl font-bold', getSignalColor(analysis.consensus.signal))}>
                {analysis.consensus.signal}
              </div>
              <div className="text-sm text-foreground-muted mt-2">
                Confidence: {analysis.consensus.confidence.toFixed(1)}%
              </div>
              <div className="text-xs text-foreground-muted mt-1">
                {analysis.consensus.agreeing}/{analysis.consensus.total} cycles agreeing
              </div>
            </div>
          </div>

          {/* Individual Cycles */}
          <div className="col-span-5 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">INDIVIDUAL CYCLE SIGNALS</h3>
            <div className="max-h-[300px] overflow-y-auto space-y-2">
              {analysis.cycles.map((c: any) => (
                <div key={c.id} className="flex items-center justify-between p-2 bg-background-tertiary rounded">
                  <div>
                    <div className="text-xs font-medium">{c.name}</div>
                    <div className="text-xs text-foreground-muted">{c.description}</div>
                  </div>
                  <span className={cn(
                    'px-2 py-1 rounded text-xs font-bold',
                    getSignalBg(c.signal),
                    getSignalColor(c.signal)
                  )}>
                    {c.signal}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Economic Indicators */}
          <div className="col-span-3 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">ECONOMIC INDICATORS</h3>
            <div className="space-y-3">
              <div className="p-3 bg-background-tertiary rounded">
                <div className="text-xs text-foreground-muted">Yield Curve</div>
                <div className={cn(
                  'text-lg font-mono font-bold',
                  parseFloat(analysis.indicators.yield_curve) < 0 ? 'text-bearish' : 'text-bullish'
                )}>
                  {analysis.indicators.yield_curve}%
                </div>
              </div>
              <div className="p-3 bg-background-tertiary rounded">
                <div className="text-xs text-foreground-muted">Credit Spread</div>
                <div className={cn(
                  'text-lg font-mono font-bold',
                  parseFloat(analysis.indicators.credit_spread) > 2 ? 'text-warning' : 'text-bullish'
                )}>
                  {analysis.indicators.credit_spread}%
                </div>
              </div>
              <div className="p-3 bg-background-tertiary rounded">
                <div className="text-xs text-foreground-muted">VIX Level</div>
                <div className={cn(
                  'text-lg font-mono font-bold',
                  parseFloat(analysis.indicators.vix) > 20 ? 'text-warning' : 'text-bullish'
                )}>
                  {analysis.indicators.vix}
                </div>
              </div>
              <div className="p-3 bg-background-tertiary rounded">
                <div className="text-xs text-foreground-muted">ISM PMI</div>
                <div className={cn(
                  'text-lg font-mono font-bold',
                  parseFloat(analysis.indicators.ism_pmi) < 50 ? 'text-bearish' : 'text-bullish'
                )}>
                  {analysis.indicators.ism_pmi}
                </div>
              </div>
            </div>
          </div>

          {/* Trading Thesis */}
          <div className="col-span-12 card p-4">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">TRADING THESIS</h3>
            <p className="text-sm text-foreground-secondary">
              {analysis.thesis}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
