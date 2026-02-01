"""
Safety Guard - Non-Negotiable Trading Protection
=================================================
Ported from quant-platform for battle-tested safety.

These checks CANNOT be bypassed even with autonomous learning.

Safety Rules:
1. Max daily loss -> halt trading
2. Max drawdown -> halt trading
3. Volatility circuit breaker -> halt trading
4. Trade frequency limiter -> reject excess trades
5. Stale snapshot blocker -> refuse to trade
6. Live trading requires ALLOW_LIVE=true
7. Position limits -> reject oversized trades
8. Consecutive loss tracking

If safety triggers:
- Halt trading immediately
- Continue learning offline
- Require recovery validation before resuming

Author: QuantBrain (ported to QUANT_INDUSTRY_V1)
Version: 2.0.0
"""

import logging
import os
import threading
import time
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable

logger = logging.getLogger(__name__)


class SafetyStatus(Enum):
    """Safety system status."""
    NORMAL = "normal"
    WARNING = "warning"
    HALTED = "halted"
    RECOVERY = "recovery"
    OFFLINE_LEARNING = "offline_learning"


class HaltReason(Enum):
    """Reasons for halting trading."""
    MAX_DAILY_LOSS = "max_daily_loss"
    MAX_WEEKLY_LOSS = "max_weekly_loss"
    MAX_DRAWDOWN = "max_drawdown"
    VOLATILITY_SPIKE = "volatility_spike"
    TRADE_FREQUENCY = "trade_frequency"
    STALE_SNAPSHOT = "stale_snapshot"
    DATA_INTEGRITY = "data_integrity"
    MANUAL_HALT = "manual_halt"
    SYSTEM_ERROR = "system_error"
    MARKET_CIRCUIT_BREAKER = "market_circuit_breaker"
    POSITION_LIMIT = "position_limit"
    NO_VALID_MODEL = "no_valid_model"
    LIVE_NOT_ALLOWED = "live_not_allowed"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    VIX_CRISIS = "vix_crisis"


@dataclass
class SafetyEvent:
    """Record of a safety event."""
    event_id: str
    timestamp: datetime
    event_type: str  # "warning", "halt", "resume"
    reason: HaltReason
    details: str
    metrics: Dict[str, float] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'reason': self.reason.value,
            'details': self.details,
            'metrics': self.metrics,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


@dataclass
class TradingLimits:
    """
    Non-negotiable trading limits.

    These are HARD limits that cannot be bypassed by ML or any other component.
    Modify with extreme caution.
    """
    # Loss limits (as percentage of equity)
    max_daily_loss_pct: float = 0.02      # 2% max daily loss
    max_weekly_loss_pct: float = 0.05     # 5% max weekly loss
    max_drawdown_pct: float = 0.10        # 10% max drawdown from peak

    # Prop firm specific (TPT 50K)
    prop_firm_enabled: bool = True
    prop_firm_balance_floor: float = 48000.0  # $48K floor for $50K account
    prop_firm_profit_target: float = 3000.0   # $3K profit target

    # Volatility limits
    max_volatility: float = 0.50          # 50% annualized vol
    vol_spike_multiplier: float = 2.0     # 2x normal vol = warning
    vol_crisis_multiplier: float = 3.0    # 3x normal vol = halt
    vix_crisis_threshold: float = 40.0    # VIX > 40 = crisis mode

    # Frequency limits
    max_trades_per_hour: int = 20
    max_trades_per_day: int = 100
    min_trade_interval_seconds: int = 60  # 1 minute between trades

    # Position limits
    max_position_pct: float = 0.25        # 25% max single position
    max_total_exposure: float = 1.5       # 150% max gross exposure
    max_positions: int = 20
    max_contracts: int = 6                # Prop firm max contracts

    # Consecutive loss protection
    max_consecutive_losses: int = 5

    # Data freshness
    max_snapshot_age_seconds: int = 600   # 10 minutes
    max_price_age_seconds: int = 60       # 1 minute

    # Recovery requirements
    min_recovery_trades: int = 10
    min_recovery_win_rate: float = 0.5

    # Time-based rules
    flatten_time_est: str = "16:45"       # Flatten by 4:45 PM EST
    trading_cutoff_est: str = "17:00"     # No new trades after 5 PM EST


