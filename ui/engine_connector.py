"""
QUANT_INDUSTRY_V1 Engine Connector

Bridges the TradingEngine to the UI's state management system.
"""

import threading
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from .state import (
    get_store, get_event_bus, EventType, dispatch, notify,
    SignalState, PositionState, PortfolioState, MarketState,
)

logger = logging.getLogger(__name__)


class EngineConnector:
    """
    Connects the TradingEngine to the UI state system.

    This class:
    1. Subscribes to engine callbacks
    2. Transforms engine data to UI state format
    3. Dispatches events to the UI
    4. Provides control methods for the UI to interact with the engine
    """

    def __init__(self, engine=None):
        self._engine = engine
        self._update_interval = 1.0  # seconds
        self._stop_event = threading.Event()
        self._update_thread: Optional[threading.Thread] = None

        self._store = None
        self._event_bus = None

    def connect(self, engine) -> None:
        """Connect to a trading engine."""
        self._engine = engine

        # Setup callbacks
        engine.on_signal.append(self._on_signal)
        engine.on_trade.append(self._on_trade)
        engine.on_error.append(self._on_error)

        logger.info("Engine connector attached to trading engine")

    def start_updates(self) -> None:
        """Start periodic UI updates."""
        self._store = get_store()
        self._event_bus = get_event_bus()

        self._stop_event.clear()
        self._update_thread = threading.Thread(
            target=self._update_loop,
            daemon=True,
            name="EngineConnector-UpdateLoop"
        )
        self._update_thread.start()
        logger.info("Engine connector update loop started")

    def stop_updates(self) -> None:
        """Stop periodic updates."""
        self._stop_event.set()
        if self._update_thread:
            self._update_thread.join(timeout=5.0)
        logger.info("Engine connector update loop stopped")

    def _update_loop(self) -> None:
        """Periodic update loop."""
        while not self._stop_event.is_set():
            try:
                self._sync_state()
            except Exception as e:
                logger.error(f"Error syncing state: {e}")

            self._stop_event.wait(self._update_interval)

    def _sync_state(self) -> None:
        """Sync engine state to UI state."""
        if not self._engine or not self._store:
            return

        try:
            # Get engine status
            status = self._engine.get_status()
            positions = self._engine.get_positions()

            # Update portfolio state
            portfolio = PortfolioState(
                equity=status.get('equity', 0),
                cash=status.get('cash', 0),
                buying_power=status.get('cash', 0),
                day_pnl=status.get('pnl', 0),
                total_pnl=status.get('pnl', 0),
                total_return_pct=status.get('pnl_pct', 0) / 100 if status.get('pnl_pct') else 0,
                net_exposure=self._calculate_exposure(positions, status.get('equity', 1)),
            )
            self._store.update_portfolio(portfolio)

            # Update positions
            for symbol, pos in positions.items():
                qty = pos.get('quantity', 0)
                entry_price = pos.get('avg_price', 0)
                current = pos.get('current_price', entry_price)
                unrealized = pos.get('unrealized_pnl', 0)

                position_state = PositionState(
                    symbol=symbol,
                    side='long' if qty > 0 else 'short',
                    qty=abs(qty),
                    entry_price=entry_price,
                    current_price=current,
                    unrealized_pnl=unrealized,
                    realized_pnl=0,
                    opened_at=pos.get('entry_time', datetime.now(timezone.utc)),
                )
                self._store.update_position(symbol, position_state)

            # Remove closed positions
            current_symbols = set(positions.keys())
            state_symbols = set(self._store.state.positions.keys())
            for closed in state_symbols - current_symbols:
                self._store.remove_position(closed)

            # Update market state
            market = MarketState(
                regime=status.get('current_regime', 'unknown').upper(),
                regime_confidence=0.7,  # Would come from regime detector
                volatility=0,
                trend_strength=0,
            )
            self._store.update_market(market)

            # Dispatch portfolio update event
            dispatch(EventType.PORTFOLIO_UPDATED, {'portfolio': portfolio})
            dispatch(EventType.POSITIONS_UPDATED, {'positions': positions})

        except Exception as e:
            logger.error(f"Error syncing state: {e}")

    def _calculate_exposure(self, positions: Dict[str, Any], equity: float) -> float:
        """Calculate net exposure percentage."""
        if equity <= 0:
            return 0.0

        total_long = sum(
            pos.get('quantity', 0) * pos.get('current_price', pos.get('avg_price', 0))
            for pos in positions.values()
            if pos.get('quantity', 0) > 0
        )
        total_short = sum(
            abs(pos.get('quantity', 0)) * pos.get('current_price', pos.get('avg_price', 0))
            for pos in positions.values()
            if pos.get('quantity', 0) < 0
        )

        return (total_long - total_short) / equity

    def _on_signal(self, signal_dict: Dict[str, Any]) -> None:
        """Handle signal from engine."""
        try:
            signal = signal_dict.get('signal')
            if not signal:
                return

            signal_state = SignalState(
                id=f"{signal.symbol}_{signal.strategy_id}_{datetime.now().timestamp()}",
                symbol=signal.symbol,
                direction=signal.direction.value.upper(),
                confidence=signal.confidence,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss if hasattr(signal, 'stop_loss') else None,
                take_profit=signal.take_profit if hasattr(signal, 'take_profit') else None,
                expected_return=signal.strength * 0.02,  # Estimate
                strategy_id=signal.strategy_id,
                generated_at=datetime.now(timezone.utc),
            )

            if self._store:
                self._store.update_signal(signal_state.id, signal_state)
                dispatch(EventType.SIGNALS_UPDATED, {'signal': signal_state})

            # Send notification
            notify(
                f"Signal: {signal.direction.value.upper()} {signal.symbol}",
                level="info"
            )

        except Exception as e:
            logger.error(f"Error handling signal: {e}")

    def _on_trade(self, trade: Dict[str, Any]) -> None:
        """Handle trade from engine."""
        try:
            notify(
                f"Trade: {trade.get('side', '').upper()} {trade.get('quantity', 0)} {trade.get('symbol', '')}",
                level="success"
            )

            # Trigger position update
            dispatch(EventType.POSITIONS_UPDATED, {'trade': trade})

        except Exception as e:
            logger.error(f"Error handling trade: {e}")

    def _on_error(self, error: Exception) -> None:
        """Handle error from engine."""
        notify(f"Engine error: {str(error)}", level="error")
        dispatch(EventType.ERROR_OCCURRED, {'error': str(error)})

    # Control methods for UI

    def initialize_engine(self) -> bool:
        """Initialize the engine."""
        if not self._engine:
            return False

        try:
            self._engine.initialize()
            notify("Engine initialized", level="success")
            return True
        except Exception as e:
            notify(f"Failed to initialize: {e}", level="error")
            return False

    def start_engine(self) -> bool:
        """Start the trading engine."""
        if not self._engine:
            return False

        try:
            self._engine.start()
            self.start_updates()
            notify("Engine started", level="success")
            dispatch(EventType.STATUS_CHANGED, {'status': 'running'})
            return True
        except Exception as e:
            notify(f"Failed to start: {e}", level="error")
            return False

    def stop_engine(self) -> bool:
        """Stop the trading engine."""
        if not self._engine:
            return False

        try:
            self._engine.stop()
            self.stop_updates()
            notify("Engine stopped", level="info")
            dispatch(EventType.STATUS_CHANGED, {'status': 'stopped'})
            return True
        except Exception as e:
            notify(f"Failed to stop: {e}", level="error")
            return False

    def get_engine_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        if not self._engine:
            return {'state': 'disconnected'}
        return self._engine.get_status()


# Global connector instance
_connector: Optional[EngineConnector] = None


def get_connector() -> EngineConnector:
    """Get the global engine connector."""
    global _connector
    if _connector is None:
        _connector = EngineConnector()
    return _connector


def connect_engine(engine) -> EngineConnector:
    """Connect an engine and return the connector."""
    connector = get_connector()
    connector.connect(engine)
    return connector
