"""
QUANT_INDUSTRY_V1 Feedback Loop System

Closed-loop ML brain that learns from trade outcomes:
- Captures trade results and feeds back to models
- Online learning with validation gates
- Convergence targets (win rate, risk-reward)
- Persistent metric storage and experiment tracking
- Adaptive learning rate based on performance

This creates a true learn-log-repeat cycle for continuous improvement.
"""

import logging
import time
import json
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Tuple, Callable
from enum import Enum
from collections import deque
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# DATA TYPES
# =============================================================================

class TradeOutcome(Enum):
    """Outcome classification for trades."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    STOPPED_OUT = "stopped_out"
    TARGET_HIT = "target_hit"
    TIME_EXIT = "time_exit"


class LearningPhase(Enum):
    """Current phase of the learning system."""
    EXPLORATION = "exploration"     # High learning rate, accepting more variance
    EXPLOITATION = "exploitation"   # Lower learning rate, refining
    VALIDATION = "validation"       # Testing new learned patterns
    CONVERGED = "converged"         # Stable performance achieved


@dataclass
class TradeResult:
    """
    Result of a completed trade for feedback.

    This is the primary input to the feedback loop.
    """
    trade_id: str
    symbol: str
    direction: str              # 'LONG' or 'SHORT'
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    quantity: float
    pnl: float
    pnl_pct: float
    outcome: TradeOutcome
    strategy: str
    signal_confidence: float    # Original model confidence
    regime_at_entry: str
    features_at_entry: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConvergenceTargets:
    """
    Performance targets for the feedback loop to achieve.

    The system will optimize towards these goals.
    """
    target_win_rate: float = 0.55           # 55% win rate
    target_profit_factor: float = 1.5       # 1.5:1 profit factor
    target_risk_reward: float = 2.0         # 2:1 average R:R
    target_sharpe: float = 1.5              # Sharpe ratio
    min_trades_for_confidence: int = 30     # Minimum trades before trusting metrics
    convergence_threshold: float = 0.05     # Within 5% of target = converged


@dataclass
class PerformanceMetrics:
    """Current performance metrics of the system."""
    win_rate: float = 0.0
    loss_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_risk_reward: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['last_updated'] = self.last_updated.isoformat()
        return d


@dataclass
class LearningState:
    """Current state of the learning system."""
    phase: LearningPhase = LearningPhase.EXPLORATION
    learning_rate: float = 0.01
    momentum: float = 0.9
    exploration_rate: float = 0.2
    confidence_threshold: float = 0.6
    trades_since_last_update: int = 0
    updates_count: int = 0
    last_model_update: Optional[datetime] = None
    convergence_progress: Dict[str, float] = field(default_factory=dict)


@dataclass
class FeedbackEvent:
    """Event logged in the feedback loop."""
    timestamp: datetime
    event_type: str
    data: Dict[str, Any]
    metrics_snapshot: Optional[PerformanceMetrics] = None


# =============================================================================
# METRICS DATABASE
# =============================================================================

class MetricsDatabase:
    """
    SQLite-based persistent storage for feedback loop metrics.

    Stores:
    - Trade results
    - Performance metrics over time
    - Learning state snapshots
    - Model update history
    """

    def __init__(self, db_path: str = "brain_metrics.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trade_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    symbol TEXT,
                    direction TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    entry_time TEXT,
                    exit_time TEXT,
                    quantity REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    outcome TEXT,
                    strategy TEXT,
                    signal_confidence REAL,
                    regime_at_entry TEXT,
                    features_json TEXT,
                    metadata_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS performance_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    win_rate REAL,
                    profit_factor REAL,
                    sharpe_ratio REAL,
                    max_drawdown REAL,
                    total_trades INTEGER,
                    total_pnl REAL,
                    metrics_json TEXT
                );

                CREATE TABLE IF NOT EXISTS learning_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    event_type TEXT,
                    phase TEXT,
                    learning_rate REAL,
                    data_json TEXT
                );

                CREATE TABLE IF NOT EXISTS model_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    model_name TEXT,
                    update_type TEXT,
                    metrics_before_json TEXT,
                    metrics_after_json TEXT,
                    parameters_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_trade_symbol ON trade_results(symbol);
                CREATE INDEX IF NOT EXISTS idx_trade_strategy ON trade_results(strategy);
                CREATE INDEX IF NOT EXISTS idx_trade_outcome ON trade_results(outcome);
                CREATE INDEX IF NOT EXISTS idx_perf_timestamp ON performance_snapshots(timestamp);
            """)

    def save_trade_result(self, result: TradeResult) -> None:
        """Save a trade result to the database."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO trade_results
                    (trade_id, symbol, direction, entry_price, exit_price,
                     entry_time, exit_time, quantity, pnl, pnl_pct, outcome,
                     strategy, signal_confidence, regime_at_entry,
                     features_json, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.trade_id, result.symbol, result.direction,
                    result.entry_price, result.exit_price,
                    result.entry_time.isoformat(), result.exit_time.isoformat(),
                    result.quantity, result.pnl, result.pnl_pct,
                    result.outcome.value, result.strategy, result.signal_confidence,
                    result.regime_at_entry,
                    json.dumps(result.features_at_entry),
                    json.dumps(result.metadata)
                ))

    def save_performance_snapshot(self, metrics: PerformanceMetrics) -> None:
        """Save a performance snapshot."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO performance_snapshots
                    (timestamp, win_rate, profit_factor, sharpe_ratio,
                     max_drawdown, total_trades, total_pnl, metrics_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now(timezone.utc).isoformat(),
                    metrics.win_rate, metrics.profit_factor, metrics.sharpe_ratio,
                    metrics.max_drawdown, metrics.total_trades, metrics.total_pnl,
                    json.dumps(metrics.to_dict())
                ))

    def save_learning_event(self, event: FeedbackEvent, state: LearningState) -> None:
        """Save a learning event."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO learning_events
                    (timestamp, event_type, phase, learning_rate, data_json)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    event.timestamp.isoformat(),
                    event.event_type,
                    state.phase.value,
                    state.learning_rate,
                    json.dumps(event.data)
                ))

    def get_recent_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trade results."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM trade_results
                ORDER BY exit_time DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_performance_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get performance history."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM performance_snapshots
                WHERE timestamp > ? ORDER BY timestamp
            """, (cutoff,))
            return [dict(row) for row in cursor.fetchall()]

    def get_trades_by_strategy(self, strategy: str) -> List[Dict[str, Any]]:
        """Get trades for a specific strategy."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM trade_results
                WHERE strategy = ? ORDER BY exit_time DESC
            """, (strategy,))
            return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# ONLINE LEARNER
