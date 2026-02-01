"""
Service Orchestrator
====================
Central coordination of all services.

This is the SINGLE POINT OF ACCESS for service interactions.
All cross-service communication MUST go through this orchestrator.

Responsibilities:
1. Service lifecycle management
2. Environment isolation (paper/live)
3. Safety enforcement
4. Feedback loop coordination
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Runtime environment."""
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"
    SIMULATION = "simulation"


@dataclass
class ServiceHealth:
    """Health status of a service."""
    name: str
    healthy: bool
    message: str
    last_check: datetime
    details: Dict[str, Any]


class ServiceOrchestrator:
    """
    Central service coordinator.

    Singleton pattern ensures one orchestrator per process.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        # Determine environment
        self._environment = self._detect_environment()
        self._allow_live = os.environ.get('ALLOW_LIVE', '').lower() == 'true'

        # Service references (lazy loaded)
        self._market_data = None
        self._execution = None
        self._portfolio = None
        self._risk = None
        self._journal = None

        # Safety systems
        self._safety_guard = None
        self._kill_switch = None

        # ML systems
        self._brain = None
        self._feedback_loop = None

        # Journaling
        self._journal = None

        # State
        self._started = False
        self._start_time = None

        self._initialized = True

        logger.info(f"ServiceOrchestrator initialized: env={self._environment.value}, allow_live={self._allow_live}")

    def _detect_environment(self) -> Environment:
        """Detect runtime environment from env vars."""
        mode = os.environ.get('QUANT_MODE', 'paper').lower()

        if mode == 'live':
            return Environment.LIVE
        elif mode == 'backtest':
            return Environment.BACKTEST
        elif mode == 'simulation':
            return Environment.SIMULATION
        else:
            return Environment.PAPER

    @property
    def environment(self) -> Environment:
        return self._environment

    @property
    def is_live(self) -> bool:
        return self._environment == Environment.LIVE and self._allow_live

    @property
    def is_paper(self) -> bool:
        return self._environment == Environment.PAPER

    # =========================================================================
    # Service Access
    # =========================================================================

    @property
    def safety_guard(self):
        """Get SafetyGuard instance."""
        if self._safety_guard is None:
            try:
                from backend.core.safety_guard import get_safety_guard
                self._safety_guard = get_safety_guard()
            except ImportError:
                from core.safety_guard import get_safety_guard
                self._safety_guard = get_safety_guard()
        return self._safety_guard

    @property
    def kill_switch(self):
        """Get KillSwitch instance."""
        if self._kill_switch is None:
            try:
                from backend.execution.kill_switch import get_kill_switch
                self._kill_switch = get_kill_switch()
            except ImportError:
                from execution.kill_switch import get_kill_switch
                self._kill_switch = get_kill_switch()
        return self._kill_switch

    @property
    def market_data(self):
        """Get MarketData service."""
        if self._market_data is None:
            try:
                from services.data_service import get_data_service
                self._market_data = get_data_service()
            except ImportError:
                logger.warning("MarketData service not available")
        return self._market_data

    @property
    def feedback_loop(self):
        """Get FeedbackLoop instance."""
        if self._feedback_loop is None:
            try:
                from brain.feedback_loop import get_feedback_loop
                self._feedback_loop = get_feedback_loop()
            except ImportError:
                logger.warning("FeedbackLoop not available")
        return self._feedback_loop

    @property
    def journal(self):
        """Get TradeJournal instance."""
        if self._journal is None:
            try:
                from services.trade_journal import get_trade_journal
                self._journal = get_trade_journal()
            except ImportError:
                logger.warning("TradeJournal not available")
        return self._journal

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def start(self) -> bool:
        """
        Start all services.

        Returns True if successful.
        """
        if self._started:
            logger.warning("Orchestrator already started")
            return True

        logger.info(f"Starting ServiceOrchestrator in {self._environment.value} mode")

        try:
            # Initialize safety systems first
            _ = self.safety_guard
            _ = self.kill_switch

            # Set initial equity in SafetyGuard
            if self.safety_guard:
                initial_equity = float(os.environ.get('INITIAL_EQUITY', '50000'))
                self.safety_guard.set_equity(initial_equity, is_starting=True)
                logger.info(f"SafetyGuard initialized with equity: ${initial_equity:,.2f}")

            # Initialize market data
            _ = self.market_data

            self._started = True
            self._start_time = datetime.now()

            logger.info("ServiceOrchestrator started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start orchestrator: {e}")
            return False

    def stop(self) -> None:
        """Stop all services gracefully."""
        logger.info("Stopping ServiceOrchestrator")

        # Flatten positions if in live mode
        if self.is_live:
            logger.warning("Flattening all positions before shutdown")
            # TODO: Call execution.flatten_all()

        self._started = False

    # =========================================================================
    # Trading Operations
    # =========================================================================

    def can_trade(self, symbol: str = None, is_live: bool = None) -> tuple:
        """
        Check if trading is allowed.

        Returns (allowed, reason).
        """
        # Use environment if is_live not specified
        if is_live is None:
            is_live = self.is_live

        # Check KillSwitch first
        if self.kill_switch and self.kill_switch.check():
            return False, f"KillSwitch active: {self.kill_switch.reason}"

        # Check SafetyGuard
        if self.safety_guard:
            allowed, reason = self.safety_guard.can_trade(
                symbol=symbol,
                is_live=is_live
            )
            if not allowed:
                return False, reason

        return True, "OK"

    def record_trade_result(
        self,
        symbol: str,
        pnl: float,
        strategy_id: str = None,
        signal_confidence: float = 0.0
    ) -> None:
        """
        Record a trade result.

        This updates:
        1. SafetyGuard equity and P&L
        2. FeedbackLoop for ML learning
        3. Trade journal
        """
        # Update SafetyGuard
        if self.safety_guard:
            self.safety_guard.record_trade(
                symbol=symbol,
                pnl=pnl,
                size_pct=0.0  # Will be calculated from position
            )

        # Update FeedbackLoop for ML learning
        if self.feedback_loop:
            try:
                self.feedback_loop.record_trade(
                    symbol=symbol,
                    pnl=pnl,
                    strategy_id=strategy_id,
                    confidence=signal_confidence
                )
            except Exception as e:
                logger.warning(f"FeedbackLoop record failed: {e}")

        logger.info(f"Trade result recorded: {symbol} PnL=${pnl:.2f}")

    def update_vix(self, vix: float) -> None:
        """Update VIX level in safety systems."""
        if self.safety_guard:
            self.safety_guard.record_vix(vix)

    def sync_broker_equity(self, equity: float) -> None:
        """
        Sync account equity from broker to SafetyGuard.

        Call this after broker account sync to keep SafetyGuard in sync.
        """
        if self.safety_guard:
            self.safety_guard.set_equity(equity, is_starting=False)
            logger.debug(f"SafetyGuard equity synced: ${equity:,.2f}")

    def get_position_size_limit(self, symbol: str = None) -> dict:
        """
        Get allowed position size for a symbol.

        Returns sizing limits based on current risk state.
        """
        if not self.safety_guard:
            return {
                "max_size_pct": 0.25,
                "max_contracts": 6,
                "multiplier": 1.0,
                "reason": "SafetyGuard not available"
            }

        status = self.safety_guard.get_status()
        vix_multiplier = status.get("vix_multiplier", 1.0)
        size_multiplier = status.get("size_multiplier", 1.0)

        # Combine multipliers
        combined = min(vix_multiplier, size_multiplier)

        return {
            "max_size_pct": 0.25 * combined,
            "max_contracts": max(1, int(6 * combined)),
            "multiplier": combined,
            "vix_level": status.get("current_vix", 15.0),
            "consecutive_losses": status.get("consecutive_losses", 0),
            "reason": "OK" if combined >= 0.5 else "Reduced due to risk conditions"
        }

    # =========================================================================
    # Health
    # =========================================================================

    def get_health(self) -> Dict[str, Any]:
        """Get overall system health."""
        health = {
            "status": "healthy" if self._started else "stopped",
            "environment": self._environment.value,
            "is_live": self.is_live,
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds() if self._start_time else 0,
            "services": {}
        }

        # SafetyGuard health
        if self.safety_guard:
            health["services"]["safety_guard"] = self.safety_guard.get_status()

        # KillSwitch health
        if self.kill_switch:
            health["services"]["kill_switch"] = self.kill_switch.get_status()

        # Market data health
        if self.market_data:
            try:
                health["services"]["market_data"] = {
                    "healthy": True,
                    "sources": getattr(self.market_data, 'active_sources', [])
                }
            except Exception:
                health["services"]["market_data"] = {"healthy": False}

        return health


# Global instance
_orchestrator: Optional[ServiceOrchestrator] = None


def get_orchestrator() -> ServiceOrchestrator:
    """Get global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ServiceOrchestrator()
    return _orchestrator


def require_trading_allowed(func):
    """
    Decorator that checks trading is allowed before function execution.

    Usage:
        @require_trading_allowed
        def submit_order(order):
            ...
    """
    def wrapper(*args, **kwargs):
        orchestrator = get_orchestrator()
        allowed, reason = orchestrator.can_trade()
        if not allowed:
            raise RuntimeError(f"Trading not allowed: {reason}")
        return func(*args, **kwargs)
    return wrapper


__all__ = [
    'ServiceOrchestrator',
    'Environment',
    'ServiceHealth',
    'get_orchestrator',
    'require_trading_allowed',
]
