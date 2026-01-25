"""
QUANT INDUSTRY Learning Center Service
=======================================
Comprehensive documentation system explaining WHY and HOW everything works.

This service provides educational content for understanding:
- Trading concepts and metrics
- ML/AI algorithms used in the platform
- Risk management principles
- Platform architecture and components
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TopicCategory(Enum):
    """Learning topic categories"""
    FUNDAMENTALS = "fundamentals"
    ML_AI = "ml_ai"
    RISK = "risk"
    STRATEGIES = "strategies"
    PLATFORM = "platform"
    PROP_FIRM = "prop_firm"
    DATA = "data"
    EXECUTION = "execution"


@dataclass
class LearningTopic:
    """A learning topic with comprehensive content"""
    id: str
    title: str
    category: TopicCategory
    summary: str
    why_it_matters: str
    how_it_works: str
    key_concepts: List[str]
    formulas: List[Dict[str, str]] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)
    related_topics: List[str] = field(default_factory=list)
    code_location: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value,
            "summary": self.summary,
            "why_it_matters": self.why_it_matters,
            "how_it_works": self.how_it_works,
            "key_concepts": self.key_concepts,
            "formulas": self.formulas,
            "best_practices": self.best_practices,
            "common_mistakes": self.common_mistakes,
            "related_topics": self.related_topics,
            "code_location": self.code_location
        }


class LearningCenterService:
    """Service providing comprehensive learning content"""

    def __init__(self):
        self.topics: Dict[str, LearningTopic] = {}
        self._load_topics()
        logger.info(f"Learning Center initialized with {len(self.topics)} topics")

    def _load_topics(self):
        """Load all learning topics"""

        # ============== FUNDAMENTALS ==============

        self.topics["sharpe_ratio"] = LearningTopic(
            id="sharpe_ratio",
            title="Sharpe Ratio",
            category=TopicCategory.FUNDAMENTALS,
            summary="Risk-adjusted return metric measuring excess return per unit of risk",
            why_it_matters="""
The Sharpe Ratio is the gold standard for comparing strategy performance because it accounts
for BOTH returns AND risk. A strategy returning 20% with 40% volatility (Sharpe=0.5) is
worse than one returning 10% with 5% volatility (Sharpe=2.0). Without risk-adjustment,
you might pick strategies that look great in backtests but blow up in live trading.
            """.strip(),
            how_it_works="""
1. Calculate your strategy's excess return (return minus risk-free rate, ~4-5% currently)
2. Calculate the standard deviation of those returns (volatility)
3. Divide excess return by volatility
4. Annualize by multiplying by sqrt(252) for daily data

The result tells you how much return you get per unit of risk taken. Higher is better.
            """.strip(),
            key_concepts=[
                "Risk-free rate: The return you'd get from Treasury bills (~4-5%)",
                "Volatility: Standard deviation of returns - measures uncertainty",
                "Annualization: Converting to yearly terms for comparison",
                "Risk-adjusted: Accounting for the risk taken to achieve returns"
            ],
            formulas=[
                {"name": "Sharpe Ratio", "formula": "(Return - Risk-Free Rate) / Volatility"},
                {"name": "Annualized Sharpe", "formula": "Daily Sharpe × √252"}
            ],
            best_practices=[
                "Aim for Sharpe > 1.0 minimum, > 2.0 is excellent",
                "Use at least 2 years of data for reliable estimates",
                "Compare strategies using the same time period",
                "Consider Sortino ratio for downside-focused analysis"
            ],
            common_mistakes=[
                "Using too short a time period (inflates Sharpe)",
                "Ignoring transaction costs (reduces actual Sharpe)",
                "Not accounting for survivorship bias in backtests",
                "Comparing strategies from different market regimes"
            ],
            related_topics=["sortino_ratio", "max_drawdown", "profit_factor"],
            code_location="backend/brain/propfirm_brain_v6.py"
        )

        self.topics["max_drawdown"] = LearningTopic(
            id="max_drawdown",
            title="Maximum Drawdown",
            category=TopicCategory.FUNDAMENTALS,
            summary="The largest peak-to-trough decline in portfolio value",
            why_it_matters="""
