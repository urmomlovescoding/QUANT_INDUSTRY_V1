"""
Tape Reading & Time and Sales Analysis
======================================
Analyzes time and sales data for trading patterns.
"""

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from collections import deque
import logging

from .order_flow_features import TradeEvent, AggressorSide

logger = logging.getLogger(__name__)


class TapePatternType(Enum):
    """Types of patterns detected in tape."""
    MOMENTUM_BURST = "momentum_burst"  # Rapid one-sided flow
    ABSORPTION = "absorption"  # Large orders absorbing flow
    EXHAUSTION = "exhaustion"  # Momentum fading
    ICEBERG = "iceberg"  # Hidden large order
    SWEEP = "sweep"  # Aggressive multi-level execution
    STOP_RUN = "stop_run"  # Stop loss cascade
    REVERSAL = "reversal"  # Direction change
    ACCUMULATION = "accumulation"  # Steady buying
    DISTRIBUTION = "distribution"  # Steady selling
    PRINT_CLUSTER = "print_cluster"  # Multiple prints at same price


class PrintSize(Enum):
    """Trade size classification."""
    ODD_LOT = "odd_lot"  # < 100
    ROUND_LOT = "round_lot"  # 100
    BLOCK = "block"  # > 10,000
    INSTITUTIONAL = "institutional"  # > 50,000
    WHALE = "whale"  # > 100,000


@dataclass
class TapeEvent:
    """Processed tape event with context."""
    trade: TradeEvent
    
    # Classification
    size_class: PrintSize
    is_aggressive: bool
    
    # Price context
    vs_vwap: float = 0.0  # Premium/discount to VWAP
    vs_mid: float = 0.0  # Distance from mid
    
    # Flow context
    cumulative_delta: int = 0  # Running buy-sell imbalance
    volume_percentile: float = 0.0  # Size vs recent history
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.trade.timestamp.isoformat(),
            "price": self.trade.price,
            "size": self.trade.size,
            "side": self.trade.aggressor.value,
            "size_class": self.size_class.value,
            "is_aggressive": self.is_aggressive,
            "vs_vwap": self.vs_vwap,
            "cumulative_delta": self.cumulative_delta,
        }


@dataclass
class TapePattern:
    """Detected pattern in tape."""
    timestamp: datetime
    symbol: str
    pattern_type: TapePatternType
    
    # Pattern details
    trades: List[TapeEvent] = field(default_factory=list)
    start_price: float = 0.0
    end_price: float = 0.0
    total_volume: int = 0
    duration_seconds: float = 0.0
    
    # Signal
    direction: str = ""  # "bullish", "bearish", "neutral"
    strength: float = 0.0  # 0-1
    
    # Context
    description: str = ""
    
    @property
    def price_change(self) -> float:
        return self.end_price - self.start_price
    
    @property
    def price_change_pct(self) -> float:
        if self.start_price == 0:
            return 0
        return (self.end_price - self.start_price) / self.start_price * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "pattern_type": self.pattern_type.value,
            "start_price": self.start_price,
            "end_price": self.end_price,
            "price_change_pct": self.price_change_pct,
            "total_volume": self.total_volume,
            "duration_seconds": self.duration_seconds,
            "direction": self.direction,
            "strength": self.strength,
            "description": self.description,
        }


@dataclass
class TapeConfig:
    """Configuration for tape reading."""
    # Size thresholds
    block_size: int = 10_000
    institutional_size: int = 50_000
    whale_size: int = 100_000
    
    # Pattern detection windows
    momentum_window_seconds: int = 10
    absorption_window_seconds: int = 30
    accumulation_window_seconds: int = 300
    
    # Pattern thresholds
    momentum_min_trades: int = 10
    momentum_imbalance_threshold: float = 0.8  # 80% one side
    
    absorption_min_volume: int = 10_000
    absorption_price_threshold: float = 0.001  # 0.1% price movement
    
    iceberg_min_prints: int = 5
    iceberg_size_variance_threshold: float = 0.2  # Similar sizes
    
    sweep_min_levels: int = 3
    sweep_time_window_ms: int = 500
    
    # History
    max_history: int = 10_000


