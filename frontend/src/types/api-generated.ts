/**
 * API Generated Types
 * Auto-generated from OpenAPI spec at docs/openapi.yaml
 * 
 * @generated
 * @version 1.0.0
 */

// =====================================================================
// ENUM TYPES
// =====================================================================

/**
 * Health status of the service
 */
export type HealthStatusType = 'healthy' | 'degraded' | 'unhealthy';

/**
 * Market session type
 */
export type MarketSession = 'pre_market' | 'regular' | 'after_hours' | 'closed';

/**
 * Chart interval for OHLCV data
 */
export type ChartInterval = '1D' | '1H' | '5M' | '15M' | '1W';

/**
 * Chart period for historical data
 */
export type ChartPeriod = '1M' | '3M' | '6M' | '1Y' | '2Y' | 'ALL';

/**
 * Trading signal direction
 */
export type SignalDirection = 'LONG' | 'SHORT';

/**
 * Signal status
 */
export type SignalStatus = 'active' | 'executed' | 'dismissed' | 'expired';

/**
 * Position side
 */
export type PositionSide = 'long' | 'short';

/**
 * Order side
 */
export type OrderSide = 'buy' | 'sell';

/**
 * Order type
 */
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit';

/**
 * Order status
 */
export type OrderStatus = 'submitted' | 'filled' | 'partial' | 'rejected' | 'cancelled';

/**
 * Time in force for orders
 */
export type TimeInForce = 'day' | 'gtc' | 'ioc' | 'fok';

/**
 * Option type filter
 */
export type OptionTypeFilter = 'ALL' | 'CALL' | 'PUT';

/**
 * Option contract type
 */
export type OptionType = 'call' | 'put';

/**
 * Options flow side
 */
export type OptionsFlowSide = 'buy' | 'sell';

/**
 * Options flow sentiment
 */
export type OptionsFlowSentiment = 'bullish' | 'bearish';

/**
 * Market regime classification
 */
export type MarketRegimeType = 'trending' | 'ranging' | 'volatile' | 'quiet';

/**
 * News sentiment
 */
export type NewsSentiment = 'positive' | 'negative' | 'neutral';

/**
 * Application theme
 */
export type Theme = 'dark' | 'light';

// =====================================================================
// HEALTH & SYSTEM SCHEMAS
// =====================================================================

/**
 * Health check response
 */
export interface HealthStatus {
  /** Current health status */
  status: HealthStatusType;
  /** Market status information */
  market?: MarketStatus;
  /** Service availability map */
  services?: Record<string, boolean>;
  /** Timestamp of health check */
  timestamp?: string;
}

/**
 * System status with resource metrics
 */
export interface SystemStatus {
  /** CPU usage percentage */
  cpu_percent?: number;
  /** Memory usage percentage */
  memory_percent?: number;
  /** Whether GPU is available */
  gpu_available?: boolean;
  /** GPU usage percentage (if available) */
  gpu_percent?: number;
  /** Number of active WebSocket connections */
  active_connections?: number;
  /** System uptime in hours */
  uptime_hours?: number;
}

/**
 * Memory status response
 */
export interface MemoryStatus {
  /** Total memory in MB */
  total_mb?: number;
  /** Used memory in MB */
  used_mb?: number;
  /** Memory usage percentage */
  percent?: number;
}

// =====================================================================
// MARKET DATA SCHEMAS
// =====================================================================

/**
 * Market session status
 */
export interface MarketStatus {
  /** Current market session */
  session?: MarketSession;
  /** Whether market is currently open */
  is_open?: boolean;
  /** Whether currently in pre-market hours */
  is_pre_market?: boolean;
  /** Whether currently in after-hours */
  is_after_hours?: boolean;
  /** Whether today is a weekend */
  is_weekend?: boolean;
  /** Whether today is a market holiday */
  is_holiday?: boolean;
  /** Next market open time (ISO 8601) */
  next_open?: string;
  /** Next market close time (ISO 8601) */
  next_close?: string;
}