Max Drawdown tells you the WORST you can expect to lose from a peak. A strategy with
50% max drawdown means at some point you'd watch half your money disappear before
recovery. Most traders can't stomach this psychologically and abandon strategies at
the worst time. Prop firms have strict drawdown limits (typically 4-6%) that will
fail your account if breached.
            """.strip(),
            how_it_works="""
1. Track the highest equity value reached (the "peak")
2. Measure the current decline from that peak (the "drawdown")
3. The largest such decline is the Max Drawdown
4. Recovery time measures how long until a new peak is reached

Example: Peak at $100K, drops to $85K = 15% drawdown. If it later drops from
$110K to $80K = 27% drawdown (the new max).
            """.strip(),
            key_concepts=[
                "Peak: Highest equity value achieved",
                "Trough: Lowest point after a peak",
                "Recovery: Time to reach a new all-time high",
                "Underwater: Period below previous peak"
            ],
            formulas=[
                {"name": "Drawdown", "formula": "(Peak - Current) / Peak × 100%"},
                {"name": "Calmar Ratio", "formula": "CAGR / Max Drawdown"}
            ],
            best_practices=[
                "Keep max drawdown under 20% for most strategies",
                "Prop firms typically allow 4-6% max drawdown",
                "Use position sizing to control drawdown",
                "Monitor drawdown in real-time, not just backtests"
            ],
            common_mistakes=[
                "Ignoring recovery time (deep drawdowns take years to recover)",
                "Backtests often underestimate real drawdowns",
                "Not accounting for psychological impact on trading decisions",
                "Position sizing too aggressively based on backtested drawdowns"
            ],
            related_topics=["sharpe_ratio", "position_sizing", "risk_management"],
            code_location="backend/brain/algo_bot.py:817"
        )

        self.topics["profit_factor"] = LearningTopic(
            id="profit_factor",
            title="Profit Factor",
            category=TopicCategory.FUNDAMENTALS,
            summary="Ratio of gross profits to gross losses",
            why_it_matters="""
Profit Factor shows the relationship between winning and losing trades in dollar terms.
A profit factor of 2.0 means you make $2 for every $1 you lose. Unlike win rate alone,
it accounts for the SIZE of wins vs losses. You can have a 30% win rate but still be
profitable if your winners are 3x larger than losers (PF > 1.0).
            """.strip(),
            how_it_works="""
1. Sum up all profitable trades (gross profit)
2. Sum up all losing trades in absolute value (gross loss)
3. Divide gross profit by gross loss
4. Result > 1.0 means profitable, > 1.5 is good, > 2.0 is excellent
            """.strip(),
            key_concepts=[
                "Gross profit: Sum of all winning trades",
                "Gross loss: Sum of all losing trades (absolute)",
                "Win rate: Percentage of winning trades",
                "Average R-multiple: Average profit per unit of risk"
            ],
            formulas=[
                {"name": "Profit Factor", "formula": "Gross Profit / |Gross Loss|"},
                {"name": "Expectancy", "formula": "(Win% × Avg Win) - (Loss% × Avg Loss)"}
            ],
            best_practices=[
                "Aim for profit factor > 1.5",
                "Combine with win rate for full picture",
                "Use R-multiples for position sizing alignment",
                "Monitor separately by strategy and market regime"
            ],
            common_mistakes=[
                "Ignoring commission costs in calculation",
                "Small sample size (need 100+ trades minimum)",
                "Not accounting for slippage in backtests",
                "Optimizing for profit factor can lead to curve fitting"
            ],
            related_topics=["sharpe_ratio", "expectancy", "win_rate"],
            code_location="backend/brain/propfirm_brain_v6.py"
        )

        # ============== ML/AI ==============

        self.topics["regime_detection"] = LearningTopic(
            id="regime_detection",
            title="Market Regime Detection",
            category=TopicCategory.ML_AI,
            summary="Identifying market states (trending, ranging, volatile) for adaptive strategy selection",
            why_it_matters="""
