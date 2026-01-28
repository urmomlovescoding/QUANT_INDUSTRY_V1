/**
 * Order Book Widget - Real-time order book visualization
 */

import { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Activity } from 'lucide-react'

interface OrderBookLevel {
  price: number
  size: number
  total: number
}

interface OrderBookData {
  symbol: string
  timestamp: string
  bids: OrderBookLevel[]
  asks: OrderBookLevel[]
  spread: number
  spread_bps: number
  imbalance: number
  microprice: number
  mid_price: number
}

interface OrderBookWidgetProps {
  symbol?: string
  maxLevels?: number
}

export function OrderBookWidget({ symbol = 'SPY', maxLevels = 8 }: OrderBookWidgetProps) {
  const [bookData, setBookData] = useState<OrderBookData | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchOrderBook = async () => {
      try {
        const res = await fetch(`/api/orderbook/${symbol}/snapshot`)
        if (res.ok) {
          const data = await res.json()
          setBookData(data)
        }
      } catch (error) {
        console.error('Failed to fetch order book:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchOrderBook()
    const interval = setInterval(fetchOrderBook, 1000) // 1s refresh for HFT
    return () => clearInterval(interval)
  }, [symbol])

  // Calculate max size for bar scaling
  const maxBidSize = bookData?.bids.reduce((max, b) => Math.max(max, b.size), 0) ?? 1
  const maxAskSize = bookData?.asks.reduce((max, a) => Math.max(max, a.size), 0) ?? 1
  const maxSize = Math.max(maxBidSize, maxAskSize)

  const formatPrice = (price: number) => price.toFixed(2)
  const formatSize = (size: number) => {
    if (size >= 1000000) return `${(size / 1000000).toFixed(1)}M`
    if (size >= 1000) return `${(size / 1000).toFixed(1)}K`
    return size.toString()
  }

  // Imbalance indicator
  const imbalance = bookData?.imbalance ?? 0
  const imbalanceColor = imbalance > 0.2 ? 'text-green-400' : imbalance < -0.2 ? 'text-red-400' : 'text-foreground-muted'
  const ImbalanceIcon = imbalance > 0 ? TrendingUp : imbalance < 0 ? TrendingDown : Activity

  if (isLoading) {
    return (
      <div className="card p-4 animate-pulse">
        <div className="h-4 bg-background-tertiary rounded w-1/3 mb-4"></div>
        <div className="space-y-1">
          {Array(8).fill(0).map((_, i) => (
            <div key={i} className="h-5 bg-background-tertiary rounded"></div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="card p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium">{symbol}</h3>
          <span className="text-xs text-foreground-muted">Order Book</span>
        </div>
        <div className={`flex items-center gap-1 text-xs ${imbalanceColor}`}>
          <ImbalanceIcon className="w-3 h-3" />
          {(imbalance * 100).toFixed(0)}%
        </div>
      </div>

      {/* Spread indicator */}
      <div className="flex items-center justify-between text-xs mb-3 px-1">
        <span className="text-foreground-muted">Spread</span>
        <span className="font-mono">
          ${bookData?.spread.toFixed(2)} ({bookData?.spread_bps.toFixed(1)} bps)
        </span>
      </div>

      {/* Ask levels (reversed, best ask at bottom) */}
      <div className="space-y-0.5 mb-1">
        {bookData?.asks.slice(0, maxLevels).reverse().map((level, idx) => (
          <div key={`ask-${idx}`} className="relative flex items-center text-xs h-5">
            {/* Size bar */}
            <div
              className="absolute right-0 h-full bg-red-500/20 rounded-sm"
              style={{ width: `${(level.size / maxSize) * 100}%` }}
            />
            {/* Content */}
            <div className="relative flex w-full justify-between px-1">
              <span className="font-mono text-foreground-muted">{formatSize(level.size)}</span>
              <span className="font-mono text-red-400">{formatPrice(level.price)}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Spread line / Mid price */}
      <div className="flex items-center justify-center py-1.5 border-y border-border/50 my-1">
        <span className="text-xs font-mono font-medium text-cyan-400">
          ${bookData?.mid_price.toFixed(2)}
        </span>
        <span className="text-[10px] text-foreground-muted ml-2">
          μ: ${bookData?.microprice.toFixed(2)}
        </span>
      </div>

      {/* Bid levels */}
      <div className="space-y-0.5 mt-1">
        {bookData?.bids.slice(0, maxLevels).map((level, idx) => (
          <div key={`bid-${idx}`} className="relative flex items-center text-xs h-5">
            {/* Size bar */}
            <div
              className="absolute left-0 h-full bg-green-500/20 rounded-sm"
              style={{ width: `${(level.size / maxSize) * 100}%` }}
            />
            {/* Content */}
            <div className="relative flex w-full justify-between px-1">
              <span className="font-mono text-green-400">{formatPrice(level.price)}</span>
              <span className="font-mono text-foreground-muted">{formatSize(level.size)}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Footer stats */}
      <div className="flex justify-between text-[10px] text-foreground-muted mt-3 pt-2 border-t border-border/30">
        <span>Bid Depth: {formatSize(bookData?.bids.reduce((s, b) => s + b.size, 0) ?? 0)}</span>
        <span>Ask Depth: {formatSize(bookData?.asks.reduce((s, a) => s + a.size, 0) ?? 0)}</span>
      </div>
    </div>
  )
}
