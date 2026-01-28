"""
QUANT_INDUSTRY_V1 Core Types

Common data types and structures used throughout the system.
All components should use these types for consistency.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, NewType
from enum import Enum
import hashlib
import json
import numpy as np
import pandas as pd


# Type aliases
Symbol = NewType('Symbol', str)
Timeframe = NewType('Timeframe', str)
ModelId = NewType('ModelId', str)
StrategyId = NewType('StrategyId', str)
RunId = NewType('RunId', str)
CorrelationId = NewType('CorrelationId', str)


class Direction(Enum):
    """Trading direction."""
    LONG = 'long'
    SHORT = 'short'
    FLAT = 'flat'

    def __str__(self) -> str:
        return self.value

    @property
    def sign(self) -> int:
        """Get numerical sign (-1, 0, 1)."""
        if self == Direction.LONG:
            return 1
        elif self == Direction.SHORT:
            return -1
        return 0


class SignalType(Enum):
    """Type of trading signal."""
    ENTRY_LONG = 'entry_long'
    ENTRY_SHORT = 'entry_short'
    EXIT = 'exit'
    HOLD = 'hold'
    SCALE_IN = 'scale_in'
    SCALE_OUT = 'scale_out'


class Regime(Enum):
    """Market regime classification."""
    LOW_VOL = 'low_vol'
    NORMAL = 'normal'
    HIGH_VOL = 'high_vol'
    CRISIS = 'crisis'
    TRENDING_UP = 'trending_up'
    TRENDING_DOWN = 'trending_down'
    RANGING = 'ranging'

    @property
    def is_volatile(self) -> bool:
        """Check if regime indicates high volatility."""
        return self in (Regime.HIGH_VOL, Regime.CRISIS)

    @property
    def is_trending(self) -> bool:
        """Check if regime indicates trending market."""
        return self in (Regime.TRENDING_UP, Regime.TRENDING_DOWN)


@dataclass
class MarketData:
    """
    Market data container.

    Holds OHLCV data with metadata for a single symbol.
    """
    symbol: Symbol
    timeframe: Timeframe
    df: pd.DataFrame  # Must have columns: timestamp, open, high, low, close, volume
    source: str
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    is_adjusted: bool = True

    def __post_init__(self):
        """Validate DataFrame columns."""
        required_cols = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
        # Handle case where index might be timestamp
        available = set(self.df.columns) | ({self.df.index.name} if self.df.index.name else set())
        missing = required_cols - available
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    @property
    def latest(self) -> Dict[str, Any]:
        """Get latest bar as dictionary."""
        if self.df.empty:
            return {}
        row = self.df.iloc[-1]
        return {
            'timestamp': row.get('timestamp', self.df.index[-1]),
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close'],
            'volume': row['volume'],
        }

    @property
    def close(self) -> pd.Series:
        """Get close prices."""
        return self.df['close']

    @property
    def returns(self) -> pd.Series:
        """Calculate returns."""
        return self.df['close'].pct_change()

    @property
    def is_empty(self) -> bool:
        """Check if data is empty."""
        return self.df.empty

    def validate_ohlc(self) -> List[str]:
        """Validate OHLC relationships. Returns list of errors."""
        errors = []
        for idx, row in self.df.iterrows():
            if row['high'] < row['low']:
                errors.append(f"{idx}: High < Low")
            if row['open'] > row['high'] or row['open'] < row['low']:
                errors.append(f"{idx}: Open outside High-Low")
            if row['close'] > row['high'] or row['close'] < row['low']:
                errors.append(f"{idx}: Close outside High-Low")
        return errors


@dataclass
class FeatureVector:
    """
    Computed feature vector for a single observation.

    Contains feature values with metadata for reproducibility.
    """
    symbol: Symbol
    timestamp: datetime
    features: Dict[str, float]
    feature_names: List[str]
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Ensure feature_names matches features."""
        if not self.feature_names:
            self.feature_names = list(self.features.keys())

    @property
    def values(self) -> np.ndarray:
        """Get feature values as numpy array."""
        return np.array([self.features.get(name, 0.0) for name in self.feature_names])

    @property
    def hash(self) -> str:
        """Get reproducible hash of feature configuration."""
        feature_str = json.dumps({
            'names': sorted(self.feature_names),
            'values': [round(v, 6) for v in self.values]
        }, sort_keys=True)
        return hashlib.sha256(feature_str.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'features': self.features,
            'hash': self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureVector':
        """Create from dictionary."""
        return cls(
            symbol=Symbol(data['symbol']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            features=data['features'],
            feature_names=list(data['features'].keys()),
        )


@dataclass
class Prediction:
    """
    Model prediction output.

    Contains direction, strength, confidence, and metadata.
    """
    direction: Direction
    strength: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    model_id: ModelId
    probabilities: Optional[Dict[Direction, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate ranges."""
        if not -1.0 <= self.strength <= 1.0:
            raise ValueError(f"Strength must be in [-1, 1], got {self.strength}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")

    @property
    def is_actionable(self) -> bool:
        """Check if prediction is strong enough to act on."""
        return self.confidence >= 0.6 and abs(self.strength) >= 0.3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'direction': self.direction.value,
            'strength': self.strength,
            'confidence': self.confidence,
            'model_id': self.model_id,
            'probabilities': {k.value: v for k, v in (self.probabilities or {}).items()},
            'metadata': self.metadata,
        }


@dataclass
class Signal:
    """
    Trading signal with full context.

    Generated by SignalGenerator, consumed by Executor.
    """
    symbol: Symbol
    timestamp: datetime
    signal_type: SignalType
    direction: Direction
    strength: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    features_hash: str
    model_id: ModelId

    # Optional context
    regime: Optional[Regime] = None
    strategy_id: Optional[StrategyId] = None
    run_id: Optional[RunId] = None

    # Explanation
    explanation: Dict[str, Any] = field(default_factory=dict)
    top_features: List[Dict[str, Any]] = field(default_factory=list)

    # Position sizing suggestions
    suggested_size_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'signal_type': self.signal_type.value,
            'direction': self.direction.value,
            'strength': self.strength,
            'confidence': self.confidence,
            'features_hash': self.features_hash,
            'model_id': self.model_id,
            'regime': self.regime.value if self.regime else None,
            'strategy_id': self.strategy_id,
            'explanation': self.explanation,
            'top_features': self.top_features,
        }


@dataclass
class ExecutionResult:
    """
    Result of order execution.

    Contains fill information and execution quality metrics.
    """
    order_id: str
    symbol: Symbol
    direction: Direction
    requested_qty: float
    filled_qty: float
    average_price: float
    executed_at: datetime

    # Execution quality
    slippage_bps: Optional[float] = None
    commission: float = 0.0
    expected_price: Optional[float] = None

    # Status
    is_complete: bool = True
    is_rejected: bool = False
    rejection_reason: Optional[str] = None

    @property
    def fill_rate(self) -> float:
        """Calculate fill rate."""
        if self.requested_qty == 0:
            return 0.0
        return self.filled_qty / self.requested_qty

    @property
    def total_value(self) -> float:
        """Calculate total execution value."""
        return self.filled_qty * self.average_price

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'direction': self.direction.value,
            'requested_qty': self.requested_qty,
            'filled_qty': self.filled_qty,
            'average_price': self.average_price,
            'executed_at': self.executed_at.isoformat(),
            'slippage_bps': self.slippage_bps,
            'commission': self.commission,
            'fill_rate': self.fill_rate,
        }


@dataclass
class RiskAssessment:
    """
    Result of pre-trade risk check.

    Indicates whether a trade is approved and any adjustments.
    """
    is_approved: bool
    original_size: float
    adjusted_size: float

    # Risk metrics
    risk_score: float  # 0-100, higher = riskier
    breached_limits: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Recommendations
    recommended_size: Optional[float] = None
    recommended_stop_loss: Optional[float] = None
    recommended_take_profit: Optional[float] = None

    @property
    def was_adjusted(self) -> bool:
        """Check if size was adjusted."""
        return self.adjusted_size != self.original_size

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'is_approved': self.is_approved,
            'original_size': self.original_size,
            'adjusted_size': self.adjusted_size,
            'risk_score': self.risk_score,
            'breached_limits': self.breached_limits,
            'warnings': self.warnings,
        }


@dataclass
class PortfolioSnapshot:
    """
    Point-in-time portfolio state.

    Used for performance tracking and risk monitoring.
    """
    timestamp: datetime
    cash: float
    equity: float
    buying_power: float
    positions: Dict[Symbol, float]  # symbol -> quantity

    # Calculated metrics
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    total_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def __post_init__(self):
        """Calculate exposures if not set."""
        if self.gross_exposure == 0 and self.positions:
            self.gross_exposure = sum(abs(v) for v in self.positions.values())
            self.net_exposure = sum(self.positions.values())

    @property
    def position_count(self) -> int:
        """Count non-zero positions."""
        return sum(1 for v in self.positions.values() if v != 0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'cash': self.cash,
            'equity': self.equity,
            'buying_power': self.buying_power,
            'positions': {str(k): v for k, v in self.positions.items()},
            'gross_exposure': self.gross_exposure,
            'net_exposure': self.net_exposure,
            'total_pnl': self.total_pnl,
        }


@dataclass
class PerformanceMetrics:
    """
    Performance metrics over a period.

    Used for strategy evaluation and model assessment.
    """
    period_start: datetime
    period_end: datetime

    # Returns
    total_return: float
    annualized_return: float

    # Risk metrics
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    current_drawdown: float

    # Trade stats
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float

    # Exposure
    avg_gross_exposure: float
    avg_net_exposure: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': self.max_drawdown,
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
        }