Markets behave differently in different regimes. A trend-following strategy kills it
in trending markets but bleeds in sideways markets. Mean reversion works in ranging
markets but gets crushed in trends. By detecting the current regime, you can:
- Select appropriate strategies for current conditions
- Adjust position sizing based on expected volatility
- Avoid strategies that underperform in current regime
            """.strip(),
            how_it_works="""
Our regime detection uses multiple indicators:

1. **ADX (Average Directional Index)**: Measures trend strength
   - ADX > 25: Trending market
   - ADX < 20: Ranging/choppy market

2. **ATR (Average True Range)**: Measures volatility
   - Rising ATR: Increasing volatility
   - Falling ATR: Decreasing volatility

3. **HMM (Hidden Markov Model)**: Statistical model that learns regime transitions
   - Identifies hidden states from observable price data
   - Calculates probability of being in each regime

4. **Bollinger Band Width**: Volatility expansion/contraction
   - Narrow bands: Low volatility, expecting breakout
   - Wide bands: High volatility regime

Regimes detected: TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE, CRISIS
            """.strip(),
            key_concepts=[
                "ADX: Trend strength indicator (0-100 scale)",
                "ATR: Average range of price movement",
                "HMM: Statistical model for regime switching",
                "Regime transition: Probability of switching states"
            ],
            formulas=[
                {"name": "ADX", "formula": "100 × EMA(|+DI - -DI| / (+DI + -DI))"},
                {"name": "ATR", "formula": "EMA(max(H-L, |H-Cp|, |L-Cp|))"}
            ],
            best_practices=[
                "Use multiple indicators for regime confirmation",
                "Allow for transition periods between regimes",
                "Don't switch strategies too frequently (transaction costs)",
                "Backtest strategy performance by regime separately"
            ],
            common_mistakes=[
                "Over-optimizing regime thresholds to past data",
                "Ignoring regime transition costs",
                "Not accounting for regime detection lag",
                "Using single indicator for regime determination"
            ],
            related_topics=["trend_following", "mean_reversion", "volatility_strategies"],
            code_location="backend/core/regime_discovery.py"
        )

        self.topics["reinforcement_learning"] = LearningTopic(
            id="reinforcement_learning",
            title="Reinforcement Learning for Trading",
            category=TopicCategory.ML_AI,
            summary="Training adaptive agents that learn optimal trading policies through experience",
            why_it_matters="""
Traditional strategies use fixed rules. RL agents LEARN optimal actions through
trial and error, adapting to changing market conditions. They can discover
non-obvious patterns and optimize for complex objectives like risk-adjusted
returns. Our PropFirm Brain V6 uses RL to:
- Learn position sizing based on market conditions
- Adapt entry/exit timing dynamically
- Optimize for prop firm rules (max drawdown, consistency)
            """.strip(),
            how_it_works="""
1. **Environment**: The market simulation where the agent trades
   - State: Current market features (prices, indicators, position)
   - Actions: Buy, Sell, Hold, position sizes
   - Rewards: P&L, risk-adjusted returns, or custom metrics

2. **Agent**: Neural network that learns the policy
   - Input: Current state features
   - Output: Action probabilities or values

3. **Training**: Learning through experience
   - Agent takes actions, observes rewards
   - Updates policy to maximize expected future rewards
   - Uses algorithms like PPO, A2C, or SAC

