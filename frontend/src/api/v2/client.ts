/**
 * API V2 Client
 * Type-safe API client for QUANT INDUSTRY V1
 * 
 * Uses the existing fetch wrapper pattern with full type safety.
 * 
 * @module api/v2/client
 */

import { api, ApiResponse } from '../client';
import type {
  // Health & System
  HealthStatus,
  SystemStatus,
  MemoryStatus,
  
  // Market Data
  MarketStatus,
  TickerPrice,
  Quote,
  OHLCVData,
  TechnicalIndicators,
  SectorData,
  MoversData,
  GetTickersParams,
  GetOHLCVParams,
  
  // Trading
  Signal,
  Position,
  Order,
  OrderRequest,
  OrderResult,
  ExecutionResult,
  TradeConfirmRequest,
  AIDecision,
  
  // Portfolio
  Portfolio,
  Holding,
  Performance,
  
  // Risk
  RiskMetrics,
  SafetyStatus,
  Exposure,
  KillSwitchStatus,
  KillSwitchRequest,
  
  // Brain/ML
  BrainStatus,
  TrainResult,
  MarketRegime,
  FeedbackStatus,
  GenerateSignalRequest,
  
  // Options
  OptionContract,
  GEXData,
  OptionsFlow,
  GetOptionsChainParams,
  
  // Backtest
  BacktestConfig,
  BacktestResult,
  Strategy,
  MonteCarloRequest,
  
  // Research
  NewsItem,
  Filing13F,
  EarningsData,
  GetNewsParams,
  
  // Settings
  Settings,
  ApiKeys,
} from './types';

// =====================================================================
// HELPER FUNCTIONS
// =====================================================================

type QueryParams = Record<string, string | number | boolean | undefined>;

/**
 * Build query string from params object
 */
function buildQueryString<T extends QueryParams>(params?: T): string {
  if (!params) return '';
  
  const entries = Object.entries(params)
    .filter(([, value]) => value !== undefined)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  
  return entries.length > 0 ? `?${entries.join('&')}` : '';
}

// =====================================================================
// HEALTH & SYSTEM API
// =====================================================================

/**
 * Health and system status endpoints
 */
export const healthApi = {
  /**
   * Check service health
   * @returns Health status including market and service states
   */
  check: (): Promise<ApiResponse<HealthStatus>> => 
    api.get<HealthStatus>('/api/health'),

  /**
   * Get system resource status
   * @returns CPU, memory, GPU metrics
   */
  getSystemStatus: (): Promise<ApiResponse<SystemStatus>> => 
    api.get<SystemStatus>('/api/system/status'),

  /**
   * Get memory usage
   * @returns Memory metrics
   */
  getMemoryStatus: (): Promise<ApiResponse<MemoryStatus>> => 
    api.get<MemoryStatus>('/api/system/memory'),
};

// =====================================================================
// MARKET DATA API
// =====================================================================

/**
 * Market data endpoints
 */
