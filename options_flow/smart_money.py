"""
Smart Money Tracking
====================
Identifies and tracks institutional and informed flow patterns.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from enum import Enum
from typing import Optional, List, Dict, Any, Set
import logging
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class FlowCategory(Enum):
    """Classification of flow source."""
    RETAIL = "retail"
    INSTITUTIONAL = "institutional"
    MARKET_MAKER = "market_maker"
    HEDGE_FUND = "hedge_fund"
    UNKNOWN = "unknown"


class PositionIntent(Enum):
    """Inferred intent behind position."""
    OPENING = "opening"
    CLOSING = "closing"
    ROLLING = "rolling"
    HEDGING = "hedging"
    SPECULATING = "speculating"


@dataclass
class InstitutionalFlow:
    """Represents identified institutional flow."""
    symbol: str
    timestamp: datetime
    category: FlowCategory
    intent: PositionIntent
    direction: str  # "bullish" or "bearish"
    
    # Position details
    strike: float
    expiry: date
    is_call: bool
    contracts: int
    premium: float
    
    # Context
    spot_price: float
    iv: float = 0.0
    delta: float = 0.0
    
    # Classification confidence
    confidence: float = 0.0  # 0-100
    signals: List[str] = field(default_factory=list)  # Why we classified this way
    
    @property
    def notional(self) -> float:
        """Notional value controlled."""
        return self.contracts * 100 * self.spot_price
    
    @property
    def is_otm(self) -> bool:
        """Is option out of the money."""
        if self.is_call:
            return self.strike > self.spot_price
        return self.strike < self.spot_price
    
    @property
    def moneyness_pct(self) -> float:
        """Percent away from ATM."""
        return (self.strike - self.spot_price) / self.spot_price * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "intent": self.intent.value,
            "direction": self.direction,
            "strike": self.strike,
            "expiry": self.expiry.isoformat(),
            "is_call": self.is_call,
            "contracts": self.contracts,
            "premium": self.premium,
            "spot_price": self.spot_price,
            "confidence": self.confidence,
            "signals": self.signals,
        }


@dataclass
class SmartMoneyPosition:
    """Aggregated smart money position in a symbol."""
    symbol: str
    flows: List[InstitutionalFlow] = field(default_factory=list)
    
    @property
    def total_bullish_premium(self) -> float:
        return sum(f.premium for f in self.flows if f.direction == "bullish")
    
    @property
    def total_bearish_premium(self) -> float:
        return sum(f.premium for f in self.flows if f.direction == "bearish")
    
    @property
    def net_direction(self) -> str:
        if self.total_bullish_premium > self.total_bearish_premium * 1.2:
            return "bullish"
        elif self.total_bearish_premium > self.total_bullish_premium * 1.2:
            return "bearish"
        return "neutral"
    
    @property
    def conviction_score(self) -> float:
        """Score based on premium and consistency."""
        if not self.flows:
            return 0
        
        total = self.total_bullish_premium + self.total_bearish_premium
        consistency = abs(self.total_bullish_premium - self.total_bearish_premium) / max(1, total)
        avg_confidence = statistics.mean(f.confidence for f in self.flows)
        
        return min(100, consistency * 50 + avg_confidence * 0.5)
    
    def get_key_strikes(self) -> Dict[float, Dict[str, Any]]:
        """Get breakdown by strike."""
        by_strike = defaultdict(lambda: {
            "bullish_premium": 0,
            "bearish_premium": 0,
            "contracts": 0,
            "flow_count": 0,
        })
        
        for f in self.flows:
            by_strike[f.strike]["contracts"] += f.contracts
            by_strike[f.strike]["flow_count"] += 1
            if f.direction == "bullish":
                by_strike[f.strike]["bullish_premium"] += f.premium
            else:
                by_strike[f.strike]["bearish_premium"] += f.premium
                
        return dict(by_strike)


@dataclass
class TrackerConfig:
    """Configuration for smart money detection."""
    # Size thresholds (adjusted per underlying liquidity)
    min_premium_institutional: float = 100_000
    min_contracts_institutional: int = 100
    
    # Behavioral signals
    unusual_strike_oi_threshold: int = 500  # Low OI = unusual strike
    sweep_aggression_threshold: float = 0.8  # % at/above ask
    
    # Time patterns
    opening_auction_minutes: int = 30  # First 30 min
    closing_auction_minutes: int = 30  # Last 30 min
    
    # Confidence weights
    weight_size: float = 0.25
    weight_aggression: float = 0.25
    weight_timing: float = 0.15
    weight_strike_selection: float = 0.20
    weight_consistency: float = 0.15


class SmartMoneyTracker:
    """
    Tracks and analyzes institutional/informed flow.
    
    Identifies smart money through:
    - Trade size and premium
    - Execution aggressiveness
    - Strike selection (unusual/illiquid)
    - Timing patterns
    - Position building behavior
    """
    
    def __init__(self, config: Optional[TrackerConfig] = None):
        self.config = config or TrackerConfig()
        self._positions: Dict[str, SmartMoneyPosition] = defaultdict(
            lambda: SmartMoneyPosition(symbol="")
        )
        self._flow_history: Dict[str, List[InstitutionalFlow]] = defaultdict(list)
        self._daily_patterns: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
    def classify_trade(
        self,
        symbol: str,
        strike: float,
        expiry: date,
        is_call: bool,
        contracts: int,
        premium: float,
        spot_price: float,
        timestamp: datetime,
        execution_price: float,
        bid: float,
        ask: float,
        open_interest: int,
        volume_before: int,
        iv: float = 0.0,
        delta: float = 0.0,
    ) -> Optional[InstitutionalFlow]:
        """
        Classify a trade and determine if it's smart money.
        
        Returns InstitutionalFlow if classified as institutional, None otherwise.
        """
        signals = []
        confidence_components = []
        
        # 1. Size analysis
        size_score = self._analyze_size(premium, contracts, signals)
        confidence_components.append(("size", size_score, self.config.weight_size))
        
        # 2. Execution aggressiveness
        aggression_score = self._analyze_aggression(
            execution_price, bid, ask, signals
        )
        confidence_components.append(("aggression", aggression_score, self.config.weight_aggression))
        
        # 3. Timing analysis
        timing_score = self._analyze_timing(timestamp, signals)
        confidence_components.append(("timing", timing_score, self.config.weight_timing))
        
        # 4. Strike selection
        strike_score = self._analyze_strike(
            strike, spot_price, open_interest, is_call, signals
        )
        confidence_components.append(("strike", strike_score, self.config.weight_strike_selection))
        
        # 5. Consistency with prior flow
        consistency_score = self._analyze_consistency(
            symbol, strike, is_call, signals
        )
        confidence_components.append(("consistency", consistency_score, self.config.weight_consistency))
        
        # Calculate weighted confidence
        confidence = sum(score * weight for _, score, weight in confidence_components)
        
        # Must meet minimum threshold
        if confidence < 40 or premium < self.config.min_premium_institutional:
            return None
            
        # Determine category
        category = self._determine_category(confidence_components, signals)
        
        # Determine intent
        intent = self._determine_intent(
            contracts, open_interest, volume_before, signals
        )
        
        # Determine direction
        if is_call:
            direction = "bullish" if "aggressive_buy" in signals else "bearish"
        else:
            direction = "bearish" if "aggressive_buy" in signals else "bullish"
            
        flow = InstitutionalFlow(
            symbol=symbol,
            timestamp=timestamp,
            category=category,
            intent=intent,
            direction=direction,
            strike=strike,
            expiry=expiry,
            is_call=is_call,
            contracts=contracts,
            premium=premium,
            spot_price=spot_price,
            iv=iv,
            delta=delta,
            confidence=confidence,
            signals=signals,
        )
        
        # Track the flow
        self._track_flow(flow)
        
        return flow
    
    def _analyze_size(
        self,
        premium: float,
        contracts: int,
        signals: List[str],
    ) -> float:
        """Analyze trade size for institutional characteristics."""
        score = 0
        
        if premium >= 1_000_000:
            signals.append("whale_premium")
            score = 100
        elif premium >= 500_000:
            signals.append("large_premium")
            score = 80
        elif premium >= 250_000:
            signals.append("medium_premium")
            score = 60
        elif premium >= self.config.min_premium_institutional:
            score = 40
            
        if contracts >= 1000:
            signals.append("large_contract_size")
            score = max(score, 80)
        elif contracts >= 500:
            score = max(score, 60)
            
        return score
    
    def _analyze_aggression(
        self,
        execution_price: float,
        bid: float,
        ask: float,
        signals: List[str],
    ) -> float:
        """Analyze execution aggressiveness."""
        if ask <= bid or execution_price <= 0:
            return 50  # Can't determine
            
        spread = ask - bid
        mid = (bid + ask) / 2
        
        # Where in the spread did they execute?
        if spread > 0:
            position = (execution_price - bid) / spread
        else:
            position = 0.5
            
        if position >= 0.9:  # At or above ask
            signals.append("aggressive_buy")
            return 100
        elif position <= 0.1:  # At or below bid
            signals.append("aggressive_sell")
            return 100
        elif position >= 0.7:
            signals.append("leaning_ask")
            return 70
        elif position <= 0.3:
            signals.append("leaning_bid")
            return 70
        else:
            return 40  # Mid execution, less directional conviction
    
    def _analyze_timing(
        self,
        timestamp: datetime,
        signals: List[str],
    ) -> float:
        """Analyze trade timing for institutional patterns."""
        hour = timestamp.hour
        minute = timestamp.minute
        
        # Market hours (EST)
        market_open = 9 * 60 + 30  # 9:30
        market_close = 16 * 60  # 16:00
        
        time_minutes = hour * 60 + minute
        
        # Opening auction (first 30 min) - institutional order flow
        if time_minutes <= market_open + self.config.opening_auction_minutes:
            signals.append("opening_auction")
            return 80
            
        # Closing auction (last 30 min) - index rebalancing
        if time_minutes >= market_close - self.config.closing_auction_minutes:
            signals.append("closing_auction")
            return 75
            
        # Power hour (3-4pm) - often institutional
        if 15 * 60 <= time_minutes < 16 * 60:
            signals.append("power_hour")
            return 65
            
        # Mid-day lull - less institutional
        if 12 * 60 <= time_minutes < 14 * 60:
            return 40
            
        return 50
    
    def _analyze_strike(
        self,
        strike: float,
        spot_price: float,
        open_interest: int,
        is_call: bool,
        signals: List[str],
    ) -> float:
        """Analyze strike selection for unusual activity."""
        moneyness = (strike - spot_price) / spot_price
        
        # Unusual/illiquid strike selection
        if open_interest < self.config.unusual_strike_oi_threshold:
            signals.append("unusual_strike")
            score = 80
        else:
            score = 40
            
        # Deep OTM with conviction
        if is_call and moneyness > 0.1:  # >10% OTM call
            signals.append("deep_otm_call")
            score = max(score, 75)
        elif not is_call and moneyness < -0.1:  # >10% OTM put
            signals.append("deep_otm_put")
            score = max(score, 75)
            
        # ATM options (precise strike selection)
        if abs(moneyness) < 0.02:
            signals.append("atm_strike")
            score = max(score, 60)
            
        return score
    
    def _analyze_consistency(
        self,
        symbol: str,
        strike: float,
        is_call: bool,
        signals: List[str],
    ) -> float:
        """Check consistency with prior smart money flow."""
        recent_flows = self._get_recent_flows(symbol, hours=4)
        
        if not recent_flows:
            return 50  # No history
            
        # Same strike hits
        same_strike = [
            f for f in recent_flows
            if f.strike == strike and f.is_call == is_call
        ]
        
        if len(same_strike) >= 3:
            signals.append("repeated_strike")
            return 90
        elif len(same_strike) >= 2:
            signals.append("building_position")
            return 75
            
        # Same direction
        if is_call:
            same_direction = [f for f in recent_flows if f.direction == "bullish"]
        else:
            same_direction = [f for f in recent_flows if f.direction == "bearish"]
            
        if len(same_direction) > len(recent_flows) * 0.7:
            signals.append("consistent_direction")
            return 70
            
        return 50
    
    def _determine_category(
        self,
        components: List[tuple],
        signals: List[str],
    ) -> FlowCategory:
        """Determine the category of flow."""
        # High aggression + large size + unusual timing = hedge fund
        has_aggression = any("aggressive" in s for s in signals)
        has_size = any(s in signals for s in ["whale_premium", "large_premium"])
        has_timing = any(s in signals for s in ["opening_auction", "power_hour"])
        
        if has_aggression and has_size and has_timing:
            return FlowCategory.HEDGE_FUND
            
        if has_size and "unusual_strike" in signals:
            return FlowCategory.INSTITUTIONAL
            
        if "repeated_strike" in signals or "building_position" in signals:
            return FlowCategory.INSTITUTIONAL
            
        return FlowCategory.UNKNOWN
    
    def _determine_intent(
        self,
        contracts: int,
        open_interest: int,
        volume_before: int,
        signals: List[str],
    ) -> PositionIntent:
        """Determine the intent behind the position."""
        # Opening: volume > OI suggests new positions
        if volume_before + contracts > open_interest * 0.5:
            signals.append("likely_opening")
            return PositionIntent.OPENING
            
        # Large relative to OI
        if contracts > open_interest * 0.1:
            signals.append("significant_vs_oi")
            return PositionIntent.OPENING
            
        return PositionIntent.SPECULATING
    
    def _track_flow(self, flow: InstitutionalFlow):
        """Track flow internally."""
        self._positions[flow.symbol].symbol = flow.symbol
        self._positions[flow.symbol].flows.append(flow)
        self._flow_history[flow.symbol].append(flow)
        
        # Cleanup old data
        self._cleanup()
    
    def _get_recent_flows(
        self,
        symbol: str,
        hours: int = 24,
    ) -> List[InstitutionalFlow]:
        """Get recent flows for symbol."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            f for f in self._flow_history.get(symbol, [])
            if f.timestamp > cutoff
        ]
    
    def _cleanup(self):
        """Remove old data."""
        cutoff = datetime.now() - timedelta(days=5)
        
        for symbol in list(self._flow_history.keys()):
            self._flow_history[symbol] = [
                f for f in self._flow_history[symbol]
                if f.timestamp > cutoff
            ]
            
        # Also cleanup positions
        for symbol in list(self._positions.keys()):
            self._positions[symbol].flows = [
                f for f in self._positions[symbol].flows
                if f.timestamp > cutoff
            ]
    
    def get_position(self, symbol: str) -> SmartMoneyPosition:
        """Get aggregated smart money position."""
        return self._positions[symbol]
    
    def get_top_symbols(
        self,
        hours: int = 24,
        min_flows: int = 2,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get symbols with most smart money activity."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        symbol_stats = []
        for symbol, flows in self._flow_history.items():
            recent = [f for f in flows if f.timestamp > cutoff]
            
            if len(recent) < min_flows:
                continue
                
            bullish = sum(f.premium for f in recent if f.direction == "bullish")
            bearish = sum(f.premium for f in recent if f.direction == "bearish")
            
            symbol_stats.append({
                "symbol": symbol,
                "flow_count": len(recent),
                "bullish_premium": bullish,
                "bearish_premium": bearish,
                "net_premium": bullish - bearish,
                "direction": "bullish" if bullish > bearish else "bearish",
                "avg_confidence": statistics.mean(f.confidence for f in recent),
            })
            
        # Sort by absolute net premium
        symbol_stats.sort(key=lambda x: abs(x["net_premium"]), reverse=True)
        return symbol_stats[:limit]
    
    def get_sector_flow(
        self,
        symbol_to_sector: Dict[str, str],
        hours: int = 24,
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate smart money flow by sector."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        sector_data = defaultdict(lambda: {
            "bullish_premium": 0,
            "bearish_premium": 0,
            "flow_count": 0,
            "symbols": set(),
        })
        
        for symbol, flows in self._flow_history.items():
            sector = symbol_to_sector.get(symbol, "Unknown")
            recent = [f for f in flows if f.timestamp > cutoff]
            
            for f in recent:
                sector_data[sector]["flow_count"] += 1
                sector_data[sector]["symbols"].add(symbol)
                
                if f.direction == "bullish":
                    sector_data[sector]["bullish_premium"] += f.premium
                else:
                    sector_data[sector]["bearish_premium"] += f.premium
                    
        # Convert to regular dict
        result = {}
        for sector, data in sector_data.items():
            total = data["bullish_premium"] + data["bearish_premium"]
            result[sector] = {
                **data,
                "symbols": list(data["symbols"]),
                "total_premium": total,
                "net_premium": data["bullish_premium"] - data["bearish_premium"],
                "direction": "bullish" if data["bullish_premium"] > data["bearish_premium"] else "bearish",
            }
            
        return result
    
    def get_flow_timeline(
        self,
        symbol: str,
        hours: int = 8,
        bucket_minutes: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get timeline of smart money flow."""
        cutoff = datetime.now() - timedelta(hours=hours)
        flows = [f for f in self._flow_history.get(symbol, []) if f.timestamp > cutoff]
        
        if not flows:
            return []
            
        # Bucket by time
        buckets = defaultdict(lambda: {"bullish": 0, "bearish": 0, "count": 0})
        
        for f in flows:
            # Round to bucket
            bucket_time = f.timestamp.replace(
                minute=(f.timestamp.minute // bucket_minutes) * bucket_minutes,
                second=0,
                microsecond=0,
            )
            bucket_key = bucket_time.isoformat()
            
            buckets[bucket_key]["count"] += 1
            if f.direction == "bullish":
                buckets[bucket_key]["bullish"] += f.premium
            else:
                buckets[bucket_key]["bearish"] += f.premium
                
        # Convert to list
        timeline = [
            {"timestamp": k, **v, "net": v["bullish"] - v["bearish"]}
            for k, v in sorted(buckets.items())
        ]
        
        return timeline
