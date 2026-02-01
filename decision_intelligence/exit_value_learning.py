"""
Exit-Value Learning (Recursive MDP)
====================================
P1: Learn optimal exit timing per regime using Bellman updates.

Most trading systems have static exit rules (stop-loss, take-profit).
This learns WHEN to exit based on:
- Current regime
- Time in trade
- Unrealized P&L trajectory
- Volatility conditions

Uses a Recursive MDP formulation where:
- State = (regime, time_in_trade, unrealized_pnl_bucket, volatility_bucket)
- Actions = (HOLD, EXIT)
- Reward = realized P&L on exit, 0 on hold
- Value function = expected future P&L from this state

SHADOW MODE: Always shadow. Suggests exits but doesn't execute them.

Rollback Plan: Delete this file, fall back to static exit rules.
"""

import json
import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import sqlite3

logger = logging.getLogger(__name__)

# Optional numpy
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy not installed - using basic math")


class ExitAction(Enum):
    """Possible actions in the exit MDP."""
    HOLD = "hold"
    EXIT = "exit"


class ExitReason(Enum):
    """Reasons for suggested exit."""
    VALUE_OPTIMAL = "value_optimal"      # Value function says exit
    TIME_DECAY = "time_decay"            # Holding too long
    REGIME_CHANGE = "regime_change"      # Regime no longer favorable
    VOLATILITY_SPIKE = "volatility_spike"  # Volatility increased
    DRAWDOWN = "drawdown"                # Unrealized loss too large
    TARGET_HIT = "target_hit"            # Target reached
    STOP_HIT = "stop_hit"                # Stop loss hit


@dataclass(frozen=True)
class ExitState:
    """State representation for exit decision."""
    regime: str
    time_in_trade_bucket: int      # 0-4 (buckets of holding time)
    pnl_bucket: int                # -2 to +2 (loss/gain buckets)
    volatility_bucket: int         # 0-2 (low/med/high)
    direction: str                 # LONG or SHORT
    
    def to_tuple(self) -> Tuple:
        """Convert to hashable tuple for dictionary keys."""
        return (
            self.regime,
            self.time_in_trade_bucket,
            self.pnl_bucket,
            self.volatility_bucket,
            self.direction,
        )
    
    @classmethod
    def from_tuple(cls, t: Tuple) -> "ExitState":
        return cls(
            regime=t[0],
            time_in_trade_bucket=t[1],
            pnl_bucket=t[2],
            volatility_bucket=t[3],
            direction=t[4],
        )


@dataclass
class ExitRecommendation:
    """Recommendation from the exit value learner."""
    action: ExitAction
    reason: ExitReason
    confidence: float
    expected_value_hold: float
    expected_value_exit: float
    current_state: ExitState
    
    # Shadow mode indicator
    is_shadow: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "reason": self.reason.value,
            "confidence": self.confidence,
            "expected_value_hold": self.expected_value_hold,
            "expected_value_exit": self.expected_value_exit,
            "state": {
                "regime": self.current_state.regime,
                "time_bucket": self.current_state.time_in_trade_bucket,
                "pnl_bucket": self.current_state.pnl_bucket,
                "volatility_bucket": self.current_state.volatility_bucket,
            },
            "is_shadow": self.is_shadow,
        }


@dataclass
class TradeEpisode:
    """A complete trade episode for learning."""
    episode_id: str
    symbol: str
    direction: str
    entry_time: datetime
    exit_time: datetime
    
    # State trajectory
    states: List[ExitState] = field(default_factory=list)
    actions: List[ExitAction] = field(default_factory=list)
    
    # Outcome
    final_pnl: float = 0.0
    exit_reason: ExitReason = ExitReason.VALUE_OPTIMAL