export const marketApi = {
  /**
   * Get market session status
   * @returns Current market hours and session info
   */
  getStatus: (): Promise<ApiResponse<MarketStatus>> => 
    api.get<MarketStatus>('/api/market/status'),

  /**
   * Get ticker prices for multiple symbols
   * @param params - Optional symbols to fetch (default: SPY,QQQ,DIA,IWM)
   * @returns Array of ticker prices
   */
  getTickers: (params?: GetTickersParams): Promise<ApiResponse<TickerPrice[]>> => 
    api.get<TickerPrice[]>(`/api/market/tickers${buildQueryString(params)}`),

  /**
   * Get detailed quote for a symbol
   * @param symbol - Stock symbol
   * @returns Detailed quote data
   */
  getQuote: (symbol: string): Promise<ApiResponse<Quote>> => 
    api.get<Quote>(`/api/market/quote/${encodeURIComponent(symbol)}`),

  /**
   * Get OHLCV candlestick data
   * @param symbol - Stock symbol
   * @param params - Interval and period options
   * @returns OHLCV chart data
   */
  getOHLCV: (symbol: string, params?: GetOHLCVParams): Promise<ApiResponse<OHLCVData>> => 
    api.get<OHLCVData>(`/api/charts/ohlcv/${encodeURIComponent(symbol)}${buildQueryString(params)}`),

  /**
   * Get technical indicators for a symbol
   * @param symbol - Stock symbol
   * @param period - Optional period (default: 1Y)
   * @returns Technical indicator values
   */
  getIndicators: (symbol: string, period?: string): Promise<ApiResponse<TechnicalIndicators>> => 
    api.get<TechnicalIndicators>(`/api/charts/indicators/${encodeURIComponent(symbol)}${buildQueryString({ period })}`),

  /**
   * Get sector performance
   * @returns Array of sector performance data
   */
  getSectors: (): Promise<ApiResponse<SectorData[]>> => 
    api.get<SectorData[]>('/api/market/sectors'),

  /**
   * Get top market movers
   * @returns Gainers and losers
   */
  getMovers: (): Promise<ApiResponse<MoversData>> => 
    api.get<MoversData>('/api/market/movers'),
};

// =====================================================================
// TRADING SIGNALS API
// =====================================================================

/**
 * Trading signals endpoints
 */
export const signalsApi = {
  /**
   * Get all signals
   * @returns Array of all signals
   */
  getAll: (): Promise<ApiResponse<Signal[]>> => 
    api.get<Signal[]>('/api/signals'),

  /**
   * Get active signals only
   * @returns Array of active signals
   */
  getActive: (): Promise<ApiResponse<Signal[]>> => 
    api.get<Signal[]>('/api/signals/active'),

  /**
   * Execute a signal (create order)
   * @param signalId - Signal identifier
   * @returns Execution result
   */
  execute: (signalId: string): Promise<ApiResponse<ExecutionResult>> => 
    api.post<ExecutionResult>(`/api/signals/${encodeURIComponent(signalId)}/execute`),

  /**
   * Dismiss a signal
   * @param signalId - Signal identifier
   */
  dismiss: (signalId: string): Promise<ApiResponse<void>> => 
    api.post<void>(`/api/signals/${encodeURIComponent(signalId)}/dismiss`),
};

// =====================================================================
// TRADING ORDERS API
// =====================================================================

/**
 * Trading orders endpoints
 */
export const ordersApi = {
  /**
   * Get all orders
   * @returns Array of orders
   */
  getAll: (): Promise<ApiResponse<Order[]>> => 
    api.get<Order[]>('/api/orders'),

  /**
   * Submit a new order
   * @param order - Order request details
   * @returns Order result
   */
  submit: (order: OrderRequest): Promise<ApiResponse<OrderResult>> => 
    api.post<OrderResult>('/api/orders', order),

  /**
   * Cancel an order
   * @param orderId - Order identifier
   */
  cancel: (orderId: string): Promise<ApiResponse<void>> => 
    api.delete<void>(`/api/orders/${encodeURIComponent(orderId)}`),

  /**
   * Request AI trade confirmation
   * @param request - Trade details for AI analysis
   * @returns AI decision
   */
  confirmWithAI: (request: TradeConfirmRequest): Promise<ApiResponse<AIDecision>> => 
    api.post<AIDecision>('/api/confirm-trade', request),
};

// =====================================================================
// POSITIONS API
// =====================================================================

/**
 * Positions endpoints
 */
export const positionsApi = {
  /**
   * Get all open positions
   * @returns Array of positions
   */
  getAll: (): Promise<ApiResponse<Position[]>> => 
    api.get<Position[]>('/api/positions'),
};

// =====================================================================
// PORTFOLIO API
// =====================================================================

/**
 * Portfolio endpoints
 */