/**
 * Basic ticker price information
 */
export interface TickerPrice {
  /** Stock symbol */
  symbol?: string;
  /** Current price */
  price?: number;
  /** Price change from previous close */
  change?: number;
  /** Percentage change from previous close */
  change_pct?: number;
  /** Trading volume */
  volume?: number;
}

/**
 * Detailed quote information
 */
export interface Quote {
  /** Stock symbol */
  symbol?: string;
  /** Current price */
  price?: number;
  /** Best bid price */
  bid?: number;
  /** Best ask price */
  ask?: number;
  /** Price change from previous close */
  change?: number;
  /** Percentage change from previous close */
  change_pct?: number;
  /** Trading volume */
  volume?: number;
  /** Day high */
  high?: number;
  /** Day low */
  low?: number;
  /** Opening price */
  open?: number;
  /** Previous close price */
  prev_close?: number;
  /** Data source identifier */
  source?: string;
  /** Quote timestamp (ISO 8601) */
  timestamp?: string;
}

/**
 * Single OHLCV data point
 */
export interface OHLCVDataPoint {
  /** Date/time of the candle */
  date?: string;
  /** Opening price */
  open?: number;
  /** Highest price */
  high?: number;
  /** Lowest price */
  low?: number;
  /** Closing price */
  close?: number;
  /** Volume */
  volume?: number;
}

/**
 * OHLCV chart data response
 */
export interface OHLCVData {
  /** Stock symbol */
  symbol?: string;
  /** Data interval */
  interval?: string;
  /** Data period */
  period?: string;
  /** Number of data points */
  data_points?: number;
  /** OHLCV candle data */
  data?: OHLCVDataPoint[];
}

/**
 * Technical indicator values
 */
export interface TechnicalIndicatorValues {
  /** 20-period Simple Moving Average */
  sma_20?: number;
  /** 50-period Simple Moving Average */
  sma_50?: number;
  /** 200-period Simple Moving Average */
  sma_200?: number;
  /** Relative Strength Index (14-period) */
  rsi?: number;
  /** MACD line value */
  macd?: number;
  /** MACD signal line value */
  macd_signal?: number;
  /** Average Directional Index */
  adx?: number;
  /** Average True Range */
  atr?: number;
  /** Bollinger Band upper */
  bb_upper?: number;
  /** Bollinger Band middle */
  bb_middle?: number;
  /** Bollinger Band lower */
  bb_lower?: number;
}

/**
 * Technical indicators response
 */
export interface TechnicalIndicators {
  /** Stock symbol */
  symbol?: string;
  /** Calculated indicator values */
  indicators?: TechnicalIndicatorValues;
}

/**
 * Sector performance data
 */
export interface SectorData {
  /** Sector name */
  name?: string;
  /** Percentage change */
  change_pct?: number;
  /** Sector weight in index */
  weight?: number;
}

/**
 * Top market movers response
 */
export interface MoversData {
  /** Top gaining stocks */
  gainers?: TickerPrice[];
  /** Top losing stocks */
  losers?: TickerPrice[];
}

// =====================================================================
// TRADING SCHEMAS
// =====================================================================

/**
 * Trading signal
 */
export interface Signal {
  /** Unique signal identifier */
  id?: string;
  /** Stock symbol */
  symbol?: string;
  /** Trade direction */
  direction?: SignalDirection;
  /** Signal confidence (0-1) */
  confidence?: number;
  /** Strategy that generated the signal */
  strategy?: string;
  /** Suggested entry price */
  entry_price?: number;
  /** Stop loss price */
  stop_loss?: number;
  /** Take profit target */
  take_profit?: number;
  /** Risk/reward ratio */
  risk_reward?: number;
  /** Signal timeframe */
  timeframe?: string;
  /** Whether signal aligns with current market regime */
  regime_alignment?: boolean;
  /** Signal generation timestamp (ISO 8601) */
  timestamp?: string;
  /** Current signal status */
  status?: SignalStatus;
}

