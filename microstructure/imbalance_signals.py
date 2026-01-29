"""
Order Book Imbalance Signals
============================
Detects and generates signals from order book imbalances.
"""

import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from collections import deque
import logging

from .order_flow_features import OrderBookSnapshot, PriceLevel

logger = logging.getLogger(__name__)


class ImbalanceType(Enum):
    """Types of order book imbalance."""
    BID_HEAVY = "bid_heavy"  # More size on bid
    ASK_HEAVY = "ask_heavy"  # More size on ask
    STACKED_BID = "stacked_bid"  # Large bid wall
    STACKED_ASK = "stacked_ask"  # Large ask wall
    ABSORPTION = "absorption"  # Large orders absorbing flow
    VACUUM = "vacuum"  # Thin book one side
    BALANCED = "balanced"


class SignalStrength(Enum):
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    EXTREME = 4


@dataclass
class OrderImbalance:
    """Detected order book imbalance."""
    timestamp: datetime
    symbol: str
    imbalance_type: ImbalanceType
    
    # Imbalance metrics
    imbalance_ratio: float  # bid_size / ask_size
    imbalance_pct: float  # (bid - ask) / (bid + ask)
    
    # Depth info
    bid_depth: int
    ask_depth: int
    bid_levels: int
    ask_levels: int
    
    # Price context
    mid_price: float
    spread_bps: float
    
    # Wall detection
    wall_price: Optional[float] = None
    wall_size: int = 0
    
    # Strength
    strength: SignalStrength = SignalStrength.MODERATE
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "imbalance_type": self.imbalance_type.value,
            "imbalance_ratio": self.imbalance_ratio,
            "imbalance_pct": self.imbalance_pct,
            "bid_depth": self.bid_depth,
            "ask_depth": self.ask_depth,
            "mid_price": self.mid_price,
            "spread_bps": self.spread_bps,
            "wall_price": self.wall_price,
            "wall_size": self.wall_size,
            "strength": self.strength.value,
        }


@dataclass
class ImbalanceSignal:
    """Trading signal from imbalance detection."""
    timestamp: datetime
    symbol: str
    direction: str  # "long" or "short"
    strength: SignalStrength
    confidence: float  # 0-1
    
    # Signal source
    imbalance: OrderImbalance
    
    # Suggested levels
    entry_price: float
    stop_price: float
    target_price: float
    
    # Context
    reasoning: str = ""
    
    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry_price - self.stop_price)
        reward = abs(self.target_price - self.entry_price)
        return reward / risk if risk > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "direction": self.direction,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "risk_reward": self.risk_reward,
            "reasoning": self.reasoning,
            "imbalance": self.imbalance.to_dict(),
        }


@dataclass
class ImbalanceConfig:
    """Configuration for imbalance detection."""
    # Imbalance thresholds
    min_imbalance_ratio: float = 1.5  # 1.5:1 ratio
    strong_imbalance_ratio: float = 3.0  # 3:1 ratio
    extreme_imbalance_ratio: float = 5.0  # 5:1 ratio
    
    # Depth levels to analyze
    depth_levels: int = 10
    
    # Wall detection
    wall_size_multiplier: float = 3.0  # vs avg level size
    min_wall_size: int = 10000
    
    # Absorption detection
    absorption_lookback_seconds: int = 30
    absorption_min_volume: int = 5000
    
    # Vacuum detection
    vacuum_depth_threshold: int = 1000  # Thin if < this
    
    # Signal generation
    min_signal_confidence: float = 0.5
    cooldown_seconds: int = 5


