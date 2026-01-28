"""
QUANT INDUSTRY - Prop Firm Compliance Risk Engine
Institutional-Grade Risk Management for Prop Firm Trading

Features:
- Daily drawdown monitoring (5% limit)
- Total drawdown monitoring (10% limit)
- Profit target tracking (8-10%)
- Position sizing limits
- Consistency monitoring
- Auto-stop on limit breach
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classifications"""
    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"
    BREACH = "breach"


class TradingStatus(Enum):
    """Trading status"""
    ACTIVE = "active"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    DAILY_LIMIT_REACHED = "daily_limit_reached"
    TOTAL_LIMIT_REACHED = "total_limit_reached"
    PROFIT_TARGET_MET = "profit_target_met"


@dataclass
class PropFirmConfig:
    """Prop Firm Trading Configuration"""
    # Account info
    initial_balance: float = 100000.0
    account_type: str = "challenge"  # challenge, funded, evaluation

    # Drawdown limits
    max_daily_drawdown_pct: float = 0.05  # 5%
    max_total_drawdown_pct: float = 0.10  # 10%
    trailing_drawdown: bool = False  # Some firms use trailing

    # Profit targets
    profit_target_pct: float = 0.08  # 8%
    profit_target_phase1: float = 0.08  # Challenge phase 1
    profit_target_phase2: float = 0.05  # Challenge phase 2

    # Time constraints
    min_trading_days: int = 5
    max_trading_days: int = 30

    # Position limits
    max_position_size_pct: float = 0.10  # 10% per position
    max_positions: int = 5
    max_lot_size: float = 10.0

    # Risk per trade
    max_risk_per_trade_pct: float = 0.01  # 1%

    # Consistency rules
    consistency_target_pct: float = 0.30  # Max 30% profit from single day

    # Warning thresholds
    daily_dd_warning_pct: float = 0.03  # 3% - warning
    daily_dd_critical_pct: float = 0.04  # 4% - critical
    total_dd_warning_pct: float = 0.06  # 6% - warning
    total_dd_critical_pct: float = 0.08  # 8% - critical


@dataclass
class RiskState:
    """Current risk state"""
    timestamp: datetime
    account_balance: float
    daily_pnl: float
    daily_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    current_drawdown_pct: float
    daily_drawdown_pct: float
    max_drawdown_pct: float
    high_water_mark: float
    risk_level: RiskLevel
    trading_status: TradingStatus
    open_positions: int
    position_value: float

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'account_balance': round(self.account_balance, 2),
            'daily_pnl': round(self.daily_pnl, 2),
            'daily_pnl_pct': round(self.daily_pnl_pct * 100, 2),
            'total_pnl': round(self.total_pnl, 2),
            'total_pnl_pct': round(self.total_pnl_pct * 100, 2),
            'current_drawdown_pct': round(self.current_drawdown_pct * 100, 2),
            'daily_drawdown_pct': round(self.daily_drawdown_pct * 100, 2),
            'max_drawdown_pct': round(self.max_drawdown_pct * 100, 2),
            'high_water_mark': round(self.high_water_mark, 2),
            'risk_level': self.risk_level.value,
            'trading_status': self.trading_status.value,
            'open_positions': self.open_positions,
            'position_value': round(self.position_value, 2)
        }


@dataclass
class TradeRecord:
    """Trade record for compliance tracking"""
    trade_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    entry_price: float
    exit_price: Optional[float]
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl: float
    pnl_pct: float
    status: str  # 'open', 'closed', 'cancelled'