/**
 * Open position
 */
export interface Position {
  /** Unique position identifier */
  id?: string;
  /** Stock symbol */
  symbol?: string;
  /** Position side */
  side?: PositionSide;
  /** Number of shares */
  quantity?: number;
  /** Average entry price */
  entry_price?: number;
  /** Current market price */
  current_price?: number;
  /** Unrealized P&L */
  pnl?: number;
  /** Unrealized P&L percentage */
  pnl_pct?: number;
  /** Position open timestamp (ISO 8601) */
  opened_at?: string;
}

/**
 * Trading order
 */
export interface Order {
  /** Unique order identifier */
  id?: string;
  /** Stock symbol */
  symbol?: string;
  /** Order side */
  side?: OrderSide;
  /** Order quantity */
  quantity?: number;
  /** Filled quantity */
  filled_qty?: number;
  /** Order type */
  order_type?: string;
  /** Order status */
  status?: string;
  /** Limit price (for limit orders) */
  limit_price?: number;
  /** Stop price (for stop orders) */
  stop_price?: number;
  /** Order creation timestamp (ISO 8601) */
  created_at?: string;
  /** Order fill timestamp (ISO 8601) */
  filled_at?: string;
}

/**
 * Order submission request
 */
export interface OrderRequest {
  /** Stock symbol */
  symbol: string;
  /** Order side */
  side: OrderSide;
  /** Order quantity */
  quantity: number;
  /** Order type */
  order_type: OrderType;
  /** Limit price (required for limit/stop_limit orders) */
  limit_price?: number;
  /** Stop price (required for stop/stop_limit orders) */
  stop_price?: number;
  /** Time in force (defaults to 'day') */
  time_in_force?: TimeInForce;
}

/**
 * Order submission result
 */
export interface OrderResult {
  /** Order identifier */
  id?: string;
  /** Order status after submission */
  status?: OrderStatus;
  /** Quantity filled immediately */
  filled_qty?: number;
  /** Fill price (if filled) */
  filled_price?: number;
  /** Status message */
  message?: string;
}

/**
 * Signal execution result
 */
export interface ExecutionResult {
  /** Whether execution was successful */
  success?: boolean;
  /** Created order identifier */
  order_id?: string;
  /** Status message */
  message?: string;
}

/**
 * AI trade confirmation request
 */
export interface TradeConfirmRequest {
  /** Stock symbol */
  ticker: string;
  /** Trade direction (LONG/SHORT) */
  direction: string;
  /** Entry price */
  entry_price: number;
  /** Target price */
  target: number;
  /** Stop loss price */
  stop_loss: number;
}

/**
 * AI decision response
 */
export interface AIDecision {
  /** Whether trade is approved */
  approved?: boolean;
  /** Decision score (0-100) */
  score?: number;
  /** Confidence level (0-1) */
  confidence?: number;
  /** Component scores breakdown */
  components?: Record<string, unknown>;
  /** AI recommendation */
  recommendation?: string;
  /** Detailed analysis */
  analysis?: string;
}

// =====================================================================
// PORTFOLIO SCHEMAS
// =====================================================================

/**
 * Portfolio overview
 */
export interface Portfolio {
  /** Total portfolio equity */
  equity?: number;
  /** Available cash */
  cash?: number;
  /** Buying power */
  buying_power?: number;
  /** Day's P&L */
  day_pnl?: number;
  /** Day's P&L percentage */
  day_pnl_pct?: number;
  /** Total P&L */
  total_pnl?: number;
  /** Total P&L percentage */
  total_pnl_pct?: number;
  /** Number of open positions */
  positions_count?: number;
}

/**
 * Portfolio holding
 */
