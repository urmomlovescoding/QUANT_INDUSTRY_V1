import { FileSearch, Search, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils/cn'

export function SECFilings() {
  const [ticker, setTicker] = useState('AAPL')
  const [loading, setLoading] = useState(false)
  const [filings, setFilings] = useState<any[]>([])

  const [error, setError] = useState<string | null>(null)

  const search = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/research/sec/${ticker}`)
      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail || 'Failed to fetch SEC filings')
      }

      // Check if data is unavailable
      if (result.status === 'unavailable') {
        setError(result.message || 'SEC filings data not available. Configure SEC EDGAR API to enable.')
        setFilings([])
        return
      }

      // Use API data
      const apiFilings = result.data?.filings || result.filings || []
      setFilings(apiFilings.map((f: any) => ({
        date: f.date || f.filed_date || 'N/A',
        type: f.type || f.form_type || 'N/A',
        title: f.title || f.description || 'SEC Filing',
        url: f.url || f.link || `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${ticker}`
      })))

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch SEC filings')
      setFilings([])
    } finally {
      setLoading(false)
    }
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

      {/* Error display */}
      {error && (
        <div className="card p-4 bg-bearish/10 border border-bearish/30">
          <p className="text-bearish text-sm">{error}</p>
        </div>
      )}

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
