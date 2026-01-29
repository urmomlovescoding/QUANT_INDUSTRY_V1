/**
 * Microstructure Module Types
 * QUANT_INDUSTRY_V1
 */

export type OrderSide = 'bid' | 'ask';
export type TradeDirection = 'uptick' | 'downtick' | 'zero';
export type ImbalanceDirection = 'buy' | 'sell' | 'neutral';

// Order Book
export interface OrderBookLevel {
  price: number;
  size: number;
  orders: number;
  side: OrderSide;
  cumulative: number;
}

export interface OrderBook {
  symbol: string;
  timestamp: string;
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  midPrice: number;
  spread: number;
  spreadBps: number;
  imbalance: number;
  depth: {
    bid1Pct: number;
    ask1Pct: number;
    bid5Pct: number;
    ask5Pct: number;
  };
}

export interface OrderBookHeatmapData {
  timestamp: string;
  priceLevel: number;
  bidSize: number;
  askSize: number;
  intensity: number;
}

// Imbalance
export interface ImbalanceMetrics {
  symbol: string;
  timestamp: string;
  volumeImbalance: number;
  orderImbalance: number;
  tradeImbalance: number;
  vwapImbalance: number;
  direction: ImbalanceDirection;
  confidence: number;
  predictedMove: number;
  historicalAccuracy: number;
}

// Time & Sales (Tape)
export interface TapeEntry {
  id: string;
  symbol: string;
  timestamp: string;
  price: number;
  size: number;
  side: 'buy' | 'sell' | 'unknown';
  exchange: string;
  condition: string;
  isBlock: boolean;
  isSweep: boolean;
  direction: TradeDirection;
  aggressorSide: 'buyer' | 'seller' | 'unknown';
}

export interface TapeAnalysis {
  symbol: string;
  period: string;
  totalVolume: number;
  buyVolume: number;
  sellVolume: number;
  unknownVolume: number;
  vwap: number;
  twap: number;
  volumeProfile: Array<{
    price: number;
    volume: number;
    buyVolume: number;
    sellVolume: number;
  }>;
  largestTrades: TapeEntry[];
  tradeVelocity: number;
}

// Flow Model
export interface FlowModelPrediction {
  symbol: string;
  timestamp: string;
  predictedDirection: ImbalanceDirection;
  confidence: number;
  expectedMove: number;
  horizon: string;
  features: Record<string, number>;
}

export interface FlowModelMetrics {
  modelId: string;
  modelName: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  sharpeRatio: number;
  hitRate: number;
  avgPredictedMove: number;
  avgActualMove: number;
  mse: number;
  trainingDate: string;
  validationPeriod: string;
  confusionMatrix: {
    truePositive: number;
    falsePositive: number;
    trueNegative: number;
    falseNegative: number;
  };
  performanceByRegime: Record<string, {
    accuracy: number;
    samples: number;
  }>;
}

// Backtest Results
export interface OrderFlowBacktestTrade {
  id: string;
  entryTime: string;
  exitTime: string;
  symbol: string;
  side: 'long' | 'short';
  entryPrice: number;
  exitPrice: number;
  size: number;
  pnl: number;
  pnlPct: number;
  signal: string;
  signalStrength: number;
  exitReason: string;
}

export interface OrderFlowBacktestResult {
  id: string;
  strategyName: string;
  startDate: string;
  endDate: string;
  symbol: string;
  totalReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  avgTrade: number;
  avgWinner: number;
  avgLoser: number;
  largestWin: number;
  largestLoss: number;
  avgHoldingTime: string;
  trades: OrderFlowBacktestTrade[];
  equityCurve: Array<{
    timestamp: string;
    equity: number;
    drawdown: number;
  }>;
  monthlyReturns: Array<{
    month: string;
    return: number;
  }>;
}

// Dashboard State
export interface MicrostructureState {
  orderBook: OrderBook | null;
  orderBookHistory: OrderBookHeatmapData[];
  imbalanceMetrics: ImbalanceMetrics | null;
  tapeEntries: TapeEntry[];
  tapeAnalysis: TapeAnalysis | null;
  flowModelMetrics: FlowModelMetrics[];
  backtestResults: OrderFlowBacktestResult[];
  selectedSymbol: string;
  isLoading: boolean;
  error: string | null;
}
