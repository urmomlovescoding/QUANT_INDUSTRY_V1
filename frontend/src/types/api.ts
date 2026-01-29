/**
 * API Types - TypeScript types matching backend Pydantic schemas
 * This file provides strong typing for API responses
 */

// ==================== COMMON TYPES ====================

export type TradingDirection = 'LONG' | 'SHORT';
export type SignalStatus = 'active' | 'executed' | 'dismissed' | 'expired';
export type OrderSide = 'buy' | 'sell';
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit';
export type TimeInForce = 'day' | 'gtc' | 'ioc' | 'fok';
export type MarketSession = 'pre_market' | 'regular' | 'after_hours' | 'closed';
export type MarketRegimeType = 'trending' | 'ranging' | 'volatile' | 'quiet';
export type Sentiment = 'positive' | 'negative' | 'neutral';
export type OptionType = 'call' | 'put';

// ==================== DECISION INTELLIGENCE TYPES ====================

export type ControlPlaneMode = 'shadow' | 'paper' | 'live' | 'disabled';
export type ShadowStatus = 'shadow' | 'parallel' | 'candidate' | 'promoted' | 'rejected';
export type TriggerType = 'drift' | 'scheduled' | 'manual' | 'performance';
export type ImprovementPhase = 'idle' | 'analysis' | 'generation' | 'validation' | 'promotion' | 'completed' | 'failed';

export interface ControlPlaneStatus {
  mode: ControlPlaneMode;
  is_active: boolean;
  kill_switch_engaged: boolean;
  decisions_today: number;
  trades_today: number;
  shadow_decisions_today: number;
  components_registered: string[];
  safety_checks_count: number;
  contexts_cached: number;
}

export interface ControlPlaneHealth {
  overall: 'healthy' | 'degraded' | 'unhealthy';
  components: Record<string, {
    status: 'healthy' | 'unhealthy';
    last_check: string;
    error?: string;
  }>;
}

export interface DecisionNode {
  context_id: string;
  timestamp: string;
  component: string;
  decision: string;
  reason: string;
  data: Record<string, unknown>;
  outcome?: string;
  pnl?: number;
}

export interface DecisionContext {
  context_id: string;
  timestamp: string;
  symbol: string;
  regime: string;
  regime_confidence: number;
  signal_direction: TradingDirection | null;
  signal_confidence: number;
  signal_source: string;
  risk_approved: boolean;
  risk_adjusted_size: number;
  risk_warnings: string[];
  execution_allowed: boolean;
  execution_mode: string;
  decisions: DecisionNode[];
}

export interface DecisionTraceStats {
  total_nodes: number;
  total_edges: number;
  outcomes: Record<string, number>;
  components: Record<string, number>;
  graph_available: boolean;
}

export interface FailurePattern {
  pattern_id: string;
  description: string;
  frequency: number;
  avg_loss: number;
  components_involved: string[];
  common_conditions: Record<string, unknown>;
  suggested_fix?: string;
}

export interface SuccessPattern {
  pattern_id: string;
  description: string;
  frequency: number;
  avg_profit: number;
  components_involved: string[];
  common_conditions: Record<string, unknown>;
}

export interface ExitRecommendation {
  action: 'hold' | 'exit';
  reason: string;
  confidence: number;
  expected_value_hold: number;
  expected_value_exit: number;
  state: {
    regime: string;
    time_bucket: number;
    pnl_bucket: number;
    volatility_bucket: number;
  };
  is_shadow: boolean;
}

export interface ExitLearnerStats {
  total_observations: number;
  states_learned: number;
  avg_q_value_hold: number;
  avg_q_value_exit: number;
  last_updated: string;
  learning_rate: number;
}

export interface ValueSurfacePoint {
  time_bucket: number;
  pnl_bucket: number;
  volatility_bucket: number;
  q_hold: number;
  q_exit: number;
  optimal_action: 'hold' | 'exit';
}

