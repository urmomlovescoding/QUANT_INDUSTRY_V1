"""
QUANT_INDUSTRY_V1 NinjaTrader Integration Bridge

File-based ATI (Automated Trading Interface) integration with NinjaTrader 8.

Features:
- Order placement via ATI files
- Position tracking
- Real-time status monitoring
- Error handling and recovery
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
import threading

logger = logging.getLogger(__name__)


# =============================================================================
# TYPES
# =============================================================================

class NTOrderAction(Enum):
    """NinjaTrader order actions."""
    BUY = "BUY"
    SELL = "SELL"
    BUYTOCOVER = "BUYTOCOVER"
    SELLSHORT = "SELLSHORT"


class NTOrderType(Enum):
    """NinjaTrader order types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOPLIMIT = "STOPLIMIT"


class NTOrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    WORKING = "working"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass
class NTOrder:
    """NinjaTrader order."""
    order_id: str
    instrument: str
    action: NTOrderAction
    quantity: int
    order_type: NTOrderType
    price: float = 0.0
    stop_price: float = 0.0
    tif: str = "DAY"  # Time in force
    oco_id: str = ""  # One-cancels-other group
    strategy_id: str = ""
    status: NTOrderStatus = NTOrderStatus.PENDING
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class NTPosition:
    """NinjaTrader position."""
    instrument: str
    quantity: int  # Positive = long, negative = short
    avg_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


# =============================================================================
# ATI FILE COMMANDS
# =============================================================================

class ATICommands:
    """ATI command templates."""

    @staticmethod
    def place_order(
        action: str,
        quantity: int,
        instrument: str,
        order_type: str,
        price: float = 0,
        stop_price: float = 0,
        tif: str = "DAY",
        oco: str = "",
        strategy: str = "",
        order_id: str = "",
    ) -> str:
        """Generate order placement command."""
        cmd = f"PLACE;{instrument};{action};{quantity};{order_type}"

        if order_type in ["LIMIT", "STOPLIMIT"]:
            cmd += f";{price}"
        if order_type in ["STOP", "STOPLIMIT"]:
            cmd += f";{stop_price}" if price == 0 else ""

        cmd += f";{tif}"

        if oco:
            cmd += f";{oco}"
        if strategy:
            cmd += f";{strategy}"
        if order_id:
            cmd += f";{order_id}"

        return cmd

    @staticmethod
    def cancel_order(order_id: str) -> str:
        """Generate cancel order command."""
        return f"CANCEL;{order_id}"

    @staticmethod
    def close_position(instrument: str) -> str:
        """Generate close position command."""
        return f"CLOSEPOSITION;{instrument}"

    @staticmethod
    def flatten_all() -> str:
        """Generate flatten all command."""
        return "FLATTENALL"

    @staticmethod
    def cancel_all_orders() -> str:
        """Generate cancel all orders command."""
        return "CANCELALLORDERS"


# =============================================================================
# NINJATRADER BRIDGE
# =============================================================================

