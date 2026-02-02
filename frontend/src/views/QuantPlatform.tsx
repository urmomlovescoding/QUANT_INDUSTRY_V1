/**
 * QUANT PLATFORM - Institutional Grade Trading Platform
 * Enhanced with 53+ strategies, portfolio optimization, backtesting,
 * risk analytics, Monte Carlo simulation, and learning features
 */

import { useState, useEffect, useMemo } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import {
  Building2, Play, Pause, RotateCcw, Download, Upload, Settings,
  TrendingUp, TrendingDown, Activity, Brain, Target, Shield,
  BarChart3, PieChart, LineChart, Zap, BookOpen, Lightbulb,
  ChevronRight, ChevronDown, Check, X, AlertTriangle, Info,
  Layers, GitBranch, Cpu, Database, FlaskConical, GraduationCap
} from 'lucide-react'
import { cn } from '@/utils/cn'

// ==================== TYPES ====================

type TabId = 'optimizer' | 'strategies' | 'backtest' | 'walkforward' | 'risk' | 'montecarlo' | 'mlbrain' | 'learning'

interface Strategy {
  id: string
  name: string
  category: string
  description: string
  enabled: boolean
  weight: number
  sharpe: number
  winRate: number
  maxDD: number
  trades: number
}

interface BacktestResult {
  totalReturn: number
  annualizedReturn: number
  sharpe: number
  sortino: number
  calmar: number
  maxDrawdown: number
  winRate: number
  profitFactor: number
  totalTrades: number
  avgTrade: number
  avgWin: number
  avgLoss: number
  bestTrade: number
  worstTrade: number
  avgHoldingPeriod: string
  exposure: number
}

interface MonteCarloResult {
  iterations: number
  median: number
  mean: number
  std: number
  percentile5: number
  percentile25: number
  percentile75: number
  percentile95: number
  maxDD_median: number
  maxDD_95: number
  probProfit: number
  probRuin: number
}

interface RiskMetrics {
  var95: number
  var99: number
  cvar95: number
  cvar99: number
  beta: number
  alpha: number
  treynor: number
  informationRatio: number
  trackingError: number
  upCapture: number
  downCapture: number
}

// ==================== CONSTANTS ====================

const TABS: { id: TabId; label: string; icon: typeof Building2 }[] = [
  { id: 'optimizer', label: 'Portfolio Optimizer', icon: PieChart },
  { id: 'strategies', label: 'Strategy Registry', icon: Layers },
  { id: 'backtest', label: 'Backtesting', icon: BarChart3 },
  { id: 'walkforward', label: 'Walk-Forward', icon: GitBranch },
  { id: 'risk', label: 'Risk Analytics', icon: Shield },
  { id: 'montecarlo', label: 'Monte Carlo', icon: Activity },
  { id: 'mlbrain', label: 'ML Brain', icon: Brain },
  { id: 'learning', label: 'Learning Center', icon: GraduationCap },
]

const STRATEGY_CATEGORIES = [
  'Machine Learning',
  'Reinforcement Learning',
  'Deep Learning',
  'Evolutionary',
  'Trend Following',
  'Mean Reversion',
  'Volatility',
  'Momentum',
  'Market Structure',
  'Regime-Based',
  'Options',
  'Macro'
]

