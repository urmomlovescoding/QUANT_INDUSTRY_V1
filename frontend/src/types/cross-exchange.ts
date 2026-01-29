/**
 * Cross-Exchange Arbitrage Module Types
 * QUANT_INDUSTRY_V1
 */

export type ExchangeType = 'cex' | 'dex';
export type ArbStatus = 'pending' | 'executing' | 'completed' | 'failed' | 'expired';
export type ArbType = 'simple' | 'triangular' | 'statistical' | 'cex_dex';

// Exchange Data
export interface ExchangePrice {
  exchange: string;
  exchangeType: ExchangeType;
  symbol: string;
  bid: number;
  ask: number;
  mid: number;
  spread: number;
  spreadBps: number;
  volume24h: number;
  lastUpdate: string;
  latencyMs: number;
}

export interface PriceMatrix {
  symbol: string;
  timestamp: string;
  prices: ExchangePrice[];
  bestBid: {
    exchange: string;
    price: number;
  };
  bestAsk: {
    exchange: string;
    price: number;
  };
  maxSpread: number;
  avgSpread: number;
}

// Arbitrage Opportunities
export interface ArbOpportunity {
  id: string;
  timestamp: string;
  type: ArbType;
  symbol: string;
  buyExchange: string;
  sellExchange: string;
  buyPrice: number;
  sellPrice: number;
  spreadPct: number;
  profitEstimate: number;
  profitAfterFees: number;
  size: number;
  notional: number;
  confidence: number;
  risk: 'low' | 'medium' | 'high';
  expiresIn: number;
  status: ArbStatus;
  executionWindow: number;
  fees: {
    buyFee: number;
    sellFee: number;
    networkFee?: number;
    totalFees: number;
  };
}

// Triangular Arbitrage
export interface TriangularArbPath {
  id: string;
  timestamp: string;
  exchange: string;
  leg1: {
    pair: string;
    side: 'buy' | 'sell';
    price: number;
    amount: number;
  };
  leg2: {
    pair: string;
    side: 'buy' | 'sell';
    price: number;
    amount: number;
  };
  leg3: {
    pair: string;
    side: 'buy' | 'sell';
    price: number;
    amount: number;
  };
  startAmount: number;
  endAmount: number;
  profitPct: number;
  profitAfterFees: number;
  executionTimeMs: number;
  status: ArbStatus;
}

// CEX-DEX Spread
export interface CexDexSpread {
  symbol: string;
  timestamp: string;
  cexPrice: number;
  cexExchange: string;
  dexPrice: number;
  dexExchange: string;
  spread: number;
  spreadPct: number;
  gasPrice: number;
  gasCostUsd: number;
  netProfit: number;
  profitable: boolean;
  direction: 'cex_to_dex' | 'dex_to_cex';
}

export interface CexDexSpreadHistory {
  symbol: string;
  data: Array<{
    timestamp: string;
    spread: number;
    spreadPct: number;
    cexPrice: number;
    dexPrice: number;
  }>;
}

// Latency Monitoring
export interface ExchangeLatency {
  exchange: string;
  exchangeType: ExchangeType;
  avgLatencyMs: number;
  p50LatencyMs: number;
  p95LatencyMs: number;
  p99LatencyMs: number;
  maxLatencyMs: number;
  minLatencyMs: number;
  lastPingMs: number;
  status: 'healthy' | 'degraded' | 'down';
  uptime: number;
  lastCheck: string;
  history: Array<{
    timestamp: string;
    latencyMs: number;
  }>;
}

// Execution Log
export interface ArbExecution {
  id: string;
  opportunityId: string;
  timestamp: string;
  type: ArbType;
  symbol: string;
  buyExchange: string;
  sellExchange: string;
  buyOrderId: string;
  sellOrderId: string;
  intendedBuyPrice: number;
  actualBuyPrice: number;
  intendedSellPrice: number;
  actualSellPrice: number;
  size: number;
  slippage: number;
  slippagePct: number;
  expectedProfit: number;
  actualProfit: number;
  fees: number;
  netProfit: number;
  executionTimeMs: number;
  status: 'success' | 'partial' | 'failed';
  errorMessage?: string;
  legs: Array<{
    exchange: string;
    side: 'buy' | 'sell';
    status: 'filled' | 'partial' | 'failed';
    filledQty: number;
    avgPrice: number;
    latencyMs: number;
  }>;
}

// Dashboard State
export interface CrossExchangeState {
  priceMatrices: PriceMatrix[];
  opportunities: ArbOpportunity[];
  triangularPaths: TriangularArbPath[];
  cexDexSpreads: CexDexSpread[];
  spreadHistory: CexDexSpreadHistory[];
  latencyStats: ExchangeLatency[];
  executions: ArbExecution[];
  selectedSymbol: string;
  isLoading: boolean;
  error: string | null;
}
