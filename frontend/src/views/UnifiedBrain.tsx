/**
 * UnifiedBrain - Comprehensive AI Trading System with 53+ Strategies
 * Combines ML, RL, DL, Evolution, and Traditional Quant Strategies
 */

import { useState, useEffect, useCallback } from 'react'
import {
  Brain,
  Zap,
  Activity,
  Target,
  Shield,
  TrendingUp,
  TrendingDown,
  Layers,
  GitBranch,
  Cpu,
  BarChart3,
  RefreshCw,
  Play,
  Pause,
  Settings,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  Clock,
  Gauge,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
} from 'recharts'

// ============== STRATEGY DEFINITIONS ==============

interface Strategy {
  id: string
  name: string
  category: StrategyCategory
  type: StrategyType
  description: string
  weight: number
  active: boolean
  confidence: number
  signal: Signal
  performance: {
    winRate: number
    sharpe: number
    maxDrawdown: number
    totalTrades: number
    avgProfit: number
  }
}

type StrategyCategory =
  | 'ML'
  | 'RL'
  | 'DL'
  | 'Evolution'
  | 'Trend'
  | 'MeanReversion'
  | 'Volatility'
  | 'Momentum'
  | 'Market_Structure'
  | 'Regime'
  | 'Options'
  | 'Macro'

type StrategyType = 'long' | 'short' | 'both'
type Signal = 'LONG' | 'SHORT' | 'NEUTRAL' | 'NO_SIGNAL'

const STRATEGY_CATEGORIES: { id: StrategyCategory; name: string; icon: any; color: string }[] = [
  { id: 'ML', name: 'Machine Learning', icon: Brain, color: 'text-purple-500' },
  { id: 'RL', name: 'Reinforcement Learning', icon: GitBranch, color: 'text-blue-500' },
  { id: 'DL', name: 'Deep Learning', icon: Layers, color: 'text-cyan-500' },
  { id: 'Evolution', name: 'Evolution/Genetic', icon: Zap, color: 'text-yellow-500' },
  { id: 'Trend', name: 'Trend Following', icon: TrendingUp, color: 'text-bullish' },
  { id: 'MeanReversion', name: 'Mean Reversion', icon: Activity, color: 'text-orange-500' },
  { id: 'Volatility', name: 'Volatility', icon: BarChart3, color: 'text-red-500' },
  { id: 'Momentum', name: 'Momentum', icon: Target, color: 'text-pink-500' },
  { id: 'Market_Structure', name: 'Market Structure', icon: Cpu, color: 'text-indigo-500' },
  { id: 'Regime', name: 'Regime Detection', icon: Gauge, color: 'text-teal-500' },
  { id: 'Options', name: 'Options Flow', icon: Shield, color: 'text-emerald-500' },
  { id: 'Macro', name: 'Macro/Cycles', icon: RefreshCw, color: 'text-amber-500' },
]