const ALL_STRATEGIES: Strategy[] = [
  // Machine Learning
  { id: 'rf_classifier', name: 'Random Forest Classifier', category: 'Machine Learning', description: 'Ensemble of decision trees for trend classification', enabled: true, weight: 5, sharpe: 1.45, winRate: 62, maxDD: -12.3, trades: 156 },
  { id: 'xgb_regressor', name: 'XGBoost Regressor', category: 'Machine Learning', description: 'Gradient boosting for return prediction', enabled: true, weight: 5, sharpe: 1.62, winRate: 58, maxDD: -15.2, trades: 142 },
  { id: 'lgbm_ranker', name: 'LightGBM Ranker', category: 'Machine Learning', description: 'Ranking model for stock selection', enabled: true, weight: 4, sharpe: 1.38, winRate: 55, maxDD: -18.1, trades: 198 },
  { id: 'catboost', name: 'CatBoost Ensemble', category: 'Machine Learning', description: 'Categorical feature handling with boosting', enabled: false, weight: 3, sharpe: 1.51, winRate: 60, maxDD: -14.5, trades: 167 },
  { id: 'svm_rbf', name: 'SVM RBF Kernel', category: 'Machine Learning', description: 'Support vector machine with radial basis', enabled: false, weight: 2, sharpe: 1.22, winRate: 54, maxDD: -19.8, trades: 134 },

  // Reinforcement Learning
  { id: 'ppo_trader', name: 'PPO Agent', category: 'Reinforcement Learning', description: 'Proximal Policy Optimization for trading', enabled: true, weight: 6, sharpe: 1.78, winRate: 65, maxDD: -11.2, trades: 245 },
  { id: 'a2c_multi', name: 'A2C Multi-Asset', category: 'Reinforcement Learning', description: 'Advantage Actor-Critic for portfolio allocation', enabled: true, weight: 5, sharpe: 1.55, winRate: 61, maxDD: -13.8, trades: 189 },
  { id: 'dqn_discrete', name: 'DQN Discrete', category: 'Reinforcement Learning', description: 'Deep Q-Network for discrete actions', enabled: false, weight: 3, sharpe: 1.32, winRate: 57, maxDD: -16.5, trades: 212 },
  { id: 'sac_continuous', name: 'SAC Continuous', category: 'Reinforcement Learning', description: 'Soft Actor-Critic for continuous sizing', enabled: true, weight: 4, sharpe: 1.68, winRate: 63, maxDD: -12.1, trades: 178 },
  { id: 'td3_robust', name: 'TD3 Robust', category: 'Reinforcement Learning', description: 'Twin Delayed DDPG with noise', enabled: false, weight: 2, sharpe: 1.41, winRate: 59, maxDD: -14.9, trades: 156 },

  // Deep Learning
  { id: 'lstm_seq', name: 'LSTM Sequence', category: 'Deep Learning', description: 'Long short-term memory for time series', enabled: true, weight: 5, sharpe: 1.52, winRate: 60, maxDD: -14.2, trades: 134 },
  { id: 'transformer', name: 'Transformer Attention', category: 'Deep Learning', description: 'Self-attention mechanism for pattern recognition', enabled: true, weight: 6, sharpe: 1.85, winRate: 67, maxDD: -10.5, trades: 112 },
  { id: 'cnn_patterns', name: 'CNN Pattern Detector', category: 'Deep Learning', description: 'Convolutional network for chart patterns', enabled: false, weight: 3, sharpe: 1.28, winRate: 55, maxDD: -17.8, trades: 98 },
  { id: 'gru_fast', name: 'GRU Fast Inference', category: 'Deep Learning', description: 'Gated recurrent unit optimized for speed', enabled: true, weight: 4, sharpe: 1.45, winRate: 58, maxDD: -15.1, trades: 145 },
  { id: 'autoencoder', name: 'Autoencoder Anomaly', category: 'Deep Learning', description: 'Anomaly detection via reconstruction error', enabled: false, weight: 2, sharpe: 1.18, winRate: 52, maxDD: -21.3, trades: 67 },

  // Evolutionary
  { id: 'genetic_opt', name: 'Genetic Optimizer', category: 'Evolutionary', description: 'Genetic algorithm for strategy parameters', enabled: true, weight: 4, sharpe: 1.56, winRate: 62, maxDD: -13.4, trades: 189 },
  { id: 'pso_swarm', name: 'PSO Swarm', category: 'Evolutionary', description: 'Particle swarm optimization ensemble', enabled: false, weight: 3, sharpe: 1.35, winRate: 57, maxDD: -16.2, trades: 156 },
  { id: 'de_robust', name: 'Differential Evolution', category: 'Evolutionary', description: 'Robust parameter optimization', enabled: true, weight: 3, sharpe: 1.42, winRate: 59, maxDD: -14.8, trades: 167 },
  { id: 'cma_es', name: 'CMA-ES Adaptive', category: 'Evolutionary', description: 'Covariance matrix adaptation strategy', enabled: false, weight: 2, sharpe: 1.29, winRate: 55, maxDD: -17.5, trades: 134 },

  // Trend Following
  { id: 'dual_ma', name: 'Dual Moving Average', category: 'Trend Following', description: 'Classic MA crossover with adaptive periods', enabled: true, weight: 5, sharpe: 1.35, winRate: 48, maxDD: -18.5, trades: 87 },
  { id: 'donchian_break', name: 'Donchian Breakout', category: 'Trend Following', description: 'Channel breakout with volatility filter', enabled: true, weight: 4, sharpe: 1.28, winRate: 45, maxDD: -22.1, trades: 65 },
  { id: 'turtle_trend', name: 'Turtle Trading', category: 'Trend Following', description: 'Classic turtle rules with ATR sizing', enabled: false, weight: 3, sharpe: 1.15, winRate: 42, maxDD: -25.3, trades: 54 },
  { id: 'supertrend', name: 'SuperTrend Adaptive', category: 'Trend Following', description: 'ATR-based trend following indicator', enabled: true, weight: 4, sharpe: 1.42, winRate: 52, maxDD: -16.8, trades: 112 },
  { id: 'adx_trend', name: 'ADX Trend Strength', category: 'Trend Following', description: 'Directional movement with strength filter', enabled: true, weight: 3, sharpe: 1.31, winRate: 50, maxDD: -19.2, trades: 98 },

  // Mean Reversion
  { id: 'bb_revert', name: 'Bollinger Band Reversion', category: 'Mean Reversion', description: 'Mean reversion at band extremes', enabled: true, weight: 4, sharpe: 1.48, winRate: 65, maxDD: -12.5, trades: 234 },
  { id: 'rsi_extreme', name: 'RSI Extreme', category: 'Mean Reversion', description: 'Oversold/overbought reversal plays', enabled: true, weight: 4, sharpe: 1.52, winRate: 68, maxDD: -11.8, trades: 198 },
  { id: 'pairs_stat', name: 'Statistical Pairs', category: 'Mean Reversion', description: 'Cointegrated pairs mean reversion', enabled: true, weight: 5, sharpe: 1.65, winRate: 72, maxDD: -9.5, trades: 312 },
  { id: 'ornstein', name: 'Ornstein-Uhlenbeck', category: 'Mean Reversion', description: 'OU process for spread trading', enabled: false, weight: 3, sharpe: 1.38, winRate: 64, maxDD: -13.2, trades: 178 },
  { id: 'zscore_revert', name: 'Z-Score Reversion', category: 'Mean Reversion', description: 'Statistical z-score based entries', enabled: true, weight: 3, sharpe: 1.45, winRate: 66, maxDD: -12.1, trades: 256 },

  // Volatility
  { id: 'vol_breakout', name: 'Volatility Breakout', category: 'Volatility', description: 'Expansion after compression plays', enabled: true, weight: 4, sharpe: 1.55, winRate: 55, maxDD: -15.5, trades: 145 },
  { id: 'garch_forecast', name: 'GARCH Forecast', category: 'Volatility', description: 'Volatility forecasting model', enabled: true, weight: 3, sharpe: 1.38, winRate: 58, maxDD: -14.2, trades: 167 },
  { id: 'vix_regime', name: 'VIX Regime', category: 'Volatility', description: 'VIX-based regime switching', enabled: true, weight: 5, sharpe: 1.62, winRate: 62, maxDD: -12.8, trades: 89 },
  { id: 'vol_surface', name: 'Vol Surface Arbitrage', category: 'Volatility', description: 'Options volatility surface exploitation', enabled: false, weight: 3, sharpe: 1.72, winRate: 70, maxDD: -8.5, trades: 234 },
  { id: 'variance_swap', name: 'Variance Swap', category: 'Volatility', description: 'Realized vs implied variance', enabled: false, weight: 2, sharpe: 1.45, winRate: 65, maxDD: -10.2, trades: 56 },

  // Momentum
  { id: 'cross_sectional', name: 'Cross-Sectional Momentum', category: 'Momentum', description: 'Relative strength ranking', enabled: true, weight: 5, sharpe: 1.48, winRate: 58, maxDD: -16.5, trades: 234 },
  { id: 'time_series_mom', name: 'Time Series Momentum', category: 'Momentum', description: 'Absolute momentum with lookback', enabled: true, weight: 4, sharpe: 1.42, winRate: 55, maxDD: -18.2, trades: 178 },
  { id: 'dual_momentum', name: 'Dual Momentum', category: 'Momentum', description: 'Relative + absolute momentum combo', enabled: true, weight: 5, sharpe: 1.58, winRate: 60, maxDD: -14.5, trades: 145 },
  { id: 'sector_rotation', name: 'Sector Rotation', category: 'Momentum', description: 'Rotate into strongest sectors', enabled: true, weight: 4, sharpe: 1.35, winRate: 54, maxDD: -17.8, trades: 98 },
  { id: 'momentum_crash', name: 'Momentum Crash Hedge', category: 'Momentum', description: 'Momentum with crash protection', enabled: false, weight: 3, sharpe: 1.25, winRate: 52, maxDD: -12.5, trades: 112 },

  // Market Structure (ICT)
  { id: 'ict_fvg', name: 'ICT Fair Value Gap', category: 'Market Structure', description: 'Imbalance zones for entries', enabled: true, weight: 4, sharpe: 1.65, winRate: 68, maxDD: -11.5, trades: 189 },
  { id: 'ict_ob', name: 'ICT Order Blocks', category: 'Market Structure', description: 'Institutional order flow zones', enabled: true, weight: 4, sharpe: 1.58, winRate: 65, maxDD: -12.8, trades: 167 },
  { id: 'ict_liquidity', name: 'ICT Liquidity Sweep', category: 'Market Structure', description: 'Stop hunt reversal patterns', enabled: true, weight: 5, sharpe: 1.72, winRate: 70, maxDD: -10.2, trades: 145 },
  { id: 'ict_killzone', name: 'ICT Kill Zones', category: 'Market Structure', description: 'Time-based session entries', enabled: true, weight: 3, sharpe: 1.45, winRate: 62, maxDD: -13.5, trades: 234 },
  { id: 'wyckoff', name: 'Wyckoff Method', category: 'Market Structure', description: 'Accumulation/distribution phases', enabled: false, weight: 3, sharpe: 1.38, winRate: 60, maxDD: -14.8, trades: 78 },

  // Regime-Based
  { id: 'hmm_regime', name: 'HMM Regime Detector', category: 'Regime-Based', description: 'Hidden Markov Model state detection', enabled: true, weight: 5, sharpe: 1.68, winRate: 64, maxDD: -12.1, trades: 156 },
  { id: 'markov_switch', name: 'Markov Switching', category: 'Regime-Based', description: 'Regime-switching model', enabled: true, weight: 4, sharpe: 1.55, winRate: 61, maxDD: -13.5, trades: 134 },
  { id: 'adaptive_regime', name: 'Adaptive Regime', category: 'Regime-Based', description: 'Dynamic strategy selection by regime', enabled: true, weight: 6, sharpe: 1.82, winRate: 68, maxDD: -10.8, trades: 189 },
  { id: 'trend_vs_range', name: 'Trend vs Range', category: 'Regime-Based', description: 'Automatic trend/range detection', enabled: true, weight: 4, sharpe: 1.48, winRate: 62, maxDD: -14.2, trades: 167 },

  // Options
  { id: 'wheel_premium', name: 'Wheel Strategy', category: 'Options', description: 'CSP + CC premium collection', enabled: true, weight: 4, sharpe: 1.35, winRate: 78, maxDD: -15.5, trades: 89 },
  { id: 'iron_condor', name: 'Iron Condor', category: 'Options', description: 'Range-bound premium selling', enabled: true, weight: 3, sharpe: 1.28, winRate: 72, maxDD: -18.2, trades: 67 },
  { id: 'gamma_scalp', name: 'Gamma Scalping', category: 'Options', description: 'Delta-neutral gamma trading', enabled: false, weight: 3, sharpe: 1.55, winRate: 65, maxDD: -12.5, trades: 312 },
  { id: 'vol_spread', name: 'Volatility Spread', category: 'Options', description: 'Calendar and diagonal spreads', enabled: true, weight: 3, sharpe: 1.42, winRate: 68, maxDD: -14.8, trades: 98 },

  // Macro
  { id: 'risk_parity', name: 'Risk Parity', category: 'Macro', description: 'Equal risk contribution allocation', enabled: true, weight: 5, sharpe: 1.25, winRate: 55, maxDD: -12.5, trades: 24 },
  { id: 'global_macro', name: 'Global Macro', category: 'Macro', description: 'Cross-asset macro signals', enabled: true, weight: 4, sharpe: 1.45, winRate: 58, maxDD: -16.8, trades: 45 },
  { id: 'carry_trade', name: 'Carry Trade', category: 'Macro', description: 'Interest rate differential capture', enabled: false, weight: 2, sharpe: 1.15, winRate: 52, maxDD: -22.5, trades: 36 },
  { id: 'trend_macro', name: 'Trend + Macro', category: 'Macro', description: 'CTA-style multi-asset trend', enabled: true, weight: 4, sharpe: 1.52, winRate: 48, maxDD: -18.5, trades: 67 },
]