4. **Our Implementation**: PPO (Proximal Policy Optimization)
   - Stable training with clipped objective
   - Good sample efficiency
   - Handles continuous action spaces
            """.strip(),
            key_concepts=[
                "State: Current market observation (features)",
                "Action: Trading decision (buy/sell/hold/size)",
                "Reward: Feedback signal (P&L, Sharpe, etc.)",
                "Policy: Strategy the agent learns",
                "PPO: Proximal Policy Optimization algorithm"
            ],
            formulas=[
                {"name": "Q-Value", "formula": "E[Σ γ^t × r_t | s, a]"},
                {"name": "Policy Gradient", "formula": "∇θ log π(a|s) × A(s,a)"}
            ],
            best_practices=[
                "Use realistic transaction costs in simulation",
                "Normalize state features for stable training",
                "Use reward shaping to guide learning",
                "Validate on out-of-sample data extensively"
            ],
            common_mistakes=[
                "Training on too short history (overfitting)",
                "Unrealistic reward functions",
                "Not accounting for market impact",
                "Ignoring regime changes in training data"
            ],
            related_topics=["regime_detection", "neural_networks", "feature_engineering"],
            code_location="backend/brain/propfirm_brain_v6.py:600-760"
        )

        self.topics["ensemble_learning"] = LearningTopic(
            id="ensemble_learning",
            title="Ensemble Strategy Learning",
            category=TopicCategory.ML_AI,
            summary="Combining multiple strategies for more robust predictions",
            why_it_matters="""
No single strategy works in all market conditions. Ensembles combine multiple
strategies, each contributing based on its strengths. Benefits:
- Diversification: Reduces dependence on any single strategy
- Robustness: Less sensitive to individual strategy failures
- Adaptability: Can weight strategies based on recent performance
            """.strip(),
            how_it_works="""
Our Strategy Ensemble combines 6 core strategies:

1. **TrendFollowing**: ADX + Moving Average crossovers
2. **Momentum**: RSI + MACD divergence
3. **MeanReversion**: Bollinger Band mean reversion
4. **Volume**: Volume spike detection
5. **Breakout**: Range expansion signals
6. **ICT_OrderFlow**: Institutional order flow patterns

Combination methods:
- **Weighted Voting**: Each strategy votes, weighted by confidence
- **Meta-Learning**: ML model learns optimal weights
- **Dynamic Weighting**: Adjust weights based on recent performance
            """.strip(),
            key_concepts=[
                "Voting ensemble: Each model gets a vote",
                "Weighted average: Confidence-weighted predictions",
                "Stacking: Meta-model learns from base models",
                "Dynamic weighting: Adjust weights over time"
            ],
            formulas=[
                {"name": "Weighted Signal", "formula": "Σ(w_i × signal_i) / Σ(w_i)"},
                {"name": "Meta Learner", "formula": "f(signal_1, ..., signal_n) → final_signal"}
            ],
            best_practices=[
                "Use diverse strategies (uncorrelated signals)",
                "Validate ensemble performance, not just components",
                "Limit ensemble to 5-10 well-tested strategies",
                "Monitor individual strategy contribution"
            ],
            common_mistakes=[
                "Adding too many correlated strategies",
                "Over-weighting recent top performers",
                "Not rebalancing weights over time",
                "Ignoring transaction costs of multiple signals"
            ],
            related_topics=["regime_detection", "reinforcement_learning", "meta_learning"],
            code_location="backend/brain/propfirm_brain_v6.py:969-1020"
        )

        # ============== RISK MANAGEMENT ==============

        self.topics["position_sizing"] = LearningTopic(
            id="position_sizing",
            title="Position Sizing",
            category=TopicCategory.RISK,
            summary="Determining optimal trade size based on risk parameters",
            why_it_matters="""
Position sizing is arguably MORE important than entry signals. A great strategy
with bad sizing will blow up. A mediocre strategy with good sizing survives.
Position sizing determines:
- How much you risk per trade
- Your max drawdown potential
- How quickly you recover from losses
- Whether you survive inevitable losing streaks
            """.strip(),
            how_it_works="""
We use Kelly Criterion modified for trading:

