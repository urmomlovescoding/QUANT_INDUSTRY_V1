"""
Portfolio Contract
==================
Canonical interface for portfolio state.

This is the SINGLE SOURCE OF TRUTH for:
- Current positions
- Holdings
- P&L tracking
- Equity curves
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Any


@dataclass
class Position:
    """Single position in portfolio."""
    symbol: str
    quantity: int  # Positive = long, negative = short
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float = 0.0

    # Metadata
    opened_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    @property
    def cost_basis(self) -> float:
        return abs(self.quantity) * self.avg_cost

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "is_long": self.is_long,
            "cost_basis": self.cost_basis,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class Holdings:
    """Cash and securities holdings."""
    cash: float
    buying_power: float
    equity: float
    positions: Dict[str, Position] = field(default_factory=dict)

    @property
    def total_market_value(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def total_realized_pnl(self) -> float:
        return sum(p.realized_pnl for p in self.positions.values())

    @property
    def position_count(self) -> int:
        return len(self.positions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cash": self.cash,
            "buying_power": self.buying_power,
            "equity": self.equity,
            "total_market_value": self.total_market_value,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "total_realized_pnl": self.total_realized_pnl,
            "position_count": self.position_count,
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
        }


@dataclass
class PortfolioSnapshot:
    """Point-in-time portfolio snapshot."""
    timestamp: datetime
    equity: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    realized_pnl: float
    day_pnl: float
    day_pnl_pct: float

    # Risk metrics
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    leverage: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": self.equity,
            "cash": self.cash,
            "positions_value": self.positions_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "day_pnl": self.day_pnl,
            "day_pnl_pct": self.day_pnl_pct,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "leverage": self.leverage,
        }


class PortfolioContract(ABC):
    """
    Portfolio Service Contract.

    All implementations MUST:
    1. Provide accurate real-time position data
    2. Track P&L correctly
    3. Update SafetyGuard with equity changes
    4. Maintain audit trail of changes
    """

    @abstractmethod
    def get_holdings(self) -> Holdings:
        """Get current holdings."""
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol."""
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """Get all positions."""
        pass

    @abstractmethod
    def get_equity(self) -> float:
        """Get current equity value."""
        pass

    @abstractmethod
    def get_cash(self) -> float:
        """Get available cash."""
        pass

    @abstractmethod
    def get_day_pnl(self) -> float:
        """Get today's P&L."""
        pass

    @abstractmethod
    def get_snapshot(self) -> PortfolioSnapshot:
        """Get current portfolio snapshot."""
        pass

    @abstractmethod
    def get_history(
        self,
        start_date: date,
        end_date: Optional[date] = None
    ) -> List[PortfolioSnapshot]:
        """Get historical snapshots."""
        pass

    @abstractmethod
    def record_fill(
        self,
        symbol: str,
        quantity: int,
        price: float,
        side: str,
        order_id: str
    ) -> None:
        """
        Record a fill and update positions.

        MUST:
        1. Update position
        2. Calculate realized P&L if closing
        3. Update SafetyGuard equity
        4. Trigger feedback loop
        """
        pass

    @abstractmethod
    def sync_with_broker(self) -> bool:
        """
        Sync portfolio state with broker.

        Returns True if sync successful.
        """
        pass