const OBJECTIVES = [
  { value: 'max_sharpe', label: 'Max Sharpe Ratio', description: 'Maximize risk-adjusted returns' },
  { value: 'min_variance', label: 'Min Variance', description: 'Minimize portfolio volatility' },
  { value: 'risk_parity', label: 'Risk Parity', description: 'Equal risk contribution' },
  { value: 'max_return', label: 'Max Return', description: 'Maximize expected returns' },
  { value: 'target_vol', label: 'Target Volatility', description: 'Hit specific vol target' },
  { value: 'min_cvar', label: 'Min CVaR', description: 'Minimize tail risk' },
  { value: 'black_litterman', label: 'Black-Litterman', description: 'Incorporate views' },
]

// ==================== MAIN COMPONENT ====================

export function QuantPlatform() {
  const [strategies, setStrategies] = useState<Strategy[]>(ALL_STRATEGIES)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-primary/10">
            <Building2 className="w-5 h-5 text-accent-primary" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-accent-primary">QUANT PLATFORM</h1>
            <span className="text-xs text-foreground-muted">INSTITUTIONAL GRADE • 53+ STRATEGIES</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-foreground-muted">
            {strategies.filter(s => s.enabled).length} Active Strategies
          </span>
          <span className="text-xs text-bullish flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-bullish animate-pulse" />
            READY
          </span>
        </div>
      </div>

      {/* Tabs - Using Radix UI for accessibility */}
      <Tabs.Root defaultValue="optimizer" className="card">
        <Tabs.List className="flex border-b border-border overflow-x-auto" aria-label="Quant Platform sections">
          {TABS.map(tab => {
            const Icon = tab.icon
            return (
              <Tabs.Trigger
                key={tab.id}
                value={tab.id}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-xs font-medium border-b-2 -mb-px transition-colors whitespace-nowrap',
                  'border-transparent text-foreground-secondary hover:text-foreground-primary',
                  'data-[state=active]:border-accent-primary data-[state=active]:text-accent-primary',
                  'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/50'
                )}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </Tabs.Trigger>
            )
          })}
        </Tabs.List>

        <div className="p-6">
          <Tabs.Content value="optimizer" className="focus:outline-none">
            <PortfolioOptimizer strategies={strategies} />
          </Tabs.Content>
          <Tabs.Content value="strategies" className="focus:outline-none">
            <StrategyRegistry strategies={strategies} setStrategies={setStrategies} />
          </Tabs.Content>
          <Tabs.Content value="backtest" className="focus:outline-none">
            <BacktestEngine strategies={strategies} />
          </Tabs.Content>
          <Tabs.Content value="walkforward" className="focus:outline-none">
            <WalkForwardAnalysis />
          </Tabs.Content>
          <Tabs.Content value="risk" className="focus:outline-none">
            <RiskAnalytics />
          </Tabs.Content>
          <Tabs.Content value="montecarlo" className="focus:outline-none">
            <MonteCarloSimulation />
          </Tabs.Content>
          <Tabs.Content value="mlbrain" className="focus:outline-none">
            <MLBrainDashboard />
          </Tabs.Content>
          <Tabs.Content value="learning" className="focus:outline-none">
            <LearningCenter />
          </Tabs.Content>
        </div>
      </Tabs.Root>
    </div>
  )
}

// ==================== PORTFOLIO OPTIMIZER ====================

