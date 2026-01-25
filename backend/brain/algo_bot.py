"""
QUANT INDUSTRY - Algorithmic Trading Bot
Automated trading strategies with ML-enhanced decision making
"""

import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class BotState(Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    WARMING_UP = "WARMING_UP"


class TradingStrategy(Enum):
    TREND_FOLLOWING = "TREND_FOLLOWING"
    MEAN_REVERSION = "MEAN_REVERSION"
    MOMENTUM = "MOMENTUM"
    BREAKOUT = "BREAKOUT"
    PAIRS_TRADING = "PAIRS_TRADING"
    SCALPING = "SCALPING"
    SWING_TRADING = "SWING_TRADING"
    OPTIONS_SELLING = "OPTIONS_SELLING"
    ML_ENSEMBLE = "ML_ENSEMBLE"


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"
    SCALE_IN = "SCALE_IN"
    SCALE_OUT = "SCALE_OUT"


@dataclass
class TradingSignal:
    signal_id: str
    symbol: str
    signal_type: SignalType
    strategy: TradingStrategy
    confidence: float
    price: float
    quantity: int
    timestamp: datetime = field(default_factory=datetime.now)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""
    executed: bool = False

    def to_dict(self) -> Dict:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "strategy": self.strategy.value,
            "confidence": round(self.confidence, 3),
            "price": self.price,
            "quantity": self.quantity,
            "timestamp": self.timestamp.isoformat(),
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "reason": self.reason,
            "executed": self.executed,
        }


@dataclass
class BotPosition:
    symbol: str
    side: str  # LONG or SHORT
    quantity: int
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    strategy: TradingStrategy
    entry_time: datetime
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "strategy": self.strategy.value,
            "entry_time": self.entry_time.isoformat(),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 2),
        }