# =============================================================================

class OnlineLearner:
    """
    Incremental learning component with validation gates.

    Features:
    - ADAM-style momentum updates
    - Validation gates to prevent bad updates
    - Rollback capability
    - Confidence-weighted learning
    """

    def __init__(
        self,
        learning_rate: float = 0.01,
        momentum: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
        validation_threshold: float = 0.6,
    ):
        self.learning_rate = learning_rate
        self.momentum = momentum
        self.beta2 = beta2
        self.epsilon = epsilon
        self.validation_threshold = validation_threshold

        # ADAM state
        self._m: Dict[str, np.ndarray] = {}  # First moment
        self._v: Dict[str, np.ndarray] = {}  # Second moment
        self._t = 0  # Timestep

        # Weight history for rollback
        self._weight_history: deque = deque(maxlen=10)

        # Validation buffer
        self._validation_buffer: List[TradeResult] = []

    def compute_update(
        self,
        param_name: str,
        gradient: np.ndarray,
        weight: float = 1.0
    ) -> np.ndarray:
        """
        Compute ADAM-style parameter update.

        Args:
            param_name: Name of parameter being updated
            gradient: Gradient to apply
            weight: Confidence weight (0-1)

        Returns:
            Update delta to apply
        """
        self._t += 1

        # Initialize moments if needed
        if param_name not in self._m:
            self._m[param_name] = np.zeros_like(gradient)
            self._v[param_name] = np.zeros_like(gradient)

        # Weighted gradient
        g = gradient * weight

        # Update moments
        self._m[param_name] = self.momentum * self._m[param_name] + (1 - self.momentum) * g
        self._v[param_name] = self.beta2 * self._v[param_name] + (1 - self.beta2) * (g ** 2)

        # Bias correction
        m_hat = self._m[param_name] / (1 - self.momentum ** self._t)
        v_hat = self._v[param_name] / (1 - self.beta2 ** self._t)

        # Compute update
        update = self.learning_rate * m_hat / (np.sqrt(v_hat) + self.epsilon)

        return update

    def validate_update(
        self,
        current_metrics: PerformanceMetrics,
        proposed_metrics: PerformanceMetrics,
    ) -> bool:
        """
        Validate whether a model update should be applied.

        Uses a validation gate to prevent degradation.
        """
        # Must have minimum trades
        if proposed_metrics.total_trades < 10:
            return False

        # Check for significant degradation
        if current_metrics.total_trades > 0:
            win_rate_change = proposed_metrics.win_rate - current_metrics.win_rate
            sharpe_change = proposed_metrics.sharpe_ratio - current_metrics.sharpe_ratio

            # Reject if both metrics significantly worse
            if win_rate_change < -0.1 and sharpe_change < -0.3:
                logger.warning(
                    f"Update rejected: win_rate {win_rate_change:.2%}, "
                    f"sharpe {sharpe_change:.2f}"
                )
                return False

        return True

    def save_checkpoint(self, weights: Dict[str, Any]) -> None:
        """Save weights for potential rollback."""
        self._weight_history.append({
            'timestamp': datetime.now(timezone.utc),
            'weights': weights.copy(),
            't': self._t
        })

    def rollback(self) -> Optional[Dict[str, Any]]:
        """Rollback to previous weights if available."""
        if self._weight_history:
            checkpoint = self._weight_history.pop()
            logger.info(f"Rolling back to checkpoint from {checkpoint['timestamp']}")
            return checkpoint['weights']
        return None