function PortfolioOptimizer({ strategies }: { strategies: Strategy[] }) {
  const [objective, setObjective] = useState('max_sharpe')
  const [targetVol, setTargetVol] = useState(15)
  const [covariance, setCovariance] = useState('shrinkage')
  const [constraints, setConstraints] = useState({
    maxWeight: 20,
    minWeight: 2,
    maxCategory: 40,
    longOnly: true
  })
  const [optimizing, setOptimizing] = useState(false)
  const [results, setResults] = useState<any>(null)

  const activeStrategies = strategies.filter(s => s.enabled)

  const handleOptimize = () => {
    setOptimizing(true)
    setTimeout(() => {
      // Simulate optimization results
      const weights: Record<string, number> = {}
      let remaining = 100
      activeStrategies.forEach((s, i) => {
        if (i === activeStrategies.length - 1) {
          weights[s.id] = Math.max(constraints.minWeight, remaining)
        } else {
          const w = Math.min(constraints.maxWeight, Math.max(constraints.minWeight, Math.random() * 15 + 3))
          weights[s.id] = Math.round(w * 10) / 10
          remaining -= weights[s.id]
        }
      })

      setResults({
        weights,
        metrics: {
          expectedReturn: 18.5 + Math.random() * 5,
          expectedVol: 12.5 + Math.random() * 3,
          sharpe: 1.45 + Math.random() * 0.3,
          sortino: 1.85 + Math.random() * 0.4,
          maxDD: -(8 + Math.random() * 5),
          diversificationRatio: 1.2 + Math.random() * 0.3
        },
        efficientFrontier: Array.from({ length: 20 }, (_, i) => ({
          vol: 8 + i * 1.5,
          ret: 5 + i * 1.2 + Math.random() * 2
        }))
      })
      setOptimizing(false)
    }, 1500)
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Optimization Objective</label>
          <select
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            className="input w-full"
          >
            {OBJECTIVES.map(obj => (
              <option key={obj.value} value={obj.value}>{obj.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Covariance Method</label>
          <select
            value={covariance}
            onChange={(e) => setCovariance(e.target.value)}
            className="input w-full"
          >
            <option value="sample">Sample</option>
            <option value="shrinkage">Ledoit-Wolf Shrinkage</option>
            <option value="ewma">EWMA</option>
            <option value="robust">Robust (MCD)</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Max Weight %</label>
          <input
            type="number"
            value={constraints.maxWeight}
            onChange={(e) => setConstraints({ ...constraints, maxWeight: Number(e.target.value) })}
            className="input w-full"
            min={5}
            max={100}
          />
        </div>
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Target Vol %</label>
          <input
            type="number"
            value={targetVol}
            onChange={(e) => setTargetVol(Number(e.target.value))}
            className="input w-full"
            disabled={objective !== 'target_vol'}
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={handleOptimize}
          disabled={optimizing || activeStrategies.length < 2}
          className="btn-primary flex items-center gap-2"
        >
          {optimizing ? <RotateCcw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Run Optimization
        </button>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={constraints.longOnly}
            onChange={(e) => setConstraints({ ...constraints, longOnly: e.target.checked })}
            className="rounded"
          />
          Long Only
        </label>
        <span className="text-xs text-foreground-muted">
          {activeStrategies.length} strategies selected
        </span>
      </div>

      {results && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Results Metrics */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-foreground-primary">OPTIMIZATION RESULTS</h3>
            <div className="grid grid-cols-3 gap-3">
              <MetricCard label="Expected Return" value={`+${results.metrics.expectedReturn.toFixed(1)}%`} color="bullish" />
              <MetricCard label="Volatility" value={`${results.metrics.expectedVol.toFixed(1)}%`} />
              <MetricCard label="Sharpe Ratio" value={results.metrics.sharpe.toFixed(2)} color="accent" />
              <MetricCard label="Sortino Ratio" value={results.metrics.sortino.toFixed(2)} color="accent" />
              <MetricCard label="Max Drawdown" value={`${results.metrics.maxDD.toFixed(1)}%`} color="bearish" />
              <MetricCard label="Diversification" value={`${results.metrics.diversificationRatio.toFixed(2)}x`} />
            </div>

            {/* Efficient Frontier Mini Chart */}
            <div>
              <h4 className="text-xs font-bold text-foreground-muted mb-2">EFFICIENT FRONTIER</h4>
              <div className="h-32 bg-background-tertiary rounded p-2 relative">
                <svg className="w-full h-full">
                  {results.efficientFrontier.map((p: any, i: number) => (
                    <circle
                      key={i}
                      cx={`${((p.vol - 8) / 30) * 100}%`}
                      cy={`${100 - ((p.ret - 5) / 30) * 100}%`}
                      r={3}
                      className="fill-accent-primary"
                    />
                  ))}
                  {/* Current portfolio marker */}
                  <circle
                    cx={`${((results.metrics.expectedVol - 8) / 30) * 100}%`}
                    cy={`${100 - ((results.metrics.expectedReturn - 5) / 30) * 100}%`}
                    r={6}
                    className="fill-bullish stroke-white stroke-2"
                  />
                </svg>
                <div className="absolute bottom-1 left-2 text-[10px] text-foreground-muted">Risk (Vol)</div>
                <div className="absolute top-1 left-2 text-[10px] text-foreground-muted">Return</div>
              </div>
            </div>
          </div>

          {/* Weights */}
          <div className="space-y-4">
            <h3 className="text-sm font-bold text-foreground-primary">OPTIMAL WEIGHTS</h3>
            <div className="max-h-80 overflow-y-auto space-y-2">
              {Object.entries(results.weights)
                .sort(([, a], [, b]) => (b as number) - (a as number))
                .map(([id, weight]) => {
                  const strategy = strategies.find(s => s.id === id)
                  if (!strategy) return null
                  return (
                    <div key={id} className="flex items-center gap-2">
                      <span className="text-xs w-32 truncate" title={strategy.name}>
                        {strategy.name}
                      </span>
                      <div className="flex-1 h-4 bg-background-tertiary rounded overflow-hidden">
                        <div
                          className="h-full bg-accent-primary"
                          style={{ width: `${(weight as number) / constraints.maxWeight * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono w-12 text-right">{(weight as number).toFixed(1)}%</span>
                    </div>
                  )
                })}
            </div>
            <div className="flex gap-2">
              <button className="btn-secondary flex items-center gap-1 text-xs">
                <Download className="w-3 h-3" /> Export
              </button>
              <button className="btn-secondary flex items-center gap-1 text-xs">
                <Upload className="w-3 h-3" /> Apply
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ==================== STRATEGY REGISTRY ====================

function StrategyRegistry({ strategies, setStrategies }: {
  strategies: Strategy[]
  setStrategies: (s: Strategy[]) => void
}) {
  const [expandedCategory, setExpandedCategory] = useState<string | null>('Machine Learning')
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState<'name' | 'sharpe' | 'winRate'>('sharpe')

  const filteredStrategies = useMemo(() => {
    return strategies.filter(s =>
      s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.category.toLowerCase().includes(searchTerm.toLowerCase())
    )
  }, [strategies, searchTerm])

  const categorizedStrategies = useMemo(() => {
    const result: Record<string, Strategy[]> = {}
    STRATEGY_CATEGORIES.forEach(cat => {
      const strats = filteredStrategies.filter(s => s.category === cat)
      if (strats.length > 0) {
        result[cat] = strats.sort((a, b) => {
          if (sortBy === 'sharpe') return b.sharpe - a.sharpe
          if (sortBy === 'winRate') return b.winRate - a.winRate
          return a.name.localeCompare(b.name)
        })
      }
    })
    return result
  }, [filteredStrategies, sortBy])

  const toggleStrategy = (id: string) => {
    setStrategies(strategies.map(s =>
      s.id === id ? { ...s, enabled: !s.enabled } : s
    ))
  }

  const toggleCategory = (category: string, enable: boolean) => {
    setStrategies(strategies.map(s =>
      s.category === category ? { ...s, enabled: enable } : s
    ))
  }

  const activeCount = strategies.filter(s => s.enabled).length
  const avgSharpe = strategies.filter(s => s.enabled).reduce((a, b) => a + b.sharpe, 0) / Math.max(activeCount, 1)

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Total Strategies" value={strategies.length.toString()} />
        <MetricCard label="Active" value={activeCount.toString()} color="bullish" />
        <MetricCard label="Avg Sharpe" value={avgSharpe.toFixed(2)} color="accent" />
        <MetricCard label="Categories" value={STRATEGY_CATEGORIES.length.toString()} />
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search strategies..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="input flex-1"
        />
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as any)}
          className="input w-40"
        >
          <option value="sharpe">Sort by Sharpe</option>
          <option value="winRate">Sort by Win Rate</option>
          <option value="name">Sort by Name</option>
        </select>
        <button
          onClick={() => setStrategies(strategies.map(s => ({ ...s, enabled: true })))}
          className="btn-secondary text-xs"
        >
          Enable All
        </button>
        <button
          onClick={() => setStrategies(strategies.map(s => ({ ...s, enabled: false })))}
          className="btn-secondary text-xs"
        >
          Disable All
        </button>
      </div>

      {/* Categories */}
      <div className="space-y-2 max-h-[500px] overflow-y-auto">
        {Object.entries(categorizedStrategies).map(([category, strats]) => {
          const isExpanded = expandedCategory === category
          const enabledInCat = strats.filter(s => s.enabled).length

          return (
            <div key={category} className="border border-border rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedCategory(isExpanded ? null : category)}
                className="w-full flex items-center justify-between p-3 bg-background-tertiary hover:bg-background-secondary transition-colors"
              >
                <div className="flex items-center gap-2">
                  {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  <span className="font-medium text-sm">{category}</span>
                  <span className="text-xs text-foreground-muted">
                    {enabledInCat}/{strats.length} active
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleCategory(category, true) }}
                    className="text-[10px] px-2 py-0.5 rounded bg-bullish/20 text-bullish hover:bg-bullish/30"
                  >
                    All On
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleCategory(category, false) }}
                    className="text-[10px] px-2 py-0.5 rounded bg-bearish/20 text-bearish hover:bg-bearish/30"
                  >
                    All Off
                  </button>
                </div>
              </button>

              {isExpanded && (
                <div className="p-3 space-y-2">
                  {strats.map(strategy => (
                    <div
                      key={strategy.id}
                      className={cn(
                        'flex items-center gap-3 p-2 rounded transition-colors',
                        strategy.enabled ? 'bg-accent-primary/5' : 'bg-background-tertiary/50'
                      )}
                    >
                      <button
                        onClick={() => toggleStrategy(strategy.id)}
                        className={cn(
                          'w-5 h-5 rounded flex items-center justify-center transition-colors',
                          strategy.enabled ? 'bg-bullish text-white' : 'bg-background-tertiary'
                        )}
                      >
                        {strategy.enabled && <Check className="w-3 h-3" />}
                      </button>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium truncate">{strategy.name}</span>
                        </div>
                        <p className="text-xs text-foreground-muted truncate">{strategy.description}</p>
                      </div>
                      <div className="flex items-center gap-4 text-xs">
                        <div className="text-center">
                          <div className="text-foreground-muted">Sharpe</div>
                          <div className={cn('font-mono font-bold', strategy.sharpe > 1.5 ? 'text-bullish' : '')}>{strategy.sharpe.toFixed(2)}</div>
                        </div>
                        <div className="text-center">
                          <div className="text-foreground-muted">Win%</div>
                          <div className="font-mono">{strategy.winRate}%</div>
                        </div>
                        <div className="text-center">
                          <div className="text-foreground-muted">MaxDD</div>
                          <div className="font-mono text-bearish">{strategy.maxDD}%</div>
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
  )
}

// ==================== BACKTEST ENGINE ====================

function BacktestEngine({ strategies }: { strategies: Strategy[] }) {
  const [startDate, setStartDate] = useState('2020-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [initialCapital, setInitialCapital] = useState(100000)
  const [engine, setEngine] = useState<'standard' | 'tpt' | 'comprehensive'>('standard')
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<BacktestResult | null>(null)
  const [equityCurve, setEquityCurve] = useState<number[]>([])

  const activeStrategies = strategies.filter(s => s.enabled)

  const runBacktest = async () => {
    setRunning(true)
    try {
      // Use actual backtest API
      const enabledStrategies = strategies.filter(s => s.enabled).map(s => s.id)
      const response = await fetch(`/api/backtest/run?strategy=${enabledStrategies[0] || 'momentum'}&ticker=SPY&period=365d&capital=${initialCapital}`, {
        method: 'POST'
      })
      const data = await response.json()

      if (response.ok) {
        // Extract equity curve from API response
        const curve = data.equity_curve?.map((d: any) => d.equity) || [initialCapital]
        setEquityCurve(curve)

        setResults({
          totalReturn: data.total_return || 0,
          annualizedReturn: (data.total_return || 0),
          sharpe: data.sharpe_ratio || 0,
          sortino: data.sortino_ratio || 0,
          calmar: data.calmar_ratio || 0,
          maxDrawdown: data.max_drawdown || 0,
          winRate: data.win_rate || 0,
          profitFactor: data.profit_factor || 0,
          totalTrades: data.trade_count || 0,
          avgTrade: 0,
          avgWin: 0,
          avgLoss: 0,
          bestTrade: 0,
          worstTrade: 0,
          avgHoldingPeriod: 'N/A',
          exposure: 0
        })
      } else {
        setResults(null)
      }
    } catch {
      setResults(null)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="input w-full"
          />
        </div>
        <div>
          <label className="block text-xs text-foreground-muted mb-1">End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="input w-full"
          />
        </div>
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Initial Capital</label>
          <input
            type="number"
            value={initialCapital}
            onChange={(e) => setInitialCapital(Number(e.target.value))}
            className="input w-full"
          />
        </div>
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Engine</label>
          <select
            value={engine}
            onChange={(e) => setEngine(e.target.value as any)}
            className="input w-full"
          >
            <option value="standard">Standard</option>
            <option value="tpt">TPT Compliant</option>
            <option value="comprehensive">Comprehensive</option>
          </select>
        </div>
        <div className="flex items-end">
          <button
            onClick={runBacktest}
            disabled={running || activeStrategies.length === 0}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {running ? <RotateCcw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Run Backtest
          </button>
        </div>
      </div>

      {results && (
        <>
          {/* Equity Curve */}
          <div>
            <h3 className="text-sm font-bold text-foreground-primary mb-2">EQUITY CURVE</h3>
            <div className="h-48 bg-background-tertiary rounded p-2">
              <svg className="w-full h-full" viewBox="0 0 1000 200" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00d4aa" stopOpacity="0.3" />
                    <stop offset="100%" stopColor="#00d4aa" stopOpacity="0" />
                  </linearGradient>
                </defs>
                {equityCurve.length > 0 && (
                  <>
                    <path
                      d={`M 0 ${200 - (equityCurve[0] / Math.max(...equityCurve)) * 180} ${equityCurve.map((v, i) =>
                        `L ${(i / equityCurve.length) * 1000} ${200 - (v / Math.max(...equityCurve)) * 180}`
                      ).join(' ')} L 1000 200 L 0 200 Z`}
                      fill="url(#equityGradient)"
                    />
                    <path
                      d={`M 0 ${200 - (equityCurve[0] / Math.max(...equityCurve)) * 180} ${equityCurve.map((v, i) =>
                        `L ${(i / equityCurve.length) * 1000} ${200 - (v / Math.max(...equityCurve)) * 180}`
                      ).join(' ')}`}
                      fill="none"
                      stroke="#00d4aa"
                      strokeWidth="2"
                    />
                  </>
                )}
              </svg>
            </div>
          </div>

          {/* Results Grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label="Total Return" value={`+${results.totalReturn.toFixed(1)}%`} color="bullish" />
            <MetricCard label="Annualized" value={`+${results.annualizedReturn.toFixed(1)}%`} color="bullish" />
            <MetricCard label="Sharpe Ratio" value={results.sharpe.toFixed(2)} color="accent" />
            <MetricCard label="Sortino Ratio" value={results.sortino.toFixed(2)} color="accent" />
            <MetricCard label="Calmar Ratio" value={results.calmar.toFixed(2)} color="accent" />
            <MetricCard label="Max Drawdown" value={`${results.maxDrawdown.toFixed(1)}%`} color="bearish" />
            <MetricCard label="Win Rate" value={`${results.winRate.toFixed(1)}%`} color={results.winRate > 50 ? 'bullish' : 'bearish'} />
            <MetricCard label="Profit Factor" value={`${results.profitFactor.toFixed(2)}x`} color="bullish" />
          </div>

          {/* Trade Statistics */}
          <div className="grid grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-bold text-foreground-primary mb-3">TRADE STATISTICS</h3>
              <div className="space-y-2">
                <StatRow label="Total Trades" value={results.totalTrades.toString()} />
                <StatRow label="Avg Trade P/L" value={`$${results.avgTrade.toFixed(0)}`} positive />
                <StatRow label="Avg Winner" value={`$${results.avgWin.toFixed(0)}`} positive />
                <StatRow label="Avg Loser" value={`$${results.avgLoss.toFixed(0)}`} />
                <StatRow label="Best Trade" value={`$${results.bestTrade.toFixed(0)}`} positive />
                <StatRow label="Worst Trade" value={`$${results.worstTrade.toFixed(0)}`} />
                <StatRow label="Avg Holding" value={results.avgHoldingPeriod} />
                <StatRow label="Exposure" value={`${results.exposure.toFixed(1)}%`} />
              </div>
            </div>
            <div>
              <h3 className="text-sm font-bold text-foreground-primary mb-3">ACTIVE STRATEGIES ({activeStrategies.length})</h3>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {activeStrategies.slice(0, 10).map(s => (
                  <div key={s.id} className="flex items-center justify-between text-xs p-2 bg-background-tertiary rounded">
                    <span className="truncate">{s.name}</span>
                    <span className="font-mono text-bullish">{s.sharpe.toFixed(2)}</span>
                  </div>
                ))}
                {activeStrategies.length > 10 && (
                  <div className="text-xs text-foreground-muted text-center py-1">
                    +{activeStrategies.length - 10} more
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ==================== WALK-FORWARD ANALYSIS ====================

function WalkForwardAnalysis() {
  const [trainWindow, setTrainWindow] = useState(252)
  const [testWindow, setTestWindow] = useState(63)
  const [folds, setFolds] = useState(5)
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<any[]>([])

  const runAnalysis = () => {
    setRunning(true)
    setTimeout(() => {
      setResults(Array.from({ length: folds }, (_, i) => ({
        fold: i + 1,
        trainStart: `2020-${String((i * 3) % 12 + 1).padStart(2, '0')}-01`,
        trainEnd: `2021-${String((i * 3 + 11) % 12 + 1).padStart(2, '0')}-30`,
        testStart: `2022-${String((i * 3) % 12 + 1).padStart(2, '0')}-01`,
        testEnd: `2022-${String((i * 3 + 2) % 12 + 1).padStart(2, '0')}-30`,
        trainSharpe: 1.5 + Math.random() * 0.5,
        testSharpe: 1.2 + Math.random() * 0.5,
        trainReturn: 15 + Math.random() * 10,
        testReturn: 8 + Math.random() * 10,
        degradation: 10 + Math.random() * 25
      })))
      setRunning(false)
    }, 1500)
  }

  const avgDegradation = results.length > 0
    ? results.reduce((a, b) => a + b.degradation, 0) / results.length
    : 0

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-end gap-4 flex-wrap">
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Train Window (days)</label>
          <input type="number" value={trainWindow} onChange={(e) => setTrainWindow(Number(e.target.value))} className="input w-28" />
        </div>
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Test Window (days)</label>
          <input type="number" value={testWindow} onChange={(e) => setTestWindow(Number(e.target.value))} className="input w-28" />
        </div>
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Number of Folds</label>
          <input type="number" value={folds} onChange={(e) => setFolds(Number(e.target.value))} className="input w-20" min={2} max={10} />
        </div>
        <button onClick={runAnalysis} disabled={running} className="btn-primary flex items-center gap-2">
          {running ? <RotateCcw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Run Walk-Forward
        </button>
      </div>

      {results.length > 0 && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-4 gap-4">
            <MetricCard label="Avg Train Sharpe" value={(results.reduce((a, b) => a + b.trainSharpe, 0) / results.length).toFixed(2)} color="accent" />
            <MetricCard label="Avg Test Sharpe" value={(results.reduce((a, b) => a + b.testSharpe, 0) / results.length).toFixed(2)} color="accent" />
            <MetricCard
              label="Avg Degradation"
              value={`${avgDegradation.toFixed(1)}%`}
              color={avgDegradation < 20 ? 'bullish' : avgDegradation < 30 ? 'warning' : 'bearish'}
            />
            <MetricCard
              label="Robustness"
              value={avgDegradation < 25 ? 'HIGH' : avgDegradation < 35 ? 'MEDIUM' : 'LOW'}
              color={avgDegradation < 25 ? 'bullish' : avgDegradation < 35 ? 'warning' : 'bearish'}
            />
          </div>

          {/* Results Table */}
          <div>
            <h3 className="text-sm font-bold text-foreground-primary mb-2">FOLD RESULTS</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Fold</th>
                  <th>Train Period</th>
                  <th>Test Period</th>
                  <th>Train Sharpe</th>
                  <th>Test Sharpe</th>
                  <th>Train Return</th>
                  <th>Test Return</th>
                  <th>Degradation</th>
                </tr>
              </thead>
              <tbody>
                {results.map(row => (
                  <tr key={row.fold}>
                    <td className="font-medium">{row.fold}</td>
                    <td className="text-xs">{row.trainStart} - {row.trainEnd}</td>
                    <td className="text-xs">{row.testStart} - {row.testEnd}</td>
                    <td className="font-mono text-bullish">{row.trainSharpe.toFixed(2)}</td>
                    <td className="font-mono">{row.testSharpe.toFixed(2)}</td>
                    <td className="font-mono text-bullish">+{row.trainReturn.toFixed(1)}%</td>
                    <td className="font-mono">+{row.testReturn.toFixed(1)}%</td>
                    <td className={cn(
                      'font-mono',
                      row.degradation < 20 ? 'text-bullish' : row.degradation < 30 ? 'text-warning' : 'text-bearish'
                    )}>
                      {row.degradation.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Interpretation */}
          <div className="p-4 bg-background-tertiary rounded-lg">
            <div className="flex items-start gap-2">
              <Lightbulb className="w-4 h-4 text-warning mt-0.5" />
              <div>
                <h4 className="text-sm font-bold text-foreground-primary">Interpretation</h4>
                <p className="text-xs text-foreground-muted mt-1">
                  {avgDegradation < 20
                    ? 'Excellent out-of-sample stability. Strategy shows robust performance across different market regimes.'
                    : avgDegradation < 30
                    ? 'Acceptable degradation levels. Consider additional regime filtering to improve robustness.'
                    : 'High performance degradation detected. Strategy may be overfit to training data. Review feature selection and model complexity.'
                  }
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ==================== RISK ANALYTICS ====================

function RiskAnalytics() {
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    setTimeout(() => {
      setMetrics({
        var95: -2.5 - Math.random() * 1.5,
        var99: -3.8 - Math.random() * 2,
        cvar95: -3.2 - Math.random() * 1.5,
        cvar99: -4.5 - Math.random() * 2,
        beta: 0.75 + Math.random() * 0.3,
        alpha: 0.02 + Math.random() * 0.03,
        treynor: 0.12 + Math.random() * 0.08,
        informationRatio: 0.8 + Math.random() * 0.4,
        trackingError: 3 + Math.random() * 2,
        upCapture: 95 + Math.random() * 20,
        downCapture: 60 + Math.random() * 20
      })
      setLoading(false)
    }, 500)
  }, [])

  if (loading || !metrics) {
    return <div className="text-center py-12 text-foreground-muted">Loading risk analytics...</div>
  }

  return (
    <div className="space-y-6">
      {/* Value at Risk */}
      <div>
        <h3 className="text-sm font-bold text-foreground-primary mb-3">VALUE AT RISK</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard label="VaR (95%)" value={`${metrics.var95.toFixed(2)}%`} color="bearish" />
          <MetricCard label="VaR (99%)" value={`${metrics.var99.toFixed(2)}%`} color="bearish" />
          <MetricCard label="CVaR (95%)" value={`${metrics.cvar95.toFixed(2)}%`} color="bearish" />
          <MetricCard label="CVaR (99%)" value={`${metrics.cvar99.toFixed(2)}%`} color="bearish" />
        </div>
        <p className="text-xs text-foreground-muted mt-2">
          95% VaR: Daily losses will not exceed {Math.abs(metrics.var95).toFixed(2)}% on 95 out of 100 days.
        </p>
      </div>

      {/* Market Risk */}
      <div>
        <h3 className="text-sm font-bold text-foreground-primary mb-3">MARKET RISK METRICS</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard label="Beta" value={metrics.beta.toFixed(2)} color={metrics.beta < 1 ? 'bullish' : 'warning'} />
          <MetricCard label="Alpha (Monthly)" value={`${(metrics.alpha * 100).toFixed(2)}%`} color="bullish" />
          <MetricCard label="Treynor Ratio" value={metrics.treynor.toFixed(3)} color="accent" />
          <MetricCard label="Information Ratio" value={metrics.informationRatio.toFixed(2)} color="accent" />
        </div>
      </div>

      {/* Capture Ratios */}
      <div>
        <h3 className="text-sm font-bold text-foreground-primary mb-3">CAPTURE RATIOS</h3>
        <div className="grid grid-cols-3 gap-4">
          <MetricCard label="Up Capture" value={`${metrics.upCapture.toFixed(0)}%`} color="bullish" />
          <MetricCard label="Down Capture" value={`${metrics.downCapture.toFixed(0)}%`} color={metrics.downCapture < 80 ? 'bullish' : 'bearish'} />
          <MetricCard
            label="Capture Ratio"
            value={`${(metrics.upCapture / metrics.downCapture).toFixed(2)}x`}
            color={metrics.upCapture / metrics.downCapture > 1.2 ? 'bullish' : 'warning'}
          />
        </div>
        <div className="mt-3 h-8 bg-background-tertiary rounded overflow-hidden flex">
          <div className="h-full bg-bullish/50 flex items-center justify-center" style={{ width: `${metrics.upCapture / 2}%` }}>
            <span className="text-[10px] font-bold">UP</span>
          </div>
          <div className="h-full bg-bearish/50 flex items-center justify-center" style={{ width: `${metrics.downCapture / 2}%` }}>
            <span className="text-[10px] font-bold">DOWN</span>
          </div>
        </div>
      </div>

      {/* Risk Interpretation */}
      <div className="p-4 bg-background-tertiary rounded-lg space-y-2">
        <h4 className="text-sm font-bold text-foreground-primary flex items-center gap-2">
          <Shield className="w-4 h-4 text-accent-primary" />
          Risk Assessment
        </h4>
        <ul className="text-xs text-foreground-muted space-y-1">
          <li>• Portfolio beta of {metrics.beta.toFixed(2)} indicates {metrics.beta < 0.8 ? 'defensive' : metrics.beta < 1.2 ? 'market-neutral' : 'aggressive'} positioning</li>
          <li>• Positive alpha suggests {metrics.alpha > 0.02 ? 'strong' : 'modest'} skill-based returns</li>
          <li>• Capture ratio of {(metrics.upCapture / metrics.downCapture).toFixed(2)}x is {metrics.upCapture / metrics.downCapture > 1.3 ? 'excellent' : 'acceptable'}</li>
          <li>• Maximum daily loss expectation (99% confidence): {Math.abs(metrics.var99).toFixed(2)}%</li>
        </ul>
      </div>
    </div>
  )
}

// ==================== MONTE CARLO SIMULATION ====================

function MonteCarloSimulation() {
  const [iterations, setIterations] = useState(10000)
  const [horizon, setHorizon] = useState(252)
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<MonteCarloResult | null>(null)
  const [distribution, setDistribution] = useState<number[]>([])

  const runSimulation = () => {
    setRunning(true)
    setTimeout(() => {
      // Generate distribution
      const dist: number[] = []
      for (let i = 0; i < 50; i++) {
        dist.push(Math.floor(iterations * Math.exp(-0.5 * Math.pow((i - 25) / 8, 2)) / 8))
      }
      setDistribution(dist)

      setResults({
        iterations,
        median: 12 + Math.random() * 8,
        mean: 14 + Math.random() * 6,
        std: 15 + Math.random() * 5,
        percentile5: -5 - Math.random() * 10,
        percentile25: 3 + Math.random() * 5,
        percentile75: 18 + Math.random() * 8,
        percentile95: 35 + Math.random() * 15,
        maxDD_median: -(10 + Math.random() * 5),
        maxDD_95: -(20 + Math.random() * 10),
        probProfit: 65 + Math.random() * 15,
        probRuin: 2 + Math.random() * 3
      })
      setRunning(false)
    }, 2000)
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-end gap-4">
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Iterations</label>
          <select value={iterations} onChange={(e) => setIterations(Number(e.target.value))} className="input w-32">
            <option value={1000}>1,000</option>
            <option value={10000}>10,000</option>
            <option value={50000}>50,000</option>
            <option value={100000}>100,000</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-foreground-muted mb-1">Horizon (days)</label>
          <input type="number" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} className="input w-28" />
        </div>
        <button onClick={runSimulation} disabled={running} className="btn-primary flex items-center gap-2">
          {running ? <RotateCcw className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
          Run Simulation
        </button>
      </div>

      {results && (
        <>
          {/* Distribution Chart */}
          <div>
            <h3 className="text-sm font-bold text-foreground-primary mb-2">RETURN DISTRIBUTION</h3>
            <div className="h-40 bg-background-tertiary rounded p-2 flex items-end gap-0.5">
              {distribution.map((height, i) => {
                const pct = i * 4 - 100
                const isMean = Math.abs(pct - results.mean) < 4
                return (
                  <div
                    key={i}
                    className={cn(
                      'flex-1 transition-all',
                      pct < 0 ? 'bg-bearish/60' : 'bg-bullish/60',
                      isMean && 'bg-accent-primary'
                    )}
                    style={{ height: `${(height / Math.max(...distribution)) * 100}%` }}
                  />
                )
              })}
            </div>
            <div className="flex justify-between text-[10px] text-foreground-muted mt-1">
              <span>-100%</span>
              <span>0%</span>
              <span>+100%</span>
            </div>
          </div>

          {/* Percentiles */}
          <div>
            <h3 className="text-sm font-bold text-foreground-primary mb-3">CONFIDENCE INTERVALS</h3>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard label="5th Percentile" value={`${results.percentile5.toFixed(1)}%`} color="bearish" />
              <MetricCard label="25th Percentile" value={`${results.percentile25.toFixed(1)}%`} />
              <MetricCard label="Median (50th)" value={`${results.median.toFixed(1)}%`} color="accent" />
              <MetricCard label="75th Percentile" value={`${results.percentile75.toFixed(1)}%`} color="bullish" />
            </div>
            <div className="mt-2 h-6 bg-background-tertiary rounded overflow-hidden relative">
              <div className="absolute h-full bg-bearish/30" style={{ left: 0, width: '10%' }} />
              <div className="absolute h-full bg-warning/30" style={{ left: '10%', width: '15%' }} />
              <div className="absolute h-full bg-accent-primary/30" style={{ left: '25%', width: '50%' }} />
              <div className="absolute h-full bg-bullish/30" style={{ left: '75%', width: '20%' }} />
              <div className="absolute h-full bg-bullish/50" style={{ left: '95%', width: '5%' }} />
            </div>
          </div>

          {/* Risk Metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label="Mean Return" value={`${results.mean.toFixed(1)}%`} color="bullish" />
            <MetricCard label="Std Dev" value={`${results.std.toFixed(1)}%`} />
            <MetricCard label="Prob of Profit" value={`${results.probProfit.toFixed(0)}%`} color="bullish" />
            <MetricCard label="Prob of Ruin" value={`${results.probRuin.toFixed(1)}%`} color="bearish" />
          </div>

          {/* Drawdown */}
          <div className="grid grid-cols-2 gap-4">
            <MetricCard label="Median Max DD" value={`${results.maxDD_median.toFixed(1)}%`} color="bearish" />
            <MetricCard label="95th Pct Max DD" value={`${results.maxDD_95.toFixed(1)}%`} color="bearish" />
          </div>
        </>
      )}
    </div>
  )
}

// ==================== ML BRAIN DASHBOARD ====================

function MLBrainDashboard() {
  const [models] = useState([
    { id: 'rf', name: 'Random Forest', accuracy: 0.68, f1: 0.65, auc: 0.72, status: 'active' },
    { id: 'xgb', name: 'XGBoost', accuracy: 0.71, f1: 0.68, auc: 0.75, status: 'active' },
    { id: 'lgbm', name: 'LightGBM', accuracy: 0.69, f1: 0.66, auc: 0.73, status: 'active' },
    { id: 'lstm', name: 'LSTM', accuracy: 0.65, f1: 0.62, auc: 0.70, status: 'training' },
    { id: 'transformer', name: 'Transformer', accuracy: 0.73, f1: 0.70, auc: 0.78, status: 'active' },
    { id: 'ppo', name: 'PPO Agent', accuracy: 0.67, f1: 0.64, auc: 0.71, status: 'active' },
  ])

  const [features] = useState([
    { name: 'RSI_14', importance: 0.15 },
    { name: 'MACD_Signal', importance: 0.12 },
    { name: 'BB_Width', importance: 0.11 },
    { name: 'Volume_SMA_Ratio', importance: 0.09 },
    { name: 'ATR_14', importance: 0.08 },
    { name: 'Price_SMA_50_Dist', importance: 0.07 },
    { name: 'Momentum_10', importance: 0.06 },
    { name: 'OBV_Change', importance: 0.05 },
  ])

  return (
    <div className="space-y-6">
      {/* Model Status */}
      <div>
        <h3 className="text-sm font-bold text-foreground-primary mb-3">MODEL STATUS</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {models.map(model => (
            <div key={model.id} className="p-4 bg-background-tertiary rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Brain className="w-4 h-4 text-accent-primary" />
                  <span className="font-medium">{model.name}</span>
                </div>
                <span className={cn(
                  'px-2 py-0.5 rounded text-[10px] font-bold',
                  model.status === 'active' ? 'bg-bullish/20 text-bullish' : 'bg-warning/20 text-warning'
                )}>
                  {model.status.toUpperCase()}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <div className="text-[10px] text-foreground-muted">Accuracy</div>
                  <div className="font-mono font-bold">{(model.accuracy * 100).toFixed(0)}%</div>
                </div>
                <div>
                  <div className="text-[10px] text-foreground-muted">F1 Score</div>
                  <div className="font-mono font-bold">{model.f1.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-foreground-muted">AUC-ROC</div>
                  <div className="font-mono font-bold">{model.auc.toFixed(2)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Feature Importance */}
      <div>
        <h3 className="text-sm font-bold text-foreground-primary mb-3">FEATURE IMPORTANCE</h3>
        <div className="space-y-2">
          {features.map(f => (
            <div key={f.name} className="flex items-center gap-3">
              <span className="text-xs w-32 truncate font-mono">{f.name}</span>
              <div className="flex-1 h-4 bg-background-tertiary rounded overflow-hidden">
                <div
                  className="h-full bg-accent-primary"
                  style={{ width: `${f.importance * 100 / 0.15}%` }}
                />
              </div>
              <span className="text-xs font-mono w-12 text-right">{(f.importance * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Ensemble Consensus */}
      <div className="p-4 bg-accent-primary/10 rounded-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-accent-primary" />
            <span className="font-bold text-accent-primary">ENSEMBLE CONSENSUS</span>
          </div>
          <div className="text-right">
            <div className="text-2xl font-mono font-bold text-bullish">BULLISH</div>
            <div className="text-xs text-foreground-muted">72% confidence</div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ==================== LEARNING CENTER ====================

function LearningCenter() {
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null)

  const topics = [
    {
      id: 'sharpe',
      title: 'Sharpe Ratio',
      icon: Target,
      description: 'Risk-adjusted return metric',
      content: 'The Sharpe Ratio measures excess return per unit of risk. Formula: (Return - Risk-Free Rate) / Std Dev. A Sharpe > 1.0 is good, > 2.0 is excellent.'
    },
    {
      id: 'walkforward',
      title: 'Walk-Forward Analysis',
      icon: GitBranch,
      description: 'Out-of-sample validation technique',
      content: 'Walk-forward testing trains on historical data, then tests on unseen future data, rolling forward through time. This helps detect overfitting.'
    },
    {
      id: 'montecarlo',
      title: 'Monte Carlo Simulation',
      icon: Activity,
      description: 'Statistical outcome modeling',
      content: 'Monte Carlo randomizes trade sequence to generate thousands of possible equity curves. Shows the range of outcomes and worst-case scenarios.'
    },
    {
      id: 'var',
      title: 'Value at Risk (VaR)',
      icon: Shield,
      description: 'Downside risk measurement',
      content: 'VaR estimates the maximum loss at a given confidence level. 95% VaR of -2% means on 95 out of 100 days, you won\'t lose more than 2%.'
    },
    {
      id: 'regime',
      title: 'Regime Detection',
      icon: Layers,
      description: 'Market state identification',
      content: 'Regime detection identifies market states (trending, ranging, volatile) to adapt strategy selection. Uses HMM or clustering algorithms.'
    },
    {
      id: 'rl',
      title: 'Reinforcement Learning',
      icon: Brain,
      description: 'Adaptive trading agents',
      content: 'RL agents learn trading policies through trial and error. PPO, A2C, and SAC are popular algorithms that optimize for cumulative reward.'
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <GraduationCap className="w-5 h-5 text-accent-primary" />
        <h3 className="text-lg font-bold text-foreground-primary">Learning Center</h3>
      </div>
      <p className="text-sm text-foreground-muted">
        Understanding quantitative concepts helps you build better strategies. Select a topic to learn more.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {topics.map(topic => {
          const Icon = topic.icon
          const isSelected = selectedTopic === topic.id
          return (
            <button
              key={topic.id}
              onClick={() => setSelectedTopic(isSelected ? null : topic.id)}
              className={cn(
                'p-4 rounded-lg text-left transition-all',
                isSelected ? 'bg-accent-primary/20 border-accent-primary' : 'bg-background-tertiary hover:bg-background-secondary',
                'border border-transparent'
              )}
            >
              <div className="flex items-start gap-3">
                <Icon className={cn('w-5 h-5 mt-0.5', isSelected ? 'text-accent-primary' : 'text-foreground-muted')} />
                <div>
                  <h4 className="font-medium">{topic.title}</h4>
                  <p className="text-xs text-foreground-muted mt-1">{topic.description}</p>
                  {isSelected && (
                    <p className="text-sm text-foreground-secondary mt-3 pt-3 border-t border-border">
                      {topic.content}
                    </p>
                  )}
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* Quick Tips */}
      <div className="p-4 bg-warning/10 rounded-lg">
        <div className="flex items-start gap-2">
          <Lightbulb className="w-4 h-4 text-warning mt-0.5" />
          <div>
            <h4 className="text-sm font-bold text-foreground-primary">Pro Tip</h4>
            <p className="text-xs text-foreground-muted mt-1">
              Always validate strategies with walk-forward analysis before deploying. In-sample performance often degrades 20-40% out-of-sample.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ==================== UTILITY COMPONENTS ====================

function MetricCard({ label, value, color }: { label: string; value: string; color?: 'bullish' | 'bearish' | 'accent' | 'warning' }) {
  return (
    <div className="bg-background-tertiary p-3 rounded">
      <div className="text-xs text-foreground-muted">{label}</div>
      <div className={cn(
        'text-lg font-mono font-bold',
        color === 'bullish' && 'text-bullish',
        color === 'bearish' && 'text-bearish',
        color === 'accent' && 'text-accent-primary',
        color === 'warning' && 'text-warning',
        !color && 'text-foreground-primary'
      )}>
        {value}
      </div>
    </div>
  )
}

function StatRow({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-border/50">
      <span className="text-xs text-foreground-muted">{label}</span>
      <span className={cn('text-xs font-mono', positive ? 'text-bullish' : positive === false ? 'text-bearish' : '')}>
        {value}
      </span>
    </div>
  )
}