class ImbalanceDetector:
    """
    Detects order book imbalances and generates trading signals.
    
    Types of imbalances:
    - Directional: More size on one side
    - Walls: Large resting orders
    - Absorption: Large orders eating flow
    - Vacuum: Thin liquidity creating gaps
    """
    
    def __init__(self, config: Optional[ImbalanceConfig] = None):
        self.config = config or ImbalanceConfig()
        
        # History for pattern detection
        self._book_history: Dict[str, deque] = {}
        self._imbalance_history: Dict[str, deque] = {}
        self._signal_history: Dict[str, List[ImbalanceSignal]] = {}
        self._last_signal_time: Dict[str, datetime] = {}
        
    def analyze(self, book: OrderBookSnapshot) -> Optional[OrderImbalance]:
        """
        Analyze order book for imbalances.
        
        Returns OrderImbalance if significant imbalance detected.
        """
        symbol = book.symbol
        
        # Store in history
        if symbol not in self._book_history:
            self._book_history[symbol] = deque(maxlen=1000)
        self._book_history[symbol].append(book)
        
        # Calculate basic imbalance
        bid_depth = book.total_bid_size(self.config.depth_levels)
        ask_depth = book.total_ask_size(self.config.depth_levels)
        
        if bid_depth == 0 and ask_depth == 0:
            return None
            
        # Imbalance metrics
        total = bid_depth + ask_depth
        imbalance_pct = (bid_depth - ask_depth) / total if total > 0 else 0
        imbalance_ratio = bid_depth / ask_depth if ask_depth > 0 else float('inf')
        
        if ask_depth > bid_depth:
            imbalance_ratio = ask_depth / bid_depth if bid_depth > 0 else float('inf')
            
        # Check if significant
        if imbalance_ratio < self.config.min_imbalance_ratio:
            return None
            
        # Determine type and strength
        imbalance_type, strength, wall_info = self._classify_imbalance(
            book, bid_depth, ask_depth, imbalance_ratio
        )
        
        imbalance = OrderImbalance(
            timestamp=book.timestamp,
            symbol=symbol,
            imbalance_type=imbalance_type,
            imbalance_ratio=imbalance_ratio,
            imbalance_pct=imbalance_pct,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            bid_levels=len(book.bids),
            ask_levels=len(book.asks),
            mid_price=book.mid_price,
            spread_bps=book.spread_bps,
            wall_price=wall_info.get("price"),
            wall_size=wall_info.get("size", 0),
            strength=strength,
        )
        
        # Store
        if symbol not in self._imbalance_history:
            self._imbalance_history[symbol] = deque(maxlen=500)
        self._imbalance_history[symbol].append(imbalance)
        
        return imbalance
    
    def _classify_imbalance(
        self,
        book: OrderBookSnapshot,
        bid_depth: int,
        ask_depth: int,
        imbalance_ratio: float,
    ) -> Tuple[ImbalanceType, SignalStrength, Dict[str, Any]]:
        """Classify the type and strength of imbalance."""
        wall_info = {}
        
        # Determine strength from ratio
        if imbalance_ratio >= self.config.extreme_imbalance_ratio:
            strength = SignalStrength.EXTREME
        elif imbalance_ratio >= self.config.strong_imbalance_ratio:
            strength = SignalStrength.STRONG
        elif imbalance_ratio >= self.config.min_imbalance_ratio:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK
            
        # Check for walls
        bid_wall = self._detect_wall(book.bids)
        ask_wall = self._detect_wall(book.asks)
        
        if bid_wall:
            wall_info = {"price": bid_wall.price, "size": bid_wall.size}
            return ImbalanceType.STACKED_BID, strength, wall_info
            
        if ask_wall:
            wall_info = {"price": ask_wall.price, "size": ask_wall.size}
            return ImbalanceType.STACKED_ASK, strength, wall_info
            
        # Check for vacuum (thin liquidity)
        if ask_depth < self.config.vacuum_depth_threshold:
            return ImbalanceType.VACUUM, strength, wall_info
            
        if bid_depth < self.config.vacuum_depth_threshold:
            return ImbalanceType.VACUUM, strength, wall_info
            
        # Simple directional imbalance
        if bid_depth > ask_depth:
            return ImbalanceType.BID_HEAVY, strength, wall_info
        else:
            return ImbalanceType.ASK_HEAVY, strength, wall_info
    
    def _detect_wall(
        self,
        levels: List[PriceLevel],
    ) -> Optional[PriceLevel]:
        """Detect if there's a wall (large resting order)."""
        if len(levels) < 3:
            return None
            
        # Calculate average size
        sizes = [l.size for l in levels[:self.config.depth_levels]]
        avg_size = np.mean(sizes)
        
        # Check each level for wall
        for level in levels[:5]:  # Only check top 5 levels
            if level.size >= avg_size * self.config.wall_size_multiplier:
                if level.size >= self.config.min_wall_size:
                    return level
                    
        return None
    
    def generate_signal(
        self,
        imbalance: OrderImbalance,
    ) -> Optional[ImbalanceSignal]:
        """
        Generate trading signal from imbalance.
        """
        symbol = imbalance.symbol
        
        # Check cooldown
        if symbol in self._last_signal_time:
            elapsed = (imbalance.timestamp - self._last_signal_time[symbol]).total_seconds()
            if elapsed < self.config.cooldown_seconds:
                return None
                
        # Determine direction
        direction = self._get_signal_direction(imbalance)
        if not direction:
            return None
            
        # Calculate confidence
        confidence = self._calculate_confidence(imbalance)
        if confidence < self.config.min_signal_confidence:
            return None
            
        # Calculate levels
        entry, stop, target = self._calculate_levels(imbalance, direction)
        
        # Build reasoning
        reasoning = self._build_reasoning(imbalance, direction)
        
        signal = ImbalanceSignal(
            timestamp=imbalance.timestamp,
            symbol=symbol,
            direction=direction,
            strength=imbalance.strength,
            confidence=confidence,
            imbalance=imbalance,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            reasoning=reasoning,
        )
        
        # Store
        self._last_signal_time[symbol] = imbalance.timestamp
        if symbol not in self._signal_history:
            self._signal_history[symbol] = []
        self._signal_history[symbol].append(signal)
        
        return signal
    
    def _get_signal_direction(
        self,
        imbalance: OrderImbalance,
    ) -> Optional[str]:
        """Determine signal direction from imbalance type."""
        if imbalance.imbalance_type in (ImbalanceType.BID_HEAVY, ImbalanceType.STACKED_BID):
            return "long"  # Buyers overwhelming sellers
        elif imbalance.imbalance_type in (ImbalanceType.ASK_HEAVY, ImbalanceType.STACKED_ASK):
            return "short"  # Sellers overwhelming buyers
        elif imbalance.imbalance_type == ImbalanceType.VACUUM:
            # Vacuum direction depends on which side is thin
            if imbalance.ask_depth < imbalance.bid_depth:
                return "long"  # Thin asks, price can run up
            else:
                return "short"  # Thin bids, price can run down
        return None
    
    def _calculate_confidence(
        self,
        imbalance: OrderImbalance,
    ) -> float:
        """Calculate signal confidence."""
        confidence = 0.0
        
        # Ratio contribution
        ratio = imbalance.imbalance_ratio
        if ratio >= self.config.extreme_imbalance_ratio:
            confidence += 0.4
        elif ratio >= self.config.strong_imbalance_ratio:
            confidence += 0.3
        elif ratio >= self.config.min_imbalance_ratio:
            confidence += 0.2
            
        # Wall contribution
        if imbalance.wall_size > 0:
            confidence += 0.2
            
        # Spread contribution (tighter = better)
        if imbalance.spread_bps < 5:
            confidence += 0.15
        elif imbalance.spread_bps < 10:
            confidence += 0.1
            
        # Historical consistency
        history = list(self._imbalance_history.get(imbalance.symbol, []))[-10:]
        if len(history) >= 3:
            same_direction = sum(
                1 for h in history
                if self._get_signal_direction(h) == self._get_signal_direction(imbalance)
            )
            if same_direction / len(history) > 0.7:
                confidence += 0.25
                
        return min(1.0, confidence)
    
    def _calculate_levels(
        self,
        imbalance: OrderImbalance,
        direction: str,
    ) -> Tuple[float, float, float]:
        """Calculate entry, stop, and target prices."""
        mid = imbalance.mid_price
        
        # Use wall as reference if present
        if imbalance.wall_price:
            if direction == "long":
                entry = mid
                stop = imbalance.wall_price * 0.998  # Below wall
                target = mid + (mid - stop) * 2  # 2:1 R:R
            else:
                entry = mid
                stop = imbalance.wall_price * 1.002  # Above wall
                target = mid - (stop - mid) * 2
        else:
            # Default to spread-based levels
            spread = imbalance.spread_bps / 10000 * mid
            
            if direction == "long":
                entry = mid
                stop = mid - spread * 3
                target = mid + spread * 6
            else:
                entry = mid
                stop = mid + spread * 3
                target = mid - spread * 6
                
        return entry, stop, target
    
    def _build_reasoning(
        self,
        imbalance: OrderImbalance,
        direction: str,
    ) -> str:
        """Build human-readable reasoning."""
        parts = []
        
        parts.append(f"{imbalance.imbalance_type.value.replace('_', ' ').title()}")
        parts.append(f"Ratio: {imbalance.imbalance_ratio:.1f}:1")
        parts.append(f"Bid: {imbalance.bid_depth:,} vs Ask: {imbalance.ask_depth:,}")
        
        if imbalance.wall_size > 0:
            side = "bid" if "bid" in imbalance.imbalance_type.value.lower() else "ask"
            parts.append(f"Wall: {imbalance.wall_size:,} @ ${imbalance.wall_price:.2f} ({side})")
            
        return " | ".join(parts)
    
    def get_current_state(self, symbol: str) -> Dict[str, Any]:
        """Get current imbalance state for symbol."""
        history = list(self._imbalance_history.get(symbol, []))
        
        if not history:
            return {"symbol": symbol, "has_data": False}
            
        recent = history[-1]
        
        # Calculate trend
        if len(history) >= 5:
            recent_ratios = [h.imbalance_ratio for h in history[-5:]]
            trend = "increasing" if recent_ratios[-1] > recent_ratios[0] else "decreasing"
        else:
            trend = "unknown"
            
        return {
            "symbol": symbol,
            "has_data": True,
            "current_imbalance": recent.to_dict(),
            "trend": trend,
            "signal_count_last_hour": len([
                s for s in self._signal_history.get(symbol, [])
                if (recent.timestamp - s.timestamp).total_seconds() < 3600
            ]),
        }