1. **Fixed Fractional**: Risk X% of capital per trade
   - Common: 1-2% risk per trade
   - Reduces size as account shrinks, increases as it grows

2. **Kelly Criterion**: Optimal growth rate
   - Kelly% = (Win% × Avg Win - Loss% × Avg Loss) / Avg Win
   - Often use half-Kelly for safety

3. **Volatility-Adjusted**: Scale by market volatility
   - Higher volatility = smaller positions
   - Uses ATR or standard deviation

4. **Prop Firm Rules**: TPT $50K account
   - Max 6 contracts
   - $2K trailing drawdown limit
   - Position size must respect daily loss limit
            """.strip(),
            key_concepts=[
                "Risk per trade: Amount you're willing to lose",
                "Kelly Criterion: Mathematically optimal bet size",
                "Volatility scaling: Adjust for market conditions",
                "Max position: Absolute limit regardless of edge"
            ],
            formulas=[
                {"name": "Fixed Fractional", "formula": "Position = (Capital × Risk%) / Stop Distance"},
                {"name": "Kelly", "formula": "f* = (p × b - q) / b where p=win%, b=win/loss ratio, q=loss%"},
                {"name": "Vol-Adjusted", "formula": "Position = Target$ Risk / (ATR × Multiplier)"}
            ],
            best_practices=[
                "Never risk more than 2% per trade",
                "Use half-Kelly or less for safety margin",
                "Scale down position size during drawdowns",
                "Account for correlation between positions"
            ],
            common_mistakes=[
                "Increasing size after wins (gambling fallacy)",
                "Not accounting for overnight gap risk",
                "Ignoring correlation between positions",
                "Using backtested metrics for Kelly (overstated)"
            ],
            related_topics=["max_drawdown", "risk_management", "kelly_criterion"],
            code_location="backend/core/engine.py"
        )

        self.topics["var_cvar"] = LearningTopic(
            id="var_cvar",
            title="Value at Risk (VaR) and CVaR",
            category=TopicCategory.RISK,
            summary="Quantifying potential losses at specific confidence levels",
            why_it_matters="""
VaR answers: "What's the most I can lose on X% of days?"
CVaR (Conditional VaR) answers: "When things go bad, HOW bad?"

These metrics help you:
- Set appropriate position sizes
- Understand tail risk (extreme events)
- Comply with prop firm risk limits
- Prepare psychologically for worst cases
            """.strip(),
            how_it_works="""
1. **Historical VaR**: Sort historical returns, find percentile
   - 95% VaR: 5th percentile of returns
   - 99% VaR: 1st percentile of returns

2. **Parametric VaR**: Assume normal distribution
   - VaR = μ - z × σ
   - z = 1.645 for 95%, 2.326 for 99%

3. **Monte Carlo VaR**: Simulate thousands of paths
   - Generate random returns based on historical distribution
   - Calculate VaR from simulated distribution

4. **CVaR (Expected Shortfall)**: Average loss beyond VaR
   - More conservative than VaR
   - Accounts for tail severity
            """.strip(),
            key_concepts=[
                "Confidence level: Probability threshold (95%, 99%)",
                "Time horizon: Period for risk calculation (daily, weekly)",
                "Tail risk: Extreme events beyond VaR",
                "Expected Shortfall: Average loss in worst cases"
            ],
            formulas=[
                {"name": "Parametric VaR", "formula": "VaR = μ - z_α × σ"},
                {"name": "Historical VaR", "formula": "VaR = Percentile(returns, 1-α)"},
                {"name": "CVaR", "formula": "E[Loss | Loss > VaR]"}
            ],
            best_practices=[
                "Use CVaR for tail risk management",
                "Calculate at multiple confidence levels",
                "Stress test with historical crisis periods",
                "Update VaR estimates regularly"
            ],
            common_mistakes=[
                "Assuming normal distribution (fat tails exist)",
                "Using too short a lookback period",
                "Ignoring correlation changes in stress",
                "Not stress testing for extreme scenarios"
            ],
            related_topics=["max_drawdown", "position_sizing", "monte_carlo"],
            code_location="backend/core/engine.py"
        )

        # ============== PROP FIRM ==============

        self.topics["tpt_rules"] = LearningTopic(
            id="tpt_rules",
            title="Take Profit Trader (TPT) Rules",
            category=TopicCategory.PROP_FIRM,
            summary="Understanding TPT evaluation requirements and how our system complies",
            why_it_matters="""
