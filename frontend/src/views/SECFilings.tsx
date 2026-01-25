import { FileSearch, Search, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

export function SECFilings() {
  const [ticker, setTicker] = useState('AAPL')
  const [loading, setLoading] = useState(false)
  const [filings, setFilings] = useState<any[]>([])

  const search = () => {
    setLoading(true)
    setTimeout(() => {
      const types = ['10-K', '10-Q', '8-K', '4', 'DEF 14A', '13F-HR']
      const titles: Record<string, string> = {
        '10-K': 'Annual Report',
        '10-Q': 'Quarterly Report',
        '8-K': 'Current Report',
        '4': 'Statement of Changes in Beneficial Ownership',
        'DEF 14A': 'Proxy Statement',
        '13F-HR': 'Institutional Holdings Report'
      }

      const mockFilings = Array.from({ length: 25 }, (_, i) => {
        const type = types[Math.floor(Math.random() * types.length)]
        return {
          date: new Date(Date.now() - i * 7 * 24 * 60 * 60 * 1000 - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          type,
          title: titles[type],
          url: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${ticker}`
        }
      }).sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())

      setFilings(mockFilings)
      setLoading(false)
    }, 500)
  }

  const getTypeBadgeColor = (type: string) => {
    switch (type) {
      case '10-K': return 'bg-accent-primary/20 text-accent-primary'
      case '10-Q': return 'bg-bullish/20 text-bullish'
      case '8-K': return 'bg-warning/20 text-warning'
      case '4': return 'bg-foreground-muted/20 text-foreground-muted'
      default: return 'bg-background-tertiary text-foreground-secondary'
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <FileSearch className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-accent-primary">SEC FILINGS</h1>
          <p className="text-xs text-foreground-muted">Search SEC EDGAR database</p>
        </div>
      </div>

      {/* Search */}
      <div className="card p-4">
        <div className="flex items-end gap-4">
          <div>
            <label className="block text-xs text-foreground-muted mb-1">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="input w-32"
            />
          </div>
          <button onClick={search} disabled={loading} className="btn-primary flex items-center gap-2">
            <Search className="w-4 h-4" />
            Search
          </button>
        </div>
      </div>

      {/* Filing types legend */}
      <div className="flex items-center gap-4 text-xs">
        <span className="text-foreground-muted">Filing Types:</span>
        {['10-K', '10-Q', '8-K', '4', 'DEF 14A'].map(type => (
          <span key={type} className={cn('px-2 py-0.5 rounded', getTypeBadgeColor(type))}>
            {type}
          </span>
        ))}
      </div>

      {/* Filings Table */}
      {filings.length > 0 && (
        <div className="card overflow-hidden">
          <div className="p-4 border-b border-border">
            <h3 className="text-sm font-bold">Recent Filings - {ticker}</h3>
          </div>
          <div className="max-h-[500px] overflow-y-auto">
            <table className="data-table">
              <thead className="sticky top-0 bg-background-secondary">
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Title</th>
                  <th>Link</th>
                </tr>
              </thead>
              <tbody>
                {filings.map((f, i) => (
                  <tr key={i}>
                    <td className="font-mono text-xs">{f.date}</td>
                    <td>
                      <span className={cn('px-2 py-0.5 rounded text-xs font-bold', getTypeBadgeColor(f.type))}>
                        {f.type}
                      </span>
                    </td>
                    <td className="text-sm">{f.title}</td>
                    <td>
                      <a
                        href={f.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent-primary hover:underline flex items-center gap-1 text-xs"
                      >
                        View <ExternalLink className="w-3 h-3" />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