@dataclass
class BotStats:
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    current_drawdown: float
    avg_holding_period: float

    def to_dict(self) -> Dict:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": round(self.total_pnl, 2),
            "win_rate": round(self.win_rate, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "profit_factor": round(self.profit_factor, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "current_drawdown": round(self.current_drawdown, 2),
            "avg_holding_period": round(self.avg_holding_period, 2),
        }


@dataclass
class BotConfig:
    name: str = "QuantBot_v10"
    strategy: TradingStrategy = TradingStrategy.ML_ENSEMBLE
    symbols: List[str] = field(default_factory=lambda: ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"])

    # Risk management
    max_position_size: float = 10000.0
    max_positions: int = 5
    max_daily_loss: float = 1000.0
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 4.0

    # Execution
    min_confidence: float = 0.6
    cooldown_minutes: int = 5
    paper_trading: bool = True

    # ML settings
    use_neural_signals: bool = True
    use_regime_filter: bool = True
    regime_allowed: List[str] = field(default_factory=lambda: ["BULL_STRONG", "BULL_WEAK", "RECOVERY"])

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "strategy": self.strategy.value,
            "symbols": self.symbols,
            "max_position_size": self.max_position_size,
            "max_positions": self.max_positions,
            "max_daily_loss": self.max_daily_loss,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "min_confidence": self.min_confidence,
            "cooldown_minutes": self.cooldown_minutes,
            "paper_trading": self.paper_trading,
            "use_neural_signals": self.use_neural_signals,
            "use_regime_filter": self.use_regime_filter,
            "regime_allowed": self.regime_allowed,
        }


class AlgoBot:
    """
    Algorithmic trading bot with multiple strategies and ML integration
    """

    def __init__(self, config: BotConfig = None, db_path: str = None):
        self.config = config or BotConfig()
        self.state = BotState.STOPPED
        self.positions: Dict[str, BotPosition] = {}
        self.signals: List[TradingSignal] = []
        self.trade_history: List[Dict] = []

        self.start_time: Optional[datetime] = None
        self.daily_pnl: float = 0.0
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.high_water_mark: float = 0.0

        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Last signal time per symbol (for cooldown)
        self._last_signal_time: Dict[str, datetime] = {}

        # Database
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "algobot.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        logger.info(f"AlgoBot initialized: {self.config.name}")

    def _init_db(self):
        """Initialize database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER,
                entry_price REAL,
                exit_price REAL,
                entry_time TEXT,
                exit_time TEXT,
                strategy TEXT,
                pnl REAL,
                pnl_pct REAL,
                status TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                strategy TEXT,
                confidence REAL,
                price REAL,
                quantity INTEGER,
                timestamp TEXT,
                reason TEXT,
                executed INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_equity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                equity REAL,
                daily_pnl REAL,
                position_count INTEGER
            )
        """)

        conn.commit()
        conn.close()

    def start(self):
        """Start the bot"""
        if self.state == BotState.RUNNING:
            logger.warning("Bot is already running")
            return

        self.state = BotState.WARMING_UP
        self.start_time = datetime.now()
        self._stop_event.clear()

        logger.info(f"Starting bot: {self.config.name}")

        # Start main loop in background thread
        self._thread = threading.Thread(target=self._main_loop, daemon=True)
        self._thread.start()

        self.state = BotState.RUNNING

    def stop(self):
        """Stop the bot"""
        if self.state == BotState.STOPPED:
            return

        logger.info("Stopping bot...")
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5)

        self.state = BotState.STOPPED

    def pause(self):
        """Pause the bot"""
        if self.state == BotState.RUNNING:
            self.state = BotState.PAUSED
            logger.info("Bot paused")

    def resume(self):
        """Resume the bot"""
        if self.state == BotState.PAUSED:
            self.state = BotState.RUNNING
            logger.info("Bot resumed")

    def _main_loop(self):
        """Main trading loop"""
        while not self._stop_event.is_set():
            try:
                if self.state == BotState.RUNNING:
                    self._process_cycle()
            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
                self.state = BotState.ERROR

            time.sleep(1)  # 1 second between cycles

    def _process_cycle(self):
        """Process one trading cycle"""
        # Check daily loss limit
        if self.daily_pnl <= -self.config.max_daily_loss:
            logger.warning("Daily loss limit reached, stopping bot")
            self.stop()
            return

        # Update positions
        self._update_positions()

        # Check stop loss and take profit
        self._check_exits()

        # Generate signals for each symbol
        for symbol in self.config.symbols:
            if self._can_generate_signal(symbol):
                signal = self._generate_signal(symbol)
                if signal and signal.confidence >= self.config.min_confidence:
                    self._process_signal(signal)

    def _can_generate_signal(self, symbol: str) -> bool:
        """Check if we can generate a signal for this symbol"""
        # Check cooldown
        last_time = self._last_signal_time.get(symbol)
        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds() / 60
            if elapsed < self.config.cooldown_minutes:
                return False

        # Check max positions
        if len(self.positions) >= self.config.max_positions:
            if symbol not in self.positions:
                return False

        return True

    def _generate_signal(self, symbol: str) -> Optional[TradingSignal]:
        """Generate trading signal for a symbol"""
        try:
            # Get market data
            from ..services.data_service import get_data_service
            data_service = get_data_service()

            quote = data_service.get_quote(symbol)
            if not quote:
                return None

            price = quote.get("price", 0)
            if price <= 0:
                return None

            # Get neural signal if enabled
            neural_score = 0
            if self.config.use_neural_signals:
                from .neural_engine import get_neural_engine
                neural_engine = get_neural_engine()

                historical = data_service.get_historical(symbol, "1d", 100)
                if historical:
                    analysis = neural_engine.analyze(symbol, historical)
                    neural_score = analysis.neural_score

            # Check regime if enabled
            if self.config.use_regime_filter:
                from .regime_detector import get_regime_detector
                regime_detector = get_regime_detector()

                # Get market data for regime detection
                market_data = {}
                for sym in ["SPY", "QQQ"]:
                    hist = data_service.get_historical(sym, "1d", 100)
                    if hist:
                        market_data[sym] = hist

                if market_data:
                    regime_analysis = regime_detector.detect_regime(market_data)
                    current_regime = regime_analysis.current_state.regime.value

                    if current_regime not in self.config.regime_allowed:
                        return None

            # Generate signal based on strategy
            signal = self._apply_strategy(symbol, price, neural_score)

            if signal:
                self._save_signal(signal)
                self.signals.append(signal)
                self._last_signal_time[symbol] = datetime.now()

            return signal

        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {e}")
            return None

    def _apply_strategy(
        self,
        symbol: str,
        price: float,
        neural_score: float
    ) -> Optional[TradingSignal]:
        """Apply trading strategy to generate signal"""
        strategy = self.config.strategy

        if strategy == TradingStrategy.ML_ENSEMBLE:
            return self._ml_ensemble_strategy(symbol, price, neural_score)
        elif strategy == TradingStrategy.TREND_FOLLOWING:
            return self._trend_following_strategy(symbol, price)
        elif strategy == TradingStrategy.MEAN_REVERSION:
            return self._mean_reversion_strategy(symbol, price)
        elif strategy == TradingStrategy.MOMENTUM:
            return self._momentum_strategy(symbol, price)
        else:
            return self._ml_ensemble_strategy(symbol, price, neural_score)

    def _ml_ensemble_strategy(
        self,
        symbol: str,
        price: float,
        neural_score: float
    ) -> Optional[TradingSignal]:
        """ML ensemble strategy combining multiple signals"""
        if abs(neural_score) < 20:
            return None  # No strong signal

        # Determine signal type and confidence
        if neural_score > 30:
            signal_type = SignalType.BUY
            confidence = min(neural_score / 100 + 0.5, 1.0)
        elif neural_score < -30:
            signal_type = SignalType.SELL
            confidence = min(abs(neural_score) / 100 + 0.5, 1.0)
        else:
            return None

        # Check if we already have a position
        if symbol in self.positions:
            pos = self.positions[symbol]
            if pos.side == "LONG" and signal_type == SignalType.SELL:
                signal_type = SignalType.CLOSE_LONG
            elif pos.side == "SHORT" and signal_type == SignalType.BUY:
                signal_type = SignalType.CLOSE_SHORT
            else:
                return None  # Same direction, skip

        # Calculate quantity
        quantity = int(self.config.max_position_size / price)
        if quantity <= 0:
            return None

        # Calculate stop loss and take profit
        if signal_type == SignalType.BUY:
            stop_loss = price * (1 - self.config.stop_loss_pct / 100)
            take_profit = price * (1 + self.config.take_profit_pct / 100)
        else:
            stop_loss = price * (1 + self.config.stop_loss_pct / 100)
            take_profit = price * (1 - self.config.take_profit_pct / 100)

        return TradingSignal(
            signal_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            signal_type=signal_type,
            strategy=TradingStrategy.ML_ENSEMBLE,
            confidence=confidence,
            price=price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=f"Neural score: {neural_score:.1f}",
        )

    def _trend_following_strategy(self, symbol: str, price: float) -> Optional[TradingSignal]:
        """Simple trend following strategy"""
        try:
            from ..services.data_service import get_data_service
            data_service = get_data_service()

            historical = data_service.get_historical(symbol, "1d", 50)
            if not historical or len(historical) < 50:
                return None

            closes = [d["close"] for d in historical]
            sma_20 = np.mean(closes[-20:])
            sma_50 = np.mean(closes[-50:])

            # Trend following: buy when price above both SMAs and 20 > 50
            if price > sma_20 > sma_50:
                signal_type = SignalType.BUY
                confidence = 0.65
            elif price < sma_20 < sma_50:
                signal_type = SignalType.SELL
                confidence = 0.65
            else:
                return None

            quantity = int(self.config.max_position_size / price)
            if quantity <= 0:
                return None

            return TradingSignal(
                signal_id=str(uuid.uuid4())[:8],
                symbol=symbol,
                signal_type=signal_type,
                strategy=TradingStrategy.TREND_FOLLOWING,
                confidence=confidence,
                price=price,
                quantity=quantity,
                stop_loss=price * (1 - self.config.stop_loss_pct / 100),
                take_profit=price * (1 + self.config.take_profit_pct / 100),
                reason=f"Price ${price:.2f} vs SMA20 ${sma_20:.2f} vs SMA50 ${sma_50:.2f}",
            )
        except Exception as e:
            logger.error(f"Error in trend following strategy: {e}")
            return None

    def _mean_reversion_strategy(self, symbol: str, price: float) -> Optional[TradingSignal]:
        """Mean reversion strategy using Bollinger Bands"""
        try:
            from ..services.data_service import get_data_service
            data_service = get_data_service()

            historical = data_service.get_historical(symbol, "1d", 20)
            if not historical or len(historical) < 20:
                return None

            closes = np.array([d["close"] for d in historical])
            sma = np.mean(closes)
            std = np.std(closes)

            upper_band = sma + 2 * std
            lower_band = sma - 2 * std

            # Mean reversion: buy at lower band, sell at upper band
            if price <= lower_band:
                signal_type = SignalType.BUY
                confidence = 0.7
            elif price >= upper_band:
                signal_type = SignalType.SELL
                confidence = 0.7
            else:
                return None

            quantity = int(self.config.max_position_size / price)
            if quantity <= 0:
                return None

            return TradingSignal(
                signal_id=str(uuid.uuid4())[:8],
                symbol=symbol,
                signal_type=signal_type,
                strategy=TradingStrategy.MEAN_REVERSION,
                confidence=confidence,
                price=price,
                quantity=quantity,
                stop_loss=price * (1 - self.config.stop_loss_pct / 100),
                take_profit=sma,  # Target mean
                reason=f"BB: Lower ${lower_band:.2f}, Upper ${upper_band:.2f}",
            )
        except Exception as e:
            logger.error(f"Error in mean reversion strategy: {e}")
            return None

    def _momentum_strategy(self, symbol: str, price: float) -> Optional[TradingSignal]:
        """Momentum strategy using RSI and rate of change"""
        try:
            from ..services.data_service import get_data_service
            data_service = get_data_service()

            historical = data_service.get_historical(symbol, "1d", 30)
            if not historical or len(historical) < 30:
                return None

            closes = np.array([d["close"] for d in historical])
            returns = np.diff(closes) / closes[:-1]

            # Calculate RSI
            gains = np.where(returns > 0, returns, 0)
            losses = np.where(returns < 0, -returns, 0)
            avg_gain = np.mean(gains[-14:])
            avg_loss = np.mean(losses[-14:])
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))

            # Calculate momentum (10-day ROC)
            roc = (closes[-1] / closes[-10] - 1) * 100

            # Momentum: strong RSI and positive ROC = buy
            if rsi > 50 and rsi < 70 and roc > 3:
                signal_type = SignalType.BUY
                confidence = 0.6 + (roc / 100)
            elif rsi < 50 and rsi > 30 and roc < -3:
                signal_type = SignalType.SELL
                confidence = 0.6 + (abs(roc) / 100)
            else:
                return None

            quantity = int(self.config.max_position_size / price)
            if quantity <= 0:
                return None

            return TradingSignal(
                signal_id=str(uuid.uuid4())[:8],
                symbol=symbol,
                signal_type=signal_type,
                strategy=TradingStrategy.MOMENTUM,
                confidence=min(confidence, 0.9),
                price=price,
                quantity=quantity,
                stop_loss=price * (1 - self.config.stop_loss_pct / 100),
                take_profit=price * (1 + self.config.take_profit_pct / 100),
                reason=f"RSI: {rsi:.1f}, ROC: {roc:.1f}%",
            )
        except Exception as e:
            logger.error(f"Error in momentum strategy: {e}")
            return None

    def _process_signal(self, signal: TradingSignal):
        """Process and execute a trading signal"""
        logger.info(f"Processing signal: {signal.symbol} {signal.signal_type.value}")

        with self.lock:
            if signal.signal_type in [SignalType.BUY, SignalType.SELL]:
                self._open_position(signal)
            elif signal.signal_type in [SignalType.CLOSE_LONG, SignalType.CLOSE_SHORT]:
                self._close_position(signal.symbol, signal.price)

            signal.executed = True

    def _open_position(self, signal: TradingSignal):
        """Open a new position"""
        side = "LONG" if signal.signal_type == SignalType.BUY else "SHORT"

        position = BotPosition(
            symbol=signal.symbol,
            side=side,
            quantity=signal.quantity,
            entry_price=signal.price,
            current_price=signal.price,
            stop_loss=signal.stop_loss or signal.price * 0.98,
            take_profit=signal.take_profit or signal.price * 1.04,
            strategy=signal.strategy,
            entry_time=datetime.now(),
        )

        self.positions[signal.symbol] = position

        # Save to database
        self._save_trade_entry(signal, position)

        logger.info(f"Opened {side} position: {signal.symbol} @ ${signal.price:.2f}")

    def _close_position(self, symbol: str, exit_price: float):
        """Close an existing position"""
        if symbol not in self.positions:
            return

        position = self.positions[symbol]

        # Calculate P&L
        if position.side == "LONG":
            pnl = (exit_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - exit_price) * position.quantity

        pnl_pct = pnl / (position.entry_price * position.quantity) * 100

        # Update daily P&L
        self.daily_pnl += pnl

        # Save to trade history
        trade = {
            "symbol": symbol,
            "side": position.side,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "entry_time": position.entry_time.isoformat(),
            "exit_time": datetime.now().isoformat(),
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "strategy": position.strategy.value,
        }
        self.trade_history.append(trade)

        # Update database
        self._save_trade_exit(symbol, exit_price, pnl, pnl_pct)

        # Remove position
        del self.positions[symbol]

        logger.info(f"Closed {position.side} position: {symbol} @ ${exit_price:.2f}, P&L: ${pnl:.2f}")

    def _update_positions(self):
        """Update current prices for all positions"""
        try:
            from ..services.data_service import get_data_service
            data_service = get_data_service()

            for symbol, position in self.positions.items():
                quote = data_service.get_quote(symbol)
                if quote:
                    position.current_price = quote.get("price", position.current_price)

                    # Update unrealized P&L
                    if position.side == "LONG":
                        position.unrealized_pnl = (position.current_price - position.entry_price) * position.quantity
                    else:
                        position.unrealized_pnl = (position.entry_price - position.current_price) * position.quantity

                    position.unrealized_pnl_pct = position.unrealized_pnl / (position.entry_price * position.quantity) * 100

        except Exception as e:
            logger.error(f"Error updating positions: {e}")

    def _check_exits(self):
        """Check for stop loss and take profit exits"""
        symbols_to_close = []

        for symbol, position in self.positions.items():
            should_close = False
            reason = ""

            if position.side == "LONG":
                if position.current_price <= position.stop_loss:
                    should_close = True
                    reason = "Stop loss hit"
                elif position.current_price >= position.take_profit:
                    should_close = True
                    reason = "Take profit hit"
            elif position.current_price >= position.stop_loss:
                should_close = True
                reason = "Stop loss hit"
            elif position.current_price <= position.take_profit:
                should_close = True
                reason = "Take profit hit"

            if should_close:
                logger.info(f"{symbol}: {reason} @ ${position.current_price:.2f}")
                symbols_to_close.append((symbol, position.current_price))

        # Close positions
        for symbol, price in symbols_to_close:
            self._close_position(symbol, price)

    def get_status(self) -> Dict:
        """Get bot status"""
        with self.lock:
            return {
                "state": self.state.value,
                "name": self.config.name,
                "strategy": self.config.strategy.value,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "uptime_minutes": (datetime.now() - self.start_time).total_seconds() / 60 if self.start_time else 0,
                "positions": [p.to_dict() for p in self.positions.values()],
                "position_count": len(self.positions),
                "daily_pnl": round(self.daily_pnl, 2),
                "signals_today": len([s for s in self.signals if s.timestamp.date() == datetime.now().date()]),
                "config": self.config.to_dict(),
            }

    def get_stats(self) -> BotStats:
        """Get bot statistics"""
        if not self.trade_history:
            return BotStats(
                total_trades=0, winning_trades=0, losing_trades=0,
                total_pnl=0, win_rate=0, avg_win=0, avg_loss=0,
                profit_factor=0, sharpe_ratio=0, max_drawdown=0,
                current_drawdown=0, avg_holding_period=0
            )

        wins = [t for t in self.trade_history if t["pnl"] > 0]
        losses = [t for t in self.trade_history if t["pnl"] <= 0]

        total_pnl = sum(t["pnl"] for t in self.trade_history)
        avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0
        avg_loss = np.mean([t["pnl"] for t in losses]) if losses else 0

        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Calculate Sharpe ratio (simplified)
        pnls = [t["pnl"] for t in self.trade_history]
        if len(pnls) > 1:
            sharpe = np.mean(pnls) / np.std(pnls) * np.sqrt(252) if np.std(pnls) > 0 else 0
        else:
            sharpe = 0

        # Calculate max drawdown from equity curve
        equity_curve = []
        running_pnl = 0
        for t in self.trade_history:
            running_pnl += t["pnl"]
            equity_curve.append(running_pnl)

        max_drawdown = 0
        current_drawdown = 0
        if equity_curve:
            peak = equity_curve[0]
            for equity in equity_curve:
                if equity > peak:
                    peak = equity
                drawdown = peak - equity
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            # Current drawdown from peak
            if equity_curve:
                current_peak = max(equity_curve)
                current_drawdown = current_peak - equity_curve[-1]

        # Calculate average holding period from trade times
        holding_periods = []
        for t in self.trade_history:
            try:
                entry = datetime.fromisoformat(t["entry_time"])
                exit_time = datetime.fromisoformat(t["exit_time"])
                holding_minutes = (exit_time - entry).total_seconds() / 60
                holding_periods.append(holding_minutes)
            except (KeyError, ValueError):
                pass
        avg_holding_period = np.mean(holding_periods) if holding_periods else 0

        return BotStats(
            total_trades=len(self.trade_history),
            winning_trades=len(wins),
            losing_trades=len(losses),
            total_pnl=total_pnl,
            win_rate=len(wins) / len(self.trade_history) * 100 if self.trade_history else 0,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            avg_holding_period=avg_holding_period,
        )

    def _save_signal(self, signal: TradingSignal):
        """Save signal to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_signals
                (signal_id, symbol, signal_type, strategy, confidence, price,
                 quantity, timestamp, reason, executed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.signal_id,
                signal.symbol,
                signal.signal_type.value,
                signal.strategy.value,
                signal.confidence,
                signal.price,
                signal.quantity,
                signal.timestamp.isoformat(),
                signal.reason,
                1 if signal.executed else 0
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving signal: {e}")

    def _save_trade_entry(self, signal: TradingSignal, position: BotPosition):
        """Save trade entry to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_trades
                (signal_id, symbol, side, quantity, entry_price, entry_time, strategy, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.signal_id,
                signal.symbol,
                position.side,
                position.quantity,
                position.entry_price,
                position.entry_time.isoformat(),
                position.strategy.value,
                "OPEN"
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving trade entry: {e}")

    def _save_trade_exit(self, symbol: str, exit_price: float, pnl: float, pnl_pct: float):
        """Save trade exit to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE bot_trades
                SET exit_price = ?, exit_time = ?, pnl = ?, pnl_pct = ?, status = ?
                WHERE symbol = ? AND status = 'OPEN'
            """, (
                exit_price,
                datetime.now().isoformat(),
                pnl,
                pnl_pct,
                "CLOSED",
                symbol
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving trade exit: {e}")


# Singleton instance
_algo_bot: Optional[AlgoBot] = None

def get_algo_bot() -> AlgoBot:
    global _algo_bot
    if _algo_bot is None:
        _algo_bot = AlgoBot()
    return _algo_bot