export interface ShadowComponent {
  component_id: string;
  component_name: string;
  version: string;
  status: ShadowStatus;
  created_at: string;
  decisions_count: number;
  correct_decisions: number;
  accuracy: number;
  total_shadow_pnl: number;
  live_comparison_count: number;
  agreement_rate: number;
  outperformance_rate: number;
  promotion_score: number;
}

export interface ShadowReport {
  component: ShadowComponent;
  decision_breakdown: Record<string, number>;
  accuracy_over_time: Array<{ date: string; accuracy: number }>;
  pnl_comparison: {
    shadow_pnl: number;
    live_pnl: number;
    outperformance: number;
  };
  recommendation: 'promote' | 'continue_shadow' | 'reject';
}

export interface ShadowComparison {
  total_components: number;
  by_status: Record<ShadowStatus, number>;
  top_performers: ShadowComponent[];
  promotion_candidates: ShadowComponent[];
}

export interface ImprovementCycle {
  cycle_id: string;
  trigger: TriggerType;
  started_at: string;
  completed_at?: string;
  phase: ImprovementPhase;
  component_name: string;
  old_version: string;
  new_version: string | null;
  improvement_pct?: number;
  error?: string;
}

export interface SelfImprovementStatus {
  current_phase: ImprovementPhase;
  active_cycle: ImprovementCycle | null;
  consecutive_failures: number;
  total_cycles: number;
  successful_cycles: number;
  config: {
    drift_threshold: number;
    validation_days: number;
    improvement_threshold: number;
  };
}

// ==================== DATA INTEGRITY TYPES ====================

export type DataMode = 'live' | 'paper' | 'backtest' | 'simulation';

export interface DataModeStatus {
  mode: DataMode;
  available: boolean;
  modes: Record<DataMode, string>;
  current_description: string;
  quality_stats: {
    freshness: number;
    completeness: number;
    consistency: number;
  };
  timestamp: string;
}

export interface DataIntegrityStatus {
  overall_health: 'healthy' | 'degraded' | 'unhealthy';
  sources: Record<string, {
    status: 'connected' | 'disconnected' | 'stale';
    last_update: string;
    latency_ms: number;
  }>;
  data_quality_score: number;
}

export interface PriceWithProvenance {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  timestamp: string;
  source: string;
  quality: 'verified' | 'unverified' | 'stale';
  provenance: {
    primary_source: string;
    fallback_sources: string[];
    age_ms: number;
    staleness_threshold_ms: number;
  };
}

export interface StalenessStatus {
  stale_symbols: string[];
  fresh_count: number;
  stale_count: number;
  threshold_ms: number;
  oldest_data_age_ms: number;
}

// ==================== WEBSOCKET TYPES ====================

export interface WSMarketData {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  volume: number;
  change: number;
  change_pct: number;
  timestamp: string;
}

export interface WSSignal {
  id: string;
  symbol: string;
  signal_type: string;
  direction: TradingDirection;
  strength: number;
  metadata: Record<string, unknown>;
  generated_at: string;
}

export interface WSRiskMetrics {
  var_95: number;
  cvar_95: number;
  portfolio_beta: number;
  current_drawdown: number;
  sector_exposure: Record<string, number>;
  updated_at: string;
}

export interface WSAlert {
  id: string;
  alert_type: 'risk' | 'execution' | 'system' | 'opportunity';
  severity: 'info' | 'warning' | 'critical';
  message: string;
  details: Record<string, unknown>;
  triggered_at: string;
  acknowledged?: boolean;
}

export interface WSExecution {
  order_id: string;
  symbol: string;
  side: OrderSide;
  quantity: number;
  price: number;
  status: 'submitted' | 'filled' | 'partial' | 'cancelled' | 'rejected';
  filled_qty: number;
  avg_price: number;
  updated_at: string;
}

export interface WSPortfolioUpdate {
  equity: number;
  cash: number;
  buying_power: number;
  day_pnl: number;
  day_pnl_pct: number;
  updated_at: string;
}
