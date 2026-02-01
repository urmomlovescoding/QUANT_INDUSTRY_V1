"""
VIX Monitor Service
===================
Monitors VIX (market volatility) and updates SafetyGuard automatically.

VIX thresholds:
- Normal: < 20 (full position sizing)
- Elevated: 20-25 (reduced sizing)
- Warning: 25-40 (minimal positions)
- Critical: > 40 (halt new positions)
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class VIXLevel(Enum):
    """VIX volatility levels."""
    NORMAL = "normal"         # VIX < 20
    ELEVATED = "elevated"     # VIX 20-25
    WARNING = "warning"       # VIX 25-40
    CRITICAL = "critical"     # VIX > 40


@dataclass
class VIXReading:
    """VIX reading with metadata."""
    value: float
    level: VIXLevel
    timestamp: datetime
    source: str
    is_market_hours: bool


class VIXMonitor:
    """
    Monitors VIX and triggers safety updates.

    This runs in the background and:
    1. Fetches VIX periodically
    2. Updates SafetyGuard with current VIX
    3. Triggers alerts on level changes
    """

    # VIX thresholds
    NORMAL_THRESHOLD = 20.0
    ELEVATED_THRESHOLD = 25.0
    CRITICAL_THRESHOLD = 40.0

    def __init__(
        self,
        update_interval_seconds: int = 60,
        fallback_vix: float = 15.0
    ):
        self.update_interval = update_interval_seconds
        self.fallback_vix = fallback_vix

        self._current_reading: Optional[VIXReading] = None
        self._history: List[VIXReading] = []
        self._max_history = 1000

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[VIXReading], None]] = []

        logger.info(f"VIXMonitor initialized: update_interval={update_interval_seconds}s")

    @property
    def current_vix(self) -> float:
        """Get current VIX value."""
        if self._current_reading:
            return self._current_reading.value
        return self.fallback_vix

    @property
    def current_level(self) -> VIXLevel:
        """Get current VIX level."""
        return self._classify_vix(self.current_vix)

    def _classify_vix(self, vix: float) -> VIXLevel:
        """Classify VIX value into level."""
        if vix >= self.CRITICAL_THRESHOLD:
            return VIXLevel.CRITICAL
        elif vix >= self.ELEVATED_THRESHOLD:
            return VIXLevel.WARNING
        elif vix >= self.NORMAL_THRESHOLD:
            return VIXLevel.ELEVATED
        else:
            return VIXLevel.NORMAL

    def _is_market_hours(self) -> bool:
        """Check if currently during US market hours."""
        now = datetime.now()
        # Simple check: 9:30 AM - 4:00 PM Eastern, Mon-Fri
        # This is simplified - real implementation would use proper timezone handling
        if now.weekday() >= 5:  # Weekend
            return False
        hour = now.hour
        return 9 <= hour < 16

    async def _fetch_vix(self) -> float:
        """
        Fetch current VIX value.

        Tries multiple sources in order:
        1. Real-time market data API
        2. Yahoo Finance
        3. Fallback value
        """
        # Try to get from market data service
        try:
            from services.data_service import get_data_service
            data_service = get_data_service()
            if hasattr(data_service, 'get_quote'):
                quote = await data_service.get_quote("^VIX")
                if quote and 'price' in quote:
                    return quote['price']
        except Exception as e:
            logger.debug(f"Market data VIX fetch failed: {e}")

        # Try Yahoo Finance
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="1d")
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except Exception as e:
            logger.debug(f"Yahoo Finance VIX fetch failed: {e}")

        # Try environment variable (for testing/manual override)
        env_vix = os.environ.get('OVERRIDE_VIX')
        if env_vix:
            try:
                return float(env_vix)
            except ValueError:
                pass

        # Return fallback
        logger.warning(f"Using fallback VIX: {self.fallback_vix}")
        return self.fallback_vix

    async def _update_vix(self) -> None:
        """Fetch and process VIX update."""
        try:
            vix_value = await self._fetch_vix()
            level = self._classify_vix(vix_value)

            reading = VIXReading(
                value=vix_value,
                level=level,
                timestamp=datetime.now(),
                source="live" if vix_value != self.fallback_vix else "fallback",
                is_market_hours=self._is_market_hours()
            )

            # Detect level change
            old_level = self._current_reading.level if self._current_reading else None
            self._current_reading = reading

            # Store in history
            self._history.append(reading)
            if len(self._history) > self._max_history:
                self._history.pop(0)

            # Update SafetyGuard
            self._update_safety_guard(vix_value)

            # Trigger callbacks if level changed
            if old_level and old_level != level:
                logger.warning(f"VIX level changed: {old_level.value} -> {level.value} (VIX={vix_value:.2f})")
                self._trigger_callbacks(reading)

            logger.debug(f"VIX updated: {vix_value:.2f} ({level.value})")

        except Exception as e:
            logger.error(f"VIX update failed: {e}")

    def _update_safety_guard(self, vix: float) -> None:
        """Update SafetyGuard with current VIX."""
        try:
            from core.safety_guard import get_safety_guard
            guard = get_safety_guard()
            guard.record_vix(vix)
        except ImportError:
            logger.debug("SafetyGuard not available")
        except Exception as e:
            logger.warning(f"Failed to update SafetyGuard VIX: {e}")

    def register_callback(self, callback: Callable[[VIXReading], None]) -> None:
        """Register callback for VIX level changes."""
        self._callbacks.append(callback)

    def _trigger_callbacks(self, reading: VIXReading) -> None:
        """Trigger all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(reading)
            except Exception as e:
                logger.error(f"VIX callback error: {e}")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            await self._update_vix()
            await asyncio.sleep(self.update_interval)

    async def start(self) -> None:
        """Start the VIX monitor."""
        if self._running:
            logger.warning("VIXMonitor already running")
            return

        self._running = True

        # Initial fetch
        await self._update_vix()

        # Start background task
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("VIXMonitor started")

    async def stop(self) -> None:
        """Stop the VIX monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("VIXMonitor stopped")

    def get_status(self) -> dict:
        """Get monitor status."""
        return {
            "running": self._running,
            "current_vix": self.current_vix,
            "current_level": self.current_level.value,
            "last_update": self._current_reading.timestamp.isoformat() if self._current_reading else None,
            "source": self._current_reading.source if self._current_reading else "none",
            "history_count": len(self._history),
            "thresholds": {
                "normal": f"< {self.NORMAL_THRESHOLD}",
                "elevated": f"{self.NORMAL_THRESHOLD}-{self.ELEVATED_THRESHOLD}",
                "warning": f"{self.ELEVATED_THRESHOLD}-{self.CRITICAL_THRESHOLD}",
                "critical": f"> {self.CRITICAL_THRESHOLD}"
            }
        }

    def get_history(self, limit: int = 100) -> List[dict]:
        """Get VIX history."""
        return [
            {
                "value": r.value,
                "level": r.level.value,
                "timestamp": r.timestamp.isoformat(),
                "source": r.source
            }
            for r in self._history[-limit:]
        ]


# Singleton instance
_vix_monitor: Optional[VIXMonitor] = None


def get_vix_monitor() -> VIXMonitor:
    """Get global VIX monitor instance."""
    global _vix_monitor
    if _vix_monitor is None:
        _vix_monitor = VIXMonitor()
    return _vix_monitor


async def start_vix_monitor() -> VIXMonitor:
    """Start the global VIX monitor."""
    monitor = get_vix_monitor()
    await monitor.start()
    return monitor


__all__ = [
    'VIXMonitor',
    'VIXLevel',
    'VIXReading',
    'get_vix_monitor',
    'start_vix_monitor',
]