# =============================================================================
# CONVERGENCE TRACKER
# =============================================================================

class ConvergenceTracker:
    """
    Tracks progress towards convergence targets.

    Determines when the system has achieved stable, good performance.
    """

    def __init__(self, targets: ConvergenceTargets):
        self.targets = targets
        self._history: deque = deque(maxlen=100)
        self._convergence_streak = 0
        self._required_streak = 5  # Consecutive checks within threshold

    def update(self, metrics: PerformanceMetrics) -> Dict[str, float]:
        """
        Update convergence tracking with new metrics.

        Returns progress towards each target (0-1, >1 means exceeded).
        """
        progress = {}

        if metrics.total_trades >= self.targets.min_trades_for_confidence:
            progress['win_rate'] = metrics.win_rate / self.targets.target_win_rate
            progress['profit_factor'] = metrics.profit_factor / self.targets.target_profit_factor
            progress['risk_reward'] = metrics.avg_risk_reward / self.targets.target_risk_reward
            progress['sharpe'] = metrics.sharpe_ratio / self.targets.target_sharpe
        else:
            progress = {
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'risk_reward': 0.0,
                'sharpe': 0.0
            }

        self._history.append({
            'timestamp': datetime.now(timezone.utc),
            'progress': progress,
            'metrics': metrics.to_dict()
        })

        return progress

    def is_converged(self) -> bool:
        """Check if system has converged to targets."""
        if len(self._history) < self._required_streak:
            return False

        # Check last N entries
        recent = list(self._history)[-self._required_streak:]

        for entry in recent:
            progress = entry['progress']
            # All metrics must be within threshold of target
            for key, value in progress.items():
                if abs(1.0 - value) > self.targets.convergence_threshold:
                    return False

        return True

    def get_weakest_metric(self) -> Tuple[str, float]:
        """Get the metric furthest from its target."""
        if not self._history:
            return ('unknown', 0.0)

        latest = self._history[-1]['progress']
        weakest = min(latest.items(), key=lambda x: x[1])
        return weakest