export const portfolioApi = {
  /**
   * Get portfolio overview
   * @returns Portfolio summary
   */
  get: (): Promise<ApiResponse<Portfolio>> => 
    api.get<Portfolio>('/api/portfolio'),

  /**
   * Get portfolio holdings
   * @returns Array of holdings
   */
  getHoldings: (): Promise<ApiResponse<Holding[]>> => 
    api.get<Holding[]>('/api/portfolio/holdings'),

  /**
   * Get performance metrics
   * @returns Performance statistics
   */
  getPerformance: (): Promise<ApiResponse<Performance>> => 
    api.get<Performance>('/api/portfolio/performance'),
};

// =====================================================================
// RISK API
// =====================================================================

/**
 * Risk management endpoints
 */
export const riskApi = {
  /**
   * Get risk metrics
   * @returns Risk metrics
   */
  getMetrics: (): Promise<ApiResponse<RiskMetrics>> => 
    api.get<RiskMetrics>('/api/risk/metrics'),

  /**
   * Get safety status
   * @returns Safety status with breaches/warnings
   */
  getSafetyStatus: (): Promise<ApiResponse<SafetyStatus>> => 
    api.get<SafetyStatus>('/api/risk/safety'),

  /**
   * Get exposure breakdown
   * @returns Exposure data
   */
  getExposure: (): Promise<ApiResponse<Exposure>> => 
    api.get<Exposure>('/api/risk/exposure'),

  /**
   * Get kill switch status
   * @returns Kill switch state
   */
  getKillSwitchStatus: (): Promise<ApiResponse<KillSwitchStatus>> => 
    api.get<KillSwitchStatus>('/api/kill-switch'),

  /**
   * Activate kill switch (emergency stop)
   * @param request - Optional reason
   */
  activateKillSwitch: (request?: KillSwitchRequest): Promise<ApiResponse<void>> => 
    api.post<void>('/api/kill-switch/activate', request),

  /**
   * Deactivate kill switch
   */
  deactivateKillSwitch: (): Promise<ApiResponse<void>> => 
    api.post<void>('/api/kill-switch/deactivate'),
};

// =====================================================================
// BRAIN/ML API
// =====================================================================

/**
 * ML/AI Brain endpoints
 */
export const brainApi = {
  /**
   * Get brain status
   * @returns Brain status and metrics
   */
  getStatus: (): Promise<ApiResponse<BrainStatus>> => 
    api.get<BrainStatus>('/api/brain-v6/status'),

  /**
   * Get brain-generated signals
   * @returns Array of signals
   */
  getSignals: (): Promise<ApiResponse<Signal[]>> => 
    api.get<Signal[]>('/api/brain-v6/signals'),

  /**
   * Generate signal for a symbol
   * @param request - Symbol to analyze
   * @returns Generated signal
   */
  generateSignal: (request: GenerateSignalRequest): Promise<ApiResponse<Signal>> => 
    api.post<Signal>('/api/brain-v6/generate-signal', request),

  /**
   * Train the brain model
   * @returns Training result
   */
  train: (): Promise<ApiResponse<TrainResult>> => 
    api.post<TrainResult>('/api/brain-v6/train'),

  /**
   * Get brain configuration
   * @returns Current config
   */
  getConfig: (): Promise<ApiResponse<Record<string, unknown>>> => 
    api.get<Record<string, unknown>>('/api/brain-v6/config'),

  /**
   * Update brain configuration
   * @param config - New configuration values
   */
  updateConfig: (config: Record<string, unknown>): Promise<ApiResponse<void>> => 
    api.post<void>('/api/brain-v6/config', config),

  /**
   * Get current market regime
   * @returns Market regime classification
   */
  getMarketRegime: (): Promise<ApiResponse<MarketRegime>> => 
    api.get<MarketRegime>('/api/ml/regime'),

  /**
   * Get feedback loop status
   * @returns Feedback learning status
   */
  getFeedbackStatus: (): Promise<ApiResponse<FeedbackStatus>> => 
    api.get<FeedbackStatus>('/api/feedback/status'),
};

// =====================================================================
// OPTIONS API
// =====================================================================

/**
 * Options chain and flow endpoints
 */
