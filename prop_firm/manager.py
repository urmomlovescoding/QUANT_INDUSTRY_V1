"""
QUANT_INDUSTRY_V1 Prop Firm Manager

Central management for prop firm trading operations.
Coordinates rules, consistency monitoring, and position sizing.
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from prop_firm.rules import (
    PropFirmRules, AccountConfig, EvaluationTracker,
    PropFirm, TPT_ACCOUNTS, APEX_ACCOUNTS, FTMO_ACCOUNTS
)

logger = logging.getLogger(__name__)


@dataclass
class TradeRequest:
    """Trade request for prop firm validation."""
    symbol: str
    direction: str  # 'long' or 'short'
    size: int
    entry_price: float
    stop_loss: float
    take_profit: float = None
    signal_confidence: float = 0.5


@dataclass
class TradeResponse:
    """Response from trade validation."""
    approved: bool
    adjusted_size: int
    max_loss: float
    max_profit: float
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    risk_score: float = 0.0


class PropFirmManager:
    """
    Prop Firm Trading Manager.

    Coordinates:
    - Rule enforcement
    - Dynamic position sizing
    - Risk-adjusted trading
    - Performance tracking
    """

    def __init__(
        self,
        firm: PropFirm = PropFirm.TPT,
        account_tier: str = "50K",
        custom_config: AccountConfig = None,
    ):
        # Initialize account config
        if custom_config:
            self.config = custom_config
        else:
            configs = {
                PropFirm.TPT: TPT_ACCOUNTS,
                PropFirm.APEX: APEX_ACCOUNTS,
                PropFirm.FTMO: FTMO_ACCOUNTS,
            }
            firm_configs = configs.get(firm, TPT_ACCOUNTS)
            self.config = firm_configs.get(account_tier, list(firm_configs.values())[0])

        # Initialize rules engine
        self.rules = PropFirmRules(self.config)

        # Position tracking
        self.open_positions: Dict[str, Dict] = {}
        self.position_pnl: Dict[str, float] = {}

        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_volume = 0

        # Risk parameters
        self.max_risk_per_trade = 0.01  # 1% of account
        self.atr_stop_multiplier = 2.0
        self.min_reward_risk = 1.5

    def validate_trade(self, request: TradeRequest) -> TradeResponse:
        """
        Validate and potentially adjust a trade request.
        """
        # Calculate potential loss/profit
        if request.direction == 'long':
            potential_loss = (request.entry_price - request.stop_loss) * request.size
            potential_profit = (request.take_profit - request.entry_price) * request.size if request.take_profit else potential_loss * 2
        else:
            potential_loss = (request.stop_loss - request.entry_price) * request.size
            potential_profit = (request.entry_price - request.take_profit) * request.size if request.take_profit else potential_loss * 2

        # Validate with rules engine
        validation = self.rules.validate_trade(
            direction=request.direction,
            size=request.size,
            potential_loss=potential_loss,
            potential_profit=potential_profit,
        )

        # Calculate risk-adjusted size
        optimal_size = self._calculate_optimal_size(
            request.entry_price,
            request.stop_loss,
            request.signal_confidence,
        )

        # Use minimum of requested, rules-adjusted, and optimal
        final_size = min(request.size, validation['adjusted_size'], optimal_size)

        # Recalculate with final size
        if request.direction == 'long':
            max_loss = (request.entry_price - request.stop_loss) * final_size
            max_profit = (request.take_profit - request.entry_price) * final_size if request.take_profit else max_loss * 2
        else:
            max_loss = (request.stop_loss - request.entry_price) * final_size
            max_profit = (request.entry_price - request.take_profit) * final_size if request.take_profit else max_loss * 2

        return TradeResponse(
            approved=validation['allowed'] and final_size > 0,
            adjusted_size=final_size,
            max_loss=max_loss,
            max_profit=max_profit,
            warnings=validation['warnings'],
            errors=validation['errors'],
            risk_score=self.rules.get_risk_metrics()['risk_score'],
        )

    def _calculate_optimal_size(
        self,
        entry_price: float,
        stop_loss: float,
        confidence: float,
    ) -> int:
        """Calculate optimal position size based on risk parameters."""
        # Risk amount
        max_risk = self.rules.current_balance * self.max_risk_per_trade

        # Adjust for confidence
        adjusted_risk = max_risk * min(1.0, confidence * 1.2)

        # Calculate size
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            return 0

        optimal_size = int(adjusted_risk / risk_per_unit)

        # Apply scaling plan limits
        max_allowed = self.rules._get_scaled_position_limit()

        return min(optimal_size, max_allowed)

    def open_position(
        self,
        symbol: str,
        direction: str,
        size: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float = None,
    ) -> bool:
        """Open a new position."""
        if symbol in self.open_positions:
            logger.warning(f"Position already exists for {symbol}")
            return False

        self.open_positions[symbol] = {
            'direction': direction,
            'size': size,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'opened_at': datetime.now(timezone.utc),
            'unrealized_pnl': 0.0,
        }

        self.position_pnl[symbol] = 0.0
        self.total_volume += size

        logger.info(f"Opened {direction} position: {size} {symbol} @ {entry_price}")
        return True

    def update_position(self, symbol: str, current_price: float) -> float:
        """Update position with current price and return unrealized PnL."""
        if symbol not in self.open_positions:
            return 0.0

        pos = self.open_positions[symbol]

        if pos['direction'] == 'long':
            pnl = (current_price - pos['entry_price']) * pos['size']
        else:
            pnl = (pos['entry_price'] - current_price) * pos['size']

        pos['unrealized_pnl'] = pnl
        self.position_pnl[symbol] = pnl

        return pnl

    def close_position(self, symbol: str, exit_price: float) -> Optional[float]:
        """Close a position and record the trade."""
        if symbol not in self.open_positions:
            return None

        pos = self.open_positions[symbol]

        # Calculate final PnL
        if pos['direction'] == 'long':
            pnl = (exit_price - pos['entry_price']) * pos['size']
        else:
            pnl = (pos['entry_price'] - exit_price) * pos['size']

        # Record with rules engine
        self.rules.record_trade(pnl)

        # Update statistics
        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Remove position
        del self.open_positions[symbol]
        del self.position_pnl[symbol]

        logger.info(f"Closed position: {symbol} with PnL ${pnl:.2f}")
        return pnl

    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """Check if stop loss was hit."""
        if symbol not in self.open_positions:
            return False

        pos = self.open_positions[symbol]

        if pos['direction'] == 'long':
            return current_price <= pos['stop_loss']
        else:
            return current_price >= pos['stop_loss']

    def check_take_profit(self, symbol: str, current_price: float) -> bool:
        """Check if take profit was hit."""
        if symbol not in self.open_positions:
            return False

        pos = self.open_positions[symbol]

        if pos['take_profit'] is None:
            return False

        if pos['direction'] == 'long':
            return current_price >= pos['take_profit']
        else:
            return current_price <= pos['take_profit']

    def get_exposure(self) -> Dict[str, float]:
        """Get current exposure metrics."""
        total_long = 0
        total_short = 0
        total_unrealized = 0

        for symbol, pos in self.open_positions.items():
            notional = pos['entry_price'] * pos['size']
            unrealized = pos['unrealized_pnl']
            total_unrealized += unrealized

            if pos['direction'] == 'long':
                total_long += notional
            else:
                total_short += notional

        return {
            'long_exposure': total_long,
            'short_exposure': total_short,
            'net_exposure': total_long - total_short,
            'gross_exposure': total_long + total_short,
            'unrealized_pnl': total_unrealized,
            'position_count': len(self.open_positions),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get trading statistics."""
        win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0

        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'total_volume': self.total_volume,
            'account_status': self.rules.get_status(),
            'risk_metrics': self.rules.get_risk_metrics(),
            'exposure': self.get_exposure(),
        }

    def start_new_day(self) -> None:
        """Start a new trading day."""
        self.rules.start_new_day()
        logger.info("New trading day started")

    def should_stop_trading(self) -> Tuple[bool, str]:
        """Check if trading should stop."""
        if self.rules.is_halted:
            return True, self.rules.halt_reason

        risk_metrics = self.rules.get_risk_metrics()

        # Stop if risk is too high
        if risk_metrics['risk_score'] > 80:
            return True, f"Risk score too high: {risk_metrics['risk_score']:.1f}"

        # Stop if close to daily limit
        if risk_metrics['daily_loss_used_pct'] > 90:
            return True, f"Daily loss limit nearly reached: {risk_metrics['daily_loss_used_pct']:.1f}%"

        return False, ""

    def flatten_all(self, current_prices: Dict[str, float]) -> float:
        """Flatten all positions (end of day or emergency)."""
        total_pnl = 0

        for symbol in list(self.open_positions.keys()):
            if symbol in current_prices:
                pnl = self.close_position(symbol, current_prices[symbol])
                if pnl:
                    total_pnl += pnl

        logger.info(f"Flattened all positions. Total PnL: ${total_pnl:.2f}")
        return total_pnl


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ['PropFirmManager', 'TradeRequest', 'TradeResponse']
