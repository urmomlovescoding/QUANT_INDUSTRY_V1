/**
 * Learning Center View
 * =====================
 * Educational hub for the QUANT INDUSTRY platform.
 * Covers getting started, trading concepts, ML/AI features, and platform guides.
 */

import { useState } from 'react'
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Rocket,
  Key,
  PlayCircle,
  Brain,
  LayoutDashboard,
  TrendingUp,
  Gauge,
  Shield,
  Building,
  Calculator,
  Activity,
  Cpu,
  GitBranch,
  Layers,
  RefreshCw,
  BarChart3,
  Dice5,
  Repeat,
  Moon,
  FileSearch,
  Zap,
  Target,
  Workflow,
  Network,
  LineChart,
  Search,
} from 'lucide-react'
import { cn } from '@/utils/cn'

// -------------------------------------------------------------------
// Accordion primitive
// -------------------------------------------------------------------

interface AccordionItemData {
  id: string
  icon: React.ComponentType<{ className?: string }>
  title: string
  content: React.ReactNode
}

function AccordionItem({
  item,
  isOpen,
  onToggle,
}: {
  item: AccordionItemData
  isOpen: boolean
  onToggle: () => void
}) {
  const Icon = item.icon

  return (
    <div className="border border-border/60 rounded-lg overflow-hidden transition-colors hover:border-border">
      <button
        onClick={onToggle}
        className={cn(
          'w-full flex items-center gap-3 px-4 py-3 text-left transition-colors',
          isOpen
            ? 'bg-accent-primary/5 border-b border-border/40'
            : 'hover:bg-background-hover/40'
        )}
      >
        <div
          className={cn(
            'p-1.5 rounded-md flex-shrink-0',
            isOpen ? 'bg-accent-primary/15' : 'bg-background-tertiary'
          )}
        >
          <Icon
            className={cn(
              'w-4 h-4',
              isOpen ? 'text-accent-primary' : 'text-foreground-muted'
            )}
          />
        </div>
        <span
          className={cn(
            'flex-1 text-sm font-medium',
            isOpen ? 'text-accent-primary' : 'text-foreground-primary'
          )}
        >
          {item.title}
        </span>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-foreground-muted flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-foreground-muted flex-shrink-0" />
        )}
      </button>
      {isOpen && (
        <div className="px-4 py-4 text-sm text-foreground-secondary leading-relaxed space-y-3">
          {item.content}
        </div>
      )}
    </div>
  )
}

function AccordionGroup({
  items,
  allowMultiple = false,
}: {
  items: AccordionItemData[]
  allowMultiple?: boolean
}) {
  const [openIds, setOpenIds] = useState<string[]>([])

  const toggle = (id: string) => {
    setOpenIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      return allowMultiple ? [...prev, id] : [id]
    })
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <AccordionItem
          key={item.id}
          item={item}
          isOpen={openIds.includes(item.id)}
          onToggle={() => toggle(item.id)}
        />
      ))}
    </div>
  )
}

// -------------------------------------------------------------------
// Section wrapper
// -------------------------------------------------------------------

function Section({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <h2 className="text-base font-bold text-foreground-primary mb-1">
        {title}
      </h2>
      {description && (
        <p className="text-xs text-foreground-muted mb-4">{description}</p>
      )}
      {!description && <div className="mb-4" />}
      {children}
    </div>
  )
}

// -------------------------------------------------------------------
// Content definitions
// -------------------------------------------------------------------