TPT provides funded trading accounts but has strict rules. Breaking them fails
your evaluation and loses your fee. Our system is designed to automatically
comply with these rules while maximizing profit potential. Understanding the
rules helps you configure the system appropriately.
            """.strip(),
            how_it_works="""
**TPT $50K Account Rules:**

1. **Profit Target**: $3,000 (6% of account)
   - Must reach this to pass evaluation
   - Our system tracks progress toward target

2. **Trailing Drawdown**: $2,000 (4% max)
   - Tracks from highest equity reached
   - Breaching this fails evaluation immediately
   - Our risk engine enforces hard stops

3. **Max Contracts**: 6 contracts
   - Position sizing capped automatically
   - Our system never exceeds this limit

4. **Consistency Rule**: 50%
   - No single day can exceed 50% of total profit
   - Prevents lucky one-day passes
   - Our system distributes risk across days

5. **Minimum Trading Days**: 5
   - Must trade at least 5 days
   - Cannot pass in less than 1 week

6. **Trading Hours**: Close by 5PM ET
   - All positions must be flat by close
   - Our system auto-closes before deadline
            """.strip(),
            key_concepts=[
                "Profit Target: Amount needed to pass",
                "Trailing Drawdown: Dynamic loss limit from peak",
                "Consistency Rule: Prevents one-day luck passes",
                "Max Contracts: Position size limit"
            ],
            formulas=[
                {"name": "Pass Progress", "formula": "Current Profit / $3,000 × 100%"},
                {"name": "Available Risk", "formula": "$2,000 - (Peak Equity - Current Equity)"},
                {"name": "Consistency Check", "formula": "Best Day P&L / Total P&L ≤ 50%"}
            ],
            best_practices=[
                "Aim for consistent $200-400/day rather than big swings",
                "Keep at least 50% of drawdown buffer available",
                "Scale up position size gradually as profit grows",
                "Don't rush - 5-day minimum exists for a reason"
            ],
            common_mistakes=[
                "Going for home runs (breaks consistency rule)",
                "Trading too large early (no drawdown buffer)",
                "Holding overnight (gap risk)",
                "Not tracking trailing drawdown correctly"
            ],
            related_topics=["position_sizing", "risk_management", "max_drawdown"],
            code_location="backend/strategies/tpt_aggressive.py"
        )

        # ============== ICT STRATEGIES ==============

        self.topics["ict_concepts"] = LearningTopic(
            id="ict_concepts",
            title="ICT / Smart Money Concepts",
            category=TopicCategory.STRATEGIES,
            summary="Understanding institutional order flow and market structure",
            why_it_matters="""
ICT (Inner Circle Trader) concepts model how institutional traders (the "smart money")
actually move markets. By understanding their patterns, you can:
- Trade in the same direction as institutions
- Avoid being the liquidity they hunt
- Find high-probability entry zones
- Understand why support/resistance works
            """.strip(),
            how_it_works="""
**Key ICT Concepts in Our System:**

1. **Fair Value Gaps (FVG)**
   - Price imbalances where candle bodies don't overlap
   - Price tends to return to fill these gaps
   - Our system detects and tracks FVGs automatically

2. **Order Blocks**
   - Consolidation zones before strong moves
   - Represent institutional accumulation/distribution
   - Act as support/resistance when retested

3. **Liquidity Sweeps**
   - Price moves above/below recent highs/lows
   - Takes out stop losses (hunting liquidity)
   - Often reverses after sweep completion

