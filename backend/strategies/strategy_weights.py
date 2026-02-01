"""
Strategy Weights Manager
========================
Unified system for managing strategy weights and performance tracking.

This provides:
1. Persistent weight storage (JSON + SQLite)
2. Performance-based weight adjustment
3. Strategy attribution tracking
4. Confidence calibration

All strategies MUST use this for weight management.
"""

import json
import logging
import os
import sqlite3
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class StrategyWeight:
    """Weight configuration for a single strategy."""
    strategy_id: str
    weight: float                    # 0.0 to 1.0
    enabled: bool = True
    min_confidence: float = 0.5      # Minimum confidence to trigger
    max_position_pct: float = 0.25   # Max position size
    cooldown_minutes: int = 5        # Time between signals

    # Performance tracking
    trades_total: int = 0
    trades_won: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    sharpe: float = 0.0

    # Timestamps
    last_signal: Optional[datetime] = None
    last_trade: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['last_signal'] = self.last_signal.isoformat() if self.last_signal else None
        d['last_trade'] = self.last_trade.isoformat() if self.last_trade else None
        d['last_updated'] = self.last_updated.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyWeight':
        data = data.copy()
        if data.get('last_signal'):
            data['last_signal'] = datetime.fromisoformat(data['last_signal'])
        if data.get('last_trade'):
            data['last_trade'] = datetime.fromisoformat(data['last_trade'])
        if data.get('last_updated'):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        else:
            data['last_updated'] = datetime.now()
        return cls(**data)


@dataclass
class WeightConfig:
    """Global weight configuration."""
    version: str = "1.0"
    auto_adjust: bool = True            # Auto-adjust based on performance
    adjustment_interval_days: int = 7   # Days between auto-adjustments
    min_trades_for_adjust: int = 10     # Minimum trades before adjusting
    decay_factor: float = 0.95          # Weight decay for poor performers
    boost_factor: float = 1.05          # Weight boost for good performers
    max_weight: float = 1.0
    min_weight: float = 0.1
    last_adjusted: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "auto_adjust": self.auto_adjust,
            "adjustment_interval_days": self.adjustment_interval_days,
            "min_trades_for_adjust": self.min_trades_for_adjust,
            "decay_factor": self.decay_factor,
            "boost_factor": self.boost_factor,
            "max_weight": self.max_weight,
            "min_weight": self.min_weight,
            "last_adjusted": self.last_adjusted.isoformat() if self.last_adjusted else None
        }


# Default strategy weights
DEFAULT_WEIGHTS = {
    # ICT Strategies
    "ict_fvg": StrategyWeight("ict_fvg", weight=0.8, min_confidence=0.6),
    "ict_order_block": StrategyWeight("ict_order_block", weight=0.75, min_confidence=0.65),
    "ict_breaker": StrategyWeight("ict_breaker", weight=0.7, min_confidence=0.6),
    "ict_liquidity_sweep": StrategyWeight("ict_liquidity_sweep", weight=0.85, min_confidence=0.7),
    "ict_smt": StrategyWeight("ict_smt", weight=0.9, min_confidence=0.75),
    "ict_ote": StrategyWeight("ict_ote", weight=0.8, min_confidence=0.65),
    "ict_killzone": StrategyWeight("ict_killzone", weight=0.7, min_confidence=0.6),
    "ict_mss": StrategyWeight("ict_mss", weight=0.75, min_confidence=0.65),

    # Technical Strategies
    "ma_crossover": StrategyWeight("ma_crossover", weight=0.5, min_confidence=0.55),
    "rsi_reversal": StrategyWeight("rsi_reversal", weight=0.55, min_confidence=0.6),
    "macd_signal": StrategyWeight("macd_signal", weight=0.5, min_confidence=0.55),
    "bollinger_squeeze": StrategyWeight("bollinger_squeeze", weight=0.6, min_confidence=0.6),

    # ML Strategies
    "ml_ensemble": StrategyWeight("ml_ensemble", weight=0.85, min_confidence=0.7),
    "futures_brain_v2": StrategyWeight("futures_brain_v2", weight=0.9, min_confidence=0.75),
    "rl_agent": StrategyWeight("rl_agent", weight=0.8, min_confidence=0.7),

    # Hybrid
    "tpt_aggressive": StrategyWeight("tpt_aggressive", weight=0.75, min_confidence=0.65),
}


