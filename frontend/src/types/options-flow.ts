/**
 * Options Flow Module Types
 * QUANT_INDUSTRY_V1
 */

export type FlowDirection = 'bullish' | 'bearish' | 'neutral';
export type FlowType = 'sweep' | 'block' | 'split' | 'regular';
export type OptionSide = 'call' | 'put';
export type TradeAggressor = 'buy' | 'sell' | 'mid';

// Unusual Options Activity
export interface UnusualActivity {
  id: string;
  symbol: string;
  timestamp: string;
  optionType: OptionSide;
  strike: number;
  expiration: string;
  premium: number;
  volume: number;
  openInterest: number;
  volumeOIRatio: number;
  impliedVolatility: number;
  delta: number;
  flowType: FlowType;
  aggressor: TradeAggressor;
  spot: number;
  sentiment: FlowDirection;
  unusualScore: number;
  exchange: string;
}

// Gamma Exposure
export interface GammaExposureLevel {
  strike: number;
  callGamma: number;
  putGamma: number;
  netGamma: number;
  totalGamma: number;
  openInterest: number;
}

export interface GammaExposureProfile {
  symbol: string;
  spotPrice: number;
  totalNetGamma: number;
  gammaFlip: number;
  maxPainStrike: number;
  levels: GammaExposureLevel[];
  zeroGammaLevel: number;
  callWall: number;
  putWall: number;
  expectedMove: number;
  timestamp: string;
}

// Dark Pool
export interface DarkPoolPrint {
  id: string;
  symbol: string;
  timestamp: string;
  price: number;
  size: number;
  notional: number;
  exchange: string;
  condition: string;
  aboveAsk: boolean;
  belowBid: boolean;
  blockTrade: boolean;
  darkPoolType: 'dp' | 'block' | 'hidden';
}

export interface DarkPoolAccumulation {
  symbol: string;
  date: string;
  totalVolume: number;
  darkPoolVolume: number;
  darkPoolPct: number;
  netAccumulation: number;
  avgPrice: number;
  largestPrint: DarkPoolPrint;
  prints: DarkPoolPrint[];
}

// Smart Money / Institutional Flow
export interface InstitutionalFlow {
  id: string;
  symbol: string;
  timestamp: string;
  flowType: 'buy' | 'sell';
  size: number;
  notional: number;
  isBlock: boolean;
  isSweep: boolean;
  institution?: string;
  sentiment: FlowDirection;
  confidence: number;
}

export interface SmartMoneyMetrics {
  symbol: string;
  smartMoneyIndex: number;
  institutionalAccumulation: number;
  retailSentiment: FlowDirection;
  smartMoneySentiment: FlowDirection;
  divergence: number;
  flowImbalance: number;
  largeTraderActivity: number;
  timestamp: string;
}

// Flow Signals
export interface FlowSignal {
  id: string;
  symbol: string;
  timestamp: string;
  signalType: 'unusual_activity' | 'gamma_squeeze' | 'dark_pool_block' | 'smart_money_divergence' | 'sweep_alert';
  direction: FlowDirection;
  strength: number;
  description: string;
  details: Record<string, any>;
  alertLevel: 'info' | 'warning' | 'critical';
  expiresAt?: string;
}

// Dashboard State
export interface OptionsFlowState {
  unusualActivity: UnusualActivity[];
  gammaExposure: GammaExposureProfile | null;
  darkPoolPrints: DarkPoolPrint[];
  darkPoolAccumulation: DarkPoolAccumulation[];
  institutionalFlow: InstitutionalFlow[];
  smartMoneyMetrics: SmartMoneyMetrics[];
  flowSignals: FlowSignal[];
  selectedSymbol: string;
  isLoading: boolean;
  error: string | null;
}
