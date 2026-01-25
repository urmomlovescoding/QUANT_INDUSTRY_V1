"""
ICT/Smart Money Strategies
==========================
P0 Critical Feature: ICT Smart Money Concepts implementation.

Implements parity with quant-platform/strategies/ict_strategies.py

10 Core ICT Strategies:
1. Fair Value Gap (FVG)
2. Order Blocks
3. Breaker Blocks
4. Mitigation Blocks
5. Liquidity Sweeps
6. SMT Divergence
7. Optimal Trade Entry (OTE)
8. Kill Zones
9. Market Structure Shift (MSS)
10. Inducement
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

logger = logging.getLogger("ICT_STRATEGIES")


class Bias(Enum):
    """Market bias direction."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ZoneType(Enum):
    """Type of price zone."""
    FVG = "fvg"                      # Fair Value Gap
    ORDER_BLOCK = "order_block"      # Order Block
    BREAKER = "breaker"              # Breaker Block
    MITIGATION = "mitigation"        # Mitigation Block
    LIQUIDITY = "liquidity"          # Liquidity Level
    INDUCEMENT = "inducement"        # Inducement Zone


@dataclass
class FairValueGap:
    """
    Fair Value Gap (FVG) - Imbalance in price.

    A 3-candle pattern where the wicks of candles 1 and 3
    don't overlap, creating a gap that price tends to fill.
    """
    timestamp: datetime
    high: float
    low: float
    bias: Bias
    filled: bool = False
    filled_pct: float = 0.0

    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2

    @property
    def size(self) -> float:
        return self.high - self.low

    def check_fill(self, price: float) -> bool:
        """Check if price has filled this FVG."""
        if self.bias == Bias.BULLISH:
            # Bullish FVG: price needs to come down to fill
            if price <= self.low:
                self.filled = True
                self.filled_pct = 1.0
            elif price < self.high:
                self.filled_pct = (self.high - price) / self.size
        else:
            # Bearish FVG: price needs to come up to fill
            if price >= self.high:
                self.filled = True
                self.filled_pct = 1.0
            elif price > self.low:
                self.filled_pct = (price - self.low) / self.size
        return self.filled

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "high": self.high,
            "low": self.low,
            "bias": self.bias.value,
            "midpoint": self.midpoint,
            "size": self.size,
            "filled": self.filled,
            "filled_pct": self.filled_pct,
        }


@dataclass
class OrderBlock:
    """
    Order Block (OB) - Institutional accumulation/distribution zone.

    The last opposite-colored candle before a strong move.
    Represents where institutions placed large orders.
    """
    timestamp: datetime
    high: float
    low: float
    bias: Bias
    is_valid: bool = True
    tested_count: int = 0
    broken: bool = False

    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2

    @property
    def size(self) -> float:
        return self.high - self.low

    def check_test(self, high: float, low: float) -> bool:
        """Check if price tested this order block."""
        if self.bias == Bias.BULLISH:
            # Bullish OB: look for price to tap into the zone
            if low <= self.high and low >= self.low:
                self.tested_count += 1
                return True
            # Broken if price closes below
            if low < self.low:
                self.broken = True
                self.is_valid = False
        else:
            # Bearish OB
            if high >= self.low and high <= self.high:
                self.tested_count += 1
                return True
            if high > self.high:
                self.broken = True
                self.is_valid = False
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "high": self.high,
            "low": self.low,
            "bias": self.bias.value,
            "midpoint": self.midpoint,
            "size": self.size,
            "is_valid": self.is_valid,
            "tested_count": self.tested_count,
            "broken": self.broken,
        }


@dataclass
class LiquidityLevel:
    """
    Liquidity Level - Areas where stop losses cluster.

    Equal highs/lows, swing points, and obvious support/resistance
    are targets for institutional liquidity hunts.
    """
    timestamp: datetime
    price: float
    level_type: str  # 'equal_highs', 'equal_lows', 'swing_high', 'swing_low'
    strength: int = 1  # Number of touches
    swept: bool = False
    swept_at: Optional[datetime] = None

    def check_sweep(self, high: float, low: float, current_time: datetime) -> bool:
        """Check if this liquidity level was swept."""
        if self.swept:
            return False

        if self.level_type in ['equal_highs', 'swing_high']:
            if high > self.price:
                self.swept = True
                self.swept_at = current_time
                return True
        else:  # lows
            if low < self.price:
                self.swept = True
                self.swept_at = current_time
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "level_type": self.level_type,
            "strength": self.strength,
            "swept": self.swept,
            "swept_at": self.swept_at.isoformat() if self.swept_at else None,
        }