class SafetyGuard:
    """
    Non-negotiable safety system.

    This class is the FINAL arbiter of whether trading is allowed.
    Its decisions CANNOT be overridden by ML or any other component.

    Philosophy:
    - Safety rules are absolute
    - When in doubt, don't trade
    - Preserve capital above all else
    - Allow learning to continue even when trading is halted

    Usage:
        guard = get_safety_guard()
        can_trade, reason = guard.can_trade(symbol="SPY", size_pct=0.1)
        if not can_trade:
            logger.warning(f"Trade blocked: {reason}")
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Ensure singleton pattern for safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self,
                 limits: TradingLimits = None,
                 storage_path: str = None):
        """
        Initialize the safety guard.

        Args:
            limits: Trading limits (uses defaults if not provided)
            storage_path: Where to persist safety logs
        """
        # Prevent re-initialization
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.limits = limits or TradingLimits()
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), '..', '..', 'logs', 'safety'
        )
        os.makedirs(self.storage_path, exist_ok=True)

        # Current status
        self._status = SafetyStatus.NORMAL
        self._halt_reason: Optional[HaltReason] = None
        self._halt_details: str = ""
        self._halted_at: Optional[datetime] = None

        # Tracking
        self._daily_pnl: float = 0.0
        self._weekly_pnl: float = 0.0
        self._daily_date: date = date.today()
        self._week_start: date = date.today() - timedelta(days=date.today().weekday())
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._starting_equity: float = 50000.0  # Default prop firm balance

        # Trade tracking
        self._trades_today: int = 0
        self._trades_this_hour: int = 0
        self._hour_start: datetime = datetime.now()
        self._last_trade_time: Optional[datetime] = None
        self._consecutive_losses: int = 0

        # Recovery tracking
        self._recovery_trades: int = 0
        self._recovery_wins: int = 0

        # Position tracking
        self._positions: Dict[str, float] = {}
        self._total_exposure: float = 0.0
        self._total_contracts: int = 0

        # VIX tracking
        self._current_vix: float = 15.0
        self._crisis_mode: bool = False

        # Event history
        self._events: List[SafetyEvent] = []

        # Callbacks
        self._halt_callbacks: List[Callable] = []

        # Thread lock
        self._state_lock = threading.RLock()

        # Check ALLOW_LIVE on init
        self._allow_live = os.environ.get('ALLOW_LIVE', '').lower() == 'true'

        self._initialized = True

        logger.info(f"SafetyGuard initialized. ALLOW_LIVE={self._allow_live}")

        if not self._allow_live:
            logger.warning("Live trading NOT ALLOWED. Set ALLOW_LIVE=true to enable.")

    def can_trade(self,
                 symbol: str = None,
                 size_pct: float = 0,
                 contracts: int = 0,
                 is_live: bool = False) -> Tuple[bool, str]:
        """
        Check if a trade is allowed.

        This is the FINAL gate - if this returns False, do NOT trade.

        Args:
            symbol: Symbol to trade
            size_pct: Position size as % of equity
            contracts: Number of contracts (for futures)
            is_live: Whether this is live trading

        Returns:
            (allowed, reason)
        """
        with self._state_lock:
            # Check 1: Live trading permission
            if is_live and not self._allow_live:
                return False, "Live trading requires ALLOW_LIVE=true environment variable"

            # Check 2: System halted
            if self._status == SafetyStatus.HALTED:
                return False, f"Trading halted: {self._halt_reason.value} - {self._halt_details}"

            # Check 3: Recovery mode - only paper trading allowed
            if self._status == SafetyStatus.RECOVERY:
                if is_live:
                    return False, "System in recovery mode - paper trading only"

            # Check 4: Daily loss limit
            if self._current_equity > 0:
                daily_loss_pct = -self._daily_pnl / self._current_equity
                if daily_loss_pct > self.limits.max_daily_loss_pct:
                    self._trigger_halt(HaltReason.MAX_DAILY_LOSS,
                                     f"Daily loss {daily_loss_pct:.2%} exceeds limit {self.limits.max_daily_loss_pct:.2%}")
                    return False, f"Daily loss limit reached: {daily_loss_pct:.2%}"

            # Check 5: Weekly loss limit
            if self._current_equity > 0:
                weekly_loss_pct = -self._weekly_pnl / self._current_equity
                if weekly_loss_pct > self.limits.max_weekly_loss_pct:
                    self._trigger_halt(HaltReason.MAX_WEEKLY_LOSS,
                                     f"Weekly loss {weekly_loss_pct:.2%} exceeds limit {self.limits.max_weekly_loss_pct:.2%}")
                    return False, f"Weekly loss limit reached: {weekly_loss_pct:.2%}"

            # Check 6: Drawdown limit
            drawdown = self._calculate_drawdown()
            if drawdown > self.limits.max_drawdown_pct:
                self._trigger_halt(HaltReason.MAX_DRAWDOWN,
                                 f"Drawdown {drawdown:.2%} exceeds limit {self.limits.max_drawdown_pct:.2%}")
                return False, f"Max drawdown reached: {drawdown:.2%}"

            # Check 7: Prop firm balance floor
            if self.limits.prop_firm_enabled:
                if self._current_equity < self.limits.prop_firm_balance_floor:
                    self._trigger_halt(HaltReason.MAX_DRAWDOWN,
                                     f"Balance ${self._current_equity:,.0f} below floor ${self.limits.prop_firm_balance_floor:,.0f}")
                    return False, f"Prop firm balance floor breached"

            # Check 8: VIX crisis mode
            if self._current_vix > self.limits.vix_crisis_threshold:
                if not self._crisis_mode:
                    self._crisis_mode = True
                    self._log_event("warning", HaltReason.VIX_CRISIS,
                                  f"VIX at {self._current_vix:.1f} - entering crisis mode")
                    logger.warning(f"CRISIS MODE: VIX at {self._current_vix:.1f}")
                # Allow trading but with reduced size (handled by caller)

            # Check 9: Consecutive losses
            if self._consecutive_losses >= self.limits.max_consecutive_losses:
                self._trigger_halt(HaltReason.CONSECUTIVE_LOSSES,
                                 f"{self._consecutive_losses} consecutive losses")
                return False, f"Max consecutive losses ({self._consecutive_losses}) reached"

            # Check 10: Trade frequency
            self._update_trade_counts()

            if self._trades_today >= self.limits.max_trades_per_day:
                return False, f"Daily trade limit reached: {self._trades_today}/{self.limits.max_trades_per_day}"

            if self._trades_this_hour >= self.limits.max_trades_per_hour:
                return False, f"Hourly trade limit reached: {self._trades_this_hour}/{self.limits.max_trades_per_hour}"

            if self._last_trade_time:
                seconds_since_last = (datetime.now() - self._last_trade_time).total_seconds()
                if seconds_since_last < self.limits.min_trade_interval_seconds:
                    return False, f"Minimum trade interval not met: {seconds_since_last:.0f}s < {self.limits.min_trade_interval_seconds}s"

            # Check 11: Position limits
            if symbol and symbol in self._positions:
                current_size = self._positions[symbol]
                new_size = current_size + size_pct
                if abs(new_size) > self.limits.max_position_pct:
                    return False, f"Position limit exceeded: {new_size:.1%} > {self.limits.max_position_pct:.1%}"

            if len(self._positions) >= self.limits.max_positions:
                if symbol not in self._positions:
                    return False, f"Max positions reached: {len(self._positions)}/{self.limits.max_positions}"

            if self._total_exposure + abs(size_pct) > self.limits.max_total_exposure:
                return False, f"Total exposure limit: {self._total_exposure:.1%} + {size_pct:.1%}"

            # Check 12: Contract limits (for futures)
            if contracts > 0:
                if self._total_contracts + contracts > self.limits.max_contracts:
                    return False, f"Max contracts exceeded: {self._total_contracts + contracts} > {self.limits.max_contracts}"

            return True, "OK"

    def get_position_size_multiplier(self) -> float:
        """
        Get position size multiplier based on current conditions.

        Returns:
            Multiplier for position sizing (0.25-1.0)
        """
        multiplier = 1.0

        # Crisis mode = 25% size
        if self._crisis_mode:
            multiplier = 0.25
        # High volatility = 50% size
        elif self._current_vix > 30:
            multiplier = 0.5
        # Elevated volatility = 75% size
        elif self._current_vix > 25:
            multiplier = 0.75

        # Reduce further if in recovery
        if self._status == SafetyStatus.RECOVERY:
            multiplier *= 0.5

        # Reduce if consecutive losses
        if self._consecutive_losses >= 3:
            multiplier *= 0.5

        return max(0.25, multiplier)

    def validate_snapshot(self, snapshot: Any) -> Tuple[bool, str]:
        """
        Validate that a snapshot is safe to use for trading.

        Args:
            snapshot: ML snapshot to validate

        Returns:
            (valid, reason)
        """
        if snapshot is None:
            self._log_event("warning", HaltReason.NO_VALID_MODEL, "No snapshot provided")
            return False, "No snapshot provided"

        # Check expiration
        if hasattr(snapshot, 'expires_at'):
            if datetime.now() > snapshot.expires_at:
                self._log_event("warning", HaltReason.STALE_SNAPSHOT,
                              f"Snapshot expired at {snapshot.expires_at}")
                return False, f"Snapshot expired at {snapshot.expires_at}"

        # Check age
        if hasattr(snapshot, 'created_at'):
            age_seconds = (datetime.now() - snapshot.created_at).total_seconds()
            if age_seconds > self.limits.max_snapshot_age_seconds:
                self._log_event("warning", HaltReason.STALE_SNAPSHOT,
                              f"Snapshot too old: {age_seconds:.0f}s")
                return False, f"Snapshot too old: {age_seconds:.0f}s (max {self.limits.max_snapshot_age_seconds}s)"

        # Check validity flag
        if hasattr(snapshot, 'is_valid') and not snapshot.is_valid:
            return False, "Snapshot marked as invalid"

        # Check confidence
        if hasattr(snapshot, 'confidence') and snapshot.confidence < 0.3:
            return False, f"Snapshot confidence too low: {snapshot.confidence:.2f}"

        return True, "OK"

    def validate_price_data(self, timestamp: datetime) -> Tuple[bool, str]:
        """
        Validate that price data is fresh enough.

        Args:
            timestamp: Timestamp of price data

        Returns:
            (valid, reason)
        """
        if timestamp.tzinfo:
            age_seconds = (datetime.now(timestamp.tzinfo) - timestamp).total_seconds()
        else:
            age_seconds = (datetime.now() - timestamp).total_seconds()

        if age_seconds > self.limits.max_price_age_seconds:
            return False, f"Price data too stale: {age_seconds:.0f}s (max {self.limits.max_price_age_seconds}s)"

        return True, "OK"

    def record_trade(self, symbol: str, pnl: float, size_pct: float = 0, contracts: int = 0):
        """
        Record a completed trade.

        Args:
            symbol: Symbol traded
            pnl: P&L from trade (in dollars or % of equity)
            size_pct: Position size change
            contracts: Number of contracts traded
        """
        with self._state_lock:
            # Reset daily counters if new day
            today = date.today()
            if today != self._daily_date:
                self._daily_date = today
                self._daily_pnl = 0.0
                self._trades_today = 0

            # Reset weekly counters if new week
            week_start = today - timedelta(days=today.weekday())
            if week_start != self._week_start:
                self._week_start = week_start
                self._weekly_pnl = 0.0

            # Update P&L
            self._daily_pnl += pnl
            self._weekly_pnl += pnl
            self._current_equity += pnl

            # Update peak
            if self._current_equity > self._peak_equity:
                self._peak_equity = self._current_equity

            # Update consecutive losses
            if pnl < 0:
                self._consecutive_losses += 1
            else:
                self._consecutive_losses = 0

            # Update position tracking
            if symbol:
                if symbol in self._positions:
                    self._positions[symbol] += size_pct
                    if abs(self._positions[symbol]) < 0.001:
                        del self._positions[symbol]
                else:
                    if abs(size_pct) >= 0.001:
                        self._positions[symbol] = size_pct

            # Update exposure
            self._total_exposure = sum(abs(p) for p in self._positions.values())

            # Update contract count
            self._total_contracts = max(0, self._total_contracts + contracts)

            # Update trade counts
            self._trades_today += 1
            self._trades_this_hour += 1
            self._last_trade_time = datetime.now()

            # Recovery tracking
            if self._status == SafetyStatus.RECOVERY:
                self._recovery_trades += 1
                if pnl > 0:
                    self._recovery_wins += 1

                # Check if recovery complete
                if self._recovery_trades >= self.limits.min_recovery_trades:
                    win_rate = self._recovery_wins / self._recovery_trades
                    if win_rate >= self.limits.min_recovery_win_rate:
                        self._complete_recovery()

            logger.debug(f"Trade recorded: {symbol} PnL=${pnl:.2f}, Daily=${self._daily_pnl:.2f}, Equity=${self._current_equity:.2f}")

    def record_vix(self, vix: float):
        """Record current VIX level."""
        with self._state_lock:
            old_vix = self._current_vix
            self._current_vix = vix

            # Check for crisis mode entry/exit
            if vix > self.limits.vix_crisis_threshold and not self._crisis_mode:
                self._crisis_mode = True
                self._log_event("warning", HaltReason.VIX_CRISIS, f"VIX spiked to {vix:.1f}")
                logger.warning(f"CRISIS MODE ACTIVATED: VIX at {vix:.1f}")
            elif vix < self.limits.vix_crisis_threshold * 0.8 and self._crisis_mode:
                self._crisis_mode = False
                logger.info(f"Crisis mode deactivated: VIX at {vix:.1f}")

    def record_volatility(self, current_vol: float, normal_vol: float):
        """
        Record current volatility for circuit breaker check.

        Args:
            current_vol: Current volatility (annualized)
            normal_vol: Normal/baseline volatility
        """
        with self._state_lock:
            if current_vol > self.limits.max_volatility:
                self._trigger_halt(HaltReason.VOLATILITY_SPIKE,
                                 f"Volatility {current_vol:.1%} exceeds max {self.limits.max_volatility:.1%}")
                return

            if normal_vol > 0:
                vol_ratio = current_vol / normal_vol
                if vol_ratio >= self.limits.vol_crisis_multiplier:
                    self._trigger_halt(HaltReason.VOLATILITY_SPIKE,
                                     f"Volatility spike: {current_vol:.1%} = {vol_ratio:.1f}x normal")
                elif vol_ratio >= self.limits.vol_spike_multiplier:
                    self._log_event("warning", HaltReason.VOLATILITY_SPIKE,
                                  f"Elevated volatility: {current_vol:.1%} = {vol_ratio:.1f}x normal")

    def manual_halt(self, reason: str = "Manual halt requested"):
        """Manually halt trading."""
        self._trigger_halt(HaltReason.MANUAL_HALT, reason)

    def manual_resume(self) -> Tuple[bool, str]:
        """
        Manually resume trading after halt.

        Returns:
            (success, message)
        """
        with self._state_lock:
            if self._status != SafetyStatus.HALTED:
                return False, "System not halted"

            # Can't resume if limits still breached
            if self._current_equity > 0:
                daily_loss_pct = -self._daily_pnl / self._current_equity
                if daily_loss_pct > self.limits.max_daily_loss_pct:
                    return False, "Cannot resume - daily loss limit still breached"

            drawdown = self._calculate_drawdown()
            if drawdown > self.limits.max_drawdown_pct:
                return False, "Cannot resume - drawdown limit still breached"

            # Check prop firm floor
            if self.limits.prop_firm_enabled:
                if self._current_equity < self.limits.prop_firm_balance_floor:
                    return False, f"Cannot resume - below prop firm floor ${self.limits.prop_firm_balance_floor:,.0f}"

            # Enter recovery mode
            self._status = SafetyStatus.RECOVERY
            self._recovery_trades = 0
            self._recovery_wins = 0

            logger.info(f"Entered recovery mode. Need {self.limits.min_recovery_trades} trades with {self.limits.min_recovery_win_rate:.0%} win rate")

            return True, "Entered recovery mode"

    def force_resume(self) -> bool:
        """Force resume without recovery (dangerous!)."""
        with self._state_lock:
            logger.warning("FORCE RESUME - bypassing recovery mode!")
            self._status = SafetyStatus.NORMAL
            self._halt_reason = None
            self._halt_details = ""
            self._consecutive_losses = 0
            return True

    def set_equity(self, equity: float, is_starting: bool = False):
        """Set current equity level."""
        with self._state_lock:
            self._current_equity = equity
            if equity > self._peak_equity:
                self._peak_equity = equity
            if is_starting:
                self._starting_equity = equity
                self._peak_equity = equity

    def register_halt_callback(self, callback: Callable[[HaltReason, str], None]):
        """Register callback for halt events."""
        self._halt_callbacks.append(callback)

    def get_status(self) -> Dict:
        """Get current safety status."""
        with self._state_lock:
            return {
                'status': self._status.value,
                'halt_reason': self._halt_reason.value if self._halt_reason else None,
                'halt_details': self._halt_details,
                'halted_at': self._halted_at.isoformat() if self._halted_at else None,
                'daily_pnl': self._daily_pnl,
                'weekly_pnl': self._weekly_pnl,
                'drawdown': self._calculate_drawdown(),
                'current_equity': self._current_equity,
                'peak_equity': self._peak_equity,
                'trades_today': self._trades_today,
                'trades_this_hour': self._trades_this_hour,
                'consecutive_losses': self._consecutive_losses,
                'positions': len(self._positions),
                'total_exposure': self._total_exposure,
                'total_contracts': self._total_contracts,
                'allow_live': self._allow_live,
                'crisis_mode': self._crisis_mode,
                'current_vix': self._current_vix,
                'position_size_multiplier': self.get_position_size_multiplier(),
                'limits': {
                    'max_daily_loss': self.limits.max_daily_loss_pct,
                    'max_weekly_loss': self.limits.max_weekly_loss_pct,
                    'max_drawdown': self.limits.max_drawdown_pct,
                    'max_trades_per_day': self.limits.max_trades_per_day,
                    'max_contracts': self.limits.max_contracts,
                    'prop_firm_floor': self.limits.prop_firm_balance_floor if self.limits.prop_firm_enabled else None,
                }
            }

    def get_events(self, limit: int = 100) -> List[Dict]:
        """Get recent safety events."""
        with self._state_lock:
            return [e.to_dict() for e in self._events[-limit:]]

    def _trigger_halt(self, reason: HaltReason, details: str):
        """Trigger a trading halt."""
        with self._state_lock:
            if self._status == SafetyStatus.HALTED:
                return  # Already halted

            self._status = SafetyStatus.HALTED
            self._halt_reason = reason
            self._halt_details = details
            self._halted_at = datetime.now()

            self._log_event("halt", reason, details, {
                'daily_pnl': self._daily_pnl,
                'drawdown': self._calculate_drawdown(),
                'equity': self._current_equity,
            })

        logger.critical(f"TRADING HALTED: {reason.value} - {details}")

        # Notify callbacks
        for callback in self._halt_callbacks:
            try:
                callback(reason, details)
            except Exception as e:
                logger.error(f"Halt callback error: {e}")

    def _complete_recovery(self):
        """Complete recovery and resume normal trading."""
        with self._state_lock:
            win_rate = self._recovery_wins / self._recovery_trades if self._recovery_trades > 0 else 0

            self._status = SafetyStatus.NORMAL
            self._halt_reason = None
            self._halt_details = ""
            self._consecutive_losses = 0

            self._log_event("resume", HaltReason.MANUAL_HALT,
                          f"Recovery complete: {self._recovery_trades} trades, {win_rate:.0%} win rate")

        logger.info(f"Recovery complete! Resuming normal trading. Win rate: {win_rate:.0%}")

    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown from peak."""
        if self._peak_equity <= 0:
            return 0.0
        return max(0, (self._peak_equity - self._current_equity) / self._peak_equity)

    def _update_trade_counts(self):
        """Update trade frequency counters."""
        now = datetime.now()

        # Reset hourly counter if new hour
        if (now - self._hour_start).total_seconds() > 3600:
            self._hour_start = now
            self._trades_this_hour = 0

        # Reset daily counter if new day
        if date.today() != self._daily_date:
            self._daily_date = date.today()
            self._trades_today = 0
            self._daily_pnl = 0.0

    def _log_event(self, event_type: str, reason: HaltReason, details: str,
                   metrics: Dict = None):
        """Log a safety event."""
        event = SafetyEvent(
            event_id=f"{event_type}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            event_type=event_type,
            reason=reason,
            details=details,
            metrics=metrics or {}
        )

        with self._state_lock:
            self._events.append(event)
            if len(self._events) > 1000:
                self._events = self._events[-1000:]

        # Persist
        self._persist_event(event)

    def _persist_event(self, event: SafetyEvent):
        """Persist event to disk."""
        date_str = event.timestamp.strftime('%Y%m%d')
        path = os.path.join(self.storage_path, f"safety_events_{date_str}.jsonl")

        try:
            with open(path, 'a') as f:
                f.write(json.dumps(event.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to persist safety event: {e}")


# Global instance
_guard: Optional[SafetyGuard] = None


def get_safety_guard() -> SafetyGuard:
    """Get global SafetyGuard instance (singleton)."""
    global _guard
    if _guard is None:
        _guard = SafetyGuard()
    return _guard


def require_safe_trading(is_live: bool = False) -> Callable:
    """
    Decorator that requires safety check before function execution.

    Usage:
        @require_safe_trading(is_live=True)
        def execute_trade(symbol, size):
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            guard = get_safety_guard()
            allowed, reason = guard.can_trade(is_live=is_live)
            if not allowed:
                raise SafetyError(f"Trade blocked: {reason}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


class SafetyError(Exception):
    """Raised when a safety check fails."""
    pass


__all__ = [
    'SafetyGuard',
    'SafetyStatus',
    'HaltReason',
    'TradingLimits',
    'SafetyEvent',
    'SafetyError',
    'get_safety_guard',
    'require_safe_trading',
]