4. **Market Structure Shift (MSS)**
   - Break of recent high/low structure
   - Signals potential trend change
   - Used for entry confirmation

5. **Optimal Trade Entry (OTE)**
   - 61.8-79% Fibonacci retracement zone
   - High-probability entry after MSS
   - Combines with FVG for precision
            """.strip(),
            key_concepts=[
                "FVG: Fair Value Gap - price imbalance zone",
                "Order Block: Institutional accumulation zone",
                "Liquidity: Stop losses clustered at obvious levels",
                "MSS: Market Structure Shift - trend change signal"
            ],
            formulas=[
                {"name": "FVG Detection", "formula": "Gap exists if Low[0] > High[2] (bullish) or High[0] < Low[2] (bearish)"},
                {"name": "OTE Zone", "formula": "Entry between 61.8% and 79% retracement of recent swing"}
            ],
            best_practices=[
                "Wait for liquidity sweep before entry",
                "Combine multiple ICT concepts for confirmation",
                "Trade in direction of higher timeframe bias",
                "Use order blocks as stop loss levels"
            ],
            common_mistakes=[
                "Trading every FVG (need context)",
                "Ignoring higher timeframe structure",
                "Entering before liquidity sweep completes",
                "Using ICT in choppy/ranging markets"
            ],
            related_topics=["regime_detection", "order_flow", "market_structure"],
            code_location="backend/strategies/ict_strategies.py"
        )

        # ============== PLATFORM ARCHITECTURE ==============

        self.topics["platform_architecture"] = LearningTopic(
            id="platform_architecture",
            title="QUANT INDUSTRY Platform Architecture",
            category=TopicCategory.PLATFORM,
            summary="Understanding how all system components work together",
            why_it_matters="""
Understanding the architecture helps you:
- Debug issues when they occur
- Configure components appropriately
- Extend the system with new features
- Optimize performance
            """.strip(),
            how_it_works="""
**System Components:**

1. **Data Layer** (`backend/services/data_service.py`)
   - Multi-source: Alpaca, Tradier, Yahoo Finance
   - Real-time and historical data
   - Caching and rate limiting

2. **Brain Layer** (`backend/brain/`)
   - PropFirm Brain V6: Main ML trading engine
   - Strategy Ensemble: 6 rule-based strategies
   - RL Engine: Reinforcement learning agent
   - Regime Detector: Market state identification

3. **Execution Layer** (`backend/execution/`)
   - Broker Adapter: Abstract broker interface
   - Paper Broker: Simulated execution
   - Alpaca Broker: Live/paper trading
   - Trade Journal: Recording all trades

4. **Risk Layer** (`backend/core/`)
   - Risk Engine: Position limits, drawdown tracking
   - Market Memory: Episode-based pattern recall
   - Regime Discovery: Multi-factor regime detection

5. **API Layer** (`backend/main.py`)
   - FastAPI server on port 8000
   - WebSocket for real-time updates
   - REST endpoints for all features

6. **Frontend** (`frontend/src/`)
   - React 18 + TypeScript
   - Real-time charts and dashboards
   - Electron wrapper for desktop
            """.strip(),
            key_concepts=[
                "Microservices: Each component has single responsibility",
                "Event-driven: Components communicate via events",
                "Stateless API: No server-side session state",
                "Real-time: WebSocket for live updates"
            ],
            formulas=[],
            best_practices=[
                "Check logs in backend/logs/ for debugging",
                "Use health endpoint to verify system status",
                "Monitor memory usage for long-running processes",
                "Restart backend after config changes"
            ],
            common_mistakes=[
                "Not checking if backend is running",
                "Ignoring rate limits on data providers",
                "Not waiting for backend startup completion",
                "Modifying code without testing"
            ],
            related_topics=["data_sources", "api_endpoints", "deployment"],
            code_location="backend/main.py"
        )

        self.topics["auto_training"] = LearningTopic(
            id="auto_training",
            title="ML Auto-Training System",
            category=TopicCategory.ML_AI,
            summary="How the system continuously learns and improves",
            why_it_matters="""