export const optionsApi = {
  /**
   * Get options chain for a symbol
   * @param symbol - Underlying symbol
   * @param params - Optional filters
   * @returns Array of option contracts
   */
  getChain: (symbol: string, params?: GetOptionsChainParams): Promise<ApiResponse<OptionContract[]>> => 
    api.get<OptionContract[]>(`/api/options/chain/${encodeURIComponent(symbol)}${buildQueryString(params)}`),

  /**
   * Get gamma exposure (GEX) data
   * @param symbol - Stock symbol
   * @returns GEX data
   */
  getGEX: (symbol: string): Promise<ApiResponse<GEXData>> => 
    api.get<GEXData>(`/api/gex/${encodeURIComponent(symbol)}`),

  /**
   * Get options flow activity
   * @returns Array of flow records
   */
  getFlow: (): Promise<ApiResponse<OptionsFlow[]>> => 
    api.get<OptionsFlow[]>('/api/options/flow'),
};

// =====================================================================
// BACKTEST API
// =====================================================================

/**
 * Backtesting endpoints
 */
export const backtestApi = {
  /**
   * Run a backtest
   * @param config - Backtest configuration
   * @returns Backtest results
   */
  run: (config: BacktestConfig): Promise<ApiResponse<BacktestResult>> => 
    api.post<BacktestResult>('/api/backtest/run', config),

  /**
   * Get available strategies
   * @returns Array of strategies
   */
  getStrategies: (): Promise<ApiResponse<Strategy[]>> => 
    api.get<Strategy[]>('/api/strategies'),

  /**
   * Run Monte Carlo simulation
   * @param request - Simulation parameters
   * @returns Simulation results
   */
  runMonteCarlo: (request: MonteCarloRequest): Promise<ApiResponse<Record<string, unknown>>> => 
    api.post<Record<string, unknown>>('/api/monte-carlo/run', request),
};

// =====================================================================
// RESEARCH API
// =====================================================================

/**
 * Research data endpoints
 */
export const researchApi = {
  /**
   * Get news articles
   * @param params - Optional symbol filter
   * @returns Array of news items
   */
  getNews: (params?: GetNewsParams): Promise<ApiResponse<NewsItem[]>> => 
    api.get<NewsItem[]>(`/api/news${buildQueryString(params)}`),

  /**
   * Get 13F filings for a symbol
   * @param symbol - Stock symbol
   * @returns Array of 13F filings
   */
  get13F: (symbol: string): Promise<ApiResponse<Filing13F[]>> => 
    api.get<Filing13F[]>(`/api/research/13f/${encodeURIComponent(symbol)}`),

  /**
   * Get earnings calendar
   * @returns Array of earnings data
   */
  getEarnings: (): Promise<ApiResponse<EarningsData[]>> => 
    api.get<EarningsData[]>('/api/research/earnings'),
};

// =====================================================================
// SETTINGS API
// =====================================================================

/**
 * Settings endpoints
 */
export const settingsApi = {
  /**
   * Get application settings
   * @returns Current settings
   */
  get: (): Promise<ApiResponse<Settings>> => 
    api.get<Settings>('/api/settings'),

  /**
   * Update application settings
   * @param settings - Settings to update
   * @returns Updated settings
   */
  update: (settings: Partial<Settings>): Promise<ApiResponse<Settings>> => 
    api.put<Settings>('/api/settings', settings),

  /**
   * Get API key status
   * @returns Which API keys are configured
   */
  getApiKeys: (): Promise<ApiResponse<ApiKeys>> => 
    api.get<ApiKeys>('/api/settings/api-keys'),
};

// =====================================================================
// UNIFIED EXPORT
// =====================================================================

/**
 * Unified API client with all endpoints organized by domain
 */
export const apiV2 = {
  health: healthApi,
  market: marketApi,
  signals: signalsApi,
  orders: ordersApi,
  positions: positionsApi,
  portfolio: portfolioApi,
  risk: riskApi,
  brain: brainApi,
  options: optionsApi,
  backtest: backtestApi,
  research: researchApi,
  settings: settingsApi,
} as const;

export default apiV2;
