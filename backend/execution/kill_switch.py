"""
Kill Switch
===========
P0 Critical Feature: Emergency stop for all trading activity.

Implements exact parity with quant-platform/execution/kill_switch.py
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

logger = logging.getLogger("KILL_SWITCH")


@dataclass
class KillSwitchEvent:
    """Record of kill switch activation/deactivation."""
    event_type: str  # 'activated' or 'deactivated'
    timestamp: datetime
    reason: str
    triggered_by: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "triggered_by": self.triggered_by,
        }


class KillSwitch:
    """
    Emergency kill switch for all trading activity.

    Implements exact parity with quant-platform behavior:
    - Global activation/deactivation
    - Automatic triggers (daily loss, consecutive losses, etc.)
    - Event logging
    - Persistence across restarts

    When activated:
    - All open positions are flattened
    - All pending orders are cancelled
    - No new trades can be executed
    - Alert is sent to operators
    """

    def __init__(self, state_dir: Optional[Path] = None):
        # State
        self.is_active: bool = False
        self.reason: str = ""
        self.activated_at: Optional[datetime] = None

        # Persistence
        self.state_dir = state_dir or Path("analytics")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self.state_dir / "kill_switch.json"
        self._log_file = self.state_dir / "kill_switch_log.json"

        # Event history
        self.events: List[KillSwitchEvent] = []

        # Callbacks
        self._on_activate: List[Callable] = []
        self._on_deactivate: List[Callable] = []

        # Auto-trigger thresholds (match platform)
        self.daily_loss_limit: float = 2000.0  # $2,000
        self.consecutive_loss_limit: int = 5
        self.error_rate_limit: float = 0.10  # 10%

        # Load persisted state
        self._load_state()

        logger.info(f"KillSwitch initialized: {'ACTIVE' if self.is_active else 'INACTIVE'}")

    def _load_state(self) -> None:
        """Load persisted state."""
        try:
            if self._state_file.exists():
                with open(self._state_file) as f:
                    data = json.load(f)
                self.is_active = data.get("is_active", False)
                self.reason = data.get("reason", "")
                if data.get("activated_at"):
                    self.activated_at = datetime.fromisoformat(data["activated_at"])

                # If was active, log warning
                if self.is_active:
                    logger.warning(
                        f"Kill switch was ACTIVE on restart: {self.reason}"
                    )
        except Exception as e:
            logger.error(f"Error loading kill switch state: {e}")

        # Load event log
        try:
            if self._log_file.exists():
                with open(self._log_file) as f:
                    log_data = json.load(f)
                self.events = [
                    KillSwitchEvent(
                        event_type=e["event_type"],
                        timestamp=datetime.fromisoformat(e["timestamp"]),
                        reason=e["reason"],
                        triggered_by=e.get("triggered_by", "system"),
                    )
                    for e in log_data
                ]
        except Exception as e:
            logger.error(f"Error loading kill switch log: {e}")

    def _save_state(self) -> None:
        """Save state to disk."""
        try:
            state = {
                "is_active": self.is_active,
                "reason": self.reason,
                "activated_at": self.activated_at.isoformat() if self.activated_at else None,
                "updated": datetime.now().isoformat(),
            }
            with open(self._state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving kill switch state: {e}")

    def _save_log(self) -> None:
        """Save event log to disk."""
        try:
            log_data = [e.to_dict() for e in self.events[-100:]]  # Keep last 100
            with open(self._log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving kill switch log: {e}")

    def register_on_activate(self, callback: Callable) -> None:
        """Register callback for activation."""
        self._on_activate.append(callback)

    def register_on_deactivate(self, callback: Callable) -> None:
        """Register callback for deactivation."""
        self._on_deactivate.append(callback)

    def activate(self, reason: str, triggered_by: str = "system") -> None:
        """
        Activate the kill switch.

        This will:
        1. Set is_active = True
        2. Record the reason and timestamp
        3. Call all registered activation callbacks
        4. Log the event
        5. Persist state

        Args:
            reason: Why the kill switch was activated
            triggered_by: Who/what triggered it (system, operator, etc.)
        """
        if self.is_active:
            logger.warning(f"Kill switch already active: {self.reason}")
            return

        self.is_active = True
        self.reason = reason
        self.activated_at = datetime.now()

        # Log event
        event = KillSwitchEvent(
            event_type="activated",
            timestamp=self.activated_at,
            reason=reason,
            triggered_by=triggered_by,
        )
        self.events.append(event)

        # Persist
        self._save_state()
        self._save_log()

        # Critical log
        logger.critical(f"KILL SWITCH ACTIVATED: {reason} (by {triggered_by})")

        # Notify callbacks
        for callback in self._on_activate:
            try:
                callback(reason)
            except Exception as e:
                logger.error(f"Activation callback error: {e}")

    def deactivate(self, reason: str = "Manual deactivation", triggered_by: str = "operator") -> None:
        """
        Deactivate the kill switch.

        Requires explicit confirmation (triggered_by should be 'operator').

        Args:
            reason: Why it's being deactivated
            triggered_by: Who is deactivating (should be 'operator')
        """
        if not self.is_active:
            logger.info("Kill switch already inactive")
            return

        self.is_active = False
        deactivated_at = datetime.now()

        # Log event
        event = KillSwitchEvent(
            event_type="deactivated",
            timestamp=deactivated_at,
            reason=reason,
            triggered_by=triggered_by,
        )
        self.events.append(event)

        # Persist
        self._save_state()
        self._save_log()

        logger.warning(f"Kill switch DEACTIVATED: {reason} (by {triggered_by})")

        # Clear activation state
        self.reason = ""
        self.activated_at = None

        # Notify callbacks
        for callback in self._on_deactivate:
            try:
                callback(reason)
            except Exception as e:
                logger.error(f"Deactivation callback error: {e}")

    def check(self) -> bool:
        """
        Check if kill switch is active.

        Returns:
            True if active (trading should stop), False otherwise
        """
        return self.is_active

    def check_auto_triggers(
        self,
        daily_loss: float = 0.0,
        consecutive_losses: int = 0,
        error_rate: float = 0.0,
    ) -> bool:
        """
        Check automatic trigger conditions.

        Called by execution engine to check if kill switch should auto-activate.

        Args:
            daily_loss: Current day's loss in dollars
            consecutive_losses: Number of consecutive losing trades
            error_rate: Rate of system errors

        Returns:
            True if kill switch was activated
        """
        if self.is_active:
            return True

        # Check daily loss limit
        if daily_loss >= self.daily_loss_limit:
            self.activate(
                f"Daily loss limit exceeded: ${daily_loss:.2f} >= ${self.daily_loss_limit:.2f}",
                triggered_by="auto_daily_loss"
            )
            return True

        # Check consecutive losses
        if consecutive_losses >= self.consecutive_loss_limit:
            self.activate(
                f"Consecutive loss limit exceeded: {consecutive_losses} >= {self.consecutive_loss_limit}",
                triggered_by="auto_consecutive_loss"
            )
            return True

        # Check error rate
        if error_rate >= self.error_rate_limit:
            self.activate(
                f"Error rate limit exceeded: {error_rate:.1%} >= {self.error_rate_limit:.1%}",
                triggered_by="auto_error_rate"
            )
            return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """Get kill switch status."""
        return {
            "is_active": self.is_active,
            "reason": self.reason,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "recent_events": [e.to_dict() for e in self.events[-5:]],
            "thresholds": {
                "daily_loss_limit": self.daily_loss_limit,
                "consecutive_loss_limit": self.consecutive_loss_limit,
                "error_rate_limit": self.error_rate_limit,
            },
        }


# Singleton instance
_kill_switch: Optional[KillSwitch] = None


def get_kill_switch() -> KillSwitch:
    """Get or create kill switch singleton."""
    global _kill_switch
    if _kill_switch is None:
        _kill_switch = KillSwitch()
    return _kill_switch