class MultiSymbolImbalanceScanner:
    """
    Scans multiple symbols for imbalance opportunities.
    """
    
    def __init__(self, config: Optional[ImbalanceConfig] = None):
        self.config = config or ImbalanceConfig()
        self.detectors: Dict[str, ImbalanceDetector] = {}
        
    def scan(
        self,
        books: List[OrderBookSnapshot],
    ) -> List[ImbalanceSignal]:
        """
        Scan multiple order books for signals.
        """
        signals = []
        
        for book in books:
            if book.symbol not in self.detectors:
                self.detectors[book.symbol] = ImbalanceDetector(self.config)
                
            detector = self.detectors[book.symbol]
            imbalance = detector.analyze(book)
            
            if imbalance:
                signal = detector.generate_signal(imbalance)
                if signal:
                    signals.append(signal)
                    
        # Sort by confidence
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals
    
    def get_rankings(self) -> List[Dict[str, Any]]:
        """Get symbols ranked by imbalance strength."""
        rankings = []
        
        for symbol, detector in self.detectors.items():
            state = detector.get_current_state(symbol)
            if state.get("has_data"):
                imb = state["current_imbalance"]
                rankings.append({
                    "symbol": symbol,
                    "imbalance_ratio": imb["imbalance_ratio"],
                    "imbalance_type": imb["imbalance_type"],
                    "strength": imb["strength"],
                })
                
        rankings.sort(key=lambda x: x["imbalance_ratio"], reverse=True)
        return rankings