class StrategyWeightsManager:
    """
    Manages strategy weights with persistence.

    Features:
    - JSON file persistence for portability
    - SQLite for performance history
    - Automatic weight adjustment based on performance
    - Thread-safe operations
    """

    def __init__(
        self,
        weights_file: str = "strategy_weights.json",
        db_path: str = "strategy_performance.db"
    ):
        self.weights_file = Path(weights_file)
        self.db_path = Path(db_path)

        self._lock = threading.Lock()
        self._weights: Dict[str, StrategyWeight] = {}
        self._config = WeightConfig()

        # Ensure directories exist
        self.weights_file.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        self._load_weights()

        logger.info(f"StrategyWeightsManager initialized with {len(self._weights)} strategies")

    def _init_db(self):
        """Initialize SQLite database for performance tracking."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS strategy_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    strategy_id TEXT,
                    symbol TEXT,
                    direction TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    entry_time TEXT,
                    exit_time TEXT,
                    pnl REAL,
                    pnl_pct REAL,
                    confidence REAL,
                    is_win INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS weight_adjustments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id TEXT,
                    old_weight REAL,
                    new_weight REAL,
                    reason TEXT,
                    metrics_json TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_trades_strategy ON strategy_trades(strategy_id);
                CREATE INDEX IF NOT EXISTS idx_trades_time ON strategy_trades(exit_time);
            """)

    def _load_weights(self):
        """Load weights from file or use defaults."""
        if self.weights_file.exists():
            try:
                with open(self.weights_file, 'r') as f:
                    data = json.load(f)

                # Load config
                if 'config' in data:
                    config_data = data['config']
                    if config_data.get('last_adjusted'):
                        config_data['last_adjusted'] = datetime.fromisoformat(config_data['last_adjusted'])
                    self._config = WeightConfig(**config_data)

                # Load weights
                for strategy_id, weight_data in data.get('weights', {}).items():
                    self._weights[strategy_id] = StrategyWeight.from_dict(weight_data)

                logger.info(f"Loaded {len(self._weights)} strategy weights from {self.weights_file}")

            except Exception as e:
                logger.error(f"Failed to load weights: {e}, using defaults")
                self._weights = DEFAULT_WEIGHTS.copy()
        else:
            self._weights = DEFAULT_WEIGHTS.copy()
            self._save_weights()

    def _save_weights(self):
        """Save weights to file."""
        with self._lock:
            data = {
                "config": self._config.to_dict(),
                "weights": {sid: w.to_dict() for sid, w in self._weights.items()},
                "saved_at": datetime.now().isoformat()
            }

            with open(self.weights_file, 'w') as f:
                json.dump(data, f, indent=2)

    def get_weight(self, strategy_id: str) -> Optional[StrategyWeight]:
        """Get weight for a strategy."""
        return self._weights.get(strategy_id)

    def get_all_weights(self) -> Dict[str, StrategyWeight]:
        """Get all strategy weights."""
        return self._weights.copy()

    def set_weight(self, strategy_id: str, weight: float, save: bool = True) -> None:
        """Set weight for a strategy."""
        with self._lock:
            if strategy_id not in self._weights:
                self._weights[strategy_id] = StrategyWeight(strategy_id, weight=weight)
            else:
                self._weights[strategy_id].weight = max(
                    self._config.min_weight,
                    min(self._config.max_weight, weight)
                )
                self._weights[strategy_id].last_updated = datetime.now()

        if save:
            self._save_weights()

    def record_trade(
        self,
        trade_id: str,
        strategy_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        entry_time: datetime,
        exit_time: datetime,
        pnl: float,
        confidence: float = 0.0
    ) -> None:
        """
        Record a trade result for a strategy.

        This updates the strategy's performance metrics.
        """
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        if direction.lower() in ['short', 'sell']:
            pnl_pct = -pnl_pct
        is_win = pnl > 0

        # Record to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO strategy_trades
                (trade_id, strategy_id, symbol, direction, entry_price, exit_price,
                 entry_time, exit_time, pnl, pnl_pct, confidence, is_win)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id, strategy_id, symbol, direction, entry_price, exit_price,
                entry_time.isoformat(), exit_time.isoformat(),
                pnl, pnl_pct, confidence, int(is_win)
            ))

        # Update in-memory weight
        with self._lock:
            if strategy_id not in self._weights:
                self._weights[strategy_id] = StrategyWeight(strategy_id, weight=0.5)

            w = self._weights[strategy_id]
            w.trades_total += 1
            w.total_pnl += pnl
            if is_win:
                w.trades_won += 1
            w.win_rate = w.trades_won / w.trades_total if w.trades_total > 0 else 0.0
            w.avg_pnl = w.total_pnl / w.trades_total if w.trades_total > 0 else 0.0
            w.last_trade = exit_time
            w.last_updated = datetime.now()

        self._save_weights()

        # Check if auto-adjustment is needed
        if self._config.auto_adjust:
            self._check_auto_adjust()

    def _check_auto_adjust(self):
        """Check if weights should be auto-adjusted."""
        if not self._config.auto_adjust:
            return

        last = self._config.last_adjusted
        if last and (datetime.now() - last).days < self._config.adjustment_interval_days:
            return

        self._auto_adjust_weights()

    def _auto_adjust_weights(self):
        """Auto-adjust weights based on performance."""
        logger.info("Running auto weight adjustment")

        adjustments = []

        with self._lock:
            for strategy_id, w in self._weights.items():
                if w.trades_total < self._config.min_trades_for_adjust:
                    continue

                old_weight = w.weight

                # Adjust based on win rate
                target_win_rate = 0.55
                if w.win_rate >= target_win_rate:
                    # Boost good performers
                    new_weight = min(
                        self._config.max_weight,
                        w.weight * self._config.boost_factor
                    )
                else:
                    # Decay poor performers
                    new_weight = max(
                        self._config.min_weight,
                        w.weight * self._config.decay_factor
                    )

                if abs(new_weight - old_weight) > 0.01:
                    w.weight = new_weight
                    w.last_updated = datetime.now()
                    adjustments.append({
                        "strategy_id": strategy_id,
                        "old_weight": old_weight,
                        "new_weight": new_weight,
                        "win_rate": w.win_rate,
                        "trades": w.trades_total
                    })

            self._config.last_adjusted = datetime.now()

        # Record adjustments
        if adjustments:
            with sqlite3.connect(self.db_path) as conn:
                for adj in adjustments:
                    conn.execute("""
                        INSERT INTO weight_adjustments
                        (strategy_id, old_weight, new_weight, reason, metrics_json)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        adj["strategy_id"],
                        adj["old_weight"],
                        adj["new_weight"],
                        "auto_adjust",
                        json.dumps(adj)
                    ))

            self._save_weights()
            logger.info(f"Adjusted weights for {len(adjustments)} strategies")

    def can_signal(self, strategy_id: str) -> Tuple[bool, str]:
        """
        Check if a strategy can generate a signal.

        Checks:
        - Strategy enabled
        - Cooldown elapsed
        """
        w = self._weights.get(strategy_id)
        if not w:
            return True, "Unknown strategy"

        if not w.enabled:
            return False, "Strategy disabled"

        if w.last_signal:
            elapsed = (datetime.now() - w.last_signal).total_seconds() / 60
            if elapsed < w.cooldown_minutes:
                return False, f"Cooldown: {w.cooldown_minutes - elapsed:.1f} minutes remaining"

        return True, "OK"

    def record_signal(self, strategy_id: str) -> None:
        """Record that a strategy generated a signal."""
        with self._lock:
            if strategy_id in self._weights:
                self._weights[strategy_id].last_signal = datetime.now()
        self._save_weights()

    def get_strategy_performance(self, strategy_id: str, days: int = 30) -> Dict[str, Any]:
        """Get detailed performance for a strategy."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get trades
            trades = conn.execute("""
                SELECT * FROM strategy_trades
                WHERE strategy_id = ? AND exit_time > ?
                ORDER BY exit_time DESC
            """, (strategy_id, cutoff)).fetchall()

            if not trades:
                return {
                    "strategy_id": strategy_id,
                    "trades": 0,
                    "win_rate": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                    "period_days": days
                }

            trades_list = [dict(t) for t in trades]
            wins = sum(1 for t in trades_list if t['is_win'])
            total_pnl = sum(t['pnl'] for t in trades_list)

            return {
                "strategy_id": strategy_id,
                "trades": len(trades_list),
                "wins": wins,
                "losses": len(trades_list) - wins,
                "win_rate": wins / len(trades_list),
                "total_pnl": total_pnl,
                "avg_pnl": total_pnl / len(trades_list),
                "period_days": days,
                "recent_trades": trades_list[:10]
            }

    def get_all_performance(self, days: int = 30) -> Dict[str, Dict[str, Any]]:
        """Get performance for all strategies."""
        result = {}
        for strategy_id in self._weights:
            result[strategy_id] = self.get_strategy_performance(strategy_id, days)
        return result

    def get_status(self) -> Dict[str, Any]:
        """Get manager status."""
        return {
            "strategies_count": len(self._weights),
            "config": self._config.to_dict(),
            "weights": {sid: w.to_dict() for sid, w in self._weights.items()},
            "weights_file": str(self.weights_file),
            "db_path": str(self.db_path)
        }


# Singleton instance
_weights_manager: Optional[StrategyWeightsManager] = None


def get_weights_manager() -> StrategyWeightsManager:
    """Get global weights manager instance."""
    global _weights_manager
    if _weights_manager is None:
        _weights_manager = StrategyWeightsManager()
    return _weights_manager


__all__ = [
    'StrategyWeight',
    'WeightConfig',
    'StrategyWeightsManager',
    'get_weights_manager',
    'DEFAULT_WEIGHTS',
]
