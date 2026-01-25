import { Calendar, TrendingUp, TrendingDown } from 'lucide-react'
import { useState, useEffect } from 'react'
import { cn } from '@/utils/cn'

export function Earnings() {
  const [calendar, setCalendar] = useState<any[]>([])
  const [filter, setFilter] = useState<'all' | 'upcoming' | 'recent'>('upcoming')

  useEffect(() => {
    const symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AMD', 'NFLX', 'CRM', 'ORCL', 'INTC']

    const mockCalendar = symbols.map(symbol => {
      const daysOffset = Math.floor(Math.random() * 60) - 30
      const date = new Date(Date.now() + daysOffset * 24 * 60 * 60 * 1000)
      const isPast = daysOffset < 0

      return {
        symbol,
        date: date.toISOString().split('T')[0],
        time: Math.random() > 0.5 ? 'BMO' : 'AMC',
        eps_estimate: (0.5 + Math.random() * 4).toFixed(2),
        eps_actual: isPast ? (0.4 + Math.random() * 4.5).toFixed(2) : null,
        revenue_estimate: `$${Math.floor(10 + Math.random() * 90)}B`,
        surprise_pct: isPast ? ((Math.random() - 0.4) * 20).toFixed(1) : null,
        isPast
      }
    }).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

    setCalendar(mockCalendar)
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
