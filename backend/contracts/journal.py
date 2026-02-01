"""
Trade Journal Contract
======================
Canonical interface for trade journaling and attribution.

Every trade MUST be journaled for:
1. Strategy attribution
2. Performance analysis
3. Feedback loop learning
4. Audit trail
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Dict, List, Optional, Any


class TradeOutcome(Enum):
    """Trade outcome classification."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    OPEN = "open"


@dataclass
class TradeRecord:
    """
    Complete trade record.

    This captures the full lifecycle of a trade.
    """
    trade_id: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: int

    # Entry
    entry_price: float
    entry_time: datetime
    entry_order_id: str

    # Exit (None if still open)
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_order_id: Optional[str] = None

    # P&L
    realized_pnl: float = 0.0
    realized_pnl_pct: float = 0.0
    unrealized_pnl: float = 0.0

    # Execution quality
    slippage: float = 0.0
    commission: float = 0.0

    # Attribution
    strategy_id: Optional[str] = None
    signal_id: Optional[str] = None
    signal_confidence: float = 0.0

    # Risk metrics
    initial_stop_loss: Optional[float] = None
    initial_take_profit: Optional[float] = None
    max_adverse_excursion: float = 0.0  # MAE
    max_favorable_excursion: float = 0.0  # MFE

    # Metadata
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    @property
    def outcome(self) -> TradeOutcome:
        if self.exit_price is None:
            return TradeOutcome.OPEN
        if self.realized_pnl > 0:
            return TradeOutcome.WIN
        if self.realized_pnl < 0:
            return TradeOutcome.LOSS
        return TradeOutcome.BREAKEVEN

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.exit_time is None:
            return None
        return (self.exit_time - self.entry_time).total_seconds()

    @property
    def r_multiple(self) -> Optional[float]:
        """Return as multiple of initial risk."""
        if self.initial_stop_loss is None or self.exit_price is None:
            return None
        initial_risk = abs(self.entry_price - self.initial_stop_loss)
        if initial_risk == 0:
            return None
        return self.realized_pnl / (initial_risk * self.quantity)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "realized_pnl": self.realized_pnl,
            "realized_pnl_pct": self.realized_pnl_pct,
            "outcome": self.outcome.value,
            "strategy_id": self.strategy_id,
            "signal_confidence": self.signal_confidence,
            "max_adverse_excursion": self.max_adverse_excursion,
            "max_favorable_excursion": self.max_favorable_excursion,
            "r_multiple": self.r_multiple,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class JournalEntry:
    """General journal entry (not just trades)."""
    entry_id: str
    timestamp: datetime
    entry_type: str  # "trade", "signal", "risk", "system"
    category: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "entry_type": self.entry_type,
            "category": self.category,
            "message": self.message,
            "data": self.data,
        }


@dataclass
class StrategyPerformance:
    """Performance metrics for a strategy."""
    strategy_id: str
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "trade_count": self.trade_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "total_pnl": self.total_pnl,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
        }


class JournalContract(ABC):
    """
    Trade Journal Contract.

    All implementations MUST:
    1. Record every trade with full attribution
    2. Track strategy performance
    3. Support feedback loop queries
    4. Maintain audit trail
    """

    @abstractmethod
    def record_trade(self, trade: TradeRecord) -> str:
        """
        Record a trade.

        Returns trade_id.
        """
        pass

    @abstractmethod
    def update_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_time: datetime,
        exit_order_id: str
    ) -> TradeRecord:
        """
        Update trade with exit info.

        MUST:
        1. Calculate final P&L
        2. Update strategy performance
        3. Trigger feedback loop
        """
        pass

    @abstractmethod
    def get_trade(self, trade_id: str) -> Optional[TradeRecord]:
        """Get trade by ID."""
        pass

    @abstractmethod
    def get_open_trades(self) -> List[TradeRecord]:
        """Get all open trades."""
        pass

    @abstractmethod
    def get_trades(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        symbol: Optional[str] = None,
        strategy_id: Optional[str] = None,
        limit: int = 100
    ) -> List[TradeRecord]:
        """Query trades with filters."""
        pass

    @abstractmethod
    def get_strategy_performance(
        self,
        strategy_id: str,
        start_date: Optional[date] = None
    ) -> StrategyPerformance:
        """Get performance metrics for a strategy."""
        pass

    @abstractmethod
    def get_all_strategy_performance(self) -> Dict[str, StrategyPerformance]:
        """Get performance for all strategies."""
        pass

    @abstractmethod
    def log_entry(self, entry: JournalEntry) -> str:
        """Log a general journal entry."""
        pass

    @abstractmethod
    def get_entries(
        self,
        entry_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[JournalEntry]:
        """Query journal entries."""
        pass

    @abstractmethod
    def export_trades(
        self,
        start_date: date,
        end_date: date,
        format: str = "csv"
    ) -> bytes:
        """Export trades for analysis."""
        pass