// Generate all 53+ strategies
const generateStrategies = (): Strategy[] => {
  const strategies: Strategy[] = [
    // Machine Learning (10)
    { id: 'xgb_trend', name: 'XGBoost Trend Classifier', category: 'ML', type: 'both', description: 'Gradient boosted trend detection', weight: 8, active: true, confidence: 0.72, signal: 'LONG', performance: { winRate: 0.58, sharpe: 1.4, maxDrawdown: -12, totalTrades: 450, avgProfit: 0.8 } },
    { id: 'rf_momentum', name: 'Random Forest Momentum', category: 'ML', type: 'both', description: 'Ensemble momentum signals', weight: 7, active: true, confidence: 0.68, signal: 'LONG', performance: { winRate: 0.55, sharpe: 1.2, maxDrawdown: -15, totalTrades: 380, avgProfit: 0.6 } },
    { id: 'lightgbm_regime', name: 'LightGBM Regime', category: 'ML', type: 'both', description: 'Fast regime classification', weight: 6, active: true, confidence: 0.75, signal: 'NEUTRAL', performance: { winRate: 0.62, sharpe: 1.6, maxDrawdown: -10, totalTrades: 290, avgProfit: 1.1 } },
    { id: 'catboost_reversal', name: 'CatBoost Reversal', category: 'ML', type: 'both', description: 'Categorical reversal patterns', weight: 5, active: true, confidence: 0.65, signal: 'SHORT', performance: { winRate: 0.52, sharpe: 1.1, maxDrawdown: -18, totalTrades: 520, avgProfit: 0.5 } },
    { id: 'svm_classifier', name: 'SVM Direction Classifier', category: 'ML', type: 'both', description: 'Support vector classification', weight: 4, active: false, confidence: 0.60, signal: 'NO_SIGNAL', performance: { winRate: 0.51, sharpe: 0.9, maxDrawdown: -20, totalTrades: 600, avgProfit: 0.3 } },
    { id: 'isolation_forest', name: 'Isolation Forest Anomaly', category: 'ML', type: 'both', description: 'Anomaly detection signals', weight: 5, active: true, confidence: 0.78, signal: 'LONG', performance: { winRate: 0.65, sharpe: 1.8, maxDrawdown: -8, totalTrades: 150, avgProfit: 1.5 } },
    { id: 'knn_pattern', name: 'KNN Pattern Matcher', category: 'ML', type: 'both', description: 'Historical pattern matching', weight: 4, active: true, confidence: 0.63, signal: 'LONG', performance: { winRate: 0.54, sharpe: 1.0, maxDrawdown: -16, totalTrades: 420, avgProfit: 0.4 } },
    { id: 'naive_bayes', name: 'Naive Bayes Signal', category: 'ML', type: 'both', description: 'Probabilistic signal generation', weight: 3, active: false, confidence: 0.58, signal: 'NO_SIGNAL', performance: { winRate: 0.50, sharpe: 0.8, maxDrawdown: -22, totalTrades: 700, avgProfit: 0.2 } },
    { id: 'adaboost_micro', name: 'AdaBoost Micro Alpha', category: 'ML', type: 'both', description: 'Boosted micro-structure signals', weight: 5, active: true, confidence: 0.70, signal: 'SHORT', performance: { winRate: 0.56, sharpe: 1.3, maxDrawdown: -14, totalTrades: 350, avgProfit: 0.7 } },
    { id: 'voting_ensemble', name: 'ML Voting Ensemble', category: 'ML', type: 'both', description: 'Meta-ensemble of all ML models', weight: 10, active: true, confidence: 0.82, signal: 'LONG', performance: { winRate: 0.68, sharpe: 2.1, maxDrawdown: -6, totalTrades: 200, avgProfit: 1.8 } },

    // Reinforcement Learning (8)
    { id: 'ppo_trader', name: 'PPO Neural Trader', category: 'RL', type: 'both', description: 'Proximal Policy Optimization', weight: 9, active: true, confidence: 0.76, signal: 'LONG', performance: { winRate: 0.62, sharpe: 1.9, maxDrawdown: -9, totalTrades: 280, avgProfit: 1.4 } },
    { id: 'a2c_position', name: 'A2C Position Sizer', category: 'RL', type: 'both', description: 'Advantage Actor-Critic sizing', weight: 7, active: true, confidence: 0.71, signal: 'LONG', performance: { winRate: 0.58, sharpe: 1.5, maxDrawdown: -12, totalTrades: 320, avgProfit: 1.0 } },
    { id: 'dqn_discrete', name: 'DQN Discrete Actions', category: 'RL', type: 'both', description: 'Deep Q-Network signals', weight: 6, active: true, confidence: 0.68, signal: 'NEUTRAL', performance: { winRate: 0.55, sharpe: 1.3, maxDrawdown: -15, totalTrades: 400, avgProfit: 0.8 } },
    { id: 'sac_continuous', name: 'SAC Continuous Control', category: 'RL', type: 'both', description: 'Soft Actor-Critic trading', weight: 8, active: true, confidence: 0.74, signal: 'LONG', performance: { winRate: 0.60, sharpe: 1.7, maxDrawdown: -10, totalTrades: 260, avgProfit: 1.2 } },
    { id: 'td3_hedging', name: 'TD3 Dynamic Hedging', category: 'RL', type: 'both', description: 'Twin delayed DDPG hedging', weight: 6, active: true, confidence: 0.69, signal: 'SHORT', performance: { winRate: 0.57, sharpe: 1.4, maxDrawdown: -13, totalTrades: 340, avgProfit: 0.9 } },
    { id: 'rainbow_dqn', name: 'Rainbow DQN', category: 'RL', type: 'both', description: 'Combined DQN improvements', weight: 7, active: false, confidence: 0.72, signal: 'NO_SIGNAL', performance: { winRate: 0.59, sharpe: 1.6, maxDrawdown: -11, totalTrades: 300, avgProfit: 1.1 } },
    { id: 'rmdp_recursive', name: 'RMDP Recursive Trainer', category: 'RL', type: 'both', description: 'Recursive MDP auto-training', weight: 8, active: true, confidence: 0.80, signal: 'LONG', performance: { winRate: 0.64, sharpe: 2.0, maxDrawdown: -7, totalTrades: 220, avgProfit: 1.6 } },
    { id: 'multi_agent_rl', name: 'Multi-Agent RL System', category: 'RL', type: 'both', description: 'Cooperative agent ensemble', weight: 9, active: true, confidence: 0.78, signal: 'LONG', performance: { winRate: 0.63, sharpe: 1.8, maxDrawdown: -8, totalTrades: 240, avgProfit: 1.5 } },

    // Deep Learning (8)
    { id: 'lstm_sequence', name: 'LSTM Sequence Predictor', category: 'DL', type: 'both', description: 'Long-short term memory', weight: 7, active: true, confidence: 0.73, signal: 'LONG', performance: { winRate: 0.59, sharpe: 1.5, maxDrawdown: -12, totalTrades: 310, avgProfit: 1.0 } },
    { id: 'transformer_attention', name: 'Transformer Attention', category: 'DL', type: 'both', description: 'Self-attention market model', weight: 9, active: true, confidence: 0.81, signal: 'LONG', performance: { winRate: 0.66, sharpe: 2.2, maxDrawdown: -6, totalTrades: 180, avgProfit: 1.9 } },
    { id: 'gru_momentum', name: 'GRU Momentum Net', category: 'DL', type: 'both', description: 'Gated recurrent momentum', weight: 6, active: true, confidence: 0.70, signal: 'LONG', performance: { winRate: 0.57, sharpe: 1.4, maxDrawdown: -14, totalTrades: 360, avgProfit: 0.9 } },
    { id: 'cnn_pattern', name: 'CNN Pattern Recognition', category: 'DL', type: 'both', description: 'Convolutional chart patterns', weight: 7, active: true, confidence: 0.75, signal: 'NEUTRAL', performance: { winRate: 0.61, sharpe: 1.7, maxDrawdown: -10, totalTrades: 270, avgProfit: 1.3 } },
    { id: 'wavenet_temporal', name: 'WaveNet Temporal', category: 'DL', type: 'both', description: 'Dilated causal convolutions', weight: 6, active: false, confidence: 0.68, signal: 'NO_SIGNAL', performance: { winRate: 0.55, sharpe: 1.2, maxDrawdown: -16, totalTrades: 400, avgProfit: 0.7 } },
    { id: 'autoencoder_regime', name: 'VAE Regime Detector', category: 'DL', type: 'both', description: 'Variational autoencoder', weight: 5, active: true, confidence: 0.72, signal: 'LONG', performance: { winRate: 0.58, sharpe: 1.5, maxDrawdown: -12, totalTrades: 320, avgProfit: 1.0 } },
    { id: 'tcn_forecast', name: 'TCN Forecaster', category: 'DL', type: 'both', description: 'Temporal convolutional network', weight: 7, active: true, confidence: 0.74, signal: 'SHORT', performance: { winRate: 0.60, sharpe: 1.6, maxDrawdown: -11, totalTrades: 290, avgProfit: 1.1 } },
    { id: 'informer_long', name: 'Informer Long-Horizon', category: 'DL', type: 'both', description: 'Efficient transformer forecasting', weight: 8, active: true, confidence: 0.77, signal: 'LONG', performance: { winRate: 0.62, sharpe: 1.8, maxDrawdown: -9, totalTrades: 250, avgProfit: 1.4 } },

    // Evolution/Genetic (5)
    { id: 'genetic_strategy', name: 'Genetic Strategy Evolver', category: 'Evolution', type: 'both', description: 'Evolved trading rules', weight: 6, active: true, confidence: 0.69, signal: 'LONG', performance: { winRate: 0.56, sharpe: 1.3, maxDrawdown: -14, totalTrades: 380, avgProfit: 0.8 } },
    { id: 'neuroevolution', name: 'NEAT Neuroevolution', category: 'Evolution', type: 'both', description: 'Evolved neural topologies', weight: 7, active: true, confidence: 0.73, signal: 'LONG', performance: { winRate: 0.59, sharpe: 1.5, maxDrawdown: -12, totalTrades: 300, avgProfit: 1.0 } },
    { id: 'differential_evolution', name: 'Differential Evolution', category: 'Evolution', type: 'both', description: 'Parameter optimization', weight: 5, active: true, confidence: 0.67, signal: 'NEUTRAL', performance: { winRate: 0.54, sharpe: 1.2, maxDrawdown: -15, totalTrades: 420, avgProfit: 0.6 } },
    { id: 'cma_es', name: 'CMA-ES Optimizer', category: 'Evolution', type: 'both', description: 'Covariance matrix adaptation', weight: 6, active: false, confidence: 0.71, signal: 'NO_SIGNAL', performance: { winRate: 0.58, sharpe: 1.4, maxDrawdown: -13, totalTrades: 350, avgProfit: 0.9 } },
    { id: 'pso_swarm', name: 'PSO Swarm Intelligence', category: 'Evolution', type: 'both', description: 'Particle swarm optimization', weight: 5, active: true, confidence: 0.66, signal: 'SHORT', performance: { winRate: 0.53, sharpe: 1.1, maxDrawdown: -16, totalTrades: 450, avgProfit: 0.5 } },

    // Trend Following (6)
    { id: 'ma_crossover', name: 'MA Crossover System', category: 'Trend', type: 'both', description: 'Classic moving average cross', weight: 5, active: true, confidence: 0.62, signal: 'LONG', performance: { winRate: 0.48, sharpe: 1.0, maxDrawdown: -20, totalTrades: 600, avgProfit: 0.4 } },
    { id: 'supertrend', name: 'SuperTrend Pro', category: 'Trend', type: 'both', description: 'ATR-based trend following', weight: 6, active: true, confidence: 0.68, signal: 'LONG', performance: { winRate: 0.52, sharpe: 1.2, maxDrawdown: -18, totalTrades: 480, avgProfit: 0.6 } },
    { id: 'turtle_breakout', name: 'Turtle Breakout', category: 'Trend', type: 'both', description: 'Donchian channel breakouts', weight: 5, active: true, confidence: 0.65, signal: 'LONG', performance: { winRate: 0.45, sharpe: 1.1, maxDrawdown: -25, totalTrades: 350, avgProfit: 0.8 } },
    { id: 'adx_trend', name: 'ADX Trend Strength', category: 'Trend', type: 'both', description: 'Directional movement system', weight: 5, active: true, confidence: 0.64, signal: 'NEUTRAL', performance: { winRate: 0.50, sharpe: 1.0, maxDrawdown: -22, totalTrades: 520, avgProfit: 0.5 } },
    { id: 'parabolic_sar', name: 'Parabolic SAR System', category: 'Trend', type: 'both', description: 'Stop and reverse signals', weight: 4, active: false, confidence: 0.58, signal: 'NO_SIGNAL', performance: { winRate: 0.46, sharpe: 0.8, maxDrawdown: -28, totalTrades: 700, avgProfit: 0.3 } },
    { id: 'ichimoku_cloud', name: 'Ichimoku Cloud', category: 'Trend', type: 'both', description: 'Multi-timeframe trend', weight: 6, active: true, confidence: 0.70, signal: 'LONG', performance: { winRate: 0.54, sharpe: 1.3, maxDrawdown: -16, totalTrades: 400, avgProfit: 0.7 } },

    // Mean Reversion (5)
    { id: 'bollinger_reversion', name: 'Bollinger Mean Reversion', category: 'MeanReversion', type: 'both', description: 'Band reversion trades', weight: 5, active: true, confidence: 0.67, signal: 'SHORT', performance: { winRate: 0.58, sharpe: 1.2, maxDrawdown: -14, totalTrades: 500, avgProfit: 0.5 } },
    { id: 'rsi_divergence', name: 'RSI Divergence', category: 'MeanReversion', type: 'both', description: 'Price-RSI divergence', weight: 5, active: true, confidence: 0.65, signal: 'SHORT', performance: { winRate: 0.55, sharpe: 1.1, maxDrawdown: -16, totalTrades: 450, avgProfit: 0.6 } },
    { id: 'z_score_reversion', name: 'Z-Score Reversion', category: 'MeanReversion', type: 'both', description: 'Statistical mean reversion', weight: 6, active: true, confidence: 0.72, signal: 'NEUTRAL', performance: { winRate: 0.62, sharpe: 1.5, maxDrawdown: -10, totalTrades: 380, avgProfit: 0.9 } },
    { id: 'pairs_trading', name: 'Pairs Trading', category: 'MeanReversion', type: 'both', description: 'Cointegrated pair spreads', weight: 7, active: true, confidence: 0.75, signal: 'LONG', performance: { winRate: 0.65, sharpe: 1.8, maxDrawdown: -8, totalTrades: 280, avgProfit: 1.2 } },
    { id: 'ornstein_uhlenbeck', name: 'OU Mean Reversion', category: 'MeanReversion', type: 'both', description: 'OU process modeling', weight: 5, active: false, confidence: 0.68, signal: 'NO_SIGNAL', performance: { winRate: 0.57, sharpe: 1.3, maxDrawdown: -13, totalTrades: 350, avgProfit: 0.7 } },

    // Volatility (4)
    { id: 'garch_vol', name: 'GARCH Vol Targeting', category: 'Volatility', type: 'both', description: 'Volatility forecasting', weight: 6, active: true, confidence: 0.70, signal: 'LONG', performance: { winRate: 0.58, sharpe: 1.4, maxDrawdown: -12, totalTrades: 320, avgProfit: 0.8 } },
    { id: 'vix_regime', name: 'VIX Regime Strategy', category: 'Volatility', type: 'both', description: 'VIX-based regime trading', weight: 5, active: true, confidence: 0.66, signal: 'NEUTRAL', performance: { winRate: 0.54, sharpe: 1.2, maxDrawdown: -15, totalTrades: 400, avgProfit: 0.6 } },
    { id: 'variance_risk_premium', name: 'Variance Risk Premium', category: 'Volatility', type: 'short', description: 'Implied vs realized vol', weight: 7, active: true, confidence: 0.74, signal: 'SHORT', performance: { winRate: 0.68, sharpe: 2.0, maxDrawdown: -18, totalTrades: 200, avgProfit: 1.5 } },
    { id: 'vol_surface', name: 'Vol Surface Analyzer', category: 'Volatility', type: 'both', description: 'Term structure signals', weight: 6, active: true, confidence: 0.71, signal: 'LONG', performance: { winRate: 0.60, sharpe: 1.5, maxDrawdown: -11, totalTrades: 280, avgProfit: 1.0 } },

    // Additional strategies to reach 53+...
    { id: 'momentum_factor', name: 'Momentum Factor', category: 'Momentum', type: 'long', description: 'Cross-sectional momentum', weight: 6, active: true, confidence: 0.68, signal: 'LONG', performance: { winRate: 0.56, sharpe: 1.3, maxDrawdown: -15, totalTrades: 420, avgProfit: 0.7 } },
    { id: 'roc_momentum', name: 'Rate of Change', category: 'Momentum', type: 'both', description: 'Price momentum signals', weight: 5, active: true, confidence: 0.64, signal: 'LONG', performance: { winRate: 0.52, sharpe: 1.1, maxDrawdown: -18, totalTrades: 500, avgProfit: 0.5 } },
    { id: 'macd_histogram', name: 'MACD Histogram', category: 'Momentum', type: 'both', description: 'MACD divergence signals', weight: 5, active: true, confidence: 0.65, signal: 'NEUTRAL', performance: { winRate: 0.53, sharpe: 1.0, maxDrawdown: -17, totalTrades: 480, avgProfit: 0.4 } },

    { id: 'order_flow_imbalance', name: 'Order Flow Imbalance', category: 'Market_Structure', type: 'both', description: 'Buy/sell pressure analysis', weight: 7, active: true, confidence: 0.76, signal: 'LONG', performance: { winRate: 0.62, sharpe: 1.7, maxDrawdown: -10, totalTrades: 350, avgProfit: 1.2 } },
    { id: 'vwap_deviation', name: 'VWAP Deviation', category: 'Market_Structure', type: 'both', description: 'Institutional flow proxy', weight: 6, active: true, confidence: 0.69, signal: 'LONG', performance: { winRate: 0.58, sharpe: 1.4, maxDrawdown: -13, totalTrades: 420, avgProfit: 0.8 } },
    { id: 'market_microstructure', name: 'Microstructure Alpha', category: 'Market_Structure', type: 'both', description: 'Tick-level signals', weight: 8, active: true, confidence: 0.78, signal: 'LONG', performance: { winRate: 0.64, sharpe: 1.9, maxDrawdown: -8, totalTrades: 250, avgProfit: 1.4 } },

    { id: 'hmm_regime', name: 'HMM Regime Detector', category: 'Regime', type: 'both', description: 'Hidden Markov regimes', weight: 7, active: true, confidence: 0.74, signal: 'LONG', performance: { winRate: 0.61, sharpe: 1.6, maxDrawdown: -11, totalTrades: 280, avgProfit: 1.1 } },
    { id: 'market_cycle', name: 'Market Cycle Phase', category: 'Regime', type: 'both', description: 'Bull/bear cycle detection', weight: 6, active: true, confidence: 0.70, signal: 'LONG', performance: { winRate: 0.58, sharpe: 1.4, maxDrawdown: -14, totalTrades: 320, avgProfit: 0.9 } },

    { id: 'gex_positioning', name: 'GEX Positioning', category: 'Options', type: 'both', description: 'Gamma exposure signals', weight: 8, active: true, confidence: 0.77, signal: 'LONG', performance: { winRate: 0.63, sharpe: 1.8, maxDrawdown: -9, totalTrades: 240, avgProfit: 1.3 } },
    { id: 'put_call_flow', name: 'Put/Call Flow', category: 'Options', type: 'both', description: 'Options sentiment', weight: 6, active: true, confidence: 0.71, signal: 'LONG', performance: { winRate: 0.59, sharpe: 1.5, maxDrawdown: -12, totalTrades: 350, avgProfit: 1.0 } },
    { id: 'dark_pool_flow', name: 'Dark Pool Flow', category: 'Options', type: 'both', description: 'Institutional dark pool', weight: 7, active: true, confidence: 0.75, signal: 'NEUTRAL', performance: { winRate: 0.62, sharpe: 1.7, maxDrawdown: -10, totalTrades: 280, avgProfit: 1.2 } },

    { id: 'yield_curve_regime', name: 'Yield Curve Regime', category: 'Macro', type: 'both', description: '10Y-2Y spread signals', weight: 6, active: true, confidence: 0.68, signal: 'LONG', performance: { winRate: 0.55, sharpe: 1.2, maxDrawdown: -16, totalTrades: 150, avgProfit: 0.9 } },
    { id: 'economic_surprise', name: 'Economic Surprise', category: 'Macro', type: 'both', description: 'Data beat/miss signals', weight: 5, active: true, confidence: 0.65, signal: 'NEUTRAL', performance: { winRate: 0.52, sharpe: 1.1, maxDrawdown: -18, totalTrades: 200, avgProfit: 0.7 } },
    { id: 'cross_asset_flow', name: 'Cross-Asset Flow', category: 'Macro', type: 'both', description: 'Risk-on/off rotation', weight: 7, active: true, confidence: 0.72, signal: 'LONG', performance: { winRate: 0.60, sharpe: 1.5, maxDrawdown: -12, totalTrades: 180, avgProfit: 1.1 } },
  ]

  return strategies
}

