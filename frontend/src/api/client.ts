/**
 * API Client - Centralized HTTP client for backend communication
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export interface ApiError {
  status: number
  message: string
  code?: string
  details?: Record<string, unknown>
}

export interface ApiResponse<T> {
  data: T | null
  error: ApiError | null
  ok: boolean
}

class ApiClient {
  private baseUrl: string
  private defaultHeaders: Record<string, string>

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          ...this.defaultHeaders,
          ...options.headers,
        },
      })

      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}`
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorData.message || errorMessage
        } catch {
          // Use default error message
        }
        return {
          data: null,
          error: {
            status: response.status,
            message: errorMessage,
          },
          ok: false,
        }
      }

      const data = await response.json()
      return { data, error: null, ok: true }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Network error'
      return {
        data: null,
        error: { status: 0, message },
        ok: false,
      }
    }
  }

  async get<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'GET' })
  }

  async post<T>(endpoint: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async put<T>(endpoint: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }
}

export const api = new ApiClient()

// ==================== API ENDPOINTS ====================

// Health & System
export const healthApi = {
  check: () => api.get<HealthStatus>('/api/health'),
  getSystemStatus: () => api.get<SystemStatus>('/api/system/status'),
}

// Market Data
export const marketApi = {
  getTickers: (symbols: string = 'SPY,QQQ,DIA,IWM') =>
    api.get<MarketTicker[]>(`/api/market/tickers?symbols=${symbols}`),
  getQuote: (symbol: string) => api.get<Quote>(`/api/market/quote/${symbol}`),
  getQuotes: (symbols: string[]) => api.post<Record<string, Quote>>('/api/quotes', { symbols }),
  getHistorical: (symbol: string, timeframe: string = '1D', period: string = '1Y') =>
    api.get<HistoricalData>(`/api/charts/ohlcv/${symbol}?interval=${timeframe}&period=${period}`),
  getMarketStatus: () => api.get<MarketStatus>('/api/market/status'),
  getSectors: () => api.get<SectorData[]>('/api/market/sectors'),
  getMovers: () => api.get<MoversData>('/api/market/movers'),
}

// Trading Brain
export const brainApi = {
  getStatus: () => api.get<BrainStatus>('/api/brain-v6/status'),
  getSignals: () => api.get<Signal[]>('/api/brain-v6/signals'),
  generateSignal: (symbol: string) => api.post<Signal>('/api/brain-v6/generate-signal', { symbol }),
  train: () => api.post<TrainResult>('/api/brain-v6/train'),
  getAnalysis: (symbol: string) => api.get<Analysis>(`/api/brain-v6/analyze/${symbol}`),
}

// Feedback Loop
export const feedbackApi = {
  getStatus: () => api.get<FeedbackStatus>('/api/feedback/status'),
  recordTrade: (trade: TradeRecord) => api.post<void>('/api/feedback/record-trade', trade),
}

// Signals
export const signalsApi = {
  getAll: () => api.get<Signal[]>('/api/signals'),
  getActive: () => api.get<Signal[]>('/api/signals/active'),
  execute: (signalId: string) => api.post<ExecutionResult>(`/api/signals/${signalId}/execute`),
  dismiss: (signalId: string) => api.post<void>(`/api/signals/${signalId}/dismiss`),
}

// Positions & Portfolio
export const portfolioApi = {
  getPositions: () => api.get<Position[]>('/api/positions'),
  getPortfolio: () => api.get<Portfolio>('/api/portfolio'),
  getPerformance: () => api.get<Performance>('/api/portfolio/performance'),
  getHoldings: () => api.get<Holding[]>('/api/portfolio/holdings'),
}

// Trading
export const tradingApi = {
  submitOrder: (order: OrderRequest) => api.post<OrderResult>('/api/orders', order),
  cancelOrder: (orderId: string) => api.delete<void>(`/api/orders/${orderId}`),
  getOrders: () => api.get<Order[]>('/api/orders'),
  confirmTrade: (trade: TradeConfirmRequest) => api.post<AIDecision>('/api/confirm-trade', trade),
}

// Risk Management
export const riskApi = {
  getMetrics: () => api.get<RiskMetrics>('/api/risk/metrics'),
  getExposure: () => api.get<Exposure>('/api/risk/exposure'),
  getSafetyStatus: () => api.get<SafetyStatus>('/api/risk/safety'),
}

// Backtesting
export const backtestApi = {
  run: (config: BacktestConfig) => api.post<BacktestResult>('/api/backtest/run', config),
  getStrategies: () => api.get<Strategy[]>('/api/strategies'),
  getResults: (id: string) => api.get<BacktestResult>(`/api/backtest/results/${id}`),
}

// Options
export const optionsApi = {
  getChain: (symbol: string) => api.get<OptionChain[]>(`/api/options/chain/${symbol}`),
  getGEX: (symbol: string) => api.get<GEXData>(`/api/gex/${symbol}`),
  getFlow: () => api.get<OptionsFlow[]>('/api/options/flow'),
}

// Research
export const researchApi = {
  get13F: (symbol: string) => api.get<Filing13F[]>(`/api/research/13f/${symbol}`),
  getSECFilings: (symbol: string) => api.get<SECFiling[]>(`/api/research/sec/${symbol}`),
  getDarkPool: (symbol: string) => api.get<DarkPoolData>(`/api/research/darkpool/${symbol}`),
  getEarnings: (symbol: string) => api.get<EarningsData>(`/api/research/earnings/${symbol}`),
  getNews: (symbol?: string) => api.get<NewsItem[]>(`/api/news${symbol ? `?symbol=${symbol}` : ''}`),
}

// Settings
export const settingsApi = {
  get: () => api.get<Settings>('/api/settings'),
  update: (settings: Partial<Settings>) => api.put<Settings>('/api/settings', settings),
  getApiKeys: () => api.get<ApiKeys>('/api/settings/api-keys'),
  updateApiKey: (key: string, value: string) =>
    api.put<void>('/api/settings/api-keys', { key, value }),
}

// Screener
export const screenerApi = {
  scan: (filters: ScreenerFilters) => api.post<ScreenerResult[]>('/api/screener/scan', filters),
  getPresets: () => api.get<ScreenerPreset[]>('/api/screener/presets'),
}

// Neural/ML
export const neuralApi = {
  getPrediction: (symbol: string) => api.get<Prediction>(`/api/ml/predict/${symbol}`),
  getRegime: () => api.get<MarketRegime>('/api/ml/regime'),
  getAnalysis: (symbol: string) => api.get<NeuralAnalysis>(`/api/neural/analyze/${symbol}`),
}

// ==================== TYPE DEFINITIONS ====================

export interface HealthStatus {
  status: string
  market: MarketStatus
  services: Record<string, boolean>
  uptime: number
}

export interface SystemStatus {
  cpu_percent: number
  memory_percent: number
  gpu_available: boolean
  gpu_percent?: number
  active_connections: number
  uptime_hours: number
}

export interface MarketTicker {
  symbol: string
  price: number
  change: number
  change_pct: number
  volume: number
  bid?: number
  ask?: number
}

export interface Quote {
  symbol: string
  price: number
  bid: number
  ask: number
  change: number
  change_pct: number
  volume: number
  high: number
  low: number
  open: number
  prev_close: number
  source: string
  timestamp: string
}

export interface HistoricalData {
  symbol: string
  timeframe: string
  data: Array<{
    date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
  }>
}

export interface MarketStatus {
  session: 'pre_market' | 'regular' | 'after_hours' | 'closed'
  is_open: boolean
  is_pre_market: boolean
  is_after_hours: boolean
  next_open?: string
  next_close?: string
}

export interface BrainStatus {
  available: boolean
  device: string
  is_trained: boolean
  current_regime: string
  auto_train_enabled: boolean
  training_step: number
  total_trades: number
  metrics: {
    win_rate: number
    total_pnl: number
    profit_factor: number
  }
  strategies: Array<{
    name: string
    weight: number
    win_rate: number
  }>
}

export interface FeedbackStatus {
  phase: string
  total_trades: number
  win_rate: number
  profit_factor: number
  sharpe_ratio: number
  convergence_progress: Record<string, number>
  is_converged: boolean
}

export interface Signal {
  id: string
  symbol: string
  direction: 'LONG' | 'SHORT'
  confidence: number
  strategy: string
  entry_price: number
  stop_loss: number
  take_profit: number
  risk_reward: number
  timeframe: string
  regime_alignment: boolean
  timestamp: string
  status: 'active' | 'executed' | 'dismissed' | 'expired'
}

export interface Position {
  id: string
  symbol: string
  side: 'long' | 'short'
  quantity: number
  entry_price: number
  current_price: number
  pnl: number
  pnl_pct: number
  opened_at: string
}

export interface Portfolio {
  equity: number
  cash: number
  buying_power: number
  day_pnl: number
  day_pnl_pct: number
  total_pnl: number
  total_pnl_pct: number
  positions_count: number
}

export interface Performance {
  total_return: number
  total_return_pct: number
  win_rate: number
  profit_factor: number
  sharpe_ratio: number
  sortino_ratio: number
  max_drawdown: number
  avg_win: number
  avg_loss: number
  total_trades: number
  winning_trades: number
  losing_trades: number
}

export interface Holding {
  symbol: string
  shares: number
  cost_basis: number
  current_price: number
  value: number
  pnl: number
  pnl_pct: number
  weight: number
  day_change: number
}

export interface RiskMetrics {
  var_95: number
  current_drawdown: number
  max_position_exposure: number
  sector_concentration: number
  daily_pnl: number
  risk_score: number
}

export interface Exposure {
  gross: number
  net: number
  long: number
  short: number
  by_sector: Record<string, number>
}

export interface SafetyStatus {
  is_safe: boolean
  breaches: string[]
  warnings: string[]
  daily_loss: number
  max_daily_loss: number
  current_drawdown: number
  max_drawdown_limit: number
}

export interface OrderRequest {
  symbol: string
  side: 'buy' | 'sell'
  quantity: number
  order_type: 'market' | 'limit' | 'stop' | 'stop_limit'
  limit_price?: number
  stop_price?: number
  time_in_force?: 'day' | 'gtc' | 'ioc' | 'fok'
}

export interface OrderResult {
  id: string
  status: 'submitted' | 'filled' | 'partial' | 'rejected' | 'cancelled'
  filled_qty: number
  filled_price: number
  message?: string
}

export interface Order {
  id: string
  symbol: string
  side: 'buy' | 'sell'
  quantity: number
  filled_qty: number
  order_type: string
  status: string
  limit_price?: number
  stop_price?: number
  created_at: string
  filled_at?: string
}

export interface TradeConfirmRequest {
  ticker: string
  direction: string
  entry_price: number
  target: number
  stop_loss: number
}

export interface AIDecision {
  approved: boolean
  score: number
  confidence: number
  components: Record<string, unknown>
  recommendation: string
  analysis: string
}

export interface BacktestConfig {
  strategy: string
  symbol: string
  start_date: string
  end_date: string
  initial_capital: number
  params?: Record<string, unknown>
}

export interface BacktestResult {
  total_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  trade_count: number
  profit_factor: number
  equity_curve: Array<{ date: string; equity: number }>
  trades: Array<Record<string, unknown>>
}

export interface Strategy {
  id: string
  name: string
  description: string
  type: string
  params: Record<string, unknown>
}

export interface OptionChain {
  expiration: string
  strike: number
  option_type: 'call' | 'put'
  bid: number
  ask: number
  iv: number
  delta: number
  gamma: number
  theta: number
  vega: number
  oi: number
  volume: number
}

export interface GEXData {
  symbol: string
  total_gex: number
  call_gex: number
  put_gex: number
  key_levels: Array<{ strike: number; gex: number }>
  flip_point: number
}

export interface OptionsFlow {
  id: string
  symbol: string
  type: 'call' | 'put'
  side: 'buy' | 'sell'
  sentiment: 'bullish' | 'bearish'
  strike: number
  expiry: string
  premium: number
  contracts: number
  is_unusual: boolean
  is_sweep: boolean
  timestamp: string
}

export interface Filing13F {
  holder: string
  shares: number
  value: number
  change_pct: number
  report_date: string
}

export interface SECFiling {
  type: string
  date: string
  description: string
  url: string
}

export interface DarkPoolData {
  symbol: string
  short_volume: number
  short_pct: number
  dark_pool_volume: number
  dark_pool_pct: number
  timestamp: string
}

export interface EarningsData {
  symbol: string
  report_date: string
  eps_estimate: number
  eps_actual?: number
  revenue_estimate: number
  revenue_actual?: number
  surprise_pct?: number
}

export interface NewsItem {
  id: string
  title: string
  summary: string
  source: string
  url: string
  symbols: string[]
  sentiment?: 'positive' | 'negative' | 'neutral'
  published_at: string
}

export interface Settings {
  theme: 'dark' | 'light'
  notifications_enabled: boolean
  auto_refresh_interval: number
  default_order_type: string
  risk_params: Record<string, number>
}

export interface ApiKeys {
  alpaca: boolean
  tradier: boolean
  polygon: boolean
}

export interface ScreenerFilters {
  min_price?: number
  max_price?: number
  min_volume?: number
  min_change_pct?: number
  max_change_pct?: number
  sector?: string
  signal_type?: string
}

export interface ScreenerResult {
  symbol: string
  price: number
  change_pct: number
  volume: number
  rsi: number
  trend: string
  signal: string
}

export interface ScreenerPreset {
  id: string
  name: string
  filters: ScreenerFilters
}

export interface Prediction {
  symbol: string
  direction: 'up' | 'down' | 'neutral'
  confidence: number
  price_target: number
  timeframe: string
}

export interface MarketRegime {
  regime: 'trending' | 'ranging' | 'volatile' | 'quiet'
  confidence: number
  volatility: number
  trend_strength: number
}

export interface NeuralAnalysis {
  symbol: string
  overall_score: number
  technical_score: number
  sentiment_score: number
  regime_alignment: boolean
  recommendation: string
  key_factors: string[]
}

export interface TrainResult {
  success: boolean
  epochs: number
  final_loss: number
  metrics: Record<string, number>
}

export interface TradeRecord {
  symbol: string
  direction: string
  entry_price: number
  exit_price: number
  quantity: number
  pnl: number
  strategy: string
}

export interface Analysis {
  symbol: string
  signals: Signal[]
  regime: string
  confidence: number
  recommendation: string
}

export interface ExecutionResult {
  success: boolean
  order_id?: string
  message: string
}

export interface SectorData {
  name: string
  change_pct: number
  weight: number
}

export interface MoversData {
  gainers: MoverStock[]
  losers: MoverStock[]
}

export interface MoverStock {
  symbol: string
  price: number
  change_pct: number
  volume: number
}

// ==================== DECISION INTELLIGENCE TYPES ====================

export interface ControlPlaneStatus {
  mode: 'shadow' | 'paper' | 'live' | 'disabled'
  is_active: boolean
  kill_switch_engaged: boolean
  decisions_today: number
  trades_today: number
  shadow_decisions_today: number
  components_registered: string[]
  safety_checks_count: number
  contexts_cached: number
}

export interface DecisionContext {
  context_id: string
  timestamp: string
  symbol: string
  regime: string
  regime_confidence: number
  signal_direction: 'LONG' | 'SHORT' | null
  signal_confidence: number
  signal_source: string
  risk_approved: boolean
  risk_adjusted_size: number
  risk_warnings: string[]
  execution_allowed: boolean
  execution_mode: string
  decisions: Array<{
    timestamp: string
    component: string
    decision: string
    reason: string
    data: Record<string, unknown>
  }>
}

export interface DecisionTraceStats {
  total_nodes: number
  total_edges: number
  outcomes: Record<string, number>
  components: Record<string, number>
  graph_available: boolean
}

export interface ExitRecommendation {
  action: 'hold' | 'exit'
  reason: string
  confidence: number
  expected_value_hold: number
  expected_value_exit: number
  state: {
    regime: string
    time_bucket: number
    pnl_bucket: number
    volatility_bucket: number
  }
  is_shadow: boolean
}

export interface ShadowComponent {
  component_id: string
  component_name: string
  version: string
  status: 'shadow' | 'parallel' | 'candidate' | 'promoted' | 'rejected'
  created_at: string
  decisions_count: number
  correct_decisions: number
  accuracy: number
  total_shadow_pnl: number
  live_comparison_count: number
  agreement_rate: number
  outperformance_rate: number
  promotion_score: number
}

export interface SelfImprovementStatus {
  current_phase: string
  active_cycle: null | {
    cycle_id: string
    trigger: string
    started_at: string
    phase: string
    component_name: string
    old_version: string
    new_version: string | null
  }
  consecutive_failures: number
  total_cycles: number
  successful_cycles: number
  config: {
    drift_threshold: number
    validation_days: number
    improvement_threshold: number
  }
}

// ==================== DECISION INTELLIGENCE API ====================

export const decisionIntelApi = {
  // Control Plane
  getControlPlaneStatus: () => api.get<ControlPlaneStatus>('/api/decision-intelligence/control-plane/status'),
  getControlPlaneHealth: () => api.get<Record<string, unknown>>('/api/decision-intelligence/control-plane/health'),
  engageKillSwitch: (reason: string) => 
    api.post<void>('/api/decision-intelligence/control-plane/kill-switch', { reason }),
  releaseKillSwitch: (reason: string) => 
    api.post<void>('/api/decision-intelligence/control-plane/kill-switch/release', { reason }),

  // Decision Trace
  getDecisionTraceStats: () => api.get<DecisionTraceStats>('/api/decision-intelligence/trace/stats'),
  getDecisionPath: (contextId: string) => 
    api.get<Array<Record<string, unknown>>>(`/api/decision-intelligence/trace/path/${contextId}`),
  getFailurePatterns: (days?: number) => 
    api.get<Array<Record<string, unknown>>>(`/api/decision-intelligence/trace/failure-patterns${days ? `?days=${days}` : ''}`),
  getSuccessPatterns: (days?: number) => 
    api.get<Array<Record<string, unknown>>>(`/api/decision-intelligence/trace/success-patterns${days ? `?days=${days}` : ''}`),

  // Exit Value Learning
  getExitRecommendation: (positionId: string, currentState: Record<string, unknown>) =>
    api.post<ExitRecommendation>(`/api/decision-intelligence/exit-learning/recommend/${positionId}`, currentState),
  getExitLearnerStats: () => api.get<Record<string, unknown>>('/api/decision-intelligence/exit-learning/stats'),
  getValueSurface: (regime: string, direction?: string) =>
    api.get<Array<Record<string, unknown>>>(`/api/decision-intelligence/exit-learning/value-surface/${regime}${direction ? `?direction=${direction}` : ''}`),

  // Shadow Mode
  getShadowComponents: () => api.get<ShadowComponent[]>('/api/decision-intelligence/shadow/components'),
  getShadowReport: (componentId: string) => 
    api.get<Record<string, unknown>>(`/api/decision-intelligence/shadow/report/${componentId}`),
  getShadowComparison: () => api.get<Record<string, unknown>>('/api/decision-intelligence/shadow/comparison'),

  // Self Improvement
  getSelfImprovementStatus: () => api.get<SelfImprovementStatus>('/api/decision-intelligence/self-improvement/status'),
  getImprovementHistory: (limit?: number) =>
    api.get<Array<Record<string, unknown>>>(`/api/decision-intelligence/self-improvement/history${limit ? `?limit=${limit}` : ''}`),
  triggerImprovement: (componentName: string) =>
    api.post<Record<string, unknown>>('/api/decision-intelligence/self-improvement/trigger', { component_name: componentName }),
}

// ==================== DATA INTEGRITY API ====================

export interface DataMode {
  mode: 'live' | 'paper' | 'backtest' | 'simulation'
  available: boolean
  modes: Record<string, string>
  current_description: string
  quality_stats: Record<string, unknown>
  timestamp: string
}

export const dataIntegrityApi = {
  getDataMode: () => api.get<DataMode>('/api/data-mode'),
  setDataMode: (mode: string, reason?: string) => 
    api.post<DataMode>('/api/data-mode', { mode, reason }),
  getIntegrityStatus: () => api.get<Record<string, unknown>>('/api/data-integrity/status'),
  getPriceWithProvenance: (symbol: string) => 
    api.get<Record<string, unknown>>(`/api/data-integrity/price/${symbol}`),
  getStalenessStatus: () => api.get<Record<string, unknown>>('/api/data/staleness'),
}