export interface Holding {
  /** Stock symbol */
  symbol?: string;
  /** Number of shares */
  shares?: number;
  /** Average cost basis */
  cost_basis?: number;
  /** Current market price */
  current_price?: number;
  /** Total market value */
  value?: number;
  /** Unrealized P&L */
  pnl?: number;
  /** Unrealized P&L percentage */
  pnl_pct?: number;
  /** Portfolio weight percentage */
  weight?: number;
  /** Day's change */
  day_change?: number;
}

/**
 * Portfolio performance metrics
 */
export interface Performance {
  /** Total return in dollars */
  total_return?: number;
  /** Total return percentage */
  total_return_pct?: number;
  /** Win rate (0-1) */
  win_rate?: number;
  /** Profit factor (gross profit / gross loss) */
  profit_factor?: number;
  /** Sharpe ratio */
  sharpe_ratio?: number;
  /** Sortino ratio */
  sortino_ratio?: number;
  /** Maximum drawdown percentage */
  max_drawdown?: number;
  /** Average winning trade amount */
  avg_win?: number;
  /** Average losing trade amount */
  avg_loss?: number;
  /** Total number of trades */
  total_trades?: number;
  /** Number of winning trades */
  winning_trades?: number;
  /** Number of losing trades */
  losing_trades?: number;
}

// =====================================================================
// RISK MANAGEMENT SCHEMAS
// =====================================================================

/**
 * Risk metrics
 */
export interface RiskMetrics {
  /** Value at Risk (95% confidence) */
  var_95?: number;
  /** Current drawdown percentage */
  current_drawdown?: number;
  /** Maximum position exposure percentage */
  max_position_exposure?: number;
  /** Sector concentration risk */
  sector_concentration?: number;
  /** Daily P&L */
  daily_pnl?: number;
  /** Overall risk score (0-100) */
  risk_score?: number;
}

/**
 * Safety status and breaches
 */
export interface SafetyStatus {
  /** Whether system is in safe state */
  is_safe?: boolean;
  /** List of risk breaches */
  breaches?: string[];
  /** List of risk warnings */
  warnings?: string[];
  /** Current daily loss */
  daily_loss?: number;
  /** Maximum allowed daily loss */
  max_daily_loss?: number;
  /** Current drawdown */
  current_drawdown?: number;
  /** Maximum drawdown limit */
  max_drawdown_limit?: number;
}

/**
 * Risk exposure breakdown
 */
export interface Exposure {
  /** Gross exposure */
  gross?: number;
  /** Net exposure */
  net?: number;
  /** Long exposure */
  long?: number;
  /** Short exposure */
  short?: number;
  /** Exposure by sector */
  by_sector?: Record<string, number>;
}

/**
 * Kill switch status
 */
export interface KillSwitchStatus {
  /** Whether kill switch is engaged */
  engaged?: boolean;
  /** Reason for engagement */
  reason?: string;
  /** Engagement timestamp (ISO 8601) */
  engaged_at?: string;
}

/**
 * Kill switch activation request
 */
export interface KillSwitchRequest {
  /** Reason for activation */
  reason?: string;
}

// =====================================================================
// ML/AI BRAIN SCHEMAS
// =====================================================================

/**
 * Strategy performance in brain
 */
export interface BrainStrategy {
  /** Strategy name */
  name?: string;
  /** Strategy weight in ensemble */
  weight?: number;
  /** Strategy win rate */
  win_rate?: number;
}

/**
 * Brain performance metrics
 */
export interface BrainMetrics {
  /** Overall win rate */
  win_rate?: number;
  /** Total P&L */
  total_pnl?: number;
  /** Profit factor */
  profit_factor?: number;
}

/**
 * Trading brain status
 */
export interface BrainStatus {
  /** Whether brain is available */
  available?: boolean;
  /** Compute device (cpu/cuda) */
  device?: string;
  /** Whether model is trained */
  is_trained?: boolean;
  /** Current market regime */
  current_regime?: string;
  /** Auto-training enabled */
  auto_train_enabled?: boolean;
  /** Current training step */
  training_step?: number;
  /** Total trades made */
  total_trades?: number;
  /** Performance metrics */
  metrics?: BrainMetrics;
  /** Strategy performances */
  strategies?: BrainStrategy[];
}