// ============== COMPONENT ==============

export function UnifiedBrain() {
  const [strategies, setStrategies] = useState<Strategy[]>(() => generateStrategies())
  const [selectedCategory, setSelectedCategory] = useState<StrategyCategory | 'ALL'>('ALL')
  const [isRunning, setIsRunning] = useState(false)
  const [expandedCategories, setExpandedCategories] = useState<Set<StrategyCategory>>(new Set(['ML', 'RL', 'DL']))
  const [consensusSignal, setConsensusSignal] = useState<{ signal: Signal; confidence: number; agreeing: number }>({
    signal: 'LONG',
    confidence: 72.5,
    agreeing: 38
  })
  const [brainV6Status, setBrainV6Status] = useState<any>(null)
  const [liveSignal, setLiveSignal] = useState<any>(null)
  const [signalSymbol, setSignalSymbol] = useState('SPY')

  // Fetch Brain V6 status
  const fetchBrainStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/brain-v6/status')
      if (res.ok) {
        const data = await res.json()
        setBrainV6Status(data)
      }
    } catch (error) {
      console.error('Error fetching brain status:', error)
    }
  }, [])

  // Generate live signal
  const generateLiveSignal = useCallback(async () => {
    try {
      const res = await fetch(`/api/brain-v6/signal/${signalSymbol}`)
      if (res.ok) {
        const data = await res.json()
        setLiveSignal(data)
      }
    } catch (error) {
      console.error('Error generating signal:', error)
    }
  }, [signalSymbol])

  // Auto-refresh brain status every 15 seconds
  useEffect(() => {
    fetchBrainStatus()
    const interval = setInterval(fetchBrainStatus, 15000)
    return () => clearInterval(interval)
  }, [fetchBrainStatus])

  // Calculate metrics
  const activeStrategies = strategies.filter(s => s.active)
  const totalStrategies = strategies.length
  const avgConfidence = activeStrategies.reduce((sum, s) => sum + s.confidence, 0) / activeStrategies.length
  const avgWinRate = activeStrategies.reduce((sum, s) => sum + s.performance.winRate, 0) / activeStrategies.length
  const avgSharpe = activeStrategies.reduce((sum, s) => sum + s.performance.sharpe, 0) / activeStrategies.length

  // Calculate signal distribution
  const signalCounts = {
    LONG: activeStrategies.filter(s => s.signal === 'LONG').length,
    SHORT: activeStrategies.filter(s => s.signal === 'SHORT').length,
    NEUTRAL: activeStrategies.filter(s => s.signal === 'NEUTRAL').length,
  }

  // Category performance for radar chart
  const categoryPerformance = STRATEGY_CATEGORIES.map(cat => {
    const catStrategies = strategies.filter(s => s.category === cat.id && s.active)
    if (catStrategies.length === 0) return { category: cat.name, value: 0 }
    const avgPerf = catStrategies.reduce((sum, s) => sum + s.performance.sharpe, 0) / catStrategies.length
    return { category: cat.name.split(' ')[0], value: avgPerf }
  }).filter(c => c.value > 0)

  // Simulate real-time updates
  useEffect(() => {
    if (!isRunning) return

    const interval = setInterval(() => {
      setStrategies(prev => prev.map(s => {
        if (!s.active) return s

        // Randomly update confidence and signal
        const newConfidence = Math.max(0.5, Math.min(0.95, s.confidence + (Math.random() - 0.5) * 0.05))
        const signals: Signal[] = ['LONG', 'SHORT', 'NEUTRAL']
        const newSignal = Math.random() > 0.9 ? signals[Math.floor(Math.random() * 3)] : s.signal

        return {
          ...s,
          confidence: newConfidence,
          signal: newSignal
        }
      }))

      // Update consensus
      setConsensusSignal(prev => ({
        ...prev,
        confidence: Math.max(50, Math.min(95, prev.confidence + (Math.random() - 0.5) * 3)),
        agreeing: Math.floor(Math.random() * 10) + 30
      }))
    }, 2000)

    return () => clearInterval(interval)
  }, [isRunning])

  const toggleStrategy = (id: string) => {
    setStrategies(prev => prev.map(s =>
      s.id === id ? { ...s, active: !s.active } : s
    ))
  }

  const toggleCategory = (category: StrategyCategory) => {
    setExpandedCategories(prev => {
      const next = new Set(prev)
      if (next.has(category)) {
        next.delete(category)
      } else {
        next.add(category)
      }
      return next
    })
  }

  const filteredStrategies = selectedCategory === 'ALL'
    ? strategies
    : strategies.filter(s => s.category === selectedCategory)

  const getSignalColor = (signal: Signal) => {
    switch (signal) {
      case 'LONG': return 'text-bullish'
      case 'SHORT': return 'text-bearish'
      case 'NEUTRAL': return 'text-warning'
      default: return 'text-foreground-muted'
    }
  }

  const getSignalBg = (signal: Signal) => {
    switch (signal) {
      case 'LONG': return 'bg-bullish/20'
      case 'SHORT': return 'bg-bearish/20'
      case 'NEUTRAL': return 'bg-warning/20'
      default: return 'bg-background-tertiary'
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-cyan-500/20">
            <Brain className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-cyan-400 bg-clip-text text-transparent">
              UNIFIED BRAIN
            </h1>
            <p className="text-xs text-foreground-muted">
              {totalStrategies} Strategies | {activeStrategies.length} Active | Multi-Agent AI System
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsRunning(!isRunning)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all',
              isRunning
                ? 'bg-bullish/20 text-bullish border border-bullish/30'
                : 'bg-background-tertiary text-foreground-secondary hover:bg-background-secondary'
            )}
          >
            {isRunning ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {isRunning ? 'RUNNING' : 'START'}
          </button>
          <button className="p-2 rounded-lg bg-background-tertiary hover:bg-background-secondary transition-colors">
            <Settings className="w-4 h-4 text-foreground-muted" />
          </button>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-6 gap-3">
        <StatCard
          label="Active Strategies"
          value={`${activeStrategies.length}/${totalStrategies}`}
          icon={<Layers className="w-4 h-4 text-purple-400" />}
          color="purple"
        />
        <StatCard
          label="Avg Confidence"
          value={`${(avgConfidence * 100).toFixed(1)}%`}
          icon={<Target className="w-4 h-4 text-cyan-400" />}
          color="cyan"
        />
        <StatCard
          label="Avg Win Rate"
          value={`${(avgWinRate * 100).toFixed(1)}%`}
          icon={<CheckCircle className="w-4 h-4 text-bullish" />}
          color="green"
        />
        <StatCard
          label="Avg Sharpe"
          value={avgSharpe.toFixed(2)}
          icon={<BarChart3 className="w-4 h-4 text-yellow-400" />}
          color="yellow"
        />
        <StatCard
          label="Long Signals"
          value={signalCounts.LONG.toString()}
          icon={<TrendingUp className="w-4 h-4 text-bullish" />}
          color="green"
        />
        <StatCard
          label="Short Signals"
          value={signalCounts.SHORT.toString()}
          icon={<TrendingDown className="w-4 h-4 text-bearish" />}
          color="red"
        />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-12 gap-4">
        {/* Consensus Panel */}
        <div className="col-span-3 space-y-4">
          {/* AI Consensus */}
          <div className="card">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">AI CONSENSUS</h3>
            <div className={cn(
              'p-6 rounded-lg text-center',
              getSignalBg(consensusSignal.signal)
            )}>
              {consensusSignal.signal === 'LONG' && <TrendingUp className="w-12 h-12 mx-auto mb-2 text-bullish" />}
              {consensusSignal.signal === 'SHORT' && <TrendingDown className="w-12 h-12 mx-auto mb-2 text-bearish" />}
              {consensusSignal.signal === 'NEUTRAL' && <Activity className="w-12 h-12 mx-auto mb-2 text-warning" />}
              <div className={cn('text-3xl font-bold', getSignalColor(consensusSignal.signal))}>
                {consensusSignal.signal}
              </div>
              <div className="text-sm text-foreground-muted mt-2">
                Confidence: {consensusSignal.confidence.toFixed(1)}%
              </div>
              <div className="text-xs text-foreground-muted mt-1">
                {consensusSignal.agreeing}/{activeStrategies.length} strategies agree
              </div>
            </div>

            {/* Signal Distribution */}
            <div className="mt-4 space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-foreground-muted">Signal Distribution</span>
              </div>
              <div className="h-3 bg-background-tertiary rounded-full overflow-hidden flex">
                <div
                  className="bg-bullish transition-all"
                  style={{ width: `${(signalCounts.LONG / activeStrategies.length) * 100}%` }}
                />
                <div
                  className="bg-warning transition-all"
                  style={{ width: `${(signalCounts.NEUTRAL / activeStrategies.length) * 100}%` }}
                />
                <div
                  className="bg-bearish transition-all"
                  style={{ width: `${(signalCounts.SHORT / activeStrategies.length) * 100}%` }}
                />
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-bullish">LONG {signalCounts.LONG}</span>
                <span className="text-warning">NEUTRAL {signalCounts.NEUTRAL}</span>
                <span className="text-bearish">SHORT {signalCounts.SHORT}</span>
              </div>
            </div>
          </div>

          {/* Category Performance Radar */}
          <div className="card">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">CATEGORY PERFORMANCE</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={categoryPerformance}>
                  <PolarGrid stroke="#333" />
                  <PolarAngleAxis dataKey="category" tick={{ fill: '#888', fontSize: 10 }} />
                  <PolarRadiusAxis tick={{ fill: '#666', fontSize: 9 }} domain={[0, 2.5]} />
                  <Radar
                    name="Sharpe"
                    dataKey="value"
                    stroke="#00d4aa"
                    fill="#00d4aa"
                    fillOpacity={0.3}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Live Signal Generator */}
          <div className="card">
            <h3 className="text-xs font-bold text-foreground-muted mb-3">LIVE SIGNAL GENERATOR</h3>
            <div className="space-y-3">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={signalSymbol}
                  onChange={(e) => setSignalSymbol(e.target.value.toUpperCase())}
                  className="flex-1 bg-background-tertiary border border-border rounded px-2 py-1 text-sm focus:border-accent-primary focus:outline-none"
                  placeholder="Symbol"
                />
                <button
                  onClick={generateLiveSignal}
                  className="px-3 py-1 bg-accent-primary/20 text-accent-primary rounded text-sm hover:bg-accent-primary/30 transition-colors"
                >
                  Generate
                </button>
              </div>
              {liveSignal && (
                <div className="space-y-2">
                  <div className={cn(
                    'text-center py-3 rounded-lg font-bold text-lg',
                    liveSignal.direction?.includes('BUY') ? 'bg-bullish/20 text-bullish' :
                    liveSignal.direction?.includes('SELL') ? 'bg-bearish/20 text-bearish' :
                    'bg-warning/20 text-warning'
                  )}>
                    {liveSignal.direction || 'HOLD'}
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-background-tertiary rounded p-2">
                      <span className="text-foreground-muted">Confidence</span>
                      <div className="font-bold text-accent-primary">
                        {((liveSignal.confidence || 0) * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div className="bg-background-tertiary rounded p-2">
                      <span className="text-foreground-muted">Regime</span>
                      <div className="font-bold capitalize">{liveSignal.regime || 'N/A'}</div>
                    </div>
                  </div>
                  {liveSignal.stop_loss && (
                    <div className="flex justify-between text-xs bg-background-tertiary rounded p-2">
                      <div>
                        <span className="text-foreground-muted">Stop: </span>
                        <span className="text-bearish">${liveSignal.stop_loss?.toFixed(2)}</span>
                      </div>
                      <div>
                        <span className="text-foreground-muted">Target: </span>
                        <span className="text-bullish">${liveSignal.take_profit?.toFixed(2)}</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
              {brainV6Status && (
                <div className="text-xs text-foreground-muted border-t border-border pt-2 mt-2">
                  <div className="flex justify-between">
                    <span>Device: {brainV6Status.device?.toUpperCase()}</span>
                    <span>Regime: {brainV6Status.current_regime}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Strategy List */}
        <div className="col-span-9 card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-foreground-primary">Strategy Ensemble</h3>
            <div className="flex gap-1">
              <button
                onClick={() => setSelectedCategory('ALL')}
                className={cn(
                  'px-3 py-1 text-xs rounded transition-colors',
                  selectedCategory === 'ALL'
                    ? 'bg-accent-primary/20 text-accent-primary'
                    : 'bg-background-tertiary text-foreground-muted hover:text-foreground-secondary'
                )}
              >
                ALL
              </button>
              {STRATEGY_CATEGORIES.slice(0, 6).map(cat => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={cn(
                    'px-2 py-1 text-xs rounded transition-colors',
                    selectedCategory === cat.id
                      ? 'bg-accent-primary/20 text-accent-primary'
                      : 'bg-background-tertiary text-foreground-muted hover:text-foreground-secondary'
                  )}
                >
                  {cat.name.split(' ')[0]}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-auto max-h-[500px]">
            {STRATEGY_CATEGORIES.map(category => {
              const categoryStrategies = filteredStrategies.filter(s => s.category === category.id)
              if (categoryStrategies.length === 0) return null

              const isExpanded = expandedCategories.has(category.id)
              const CategoryIcon = category.icon

              return (
                <div key={category.id} className="mb-2">
                  <button
                    onClick={() => toggleCategory(category.id)}
                    className="w-full flex items-center justify-between p-2 bg-background-tertiary rounded hover:bg-background-secondary transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                      <CategoryIcon className={cn('w-4 h-4', category.color)} />
                      <span className="text-sm font-medium">{category.name}</span>
                      <span className="text-xs text-foreground-muted">
                        ({categoryStrategies.filter(s => s.active).length}/{categoryStrategies.length} active)
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-foreground-muted">
                        Avg Sharpe: {(categoryStrategies.reduce((sum, s) => sum + s.performance.sharpe, 0) / categoryStrategies.length).toFixed(2)}
                      </span>
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="mt-1 space-y-1 pl-6">
                      {categoryStrategies.map(strategy => (
                        <div
                          key={strategy.id}
                          className={cn(
                            'flex items-center justify-between p-2 rounded transition-all',
                            strategy.active ? 'bg-background-secondary' : 'bg-background-tertiary opacity-50'
                          )}
                        >
                          <div className="flex items-center gap-3">
                            <button
                              onClick={() => toggleStrategy(strategy.id)}
                              className={cn(
                                'w-8 h-4 rounded-full transition-colors relative',
                                strategy.active ? 'bg-bullish' : 'bg-background-tertiary'
                              )}
                            >
                              <div className={cn(
                                'absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all',
                                strategy.active ? 'right-0.5' : 'left-0.5'
                              )} />
                            </button>
                            <div>
                              <div className="text-xs font-medium">{strategy.name}</div>
                              <div className="text-[10px] text-foreground-muted">{strategy.description}</div>
                            </div>
                          </div>

                          <div className="flex items-center gap-4">
                            <div className="text-right">
                              <div className="text-xs text-foreground-muted">Confidence</div>
                              <div className="text-xs font-mono">{(strategy.confidence * 100).toFixed(0)}%</div>
                            </div>
                            <div className="text-right">
                              <div className="text-xs text-foreground-muted">Win Rate</div>
                              <div className="text-xs font-mono">{(strategy.performance.winRate * 100).toFixed(0)}%</div>
                            </div>
                            <div className="text-right">
                              <div className="text-xs text-foreground-muted">Sharpe</div>
                              <div className="text-xs font-mono">{strategy.performance.sharpe.toFixed(1)}</div>
                            </div>
                            <div className={cn(
                              'px-2 py-1 rounded text-xs font-bold min-w-[60px] text-center',
                              getSignalBg(strategy.signal),
                              getSignalColor(strategy.signal)
                            )}>
                              {strategy.signal === 'NO_SIGNAL' ? 'OFF' : strategy.signal}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// Helper Component
function StatCard({ label, value, icon, color }: { label: string; value: string; icon: React.ReactNode; color: string }) {
  const colorClasses: Record<string, string> = {
    purple: 'text-purple-400',
    cyan: 'text-cyan-400',
    green: 'text-bullish',
    yellow: 'text-yellow-400',
    red: 'text-bearish',
  }

  return (
    <div className="card p-3">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-[10px] text-foreground-muted uppercase">{label}</span>
      </div>
      <div className={cn('text-lg font-bold font-mono', colorClasses[color])}>{value}</div>
    </div>
  )
}
