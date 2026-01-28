"""
QUANT_INDUSTRY_V1 Alpha Hypothesis Framework

Scientific framework for generating, testing, and validating trading hypotheses.

Features:
- Hypothesis generation from market anomalies
- Statistical significance testing
- Multiple testing correction
- Hypothesis lifecycle management
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
from datetime import datetime, timezone
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# HYPOTHESIS TYPES
# =============================================================================

class HypothesisType(Enum):
    """Types of trading hypotheses."""
    MOMENTUM = "momentum"           # Trend continuation
    MEAN_REVERSION = "mean_reversion"  # Price reversal
    BREAKOUT = "breakout"           # Volatility expansion
    PATTERN = "pattern"             # Chart patterns
    FACTOR = "factor"               # Factor exposure
    CROSS_ASSET = "cross_asset"     # Cross-asset relationships
    SEASONAL = "seasonal"           # Calendar effects
    MICROSTRUCTURE = "microstructure"  # Order flow patterns
    SENTIMENT = "sentiment"         # Sentiment-driven
    FUNDAMENTAL = "fundamental"     # Value-based
    ARBITRAGE = "arbitrage"         # Statistical arbitrage


class HypothesisStatus(Enum):
    """Lifecycle status of a hypothesis."""
    PROPOSED = "proposed"           # Newly generated
    TESTING = "testing"             # Being backtested
    VALIDATED = "validated"         # Passed statistical tests
    REJECTED = "rejected"           # Failed tests
    DEPLOYED = "deployed"           # In production
    DEPRECATED = "deprecated"       # No longer valid
    DEGRADED = "degraded"           # Performance decayed


@dataclass
class HypothesisCondition:
    """A single condition in a hypothesis."""
    feature: str                    # Feature name
    operator: str                   # >, <, ==, >=, <=, between
    value: Any                      # Threshold value
    value2: Optional[Any] = None    # Second value for 'between'
    lookback: int = 1               # Lookback period

    def evaluate(self, data: np.ndarray) -> np.ndarray:
        """Evaluate condition on data."""
        if self.operator == ">":
            return data > self.value
        elif self.operator == "<":
            return data < self.value
        elif self.operator == ">=":
            return data >= self.value
        elif self.operator == "<=":
            return data <= self.value
        elif self.operator == "==":
            return data == self.value
        elif self.operator == "between":
            return (data >= self.value) & (data <= self.value2)
        elif self.operator == "crosses_above":
            return (np.roll(data, 1) <= self.value) & (data > self.value)
        elif self.operator == "crosses_below":
            return (np.roll(data, 1) >= self.value) & (data < self.value)
        return np.zeros(len(data), dtype=bool)

    def to_dict(self) -> Dict:
        return {
            'feature': self.feature,
            'operator': self.operator,
            'value': self.value,
            'value2': self.value2,
            'lookback': self.lookback,
        }


@dataclass
class AlphaHypothesis:
    """
    A trading hypothesis representing a potential alpha source.
    """
    hypothesis_id: str
    name: str
    description: str
    hypothesis_type: HypothesisType

    # Entry conditions
    entry_conditions: List[HypothesisCondition]

    # Exit conditions
    exit_conditions: List[HypothesisCondition]

    # Direction: 1 for long, -1 for short, 0 for neutral
    direction: int = 1

    # Position sizing parameters
    position_size_pct: float = 0.02  # 2% of capital
    max_positions: int = 5

    # Risk management
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_holding_days: int = 5

    # Status
    status: HypothesisStatus = HypothesisStatus.PROPOSED

    # Performance metrics (from backtesting)
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    total_return: float = 0.0
    num_trades: int = 0
    avg_trade_return: float = 0.0
    t_statistic: float = 0.0
    p_value: float = 1.0

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_tested: Optional[datetime] = None
    generation: int = 0  # For evolutionary algorithms
    parent_ids: List[str] = field(default_factory=list)

    # Applicable assets/markets
    asset_universe: List[str] = field(default_factory=lambda: ["SPY"])

    def evaluate_entry(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """Evaluate if entry conditions are met."""
        if not self.entry_conditions:
            return np.zeros(len(next(iter(features.values()))), dtype=bool)

        results = []
        for condition in self.entry_conditions:
            if condition.feature in features:
                result = condition.evaluate(features[condition.feature])
                results.append(result)

        if not results:
            return np.zeros(len(next(iter(features.values()))), dtype=bool)

        # All conditions must be true
        combined = results[0]
        for result in results[1:]:
            combined = combined & result

        return combined

    def evaluate_exit(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """Evaluate if exit conditions are met."""
        if not self.exit_conditions:
            return np.zeros(len(next(iter(features.values()))), dtype=bool)

        results = []
        for condition in self.exit_conditions:
            if condition.feature in features:
                result = condition.evaluate(features[condition.feature])
                results.append(result)

        if not results:
            return np.zeros(len(next(iter(features.values()))), dtype=bool)

        # Any exit condition triggers exit
        combined = results[0]
        for result in results[1:]:
            combined = combined | result

        return combined

    def get_hash(self) -> str:
        """Get unique hash for this hypothesis."""
        content = {
            'type': self.hypothesis_type.value,
            'entry': [c.to_dict() for c in self.entry_conditions],
            'exit': [c.to_dict() for c in self.exit_conditions],
            'direction': self.direction,
        }
        return hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()[:12]

    def is_valid(self) -> bool:
        """Check if hypothesis passes minimum quality thresholds."""
        return (
            self.p_value < 0.05 and
            self.sharpe_ratio > 0.5 and
            self.win_rate > 0.4 and
            self.num_trades >= 30 and
            self.max_drawdown > -0.3
        )

    def to_dict(self) -> Dict:
        """Serialize hypothesis to dictionary."""
        return {
            'hypothesis_id': self.hypothesis_id,
            'name': self.name,
            'description': self.description,
            'type': self.hypothesis_type.value,
            'entry_conditions': [c.to_dict() for c in self.entry_conditions],
            'exit_conditions': [c.to_dict() for c in self.exit_conditions],
            'direction': self.direction,
            'position_size_pct': self.position_size_pct,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'status': self.status.value,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown,
            'total_return': self.total_return,
            'num_trades': self.num_trades,
            't_statistic': self.t_statistic,
            'p_value': self.p_value,
            'generation': self.generation,
            'parent_ids': self.parent_ids,
        }


# =============================================================================
# HYPOTHESIS GENERATOR
# =============================================================================

class HypothesisGenerator:
    """
    Generates trading hypotheses from market data patterns.
    """

    # Common features for hypothesis generation
    FEATURES = [
        # Price-based
        'returns', 'log_returns', 'close_pct_rank',
        # Moving averages
        'sma_5', 'sma_10', 'sma_20', 'sma_50', 'sma_200',
        'ema_12', 'ema_26',
        # Momentum
        'rsi_14', 'rsi_5', 'macd', 'macd_signal', 'macd_hist',
        'momentum_10', 'momentum_20', 'roc_10',
        # Volatility
        'atr_14', 'bb_upper', 'bb_lower', 'bb_width', 'bb_pct',
        'realized_vol_20', 'vol_ratio',
        # Volume
        'volume_sma_20', 'volume_ratio', 'obv', 'vwap_diff',
        # Trend
        'adx', 'plus_di', 'minus_di', 'trend_strength',
        # Mean reversion
        'zscore_20', 'zscore_50', 'hurst_exponent',
        # Microstructure
        'spread_pct', 'order_imbalance', 'trade_intensity',
    ]

    OPERATORS = ['>', '<', '>=', '<=', 'crosses_above', 'crosses_below', 'between']

    def __init__(self, seed: int = None):
        self.rng = np.random.default_rng(seed)
        self._hypothesis_counter = 0

    def generate_random(
        self,
        hypothesis_type: HypothesisType = None,
        num_entry_conditions: int = None,
        num_exit_conditions: int = None,
    ) -> AlphaHypothesis:
        """Generate a random hypothesis."""
        self._hypothesis_counter += 1

        if hypothesis_type is None:
            hypothesis_type = self.rng.choice(list(HypothesisType))

        if num_entry_conditions is None:
            num_entry_conditions = self.rng.integers(1, 5)

        if num_exit_conditions is None:
            num_exit_conditions = self.rng.integers(1, 3)

        # Generate entry conditions
        entry_conditions = []
        used_features = set()
        for _ in range(num_entry_conditions):
            condition = self._random_condition(used_features)
            if condition:
                entry_conditions.append(condition)
                used_features.add(condition.feature)

        # Generate exit conditions
        exit_conditions = []
        for _ in range(num_exit_conditions):
            condition = self._random_condition(set())
            if condition:
                exit_conditions.append(condition)

        # Direction based on type
        if hypothesis_type == HypothesisType.MOMENTUM:
            direction = 1  # Long momentum
        elif hypothesis_type == HypothesisType.MEAN_REVERSION:
            direction = self.rng.choice([-1, 1])  # Can go either way
        else:
            direction = self.rng.choice([-1, 1])

        hypothesis_id = f"H_{self._hypothesis_counter}_{self.rng.integers(10000, 99999)}"

        return AlphaHypothesis(
            hypothesis_id=hypothesis_id,
            name=f"Auto_{hypothesis_type.value}_{self._hypothesis_counter}",
            description=f"Auto-generated {hypothesis_type.value} hypothesis",
            hypothesis_type=hypothesis_type,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            direction=direction,
            stop_loss_pct=self.rng.uniform(0.01, 0.05),
            take_profit_pct=self.rng.uniform(0.02, 0.10),
            max_holding_days=self.rng.integers(1, 20),
        )

    def _random_condition(self, exclude_features: set) -> Optional[HypothesisCondition]:
        """Generate a random condition."""
        available = [f for f in self.FEATURES if f not in exclude_features]
        if not available:
            return None

        feature = self.rng.choice(available)
        operator = self.rng.choice(self.OPERATORS)

        # Generate appropriate values based on feature type
        if 'rsi' in feature:
            if operator in ['>', '>=']:
                value = self.rng.uniform(50, 80)
            elif operator in ['<', '<=']:
                value = self.rng.uniform(20, 50)
            elif operator == 'between':
                value = self.rng.uniform(30, 50)
                value2 = self.rng.uniform(50, 70)
            else:
                value = self.rng.uniform(30, 70)
        elif 'zscore' in feature:
            if operator in ['>', '>=']:
                value = self.rng.uniform(0, 2)
            elif operator in ['<', '<=']:
                value = self.rng.uniform(-2, 0)
            elif operator == 'between':
                value = -self.rng.uniform(0.5, 2)
                value2 = self.rng.uniform(0.5, 2)
            else:
                value = self.rng.uniform(-2, 2)
        elif 'bb_pct' in feature:
            value = self.rng.uniform(0, 1)
        elif 'ratio' in feature:
            value = self.rng.uniform(0.5, 2.0)
        elif 'returns' in feature:
            value = self.rng.uniform(-0.05, 0.05)
        else:
            value = self.rng.uniform(-1, 1)

        value2 = value + abs(self.rng.normal(0, 0.5)) if operator == 'between' else None

        return HypothesisCondition(
            feature=feature,
            operator=operator,
            value=value,
            value2=value2,
            lookback=self.rng.integers(1, 5),
        )

    def generate_momentum(self) -> AlphaHypothesis:
        """Generate a momentum-based hypothesis."""
        self._hypothesis_counter += 1

        lookback = self.rng.integers(5, 20)
        threshold = self.rng.uniform(0.01, 0.05)

        entry_conditions = [
            HypothesisCondition('momentum_10', '>', threshold),
            HypothesisCondition('rsi_14', 'between', 40, 70),
            HypothesisCondition('adx', '>', 20),
        ]

        exit_conditions = [
            HypothesisCondition('momentum_10', '<', 0),
            HypothesisCondition('rsi_14', '>', 75),
        ]

        return AlphaHypothesis(
            hypothesis_id=f"MOM_{self._hypothesis_counter}",
            name=f"Momentum_{lookback}d",
            description=f"Momentum strategy with {lookback}-day lookback",
            hypothesis_type=HypothesisType.MOMENTUM,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            direction=1,
        )

    def generate_mean_reversion(self) -> AlphaHypothesis:
        """Generate a mean reversion hypothesis."""
        self._hypothesis_counter += 1

        zscore_threshold = self.rng.uniform(1.5, 2.5)

        entry_conditions = [
            HypothesisCondition('zscore_20', '<', -zscore_threshold),
            HypothesisCondition('rsi_14', '<', 30),
        ]

        exit_conditions = [
            HypothesisCondition('zscore_20', '>', 0),
            HypothesisCondition('rsi_14', '>', 50),
        ]

        return AlphaHypothesis(
            hypothesis_id=f"MR_{self._hypothesis_counter}",
            name=f"MeanRev_Z{zscore_threshold:.1f}",
            description=f"Mean reversion at z-score {zscore_threshold:.1f}",
            hypothesis_type=HypothesisType.MEAN_REVERSION,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            direction=1,  # Long when oversold
        )

    def generate_breakout(self) -> AlphaHypothesis:
        """Generate a breakout hypothesis."""
        self._hypothesis_counter += 1

        entry_conditions = [
            HypothesisCondition('bb_pct', '>', 1.0),
            HypothesisCondition('volume_ratio', '>', 1.5),
            HypothesisCondition('adx', '>', 25),
        ]

        exit_conditions = [
            HypothesisCondition('bb_pct', '<', 0.8),
            HypothesisCondition('momentum_10', '<', 0),
        ]

        return AlphaHypothesis(
            hypothesis_id=f"BO_{self._hypothesis_counter}",
            name="Breakout_BBVolume",
            description="Bollinger Band breakout with volume confirmation",
            hypothesis_type=HypothesisType.BREAKOUT,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            direction=1,
        )


# =============================================================================
# STATISTICAL TESTING
# =============================================================================

class HypothesisTester:
    """
    Statistical testing framework for trading hypotheses.
    """

    def __init__(
        self,
        significance_level: float = 0.05,
        min_trades: int = 30,
        bootstrap_samples: int = 1000,
    ):
        self.significance_level = significance_level
        self.min_trades = min_trades
        self.bootstrap_samples = bootstrap_samples

    def t_test(
        self,
        returns: np.ndarray,
        null_mean: float = 0.0,
    ) -> Tuple[float, float]:
        """
        Perform one-sample t-test on returns.

        Returns: (t_statistic, p_value)
        """
        n = len(returns)
        if n < 2:
            return 0.0, 1.0

        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        if std == 0:
            return 0.0, 1.0

        t_stat = (mean - null_mean) / (std / np.sqrt(n))

        # Approximate p-value using normal distribution
        p_value = 2 * (1 - self._normal_cdf(abs(t_stat)))

        return t_stat, p_value

    def _normal_cdf(self, x: float) -> float:
        """Approximate normal CDF."""
        return 0.5 * (1 + np.tanh(0.797884560802865 * x * (1 + 0.0356774 * x * x)))

    def bootstrap_sharpe(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
    ) -> Tuple[float, float, float]:
        """
        Bootstrap confidence interval for Sharpe ratio.

        Returns: (sharpe, lower_bound, upper_bound)
        """
        n = len(returns)
        if n < 10:
            return 0.0, 0.0, 0.0

        # Calculate base Sharpe
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        base_sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret > 0 else 0

        # Bootstrap
        sharpes = []
        for _ in range(self.bootstrap_samples):
            sample_idx = np.random.randint(0, n, n)
            sample = returns[sample_idx]
            sample_mean = np.mean(sample)
            sample_std = np.std(sample)
            if sample_std > 0:
                sharpes.append(sample_mean / sample_std * np.sqrt(252))

        if not sharpes:
            return base_sharpe, base_sharpe, base_sharpe

        sharpes = np.array(sharpes)
        alpha = 1 - confidence
        lower = np.percentile(sharpes, alpha / 2 * 100)
        upper = np.percentile(sharpes, (1 - alpha / 2) * 100)

        return base_sharpe, lower, upper

    def multiple_testing_correction(
        self,
        p_values: np.ndarray,
        method: str = "benjamini_hochberg",
    ) -> np.ndarray:
        """
        Apply multiple testing correction.

        Methods:
        - bonferroni: Bonferroni correction
        - benjamini_hochberg: FDR control
        """
        n = len(p_values)
        if n == 0:
            return np.array([])

        if method == "bonferroni":
            return np.minimum(p_values * n, 1.0)

        elif method == "benjamini_hochberg":
            # Sort p-values
            sorted_idx = np.argsort(p_values)
            sorted_p = p_values[sorted_idx]

            # Apply BH correction
            adjusted = np.zeros(n)
            cummin = sorted_p[n - 1]
            adjusted[sorted_idx[n - 1]] = cummin

            for i in range(n - 2, -1, -1):
                adjusted_p = sorted_p[i] * n / (i + 1)
                cummin = min(cummin, adjusted_p)
                adjusted[sorted_idx[i]] = cummin

            return np.minimum(adjusted, 1.0)

        return p_values

    def walk_forward_test(
        self,
        hypothesis: AlphaHypothesis,
        features: Dict[str, np.ndarray],
        returns: np.ndarray,
        n_splits: int = 5,
        train_ratio: float = 0.7,
    ) -> Dict[str, float]:
        """
        Walk-forward analysis for robust validation.
        """
        n = len(returns)
        split_size = n // n_splits

        out_of_sample_returns = []

        for i in range(n_splits):
            split_start = i * split_size
            split_end = min((i + 1) * split_size, n)

            train_end = split_start + int((split_end - split_start) * train_ratio)

            # Test on out-of-sample portion
            test_features = {k: v[train_end:split_end] for k, v in features.items()}
            test_returns = returns[train_end:split_end]

            if len(test_returns) == 0:
                continue

            # Evaluate hypothesis
            signals = hypothesis.evaluate_entry(test_features)
            trade_returns = test_returns[signals[:-1]]  # Align signals with returns

            out_of_sample_returns.extend(trade_returns)

        if len(out_of_sample_returns) < self.min_trades:
            return {'valid': False, 'reason': 'insufficient_trades'}

        oos_returns = np.array(out_of_sample_returns)
        t_stat, p_value = self.t_test(oos_returns)
        sharpe, sharpe_lower, sharpe_upper = self.bootstrap_sharpe(oos_returns)

        return {
            'valid': p_value < self.significance_level and sharpe_lower > 0,
            't_statistic': t_stat,
            'p_value': p_value,
            'sharpe_ratio': sharpe,
            'sharpe_lower': sharpe_lower,
            'sharpe_upper': sharpe_upper,
            'num_trades': len(oos_returns),
            'mean_return': np.mean(oos_returns),
            'win_rate': np.mean(oos_returns > 0),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'HypothesisType',
    'HypothesisStatus',
    'HypothesisCondition',
    'AlphaHypothesis',
    'HypothesisGenerator',
    'HypothesisTester',
]
