import { useState, useEffect, useMemo } from 'react'
import {
  Newspaper,
  TrendingUp,
  TrendingDown,
  Minus,
  Clock,
  ExternalLink,
  Filter,
  RefreshCw,
  Search,
  Bookmark,
  BookmarkCheck,
  BarChart3,
  AlertTriangle,
  Zap,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'

interface NewsArticle {
  id: string
  title: string
  summary: string
  source: string
  url: string
  publishedAt: string
  symbols: string[]
  sentiment: {
    score: number // -1 to 1
    label: 'bullish' | 'bearish' | 'neutral'
    confidence: number
  }
  category: 'earnings' | 'market' | 'economy' | 'company' | 'crypto' | 'commodities'
  isBreaking: boolean
  saved: boolean
}

interface SentimentTrend {
  time: string
  bullish: number
  bearish: number
  neutral: number
}

const categoryColors: Record<string, string> = {
  earnings: 'bg-purple-500/20 text-purple-400',
  market: 'bg-blue-500/20 text-blue-400',
  economy: 'bg-yellow-500/20 text-yellow-400',
  company: 'bg-accent-primary/20 text-accent-primary',
  crypto: 'bg-orange-500/20 text-orange-400',
  commodities: 'bg-green-500/20 text-green-400',
}

// Mock news data
const generateMockNews = (): NewsArticle[] => {
  const headlines = [
    { title: 'Fed Signals Potential Rate Cut in Q2 as Inflation Cools', symbols: ['SPY', 'QQQ', 'TLT'], category: 'economy', sentiment: 0.6 },
    { title: 'NVIDIA Reports Record Revenue, AI Demand Surges', symbols: ['NVDA', 'AMD', 'SMCI'], category: 'earnings', sentiment: 0.85 },
    { title: 'Apple Announces New AI Features for iPhone 16', symbols: ['AAPL'], category: 'company', sentiment: 0.55 },
    { title: 'Tesla Cuts Prices Again Amid EV Competition', symbols: ['TSLA', 'RIVN', 'LCID'], category: 'company', sentiment: -0.45 },
    { title: 'Oil Prices Drop on OPEC+ Production Increase', symbols: ['USO', 'XOM', 'CVX'], category: 'commodities', sentiment: -0.3 },
    { title: 'Bitcoin Breaks $100K Milestone on ETF Inflows', symbols: ['BTC', 'MSTR', 'COIN'], category: 'crypto', sentiment: 0.75 },
    { title: 'Microsoft Azure Growth Beats Expectations', symbols: ['MSFT', 'AMZN', 'GOOGL'], category: 'earnings', sentiment: 0.7 },
    { title: 'Regional Banks Face Renewed Pressure on CRE Exposure', symbols: ['KRE', 'NYCB', 'PACW'], category: 'market', sentiment: -0.6 },
    { title: 'Meta Platforms Unveils Next-Gen VR Headset', symbols: ['META'], category: 'company', sentiment: 0.4 },
    { title: 'Jobs Report Shows Cooling Labor Market', symbols: ['SPY', 'DIA', 'IWM'], category: 'economy', sentiment: 0.2 },
    { title: 'Semiconductor Stocks Rally on China Export Relief', symbols: ['NVDA', 'AMD', 'INTC', 'TSM'], category: 'market', sentiment: 0.65 },
    { title: 'Amazon Web Services Announces Price Cuts', symbols: ['AMZN', 'MSFT', 'GOOGL'], category: 'company', sentiment: -0.1 },
    { title: 'Gold Reaches All-Time High on Geopolitical Tensions', symbols: ['GLD', 'NEM', 'GOLD'], category: 'commodities', sentiment: 0.5 },
    { title: 'JPMorgan Warns of Commercial Real Estate Risks', symbols: ['JPM', 'BAC', 'C'], category: 'market', sentiment: -0.4 },
    { title: 'Palantir Wins Major Government Contract', symbols: ['PLTR'], category: 'company', sentiment: 0.72 },
  ]

  const sources = ['Bloomberg', 'Reuters', 'CNBC', 'WSJ', 'MarketWatch', 'Yahoo Finance', 'Benzinga']

  return headlines.map((h, i) => ({
    id: `news_${i}`,
    title: h.title,
    summary: `Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Analysis suggests ${h.sentiment > 0 ? 'positive' : h.sentiment < 0 ? 'negative' : 'neutral'} market impact.`,
    source: sources[Math.floor(Math.random() * sources.length)],
    url: '#',
    publishedAt: new Date(Date.now() - i * 1800000).toISOString(),
    symbols: h.symbols,
    sentiment: {
      score: h.sentiment,
      label: h.sentiment > 0.2 ? 'bullish' : h.sentiment < -0.2 ? 'bearish' : 'neutral',
      confidence: 70 + Math.random() * 25,
    },
    category: h.category as NewsArticle['category'],
    isBreaking: i < 2,
    saved: false,
  }))
}

// Generate sentiment trend data
const generateSentimentTrend = (): SentimentTrend[] => {
  const data = []
  for (let i = 23; i >= 0; i--) {
    const hour = new Date(Date.now() - i * 3600000).getHours()
    data.push({
      time: `${hour}:00`,
      bullish: 30 + Math.random() * 30,
      bearish: 20 + Math.random() * 25,
      neutral: 25 + Math.random() * 20,
    })
  }
  return data
}

export function News() {
  const [news, setNews] = useState<NewsArticle[]>(() => generateMockNews())
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [sentimentFilter, setSentimentFilter] = useState<string>('all')
  const [isLoading, setIsLoading] = useState(false)
  const [sentimentTrend] = useState<SentimentTrend[]>(() => generateSentimentTrend())

  // Fetch news from API
  useEffect(() => {
    const fetchNews = async () => {
      try {
        const response = await fetch('/api/news')
        if (response.ok) {
          const data = await response.json()
          if (Array.isArray(data) && data.length > 0) {
            setNews(data)
          }
        }
      } catch (error) {
        console.error('Failed to fetch news:', error)
      }
    }
    fetchNews()
  }, [])

  const filteredNews = useMemo(() => {
    return news.filter(article => {
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        const matchesTitle = article.title.toLowerCase().includes(query)
        const matchesSymbol = article.symbols.some(s => s.toLowerCase().includes(query))
        if (!matchesTitle && !matchesSymbol) return false
      }
      if (categoryFilter !== 'all' && article.category !== categoryFilter) return false
      if (sentimentFilter !== 'all' && article.sentiment.label !== sentimentFilter) return false
      return true
    })
  }, [news, searchQuery, categoryFilter, sentimentFilter])

  const sentimentStats = useMemo(() => {
    const bullish = news.filter(n => n.sentiment.label === 'bullish').length
    const bearish = news.filter(n => n.sentiment.label === 'bearish').length
    const neutral = news.filter(n => n.sentiment.label === 'neutral').length
    const total = news.length
    return {
      bullish,
      bearish,
      neutral,
      bullishPct: Math.round((bullish / total) * 100),
      bearishPct: Math.round((bearish / total) * 100),
      neutralPct: Math.round((neutral / total) * 100),
      avgScore: news.reduce((sum, n) => sum + n.sentiment.score, 0) / total,
    }
  }, [news])

  const toggleSaved = (id: string) => {
    setNews(prev => prev.map(n => n.id === id ? { ...n, saved: !n.saved } : n))
  }

  const refreshNews = async () => {
    setIsLoading(true)
    await new Promise(resolve => setTimeout(resolve, 1000))
    setNews(generateMockNews())
    setIsLoading(false)
  }

  const pieData = [
    { name: 'Bullish', value: sentimentStats.bullish, color: '#00c853' },
    { name: 'Bearish', value: sentimentStats.bearish, color: '#ff5252' },
    { name: 'Neutral', value: sentimentStats.neutral, color: '#6b7280' },
  ]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Newspaper className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">NEWS CENTER</h1>
            <p className="text-xs text-foreground-muted">
              {news.length} articles • Real-time sentiment analysis
            </p>
          </div>
        </div>
        <button
          onClick={refreshNews}
          className="btn-secondary flex items-center gap-2"
          disabled={isLoading}
        >
          <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Sentiment Overview */}
      <div className="grid grid-cols-4 gap-4">
        {/* Sentiment Gauge */}
        <div className="card p-4">
          <h3 className="text-xs text-foreground-muted mb-3">Market Sentiment</h3>
          <div className="flex items-center gap-4">
            <div className="w-20 h-20">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    innerRadius={25}
                    outerRadius={35}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-bullish flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" /> Bullish
                </span>
                <span className="text-xs font-bold">{sentimentStats.bullishPct}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-bearish flex items-center gap-1">
                  <TrendingDown className="w-3 h-3" /> Bearish
                </span>
                <span className="text-xs font-bold">{sentimentStats.bearishPct}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-foreground-muted flex items-center gap-1">
                  <Minus className="w-3 h-3" /> Neutral
                </span>
                <span className="text-xs font-bold">{sentimentStats.neutralPct}%</span>
              </div>
            </div>
          </div>
        </div>

        {/* Overall Score */}
        <div className="card p-4">
          <h3 className="text-xs text-foreground-muted mb-2">Overall Score</h3>
          <div className={cn(
            'text-3xl font-bold',
            sentimentStats.avgScore > 0.2 ? 'text-bullish' :
            sentimentStats.avgScore < -0.2 ? 'text-bearish' : 'text-foreground-primary'
          )}>
            {sentimentStats.avgScore > 0 ? '+' : ''}{(sentimentStats.avgScore * 100).toFixed(0)}
          </div>
          <div className="mt-2 h-2 bg-surface-secondary rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full transition-all',
                sentimentStats.avgScore > 0.2 ? 'bg-bullish' :
                sentimentStats.avgScore < -0.2 ? 'bg-bearish' : 'bg-warning'
              )}
              style={{ width: `${50 + sentimentStats.avgScore * 50}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-foreground-muted mt-1">
            <span>Bearish</span>
            <span>Bullish</span>
          </div>
        </div>

        {/* Sentiment Trend */}
        <div className="card p-4 col-span-2">
          <h3 className="text-xs text-foreground-muted mb-2">24h Sentiment Trend</h3>
          <div className="h-20">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sentimentTrend}>
                <defs>
                  <linearGradient id="bullishGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00c853" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#00c853" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="bearishGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ff5252" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#ff5252" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 9 }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                  labelStyle={{ color: '#9ca3af' }}
                />
                <Area type="monotone" dataKey="bullish" stroke="#00c853" fill="url(#bullishGradient)" strokeWidth={1.5} />
                <Area type="monotone" dataKey="bearish" stroke="#ff5252" fill="url(#bearishGradient)" strokeWidth={1.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground-muted" />
          <input
            type="text"
            placeholder="Search news or symbols..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-surface-secondary border border-border rounded-lg text-sm text-foreground-primary placeholder:text-foreground-muted focus:outline-none focus:border-accent-primary"
          />
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="bg-surface-secondary border border-border rounded-lg px-3 py-2 text-sm text-foreground-primary"
        >
          <option value="all">All Categories</option>
          <option value="market">Market</option>
          <option value="earnings">Earnings</option>
          <option value="economy">Economy</option>
          <option value="company">Company</option>
          <option value="crypto">Crypto</option>
          <option value="commodities">Commodities</option>
        </select>

        <div className="flex items-center gap-1 bg-surface-secondary rounded-lg p-1">
          {(['all', 'bullish', 'bearish', 'neutral'] as const).map(s => (
            <button
              key={s}
              onClick={() => setSentimentFilter(s)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                sentimentFilter === s
                  ? s === 'bullish' ? 'bg-bullish/20 text-bullish' :
                    s === 'bearish' ? 'bg-bearish/20 text-bearish' :
                    s === 'neutral' ? 'bg-foreground-muted/20 text-foreground-primary' :
                    'bg-accent-primary text-background-primary'
                  : 'text-foreground-muted hover:text-foreground-primary'
              )}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* News Feed */}
      <div className="space-y-3">
        {filteredNews.map(article => (
          <NewsCard
            key={article.id}
            article={article}
            onToggleSaved={() => toggleSaved(article.id)}
          />
        ))}

        {filteredNews.length === 0 && (
          <div className="card p-8 text-center text-foreground-muted">
            <p>No articles match your filters</p>
          </div>
        )}
      </div>
    </div>
  )
}

function NewsCard({
  article,
  onToggleSaved,
}: {
  article: NewsArticle
  onToggleSaved: () => void
}) {
  const sentimentIcon = article.sentiment.label === 'bullish'
    ? <TrendingUp className="w-4 h-4" />
    : article.sentiment.label === 'bearish'
      ? <TrendingDown className="w-4 h-4" />
      : <Minus className="w-4 h-4" />

  const sentimentColor = article.sentiment.label === 'bullish'
    ? 'text-bullish'
    : article.sentiment.label === 'bearish'
      ? 'text-bearish'
      : 'text-foreground-muted'

  const timeAgo = getTimeAgo(article.publishedAt)

  return (
    <div className={cn(
      'card p-4 hover:border-accent-primary/50 transition-colors',
      article.isBreaking && 'border-l-4 border-l-warning'
    )}>
      <div className="flex gap-4">
        {/* Sentiment indicator */}
        <div className={cn(
          'flex flex-col items-center justify-center w-16 shrink-0',
          sentimentColor
        )}>
          {sentimentIcon}
          <span className="text-xs font-bold mt-1">
            {article.sentiment.score > 0 ? '+' : ''}{(article.sentiment.score * 100).toFixed(0)}
          </span>
          <span className="text-[10px] opacity-70">{article.sentiment.confidence.toFixed(0)}%</span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-2">
            <div>
              {article.isBreaking && (
                <span className="inline-flex items-center gap-1 text-xs font-bold text-warning mb-1">
                  <Zap className="w-3 h-3" /> BREAKING
                </span>
              )}
              <h3 className="font-medium text-foreground-primary leading-tight">{article.title}</h3>
            </div>
            <button
              onClick={onToggleSaved}
              className={cn(
                'p-1.5 rounded-lg transition-colors shrink-0',
                article.saved ? 'text-accent-primary bg-accent-primary/10' : 'text-foreground-muted hover:text-foreground-primary'
              )}
            >
              {article.saved ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
            </button>
          </div>

          <p className="text-sm text-foreground-muted line-clamp-2 mb-3">{article.summary}</p>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={cn('text-xs px-2 py-0.5 rounded-full', categoryColors[article.category])}>
                {article.category}
              </span>
              {article.symbols.map(symbol => (
                <span key={symbol} className="text-xs px-2 py-0.5 rounded-full bg-surface-secondary text-accent-primary font-mono">
                  ${symbol}
                </span>
              ))}
            </div>

            <div className="flex items-center gap-3 text-xs text-foreground-muted">
              <span>{article.source}</span>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" /> {timeAgo}
              </span>
              <a href={article.url} target="_blank" rel="noopener noreferrer" className="hover:text-accent-primary">
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function getTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
  return `${Math.floor(diffMins / 1440)}d ago`
}