/**
 * Training result
 */
export interface TrainResult {
  /** Whether training succeeded */
  success?: boolean;
  /** Number of epochs trained */
  epochs?: number;
  /** Final loss value */
  final_loss?: number;
  /** Training metrics */
  metrics?: Record<string, number>;
}

/**
 * Market regime classification
 */
export interface MarketRegime {
  /** Current regime */
  regime?: MarketRegimeType;
  /** Classification confidence */
  confidence?: number;
  /** Market volatility */
  volatility?: number;
  /** Trend strength */
  trend_strength?: number;
}

/**
 * Convergence progress for strategy
 */
export interface ConvergenceProgress {
  [strategy: string]: number;
}

/**
 * Feedback loop status
 */
export interface FeedbackStatus {
  /** Current learning phase */
  phase?: string;
  /** Total trades recorded */
  total_trades?: number;
  /** Current win rate */
  win_rate?: number;
  /** Current profit factor */
  profit_factor?: number;
  /** Current Sharpe ratio */
  sharpe_ratio?: number;
  /** Convergence progress by strategy */
  convergence_progress?: ConvergenceProgress;
  /** Whether system has converged */
  is_converged?: boolean;
}

/**
 * Signal generation request
 */
export interface GenerateSignalRequest {
  /** Stock symbol to analyze */
  symbol: string;
}

// =====================================================================
// OPTIONS SCHEMAS
// =====================================================================

/**
 * Options contract
 */
export interface OptionContract {
  /** Expiration date */
  expiration?: string;
  /** Strike price */
  strike?: number;
  /** Contract type */
  option_type?: OptionType;
  /** Best bid price */
  bid?: number;
  /** Best ask price */
  ask?: number;
  /** Implied volatility */
  iv?: number;
  /** Delta greek */
  delta?: number;
  /** Gamma greek */
  gamma?: number;
  /** Theta greek */
  theta?: number;
  /** Vega greek */
  vega?: number;
  /** Open interest */
  oi?: number;
  /** Volume */
  volume?: number;
}

/**
 * GEX key level
 */
export interface GEXKeyLevel {
  /** Strike price */
  strike?: number;
  /** GEX value at this strike */
  gex?: number;
}

/**
 * Gamma exposure data
 */
export interface GEXData {
  /** Stock symbol */
  symbol?: string;
  /** Total gamma exposure */
  total_gex?: number;
  /** Call gamma exposure */
  call_gex?: number;
  /** Put gamma exposure */
  put_gex?: number;
  /** Key GEX levels */
  key_levels?: GEXKeyLevel[];
  /** GEX flip point (where GEX changes from positive to negative) */
  flip_point?: number;
}

/**
 * Options flow record
 */
export interface OptionsFlow {
  /** Flow record identifier */
  id?: string;
  /** Underlying symbol */
  symbol?: string;
  /** Option type */
  type?: OptionType;
  /** Trade side */
  side?: OptionsFlowSide;
  /** Inferred sentiment */
  sentiment?: OptionsFlowSentiment;
  /** Strike price */
  strike?: number;
  /** Expiration date */
  expiry?: string;
  /** Total premium */
  premium?: number;
  /** Number of contracts */
  contracts?: number;
  /** Whether this is unusual activity */
  is_unusual?: boolean;
  /** Whether this was a sweep order */
  is_sweep?: boolean;
  /** Timestamp (ISO 8601) */
  timestamp?: string;
}

// =====================================================================
// BACKTEST SCHEMAS
// =====================================================================

/**
 * Backtest configuration
 */