Markets evolve. A model trained on 2023 data may not work in 2024.
Auto-training ensures the system:
- Adapts to changing market conditions
- Learns from recent trades (feedback loop)
- Maintains performance over time
- Improves strategy weights based on results
            """.strip(),
            how_it_works="""
**Training Pipeline:**

1. **Data Collection**
   - Collects market data every minute
   - Stores features and outcomes in database
   - Minimum 10 trades before training

2. **Feature Engineering**
   - Calculates 50+ technical indicators
   - Normalizes features for ML models
   - Creates regime-specific feature sets

3. **Model Training**
   - Supervised: Direction prediction (LSTM/Transformer)
   - RL: Policy optimization (PPO)
   - Ensemble: Weight optimization

4. **Training Schedule**
   - Auto-trains every 5 minutes (configurable)
   - Requires minimum trade count
   - Saves checkpoints for recovery

5. **Feedback Loop**
   - Records trade outcomes
   - Updates strategy weights based on performance
   - Adjusts risk parameters adaptively

**Configuration:**
- `auto_train_interval`: 300 seconds (5 min)
- `min_trades_for_training`: 10 trades
- `learning_rate`: 0.001
            """.strip(),
            key_concepts=[
                "Online learning: Updates with each new data point",
                "Batch training: Periodic retraining on accumulated data",
                "Feedback loop: Learning from trade outcomes",
                "Checkpointing: Saving model state for recovery"
            ],
            formulas=[
                {"name": "EMA Weight Update", "formula": "w_new = α × w_recent + (1-α) × w_old"},
                {"name": "Learning Rate Decay", "formula": "lr = lr_0 / (1 + decay × step)"}
            ],
            best_practices=[
                "Monitor training loss for convergence",
                "Keep training data diverse (multiple regimes)",
                "Validate on recent out-of-sample data",
                "Don't retrain too frequently (stability)"
            ],
            common_mistakes=[
                "Training on too few trades (overfitting)",
                "Not validating after training",
                "Ignoring regime changes in training data",
                "Too high learning rate (instability)"
            ],
            related_topics=["reinforcement_learning", "ensemble_learning", "regime_detection"],
            code_location="backend/brain/propfirm_brain_v6.py:1617-1650"
        )

    def get_topic(self, topic_id: str) -> Optional[LearningTopic]:
        """Get a specific topic by ID"""
        return self.topics.get(topic_id)

    def get_all_topics(self) -> List[LearningTopic]:
        """Get all topics"""
        return list(self.topics.values())

    def get_topics_by_category(self, category: TopicCategory) -> List[LearningTopic]:
        """Get topics filtered by category"""
        return [t for t in self.topics.values() if t.category == category]

    def search_topics(self, query: str) -> List[LearningTopic]:
        """Search topics by keyword"""
        query = query.lower()
        results = []
        for topic in self.topics.values():
            if (query in topic.title.lower() or
                query in topic.summary.lower() or
                query in topic.how_it_works.lower() or
                any(query in kc.lower() for kc in topic.key_concepts)):
                results.append(topic)
        return results

    def get_categories(self) -> List[Dict[str, str]]:
        """Get all categories with counts"""
        counts = {}
        for topic in self.topics.values():
            cat = topic.category.value
            counts[cat] = counts.get(cat, 0) + 1

        return [
            {"id": cat.value, "name": cat.value.replace("_", " ").title(), "count": counts.get(cat.value, 0)}
            for cat in TopicCategory
        ]


# Singleton instance
_learning_center: Optional[LearningCenterService] = None

def get_learning_center() -> LearningCenterService:
    """Get or create the learning center service"""
    global _learning_center
    if _learning_center is None:
        _learning_center = LearningCenterService()
    return _learning_center
