/**
 * Quick Trade Widget
 * Floating widget for fast order entry without leaving current view
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import {
  Zap,
  X,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Target,
  Shield,
  Calculator,
  ChevronDown,
  Minus,
  Plus,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Maximize2,
  Minimize2,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { useNotifications } from './NotificationSystem'

// Types
interface QuickTradeProps {
  isOpen: boolean
  onClose: () => void
  defaultSymbol?: string
  defaultSide?: 'BUY' | 'SELL'
}

interface OrderPreview {
  symbol: string
  side: 'BUY' | 'SELL'
  type: 'MARKET' | 'LIMIT' | 'STOP'
  quantity: number
  price?: number
  stopLoss?: number
  takeProfit?: number
  estimatedCost: number
  commission: number
  riskAmount: number
  riskPercent: number
}

// Quick symbols for fast selection
const QUICK_SYMBOLS = [
  { symbol: 'ES', name: 'E-mini S&P', multiplier: 50 },
  { symbol: 'NQ', name: 'E-mini Nasdaq', multiplier: 20 },
  { symbol: 'SPY', name: 'S&P ETF', multiplier: 1 },
  { symbol: 'QQQ', name: 'Nasdaq ETF', multiplier: 1 },
  { symbol: 'AAPL', name: 'Apple', multiplier: 1 },
  { symbol: 'NVDA', name: 'NVIDIA', multiplier: 1 },
  { symbol: 'TSLA', name: 'Tesla', multiplier: 1 },
  { symbol: 'MSFT', name: 'Microsoft', multiplier: 1 },
]

// Mock prices (would come from WebSocket in real app)
const MOCK_PRICES: Record<string, { bid: number; ask: number; last: number }> = {
  ES: { bid: 5125.25, ask: 5125.50, last: 5125.25 },
  NQ: { bid: 18250.00, ask: 18251.00, last: 18250.50 },
  SPY: { bid: 510.45, ask: 510.47, last: 510.46 },
  QQQ: { bid: 438.20, ask: 438.22, last: 438.21 },
  AAPL: { bid: 185.50, ask: 185.52, last: 185.51 },
  NVDA: { bid: 875.30, ask: 875.50, last: 875.40 },
  TSLA: { bid: 178.80, ask: 178.85, last: 178.82 },
  MSFT: { bid: 415.20, ask: 415.25, last: 415.22 },
}

export function QuickTrade({ isOpen, onClose, defaultSymbol = 'ES', defaultSide = 'BUY' }: QuickTradeProps) {
  const [symbol, setSymbol] = useState(defaultSymbol)
  const [side, setSide] = useState<'BUY' | 'SELL'>(defaultSide)
  const [orderType, setOrderType] = useState<'MARKET' | 'LIMIT' | 'STOP'>('MARKET')
  const [quantity, setQuantity] = useState(1)
  const [limitPrice, setLimitPrice] = useState<number | ''>('')
  const [stopLoss, setStopLoss] = useState<number | ''>('')
  const [takeProfit, setTakeProfit] = useState<number | ''>('')
  const [showSymbolSearch, setShowSymbolSearch] = useState(false)
  const [isExpanded, setIsExpanded] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [position, setPosition] = useState({ x: window.innerWidth - 420, y: 100 })
  const [isDragging, setIsDragging] = useState(false)
  const dragOffset = useRef({ x: 0, y: 0 })

  const { addNotification } = useNotifications()

  // Get current price
  const currentPrice = MOCK_PRICES[symbol] || { bid: 100, ask: 100.02, last: 100.01 }
  const executionPrice = side === 'BUY' ? currentPrice.ask : currentPrice.bid

  // Calculate order preview
  const preview: OrderPreview = {
    symbol,
    side,
    type: orderType,
    quantity,
    price: orderType === 'MARKET' ? executionPrice : (limitPrice as number),
    stopLoss: stopLoss as number,
    takeProfit: takeProfit as number,
    estimatedCost: quantity * executionPrice * (QUICK_SYMBOLS.find(s => s.symbol === symbol)?.multiplier || 1),
    commission: quantity * 2.5, // Mock commission
    riskAmount: stopLoss ? Math.abs(executionPrice - (stopLoss as number)) * quantity * (QUICK_SYMBOLS.find(s => s.symbol === symbol)?.multiplier || 1) : 0,
    riskPercent: 0, // Would calculate based on account size
  }

  // Update limit price when symbol changes
  useEffect(() => {
    const price = MOCK_PRICES[symbol]
    if (price) {
      setLimitPrice(side === 'BUY' ? price.ask : price.bid)
    }
  }, [symbol, side])

  // Handle dragging
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.drag-handle')) {
      setIsDragging(true)
      dragOffset.current = {
        x: e.clientX - position.x,
        y: e.clientY - position.y
      }
    }
  }, [position])

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        setPosition({
          x: Math.max(0, Math.min(window.innerWidth - 400, e.clientX - dragOffset.current.x)),
          y: Math.max(0, Math.min(window.innerHeight - 100, e.clientY - dragOffset.current.y))
        })
      }
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  // Submit order
  const handleSubmit = async () => {
    setIsSubmitting(true)

    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 500))

    addNotification({
      type: 'trade',
      priority: 'medium',
      title: 'Order Submitted',
      message: `${side} ${quantity} ${symbol} @ ${orderType === 'MARKET' ? 'MKT' : `$${limitPrice}`}`,
      data: preview
    })

    setIsSubmitting(false)
    onClose()
  }

  // Quick quantity buttons
  const adjustQuantity = (delta: number) => {
    setQuantity(Math.max(1, quantity + delta))
  }

  if (!isOpen) return null

  return createPortal(
    <div
      className="fixed z-[100]"
      style={{ left: position.x, top: position.y }}
      onMouseDown={handleMouseDown}
    >
      <div className={cn(
        'w-[400px] bg-background-secondary border border-border rounded-xl shadow-2xl overflow-hidden',
        isDragging && 'opacity-90'
      )}>
        {/* Header */}
        <div className="drag-handle flex items-center justify-between px-4 py-3 bg-background-tertiary cursor-move">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-accent-primary" />
            <span className="font-bold text-foreground-primary">Quick Trade</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1.5 rounded hover:bg-background-secondary transition-colors"
            >
              {isExpanded ? (
                <Minimize2 className="w-4 h-4 text-foreground-muted" />
              ) : (
                <Maximize2 className="w-4 h-4 text-foreground-muted" />
              )}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-background-secondary transition-colors"
            >
              <X className="w-4 h-4 text-foreground-muted" />
            </button>
          </div>
        </div>

        {isExpanded && (
          <div className="p-4 space-y-4">
            {/* Symbol Selection */}
            <div>
              <label className="text-xs text-foreground-muted mb-1 block">Symbol</label>
              <div className="relative">
                <button
                  onClick={() => setShowSymbolSearch(!showSymbolSearch)}
                  className="w-full flex items-center justify-between px-3 py-2 bg-background-tertiary rounded-lg hover:bg-background-primary transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-accent-primary">{symbol}</span>
                    <span className="text-xs text-foreground-muted">
                      {QUICK_SYMBOLS.find(s => s.symbol === symbol)?.name}
                    </span>
                  </div>
                  <ChevronDown className="w-4 h-4 text-foreground-muted" />
                </button>

                {showSymbolSearch && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-background-secondary border border-border rounded-lg shadow-xl z-10 max-h-48 overflow-y-auto">
                    {QUICK_SYMBOLS.map(s => (
                      <button
                        key={s.symbol}
                        onClick={() => {
                          setSymbol(s.symbol)
                          setShowSymbolSearch(false)
                        }}
                        className={cn(
                          'w-full flex items-center justify-between px-3 py-2 hover:bg-background-tertiary transition-colors',
                          symbol === s.symbol && 'bg-accent-primary/10'
                        )}
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-accent-primary">{s.symbol}</span>
                          <span className="text-xs text-foreground-muted">{s.name}</span>
                        </div>
                        <span className="text-xs font-mono text-foreground-secondary">
                          ${MOCK_PRICES[s.symbol]?.last.toFixed(2) || '0.00'}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Price Display */}
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="p-2 bg-background-tertiary rounded">
                <div className="text-[10px] text-foreground-muted">Bid</div>
                <div className="text-sm font-mono text-bearish">{currentPrice.bid.toFixed(2)}</div>
              </div>
              <div className="p-2 bg-background-tertiary rounded">
                <div className="text-[10px] text-foreground-muted">Last</div>
                <div className="text-sm font-mono text-foreground-primary">{currentPrice.last.toFixed(2)}</div>
              </div>
              <div className="p-2 bg-background-tertiary rounded">
                <div className="text-[10px] text-foreground-muted">Ask</div>
                <div className="text-sm font-mono text-bullish">{currentPrice.ask.toFixed(2)}</div>
              </div>
            </div>

            {/* Side Selection */}
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setSide('BUY')}
                className={cn(
                  'py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all',
                  side === 'BUY'
                    ? 'bg-bullish text-white'
                    : 'bg-bullish/20 text-bullish hover:bg-bullish/30'
                )}
              >
                <TrendingUp className="w-4 h-4" />
                BUY
              </button>
              <button
                onClick={() => setSide('SELL')}
                className={cn(
                  'py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all',
                  side === 'SELL'
                    ? 'bg-bearish text-white'
                    : 'bg-bearish/20 text-bearish hover:bg-bearish/30'
                )}
              >
                <TrendingDown className="w-4 h-4" />
                SELL
              </button>
            </div>

            {/* Order Type */}
            <div>
              <label className="text-xs text-foreground-muted mb-1 block">Order Type</label>
              <div className="flex gap-1">
                {(['MARKET', 'LIMIT', 'STOP'] as const).map(type => (
                  <button
                    key={type}
                    onClick={() => setOrderType(type)}
                    className={cn(
                      'flex-1 py-2 text-xs font-medium rounded transition-colors',
                      orderType === type
                        ? 'bg-accent-primary/20 text-accent-primary'
                        : 'bg-background-tertiary text-foreground-muted hover:text-foreground-secondary'
                    )}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            {/* Quantity */}
            <div>
              <label className="text-xs text-foreground-muted mb-1 block">Quantity</label>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => adjustQuantity(-1)}
                  className="p-2 bg-background-tertiary rounded-lg hover:bg-background-primary transition-colors"
                >
                  <Minus className="w-4 h-4" />
                </button>
                <input
                  type="number"
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                  className="flex-1 px-3 py-2 bg-background-tertiary rounded-lg text-center font-mono font-bold text-lg outline-none focus:ring-2 ring-accent-primary"
                />
                <button
                  onClick={() => adjustQuantity(1)}
                  className="p-2 bg-background-tertiary rounded-lg hover:bg-background-primary transition-colors"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
              <div className="flex justify-center gap-2 mt-2">
                {[1, 5, 10, 25].map(q => (
                  <button
                    key={q}
                    onClick={() => setQuantity(q)}
                    className={cn(
                      'px-3 py-1 text-xs rounded transition-colors',
                      quantity === q
                        ? 'bg-accent-primary/20 text-accent-primary'
                        : 'bg-background-tertiary text-foreground-muted hover:text-foreground-secondary'
                    )}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>

            {/* Limit Price (if applicable) */}
            {orderType !== 'MARKET' && (
              <div>
                <label className="text-xs text-foreground-muted mb-1 block">
                  {orderType === 'LIMIT' ? 'Limit Price' : 'Stop Price'}
                </label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground-muted" />
                  <input
                    type="number"
                    step="0.01"
                    value={limitPrice}
                    onChange={(e) => setLimitPrice(parseFloat(e.target.value) || '')}
                    className="w-full pl-8 pr-3 py-2 bg-background-tertiary rounded-lg font-mono outline-none focus:ring-2 ring-accent-primary"
                    placeholder="0.00"
                  />
                </div>
              </div>
            )}

            {/* Stop Loss & Take Profit */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-foreground-muted mb-1 flex items-center gap-1">
                  <Shield className="w-3 h-3 text-bearish" />
                  Stop Loss
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={stopLoss}
                  onChange={(e) => setStopLoss(parseFloat(e.target.value) || '')}
                  className="w-full px-3 py-2 bg-background-tertiary rounded-lg font-mono text-sm outline-none focus:ring-2 ring-bearish"
                  placeholder="Optional"
                />
              </div>
              <div>
                <label className="text-xs text-foreground-muted mb-1 flex items-center gap-1">
                  <Target className="w-3 h-3 text-bullish" />
                  Take Profit
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={takeProfit}
                  onChange={(e) => setTakeProfit(parseFloat(e.target.value) || '')}
                  className="w-full px-3 py-2 bg-background-tertiary rounded-lg font-mono text-sm outline-none focus:ring-2 ring-bullish"
                  placeholder="Optional"
                />
              </div>
            </div>

            {/* Order Preview */}
            <div className="p-3 bg-background-tertiary/50 rounded-lg border border-border">
              <div className="flex items-center gap-2 mb-2">
                <Calculator className="w-4 h-4 text-accent-primary" />
                <span className="text-xs font-medium text-foreground-primary">Order Preview</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Est. Cost:</span>
                  <span className="font-mono">${preview.estimatedCost.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Commission:</span>
                  <span className="font-mono">${preview.commission.toFixed(2)}</span>
                </div>
                {stopLoss && (
                  <div className="flex justify-between col-span-2">
                    <span className="text-foreground-muted">Risk Amount:</span>
                    <span className="font-mono text-bearish">${preview.riskAmount.toLocaleString()}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Warning */}
            {orderType === 'MARKET' && (
              <div className="flex items-start gap-2 p-2 bg-warning/10 rounded-lg">
                <AlertTriangle className="w-4 h-4 text-warning mt-0.5" />
                <p className="text-xs text-warning">
                  Market orders execute immediately at best available price
                </p>
              </div>
            )}

            {/* Submit Button */}
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className={cn(
                'w-full py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all',
                side === 'BUY'
                  ? 'bg-bullish text-white hover:bg-bullish/90'
                  : 'bg-bearish text-white hover:bg-bearish/90',
                isSubmitting && 'opacity-50 cursor-not-allowed'
              )}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <CheckCircle className="w-4 h-4" />
                  {side} {quantity} {symbol} @ {orderType === 'MARKET' ? 'MKT' : `$${limitPrice}`}
                </>
              )}
            </button>
          </div>
        )}

        {/* Collapsed View */}
        {!isExpanded && (
          <div className="px-4 py-2 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="font-bold text-accent-primary">{symbol}</span>
              <span className="text-sm font-mono">${currentPrice.last.toFixed(2)}</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => { setSide('BUY'); setIsExpanded(true) }}
                className="px-3 py-1 bg-bullish/20 text-bullish text-xs font-bold rounded hover:bg-bullish/30"
              >
                BUY
              </button>
              <button
                onClick={() => { setSide('SELL'); setIsExpanded(true) }}
                className="px-3 py-1 bg-bearish/20 text-bearish text-xs font-bold rounded hover:bg-bearish/30"
              >
                SELL
              </button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  )
}

// Hook for managing Quick Trade widget
export function useQuickTrade() {
  const [isOpen, setIsOpen] = useState(false)
  const [defaultSymbol, setDefaultSymbol] = useState('ES')
  const [defaultSide, setDefaultSide] = useState<'BUY' | 'SELL'>('BUY')

  const open = useCallback((symbol?: string, side?: 'BUY' | 'SELL') => {
    if (symbol) setDefaultSymbol(symbol)
    if (side) setDefaultSide(side)
    setIsOpen(true)
  }, [])

  const close = useCallback(() => {
    setIsOpen(false)
  }, [])

  // Keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+T or Cmd+T to toggle Quick Trade
      if ((e.ctrlKey || e.metaKey) && e.key === 't') {
        e.preventDefault()
        setIsOpen(prev => !prev)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return {
    isOpen,
    defaultSymbol,
    defaultSide,
    open,
    close
  }
}