class ExitValueLearner:
    """
    Recursive MDP for learning optimal exit timing.
    
    Uses Q-learning style updates:
    Q(s, a) = Q(s, a) + α * (r + γ * max_a' Q(s', a') - Q(s, a))
    
    Where:
    - s = current state
    - a = action (HOLD or EXIT)
    - r = reward (0 for HOLD, realized P&L for EXIT)
    - γ = discount factor
    - s' = next state
    """
    
    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        exploration_rate: float = 0.1,
        db_path: Path = None,
    ):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate
        
        self.db_path = db_path or Path("decision_intelligence/exit_values.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Q-table: state -> action -> value
        self.q_table: Dict[Tuple, Dict[str, float]] = defaultdict(
            lambda: {"hold": 0.0, "exit": 0.0}
        )
        
        # Visit counts for exploration
        self.visit_counts: Dict[Tuple, int] = defaultdict(int)
        
        # Episode buffer
        self.episode_buffer: List[TradeEpisode] = []
        
        # Initialize
        self._init_db()
        self._load_q_table()
        
        logger.info("ExitValueLearner initialized")
    
    def _init_db(self) -> None:
        """Initialize SQLite storage."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS q_values (
                    state_key TEXT PRIMARY KEY,
                    hold_value REAL DEFAULT 0.0,
                    exit_value REAL DEFAULT 0.0,
                    visit_count INTEGER DEFAULT 0,
                    last_updated TEXT
                );
                
                CREATE TABLE IF NOT EXISTS episodes (
                    episode_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    direction TEXT,
                    entry_time TEXT,
                    exit_time TEXT,
                    states_json TEXT,
                    final_pnl REAL,
                    exit_reason TEXT
                );
            """)
    
    def _load_q_table(self) -> None:
        """Load Q-table from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT state_key, hold_value, exit_value, visit_count FROM q_values")
                
                for row in cursor.fetchall():
                    state_tuple = tuple(json.loads(row[0]))
                    self.q_table[state_tuple] = {
                        "hold": row[1],
                        "exit": row[2],
                    }
                    self.visit_counts[state_tuple] = row[3]
                
                logger.info(f"Loaded {len(self.q_table)} Q-values from database")
        except Exception as e:
            logger.error(f"Error loading Q-table: {e}")
    
    def _save_q_value(self, state: ExitState) -> None:
        """Save single Q-value to database."""
        state_tuple = state.to_tuple()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO q_values
                    (state_key, hold_value, exit_value, visit_count, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    json.dumps(state_tuple),
                    self.q_table[state_tuple]["hold"],
                    self.q_table[state_tuple]["exit"],
                    self.visit_counts[state_tuple],
                    datetime.now(timezone.utc).isoformat(),
                ))
        except Exception as e:
            logger.error(f"Error saving Q-value: {e}")
    
    # =========================================================================
    # STATE DISCRETIZATION
    # =========================================================================
    
    def discretize_state(
        self,
        regime: str,
        time_in_trade_minutes: float,
        unrealized_pnl_pct: float,
        current_volatility: float,
        avg_volatility: float,
        direction: str,
    ) -> ExitState:
        """
        Discretize continuous state into buckets.
        
        Time buckets:
            0: 0-15 min
            1: 15-60 min
            2: 1-4 hours
            3: 4-24 hours
            4: >24 hours
        
        P&L buckets:
            -2: < -2%
            -1: -2% to -0.5%
            0: -0.5% to +0.5%
            +1: +0.5% to +2%
            +2: > +2%
        
        Volatility buckets:
            0: low (< 0.7x average)
            1: normal (0.7x - 1.3x average)
            2: high (> 1.3x average)
        """
        # Time bucket
        if time_in_trade_minutes < 15:
            time_bucket = 0
        elif time_in_trade_minutes < 60:
            time_bucket = 1
        elif time_in_trade_minutes < 240:
            time_bucket = 2
        elif time_in_trade_minutes < 1440:
            time_bucket = 3
        else:
            time_bucket = 4
        
        # P&L bucket
        if unrealized_pnl_pct < -0.02:
            pnl_bucket = -2
        elif unrealized_pnl_pct < -0.005:
            pnl_bucket = -1
        elif unrealized_pnl_pct < 0.005:
            pnl_bucket = 0
        elif unrealized_pnl_pct < 0.02:
            pnl_bucket = 1
        else:
            pnl_bucket = 2
        
        # Volatility bucket
        if avg_volatility > 0:
            vol_ratio = current_volatility / avg_volatility
        else:
            vol_ratio = 1.0
        
        if vol_ratio < 0.7:
            vol_bucket = 0
        elif vol_ratio < 1.3:
            vol_bucket = 1
        else:
            vol_bucket = 2
        
        return ExitState(
            regime=regime,
            time_in_trade_bucket=time_bucket,
            pnl_bucket=pnl_bucket,
            volatility_bucket=vol_bucket,
            direction=direction,
        )
    
    # =========================================================================
    # RECOMMENDATION
    # =========================================================================
    
    def recommend_action(
        self,
        state: ExitState,
        unrealized_pnl: float = 0.0,
        stop_loss_pct: float = -0.02,
        take_profit_pct: float = 0.04,
    ) -> ExitRecommendation:
        """
        Recommend whether to HOLD or EXIT based on learned values.
        
        ALWAYS returns a shadow recommendation - does not execute.
        """
        state_tuple = state.to_tuple()
        
        # Get Q-values
        q_hold = self.q_table[state_tuple]["hold"]
        q_exit = self.q_table[state_tuple]["exit"]
        
        # Check hard rules first (safety overrides)
        pnl_pct = unrealized_pnl  # Already percentage
        
        if pnl_pct <= stop_loss_pct:
            return ExitRecommendation(
                action=ExitAction.EXIT,
                reason=ExitReason.STOP_HIT,
                confidence=1.0,
                expected_value_hold=q_hold,
                expected_value_exit=q_exit,
                current_state=state,
                is_shadow=True,
            )
        
        if pnl_pct >= take_profit_pct:
            return ExitRecommendation(
                action=ExitAction.EXIT,
                reason=ExitReason.TARGET_HIT,
                confidence=0.9,
                expected_value_hold=q_hold,
                expected_value_exit=q_exit,
                current_state=state,
                is_shadow=True,
            )
        
        # Time decay check
        if state.time_in_trade_bucket >= 4 and state.pnl_bucket <= 0:
            return ExitRecommendation(
                action=ExitAction.EXIT,
                reason=ExitReason.TIME_DECAY,
                confidence=0.7,
                expected_value_hold=q_hold,
                expected_value_exit=q_exit,
                current_state=state,
                is_shadow=True,
            )
        
        # Volatility spike check
        if state.volatility_bucket >= 2 and state.pnl_bucket < 0:
            return ExitRecommendation(
                action=ExitAction.EXIT,
                reason=ExitReason.VOLATILITY_SPIKE,
                confidence=0.6,
                expected_value_hold=q_hold,
                expected_value_exit=q_exit,
                current_state=state,
                is_shadow=True,
            )
        
        # Value-based decision
        # Add exploration bonus for less-visited states
        visit_count = self.visit_counts[state_tuple]
        exploration_bonus = 0.1 / (1 + visit_count) if visit_count < 10 else 0
        
        effective_q_exit = q_exit + exploration_bonus
        
        if effective_q_exit > q_hold:
            # Calculate confidence based on value difference
            diff = effective_q_exit - q_hold
            confidence = min(0.9, 0.5 + diff * 10)  # Scale difference to confidence
            
            return ExitRecommendation(
                action=ExitAction.EXIT,
                reason=ExitReason.VALUE_OPTIMAL,
                confidence=confidence,
                expected_value_hold=q_hold,
                expected_value_exit=q_exit,
                current_state=state,
                is_shadow=True,
            )
        else:
            confidence = min(0.9, 0.5 + (q_hold - q_exit) * 10)
            
            return ExitRecommendation(
                action=ExitAction.HOLD,
                reason=ExitReason.VALUE_OPTIMAL,
                confidence=confidence,
                expected_value_hold=q_hold,
                expected_value_exit=q_exit,
                current_state=state,
                is_shadow=True,
            )
    
    # =========================================================================
    # LEARNING
    # =========================================================================
    
    def update_from_episode(self, episode: TradeEpisode) -> None:
        """
        Update Q-values from a completed trade episode.
        
        Uses backward induction: start from the end and propagate values back.
        """
        if not episode.states:
            return
        
        # Final reward is the realized P&L
        final_reward = episode.final_pnl
        
        # Backward pass
        future_value = 0.0  # Value of terminal state
        
        for i in range(len(episode.states) - 1, -1, -1):
            state = episode.states[i]
            action = episode.actions[i] if i < len(episode.actions) else ExitAction.EXIT
            state_tuple = state.to_tuple()
            
            # Increment visit count
            self.visit_counts[state_tuple] += 1
            
            # Current Q-value
            current_q = self.q_table[state_tuple][action.value]
            
            # Target value
            if action == ExitAction.EXIT or i == len(episode.states) - 1:
                # Terminal action - reward is the P&L
                target = final_reward
            else:
                # Non-terminal - use discounted future value
                target = 0 + self.discount_factor * future_value
            
            # Q-learning update
            new_q = current_q + self.learning_rate * (target - current_q)
            self.q_table[state_tuple][action.value] = new_q
            
            # Update future value for next iteration
            future_value = max(
                self.q_table[state_tuple]["hold"],
                self.q_table[state_tuple]["exit"]
            )
            
            # Save to database
            self._save_q_value(state)
        
        # Save episode
        self._save_episode(episode)
        
        logger.debug(f"Updated Q-values from episode {episode.episode_id}")
    
    def _save_episode(self, episode: TradeEpisode) -> None:
        """Save episode to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO episodes
                    (episode_id, symbol, direction, entry_time, exit_time,
                     states_json, final_pnl, exit_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    episode.episode_id,
                    episode.symbol,
                    episode.direction,
                    episode.entry_time.isoformat(),
                    episode.exit_time.isoformat(),
                    json.dumps([s.to_tuple() for s in episode.states]),
                    episode.final_pnl,
                    episode.exit_reason.value,
                ))
        except Exception as e:
            logger.error(f"Error saving episode: {e}")
    
    def batch_update(self, episodes: List[TradeEpisode]) -> None:
        """Update from multiple episodes."""
        for episode in episodes:
            self.update_from_episode(episode)
        
        logger.info(f"Batch updated from {len(episodes)} episodes")
    
    # =========================================================================
    # ANALYSIS
    # =========================================================================
    
    def get_optimal_exits_by_regime(self) -> Dict[str, Dict[str, float]]:
        """
        Get optimal exit points by regime.
        
        Returns expected value of EXIT action for each regime.
        """
        regime_exits = defaultdict(lambda: {"total_value": 0.0, "count": 0})
        
        for state_tuple, q_values in self.q_table.items():
            state = ExitState.from_tuple(state_tuple)
            
            # If EXIT is optimal for this state
            if q_values["exit"] > q_values["hold"]:
                regime_exits[state.regime]["total_value"] += q_values["exit"]
                regime_exits[state.regime]["count"] += 1
        
        # Calculate averages
        result = {}
        for regime, data in regime_exits.items():
            if data["count"] > 0:
                result[regime] = {
                    "avg_exit_value": data["total_value"] / data["count"],
                    "exit_states_count": data["count"],
                }
        
        return result
    
    def get_value_surface(self, regime: str, direction: str = "LONG") -> List[Dict]:
        """
        Get the value surface for a regime.
        
        Returns Q-values for all state combinations.
        """
        surface = []
        
        for time_bucket in range(5):
            for pnl_bucket in range(-2, 3):
                for vol_bucket in range(3):
                    state = ExitState(
                        regime=regime,
                        time_in_trade_bucket=time_bucket,
                        pnl_bucket=pnl_bucket,
                        volatility_bucket=vol_bucket,
                        direction=direction,
                    )
                    state_tuple = state.to_tuple()
                    
                    surface.append({
                        "time_bucket": time_bucket,
                        "pnl_bucket": pnl_bucket,
                        "vol_bucket": vol_bucket,
                        "q_hold": self.q_table[state_tuple]["hold"],
                        "q_exit": self.q_table[state_tuple]["exit"],
                        "optimal_action": "exit" if self.q_table[state_tuple]["exit"] > self.q_table[state_tuple]["hold"] else "hold",
                        "visits": self.visit_counts[state_tuple],
                    })
        
        return surface
    
    def get_stats(self) -> Dict[str, Any]:
        """Get learner statistics."""
        total_states = len(self.q_table)
        total_visits = sum(self.visit_counts.values())
        
        # Count states where EXIT is optimal
        exit_optimal_count = sum(
            1 for q in self.q_table.values()
            if q["exit"] > q["hold"]
        )
        
        # Get episode count
        with sqlite3.connect(self.db_path) as conn:
            episode_count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        
        return {
            "total_states": total_states,
            "total_visits": total_visits,
            "exit_optimal_states": exit_optimal_count,
            "hold_optimal_states": total_states - exit_optimal_count,
            "episodes_learned": episode_count,
            "learning_rate": self.learning_rate,
            "discount_factor": self.discount_factor,
        }


