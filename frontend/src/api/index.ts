/**
 * API Module Exports
 * 
 * Note: New code should use `apiV2` from '@/api/v2' for type-safe API calls.
 * The old API exports below are maintained for backward compatibility.
 */

// =====================================================================
// V2 API CLIENT (RECOMMENDED)
// =====================================================================
// Re-export v2 client for easy access
export { apiV2, default as apiV2Default } from './v2'

// =====================================================================
// LEGACY API EXPORTS (use apiV2 instead for new code)
// =====================================================================
export {
  api,
  healthApi,
  marketApi,
  brainApi,
  feedbackApi,
  signalsApi,
  portfolioApi,
  tradingApi,
  riskApi,
  backtestApi,
  optionsApi,
  researchApi,
  settingsApi,
  screenerApi,
  neuralApi,
  decisionIntelApi,
  dataIntegrityApi,
} from './client'

export type {
  ApiError,
  ApiResponse,
  HealthStatus,
  SystemStatus,
  MarketTicker,
  Quote,
  HistoricalData,
  MarketStatus,
  BrainStatus,
  FeedbackStatus,
  Signal,
  Position,
  Portfolio,
  Performance,
  Holding,
  RiskMetrics,
  Exposure,
  SafetyStatus,
  OrderRequest,
  OrderResult,
  Order,
  TradeConfirmRequest,
  AIDecision,
  BacktestConfig,
  BacktestResult,
  Strategy,
  OptionChain,
  GEXData,
  OptionsFlow,
  Filing13F,
  SECFiling,
  DarkPoolData,
  EarningsData,
  NewsItem,
  Settings,
  ApiKeys,
  ScreenerFilters,
  ScreenerResult,
  ScreenerPreset,
  Prediction,
  MarketRegime,
  NeuralAnalysis,
  TrainResult,
  TradeRecord,
  Analysis,
  ExecutionResult,
  SectorData,
  MoversData,
  MoverStock,
  // Decision Intelligence types
  ControlPlaneStatus,
  DecisionContext,
  DecisionTraceStats,
  ExitRecommendation,
  ShadowComponent,
  SelfImprovementStatus,
  DataMode,
} from './client'