# =============================================================================
# FEEDBACK LOOP CORE
# =============================================================================

class FeedbackLoop:
    """
    Core feedback loop for ML brain.

    This is the main orchestrator that:
    1. Receives trade outcomes
    2. Updates performance metrics
    3. Triggers model retraining when appropriate
    4. Adapts learning parameters
    5. Tracks convergence progress

    The feedback loop creates a closed-loop system where:
    - Model predictions → Trade execution → Outcomes → Learning → Better predictions
    """

    def __init__(
        self,
        targets: ConvergenceTargets = None,
        db_path: str = "brain_metrics.db",
        update_frequency: int = 10,  # Trades between potential model updates
        min_trades_for_update: int = 20,
    ):
        self.targets = targets or ConvergenceTargets()
        self.db = MetricsDatabase(db_path)
        self.learner = OnlineLearner()
        self.convergence = ConvergenceTracker(self.targets)

        self.update_frequency = update_frequency
        self.min_trades_for_update = min_trades_for_update

        # Current state
        self.metrics = PerformanceMetrics()
        self.state = LearningState()

        # Trade buffer for batch processing
        self._trade_buffer: List[TradeResult] = []

        # Callbacks for model updates
        self._update_callbacks: List[Callable] = []

        # Performance tracking
        self._pnl_history: deque = deque(maxlen=1000)
        self._equity_curve: List[float] = [100000.0]  # Starting equity

        logger.info("FeedbackLoop initialized with targets: "
                   f"win_rate={self.targets.target_win_rate:.1%}, "
                   f"profit_factor={self.targets.target_profit_factor:.1f}")

    def register_update_callback(self, callback: Callable[[PerformanceMetrics, LearningState], None]) -> None:
        """Register a callback to be called when model update is triggered."""
        self._update_callbacks.append(callback)

    def record_trade(self, result: TradeResult) -> Dict[str, Any]:
        """
        Record a completed trade and update metrics.

        This is the main entry point for the feedback loop.

        Args:
            result: Trade result to record

        Returns:
            Dict with updated metrics and any triggered actions
        """
        # Store to database
        self.db.save_trade_result(result)

        # Add to buffer
        self._trade_buffer.append(result)
        self._pnl_history.append(result.pnl)

        # Update equity curve
        new_equity = self._equity_curve[-1] + result.pnl
        self._equity_curve.append(new_equity)

        # Update metrics
        self._update_metrics(result)

        # Check for model update trigger
        actions = self._check_update_trigger()

        # Update convergence tracking
        progress = self.convergence.update(self.metrics)
        self.state.convergence_progress = progress

        # Check phase transition
        self._update_phase()

        # Log event
        event = FeedbackEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="trade_recorded",
            data={
                'trade_id': result.trade_id,
                'pnl': result.pnl,
                'outcome': result.outcome.value,
                'signal_confidence': result.signal_confidence,
            },
            metrics_snapshot=self.metrics
        )
        self.db.save_learning_event(event, self.state)

        return {
            'metrics': self.metrics.to_dict(),
            'convergence_progress': progress,
            'phase': self.state.phase.value,
            'actions_triggered': actions
        }

    def _update_metrics(self, result: TradeResult) -> None:
        """Update performance metrics with new trade."""
        self.metrics.total_trades += 1
        self.metrics.total_pnl += result.pnl

        if result.outcome in [TradeOutcome.WIN, TradeOutcome.TARGET_HIT]:
            self.metrics.winning_trades += 1
            self.metrics.consecutive_wins += 1
            self.metrics.consecutive_losses = 0

            # Update avg win
            n = self.metrics.winning_trades
            self.metrics.avg_win = (
                (self.metrics.avg_win * (n - 1) + result.pnl) / n
            )
        else:
            self.metrics.losing_trades += 1
            self.metrics.consecutive_losses += 1
            self.metrics.consecutive_wins = 0

            # Update avg loss
            n = self.metrics.losing_trades
            self.metrics.avg_loss = (
                (self.metrics.avg_loss * (n - 1) + abs(result.pnl)) / n
            )

        # Calculate derived metrics
        if self.metrics.total_trades > 0:
            self.metrics.win_rate = self.metrics.winning_trades / self.metrics.total_trades
            self.metrics.loss_rate = self.metrics.losing_trades / self.metrics.total_trades

        if self.metrics.avg_loss > 0:
            self.metrics.profit_factor = self.metrics.avg_win / self.metrics.avg_loss
            self.metrics.avg_risk_reward = self.metrics.avg_win / self.metrics.avg_loss

        # Calculate Sharpe (simplified, annualized)
        if len(self._pnl_history) > 10:
            returns = np.array(list(self._pnl_history))
            if returns.std() > 0:
                self.metrics.sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)

        # Calculate max drawdown
        if len(self._equity_curve) > 1:
            equity = np.array(self._equity_curve)
            peak = np.maximum.accumulate(equity)
            drawdown = (peak - equity) / peak
            self.metrics.max_drawdown = drawdown.max()

        self.metrics.last_updated = datetime.now(timezone.utc)

    def _check_update_trigger(self) -> List[str]:
        """Check if model update should be triggered."""
        actions = []

        self.state.trades_since_last_update += 1

        # Check if enough trades for update
        if self.state.trades_since_last_update >= self.update_frequency:
            if self.metrics.total_trades >= self.min_trades_for_update:
                # Trigger model update
                actions.append('model_update')
                self._trigger_model_update()
                self.state.trades_since_last_update = 0

        # Check for emergency conditions
        if self.metrics.consecutive_losses >= 5:
            actions.append('emergency_review')
            self._handle_losing_streak()

        if self.metrics.max_drawdown > 0.15:  # 15% drawdown
            actions.append('risk_alert')

        return actions

    def _trigger_model_update(self) -> None:
        """Trigger model update callbacks."""
        self.state.updates_count += 1
        self.state.last_model_update = datetime.now(timezone.utc)

        logger.info(
            f"Model update #{self.state.updates_count} triggered. "
            f"Metrics: win_rate={self.metrics.win_rate:.1%}, "
            f"sharpe={self.metrics.sharpe_ratio:.2f}"
        )

        # Save performance snapshot
        self.db.save_performance_snapshot(self.metrics)

        # Call registered callbacks
        for callback in self._update_callbacks:
            try:
                callback(self.metrics, self.state)
            except Exception as e:
                logger.error(f"Update callback failed: {e}")

    def _handle_losing_streak(self) -> None:
        """Handle losing streak with adaptive response."""
        logger.warning(
            f"Losing streak detected: {self.metrics.consecutive_losses} losses"
        )

        # Reduce confidence threshold (require higher confidence to trade)
        self.state.confidence_threshold = min(0.8, self.state.confidence_threshold + 0.05)

        # Reduce learning rate (more conservative updates)
        self.state.learning_rate *= 0.8

        # Log event
        event = FeedbackEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="losing_streak_response",
            data={
                'streak_length': self.metrics.consecutive_losses,
                'new_confidence_threshold': self.state.confidence_threshold,
                'new_learning_rate': self.state.learning_rate
            }
        )
        self.db.save_learning_event(event, self.state)

    def _update_phase(self) -> None:
        """Update learning phase based on performance."""
        old_phase = self.state.phase

        if self.convergence.is_converged():
            self.state.phase = LearningPhase.CONVERGED
            self.state.learning_rate = 0.001  # Very small updates
            self.state.exploration_rate = 0.05
        elif self.metrics.total_trades < 50:
            self.state.phase = LearningPhase.EXPLORATION
            self.state.learning_rate = 0.02
            self.state.exploration_rate = 0.3
        elif self.metrics.win_rate > 0.45:
            self.state.phase = LearningPhase.EXPLOITATION
            self.state.learning_rate = 0.01
            self.state.exploration_rate = 0.1
        else:
            self.state.phase = LearningPhase.VALIDATION
            self.state.learning_rate = 0.005
            self.state.exploration_rate = 0.15

        if old_phase != self.state.phase:
            logger.info(f"Phase transition: {old_phase.value} -> {self.state.phase.value}")

    def get_learning_signal(self, trade: TradeResult) -> np.ndarray:
        """
        Compute learning signal from trade result.

        This is used to update model weights based on outcome.

        Returns:
            Gradient-like signal indicating direction of improvement
        """
        # Compute reward signal
        outcome_reward = 1.0 if trade.outcome in [TradeOutcome.WIN, TradeOutcome.TARGET_HIT] else -1.0

        # Scale by magnitude
        magnitude = abs(trade.pnl_pct) / 0.02  # Normalize to typical 2% move

        # Weight by confidence error (higher error = more learning)
        confidence_error = abs(outcome_reward - trade.signal_confidence)

        # Combine into learning signal
        signal = outcome_reward * magnitude * (1 + confidence_error)

        # Convert features to gradient direction
        features = np.array(list(trade.features_at_entry.values())) if trade.features_at_entry else np.zeros(10)

        return signal * features

    def get_status(self) -> Dict[str, Any]:
        """Get current feedback loop status."""
        weakest_metric, weakest_value = self.convergence.get_weakest_metric()

        return {
            'phase': self.state.phase.value,
            'learning_rate': self.state.learning_rate,
            'confidence_threshold': self.state.confidence_threshold,
            'total_trades': self.metrics.total_trades,
            'win_rate': self.metrics.win_rate,
            'profit_factor': self.metrics.profit_factor,
            'sharpe_ratio': self.metrics.sharpe_ratio,
            'max_drawdown': self.metrics.max_drawdown,
            'convergence_progress': self.state.convergence_progress,
            'is_converged': self.convergence.is_converged(),
            'weakest_metric': weakest_metric,
            'weakest_value': weakest_value,
            'updates_count': self.state.updates_count,
            'last_update': self.state.last_model_update.isoformat() if self.state.last_model_update else None,
        }

    def get_strategy_performance(self) -> Dict[str, Dict[str, float]]:
        """Get performance breakdown by strategy."""
        trades = self.db.get_recent_trades(500)

        strategy_stats: Dict[str, Dict[str, Any]] = {}

        for trade in trades:
            strategy = trade['strategy']
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'total': 0, 'wins': 0, 'total_pnl': 0.0
                }

            strategy_stats[strategy]['total'] += 1
            strategy_stats[strategy]['total_pnl'] += trade['pnl']
            if trade['outcome'] in ['win', 'target_hit']:
                strategy_stats[strategy]['wins'] += 1

        # Calculate win rates
        result = {}
        for strategy, stats in strategy_stats.items():
            result[strategy] = {
                'win_rate': stats['wins'] / stats['total'] if stats['total'] > 0 else 0,
                'total_trades': stats['total'],
                'total_pnl': stats['total_pnl'],
                'avg_pnl': stats['total_pnl'] / stats['total'] if stats['total'] > 0 else 0
            }

        return result


# =============================================================================
# SINGLETON ACCESSOR
# =============================================================================

_feedback_loop: Optional[FeedbackLoop] = None

def get_feedback_loop(
    targets: ConvergenceTargets = None,
    db_path: str = "brain_metrics.db"
) -> FeedbackLoop:
    """Get or create the global feedback loop instance."""
    global _feedback_loop
    if _feedback_loop is None:
        _feedback_loop = FeedbackLoop(targets=targets, db_path=db_path)
    return _feedback_loop


def reset_feedback_loop() -> None:
    """Reset the global feedback loop (for testing)."""
    global _feedback_loop
    _feedback_loop = None