class TapeReader:
    """
    Reads and analyzes time and sales (tape) data.
    
    Detects patterns like:
    - Momentum bursts
    - Absorption (large passive orders)
    - Icebergs (hidden liquidity)
    - Sweeps (aggressive multi-level fills)
    - Stop runs
    - Accumulation/Distribution
    """
    
    def __init__(self, config: Optional[TapeConfig] = None):
        self.config = config or TapeConfig()
        
        # Per-symbol state
        self._tape: Dict[str, deque] = {}
        self._events: Dict[str, deque] = {}
        self._cumulative_delta: Dict[str, int] = {}
        self._vwap_state: Dict[str, Dict[str, float]] = {}
        self._patterns: Dict[str, List[TapePattern]] = {}
        
    def process_trade(
        self,
        trade: TradeEvent,
        mid_price: Optional[float] = None,
    ) -> TapeEvent:
        """
        Process a trade and create enriched tape event.
        """
        symbol = trade.symbol
        
        # Initialize state
        if symbol not in self._tape:
            self._tape[symbol] = deque(maxlen=self.config.max_history)
            self._events[symbol] = deque(maxlen=self.config.max_history)
            self._cumulative_delta[symbol] = 0
            self._vwap_state[symbol] = {"volume": 0, "value": 0.0}
            
        # Update cumulative delta
        if trade.aggressor == AggressorSide.BUY:
            self._cumulative_delta[symbol] += trade.size
        elif trade.aggressor == AggressorSide.SELL:
            self._cumulative_delta[symbol] -= trade.size
            
        # Update VWAP
        self._vwap_state[symbol]["volume"] += trade.size
        self._vwap_state[symbol]["value"] += trade.price * trade.size
        vwap = (
            self._vwap_state[symbol]["value"] / 
            self._vwap_state[symbol]["volume"]
        ) if self._vwap_state[symbol]["volume"] > 0 else trade.price
        
        # Classify size
        size_class = self._classify_size(trade.size)
        
        # Determine aggression
        is_aggressive = trade.aggressor in (AggressorSide.BUY, AggressorSide.SELL)
        
        # Calculate context
        vs_vwap = (trade.price - vwap) / vwap if vwap > 0 else 0
        vs_mid = (trade.price - mid_price) / mid_price if mid_price and mid_price > 0 else 0
        
        # Volume percentile
        recent_sizes = [t.size for t in list(self._tape[symbol])[-100:]]
        if recent_sizes:
            volume_percentile = sum(1 for s in recent_sizes if s <= trade.size) / len(recent_sizes)
        else:
            volume_percentile = 0.5
            
        event = TapeEvent(
            trade=trade,
            size_class=size_class,
            is_aggressive=is_aggressive,
            vs_vwap=vs_vwap,
            vs_mid=vs_mid,
            cumulative_delta=self._cumulative_delta[symbol],
            volume_percentile=volume_percentile,
        )
        
        # Store
        self._tape[symbol].append(trade)
        self._events[symbol].append(event)
        
        return event
    
    def _classify_size(self, size: int) -> PrintSize:
        """Classify trade size."""
        if size >= self.config.whale_size:
            return PrintSize.WHALE
        elif size >= self.config.institutional_size:
            return PrintSize.INSTITUTIONAL
        elif size >= self.config.block_size:
            return PrintSize.BLOCK
        elif size < 100:
            return PrintSize.ODD_LOT
        else:
            return PrintSize.ROUND_LOT
    
    def detect_patterns(self, symbol: str) -> List[TapePattern]:
        """
        Detect patterns in recent tape.
        """
        patterns = []
        
        events = list(self._events.get(symbol, []))
        if len(events) < 5:
            return patterns
            
        # Check for various patterns
        if pattern := self._detect_momentum_burst(symbol, events):
            patterns.append(pattern)
            
        if pattern := self._detect_absorption(symbol, events):
            patterns.append(pattern)
            
        if pattern := self._detect_iceberg(symbol, events):
            patterns.append(pattern)
            
        if pattern := self._detect_sweep(symbol, events):
            patterns.append(pattern)
            
        if pattern := self._detect_accumulation_distribution(symbol, events):
            patterns.append(pattern)
            
        # Store patterns
        if symbol not in self._patterns:
            self._patterns[symbol] = []
        self._patterns[symbol].extend(patterns)
        
        return patterns
    
    def _detect_momentum_burst(
        self,
        symbol: str,
        events: List[TapeEvent],
    ) -> Optional[TapePattern]:
        """Detect rapid one-sided momentum."""
        cutoff = events[-1].trade.timestamp - timedelta(
            seconds=self.config.momentum_window_seconds
        )
        recent = [e for e in events if e.trade.timestamp > cutoff]
        
        if len(recent) < self.config.momentum_min_trades:
            return None
            
        # Calculate buy/sell imbalance
        buy_vol = sum(e.trade.size for e in recent if e.trade.aggressor == AggressorSide.BUY)
        sell_vol = sum(e.trade.size for e in recent if e.trade.aggressor == AggressorSide.SELL)
        total_vol = buy_vol + sell_vol
        
        if total_vol == 0:
            return None
            
        buy_pct = buy_vol / total_vol
        sell_pct = sell_vol / total_vol
        
        # Check threshold
        if max(buy_pct, sell_pct) < self.config.momentum_imbalance_threshold:
            return None
            
        direction = "bullish" if buy_pct > sell_pct else "bearish"
        
        return TapePattern(
            timestamp=recent[-1].trade.timestamp,
            symbol=symbol,
            pattern_type=TapePatternType.MOMENTUM_BURST,
            trades=recent,
            start_price=recent[0].trade.price,
            end_price=recent[-1].trade.price,
            total_volume=total_vol,
            duration_seconds=(recent[-1].trade.timestamp - recent[0].trade.timestamp).total_seconds(),
            direction=direction,
            strength=max(buy_pct, sell_pct),
            description=f"Momentum burst: {len(recent)} trades, {max(buy_pct, sell_pct)*100:.0f}% {direction}",
        )
    
    def _detect_absorption(
        self,
        symbol: str,
        events: List[TapeEvent],
    ) -> Optional[TapePattern]:
        """Detect absorption - large volume with minimal price movement."""
        cutoff = events[-1].trade.timestamp - timedelta(
            seconds=self.config.absorption_window_seconds
        )
        recent = [e for e in events if e.trade.timestamp > cutoff]
        
        if not recent:
            return None
            
        total_vol = sum(e.trade.size for e in recent)
        if total_vol < self.config.absorption_min_volume:
            return None
            
        # Check price movement
        prices = [e.trade.price for e in recent]
        price_range = (max(prices) - min(prices)) / np.mean(prices) if prices else 0
        
        if price_range > self.config.absorption_price_threshold:
            return None  # Too much movement
            
        # Determine if bid or ask absorption
        buy_vol = sum(e.trade.size for e in recent if e.trade.aggressor == AggressorSide.BUY)
        sell_vol = sum(e.trade.size for e in recent if e.trade.aggressor == AggressorSide.SELL)
        
        if buy_vol > sell_vol * 1.5:
            direction = "bullish"  # Ask absorbing buy flow
            description = "Ask absorption: selling absorbed without price decline"
        elif sell_vol > buy_vol * 1.5:
            direction = "bearish"  # Bid absorbing sell flow
            description = "Bid absorption: buying absorbed without price rise"
        else:
            direction = "neutral"
            description = "Mixed absorption"
            
        return TapePattern(
            timestamp=recent[-1].trade.timestamp,
            symbol=symbol,
            pattern_type=TapePatternType.ABSORPTION,
            trades=recent,
            start_price=recent[0].trade.price,
            end_price=recent[-1].trade.price,
            total_volume=total_vol,
            duration_seconds=(recent[-1].trade.timestamp - recent[0].trade.timestamp).total_seconds(),
            direction=direction,
            strength=1 - price_range / self.config.absorption_price_threshold,
            description=description,
        )
    
    def _detect_iceberg(
        self,
        symbol: str,
        events: List[TapeEvent],
    ) -> Optional[TapePattern]:
        """Detect iceberg order - repeated similar-sized prints at same price."""
        # Look at very recent prints
        recent = events[-20:] if len(events) >= 20 else events
        
        # Group by price
        price_groups: Dict[float, List[TapeEvent]] = {}
        for e in recent:
            price = round(e.trade.price, 2)
            if price not in price_groups:
                price_groups[price] = []
            price_groups[price].append(e)
            
        # Check each price level
        for price, group in price_groups.items():
            if len(group) < self.config.iceberg_min_prints:
                continue
                
            # Check size consistency
            sizes = [e.trade.size for e in group]
            mean_size = np.mean(sizes)
            std_size = np.std(sizes)
            
            if mean_size == 0:
                continue
                
            cv = std_size / mean_size  # Coefficient of variation
            
            if cv > self.config.iceberg_size_variance_threshold:
                continue  # Too much variance
                
            # Found iceberg
            total_vol = sum(sizes)
            
            # Direction based on aggressor
            buys = sum(1 for e in group if e.trade.aggressor == AggressorSide.BUY)
            sells = len(group) - buys
            
            if buys > sells:
                direction = "bullish"  # Passive seller (iceberg ask)
            else:
                direction = "bearish"  # Passive buyer (iceberg bid)
                
            return TapePattern(
                timestamp=group[-1].trade.timestamp,
                symbol=symbol,
                pattern_type=TapePatternType.ICEBERG,
                trades=group,
                start_price=price,
                end_price=price,
                total_volume=total_vol,
                duration_seconds=(group[-1].trade.timestamp - group[0].trade.timestamp).total_seconds(),
                direction=direction,
                strength=1 - cv,
                description=f"Iceberg at ${price:.2f}: {len(group)} prints, ~{int(mean_size)} avg size",
            )
            
        return None
    
    def _detect_sweep(
        self,
        symbol: str,
        events: List[TapeEvent],
    ) -> Optional[TapePattern]:
        """Detect sweep - aggressive execution across multiple levels."""
        # Look at very recent prints (within sweep window)
        cutoff_ms = self.config.sweep_time_window_ms
        
        recent = []
        ref_time = events[-1].trade.timestamp
        
        for e in reversed(events):
            diff_ms = (ref_time - e.trade.timestamp).total_seconds() * 1000
            if diff_ms > cutoff_ms:
                break
            recent.insert(0, e)
            
        if len(recent) < self.config.sweep_min_levels:
            return None
            
        # Check if same side and multiple price levels
        sides = set(e.trade.aggressor for e in recent)
        if len(sides) > 1 or AggressorSide.UNKNOWN in sides:
            return None  # Mixed or unknown
            
        prices = set(round(e.trade.price, 4) for e in recent)
        if len(prices) < self.config.sweep_min_levels:
            return None  # Not enough price levels
            
        side = recent[0].trade.aggressor
        direction = "bullish" if side == AggressorSide.BUY else "bearish"
        total_vol = sum(e.trade.size for e in recent)
        
        return TapePattern(
            timestamp=recent[-1].trade.timestamp,
            symbol=symbol,
            pattern_type=TapePatternType.SWEEP,
            trades=recent,
            start_price=recent[0].trade.price,
            end_price=recent[-1].trade.price,
            total_volume=total_vol,
            duration_seconds=(recent[-1].trade.timestamp - recent[0].trade.timestamp).total_seconds(),
            direction=direction,
            strength=len(prices) / 10,  # More levels = stronger
            description=f"Sweep: {len(prices)} levels, {total_vol:,} shares in {cutoff_ms}ms",
        )
    
    def _detect_accumulation_distribution(
        self,
        symbol: str,
        events: List[TapeEvent],
    ) -> Optional[TapePattern]:
        """Detect steady accumulation or distribution."""
        cutoff = events[-1].trade.timestamp - timedelta(
            seconds=self.config.accumulation_window_seconds
        )
        recent = [e for e in events if e.trade.timestamp > cutoff]
        
        if len(recent) < 20:
            return None
            
        # Track cumulative delta over time
        deltas = []
        running = 0
        
        for e in recent:
            if e.trade.aggressor == AggressorSide.BUY:
                running += e.trade.size
            elif e.trade.aggressor == AggressorSide.SELL:
                running -= e.trade.size
            deltas.append(running)
            
        if not deltas:
            return None
            
        # Check for consistent trend
        # Fit linear regression
        x = np.arange(len(deltas))
        slope = np.polyfit(x, deltas, 1)[0]
        
        # Check R-squared for consistency
        y_pred = slope * x + np.mean(deltas)
        ss_res = np.sum((np.array(deltas) - y_pred) ** 2)
        ss_tot = np.sum((np.array(deltas) - np.mean(deltas)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        if r_squared < 0.7:  # Not consistent enough
            return None
            
        total_vol = sum(e.trade.size for e in recent)
        
        if slope > 0:
            pattern_type = TapePatternType.ACCUMULATION
            direction = "bullish"
        else:
            pattern_type = TapePatternType.DISTRIBUTION
            direction = "bearish"
            
        return TapePattern(
            timestamp=recent[-1].trade.timestamp,
            symbol=symbol,
            pattern_type=pattern_type,
            trades=recent,
            start_price=recent[0].trade.price,
            end_price=recent[-1].trade.price,
            total_volume=total_vol,
            duration_seconds=(recent[-1].trade.timestamp - recent[0].trade.timestamp).total_seconds(),
            direction=direction,
            strength=r_squared,
            description=f"{pattern_type.value.title()}: R²={r_squared:.2f}, net delta={deltas[-1]:+,}",
        )
    
    def get_tape_summary(
        self,
        symbol: str,
        seconds: int = 60,
    ) -> Dict[str, Any]:
        """Get summary of recent tape activity."""
        events = list(self._events.get(symbol, []))
        
        if not events:
            return {"symbol": symbol, "has_data": False}
            
        cutoff = events[-1].trade.timestamp - timedelta(seconds=seconds)
        recent = [e for e in events if e.trade.timestamp > cutoff]
        
        if not recent:
            return {"symbol": symbol, "has_data": False}
            
        buy_vol = sum(e.trade.size for e in recent if e.trade.aggressor == AggressorSide.BUY)
        sell_vol = sum(e.trade.size for e in recent if e.trade.aggressor == AggressorSide.SELL)
        total_vol = buy_vol + sell_vol
        
        # Size distribution
        blocks = sum(1 for e in recent if e.size_class in (PrintSize.BLOCK, PrintSize.INSTITUTIONAL, PrintSize.WHALE))
        
        return {
            "symbol": symbol,
            "has_data": True,
            "period_seconds": seconds,
            "num_trades": len(recent),
            "total_volume": total_vol,
            "buy_volume": buy_vol,
            "sell_volume": sell_vol,
            "buy_pct": buy_vol / total_vol * 100 if total_vol > 0 else 0,
            "cumulative_delta": self._cumulative_delta.get(symbol, 0),
            "block_prints": blocks,
            "vwap": (
                self._vwap_state[symbol]["value"] / self._vwap_state[symbol]["volume"]
                if self._vwap_state.get(symbol, {}).get("volume", 0) > 0 else 0
            ),
            "last_price": recent[-1].trade.price,
        }
    
    def get_recent_patterns(
        self,
        symbol: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent patterns for symbol."""
        patterns = self._patterns.get(symbol, [])[-limit:]
        return [p.to_dict() for p in patterns]