# =============================================================================
# INTEGRATION HELPER
# =============================================================================

class ExitValueIntegration:
    """
    Helper to integrate exit value learning with existing systems.
    
    Tracks open positions and generates state updates.
    """
    
    def __init__(self, learner: ExitValueLearner = None):
        self.learner = learner or ExitValueLearner()
        
        # Track open positions
        self.open_positions: Dict[str, Dict] = {}  # position_id -> data
    
    def open_position(
        self,
        position_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        regime: str,
    ) -> None:
        """Record a new position opening."""
        self.open_positions[position_id] = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "entry_time": datetime.now(timezone.utc),
            "regime": regime,
            "states": [],
            "actions": [],
        }
    
    def update_position(
        self,
        position_id: str,
        current_price: float,
        current_volatility: float,
        avg_volatility: float,
        current_regime: str,
    ) -> Optional[ExitRecommendation]:
        """
        Update position state and get exit recommendation.
        
        SHADOW MODE: Always returns recommendation but doesn't execute.
        """
        if position_id not in self.open_positions:
            return None
        
        pos = self.open_positions[position_id]
        
        # Calculate metrics
        time_in_trade = (datetime.now(timezone.utc) - pos["entry_time"]).total_seconds() / 60
        
        if pos["direction"] == "LONG":
            unrealized_pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
        else:
            unrealized_pnl_pct = (pos["entry_price"] - current_price) / pos["entry_price"]
        
        # Discretize state
        state = self.learner.discretize_state(
            regime=current_regime,
            time_in_trade_minutes=time_in_trade,
            unrealized_pnl_pct=unrealized_pnl_pct,
            current_volatility=current_volatility,
            avg_volatility=avg_volatility,
            direction=pos["direction"],
        )
        
        # Track state trajectory
        pos["states"].append(state)
        
        # Get recommendation
        recommendation = self.learner.recommend_action(
            state=state,
            unrealized_pnl=unrealized_pnl_pct,
        )
        
        # Track action (for learning later)
        pos["actions"].append(recommendation.action)
        
        return recommendation
    
    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_reason: ExitReason = ExitReason.VALUE_OPTIMAL,
    ) -> Optional[TradeEpisode]:
        """
        Close position and create learning episode.
        """
        if position_id not in self.open_positions:
            return None
        
        pos = self.open_positions.pop(position_id)
        
        # Calculate final P&L
        if pos["direction"] == "LONG":
            final_pnl = (exit_price - pos["entry_price"]) / pos["entry_price"]
        else:
            final_pnl = (pos["entry_price"] - exit_price) / pos["entry_price"]
        
        # Create episode
        episode = TradeEpisode(
            episode_id=position_id,
            symbol=pos["symbol"],
            direction=pos["direction"],
            entry_time=pos["entry_time"],
            exit_time=datetime.now(timezone.utc),
            states=pos["states"],
            actions=pos["actions"],
            final_pnl=final_pnl,
            exit_reason=exit_reason,
        )
        
        # Learn from episode
        self.learner.update_from_episode(episode)
        
        return episode


# =============================================================================
# SINGLETON
# =============================================================================

_exit_value_learner: Optional[ExitValueLearner] = None


def get_exit_value_learner() -> ExitValueLearner:
    """Get or create the ExitValueLearner singleton."""
    global _exit_value_learner
    if _exit_value_learner is None:
        _exit_value_learner = ExitValueLearner()
    return _exit_value_learner