const gettingStartedItems: AccordionItemData[] = [
  {
    id: 'gs-overview',
    icon: Rocket,
    title: 'Platform Overview — What QUANT INDUSTRY Does',
    content: (
      <>
        <p>
          QUANT INDUSTRY v10.0 is an institutional-grade quantitative trading platform that
          combines real-time market data, machine learning, reinforcement learning, and
          traditional technical analysis to generate actionable trading signals.
        </p>
        <p>
          The platform ingests live price feeds from Alpaca Markets (primary) and Yahoo Finance
          (fallback), processes them through a multi-stage signal pipeline, applies risk management
          constraints, and presents you with a unified dashboard of opportunities across equities,
          options, and futures.
        </p>
        <p>
          Core capabilities include: AI-driven signal generation, backtesting with walk-forward
          validation, Monte Carlo simulation, GEX analysis, dark pool flow tracking, pairs trading,
          13F filing analysis, and prop firm rule enforcement (TPT, APEX).
        </p>
      </>
    ),
  },
  {
    id: 'gs-setup',
    icon: Key,
    title: 'First-Time Setup — API Keys, Data Sources & Brokers',
    content: (
      <>
        <p>
          After launching the platform, navigate to <strong>Settings &gt; Data Sources</strong> to
          configure your market data providers. The minimum requirement is an Alpaca Markets API key
          for live equities data.
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Alpaca Markets</strong> — Primary data source. Provides real-time stock and
            crypto data plus paper/live trading execution. Sign up at alpaca.markets for a free API
            key.
          </li>
          <li>
            <strong>Tradier</strong> — Required for real options chain data. Provides streaming
            quotes and options execution.
          </li>
          <li>
            <strong>Finnhub</strong> — Supplementary real-time stock data and financial news
            sentiment.
          </li>
          <li>
            <strong>Polygon.io</strong> — Alternative data source for historical bars, options
            snapshots, and reference data.
          </li>
        </ul>
        <p>
          Once keys are entered, use the <em>Test Connection</em> button next to each provider to
          verify connectivity. Green status means you are ready to trade.
        </p>
      </>
    ),
  },
  {
    id: 'gs-backtest',
    icon: PlayCircle,
    title: 'Quick Start — Running Your First Backtest',
    content: (
      <>
        <p>
          Navigate to <strong>Analytics &gt; Backtesting</strong> and follow these steps:
        </p>
        <ol className="list-decimal list-inside space-y-1 ml-2">
          <li>Enter one or more ticker symbols (e.g., SPY, AAPL, MSFT).</li>
          <li>Select a date range. The minimum requirement is 50 bars of historical data.</li>
          <li>Choose a strategy preset or use the default ML ensemble.</li>
          <li>Set initial capital and position sizing rules.</li>
          <li>Click <strong>Run Backtest</strong> and wait for the results to render.</li>
        </ol>
        <p>
          Results include an equity curve, trade log, drawdown chart, and comprehensive metrics
          (Sharpe ratio, profit factor, win rate, max drawdown). You can then visualize the
          backtest in the <strong>Backtest Viz</strong> view for an interactive breakdown.
        </p>
      </>
    ),
  },
  {
    id: 'gs-brain',
    icon: Brain,
    title: 'Quick Start — Setting Up the ML Brain',
    content: (
      <>
        <p>
          The ML Brain (PropFirm Brain V6) is the core intelligence engine. To initialize it:
        </p>
        <ol className="list-decimal list-inside space-y-1 ml-2">
          <li>
            Go to <strong>Neural AI &gt; ML Training</strong>.
          </li>
          <li>
            Select a prop firm ruleset (TPT 50K, TPT 100K, or APEX 50K) or use the default.
          </li>
          <li>
            Click <strong>Start Training</strong>. The brain will train on historical data using
            an ensemble of XGBoost, LightGBM, SVM, and a neural network transformer.
          </li>
          <li>
            Training progress is shown in real time. Initial training typically takes 2-5 minutes
            depending on data volume.
          </li>
          <li>
            Once training completes, the brain will begin generating signals automatically. You can
            monitor its status on the <strong>Dashboard</strong> or the{' '}
            <strong>Unified Brain</strong> view.
          </li>
        </ol>
        <p>
          The feedback loop system continuously improves the brain by learning from executed
          trades. Convergence targets: 65% win rate, 1.5 profit factor, 1.5 Sharpe ratio.
        </p>
      </>
    ),
  },
  {
    id: 'gs-dashboard',
    icon: LayoutDashboard,
    title: 'Understanding the Dashboard',
    content: (
      <>
        <p>The main Dashboard is divided into several key areas:</p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Top Metrics Row</strong> — Portfolio value, today's P&L, win rate, and active
            signals count.
          </li>
          <li>
            <strong>Equity Curve</strong> — A real-time area chart of your portfolio value over
            time.
          </li>
          <li>
            <strong>Sector Allocation</strong> — Donut chart showing your portfolio distribution
            by sector.
          </li>
          <li>
            <strong>Active Signals Table</strong> — Live signals from the ML brain with
            confidence scores, direction, and target prices.
          </li>
          <li>
            <strong>Brain Status</strong> — Current state of the ML brain including training
            progress, model accuracy, and regime classification.
          </li>
          <li>
            <strong>Risk Gauges</strong> — Real-time drawdown, VaR, and exposure metrics.
          </li>
        </ul>
        <p>
          Data refreshes every 15 seconds automatically. You can force a manual refresh using the
          refresh button in the top-right corner.
        </p>
      </>
    ),
  },
]