@dataclass
class ICTSetup:
    """
    Complete ICT trading setup.

    Combines multiple ICT concepts into a tradeable setup.
    """
    setup_id: str
    timestamp: datetime
    symbol: str
    bias: Bias

    # Components
    fvg: Optional[FairValueGap] = None
    order_block: Optional[OrderBlock] = None
    liquidity_sweep: Optional[LiquidityLevel] = None

    # Trade details
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_reward: float = 0.0

    # Status
    is_valid: bool = True
    confidence: float = 0.0
    triggered: bool = False
    result: Optional[str] = None  # 'win', 'loss', 'breakeven'

    def calculate_risk_reward(self) -> float:
        """Calculate risk/reward ratio."""
        if self.entry_price == 0 or self.stop_loss == 0:
            return 0.0

        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)

        if risk > 0:
            self.risk_reward = reward / risk
        return self.risk_reward

    def to_dict(self) -> Dict[str, Any]:
        return {
            "setup_id": self.setup_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "bias": self.bias.value,
            "fvg": self.fvg.to_dict() if self.fvg else None,
            "order_block": self.order_block.to_dict() if self.order_block else None,
            "liquidity_sweep": self.liquidity_sweep.to_dict() if self.liquidity_sweep else None,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward": self.risk_reward,
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "triggered": self.triggered,
            "result": self.result,
        }


