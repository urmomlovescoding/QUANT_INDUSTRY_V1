"""
QUANT_INDUSTRY_V1 Trading Engine

The core trading loop that ties everything together:
- Data fetching
- Feature computation
- Signal generation
- Risk management
- Order execution
- Position tracking

This is the heart of the system.
"""

import numpy as np
import logging
import time
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import threading
import json

logger = logging.getLogger(__name__)


# =============================================================================
# ENGINE TYPES
# =============================================================================

class EngineState(Enum):
    """Trading engine state."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class TradingMode(Enum):
    """Trading mode."""
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass
class EngineConfig:
    """Trading engine configuration."""
    mode: TradingMode = TradingMode.PAPER
    symbols: List[str] = field(default_factory=lambda: ["AAPL", "MSFT", "GOOGL"])
    initial_capital: float = 100000.0
    max_position_pct: float = 0.10
    max_positions: int = 10
    update_interval_seconds: int = 60
    db_path: str = "trading.db"

    # Risk parameters
    max_daily_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.10

    # Feature parameters
    lookback_bars: int = 100


@dataclass
class EngineSnapshot:
    """Current engine snapshot/state data."""
    cash: float
    positions: Dict[str, Dict[str, Any]]
    equity: float
    daily_pnl: float
    total_pnl: float
    signals_today: int
    trades_today: int
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# TRADING ENGINE
# =============================================================================

class TradingEngine:
    """
    Main trading engine that orchestrates all components.

    This is the central hub that:
    1. Fetches market data
    2. Computes features
    3. Detects market regime
    4. Generates signals via strategies
    5. Checks risk limits
    6. Executes orders
    7. Tracks positions and PnL
    """

    def __init__(self, config: EngineConfig = None):
        self.config = config or EngineConfig()
        self.state = EngineState.STOPPED

        # Core components (lazy loaded)
        self._data_fetcher = None
        self._feature_engine = None
        self._regime_detector = None
        self._risk_engine = None
        self._broker = None
        self._strategies = []
        self._grading_engine = None

        # State
        self.cash = self.config.initial_capital
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.orders: List[Dict[str, Any]] = []
        self.trades: List[Dict[str, Any]] = []

        # Market data cache
        self._market_data: Dict[str, Dict[str, Any]] = {}
        self._features: Dict[str, Any] = {}
        self._current_regime: str = "unknown"

        # Threading
        self._stop_event = threading.Event()
        self._engine_thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_signal: List[Callable] = []
        self.on_trade: List[Callable] = []
        self.on_error: List[Callable] = []

        # Initialize database
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.config.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity INTEGER,
                avg_price REAL,
                current_price REAL,
                unrealized_pnl REAL,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                quantity INTEGER,
                price REAL,
                pnl REAL,
                strategy_id TEXT,
                executed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                direction TEXT,
                strength REAL,
                confidence REAL,
                strategy_id TEXT,
                generated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS equity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equity REAL,
                cash REAL,
                positions_value REAL,
                timestamp TEXT
            );
        """)
        conn.commit()
        conn.close()

    def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing trading engine...")

        # Import here to avoid circular imports
        from brain import FeatureComputer, EnsembleRegimeDetector, SafetyMonitor
        from execution import SimulatedBroker
        from risk import RiskEngine
        from strategies import StrategyRegistry, MomentumStrategy, MeanReversionStrategy
        from services import SelfGradingEngine

        # Data fetcher - try to use real data, fallback to simulated
        try:
            from data import UnifiedDataFetcher
            self._data_fetcher = UnifiedDataFetcher()
            logger.info("Using UnifiedDataFetcher")
        except Exception as e:
            logger.warning(f"Could not initialize data fetcher: {e}")
            self._data_fetcher = None

        # Feature engine
        self._feature_engine = FeatureComputer()
        logger.info("Feature engine initialized")

        # Regime detector
        self._regime_detector = EnsembleRegimeDetector()
        logger.info("Regime detector initialized")

        # Risk engine - uses VolatilityScaledSizer by default
        from risk import VolatilityScaledSizer
        self._risk_engine = RiskEngine(
            portfolio_value=self.config.initial_capital,
            position_sizer=VolatilityScaledSizer(target_risk=0.02)
        )
        logger.info("Risk engine initialized")

        # Broker
        self._broker = SimulatedBroker(initial_cash=self.config.initial_capital)
        self._broker.connect()  # Connect the simulated broker
        logger.info("Broker initialized (simulated)")

        # Strategies
        from strategies import StrategyConfig, StrategyStatus

        momentum = MomentumStrategy(StrategyConfig(
            name="Momentum",
            symbols=self.config.symbols,
            parameters={'lookback': 20, 'threshold': 0.02}
        ))
        momentum.set_status(StrategyStatus.PAPER if self.config.mode == TradingMode.PAPER else StrategyStatus.LIVE)
        self._strategies.append(momentum)

        mean_rev = MeanReversionStrategy(StrategyConfig(
            name="MeanReversion",
            symbols=self.config.symbols,
            parameters={'lookback': 20, 'zscore_threshold': 2.0}
        ))
        mean_rev.set_status(StrategyStatus.PAPER if self.config.mode == TradingMode.PAPER else StrategyStatus.LIVE)
        self._strategies.append(mean_rev)

        logger.info(f"Loaded {len(self._strategies)} strategies")

        # Self-grading
        self._grading_engine = SelfGradingEngine(self.config.db_path)
        logger.info("Self-grading engine initialized")

        self.state = EngineState.STOPPED
        logger.info("Trading engine initialized successfully")

    def start(self) -> None:
        """Start the trading engine."""
        if self.state == EngineState.RUNNING:
            logger.warning("Engine already running")
            return

        logger.info("Starting trading engine...")
        self.state = EngineState.STARTING
        self._stop_event.clear()

        # Start engine thread
        self._engine_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._engine_thread.start()

        self.state = EngineState.RUNNING
        logger.info("Trading engine started")

    def stop(self) -> None:
        """Stop the trading engine."""
        logger.info("Stopping trading engine...")
        self.state = EngineState.STOPPING
        self._stop_event.set()

        if self._engine_thread:
            self._engine_thread.join(timeout=10)

        self.state = EngineState.STOPPED
        logger.info("Trading engine stopped")

    def _run_loop(self) -> None:
        """Main trading loop."""
        logger.info("Trading loop started")

        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                for handler in self.on_error:
                    try:
                        handler(e)
                    except Exception as handler_err:
                        logger.warning(f"Error handler failed: {handler_err}")

            # Wait for next update
            self._stop_event.wait(self.config.update_interval_seconds)

        logger.info("Trading loop ended")

    def _tick(self) -> None:
        """Single iteration of the trading loop."""
        # 1. Fetch market data
        self._fetch_data()

        # 2. Compute features
        self._compute_features()

        # 3. Detect regime
        self._detect_regime()

        # 4. Generate signals
        signals = self._generate_signals()

        # 5. Process signals through risk
        approved_signals = self._check_risk(signals)

        # 6. Execute orders
        self._execute_signals(approved_signals)

        # 7. Update state
        self._update_state()

        # 8. Record equity
        self._record_equity()

    def _fetch_data(self) -> None:
        """Fetch market data for all symbols."""
        for symbol in self.config.symbols:
            try:
                if self._data_fetcher:
                    # Try real data
                    from data import Timeframe
                    result = self._data_fetcher.fetch(
                        symbol,
                        Timeframe.DAY_1,
                        limit=self.config.lookback_bars
                    )
                    if result.success:
                        self._market_data[symbol] = {
                            'open': np.array([b.open for b in result.data.bars]),
                            'high': np.array([b.high for b in result.data.bars]),
                            'low': np.array([b.low for b in result.data.bars]),
                            'close': np.array([b.close for b in result.data.bars]),
                            'volume': np.array([b.volume for b in result.data.bars]),
                        }
                        continue

                # Fallback: generate simulated data
                self._market_data[symbol] = self._generate_simulated_data(symbol)

            except Exception as e:
                logger.warning(f"Failed to fetch data for {symbol}: {e}")
                self._market_data[symbol] = self._generate_simulated_data(symbol)

    def _generate_simulated_data(self, symbol: str) -> Dict[str, np.ndarray]:
        """Generate simulated market data."""
        n = self.config.lookback_bars

        # Use deterministic seed based on symbol for consistency
        seed = sum(ord(c) for c in symbol)
        np.random.seed(seed + int(time.time() / 3600))  # Changes hourly

        # Generate random walk
        returns = np.random.randn(n) * 0.02
        prices = 100 * np.exp(np.cumsum(returns))

        return {
            'open': prices * (1 + np.random.randn(n) * 0.005),
            'high': prices * (1 + np.abs(np.random.randn(n)) * 0.01),
            'low': prices * (1 - np.abs(np.random.randn(n)) * 0.01),
            'close': prices,
            'volume': np.abs(np.random.randn(n)) * 1000000 + 500000,
        }

    def _compute_features(self) -> None:
        """Compute features for all symbols."""
        for symbol, data in self._market_data.items():
            try:
                features = self._feature_engine.compute(
                    data['open'],
                    data['high'],
                    data['low'],
                    data['close'],
                    data['volume'],
                    symbol=symbol
                )
                self._features[symbol] = features
            except Exception as e:
                logger.warning(f"Failed to compute features for {symbol}: {e}")

    def _detect_regime(self) -> None:
        """Detect current market regime."""
        try:
            # Use first symbol's data for regime detection
            if self._market_data:
                symbol = list(self._market_data.keys())[0]
                data = self._market_data[symbol]

                # Calculate returns for regime detection
                close = data['close']
                returns = np.diff(np.log(close + 1e-8))

                # Calculate rolling volatility
                if len(returns) >= 20:
                    volatility = np.array([
                        np.std(returns[max(0, i-20):i+1])
                        for i in range(len(returns))
                    ])
                else:
                    volatility = np.full(len(returns), np.std(returns) if len(returns) > 0 else 0.02)

                volume = data['volume'][1:]  # Align with returns

                # Ensure arrays are same length
                min_len = min(len(returns), len(volatility), len(volume))
                returns = returns[-min_len:]
                volatility = volatility[-min_len:]
                volume = volume[-min_len:]

                # Detect regime
                regime_state = self._regime_detector.detect(returns, volatility, volume)
                self._current_regime = regime_state.regime.value
                logger.debug(f"Detected regime: {self._current_regime} (confidence: {regime_state.confidence:.2f})")
        except Exception as e:
            logger.warning(f"Failed to detect regime: {e}")
            self._current_regime = "unknown"

    def _generate_signals(self) -> List[Dict[str, Any]]:
        """Generate signals from all strategies."""
        all_signals = []

        for strategy in self._strategies:
            try:
                # Prepare data for strategy
                strategy_data = {}
                for symbol, data in self._market_data.items():
                    strategy_data[symbol] = {
                        'close': data['close'].tolist(),
                        'open': data['open'].tolist(),
                        'high': data['high'].tolist(),
                        'low': data['low'].tolist(),
                        'volume': data['volume'].tolist(),
                    }

                signals = strategy.update(strategy_data)

                for signal in signals:
                    signal_dict = {
                        'signal': signal,
                        'strategy': strategy.config.name,
                        'regime': self._current_regime,
                    }
                    all_signals.append(signal_dict)

                    # Notify handlers
                    for handler in self.on_signal:
                        try:
                            handler(signal_dict)
                        except Exception as handler_err:
                            logger.warning(f"Signal handler failed: {handler_err}")

                    # Record to database
                    self._record_signal(signal)

            except Exception as e:
                logger.warning(f"Strategy {strategy.config.name} failed: {e}")

        return all_signals

    def _check_risk(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check signals against risk limits."""
        approved = []

        for signal_dict in signals:
            signal = signal_dict['signal']

            try:
                # Check position limits
                current_positions = len(self.positions)
                if current_positions >= self.config.max_positions:
                    if signal.symbol not in self.positions:
                        logger.debug(f"Skipping {signal.symbol}: max positions reached")
                        continue

                # Check position size
                equity = self._calculate_equity()
                max_position_value = equity * self.config.max_position_pct

                if signal.entry_price:
                    position_value = abs(signal.strength) * max_position_value
                    if position_value > max_position_value:
                        signal.strength = signal.strength * (max_position_value / position_value)

                # Check daily loss
                if self._daily_loss_exceeded():
                    logger.warning("Daily loss limit exceeded, no new positions")
                    continue

                approved.append(signal_dict)

            except Exception as e:
                logger.warning(f"Risk check failed for {signal.symbol}: {e}")

        return approved

    def _daily_loss_exceeded(self) -> bool:
        """Check if daily loss limit is exceeded."""
        # Simple implementation - would need proper daily tracking
        equity = self._calculate_equity()
        daily_pnl = equity - self.config.initial_capital
        max_loss = self.config.initial_capital * self.config.max_daily_loss_pct
        return daily_pnl < -max_loss

    def _execute_signals(self, signals: List[Dict[str, Any]]) -> None:
        """Execute approved signals."""
        from strategies import SignalDirection
        from execution import Order, OrderType, OrderSide

        for signal_dict in signals:
            signal = signal_dict['signal']

            try:
                # Determine order parameters
                if signal.direction == SignalDirection.LONG:
                    side = OrderSide.BUY
                elif signal.direction == SignalDirection.SHORT:
                    side = OrderSide.SELL
                else:
                    # Flat signal - close position if exists
                    if signal.symbol in self.positions:
                        self._close_position(signal.symbol)
                    continue

                # Calculate quantity
                equity = self._calculate_equity()
                position_value = equity * self.config.max_position_pct * abs(signal.strength)
                price = signal.entry_price or self._market_data[signal.symbol]['close'][-1]
                quantity = int(position_value / price)

                if quantity <= 0:
                    continue

                # Update broker price for the symbol
                self._broker.set_price(signal.symbol, price)

                # Create and submit order
                order = Order(
                    symbol=signal.symbol,
                    quantity=quantity,
                    side=side,
                    order_type=OrderType.MARKET
                )

                result = self._broker.submit_order(order)

                if result.success and result.filled_quantity > 0:
                    fill_price = result.avg_price if result.avg_price > 0 else price

                    # Update position
                    self._update_position(
                        signal.symbol,
                        int(result.filled_quantity) if side == OrderSide.BUY else -int(result.filled_quantity),
                        fill_price
                    )

                    # Record trade
                    trade = {
                        'symbol': signal.symbol,
                        'side': side.value,
                        'quantity': int(result.filled_quantity),
                        'price': fill_price,
                        'strategy': signal_dict['strategy'],
                        'timestamp': datetime.now(timezone.utc),
                    }
                    self.trades.append(trade)
                    self._record_trade(trade)

                    # Notify handlers
                    for handler in self.on_trade:
                        try:
                            handler(trade)
                        except Exception as handler_err:
                            logger.warning(f"Trade handler failed: {handler_err}")

                    logger.info(f"Executed: {side.value} {int(result.filled_quantity)} {signal.symbol} @ {fill_price:.2f}")

            except Exception as e:
                logger.error(f"Failed to execute signal for {signal.symbol}: {e}")

    def _close_position(self, symbol: str) -> None:
        """Close an existing position."""
        if symbol not in self.positions:
            return

        from execution import Order, OrderType, OrderSide

        position = self.positions[symbol]
        quantity = abs(position['quantity'])
        side = OrderSide.SELL if position['quantity'] > 0 else OrderSide.BUY
        price = self._market_data[symbol]['close'][-1]

        # Update broker price
        self._broker.set_price(symbol, price)

        order = Order(
            symbol=symbol,
            quantity=quantity,
            side=side,
            order_type=OrderType.MARKET
        )

        result = self._broker.submit_order(order)

        if result.success and result.filled_quantity > 0:
            fill_price = result.avg_price if result.avg_price > 0 else price

            # Calculate PnL
            entry_price = position['avg_price']
            pnl = (fill_price - entry_price) * position['quantity']

            # Record trade
            trade = {
                'symbol': symbol,
                'side': side.value,
                'quantity': int(result.filled_quantity),
                'price': fill_price,
                'pnl': pnl,
                'timestamp': datetime.now(timezone.utc),
            }
            self.trades.append(trade)
            self._record_trade(trade)

            # Remove position
            del self.positions[symbol]

            logger.info(f"Closed position: {symbol} PnL: ${pnl:.2f}")

    def _update_position(self, symbol: str, quantity: int, price: float) -> None:
        """Update or create position."""
        if symbol in self.positions:
            pos = self.positions[symbol]
            old_qty = pos['quantity']
            old_val = old_qty * pos['avg_price']
            new_val = quantity * price
            total_qty = old_qty + quantity

            if total_qty != 0:
                pos['quantity'] = total_qty
                pos['avg_price'] = (old_val + new_val) / total_qty
            else:
                del self.positions[symbol]
        else:
            self.positions[symbol] = {
                'quantity': quantity,
                'avg_price': price,
                'entry_time': datetime.now(timezone.utc),
            }

    def _update_state(self) -> None:
        """Update current state with latest prices."""
        for symbol, pos in self.positions.items():
            if symbol in self._market_data:
                current_price = self._market_data[symbol]['close'][-1]
                pos['current_price'] = current_price
                pos['unrealized_pnl'] = (current_price - pos['avg_price']) * pos['quantity']

        self.cash = self._broker.cash

    def _calculate_equity(self) -> float:
        """Calculate total equity."""
        positions_value = sum(
            pos.get('current_price', pos['avg_price']) * pos['quantity']
            for pos in self.positions.values()
        )
        return self.cash + positions_value

    def _record_signal(self, signal) -> None:
        """Record signal to database."""
        conn = sqlite3.connect(self.config.db_path)
        conn.execute("""
            INSERT INTO signals (symbol, direction, strength, confidence, strategy_id, generated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            signal.symbol,
            signal.direction.value,
            signal.strength,
            signal.confidence,
            signal.strategy_id,
            datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()

    def _record_trade(self, trade: Dict[str, Any]) -> None:
        """Record trade to database."""
        conn = sqlite3.connect(self.config.db_path)
        conn.execute("""
            INSERT INTO trades (symbol, side, quantity, price, pnl, strategy_id, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            trade['symbol'],
            trade['side'],
            trade['quantity'],
            trade['price'],
            trade.get('pnl', 0),
            trade.get('strategy', ''),
            trade['timestamp'].isoformat()
        ))
        conn.commit()
        conn.close()

    def _record_equity(self) -> None:
        """Record equity snapshot to database."""
        equity = self._calculate_equity()
        positions_value = equity - self.cash

        conn = sqlite3.connect(self.config.db_path)
        conn.execute("""
            INSERT INTO equity_history (equity, cash, positions_value, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            equity,
            self.cash,
            positions_value,
            datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()

    def get_status(self) -> Dict[str, Any]:
        """Get engine status."""
        equity = self._calculate_equity()

        return {
            'state': self.state.value if isinstance(self.state, Enum) else str(self.state),
            'mode': self.config.mode.value,
            'equity': equity,
            'cash': self.cash,
            'positions': len(self.positions),
            'trades_count': len(self.trades),
            'current_regime': self._current_regime,
            'symbols': self.config.symbols,
            'pnl': equity - self.config.initial_capital,
            'pnl_pct': (equity - self.config.initial_capital) / self.config.initial_capital * 100,
        }

    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current positions."""
        return self.positions.copy()

    def get_recent_trades(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent trades."""
        return self.trades[-limit:]
