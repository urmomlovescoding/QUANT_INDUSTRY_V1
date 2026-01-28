"""
QUANT_INDUSTRY_V1 ICT/Smart Money Concepts Strategies

Institutional-grade trading strategies based on Inner Circle Trader (ICT)
and Smart Money Concepts (SMC) methodologies.

Includes:
- Fair Value Gaps (FVG)
- Order Blocks
- Breaker Blocks
- Liquidity Sweeps
- Market Structure Shifts
- Kill Zones
- Optimal Trade Entry (OTE)
- Premium/Discount Zones
- Displacement Detection
- Inducement Patterns

Rollback Plan: Delete this file
Tests Required: Strategy signal validation, backtest verification
Failure Modes: Invalid data -> skip signal, alert operators
"""

import numpy as np
import logging
from datetime import datetime, timezone, time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid

from strategies.base import BaseStrategy, StrategyConfig, Signal, SignalDirection

logger = logging.getLogger(__name__)


# =============================================================================
# ICT/SMC DATA STRUCTURES
# =============================================================================

class MarketStructure(Enum):
    """Market structure types."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    CONSOLIDATION = "consolidation"
    UNKNOWN = "unknown"


class SwingType(Enum):
    """Swing point types."""
    SWING_HIGH = "swing_high"
    SWING_LOW = "swing_low"


class SessionType(Enum):
    """Trading session types."""
    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK_AM = "new_york_am"
    NEW_YORK_PM = "new_york_pm"
    LONDON_CLOSE = "london_close"


@dataclass
class SwingPoint:
    """Swing high/low point."""
    index: int
    price: float
    swing_type: SwingType
    timestamp: datetime = None
    is_broken: bool = False
    broken_at: int = None


@dataclass
class FairValueGap:
    """Fair Value Gap (imbalance) structure."""
    index: int
    high: float  # Top of gap
    low: float  # Bottom of gap
    midpoint: float
    direction: str  # 'bullish' or 'bearish'
    is_filled: bool = False
    fill_percentage: float = 0.0
    timestamp: datetime = None

    @property
    def size(self) -> float:
        """Gap size in price."""
        return self.high - self.low

    def is_price_in_gap(self, price: float) -> bool:
        """Check if price is within the gap."""
        return self.low <= price <= self.high


@dataclass
class OrderBlock:
    """Order Block structure (institutional supply/demand zone)."""
    index: int
    high: float
    low: float
    open_price: float
    close_price: float
    direction: str  # 'bullish' or 'bearish'
    is_mitigated: bool = False
    mitigation_index: int = None
    strength: float = 1.0  # Based on move after OB
    timestamp: datetime = None

    @property
    def body_high(self) -> float:
        """Top of candle body."""
        return max(self.open_price, self.close_price)

    @property
    def body_low(self) -> float:
        """Bottom of candle body."""
        return min(self.open_price, self.close_price)


@dataclass
class BreakerBlock:
    """Breaker Block (failed order block that becomes support/resistance)."""
    index: int
    high: float
    low: float
    original_direction: str
    new_direction: str
    timestamp: datetime = None


@dataclass
class LiquiditySweep:
    """Liquidity sweep (stop hunt) structure."""
    index: int
    sweep_price: float
    direction: str  # 'above' or 'below'
    liquidity_level: float
    reversal_confirmed: bool = False
    timestamp: datetime = None


@dataclass
class KillZone:
    """Kill Zone (optimal trading session)."""
    session: SessionType
    start_time: time
    end_time: time
    weight: float = 1.0  # Importance multiplier


# =============================================================================
# ICT ANALYSIS ENGINE
# =============================================================================

class ICTAnalyzer:
    """
    Core ICT/SMC analysis engine.

    Identifies institutional price action patterns:
    - Market structure (HH, HL, LH, LL)
    - Fair Value Gaps
    - Order Blocks
    - Liquidity levels
    - Kill zones
    """

    # Kill Zone definitions (UTC times)
    KILL_ZONES = [
        KillZone(SessionType.ASIAN, time(0, 0), time(6, 0), 0.7),
        KillZone(SessionType.LONDON, time(7, 0), time(10, 0), 1.0),
        KillZone(SessionType.NEW_YORK_AM, time(12, 0), time(15, 0), 1.0),
        KillZone(SessionType.NEW_YORK_PM, time(15, 0), time(17, 0), 0.8),
        KillZone(SessionType.LONDON_CLOSE, time(15, 0), time(16, 0), 0.9),
    ]

    def __init__(
        self,
        swing_lookback: int = 5,
        fvg_min_size_atr: float = 0.5,
        ob_min_move_atr: float = 1.5,
        structure_lookback: int = 20,
    ):
        self.swing_lookback = swing_lookback
        self.fvg_min_size_atr = fvg_min_size_atr
        self.ob_min_move_atr = ob_min_move_atr
        self.structure_lookback = structure_lookback

        # State
        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []
        self.fvgs: List[FairValueGap] = []
        self.order_blocks: List[OrderBlock] = []
        self.breaker_blocks: List[BreakerBlock] = []
        self.liquidity_sweeps: List[LiquiditySweep] = []
        self.market_structure = MarketStructure.UNKNOWN

    def analyze(
        self,
        open_prices: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray,
        volumes: np.ndarray = None,
        timestamps: List[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Full ICT analysis on price data.

        Returns comprehensive ICT state including:
        - Market structure
        - Active FVGs
        - Order blocks
        - Liquidity levels
        """
        n = len(close_prices)
        if n < self.structure_lookback:
            return self._empty_analysis()

        # Calculate ATR for dynamic sizing
        atr = self._calculate_atr(high_prices, low_prices, close_prices)

        # Find swing points
        self.swing_highs, self.swing_lows = self._find_swing_points(
            high_prices, low_prices, timestamps
        )

        # Determine market structure
        self.market_structure = self._determine_market_structure()

        # Find Fair Value Gaps
        self.fvgs = self._find_fvgs(
            high_prices, low_prices, atr, timestamps
        )

        # Find Order Blocks
        self.order_blocks = self._find_order_blocks(
            open_prices, high_prices, low_prices, close_prices, atr, timestamps
        )

        # Check for breaker blocks
        self.breaker_blocks = self._find_breaker_blocks()

        # Find liquidity sweeps
        self.liquidity_sweeps = self._find_liquidity_sweeps(
            high_prices, low_prices, timestamps
        )

        # Update mitigation status
        self._update_mitigation_status(high_prices, low_prices)

        return {
            'market_structure': self.market_structure,
            'swing_highs': self.swing_highs,
            'swing_lows': self.swing_lows,
            'fvgs': [f for f in self.fvgs if not f.is_filled],
            'order_blocks': [ob for ob in self.order_blocks if not ob.is_mitigated],
            'breaker_blocks': self.breaker_blocks,
            'liquidity_sweeps': self.liquidity_sweeps,
            'atr': atr[-1] if len(atr) > 0 else 0,
        }

    def _calculate_atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """Calculate Average True Range."""
        n = len(high)
        if n < 2:
            return np.array([0.0])

        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
        )
        tr = np.concatenate([[high[0] - low[0]], tr])

        # EMA of TR
        atr = np.zeros(n)
        atr[:period] = np.mean(tr[:period])
        multiplier = 2 / (period + 1)
        for i in range(period, n):
            atr[i] = tr[i] * multiplier + atr[i-1] * (1 - multiplier)

        return atr

    def _find_swing_points(
        self,
        high: np.ndarray,
        low: np.ndarray,
        timestamps: List[datetime] = None,
    ) -> Tuple[List[SwingPoint], List[SwingPoint]]:
        """Find swing highs and lows."""
        n = len(high)
        swing_highs = []
        swing_lows = []
        lb = self.swing_lookback

        for i in range(lb, n - lb):
            # Swing High
            if all(high[i] > high[i-j] for j in range(1, lb+1)) and \
               all(high[i] > high[i+j] for j in range(1, lb+1)):
                swing_highs.append(SwingPoint(
                    index=i,
                    price=high[i],
                    swing_type=SwingType.SWING_HIGH,
                    timestamp=timestamps[i] if timestamps else None,
                ))

            # Swing Low
            if all(low[i] < low[i-j] for j in range(1, lb+1)) and \
               all(low[i] < low[i+j] for j in range(1, lb+1)):
                swing_lows.append(SwingPoint(
                    index=i,
                    price=low[i],
                    swing_type=SwingType.SWING_LOW,
                    timestamp=timestamps[i] if timestamps else None,
                ))

        return swing_highs, swing_lows

    def _determine_market_structure(self) -> MarketStructure:
        """Determine market structure from swing points."""
        if len(self.swing_highs) < 2 or len(self.swing_lows) < 2:
            return MarketStructure.UNKNOWN

        # Get recent swings
        recent_highs = sorted(self.swing_highs[-4:], key=lambda x: x.index)
        recent_lows = sorted(self.swing_lows[-4:], key=lambda x: x.index)

        if len(recent_highs) < 2 or len(recent_lows) < 2:
            return MarketStructure.UNKNOWN

        # Check for Higher Highs and Higher Lows (Bullish)
        hh = recent_highs[-1].price > recent_highs[-2].price
        hl = recent_lows[-1].price > recent_lows[-2].price

        # Check for Lower Highs and Lower Lows (Bearish)
        lh = recent_highs[-1].price < recent_highs[-2].price
        ll = recent_lows[-1].price < recent_lows[-2].price

        if hh and hl:
            return MarketStructure.BULLISH
        elif lh and ll:
            return MarketStructure.BEARISH
        else:
            return MarketStructure.CONSOLIDATION

    def _find_fvgs(
        self,
        high: np.ndarray,
        low: np.ndarray,
        atr: np.ndarray,
        timestamps: List[datetime] = None,
    ) -> List[FairValueGap]:
        """Find Fair Value Gaps (imbalances)."""
        fvgs = []
        n = len(high)

        for i in range(2, n):
            min_gap_size = atr[i] * self.fvg_min_size_atr if i < len(atr) else 0.001

            # Bullish FVG: Gap between candle 1's high and candle 3's low
            if low[i] > high[i-2]:
                gap_size = low[i] - high[i-2]
                if gap_size >= min_gap_size:
                    fvgs.append(FairValueGap(
                        index=i,
                        high=low[i],
                        low=high[i-2],
                        midpoint=(low[i] + high[i-2]) / 2,
                        direction='bullish',
                        timestamp=timestamps[i] if timestamps else None,
                    ))

            # Bearish FVG: Gap between candle 1's low and candle 3's high
            if high[i] < low[i-2]:
                gap_size = low[i-2] - high[i]
                if gap_size >= min_gap_size:
                    fvgs.append(FairValueGap(
                        index=i,
                        high=low[i-2],
                        low=high[i],
                        midpoint=(low[i-2] + high[i]) / 2,
                        direction='bearish',
                        timestamp=timestamps[i] if timestamps else None,
                    ))

        return fvgs

    def _find_order_blocks(
        self,
        open_prices: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        atr: np.ndarray,
        timestamps: List[datetime] = None,
    ) -> List[OrderBlock]:
        """Find Order Blocks (institutional supply/demand zones)."""
        order_blocks = []
        n = len(close)

        for i in range(1, n - 3):
            min_move = atr[i] * self.ob_min_move_atr if i < len(atr) else 0.01

            # Bullish OB: Last down candle before up move
            is_down_candle = close[i] < open_prices[i]
            future_move_up = close[i+3] - close[i] if i + 3 < n else 0

            if is_down_candle and future_move_up > min_move:
                strength = future_move_up / atr[i] if atr[i] > 0 else 1.0
                order_blocks.append(OrderBlock(
                    index=i,
                    high=high[i],
                    low=low[i],
                    open_price=open_prices[i],
                    close_price=close[i],
                    direction='bullish',
                    strength=min(strength, 3.0),
                    timestamp=timestamps[i] if timestamps else None,
                ))

            # Bearish OB: Last up candle before down move
            is_up_candle = close[i] > open_prices[i]
            future_move_down = close[i] - close[i+3] if i + 3 < n else 0

            if is_up_candle and future_move_down > min_move:
                strength = future_move_down / atr[i] if atr[i] > 0 else 1.0
                order_blocks.append(OrderBlock(
                    index=i,
                    high=high[i],
                    low=low[i],
                    open_price=open_prices[i],
                    close_price=close[i],
                    direction='bearish',
                    strength=min(strength, 3.0),
                    timestamp=timestamps[i] if timestamps else None,
                ))

        return order_blocks

    def _find_breaker_blocks(self) -> List[BreakerBlock]:
        """Find Breaker Blocks (failed order blocks)."""
        breakers = []

        for ob in self.order_blocks:
            if ob.is_mitigated:
                new_direction = 'bearish' if ob.direction == 'bullish' else 'bullish'
                breakers.append(BreakerBlock(
                    index=ob.mitigation_index or ob.index,
                    high=ob.high,
                    low=ob.low,
                    original_direction=ob.direction,
                    new_direction=new_direction,
                    timestamp=ob.timestamp,
                ))

        return breakers

    def _find_liquidity_sweeps(
        self,
        high: np.ndarray,
        low: np.ndarray,
        timestamps: List[datetime] = None,
    ) -> List[LiquiditySweep]:
        """Find liquidity sweeps (stop hunts)."""
        sweeps = []

        # Check if recent price swept swing highs/lows
        for sh in self.swing_highs[-10:]:
            if sh.is_broken and not sh.index in [s.index for s in sweeps]:
                # Check for reversal after sweep
                if sh.broken_at and sh.broken_at < len(high) - 1:
                    next_close = high[sh.broken_at + 1] if sh.broken_at + 1 < len(high) else high[-1]
                    reversal = next_close < sh.price
                    sweeps.append(LiquiditySweep(
                        index=sh.broken_at,
                        sweep_price=high[sh.broken_at],
                        direction='above',
                        liquidity_level=sh.price,
                        reversal_confirmed=reversal,
                        timestamp=timestamps[sh.broken_at] if timestamps and sh.broken_at < len(timestamps) else None,
                    ))

        for sl in self.swing_lows[-10:]:
            if sl.is_broken and not sl.index in [s.index for s in sweeps]:
                if sl.broken_at and sl.broken_at < len(low) - 1:
                    next_close = low[sl.broken_at + 1] if sl.broken_at + 1 < len(low) else low[-1]
                    reversal = next_close > sl.price
                    sweeps.append(LiquiditySweep(
                        index=sl.broken_at,
                        sweep_price=low[sl.broken_at],
                        direction='below',
                        liquidity_level=sl.price,
                        reversal_confirmed=reversal,
                        timestamp=timestamps[sl.broken_at] if timestamps and sl.broken_at < len(timestamps) else None,
                    ))

        return sweeps

    def _update_mitigation_status(
        self,
        high: np.ndarray,
        low: np.ndarray,
    ) -> None:
        """Update mitigation/fill status of FVGs and Order Blocks."""
        current_high = high[-1]
        current_low = low[-1]
        current_idx = len(high) - 1

        # Update FVG fill status
        for fvg in self.fvgs:
            if not fvg.is_filled:
                if fvg.direction == 'bullish':
                    # Bearish price action fills bullish FVG
                    if current_low <= fvg.midpoint:
                        fvg.fill_percentage = min(1.0, (fvg.high - current_low) / fvg.size)
                        if current_low <= fvg.low:
                            fvg.is_filled = True
                else:
                    # Bullish price action fills bearish FVG
                    if current_high >= fvg.midpoint:
                        fvg.fill_percentage = min(1.0, (current_high - fvg.low) / fvg.size)
                        if current_high >= fvg.high:
                            fvg.is_filled = True

        # Update Order Block mitigation
        for ob in self.order_blocks:
            if not ob.is_mitigated:
                if ob.direction == 'bullish':
                    # Price entering OB zone
                    if current_low <= ob.body_high:
                        ob.is_mitigated = True
                        ob.mitigation_index = current_idx
                else:
                    if current_high >= ob.body_low:
                        ob.is_mitigated = True
                        ob.mitigation_index = current_idx

        # Update swing point breaks
        for sh in self.swing_highs:
            if not sh.is_broken and current_high > sh.price:
                sh.is_broken = True
                sh.broken_at = current_idx

        for sl in self.swing_lows:
            if not sl.is_broken and current_low < sl.price:
                sl.is_broken = True
                sl.broken_at = current_idx

    def get_premium_discount_zones(
        self,
        high: np.ndarray,
        low: np.ndarray,
        lookback: int = 20,
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculate premium and discount zones.

        Premium: Upper 50% of range (sell zone)
        Discount: Lower 50% of range (buy zone)
        """
        if len(high) < lookback:
            return {'premium': (0, 0), 'discount': (0, 0), 'equilibrium': 0}

        range_high = np.max(high[-lookback:])
        range_low = np.min(low[-lookback:])
        equilibrium = (range_high + range_low) / 2

        return {
            'premium': (equilibrium, range_high),
            'discount': (range_low, equilibrium),
            'equilibrium': equilibrium,
            'range_high': range_high,
            'range_low': range_low,
        }

    def is_kill_zone(self, timestamp: datetime = None) -> Tuple[bool, Optional[KillZone]]:
        """Check if current time is in a kill zone."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        current_time = timestamp.time()

        for kz in self.KILL_ZONES:
            if kz.start_time <= current_time <= kz.end_time:
                return True, kz

        return False, None

    def get_optimal_trade_entry(
        self,
        swing_high: float,
        swing_low: float,
    ) -> Dict[str, float]:
        """
        Calculate Optimal Trade Entry (OTE) zones.

        Uses Fibonacci retracement levels:
        - 62% (0.62 of range)
        - 70.5% (sweet spot)
        - 79% (deep discount)
        """
        range_size = swing_high - swing_low

        return {
            'ote_62': swing_low + range_size * 0.62,
            'ote_705': swing_low + range_size * 0.705,
            'ote_79': swing_low + range_size * 0.79,
            'fib_50': swing_low + range_size * 0.5,
            'fib_382': swing_low + range_size * 0.382,
        }

    def detect_displacement(
        self,
        open_prices: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        atr: np.ndarray,
        threshold_atr: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """
        Detect displacement candles (strong institutional moves).

        Displacement = Large body candle indicating institutional activity.
        """
        displacements = []
        n = len(close)

        for i in range(1, n):
            body_size = abs(close[i] - open_prices[i])
            total_range = high[i] - low[i]

            if total_range == 0:
                continue

            # Body should be at least 70% of total range
            body_ratio = body_size / total_range

            # Size should exceed threshold * ATR
            if i < len(atr) and body_size > atr[i] * threshold_atr and body_ratio > 0.7:
                direction = 'bullish' if close[i] > open_prices[i] else 'bearish'
                displacements.append({
                    'index': i,
                    'direction': direction,
                    'body_size': body_size,
                    'atr_multiple': body_size / atr[i] if atr[i] > 0 else 0,
                    'body_ratio': body_ratio,
                })

        return displacements

    def detect_inducement(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Detect inducement patterns (retail traps).

        Inducement occurs when price takes out a minor level
        to trap retail traders before reversing.
        """
        inducements = []
        n = len(close)

        # Look for minor swing breaks followed by reversal
        for i in range(self.swing_lookback + 5, n):
            # Check recent price action
            recent_high = np.max(high[i-5:i])
            recent_low = np.min(low[i-5:i])
            current_close = close[i]

            # Bullish inducement: Sweep below then close above
            if low[i] < recent_low and current_close > recent_low:
                inducements.append({
                    'index': i,
                    'type': 'bullish',
                    'trap_level': recent_low,
                    'sweep_low': low[i],
                    'recovery_close': current_close,
                })

            # Bearish inducement: Sweep above then close below
            if high[i] > recent_high and current_close < recent_high:
                inducements.append({
                    'index': i,
                    'type': 'bearish',
                    'trap_level': recent_high,
                    'sweep_high': high[i],
                    'recovery_close': current_close,
                })

        return inducements

    def _empty_analysis(self) -> Dict[str, Any]:
        """Return empty analysis result."""
        return {
            'market_structure': MarketStructure.UNKNOWN,
            'swing_highs': [],
            'swing_lows': [],
            'fvgs': [],
            'order_blocks': [],
            'breaker_blocks': [],
            'liquidity_sweeps': [],
            'atr': 0,
        }


# =============================================================================
# ICT STRATEGIES
# =============================================================================

class FairValueGapStrategy(BaseStrategy):
    """
    Fair Value Gap (FVG) Trading Strategy.

    Trades into unfilled gaps expecting price to return
    and respect the imbalance zone.
    """

    def __init__(self, config: StrategyConfig = None):
        if config is None:
            config = StrategyConfig(
                name="ICT Fair Value Gap",
                parameters={
                    'min_gap_size_atr': 0.5,
                    'max_gap_age': 50,  # Bars
                    'fill_threshold': 0.5,  # 50% filled triggers entry
                    'structure_aligned': True,  # Only trade with structure
                }
            )
        super().__init__(config)
        self.analyzer = ICTAnalyzer()

    def generate_signals(
        self,
        data: Dict[str, Any],
        features: Dict[str, np.ndarray] = None,
        regime: str = None
    ) -> List[Signal]:
        signals = []

        for symbol in self.config.symbols or data.keys():
            if symbol not in data:
                continue

            ohlcv = data[symbol]
            open_p = np.array(ohlcv.get('open', []))
            high = np.array(ohlcv.get('high', []))
            low = np.array(ohlcv.get('low', []))
            close = np.array(ohlcv.get('close', []))
            volume = np.array(ohlcv.get('volume', []))

            if len(close) < 30:
                continue

            analysis = self.analyzer.analyze(open_p, high, low, close, volume)

            # Get unfilled FVGs
            active_fvgs = analysis['fvgs']
            structure = analysis['market_structure']
            current_price = close[-1]

            for fvg in active_fvgs[-5:]:  # Recent FVGs only
                # Check if price is approaching FVG
                if fvg.direction == 'bullish' and structure == MarketStructure.BULLISH:
                    # Price approaching from above
                    if fvg.low < current_price < fvg.high * 1.01:
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.LONG,
                            strength=0.7 * fvg.size / analysis['atr'] if analysis['atr'] > 0 else 0.7,
                            confidence=0.65,
                            entry_price=fvg.midpoint,
                            stop_loss=fvg.low - analysis['atr'],
                            take_profit=current_price + 2 * (current_price - fvg.low),
                            metadata={
                                'strategy': 'FVG',
                                'fvg_direction': fvg.direction,
                                'gap_size': fvg.size,
                                'structure': structure.value,
                            },
                        ))

                elif fvg.direction == 'bearish' and structure == MarketStructure.BEARISH:
                    # Price approaching from below
                    if fvg.low * 0.99 < current_price < fvg.high:
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.SHORT,
                            strength=0.7 * fvg.size / analysis['atr'] if analysis['atr'] > 0 else 0.7,
                            confidence=0.65,
                            entry_price=fvg.midpoint,
                            stop_loss=fvg.high + analysis['atr'],
                            take_profit=current_price - 2 * (fvg.high - current_price),
                            metadata={
                                'strategy': 'FVG',
                                'fvg_direction': fvg.direction,
                                'gap_size': fvg.size,
                                'structure': structure.value,
                            },
                        ))

        return signals


class OrderBlockStrategy(BaseStrategy):
    """
    Order Block Trading Strategy.

    Trades retracements to institutional supply/demand zones.
    """

    def __init__(self, config: StrategyConfig = None):
        if config is None:
            config = StrategyConfig(
                name="ICT Order Block",
                parameters={
                    'min_ob_strength': 1.5,
                    'max_ob_age': 100,
                    'require_fvg': False,  # Optional FVG confluence
                    'require_kill_zone': True,
                }
            )
        super().__init__(config)
        self.analyzer = ICTAnalyzer()

    def generate_signals(
        self,
        data: Dict[str, Any],
        features: Dict[str, np.ndarray] = None,
        regime: str = None
    ) -> List[Signal]:
        signals = []

        for symbol in self.config.symbols or data.keys():
            if symbol not in data:
                continue

            ohlcv = data[symbol]
            open_p = np.array(ohlcv.get('open', []))
            high = np.array(ohlcv.get('high', []))
            low = np.array(ohlcv.get('low', []))
            close = np.array(ohlcv.get('close', []))
            volume = np.array(ohlcv.get('volume', []))

            if len(close) < 50:
                continue

            analysis = self.analyzer.analyze(open_p, high, low, close, volume)
            structure = analysis['market_structure']
            current_price = close[-1]
            atr = analysis['atr']

            # Check kill zone if required
            in_kill_zone, kz = self.analyzer.is_kill_zone()
            if self.config.parameters.get('require_kill_zone', True) and not in_kill_zone:
                continue

            kill_zone_weight = kz.weight if kz else 1.0

            for ob in analysis['order_blocks'][-10:]:
                if ob.strength < self.config.parameters.get('min_ob_strength', 1.5):
                    continue

                # Bullish OB: Price returning to demand zone
                if ob.direction == 'bullish' and structure in [MarketStructure.BULLISH, MarketStructure.CONSOLIDATION]:
                    if ob.body_low < current_price < ob.body_high * 1.005:
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.LONG,
                            strength=min(0.9, 0.6 + ob.strength * 0.1) * kill_zone_weight,
                            confidence=min(0.85, 0.5 + ob.strength * 0.1),
                            entry_price=ob.body_low,
                            stop_loss=ob.low - atr * 0.5,
                            take_profit=current_price + 3 * (current_price - ob.body_low),
                            metadata={
                                'strategy': 'OrderBlock',
                                'ob_direction': ob.direction,
                                'ob_strength': ob.strength,
                                'structure': structure.value,
                                'kill_zone': kz.session.value if kz else None,
                            },
                        ))

                # Bearish OB: Price returning to supply zone
                elif ob.direction == 'bearish' and structure in [MarketStructure.BEARISH, MarketStructure.CONSOLIDATION]:
                    if ob.body_low * 0.995 < current_price < ob.body_high:
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.SHORT,
                            strength=min(0.9, 0.6 + ob.strength * 0.1) * kill_zone_weight,
                            confidence=min(0.85, 0.5 + ob.strength * 0.1),
                            entry_price=ob.body_high,
                            stop_loss=ob.high + atr * 0.5,
                            take_profit=current_price - 3 * (ob.body_high - current_price),
                            metadata={
                                'strategy': 'OrderBlock',
                                'ob_direction': ob.direction,
                                'ob_strength': ob.strength,
                                'structure': structure.value,
                                'kill_zone': kz.session.value if kz else None,
                            },
                        ))

        return signals


class LiquiditySweepStrategy(BaseStrategy):
    """
    Liquidity Sweep (Stop Hunt) Strategy.

    Trades reversals after price sweeps obvious liquidity levels.
    """

    def __init__(self, config: StrategyConfig = None):
        if config is None:
            config = StrategyConfig(
                name="ICT Liquidity Sweep",
                parameters={
                    'require_reversal_candle': True,
                    'min_sweep_distance_atr': 0.3,
                    'confirmation_bars': 1,
                }
            )
        super().__init__(config)
        self.analyzer = ICTAnalyzer()

    def generate_signals(
        self,
        data: Dict[str, Any],
        features: Dict[str, np.ndarray] = None,
        regime: str = None
    ) -> List[Signal]:
        signals = []

        for symbol in self.config.symbols or data.keys():
            if symbol not in data:
                continue

            ohlcv = data[symbol]
            open_p = np.array(ohlcv.get('open', []))
            high = np.array(ohlcv.get('high', []))
            low = np.array(ohlcv.get('low', []))
            close = np.array(ohlcv.get('close', []))
            volume = np.array(ohlcv.get('volume', []))

            if len(close) < 50:
                continue

            analysis = self.analyzer.analyze(open_p, high, low, close, volume)
            current_price = close[-1]
            atr = analysis['atr']

            for sweep in analysis['liquidity_sweeps'][-3:]:
                # Only trade confirmed reversals
                if not sweep.reversal_confirmed:
                    continue

                # Bullish reversal after sweep below
                if sweep.direction == 'below':
                    signals.append(Signal(
                        strategy_id=self.strategy_id,
                        symbol=symbol,
                        direction=SignalDirection.LONG,
                        strength=0.8,
                        confidence=0.7,
                        entry_price=current_price,
                        stop_loss=sweep.sweep_price - atr * 0.5,
                        take_profit=current_price + 2 * (current_price - sweep.sweep_price),
                        metadata={
                            'strategy': 'LiquiditySweep',
                            'sweep_direction': sweep.direction,
                            'liquidity_level': sweep.liquidity_level,
                            'sweep_price': sweep.sweep_price,
                        },
                    ))

                # Bearish reversal after sweep above
                elif sweep.direction == 'above':
                    signals.append(Signal(
                        strategy_id=self.strategy_id,
                        symbol=symbol,
                        direction=SignalDirection.SHORT,
                        strength=0.8,
                        confidence=0.7,
                        entry_price=current_price,
                        stop_loss=sweep.sweep_price + atr * 0.5,
                        take_profit=current_price - 2 * (sweep.sweep_price - current_price),
                        metadata={
                            'strategy': 'LiquiditySweep',
                            'sweep_direction': sweep.direction,
                            'liquidity_level': sweep.liquidity_level,
                            'sweep_price': sweep.sweep_price,
                        },
                    ))

        return signals


class MarketStructureShiftStrategy(BaseStrategy):
    """
    Market Structure Shift (MSS/BOS/CHoCH) Strategy.

    Trades structural breaks and changes of character.
    - BOS: Break of Structure (continuation)
    - CHoCH: Change of Character (reversal)
    """

    def __init__(self, config: StrategyConfig = None):
        if config is None:
            config = StrategyConfig(
                name="ICT Market Structure Shift",
                parameters={
                    'lookback_swings': 3,
                    'require_displacement': True,
                    'min_structure_breaks': 1,
                }
            )
        super().__init__(config)
        self.analyzer = ICTAnalyzer()
        self.previous_structure = MarketStructure.UNKNOWN

    def generate_signals(
        self,
        data: Dict[str, Any],
        features: Dict[str, np.ndarray] = None,
        regime: str = None
    ) -> List[Signal]:
        signals = []

        for symbol in self.config.symbols or data.keys():
            if symbol not in data:
                continue

            ohlcv = data[symbol]
            open_p = np.array(ohlcv.get('open', []))
            high = np.array(ohlcv.get('high', []))
            low = np.array(ohlcv.get('low', []))
            close = np.array(ohlcv.get('close', []))
            volume = np.array(ohlcv.get('volume', []))

            if len(close) < 50:
                continue

            analysis = self.analyzer.analyze(open_p, high, low, close, volume)
            atr = self.analyzer._calculate_atr(high, low, close)

            current_structure = analysis['market_structure']
            current_price = close[-1]

            # Detect Change of Character (CHoCH)
            if current_structure != self.previous_structure and self.previous_structure != MarketStructure.UNKNOWN:

                # Check for displacement
                displacements = self.analyzer.detect_displacement(open_p, high, low, close, atr)
                has_displacement = len(displacements) > 0 and displacements[-1]['index'] >= len(close) - 3

                if not self.config.parameters.get('require_displacement', True) or has_displacement:

                    # Bullish CHoCH
                    if current_structure == MarketStructure.BULLISH and self.previous_structure == MarketStructure.BEARISH:
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.LONG,
                            strength=0.85,
                            confidence=0.75,
                            entry_price=current_price,
                            stop_loss=low[-5:].min() - atr[-1] * 0.5,
                            take_profit=current_price + 3 * atr[-1],
                            metadata={
                                'strategy': 'MSS',
                                'signal_type': 'CHoCH',
                                'from_structure': self.previous_structure.value,
                                'to_structure': current_structure.value,
                                'has_displacement': has_displacement,
                            },
                        ))

                    # Bearish CHoCH
                    elif current_structure == MarketStructure.BEARISH and self.previous_structure == MarketStructure.BULLISH:
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.SHORT,
                            strength=0.85,
                            confidence=0.75,
                            entry_price=current_price,
                            stop_loss=high[-5:].max() + atr[-1] * 0.5,
                            take_profit=current_price - 3 * atr[-1],
                            metadata={
                                'strategy': 'MSS',
                                'signal_type': 'CHoCH',
                                'from_structure': self.previous_structure.value,
                                'to_structure': current_structure.value,
                                'has_displacement': has_displacement,
                            },
                        ))

            self.previous_structure = current_structure

        return signals


class OptimalTradeEntryStrategy(BaseStrategy):
    """
    Optimal Trade Entry (OTE) Strategy.

    Uses Fibonacci retracement levels (62-79%) for entries
    in the direction of the trend.
    """

    def __init__(self, config: StrategyConfig = None):
        if config is None:
            config = StrategyConfig(
                name="ICT Optimal Trade Entry",
                parameters={
                    'fib_levels': [0.62, 0.705, 0.79],
                    'tolerance': 0.01,  # 1% tolerance
                    'require_fvg_confluence': False,
                }
            )
        super().__init__(config)
        self.analyzer = ICTAnalyzer()

    def generate_signals(
        self,
        data: Dict[str, Any],
        features: Dict[str, np.ndarray] = None,
        regime: str = None
    ) -> List[Signal]:
        signals = []

        for symbol in self.config.symbols or data.keys():
            if symbol not in data:
                continue

            ohlcv = data[symbol]
            open_p = np.array(ohlcv.get('open', []))
            high = np.array(ohlcv.get('high', []))
            low = np.array(ohlcv.get('low', []))
            close = np.array(ohlcv.get('close', []))
            volume = np.array(ohlcv.get('volume', []))

            if len(close) < 50:
                continue

            analysis = self.analyzer.analyze(open_p, high, low, close, volume)
            structure = analysis['market_structure']
            current_price = close[-1]
            atr = analysis['atr']

            # Get recent swing points
            swing_highs = analysis['swing_highs']
            swing_lows = analysis['swing_lows']

            if len(swing_highs) < 1 or len(swing_lows) < 1:
                continue

            # Get most recent swing for OTE calculation
            recent_high = swing_highs[-1].price
            recent_low = swing_lows[-1].price

            # Calculate OTE levels
            ote_levels = self.analyzer.get_optimal_trade_entry(recent_high, recent_low)
            tolerance = self.config.parameters.get('tolerance', 0.01)

            # Bullish OTE entry
            if structure == MarketStructure.BULLISH:
                for level_name, level_price in ote_levels.items():
                    if 'ote' in level_name:
                        if abs(current_price - level_price) / level_price < tolerance:
                            # Check for FVG confluence if required
                            fvg_confluence = False
                            if self.config.parameters.get('require_fvg_confluence', False):
                                for fvg in analysis['fvgs']:
                                    if fvg.direction == 'bullish' and fvg.is_price_in_gap(current_price):
                                        fvg_confluence = True
                                        break

                            if not self.config.parameters.get('require_fvg_confluence', False) or fvg_confluence:
                                signals.append(Signal(
                                    strategy_id=self.strategy_id,
                                    symbol=symbol,
                                    direction=SignalDirection.LONG,
                                    strength=0.75,
                                    confidence=0.7 + (0.1 if fvg_confluence else 0),
                                    entry_price=level_price,
                                    stop_loss=recent_low - atr * 0.5,
                                    take_profit=recent_high + (recent_high - recent_low) * 0.5,
                                    metadata={
                                        'strategy': 'OTE',
                                        'ote_level': level_name,
                                        'fib_price': level_price,
                                        'swing_high': recent_high,
                                        'swing_low': recent_low,
                                        'fvg_confluence': fvg_confluence,
                                    },
                                ))
                                break  # One signal per symbol

            # Bearish OTE entry (inverse)
            elif structure == MarketStructure.BEARISH:
                # For bearish, we invert - look for retracement up
                inverse_ote = self.analyzer.get_optimal_trade_entry(recent_low, recent_high)

                for level_name, level_price in inverse_ote.items():
                    if 'ote' in level_name:
                        # Invert the level
                        inverted_level = recent_high - (level_price - recent_low)

                        if abs(current_price - inverted_level) / inverted_level < tolerance:
                            signals.append(Signal(
                                strategy_id=self.strategy_id,
                                symbol=symbol,
                                direction=SignalDirection.SHORT,
                                strength=0.75,
                                confidence=0.7,
                                entry_price=inverted_level,
                                stop_loss=recent_high + atr * 0.5,
                                take_profit=recent_low - (recent_high - recent_low) * 0.5,
                                metadata={
                                    'strategy': 'OTE',
                                    'ote_level': level_name,
                                    'fib_price': inverted_level,
                                    'swing_high': recent_high,
                                    'swing_low': recent_low,
                                },
                            ))
                            break

        return signals


class PremiumDiscountStrategy(BaseStrategy):
    """
    Premium/Discount Zone Strategy.

    Buys in discount zones (lower 50% of range).
    Sells in premium zones (upper 50% of range).
    """

    def __init__(self, config: StrategyConfig = None):
        if config is None:
            config = StrategyConfig(
                name="ICT Premium/Discount",
                parameters={
                    'range_lookback': 20,
                    'deep_discount_threshold': 0.25,  # Bottom 25%
                    'deep_premium_threshold': 0.75,   # Top 25%
                }
            )
        super().__init__(config)
        self.analyzer = ICTAnalyzer()

    def generate_signals(
        self,
        data: Dict[str, Any],
        features: Dict[str, np.ndarray] = None,
        regime: str = None
    ) -> List[Signal]:
        signals = []

        for symbol in self.config.symbols or data.keys():
            if symbol not in data:
                continue

            ohlcv = data[symbol]
            open_p = np.array(ohlcv.get('open', []))
            high = np.array(ohlcv.get('high', []))
            low = np.array(ohlcv.get('low', []))
            close = np.array(ohlcv.get('close', []))
            volume = np.array(ohlcv.get('volume', []))

            if len(close) < 30:
                continue

            analysis = self.analyzer.analyze(open_p, high, low, close, volume)
            structure = analysis['market_structure']
            current_price = close[-1]
            atr = analysis['atr']

            lookback = self.config.parameters.get('range_lookback', 20)
            zones = self.analyzer.get_premium_discount_zones(high, low, lookback)

            range_size = zones['range_high'] - zones['range_low']
            if range_size == 0:
                continue

            # Position in range (0 = low, 1 = high)
            position_in_range = (current_price - zones['range_low']) / range_size

            deep_discount = self.config.parameters.get('deep_discount_threshold', 0.25)
            deep_premium = self.config.parameters.get('deep_premium_threshold', 0.75)

            # Buy in deep discount with bullish/neutral structure
            if position_in_range < deep_discount and structure != MarketStructure.BEARISH:
                signals.append(Signal(
                    strategy_id=self.strategy_id,
                    symbol=symbol,
                    direction=SignalDirection.LONG,
                    strength=0.7 * (1 - position_in_range),  # Stronger at deeper discount
                    confidence=0.65,
                    entry_price=current_price,
                    stop_loss=zones['range_low'] - atr * 0.3,
                    take_profit=zones['equilibrium'],
                    metadata={
                        'strategy': 'PremiumDiscount',
                        'zone': 'deep_discount',
                        'position_in_range': position_in_range,
                        'equilibrium': zones['equilibrium'],
                    },
                ))

            # Sell in deep premium with bearish/neutral structure
            elif position_in_range > deep_premium and structure != MarketStructure.BULLISH:
                signals.append(Signal(
                    strategy_id=self.strategy_id,
                    symbol=symbol,
                    direction=SignalDirection.SHORT,
                    strength=0.7 * position_in_range,  # Stronger at higher premium
                    confidence=0.65,
                    entry_price=current_price,
                    stop_loss=zones['range_high'] + atr * 0.3,
                    take_profit=zones['equilibrium'],
                    metadata={
                        'strategy': 'PremiumDiscount',
                        'zone': 'deep_premium',
                        'position_in_range': position_in_range,
                        'equilibrium': zones['equilibrium'],
                    },
                ))

        return signals


class BreakerBlockStrategy(BaseStrategy):
    """
    Breaker Block Strategy.

    Trades failed order blocks that flip from support to resistance
    or vice versa.
    """

    def __init__(self, config: StrategyConfig = None):
        if config is None:
            config = StrategyConfig(
                name="ICT Breaker Block",
                parameters={
                    'min_retest_bars': 3,
                    'max_breaker_age': 50,
                }
            )
        super().__init__(config)
        self.analyzer = ICTAnalyzer()

    def generate_signals(
        self,
        data: Dict[str, Any],
        features: Dict[str, np.ndarray] = None,
        regime: str = None
    ) -> List[Signal]:
        signals = []

        for symbol in self.config.symbols or data.keys():
            if symbol not in data:
                continue

            ohlcv = data[symbol]
            open_p = np.array(ohlcv.get('open', []))
            high = np.array(ohlcv.get('high', []))
            low = np.array(ohlcv.get('low', []))
            close = np.array(ohlcv.get('close', []))
            volume = np.array(ohlcv.get('volume', []))

            if len(close) < 60:
                continue

            analysis = self.analyzer.analyze(open_p, high, low, close, volume)
            current_price = close[-1]
            atr = analysis['atr']

            for breaker in analysis['breaker_blocks'][-5:]:
                # Bullish breaker (was bearish OB, now support)
                if breaker.new_direction == 'bullish':
                    if breaker.low < current_price < breaker.high * 1.005:
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.LONG,
                            strength=0.75,
                            confidence=0.7,
                            entry_price=breaker.low,
                            stop_loss=breaker.low - atr,
                            take_profit=current_price + 2.5 * atr,
                            metadata={
                                'strategy': 'BreakerBlock',
                                'original_direction': breaker.original_direction,
                                'new_direction': breaker.new_direction,
                            },
                        ))

                # Bearish breaker (was bullish OB, now resistance)
                elif breaker.new_direction == 'bearish':
                    if breaker.low * 0.995 < current_price < breaker.high:
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.SHORT,
                            strength=0.75,
                            confidence=0.7,
                            entry_price=breaker.high,
                            stop_loss=breaker.high + atr,
                            take_profit=current_price - 2.5 * atr,
                            metadata={
                                'strategy': 'BreakerBlock',
                                'original_direction': breaker.original_direction,
                                'new_direction': breaker.new_direction,
                            },
                        ))

        return signals


class InducementStrategy(BaseStrategy):
    """
    Inducement Strategy.

    Trades reversals after retail traders get trapped by
    minor level breaks.
    """

    def __init__(self, config: StrategyConfig = None):
        if config is None:
            config = StrategyConfig(
                name="ICT Inducement",
                parameters={
                    'lookback': 10,
                    'min_trap_size_atr': 0.3,
                }
            )
        super().__init__(config)
        self.analyzer = ICTAnalyzer()

    def generate_signals(
        self,
        data: Dict[str, Any],
        features: Dict[str, np.ndarray] = None,
        regime: str = None
    ) -> List[Signal]:
        signals = []

        for symbol in self.config.symbols or data.keys():
            if symbol not in data:
                continue

            ohlcv = data[symbol]
            open_p = np.array(ohlcv.get('open', []))
            high = np.array(ohlcv.get('high', []))
            low = np.array(ohlcv.get('low', []))
            close = np.array(ohlcv.get('close', []))
            volume = np.array(ohlcv.get('volume', []))

            if len(close) < 30:
                continue

            atr = self.analyzer._calculate_atr(high, low, close)
            inducements = self.analyzer.detect_inducement(high, low, close)

            current_price = close[-1]

            # Get recent inducements
            recent_inducements = [i for i in inducements if i['index'] >= len(close) - 3]

            for ind in recent_inducements:
                min_trap = self.config.parameters.get('min_trap_size_atr', 0.3)

                if ind['type'] == 'bullish':
                    trap_size = ind['trap_level'] - ind['sweep_low']
                    if trap_size >= atr[-1] * min_trap:
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.LONG,
                            strength=0.7,
                            confidence=0.65,
                            entry_price=current_price,
                            stop_loss=ind['sweep_low'] - atr[-1] * 0.3,
                            take_profit=current_price + 2 * trap_size,
                            metadata={
                                'strategy': 'Inducement',
                                'inducement_type': ind['type'],
                                'trap_level': ind['trap_level'],
                                'trap_size': trap_size,
                            },
                        ))

                elif ind['type'] == 'bearish':
                    trap_size = ind['sweep_high'] - ind['trap_level']
                    if trap_size >= atr[-1] * min_trap:
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.SHORT,
                            strength=0.7,
                            confidence=0.65,
                            entry_price=current_price,
                            stop_loss=ind['sweep_high'] + atr[-1] * 0.3,
                            take_profit=current_price - 2 * trap_size,
                            metadata={
                                'strategy': 'Inducement',
                                'inducement_type': ind['type'],
                                'trap_level': ind['trap_level'],
                                'trap_size': trap_size,
                            },
                        ))

        return signals


# =============================================================================
# ICT ENSEMBLE STRATEGY
# =============================================================================

class ICTEnsembleStrategy(BaseStrategy):
    """
    Ensemble of all ICT/SMC strategies.

    Combines signals from multiple ICT strategies with confluence scoring.
    """

    def __init__(self, config: StrategyConfig = None):
        if config is None:
            config = StrategyConfig(
                name="ICT Ensemble",
                parameters={
                    'min_confluence': 2,  # Minimum strategies agreeing
                    'weights': {
                        'FVG': 1.0,
                        'OrderBlock': 1.2,
                        'LiquiditySweep': 1.0,
                        'MSS': 1.3,
                        'OTE': 1.0,
                        'PremiumDiscount': 0.8,
                        'BreakerBlock': 1.0,
                        'Inducement': 0.9,
                    }
                }
            )
        super().__init__(config)

        # Initialize sub-strategies
        self.strategies = {
            'FVG': FairValueGapStrategy(),
            'OrderBlock': OrderBlockStrategy(),
            'LiquiditySweep': LiquiditySweepStrategy(),
            'MSS': MarketStructureShiftStrategy(),
            'OTE': OptimalTradeEntryStrategy(),
            'PremiumDiscount': PremiumDiscountStrategy(),
            'BreakerBlock': BreakerBlockStrategy(),
            'Inducement': InducementStrategy(),
        }

    def generate_signals(
        self,
        data: Dict[str, Any],
        features: Dict[str, np.ndarray] = None,
        regime: str = None
    ) -> List[Signal]:
        # Collect signals from all strategies
        all_signals: Dict[str, Dict[str, List[Signal]]] = {}  # symbol -> direction -> signals

        for strategy_name, strategy in self.strategies.items():
            strategy.config.symbols = self.config.symbols
            signals = strategy.generate_signals(data, features, regime)

            for signal in signals:
                symbol = signal.symbol
                direction = signal.direction.value

                if symbol not in all_signals:
                    all_signals[symbol] = {'long': [], 'short': [], 'flat': []}

                all_signals[symbol][direction].append((strategy_name, signal))

        # Combine signals with confluence
        ensemble_signals = []
        weights = self.config.parameters.get('weights', {})
        min_confluence = self.config.parameters.get('min_confluence', 2)

        for symbol, directions in all_signals.items():
            for direction in ['long', 'short']:
                signals_list = directions[direction]

                if len(signals_list) >= min_confluence:
                    # Calculate weighted average
                    total_weight = 0
                    weighted_strength = 0
                    weighted_confidence = 0
                    combined_metadata = {'strategies': [], 'confluence': len(signals_list)}

                    best_stop_loss = None
                    best_take_profit = None

                    for strategy_name, signal in signals_list:
                        weight = weights.get(strategy_name, 1.0)
                        total_weight += weight
                        weighted_strength += signal.strength * weight
                        weighted_confidence += signal.confidence * weight
                        combined_metadata['strategies'].append(strategy_name)

                        # Use most conservative stop loss and most ambitious take profit
                        if signal.stop_loss:
                            if best_stop_loss is None:
                                best_stop_loss = signal.stop_loss
                            elif direction == 'long':
                                best_stop_loss = min(best_stop_loss, signal.stop_loss)
                            else:
                                best_stop_loss = max(best_stop_loss, signal.stop_loss)

                        if signal.take_profit:
                            if best_take_profit is None:
                                best_take_profit = signal.take_profit
                            elif direction == 'long':
                                best_take_profit = max(best_take_profit, signal.take_profit)
                            else:
                                best_take_profit = min(best_take_profit, signal.take_profit)

                    ensemble_signals.append(Signal(
                        strategy_id=self.strategy_id,
                        symbol=symbol,
                        direction=SignalDirection.LONG if direction == 'long' else SignalDirection.SHORT,
                        strength=min(1.0, weighted_strength / total_weight * 1.1),  # Boost for confluence
                        confidence=min(0.95, weighted_confidence / total_weight + 0.05 * len(signals_list)),
                        entry_price=signals_list[0][1].entry_price,
                        stop_loss=best_stop_loss,
                        take_profit=best_take_profit,
                        metadata=combined_metadata,
                    ))

        return ensemble_signals


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Data structures
    'MarketStructure',
    'SwingType',
    'SessionType',
    'SwingPoint',
    'FairValueGap',
    'OrderBlock',
    'BreakerBlock',
    'LiquiditySweep',
    'KillZone',

    # Analyzer
    'ICTAnalyzer',

    # Strategies
    'FairValueGapStrategy',
    'OrderBlockStrategy',
    'LiquiditySweepStrategy',
    'MarketStructureShiftStrategy',
    'OptimalTradeEntryStrategy',
    'PremiumDiscountStrategy',
    'BreakerBlockStrategy',
    'InducementStrategy',
    'ICTEnsembleStrategy',
]