const tradingConceptItems: AccordionItemData[] = [
  {
    id: 'tc-regimes',
    icon: Gauge,
    title: 'Market Regimes — What They Are & How the Platform Detects Them',
    content: (
      <>
        <p>
          A market regime is a persistent state characterized by specific volatility, trend, and
          correlation patterns. The platform classifies the market into 7 distinct regimes:
        </p>
        <ol className="list-decimal list-inside space-y-1 ml-2">
          <li><strong>Low Volatility Bull</strong> — Steady upward drift with compressed vol.</li>
          <li><strong>High Volatility Bull</strong> — Strong uptrend with large swings.</li>
          <li><strong>Low Volatility Bear</strong> — Slow grind lower.</li>
          <li><strong>High Volatility Bear</strong> — Sharp sell-offs and panic.</li>
          <li><strong>Mean Reversion</strong> — Range-bound, choppy price action.</li>
          <li><strong>Trending</strong> — Directional momentum in either direction.</li>
          <li><strong>Crisis</strong> — Extreme vol, correlation spikes, tail risk events.</li>
        </ol>
        <p>
          Detection uses a Bayesian Regime Detector backed by Hidden Markov Models (HMM). The
          detector analyzes rolling volatility, trend strength, volume patterns, and cross-asset
          correlations to assign a probability distribution across all 7 regimes in real time.
        </p>
        <p>
          Regime classification is critical because it controls which strategies the ensemble
          activates. For example, mean-reversion strategies are scaled up in range-bound regimes
          and suppressed during trending regimes.
        </p>
      </>
    ),
  },
  {
    id: 'tc-signals',
    icon: TrendingUp,
    title: 'Signal Generation Pipeline',
    content: (
      <>
        <p>
          The signal generation pipeline transforms raw market data into actionable trading
          signals through multiple stages:
        </p>
        <ol className="list-decimal list-inside space-y-1 ml-2">
          <li>
            <strong>Data Ingestion</strong> — Real-time price, volume, and order book data flows
            through a rate limiter and validator into the cache layer.
          </li>
          <li>
            <strong>Feature Engineering</strong> — The FeatureEngine computes 64+ technical
            indicators including RSI, MACD, Bollinger Bands, ATR, VWAP, OBV, and proprietary
            microstructure features.
          </li>
          <li>
            <strong>Regime Detection</strong> — The Bayesian detector classifies the current market
            state (see Market Regimes above).
          </li>
          <li>
            <strong>Model Inference</strong> — Multiple ML models (XGBoost, LightGBM, SVM, Neural
            Net) generate independent predictions.
          </li>
          <li>
            <strong>Meta-Learner</strong> — A stacking meta-learner combines individual model
            outputs into a unified signal with a confidence score.
          </li>
          <li>
            <strong>Strategy Ensemble</strong> — 20+ strategies vote on the signal, weighted
            dynamically based on regime and recent performance.
          </li>
          <li>
            <strong>Risk Filter</strong> — Signals are filtered through position sizing rules, max
            drawdown limits, and prop firm constraints before being presented.
          </li>
        </ol>
      </>
    ),
  },
  {
    id: 'tc-risk',
    icon: Shield,
    title: 'Risk Management — Position Sizing, Stop Losses & Drawdown Limits',
    content: (
      <>
        <p>
          The platform enforces a multi-layer risk management framework:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Position Sizing</strong> — Each trade is sized using a volatility-adjusted
            Kelly criterion. Maximum position size defaults to 10% of equity but is configurable
            in Settings &gt; Risk Management.
          </li>
          <li>
            <strong>Stop Losses</strong> — Automatic stop losses are placed using ATR-based
            trailing stops. The default is 2x ATR from entry, adjusted by regime volatility.
          </li>
          <li>
            <strong>Daily Loss Limit</strong> — Trading halts automatically when daily losses
            exceed the configured threshold (default $5,000).
          </li>
          <li>
            <strong>Max Drawdown</strong> — A kill switch triggers when portfolio drawdown exceeds
            the maximum threshold (default 15%), closing all positions.
          </li>
          <li>
            <strong>Correlation Risk</strong> — The system monitors cross-position correlations and
            reduces exposure when portfolio-level correlation exceeds 0.7.
          </li>
          <li>
            <strong>VaR Monitoring</strong> — Value-at-Risk is computed continuously. Positions are
            trimmed if portfolio VaR exceeds the configured limit.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: 'tc-propfirm',
    icon: Building,
    title: 'Prop Firm Rules — TPT & APEX',
    content: (
      <>
        <p>
          Prop firm challenges impose strict rules that the platform enforces automatically:
        </p>
        <div className="space-y-3">
          <div>
            <p className="font-medium text-foreground-primary">TPT (The Prop Trader)</p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>50K Account: Max daily loss $1,000, max drawdown $2,500, profit target $3,000.</li>
              <li>100K Account: Max daily loss $2,000, max drawdown $5,000, profit target $6,000.</li>
              <li>No trading during major news events (configurable).</li>
              <li>Minimum 5 trading days requirement.</li>
            </ul>
          </div>
          <div>
            <p className="font-medium text-foreground-primary">APEX</p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>50K Account: Max trailing drawdown $2,500, profit target $3,000.</li>
              <li>Trailing drawdown follows your equity high-water mark.</li>
              <li>No daily loss limit, but the trailing drawdown acts as a dynamic safeguard.</li>
            </ul>
          </div>
        </div>
        <p>
          The platform tracks these rules in real time on the{' '}
          <strong>TPT Dashboard</strong> and will warn you or auto-halt trading if you approach
          any limit.
        </p>
      </>
    ),
  },
  {
    id: 'tc-greeks',
    icon: Calculator,
    title: 'Options Greeks Explained',
    content: (
      <>
        <p>
          Options Greeks measure the sensitivity of an option's price to various factors:
        </p>
        <ul className="list-disc list-inside space-y-2 ml-2">
          <li>
            <strong>Delta</strong> — Rate of change of option price per $1 move in the underlying.
            Calls have positive delta (0 to 1), puts have negative delta (-1 to 0). At-the-money
            options have delta near 0.50.
          </li>
          <li>
            <strong>Gamma</strong> — Rate of change of delta per $1 move in the underlying. Highest
            for at-the-money options near expiration. High gamma means delta changes rapidly.
          </li>
          <li>
            <strong>Theta</strong> — Time decay: how much value an option loses per day. Always
            negative for long positions. Accelerates as expiration approaches.
          </li>
          <li>
            <strong>Vega</strong> — Sensitivity to implied volatility. A 1% increase in IV
            increases the option price by Vega dollars. Highest for at-the-money, longer-dated
            options.
          </li>
          <li>
            <strong>Rho</strong> — Sensitivity to interest rate changes. Usually the least impactful
            Greek for short-dated options.
          </li>
        </ul>
        <p>
          The platform displays Greeks for every option in the Options Lab and uses them for
          portfolio-level risk calculations.
        </p>
      </>
    ),
  },
  {
    id: 'tc-gex',
    icon: Activity,
    title: 'GEX Analysis Explained',
    content: (
      <>
        <p>
          GEX (Gamma Exposure) measures the total gamma exposure of market makers across all
          options strikes. It reveals where dealers are hedging and how their hedging activity
          influences the underlying stock.
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Positive GEX</strong> — Market makers are long gamma. They buy dips and sell
            rips to delta-hedge, which suppresses volatility and pins the price near high-GEX
            strikes.
          </li>
          <li>
            <strong>Negative GEX</strong> — Market makers are short gamma. They must sell into
            dips and buy into rallies, amplifying moves and increasing volatility.
          </li>
          <li>
            <strong>GEX Flip Level</strong> — The strike price where GEX transitions from positive
            to negative. Below this level, expect amplified moves.
          </li>
          <li>
            <strong>Max Pain</strong> — The strike where total option holder losses are maximized.
            Stocks tend to gravitate toward max pain near expiration.
          </li>
        </ul>
        <p>
          Access GEX analysis from <strong>Options &gt; GEX Analysis</strong>. The platform
          refreshes GEX data in real time and highlights key support/resistance levels derived
          from dealer positioning.
        </p>
      </>
    ),
  },
]

const mlAiItems: AccordionItemData[] = [
  {
    id: 'ml-ensemble',
    icon: Layers,
    title: 'How the Ensemble ML System Works',
    content: (
      <>
        <p>
          The ML ensemble combines four distinct model architectures, each with different
          strengths:
        </p>
        <ul className="list-disc list-inside space-y-2 ml-2">
          <li>
            <strong>XGBoost</strong> — Gradient-boosted decision trees. Excellent at capturing
            non-linear feature interactions. Fast inference, handles missing data gracefully.
            Primary workhorse for tabular features.
          </li>
          <li>
            <strong>LightGBM</strong> — Microsoft's gradient boosting framework. Similar to
            XGBoost but uses histogram-based splitting for faster training. Often produces
            complementary predictions due to different tree-building strategies.
          </li>
          <li>
            <strong>SVM (Support Vector Machine)</strong> — Finds optimal hyperplanes to separate
            bullish and bearish regimes. Works well in high-dimensional feature spaces and provides
            natural confidence calibration via distance from the decision boundary.
          </li>
          <li>
            <strong>TradingTransformer (Neural Net)</strong> — A custom multi-head attention plus
            LSTM hybrid encoder. Captures sequential dependencies and long-range patterns in price
            action that tree models miss. Trained with dropout and layer normalization for
            regularization.
          </li>
        </ul>
        <p>
          A stacking meta-learner (logistic regression) combines the four model outputs into a
          final prediction. Each model's weight is dynamically adjusted based on recent accuracy
          within the current market regime.
        </p>
      </>
    ),
  },
  {
    id: 'ml-rl',
    icon: Cpu,
    title: 'Reinforcement Learning for Trading',
    content: (
      <>
        <p>
          The platform uses Proximal Policy Optimization (PPO), a state-of-the-art reinforcement
          learning algorithm, to make trading decisions:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>State</strong> — The agent observes a feature vector containing price data,
            technical indicators, current position, P&L, and regime probabilities.
          </li>
          <li>
            <strong>Actions</strong> — Buy, sell, hold, with continuous position sizing.
          </li>
          <li>
            <strong>Reward</strong> — Risk-adjusted return (Sharpe-like) penalized for drawdown,
            excessive trading, and prop firm rule violations.
          </li>
          <li>
            <strong>Training</strong> — The PPO agent trains on historical episodes and continues
            learning from live trades via the feedback loop.
          </li>
        </ul>
        <p>
          PPO is chosen over other RL algorithms because it is stable, sample-efficient, and
          avoids the catastrophic policy updates that can occur with vanilla policy gradient
          methods. The clipped objective function ensures the policy does not change too
          drastically in a single update.
        </p>
      </>
    ),
  },
  {
    id: 'ml-features',
    icon: BarChart3,
    title: 'Feature Engineering — What 64+ Indicators Mean',
    content: (
      <>
        <p>
          The FeatureEngine computes a comprehensive set of technical and microstructure
          indicators. Key categories include:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Trend</strong> — SMA (10, 20, 50, 200), EMA (12, 26), MACD, ADX, Aroon,
            Supertrend.
          </li>
          <li>
            <strong>Momentum</strong> — RSI (14), Stochastic (14,3,3), Williams %R, CCI, ROC,
            MFI.
          </li>
          <li>
            <strong>Volatility</strong> — ATR (14), Bollinger Bands (20,2), Keltner Channels,
            Donchian Channels, historical volatility, realized vol.
          </li>
          <li>
            <strong>Volume</strong> — OBV, VWAP, A/D line, Chaikin Money Flow, volume profile,
            relative volume.
          </li>
          <li>
            <strong>Microstructure</strong> — Bid-ask spread, order flow imbalance, trade
            intensity, Kyle's lambda (price impact).
          </li>
          <li>
            <strong>Statistical</strong> — Z-score, skewness, kurtosis, Hurst exponent,
            autocorrelation.
          </li>
          <li>
            <strong>Cross-Asset</strong> — VIX level, sector ETF returns, yield curve slope,
            dollar index.
          </li>
        </ul>
        <p>
          Features are normalized using rolling z-scores over a configurable lookback window
          (default 252 days) before being fed into the ML models.
        </p>
      </>
    ),
  },
  {
    id: 'ml-walkforward',
    icon: GitBranch,
    title: 'Walk-Forward Validation Explained',
    content: (
      <>
        <p>
          Walk-forward validation is the gold standard for evaluating trading strategies. Unlike
          simple train/test splits, it simulates how the model would actually be used in
          production:
        </p>
        <ol className="list-decimal list-inside space-y-1 ml-2">
          <li>Train the model on data from period 1 to N.</li>
          <li>Test the model on the next unseen period (N+1 to N+K).</li>
          <li>Slide the window forward: train on period 2 to N+1, test on N+2 to N+K+1.</li>
          <li>Repeat until all data is consumed.</li>
        </ol>
        <p>
          This produces out-of-sample performance metrics for every period, giving a realistic
          estimate of how the strategy would have performed in live trading. It prevents
          look-ahead bias and overfitting to specific market conditions.
        </p>
        <p>
          The platform performs walk-forward validation automatically during backtests when the
          ML ensemble is selected as the strategy.
        </p>
      </>
    ),
  },
  {
    id: 'ml-feedback',
    icon: RefreshCw,
    title: 'Feedback Loop — How the System Learns from Trades',
    content: (
      <>
        <p>
          The feedback loop creates a closed-circuit learning system:
        </p>
        <div className="bg-background-tertiary rounded-lg p-3 font-mono text-xs text-foreground-muted">
          ML Brain &rarr; Signals &rarr; Trading Brain &rarr; Execution &rarr; Outcomes &rarr;
          Feedback &rarr; ML Brain (Adapt)
        </div>
        <ul className="list-disc list-inside space-y-1 ml-2 mt-3">
          <li>
            Every executed trade is recorded with entry/exit prices, timing, regime at entry,
            feature values, and model confidence.
          </li>
          <li>
            The feedback system computes outcome metrics: realized P&L, MAE (Maximum Adverse
            Excursion), MFE (Maximum Favorable Excursion), and hold duration.
          </li>
          <li>
            Strategy weights in the ensemble are updated based on recent performance. Strategies
            that performed well in the current regime receive higher weight.
          </li>
          <li>
            The PPO agent receives reward signals from trade outcomes and updates its policy.
          </li>
          <li>
            Background auto-training runs periodically (configurable) to retrain ML models on
            the latest data including recent trade outcomes.
          </li>
        </ul>
        <p>
          Convergence targets: 65% win rate, 1.5 profit factor, 1.5 Sharpe ratio. The system
          tracks progress toward these targets on the Feedback dashboard.
        </p>
      </>
    ),
  },
  {
    id: 'ml-regime',
    icon: Network,
    title: 'Regime Detection — Bayesian & HMM',
    content: (
      <>
        <p>
          The regime detection system uses two complementary approaches:
        </p>
        <div className="space-y-3">
          <div>
            <p className="font-medium text-foreground-primary">Bayesian Regime Detector</p>
            <p>
              Computes posterior probabilities for each of the 7 market regimes given observed
              features (volatility, trend, volume). Uses conjugate priors that are updated online
              as new data arrives. The prior encodes domain knowledge about typical regime
              characteristics.
            </p>
          </div>
          <div>
            <p className="font-medium text-foreground-primary">Hidden Markov Model (HMM)</p>
            <p>
              Models regime transitions as a Markov chain where regimes are hidden states and
              market observables are emissions. The Viterbi algorithm finds the most likely
              sequence of regimes, while the forward algorithm computes current regime
              probabilities. Transition probabilities capture how likely the market is to switch
              from one regime to another.
            </p>
          </div>
        </div>
        <p>
          Both detectors vote on the current regime. When they agree, confidence is high. When
          they disagree, the system flags increased uncertainty and reduces position sizes. View
          regime probabilities on the <strong>Regime Detect</strong> page.
        </p>
      </>
    ),
  },
]

const platformGuideItems: AccordionItemData[] = [
  {
    id: 'pg-backtest',
    icon: LineChart,
    title: 'Backtesting Guide',
    content: (
      <>
        <p>
          The Backtesting module lets you evaluate any strategy against historical data:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Strategy Selection</strong> — Choose from ML ensemble, individual models,
            technical strategies (RSI mean-reversion, MACD crossover, etc.), or custom rule sets.
          </li>
          <li>
            <strong>Universe</strong> — Enter individual tickers or select from preset universes
            (S&P 500 components, sector ETFs, etc.).
          </li>
          <li>
            <strong>Parameters</strong> — Set initial capital, commission model (per-share, flat
            fee, or percentage), slippage assumptions, and position sizing method.
          </li>
          <li>
            <strong>Output</strong> — Equity curve, trade log, drawdown chart, monthly returns
            heatmap, and comprehensive statistics (Sharpe, Sortino, Calmar, profit factor, max
            drawdown, win rate, average win/loss ratio).
          </li>
        </ul>
        <p>
          Tip: Always use walk-forward validation when evaluating ML strategies. A great in-sample
          result with poor out-of-sample performance indicates overfitting.
        </p>
      </>
    ),
  },
  {
    id: 'pg-montecarlo',
    icon: Dice5,
    title: 'Monte Carlo Simulation Guide',
    content: (
      <>
        <p>
          Monte Carlo simulation stress-tests your strategy by generating thousands of randomized
          trade sequences:
        </p>
        <ol className="list-decimal list-inside space-y-1 ml-2">
          <li>Take the historical trade results from a backtest.</li>
          <li>Randomly reshuffle trade order (bootstrapping) thousands of times.</li>
          <li>Compute equity curves, drawdowns, and terminal wealth for each simulation.</li>
          <li>Build a probability distribution of outcomes.</li>
        </ol>
        <p>
          This answers questions like: "What is the probability that this strategy experiences a
          30% drawdown?" or "What is the 5th percentile outcome (worst realistic case)?"
        </p>
        <p>
          Access Monte Carlo from <strong>Analytics &gt; Monte Carlo</strong>. The visualization
          shows a fan chart of equity curve percentiles (5th, 25th, 50th, 75th, 95th) and a
          histogram of terminal portfolio values.
        </p>
      </>
    ),
  },
  {
    id: 'pg-pairs',
    icon: Repeat,
    title: 'Pairs Trading Guide',
    content: (
      <>
        <p>
          Pairs trading exploits mean-reversion in the price spread between two correlated
          securities:
        </p>
        <ol className="list-decimal list-inside space-y-1 ml-2">
          <li>
            <strong>Pair Selection</strong> — Use the Correlation view to find highly correlated
            pairs. The platform tests for cointegration using the Engle-Granger and Johansen
            methods.
          </li>
          <li>
            <strong>Spread Construction</strong> — The hedge ratio (beta) is estimated via OLS
            regression. The spread = Price_A - beta * Price_B.
          </li>
          <li>
            <strong>Signal Generation</strong> — When the spread's z-score exceeds a threshold
            (default 2.0), enter a mean-reversion trade: go long the underperformer and short the
            outperformer.
          </li>
          <li>
            <strong>Exit</strong> — Close when the spread reverts to the mean (z-score near 0) or
            when a stop loss is hit (z-score exceeds 3.0).
          </li>
        </ol>
        <p>
          The <strong>Portfolio &gt; Pairs Trading</strong> view provides an interactive
          cointegration scanner, spread chart, z-score monitor, and trade execution panel.
        </p>
      </>
    ),
  },
  {
    id: 'pg-correlation',
    icon: GitBranch,
    title: 'Correlation Analysis Guide',
    content: (
      <>
        <p>
          The Correlation view displays a real-time correlation matrix across your watchlist or
          portfolio holdings:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Pearson Correlation</strong> — Linear correlation between daily returns.
            Values range from -1 (perfect inverse) to +1 (perfect positive).
          </li>
          <li>
            <strong>Rolling Correlation</strong> — A time-series chart showing how correlation
            evolves over a configurable lookback window (default 60 days).
          </li>
          <li>
            <strong>Heatmap</strong> — Color-coded matrix for quick visual identification of
            clusters and outliers.
          </li>
          <li>
            <strong>Dendrogram</strong> — Hierarchical clustering visualization showing which
            assets group together.
          </li>
        </ul>
        <p>
          Use correlation analysis to diversify your portfolio, identify pairs trading candidates,
          and monitor concentration risk. High portfolio-wide correlation is a warning sign of
          insufficient diversification.
        </p>
      </>
    ),
  },
  {
    id: 'pg-darkpool',
    icon: Moon,
    title: 'Dark Pool Data Interpretation',
    content: (
      <>
        <p>
          Dark pools are private exchanges where institutional investors trade large blocks
          without revealing their orders to the public market. The platform tracks dark pool
          activity to identify institutional sentiment:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Dark Pool Volume %</strong> — Percentage of total volume executed in dark
            pools. A sudden increase may signal institutional accumulation or distribution.
          </li>
          <li>
            <strong>Short Volume Ratio</strong> — Proportion of dark pool volume that is short
            selling. High ratios may indicate bearish institutional positioning.
          </li>
          <li>
            <strong>Block Trades</strong> — Large transactions (typically 10,000+ shares)
            executed off-exchange. These represent significant institutional interest.
          </li>
          <li>
            <strong>Net Institutional Flow</strong> — The platform estimates net buying or selling
            pressure from dark pool data to gauge institutional sentiment.
          </li>
        </ul>
        <p>
          Access via <strong>Research &gt; Dark Pool</strong>. Data is sourced from FINRA
          aggregated dark pool reports with a short delay.
        </p>
      </>
    ),
  },
  {
    id: 'pg-13f',
    icon: FileSearch,
    title: '13F Filing Analysis',
    content: (
      <>
        <p>
          SEC Form 13F requires institutional investment managers with over $100M in qualifying
          assets to disclose their holdings quarterly:
        </p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>
            <strong>Position Changes</strong> — The platform compares consecutive 13F filings to
            identify new positions, increased positions, reduced positions, and exits.
          </li>
          <li>
            <strong>Whale Tracking</strong> — Track specific institutions (hedge funds, pension
            funds, endowments) and see their portfolio composition and changes.
          </li>
          <li>
            <strong>Consensus Picks</strong> — Aggregate analysis showing which stocks are most
            widely held and which saw the most buying activity.
          </li>
          <li>
            <strong>Sector Shifts</strong> — Track how institutional allocation to sectors changes
            over time to identify macro rotation.
          </li>
        </ul>
        <p>
          Note: 13F filings are reported with a 45-day delay from quarter-end, so the data
          reflects institutional positioning from the prior quarter. Access via{' '}
          <strong>Research &gt; 13F Holdings</strong>.
        </p>
      </>
    ),
  },
]

// -------------------------------------------------------------------
// Tabs
// -------------------------------------------------------------------

const tabs = [
  { id: 'getting-started', label: 'Getting Started', icon: Rocket },
  { id: 'trading-concepts', label: 'Trading Concepts', icon: TrendingUp },
  { id: 'ml-ai', label: 'ML / AI Features', icon: Brain },
  { id: 'platform-guides', label: 'Platform Guides', icon: Search },
]

// -------------------------------------------------------------------
// Main component
// -------------------------------------------------------------------

export function LearningCenter() {
  const [activeTab, setActiveTab] = useState('getting-started')

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-accent-primary/10">
          <BookOpen className="w-5 h-5 text-accent-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground-primary">Learning Center</h1>
          <p className="text-sm text-foreground-muted">
            Educational guides for the QUANT INDUSTRY platform
          </p>
        </div>
      </div>

      <div className="card">
        {/* Tab bar */}
        <div className="flex border-b border-border overflow-x-auto">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px whitespace-nowrap',
                activeTab === id
                  ? 'text-accent-primary border-accent-primary'
                  : 'text-foreground-secondary border-transparent hover:text-foreground-primary'
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="p-6">
          {activeTab === 'getting-started' && (
            <Section
              title="Getting Started"
              description="Everything you need to know to set up and start using the platform."
            >
              <AccordionGroup items={gettingStartedItems} />
            </Section>
          )}

          {activeTab === 'trading-concepts' && (
            <Section
              title="Trading Concepts"
              description="Core trading concepts and how the platform implements them."
            >
              <AccordionGroup items={tradingConceptItems} />
            </Section>
          )}

          {activeTab === 'ml-ai' && (
            <Section
              title="ML / AI Features"
              description="Deep dive into the machine learning and artificial intelligence systems."
            >
              <AccordionGroup items={mlAiItems} />
            </Section>
          )}

          {activeTab === 'platform-guides' && (
            <Section
              title="Platform Guides"
              description="Step-by-step guides for each major feature."
            >
              <AccordionGroup items={platformGuideItems} />
            </Section>
          )}
        </div>
      </div>
    </div>
  )
}