class PropFirmRiskEngine:
    """
    Prop Firm Compliance Risk Engine
    Monitors and enforces prop firm trading rules
    """

    def __init__(self, config: Optional[PropFirmConfig] = None):
        self.config = config or PropFirmConfig()

        # Account state
        self.initial_balance = self.config.initial_balance
        self.current_balance = self.config.initial_balance
        self.high_water_mark = self.config.initial_balance

        # Daily tracking
        self.daily_start_balance = self.config.initial_balance
        self.daily_high = self.config.initial_balance
        self.daily_low = self.config.initial_balance
        self.last_daily_reset = date.today()

        # Position tracking
        self.open_positions: Dict[str, TradeRecord] = {}
        self.trade_history: List[TradeRecord] = []
        self.daily_trades: List[TradeRecord] = []

        # Performance tracking
        self.daily_pnl_history: Dict[date, float] = {}
        self.trading_days: int = 0

        # Status
        self.trading_status = TradingStatus.ACTIVE
        self.risk_level = RiskLevel.SAFE

        # Database
        self.db_path = Path("data/propfirm_risk.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Callbacks
        self.on_risk_breach: Optional[Callable] = None
        self.on_status_change: Optional[Callable] = None

        logger.info("PropFirm Risk Engine initialized")
        logger.info(f"  Initial balance: ${self.initial_balance:,.2f}")
        logger.info(f"  Max daily DD: {self.config.max_daily_drawdown_pct:.1%}")
        logger.info(f"  Max total DD: {self.config.max_total_drawdown_pct:.1%}")
        logger.info(f"  Profit target: {self.config.profit_target_pct:.1%}")

    def _init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS risk_snapshots (
                timestamp TEXT PRIMARY KEY,
                account_balance REAL,
                daily_pnl REAL,
                daily_pnl_pct REAL,
                total_pnl REAL,
                total_pnl_pct REAL,
                current_drawdown_pct REAL,
                daily_drawdown_pct REAL,
                high_water_mark REAL,
                risk_level TEXT,
                trading_status TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_records (
                trade_id TEXT PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                entry_price REAL,
                exit_price REAL,
                entry_time TEXT,
                exit_time TEXT,
                pnl REAL,
                pnl_pct REAL,
                status TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_summary (
                date TEXT PRIMARY KEY,
                starting_balance REAL,
                ending_balance REAL,
                pnl REAL,
                pnl_pct REAL,
                max_drawdown REAL,
                n_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER
            )
        ''')

        conn.commit()
        conn.close()

    def update_balance(self, new_balance: float):
        """Update account balance and check limits"""
        # Check for new day
        self._check_daily_reset()

        old_balance = self.current_balance
        self.current_balance = new_balance

        # Update high water mark
        self.high_water_mark = max(self.high_water_mark, new_balance)

        # Update daily tracking
        self.daily_high = max(self.daily_high, new_balance)
        self.daily_low = min(self.daily_low, new_balance)

        # Check all risk limits
        self._check_risk_limits()

        # Save snapshot
        self._save_snapshot()

    def check_trade_allowed(self, symbol: str, side: str, quantity: float,
                           price: float) -> Tuple[bool, str]:
        """
        Check if a trade is allowed based on risk limits

        Returns:
            Tuple of (allowed, reason)
        """
        # Check trading status
        if self.trading_status != TradingStatus.ACTIVE:
            return False, f"Trading is {self.trading_status.value}"

        # Check position limits
        if len(self.open_positions) >= self.config.max_positions:
            if symbol not in self.open_positions:
                return False, f"Max positions ({self.config.max_positions}) reached"

        # Check position size
        trade_value = quantity * price
        position_size_pct = trade_value / self.current_balance
        if position_size_pct > self.config.max_position_size_pct:
            return False, f"Position size {position_size_pct:.1%} exceeds limit {self.config.max_position_size_pct:.1%}"

        # Check total exposure
        total_exposure = sum(
            t.quantity * t.entry_price for t in self.open_positions.values()
        ) + trade_value
        total_exposure_pct = total_exposure / self.current_balance
        if total_exposure_pct > 0.5:  # Max 50% total exposure
            return False, f"Total exposure {total_exposure_pct:.1%} exceeds 50%"

        # Check lot size
        if quantity > self.config.max_lot_size:
            return False, f"Lot size {quantity} exceeds max {self.config.max_lot_size}"

        # Check risk level
        if self.risk_level == RiskLevel.CRITICAL:
            return False, "Risk level is CRITICAL - reduce exposure first"

        return True, "Trade allowed"

    def record_trade_open(self, trade_id: str, symbol: str, side: str,
                         quantity: float, entry_price: float) -> bool:
        """Record opening of a trade"""
        if trade_id in self.open_positions:
            logger.warning(f"Trade {trade_id} already exists")
            return False

        trade = TradeRecord(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=None,
            entry_time=datetime.now(),
            exit_time=None,
            pnl=0,
            pnl_pct=0,
            status='open'
        )

        self.open_positions[trade_id] = trade
        self._save_trade(trade)

        logger.info(f"Trade opened: {trade_id} - {side.upper()} {quantity} {symbol} @ ${entry_price:.2f}")
        return True

    def record_trade_close(self, trade_id: str, exit_price: float) -> Optional[float]:
        """Record closing of a trade, returns PnL"""
        if trade_id not in self.open_positions:
            logger.warning(f"Trade {trade_id} not found")
            return None

        trade = self.open_positions[trade_id]
        trade.exit_price = exit_price
        trade.exit_time = datetime.now()

        # Calculate PnL
        if trade.side == 'buy':
            trade.pnl = (exit_price - trade.entry_price) * trade.quantity
        else:
            trade.pnl = (trade.entry_price - exit_price) * trade.quantity

        trade.pnl_pct = trade.pnl / (trade.entry_price * trade.quantity)
        trade.status = 'closed'

        # Move to history
        del self.open_positions[trade_id]
        self.trade_history.append(trade)
        self.daily_trades.append(trade)

        # Update balance
        self.current_balance += trade.pnl
        self.update_balance(self.current_balance)

        # Save trade
        self._save_trade(trade)

        logger.info(f"Trade closed: {trade_id} - PnL: ${trade.pnl:.2f} ({trade.pnl_pct:.2%})")
        return trade.pnl

    def _check_daily_reset(self):
        """Check if we need to reset daily tracking"""
        today = date.today()
        if today != self.last_daily_reset:
            # Save yesterday's summary
            self._save_daily_summary()

            # Reset daily tracking
            self.daily_start_balance = self.current_balance
            self.daily_high = self.current_balance
            self.daily_low = self.current_balance
            self.daily_trades = []
            self.last_daily_reset = today
            self.trading_days += 1

            # Reset trading status if it was daily limit
            if self.trading_status == TradingStatus.DAILY_LIMIT_REACHED:
                self.trading_status = TradingStatus.ACTIVE
                logger.info("Daily limit reset - trading resumed")

    def _check_risk_limits(self):
        """Check all risk limits and update status"""
        old_status = self.trading_status
        old_risk_level = self.risk_level

        # Calculate metrics
        daily_pnl = self.current_balance - self.daily_start_balance
        daily_pnl_pct = daily_pnl / self.daily_start_balance

        total_pnl = self.current_balance - self.initial_balance
        total_pnl_pct = total_pnl / self.initial_balance

        # Calculate drawdowns
        daily_dd_pct = (self.daily_high - self.current_balance) / self.daily_high if self.daily_high > 0 else 0

        if self.config.trailing_drawdown:
            total_dd_pct = (self.high_water_mark - self.current_balance) / self.high_water_mark
        else:
            total_dd_pct = (self.initial_balance - self.current_balance) / self.initial_balance if total_pnl < 0 else 0

        # Check daily drawdown limit
        if daily_dd_pct >= self.config.max_daily_drawdown_pct:
            self.trading_status = TradingStatus.DAILY_LIMIT_REACHED
            self.risk_level = RiskLevel.BREACH
            logger.critical(f"DAILY DRAWDOWN LIMIT BREACHED: {daily_dd_pct:.2%}")
            if self.on_risk_breach:
                self.on_risk_breach('daily_drawdown', daily_dd_pct)

        # Check total drawdown limit
        elif total_dd_pct >= self.config.max_total_drawdown_pct:
            self.trading_status = TradingStatus.TOTAL_LIMIT_REACHED
            self.risk_level = RiskLevel.BREACH
            logger.critical(f"TOTAL DRAWDOWN LIMIT BREACHED: {total_dd_pct:.2%}")
            if self.on_risk_breach:
                self.on_risk_breach('total_drawdown', total_dd_pct)

        # Check profit target
        elif total_pnl_pct >= self.config.profit_target_pct:
            self.trading_status = TradingStatus.PROFIT_TARGET_MET
            self.risk_level = RiskLevel.SAFE
            logger.info(f"PROFIT TARGET MET: {total_pnl_pct:.2%}")

        # Update risk level
        elif self.trading_status == TradingStatus.ACTIVE:
            if daily_dd_pct >= self.config.daily_dd_critical_pct or \
               total_dd_pct >= self.config.total_dd_critical_pct:
                self.risk_level = RiskLevel.CRITICAL
            elif daily_dd_pct >= self.config.daily_dd_warning_pct or \
                 total_dd_pct >= self.config.total_dd_warning_pct:
                self.risk_level = RiskLevel.WARNING
            elif daily_dd_pct > 0.01 or total_dd_pct > 0.02:
                self.risk_level = RiskLevel.CAUTION
            else:
                self.risk_level = RiskLevel.SAFE

        # Notify on status change
        if old_status != self.trading_status or old_risk_level != self.risk_level:
            if self.on_status_change:
                self.on_status_change(old_status, self.trading_status, old_risk_level, self.risk_level)

    def get_risk_state(self) -> RiskState:
        """Get current risk state"""
        daily_pnl = self.current_balance - self.daily_start_balance
        daily_pnl_pct = daily_pnl / self.daily_start_balance if self.daily_start_balance > 0 else 0

        total_pnl = self.current_balance - self.initial_balance
        total_pnl_pct = total_pnl / self.initial_balance

        daily_dd_pct = (self.daily_high - self.current_balance) / self.daily_high if self.daily_high > 0 else 0

        if self.config.trailing_drawdown:
            current_dd_pct = (self.high_water_mark - self.current_balance) / self.high_water_mark
        else:
            current_dd_pct = (self.initial_balance - self.current_balance) / self.initial_balance if total_pnl < 0 else 0

        max_dd_pct = max(
            (self.high_water_mark - self.current_balance) / self.high_water_mark if self.high_water_mark > 0 else 0,
            0
        )

        position_value = sum(
            t.quantity * t.entry_price for t in self.open_positions.values()
        )

        return RiskState(
            timestamp=datetime.now(),
            account_balance=self.current_balance,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            current_drawdown_pct=current_dd_pct,
            daily_drawdown_pct=daily_dd_pct,
            max_drawdown_pct=max_dd_pct,
            high_water_mark=self.high_water_mark,
            risk_level=self.risk_level,
            trading_status=self.trading_status,
            open_positions=len(self.open_positions),
            position_value=position_value
        )

    def get_position_size_recommendation(self, symbol: str, entry_price: float,
                                        stop_loss_price: float) -> float:
        """Calculate recommended position size based on risk limits"""
        # Risk per trade
        risk_amount = self.current_balance * self.config.max_risk_per_trade_pct

        # Calculate stop distance
        stop_distance = abs(entry_price - stop_loss_price)
        if stop_distance == 0:
            return 0

        # Position size for 1% risk
        position_size = risk_amount / stop_distance

        # Apply position size limit
        max_position_value = self.current_balance * self.config.max_position_size_pct
        max_shares = max_position_value / entry_price

        # Apply lot size limit
        position_size = min(position_size, max_shares, self.config.max_lot_size)

        # Adjust for current risk level
        risk_adjustments = {
            RiskLevel.SAFE: 1.0,
            RiskLevel.CAUTION: 0.8,
            RiskLevel.WARNING: 0.5,
            RiskLevel.CRITICAL: 0.25,
            RiskLevel.BREACH: 0.0
        }
        position_size *= risk_adjustments.get(self.risk_level, 1.0)

        return max(0, int(position_size))

    def get_daily_summary(self) -> Dict:
        """Get today's trading summary"""
        daily_pnl = self.current_balance - self.daily_start_balance
        winning_trades = [t for t in self.daily_trades if t.pnl > 0]
        losing_trades = [t for t in self.daily_trades if t.pnl < 0]

        return {
            'date': date.today().isoformat(),
            'starting_balance': self.daily_start_balance,
            'current_balance': self.current_balance,
            'pnl': daily_pnl,
            'pnl_pct': daily_pnl / self.daily_start_balance if self.daily_start_balance > 0 else 0,
            'n_trades': len(self.daily_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(self.daily_trades) if self.daily_trades else 0,
            'daily_high': self.daily_high,
            'daily_low': self.daily_low,
            'max_daily_dd': (self.daily_high - self.daily_low) / self.daily_high if self.daily_high > 0 else 0
        }

    def get_performance_summary(self) -> Dict:
        """Get overall performance summary"""
        total_pnl = self.current_balance - self.initial_balance
        all_trades = self.trade_history + list(self.open_positions.values())
        closed_trades = [t for t in all_trades if t.status == 'closed']
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl < 0]

        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0

        # Check consistency
        daily_profits = list(self.daily_pnl_history.values())
        max_single_day = max(daily_profits) if daily_profits else 0
        consistency_ratio = max_single_day / total_pnl if total_pnl > 0 else 0

        return {
            'initial_balance': self.initial_balance,
            'current_balance': self.current_balance,
            'total_pnl': total_pnl,
            'total_return_pct': total_pnl / self.initial_balance,
            'high_water_mark': self.high_water_mark,
            'max_drawdown_pct': (self.high_water_mark - min(self.current_balance, self.initial_balance)) / self.high_water_mark if self.high_water_mark > 0 else 0,
            'total_trades': len(closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(closed_trades) if closed_trades else 0,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in losing_trades)) if losing_trades else float('inf'),
            'trading_days': self.trading_days,
            'consistency_ratio': consistency_ratio,
            'meets_consistency': consistency_ratio <= self.config.consistency_target_pct,
            'profit_target_met': total_pnl / self.initial_balance >= self.config.profit_target_pct,
            'risk_level': self.risk_level.value,
            'trading_status': self.trading_status.value
        }

    def _save_snapshot(self):
        """Save risk snapshot to database"""
        state = self.get_risk_state()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO risk_snapshots
                (timestamp, account_balance, daily_pnl, daily_pnl_pct, total_pnl,
                 total_pnl_pct, current_drawdown_pct, daily_drawdown_pct,
                 high_water_mark, risk_level, trading_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                state.timestamp.isoformat(),
                state.account_balance,
                state.daily_pnl,
                state.daily_pnl_pct,
                state.total_pnl,
                state.total_pnl_pct,
                state.current_drawdown_pct,
                state.daily_drawdown_pct,
                state.high_water_mark,
                state.risk_level.value,
                state.trading_status.value
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")

    def _save_trade(self, trade: TradeRecord):
        """Save trade record to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO trade_records
                (trade_id, symbol, side, quantity, entry_price, exit_price,
                 entry_time, exit_time, pnl, pnl_pct, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade.trade_id,
                trade.symbol,
                trade.side,
                trade.quantity,
                trade.entry_price,
                trade.exit_price,
                trade.entry_time.isoformat() if trade.entry_time else None,
                trade.exit_time.isoformat() if trade.exit_time else None,
                trade.pnl,
                trade.pnl_pct,
                trade.status
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving trade: {e}")

    def _save_daily_summary(self):
        """Save daily summary to database"""
        summary = self.get_daily_summary()
        self.daily_pnl_history[self.last_daily_reset] = summary['pnl']

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO daily_summary
                (date, starting_balance, ending_balance, pnl, pnl_pct,
                 max_drawdown, n_trades, winning_trades, losing_trades)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.last_daily_reset.isoformat(),
                summary['starting_balance'],
                summary['current_balance'],
                summary['pnl'],
                summary['pnl_pct'],
                summary['max_daily_dd'],
                summary['n_trades'],
                summary['winning_trades'],
                summary['losing_trades']
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving daily summary: {e}")


# Singleton instance
_propfirm_risk_engine: Optional[PropFirmRiskEngine] = None


def get_propfirm_risk_engine(config: Optional[PropFirmConfig] = None) -> PropFirmRiskEngine:
    """Get or create PropFirm Risk Engine singleton"""
    global _propfirm_risk_engine
    if _propfirm_risk_engine is None:
        _propfirm_risk_engine = PropFirmRiskEngine(config)
    return _propfirm_risk_engine
