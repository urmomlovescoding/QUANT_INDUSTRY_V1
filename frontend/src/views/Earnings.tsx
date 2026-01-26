import { Calendar, TrendingUp, TrendingDown } from 'lucide-react'
import { useState, useEffect } from 'react'
import { cn } from '@/utils/cn'

export function Earnings() {
  const [calendar, setCalendar] = useState<any[]>([])
  const [filter, setFilter] = useState<'all' | 'upcoming' | 'recent'>('upcoming')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchEarnings = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/research/earnings')
      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail || 'Failed to fetch earnings data')
      }

      // Check if data is unavailable
      if (result.status === 'unavailable') {
        setError(result.message || 'Earnings data not available. Configure earnings data API to enable.')
        setCalendar([])
        return
      }

      // Transform API data
      const earningsData = (result.data?.calendar || result.calendar || []).map((e: any) => {
        const earningsDate = new Date(e.date || e.earnings_date)
        const isPast = earningsDate < new Date()

        return {
          symbol: e.symbol,
          date: e.date || e.earnings_date,
          time: e.time || e.report_time || 'N/A',
          eps_estimate: e.eps_estimate || e.estimate || 'N/A',
          eps_actual: e.eps_actual || e.actual || null,
          revenue_estimate: e.revenue_estimate || 'N/A',
          surprise_pct: e.surprise_pct || e.surprise || null,
          isPast
        }
      }).sort((a: any, b: any) => new Date(a.date).getTime() - new Date(b.date).getTime())

      setCalendar(earningsData)

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch earnings data')
      setCalendar([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEarnings()
  }, [])

  const filteredCalendar = calendar.filter(e => {
    if (filter === 'upcoming') return !e.isPast
    if (filter === 'recent') return e.isPast
    return true
  })

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Calendar className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">EARNINGS CALENDAR</h1>
            <p className="text-xs text-foreground-muted">Upcoming and recent earnings reports</p>
          </div>
        </div>
        <div className="flex gap-2">
          {(['all', 'upcoming', 'recent'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded capitalize transition-colors',
                filter === f
                  ? 'bg-accent-primary text-background-primary'
                  : 'bg-background-tertiary text-foreground-secondary hover:text-foreground-primary'
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Calendar */}
      <div className="card overflow-hidden">
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Date</th>
              <th>Time</th>
              <th>EPS Est.</th>
              <th>EPS Actual</th>
              <th>Revenue Est.</th>
              <th>Surprise</th>
            </tr>
          </thead>
          <tbody>
            {filteredCalendar.map((e, i) => (
              <tr key={i} className={cn(e.isPast && 'opacity-75')}>
                <td className="font-medium">{e.symbol}</td>
                <td className="font-mono text-xs">{e.date}</td>
                <td>
                  <span className={cn(
                    'px-2 py-0.5 rounded text-xs',
                    e.time === 'BMO'
                      ? 'bg-accent-primary/20 text-accent-primary'
                      : 'bg-warning/20 text-warning'
                  )}>
                    {e.time}
                  </span>
                </td>
                <td className="font-mono">${e.eps_estimate}</td>
                <td className="font-mono">
                  {e.eps_actual ? `$${e.eps_actual}` : '-'}
                </td>
                <td className="font-mono">{e.revenue_estimate}</td>
                <td>
                  {e.surprise_pct ? (
                    <span className={cn(
                      'flex items-center gap-1 font-mono',
                      parseFloat(e.surprise_pct) >= 0 ? 'text-bullish' : 'text-bearish'
                    )}>
                      {parseFloat(e.surprise_pct) >= 0 ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      {parseFloat(e.surprise_pct) >= 0 ? '+' : ''}{e.surprise_pct}%
                    </span>
                  ) : (
                    <span className="text-foreground-muted">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 text-xs text-foreground-muted">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-accent-primary/20 text-accent-primary">BMO</span>
          Before Market Open
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-warning/20 text-warning">AMC</span>
          After Market Close
        </div>
      </div>
    </div>
  )
}