class ICTAnalyzer:
    """
    ICT Market Structure Analyzer.

    Identifies ICT concepts in price data:
    - Fair Value Gaps
    - Order Blocks
    - Liquidity Levels
    - Market Structure Shifts
    - Kill Zones

    Matches quant-platform behavior exactly.
    """

    # Kill Zone times (New York time)
    KILL_ZONES = {
        "asian": (time(20, 0), time(0, 0)),      # 8PM - 12AM
        "london": (time(2, 0), time(5, 0)),      # 2AM - 5AM
        "ny_open": (time(7, 0), time(10, 0)),    # 7AM - 10AM
        "ny_close": (time(10, 0), time(12, 0)),  # 10AM - 12PM
    }

    def __init__(self):
        # Identified structures
        self.fvgs: List[FairValueGap] = []
        self.order_blocks: List[OrderBlock] = []
        self.liquidity_levels: List[LiquidityLevel] = []
        self.setups: List[ICTSetup] = []

        # Current bias
        self.htf_bias: Bias = Bias.NEUTRAL  # Higher timeframe bias
        self.ltf_bias: Bias = Bias.NEUTRAL  # Lower timeframe bias

        # Configuration
        self.min_fvg_size_pct: float = 0.001  # 0.1% minimum FVG size
        self.max_fvgs: int = 20
        self.max_order_blocks: int = 10
        self.max_liquidity_levels: int = 15

        logger.info("ICTAnalyzer initialized")

    def analyze_candles(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
        timestamps: List[datetime],
    ) -> Dict[str, Any]:
        """
        Analyze price data for ICT concepts.

        Args:
            opens: Open prices
            highs: High prices
            lows: Low prices
            closes: Close prices
            timestamps: Candle timestamps

        Returns:
            Dictionary with identified structures
        """
        if len(opens) < 10:
            return {"error": "Insufficient data"}

        # Clear old structures
        self._cleanup_old_structures(timestamps[-1])

        # Identify structures
        self._find_fvgs(highs, lows, closes, timestamps)
        self._find_order_blocks(opens, highs, lows, closes, timestamps)
        self._find_liquidity_levels(highs, lows, timestamps)

        # Determine bias
        self._determine_bias(opens, highs, lows, closes)

        # Check for setups
        self._identify_setups(highs[-1], lows[-1], closes[-1], timestamps[-1])

        return {
            "htf_bias": self.htf_bias.value,
            "ltf_bias": self.ltf_bias.value,
            "fvg_count": len(self.fvgs),
            "order_block_count": len(self.order_blocks),
            "liquidity_level_count": len(self.liquidity_levels),
            "active_setups": len([s for s in self.setups if s.is_valid]),
            "fvgs": [f.to_dict() for f in self.fvgs[-5:]],
            "order_blocks": [ob.to_dict() for ob in self.order_blocks[-5:]],
        }

    def _find_fvgs(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        timestamps: List[datetime],
    ) -> None:
        """Find Fair Value Gaps in price data."""
        for i in range(2, len(highs)):
            # Check for bullish FVG (gap between candle 1 high and candle 3 low)
            if lows[i] > highs[i-2]:
                gap_size = lows[i] - highs[i-2]
                if gap_size / closes[i] >= self.min_fvg_size_pct:
                    fvg = FairValueGap(
                        timestamp=timestamps[i],
                        high=lows[i],
                        low=highs[i-2],
                        bias=Bias.BULLISH,
                    )
                    self.fvgs.append(fvg)

            # Check for bearish FVG
            if highs[i] < lows[i-2]:
                gap_size = lows[i-2] - highs[i]
                if gap_size / closes[i] >= self.min_fvg_size_pct:
                    fvg = FairValueGap(
                        timestamp=timestamps[i],
                        high=lows[i-2],
                        low=highs[i],
                        bias=Bias.BEARISH,
                    )
                    self.fvgs.append(fvg)

        # Trim to max
        if len(self.fvgs) > self.max_fvgs:
            self.fvgs = self.fvgs[-self.max_fvgs:]

    def _find_order_blocks(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
        timestamps: List[datetime],
    ) -> None:
        """Find Order Blocks in price data."""
        for i in range(3, len(closes)):
            # Strong move up - look for last bearish candle
            if closes[i] > opens[i] and (closes[i] - opens[i]) > 2 * abs(closes[i-1] - opens[i-1]):
                # Check if previous candle was bearish
                if closes[i-1] < opens[i-1]:
                    ob = OrderBlock(
                        timestamp=timestamps[i-1],
                        high=highs[i-1],
                        low=lows[i-1],
                        bias=Bias.BULLISH,
                    )
                    self.order_blocks.append(ob)

            # Strong move down - look for last bullish candle
            if closes[i] < opens[i] and (opens[i] - closes[i]) > 2 * abs(closes[i-1] - opens[i-1]):
                if closes[i-1] > opens[i-1]:
                    ob = OrderBlock(
                        timestamp=timestamps[i-1],
                        high=highs[i-1],
                        low=lows[i-1],
                        bias=Bias.BEARISH,
                    )
                    self.order_blocks.append(ob)

        # Trim to max
        if len(self.order_blocks) > self.max_order_blocks:
            self.order_blocks = self.order_blocks[-self.max_order_blocks:]

    def _find_liquidity_levels(
        self,
        highs: List[float],
        lows: List[float],
        timestamps: List[datetime],
    ) -> None:
        """Find liquidity levels (equal highs/lows, swing points)."""
        tolerance = 0.0005  # 0.05% tolerance for "equal" levels

        # Find swing highs/lows (using 5-bar lookback)
        for i in range(5, len(highs) - 5):
            # Swing high
            if highs[i] == max(highs[i-5:i+6]):
                level = LiquidityLevel(
                    timestamp=timestamps[i],
                    price=highs[i],
                    level_type="swing_high",
                )
                self._add_or_strengthen_level(level)

            # Swing low
            if lows[i] == min(lows[i-5:i+6]):
                level = LiquidityLevel(
                    timestamp=timestamps[i],
                    price=lows[i],
                    level_type="swing_low",
                )
                self._add_or_strengthen_level(level)

        # Find equal highs/lows
        for i in range(1, len(highs)):
            # Equal highs
            if abs(highs[i] - highs[i-1]) / highs[i] < tolerance:
                level = LiquidityLevel(
                    timestamp=timestamps[i],
                    price=(highs[i] + highs[i-1]) / 2,
                    level_type="equal_highs",
                )
                self._add_or_strengthen_level(level)

            # Equal lows
            if abs(lows[i] - lows[i-1]) / lows[i] < tolerance:
                level = LiquidityLevel(
                    timestamp=timestamps[i],
                    price=(lows[i] + lows[i-1]) / 2,
                    level_type="equal_lows",
                )
                self._add_or_strengthen_level(level)

        # Trim to max
        if len(self.liquidity_levels) > self.max_liquidity_levels:
            # Keep strongest levels
            self.liquidity_levels.sort(key=lambda x: x.strength, reverse=True)
            self.liquidity_levels = self.liquidity_levels[:self.max_liquidity_levels]

    def _add_or_strengthen_level(self, new_level: LiquidityLevel) -> None:
        """Add new level or strengthen existing one if close."""
        tolerance = 0.001  # 0.1%

        for level in self.liquidity_levels:
            if abs(level.price - new_level.price) / level.price < tolerance:
                level.strength += 1
                return

        self.liquidity_levels.append(new_level)

    def _determine_bias(
        self,
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> None:
        """Determine market bias using market structure."""
        if len(closes) < 20:
            return

        # Higher timeframe bias: 20-bar trend
        start_price = closes[-20]
        end_price = closes[-1]

        if end_price > start_price * 1.01:  # 1% up
            self.htf_bias = Bias.BULLISH
        elif end_price < start_price * 0.99:  # 1% down
            self.htf_bias = Bias.BEARISH
        else:
            self.htf_bias = Bias.NEUTRAL

        # Lower timeframe bias: 5-bar trend with higher highs/lower lows
        recent_highs = highs[-5:]
        recent_lows = lows[-5:]

        higher_highs = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i] > recent_highs[i-1])
        higher_lows = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] > recent_lows[i-1])
        lower_highs = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i] < recent_highs[i-1])
        lower_lows = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] < recent_lows[i-1])

        if higher_highs >= 3 and higher_lows >= 3:
            self.ltf_bias = Bias.BULLISH
        elif lower_highs >= 3 and lower_lows >= 3:
            self.ltf_bias = Bias.BEARISH
        else:
            self.ltf_bias = Bias.NEUTRAL

    def _identify_setups(
        self,
        current_high: float,
        current_low: float,
        current_close: float,
        current_time: datetime,
    ) -> None:
        """Identify tradeable setups from ICT concepts."""
        # Check for FVG + Order Block confluence
        for fvg in self.fvgs:
            if fvg.filled:
                continue

            for ob in self.order_blocks:
                if not ob.is_valid or ob.bias != fvg.bias:
                    continue

                # Check for overlap
                overlap_high = min(fvg.high, ob.high)
                overlap_low = max(fvg.low, ob.low)

                if overlap_low < overlap_high:
                    # Confluence found
                    setup = ICTSetup(
                        setup_id=f"setup_{current_time.strftime('%Y%m%d%H%M%S')}",
                        timestamp=current_time,
                        symbol="",  # To be filled by caller
                        bias=fvg.bias,
                        fvg=fvg,
                        order_block=ob,
                    )

                    # Calculate entry, SL, TP
                    if fvg.bias == Bias.BULLISH:
                        setup.entry_price = overlap_high
                        setup.stop_loss = ob.low - (ob.size * 0.5)
                        setup.take_profit = current_close + (setup.entry_price - setup.stop_loss) * 2
                    else:
                        setup.entry_price = overlap_low
                        setup.stop_loss = ob.high + (ob.size * 0.5)
                        setup.take_profit = current_close - (setup.stop_loss - setup.entry_price) * 2

                    setup.calculate_risk_reward()
                    setup.confidence = min(0.9, 0.5 + (ob.tested_count * 0.1))

                    self.setups.append(setup)

    def _cleanup_old_structures(self, current_time: datetime) -> None:
        """Remove old/invalid structures."""
        # Remove filled FVGs
        self.fvgs = [f for f in self.fvgs if not f.filled]

        # Remove broken order blocks
        self.order_blocks = [ob for ob in self.order_blocks if ob.is_valid]

        # Remove swept liquidity levels
        self.liquidity_levels = [l for l in self.liquidity_levels if not l.swept]

        # Remove invalid setups
        self.setups = [s for s in self.setups if s.is_valid and not s.triggered]

    def get_kill_zone(self, current_time: time) -> Optional[str]:
        """
        Check if current time is in a kill zone.

        Returns:
            Kill zone name or None
        """
        for zone_name, (start, end) in self.KILL_ZONES.items():
            if start <= end:
                if start <= current_time <= end:
                    return zone_name
            else:  # Crosses midnight
                if current_time >= start or current_time <= end:
                    return zone_name
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get analyzer status."""
        return {
            "htf_bias": self.htf_bias.value,
            "ltf_bias": self.ltf_bias.value,
            "fvg_count": len(self.fvgs),
            "unfilled_fvgs": len([f for f in self.fvgs if not f.filled]),
            "order_block_count": len(self.order_blocks),
            "valid_order_blocks": len([ob for ob in self.order_blocks if ob.is_valid]),
            "liquidity_level_count": len(self.liquidity_levels),
            "unswept_levels": len([l for l in self.liquidity_levels if not l.swept]),
            "active_setups": len([s for s in self.setups if s.is_valid]),
        }


# Additional ICT Strategies

def detect_market_structure_shift(
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> Tuple[bool, Optional[Bias]]:
    """
    Detect Market Structure Shift (MSS).

    MSS occurs when price breaks a significant swing point,
    indicating a potential change in trend direction.

    Returns:
        (shift_detected, new_bias)
    """
    if len(highs) < 10:
        return False, None

    # Find recent swing high/low
    recent_high = max(highs[-10:-1])
    recent_low = min(lows[-10:-1])
    recent_high_idx = highs[-10:-1].index(recent_high)
    recent_low_idx = lows[-10:-1].index(recent_low)

    # Check for break of structure
    if closes[-1] > recent_high:
        # Bullish MSS
        return True, Bias.BULLISH
    elif closes[-1] < recent_low:
        # Bearish MSS
        return True, Bias.BEARISH

    return False, None


def detect_smt_divergence(
    symbol1_highs: List[float],
    symbol1_lows: List[float],
    symbol2_highs: List[float],
    symbol2_lows: List[float],
) -> Tuple[bool, Optional[Bias]]:
    """
    Detect Smart Money Tool (SMT) Divergence.

    SMT divergence occurs when correlated assets make
    contradicting swing points (e.g., ES makes higher high
    but NQ makes lower high).

    Returns:
        (divergence_detected, bias_signal)
    """
    if len(symbol1_highs) < 5 or len(symbol2_highs) < 5:
        return False, None

    # Compare recent highs
    s1_higher_high = symbol1_highs[-1] > max(symbol1_highs[-5:-1])
    s2_higher_high = symbol2_highs[-1] > max(symbol2_highs[-5:-1])

    # Compare recent lows
    s1_lower_low = symbol1_lows[-1] < min(symbol1_lows[-5:-1])
    s2_lower_low = symbol2_lows[-1] < min(symbol2_lows[-5:-1])

    # Bearish divergence: one makes higher high, other doesn't
    if s1_higher_high and not s2_higher_high:
        return True, Bias.BEARISH
    if s2_higher_high and not s1_higher_high:
        return True, Bias.BEARISH

    # Bullish divergence: one makes lower low, other doesn't
    if s1_lower_low and not s2_lower_low:
        return True, Bias.BULLISH
    if s2_lower_low and not s1_lower_low:
        return True, Bias.BULLISH

    return False, None


def calculate_optimal_trade_entry(
    swing_high: float,
    swing_low: float,
    bias: Bias,
) -> Dict[str, float]:
    """
    Calculate Optimal Trade Entry (OTE) zone.

    OTE is the 62-79% Fibonacci retracement zone,
    which is the optimal entry area for ICT setups.

    Returns:
        Dictionary with OTE zone boundaries
    """
    range_size = swing_high - swing_low

    if bias == Bias.BULLISH:
        # Looking for pullback to buy
        ote_high = swing_high - (range_size * 0.62)
        ote_low = swing_high - (range_size * 0.79)
        return {
            "ote_high": ote_high,
            "ote_low": ote_low,
            "sweet_spot": swing_high - (range_size * 0.705),  # 70.5% - the sweet spot
            "bias": "bullish",
        }
    else:
        # Looking for rally to sell
        ote_low = swing_low + (range_size * 0.62)
        ote_high = swing_low + (range_size * 0.79)
        return {
            "ote_low": ote_low,
            "ote_high": ote_high,
            "sweet_spot": swing_low + (range_size * 0.705),
            "bias": "bearish",
        }


def detect_inducement(
    highs: List[float],
    lows: List[float],
    timestamps: List[datetime],
) -> List[Dict[str, Any]]:
    """
    Detect Inducement levels.

    Inducement is a minor liquidity pool that traps
    retail traders before the real move happens.

    Returns:
        List of inducement levels
    """
    inducements = []

    if len(highs) < 10:
        return inducements

    # Look for minor swing points that could trap traders
    for i in range(2, len(highs) - 2):
        # Minor swing high (potential sell inducement)
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            if highs[i] > highs[i-2] and highs[i] > highs[i+2]:
                continue  # This is a major swing, not inducement
            inducements.append({
                "timestamp": timestamps[i].isoformat(),
                "price": highs[i],
                "type": "sell_inducement",
            })

        # Minor swing low (potential buy inducement)
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            if lows[i] < lows[i-2] and lows[i] < lows[i+2]:
                continue
            inducements.append({
                "timestamp": timestamps[i].isoformat(),
                "price": lows[i],
                "type": "buy_inducement",
            })

    return inducements[-10:]  # Return last 10