export interface BacktestConfig {
  /** Strategy name */
  strategy: string;
  /** Stock symbol */
  symbol: string;
  /** Start date (YYYY-MM-DD) */
  start_date: string;
  /** End date (YYYY-MM-DD) */
  end_date: string;
  /** Initial capital (defaults to 100000) */
  initial_capital?: number;
  /** Strategy parameters */
  params?: Record<string, unknown>;
}

/**
 * Equity curve point
 */
export interface EquityCurvePoint {
  /** Date */
  date?: string;
  /** Portfolio equity */
  equity?: number;
}

/**
 * Backtest result
 */
export interface BacktestResult {
  /** Total return percentage */
  total_return?: number;
  /** Sharpe ratio */
  sharpe_ratio?: number;
  /** Maximum drawdown */
  max_drawdown?: number;
  /** Win rate */
  win_rate?: number;
  /** Number of trades */
  trade_count?: number;
  /** Profit factor */
  profit_factor?: number;
  /** Equity curve data */
  equity_curve?: EquityCurvePoint[];
  /** Individual trades */
  trades?: Record<string, unknown>[];
}

/**
 * Trading strategy definition
 */
export interface Strategy {
  /** Strategy identifier */
  id?: string;
  /** Strategy name */
  name?: string;
  /** Strategy description */
  description?: string;
  /** Strategy type */
  type?: string;
  /** Strategy parameters */
  params?: Record<string, unknown>;
}

/**
 * Monte Carlo simulation request
 */
export interface MonteCarloRequest {
  /** Strategy name */
  strategy?: string;
  /** Stock symbol */
  symbol?: string;
  /** Number of simulations (defaults to 1000) */
  simulations?: number;
}

// =====================================================================
// RESEARCH SCHEMAS
// =====================================================================

/**
 * News article
 */
export interface NewsItem {
  /** Article identifier */
  id?: string;
  /** Article title */
  title?: string;
  /** Article summary */
  summary?: string;
  /** News source */
  source?: string;
  /** Article URL */
  url?: string;
  /** Related stock symbols */
  symbols?: string[];
  /** Sentiment analysis result */
  sentiment?: NewsSentiment;
  /** Publication timestamp (ISO 8601) */
  published_at?: string;
}

/**
 * 13F filing data
 */
export interface Filing13F {
  /** Institution name */
  holder?: string;
  /** Number of shares held */
  shares?: number;
  /** Total value */
  value?: number;
  /** Change from previous quarter */
  change_pct?: number;
  /** Report date */
  report_date?: string;
}

/**
 * Earnings data
 */
export interface EarningsData {
  /** Stock symbol */
  symbol?: string;
  /** Earnings report date */
  report_date?: string;
  /** Expected EPS */
  eps_estimate?: number;
  /** Actual EPS (if reported) */
  eps_actual?: number;
  /** Expected revenue */
  revenue_estimate?: number;
  /** Actual revenue (if reported) */
  revenue_actual?: number;
  /** Earnings surprise percentage */
  surprise_pct?: number;
}

// =====================================================================
// SETTINGS SCHEMAS
// =====================================================================

/**
 * Application settings
 */
export interface Settings {
  /** UI theme */
  theme?: Theme;
  /** Notifications enabled */
  notifications_enabled?: boolean;
  /** Auto-refresh interval in seconds */
  auto_refresh_interval?: number;
  /** Default order type for new orders */
  default_order_type?: string;
  /** Risk parameter settings */
  risk_params?: Record<string, unknown>;
}

/**
 * API key status (boolean indicates whether key is configured)
 */
export interface ApiKeys {
  /** Alpaca API key configured */
  alpaca?: boolean;
  /** Tradier API key configured */
  tradier?: boolean;
  /** Polygon API key configured */
  polygon?: boolean;
}

// =====================================================================
// WEBSOCKET SCHEMAS
// =====================================================================

/**
 * WebSocket subscription message
 */
export interface WSSubscribeMessage {
  /** Action type */
  action: 'subscribe' | 'unsubscribe';
  /** Channels to subscribe/unsubscribe */
  channels: WSChannel[];
}