class NinjaTraderBridge:
    """
    NinjaTrader ATI File-Based Bridge.

    Communicates with NinjaTrader via file-based interface.
    Watches for responses and status updates.
    """

    def __init__(
        self,
        incoming_dir: str = None,
        outgoing_dir: str = None,
        poll_interval: float = 0.1,
    ):
        # Default to NinjaTrader's standard ATI directories
        self.incoming_dir = Path(incoming_dir or r"C:\NinjaTrader 8\incoming")
        self.outgoing_dir = Path(outgoing_dir or r"C:\NinjaTrader 8\outgoing")

        self.poll_interval = poll_interval

        # State
        self.orders: Dict[str, NTOrder] = {}
        self.positions: Dict[str, NTPosition] = {}
        self.connected = False

        # Threading
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_fill: List[callable] = []
        self.on_order_update: List[callable] = []
        self.on_position_update: List[callable] = []

        # Order counter
        self._order_counter = 0

    def connect(self) -> bool:
        """Verify connection to NinjaTrader."""
        # Check directories exist
        if not self.incoming_dir.exists():
            try:
                self.incoming_dir.mkdir(parents=True)
            except Exception as e:
                logger.error(f"Cannot create incoming dir: {e}")
                return False

        if not self.outgoing_dir.exists():
            try:
                self.outgoing_dir.mkdir(parents=True)
            except Exception as e:
                logger.error(f"Cannot create outgoing dir: {e}")
                return False

        self.connected = True
        logger.info("NinjaTrader bridge connected")
        return True

    def start_monitoring(self) -> None:
        """Start monitoring for responses."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("NinjaTrader response monitoring started")

    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        logger.info("NinjaTrader monitoring stopped")

    def _monitor_loop(self) -> None:
        """Monitor outgoing directory for responses."""
        while not self._stop_event.is_set():
            try:
                self._process_responses()
            except Exception as e:
                logger.error(f"Monitor error: {e}")

            time.sleep(self.poll_interval)

    def _process_responses(self) -> None:
        """Process response files from NinjaTrader."""
        for file_path in self.outgoing_dir.glob("*.txt"):
            try:
                with open(file_path, 'r') as f:
                    content = f.read().strip()

                self._parse_response(content)

                # Remove processed file
                file_path.unlink()

            except Exception as e:
                logger.error(f"Error processing response file {file_path}: {e}")

    def _parse_response(self, content: str) -> None:
        """Parse NinjaTrader response."""
        lines = content.split('\n')

        for line in lines:
            parts = line.strip().split(';')
            if not parts:
                continue

            msg_type = parts[0].upper()

            if msg_type == "FILLED":
                self._handle_fill(parts)
            elif msg_type == "CANCELLED":
                self._handle_cancel(parts)
            elif msg_type == "REJECTED":
                self._handle_reject(parts)
            elif msg_type == "POSITION":
                self._handle_position(parts)
            elif msg_type == "ERROR":
                self._handle_error(parts)

    def _handle_fill(self, parts: List[str]) -> None:
        """Handle fill notification."""
        if len(parts) < 5:
            return

        order_id = parts[1]
        instrument = parts[2]
        qty = int(parts[3])
        price = float(parts[4])

        if order_id in self.orders:
            order = self.orders[order_id]
            order.filled_qty = qty
            order.avg_fill_price = price
            order.status = NTOrderStatus.FILLED
            order.updated_at = datetime.now(timezone.utc)

            # Notify callbacks
            for callback in self.on_fill:
                try:
                    callback(order)
                except Exception as e:
                    logger.error(f"Fill callback error: {e}")

        logger.info(f"Order {order_id} filled: {qty} @ {price}")

    def _handle_cancel(self, parts: List[str]) -> None:
        """Handle cancel notification."""
        if len(parts) < 2:
            return

        order_id = parts[1]
        if order_id in self.orders:
            self.orders[order_id].status = NTOrderStatus.CANCELLED
            self.orders[order_id].updated_at = datetime.now(timezone.utc)

        logger.info(f"Order {order_id} cancelled")

    def _handle_reject(self, parts: List[str]) -> None:
        """Handle rejection notification."""
        if len(parts) < 3:
            return

        order_id = parts[1]
        reason = parts[2] if len(parts) > 2 else "Unknown"

        if order_id in self.orders:
            self.orders[order_id].status = NTOrderStatus.REJECTED
            self.orders[order_id].updated_at = datetime.now(timezone.utc)

        logger.warning(f"Order {order_id} rejected: {reason}")

    def _handle_position(self, parts: List[str]) -> None:
        """Handle position update."""
        if len(parts) < 4:
            return

        instrument = parts[1]
        qty = int(parts[2])
        avg_price = float(parts[3])
        unrealized = float(parts[4]) if len(parts) > 4 else 0

        self.positions[instrument] = NTPosition(
            instrument=instrument,
            quantity=qty,
            avg_price=avg_price,
            unrealized_pnl=unrealized,
        )

        for callback in self.on_position_update:
            try:
                callback(self.positions[instrument])
            except Exception as e:
                logger.error(f"Position callback error: {e}")

    def _handle_error(self, parts: List[str]) -> None:
        """Handle error message."""
        error_msg = ';'.join(parts[1:]) if len(parts) > 1 else "Unknown error"
        logger.error(f"NinjaTrader error: {error_msg}")

    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        self._order_counter += 1
        return f"QI_{int(time.time())}_{self._order_counter}"

    def _write_command(self, command: str) -> bool:
        """Write command to incoming directory."""
        if not self.connected:
            logger.error("Not connected to NinjaTrader")
            return False

        filename = f"cmd_{int(time.time() * 1000)}.txt"
        file_path = self.incoming_dir / filename

        try:
            with open(file_path, 'w') as f:
                f.write(command)
            return True
        except Exception as e:
            logger.error(f"Failed to write command: {e}")
            return False

    # ==========================================================================
    # PUBLIC API
    # ==========================================================================

    def place_market_order(
        self,
        instrument: str,
        action: NTOrderAction,
        quantity: int,
        strategy_id: str = "",
    ) -> Optional[str]:
        """Place a market order."""
        order_id = self._generate_order_id()

        cmd = ATICommands.place_order(
            action=action.value,
            quantity=quantity,
            instrument=instrument,
            order_type="MARKET",
            strategy=strategy_id,
            order_id=order_id,
        )

        if self._write_command(cmd):
            order = NTOrder(
                order_id=order_id,
                instrument=instrument,
                action=action,
                quantity=quantity,
                order_type=NTOrderType.MARKET,
                strategy_id=strategy_id,
                status=NTOrderStatus.SUBMITTED,
            )
            self.orders[order_id] = order
            logger.info(f"Market order submitted: {order_id}")
            return order_id

        return None

    def place_limit_order(
        self,
        instrument: str,
        action: NTOrderAction,
        quantity: int,
        price: float,
        strategy_id: str = "",
    ) -> Optional[str]:
        """Place a limit order."""
        order_id = self._generate_order_id()

        cmd = ATICommands.place_order(
            action=action.value,
            quantity=quantity,
            instrument=instrument,
            order_type="LIMIT",
            price=price,
            strategy=strategy_id,
            order_id=order_id,
        )

        if self._write_command(cmd):
            order = NTOrder(
                order_id=order_id,
                instrument=instrument,
                action=action,
                quantity=quantity,
                order_type=NTOrderType.LIMIT,
                price=price,
                strategy_id=strategy_id,
                status=NTOrderStatus.SUBMITTED,
            )
            self.orders[order_id] = order
            logger.info(f"Limit order submitted: {order_id} @ {price}")
            return order_id

        return None

    def place_stop_order(
        self,
        instrument: str,
        action: NTOrderAction,
        quantity: int,
        stop_price: float,
        strategy_id: str = "",
    ) -> Optional[str]:
        """Place a stop order."""
        order_id = self._generate_order_id()

        cmd = ATICommands.place_order(
            action=action.value,
            quantity=quantity,
            instrument=instrument,
            order_type="STOP",
            stop_price=stop_price,
            strategy=strategy_id,
            order_id=order_id,
        )

        if self._write_command(cmd):
            order = NTOrder(
                order_id=order_id,
                instrument=instrument,
                action=action,
                quantity=quantity,
                order_type=NTOrderType.STOP,
                stop_price=stop_price,
                strategy_id=strategy_id,
                status=NTOrderStatus.SUBMITTED,
            )
            self.orders[order_id] = order
            logger.info(f"Stop order submitted: {order_id} @ {stop_price}")
            return order_id

        return None

    def place_bracket_order(
        self,
        instrument: str,
        action: NTOrderAction,
        quantity: int,
        entry_price: float = None,
        stop_loss: float = None,
        take_profit: float = None,
        strategy_id: str = "",
    ) -> Dict[str, str]:
        """
        Place a bracket order (entry + stop loss + take profit).

        Returns dict with order IDs.
        """
        result = {'entry': None, 'stop_loss': None, 'take_profit': None}
        oco_id = f"OCO_{int(time.time())}"

        # Entry order
        if entry_price:
            result['entry'] = self.place_limit_order(
                instrument, action, quantity, entry_price, strategy_id
            )
        else:
            result['entry'] = self.place_market_order(
                instrument, action, quantity, strategy_id
            )

        # Determine exit action
        exit_action = NTOrderAction.SELL if action == NTOrderAction.BUY else NTOrderAction.BUYTOCOVER

        # Stop loss
        if stop_loss:
            sl_id = self._generate_order_id()
            cmd = ATICommands.place_order(
                action=exit_action.value,
                quantity=quantity,
                instrument=instrument,
                order_type="STOP",
                stop_price=stop_loss,
                oco=oco_id,
                strategy=strategy_id,
                order_id=sl_id,
            )
            if self._write_command(cmd):
                result['stop_loss'] = sl_id

        # Take profit
        if take_profit:
            tp_id = self._generate_order_id()
            cmd = ATICommands.place_order(
                action=exit_action.value,
                quantity=quantity,
                instrument=instrument,
                order_type="LIMIT",
                price=take_profit,
                oco=oco_id,
                strategy=strategy_id,
                order_id=tp_id,
            )
            if self._write_command(cmd):
                result['take_profit'] = tp_id

        return result

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        cmd = ATICommands.cancel_order(order_id)
        return self._write_command(cmd)

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders."""
        cmd = ATICommands.cancel_all_orders()
        return self._write_command(cmd)

    def close_position(self, instrument: str) -> bool:
        """Close position for instrument."""
        cmd = ATICommands.close_position(instrument)
        return self._write_command(cmd)

    def flatten_all(self) -> bool:
        """Flatten all positions."""
        cmd = ATICommands.flatten_all()
        return self._write_command(cmd)

    def get_order(self, order_id: str) -> Optional[NTOrder]:
        """Get order by ID."""
        return self.orders.get(order_id)

    def get_position(self, instrument: str) -> Optional[NTPosition]:
        """Get position for instrument."""
        return self.positions.get(instrument)

    def get_all_positions(self) -> Dict[str, NTPosition]:
        """Get all positions."""
        return self.positions.copy()

    def get_open_orders(self) -> List[NTOrder]:
        """Get all open orders."""
        return [
            o for o in self.orders.values()
            if o.status in [NTOrderStatus.PENDING, NTOrderStatus.SUBMITTED, NTOrderStatus.WORKING]
        ]


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'NTOrderAction',
    'NTOrderType',
    'NTOrderStatus',
    'NTOrder',
    'NTPosition',
    'ATICommands',
    'NinjaTraderBridge',
]