/**
 * Available WebSocket channels
 */
export type WSChannel = 'market' | 'signals' | 'positions' | 'risk' | 'brain' | 'system';

/**
 * WebSocket message envelope
 */
export interface WSMessage<T = unknown> {
  /** Message channel */
  channel: WSChannel;
  /** Message type */
  type: string;
  /** Message payload */
  data: T;
  /** Message timestamp */
  timestamp: string;
}

// =====================================================================
// REQUEST/RESPONSE TYPE ALIASES
// =====================================================================

// Health
export type HealthCheckResponse = HealthStatus;
export type SystemStatusResponse = SystemStatus;
export type MemoryStatusResponse = MemoryStatus;

// Market
export type MarketStatusResponse = MarketStatus;
export type GetTickersResponse = TickerPrice[];
export type GetQuoteResponse = Quote;
export type GetOHLCVResponse = OHLCVData;
export type GetIndicatorsResponse = TechnicalIndicators;
export type GetSectorsResponse = SectorData[];
export type GetMoversResponse = MoversData;

// Trading
export type GetSignalsResponse = Signal[];
export type GetActiveSignalsResponse = Signal[];
export type ExecuteSignalResponse = ExecutionResult;
export type GetPositionsResponse = Position[];
export type GetOrdersResponse = Order[];
export type SubmitOrderResponse = OrderResult;
export type ConfirmTradeResponse = AIDecision;

// Portfolio
export type GetPortfolioResponse = Portfolio;
export type GetHoldingsResponse = Holding[];
export type GetPerformanceResponse = Performance;

// Risk
export type GetRiskMetricsResponse = RiskMetrics;
export type GetSafetyStatusResponse = SafetyStatus;
export type GetExposureResponse = Exposure;
export type GetKillSwitchResponse = KillSwitchStatus;

// Brain
export type GetBrainStatusResponse = BrainStatus;
export type GetBrainSignalsResponse = Signal[];
export type GenerateSignalResponse = Signal;
export type TrainBrainResponse = TrainResult;
export type GetMarketRegimeResponse = MarketRegime;
export type GetFeedbackStatusResponse = FeedbackStatus;

// Options
export type GetOptionsChainResponse = OptionContract[];
export type GetGEXResponse = GEXData;
export type GetOptionsFlowResponse = OptionsFlow[];

// Backtest
export type RunBacktestResponse = BacktestResult;
export type GetStrategiesResponse = Strategy[];

// Research
export type GetNewsResponse = NewsItem[];
export type Get13FResponse = Filing13F[];
export type GetEarningsResponse = EarningsData[];

// Settings
export type GetSettingsResponse = Settings;
export type UpdateSettingsResponse = Settings;
export type GetApiKeysResponse = ApiKeys;

// =====================================================================
// API OPERATION PARAMETERS
// =====================================================================

/**
 * Base type for query parameters
 */
type QueryParamValue = string | number | boolean | undefined;

/**
 * Parameters for getTickers endpoint
 */
export interface GetTickersParams {
  /** Comma-separated list of symbols (default: SPY,QQQ,DIA,IWM) */
  symbols?: string;
  [key: string]: QueryParamValue;
}

/**
 * Parameters for getOHLCV endpoint
 */
export interface GetOHLCVParams {
  /** Chart interval */
  interval?: ChartInterval;
  /** Time period */
  period?: ChartPeriod;
  [key: string]: QueryParamValue;
}

/**
 * Parameters for getOptionsChain endpoint
 */
export interface GetOptionsChainParams {
  /** Expiration date filter */
  expiration?: string;
  /** Option type filter */
  option_type?: OptionTypeFilter;
  [key: string]: QueryParamValue;
}

/**
 * Parameters for getNews endpoint
 */
export interface GetNewsParams {
  /** Filter by symbol */
  symbol?: string;
  [key: string]: QueryParamValue;
}
