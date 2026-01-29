"""
Triangular Arbitrage Detection
==============================
Detects triangular arbitrage opportunities within single exchanges.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set, Tuple
from enum import Enum
import logging
from collections import defaultdict
import itertools

from .price_feeds import Exchange, ExchangePrice

logger = logging.getLogger(__name__)


@dataclass
class CurrencyTriangle:
    """Represents a triangular arbitrage path."""
    base: str  # Starting currency
    intermediate: str  # Middle currency
    quote: str  # End currency (same as base for profit)
    
    # Trading pairs
    pair1: str  # base -> intermediate
    pair2: str  # intermediate -> quote
    pair3: str  # quote -> base
    
    # Direction for each leg (buy or sell)
    pair1_side: str  # "buy" or "sell"
    pair2_side: str
    pair3_side: str
    
    def __hash__(self):
        return hash((self.base, self.intermediate, self.quote))
    
    def __eq__(self, other):
        if not isinstance(other, CurrencyTriangle):
            return False
        return (
            self.base == other.base
            and self.intermediate == other.intermediate
            and self.quote == other.quote
        )


@dataclass
class TriangularOpportunity:
    """Detected triangular arbitrage opportunity."""
    id: str
    exchange: Exchange
    triangle: CurrencyTriangle
    detected_at: datetime
    
    # Execution path
    leg1_pair: str
    leg1_side: str
    leg1_price: float
    leg1_size: float
    
    leg2_pair: str
    leg2_side: str
    leg2_price: float
    leg2_size: float
    
    leg3_pair: str
    leg3_side: str
    leg3_price: float
    leg3_size: float
    
    # Profit calculation
    start_amount: float
    end_amount: float
    profit_pct: float
    profit_amount: float
    
    # After fees
    net_profit_pct: float
    net_profit_amount: float
    
    # Constraints
    max_size: float
    estimated_fees: float
    
    # Quality
    confidence: float = 0.0
    expires_at: Optional[datetime] = None
    
    @property
    def is_valid(self) -> bool:
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return self.net_profit_pct > 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "exchange": self.exchange.value,
            "triangle": f"{self.triangle.base}->{self.triangle.intermediate}->{self.triangle.quote}",
            "detected_at": self.detected_at.isoformat(),
            "legs": [
                {"pair": self.leg1_pair, "side": self.leg1_side, "price": self.leg1_price},
                {"pair": self.leg2_pair, "side": self.leg2_side, "price": self.leg2_price},
                {"pair": self.leg3_pair, "side": self.leg3_side, "price": self.leg3_price},
            ],
            "start_amount": self.start_amount,
            "end_amount": self.end_amount,
            "profit_pct": self.profit_pct,
            "net_profit_pct": self.net_profit_pct,
            "max_size": self.max_size,
            "confidence": self.confidence,
        }


@dataclass
class TriangularConfig:
    """Configuration for triangular arbitrage detection."""
    # Profit thresholds
    min_profit_pct: float = 0.1  # 0.1% minimum
    min_net_profit_pct: float = 0.05  # After fees
    
    # Fee estimate per leg
    taker_fee: float = 0.001  # 0.1%
    
    # Size
    min_size_usd: float = 100.0
    max_size_usd: float = 10_000.0
    
    # Currencies to include in triangles
    base_currencies: Set[str] = field(default_factory=lambda: {"BTC", "ETH", "USDT", "USDC", "BNB"})
    
    # Timing
    opportunity_ttl_seconds: float = 2.0
    
    # Max triangles to track per exchange
    max_triangles: int = 100


class TriangularArbDetector:
    """
    Detects triangular arbitrage within a single exchange.
    
    Triangular arb: A -> B -> C -> A where you end with more A than you started.
    
    Example:
    - Start with 1 BTC
    - Buy ETH with BTC (BTC/ETH pair)
    - Buy USDT with ETH (ETH/USDT pair)
    - Buy BTC with USDT (BTC/USDT pair)
    - End with > 1 BTC
    """
    
    def __init__(
        self,
        exchange: Exchange,
        config: Optional[TriangularConfig] = None,
    ):
        self.exchange = exchange
        self.config = config or TriangularConfig()
        
        # Available pairs on exchange
        self._pairs: Dict[str, ExchangePrice] = {}
        
        # Pre-computed triangles
        self._triangles: List[CurrencyTriangle] = []
        
        # Active opportunities
        self._opportunities: Dict[str, TriangularOpportunity] = {}
        self._opp_counter = 0
        
    def set_available_pairs(self, pairs: List[str]):
        """Set available trading pairs and compute triangles."""
        # Parse pairs into base/quote
        pair_map: Dict[str, Tuple[str, str]] = {}
        currencies: Set[str] = set()
        
        for pair in pairs:
            base, quote = self._parse_pair(pair)
            pair_map[pair] = (base, quote)
            currencies.add(base)
            currencies.add(quote)
            
        # Filter to base currencies
        currencies = currencies.intersection(self.config.base_currencies)
        
        # Find all valid triangles
        self._triangles = self._compute_triangles(currencies, pair_map)
        logger.info(f"Found {len(self._triangles)} possible triangles on {self.exchange.value}")
    
    def _parse_pair(self, pair: str) -> Tuple[str, str]:
        """Parse trading pair into base and quote."""
        if "/" in pair:
            parts = pair.split("/")
            return parts[0], parts[1]
        elif "-" in pair:
            parts = pair.split("-")
            return parts[0], parts[1]
        else:
            # Try common patterns
            for quote in ["USDT", "USDC", "USD", "BTC", "ETH", "BNB"]:
                if pair.endswith(quote):
                    return pair[:-len(quote)], quote
            return pair[:3], pair[3:]
    
    def _compute_triangles(
        self,
        currencies: Set[str],
        pair_map: Dict[str, Tuple[str, str]],
    ) -> List[CurrencyTriangle]:
        """Compute all valid triangular paths."""
        triangles = []
        
        # Build adjacency map
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        pair_lookup: Dict[Tuple[str, str], str] = {}
        
        for pair, (base, quote) in pair_map.items():
            adjacency[base].add(quote)
            adjacency[quote].add(base)
            pair_lookup[(base, quote)] = pair
            pair_lookup[(quote, base)] = pair
            
        # Find triangles: A -> B -> C -> A
        for a in currencies:
            for b in adjacency[a]:
                if b == a:
                    continue
                for c in adjacency[b]:
                    if c == a or c == b:
                        continue
                    if a in adjacency[c]:
                        # Found triangle A -> B -> C -> A
                        triangle = self._build_triangle(a, b, c, pair_lookup)
                        if triangle:
                            triangles.append(triangle)
                            
        # Deduplicate (A->B->C is same as B->C->A is same as C->A->B)
        unique = {}
        for t in triangles:
            key = tuple(sorted([t.base, t.intermediate, t.quote]))
            if key not in unique:
                unique[key] = t
                
        return list(unique.values())[:self.config.max_triangles]
    
    def _build_triangle(
        self,
        a: str,
        b: str,
        c: str,
        pair_lookup: Dict[Tuple[str, str], str],
    ) -> Optional[CurrencyTriangle]:
        """Build triangle with correct pair directions."""
        # Leg 1: A -> B
        if (a, b) in pair_lookup:
            pair1 = pair_lookup[(a, b)]
            pair1_side = "sell"  # Selling A for B
        elif (b, a) in pair_lookup:
            pair1 = pair_lookup[(b, a)]
            pair1_side = "buy"  # Buying B with A
        else:
            return None
            
        # Leg 2: B -> C
        if (b, c) in pair_lookup:
            pair2 = pair_lookup[(b, c)]
            pair2_side = "sell"
        elif (c, b) in pair_lookup:
            pair2 = pair_lookup[(c, b)]
            pair2_side = "buy"
        else:
            return None
            
        # Leg 3: C -> A
        if (c, a) in pair_lookup:
            pair3 = pair_lookup[(c, a)]
            pair3_side = "sell"
        elif (a, c) in pair_lookup:
            pair3 = pair_lookup[(a, c)]
            pair3_side = "buy"
        else:
            return None
            
        return CurrencyTriangle(
            base=a,
            intermediate=b,
            quote=c,
            pair1=pair1,
            pair2=pair2,
            pair3=pair3,
            pair1_side=pair1_side,
            pair2_side=pair2_side,
            pair3_side=pair3_side,
        )
    
    def update_price(self, price: ExchangePrice):
        """Update price for a pair."""
        self._pairs[price.symbol] = price
    
    def scan(self) -> List[TriangularOpportunity]:
        """Scan all triangles for opportunities."""
        opportunities = []
        
        for triangle in self._triangles:
            opp = self._check_triangle(triangle)
            if opp and opp.is_valid:
                opportunities.append(opp)
                self._opportunities[opp.id] = opp
                
        self._cleanup_expired()
        return opportunities
    
    def _check_triangle(
        self,
        triangle: CurrencyTriangle,
    ) -> Optional[TriangularOpportunity]:
        """Check if triangle has profitable opportunity."""
        # Get prices for all legs
        price1 = self._pairs.get(triangle.pair1)
        price2 = self._pairs.get(triangle.pair2)
        price3 = self._pairs.get(triangle.pair3)
        
        if not all([price1, price2, price3]):
            return None
            
        # Check staleness
        if any(p.is_stale for p in [price1, price2, price3]):
            return None
            
        # Simulate trade starting with 1 unit
        start_amount = 1.0
        
        # Leg 1
        if triangle.pair1_side == "buy":
            # Buying base with quote
            leg1_price = price1.ask
            leg1_result = start_amount / leg1_price  # units of base
        else:
            # Selling base for quote
            leg1_price = price1.bid
            leg1_result = start_amount * leg1_price
            
        # Leg 2
        if triangle.pair2_side == "buy":
            leg2_price = price2.ask
            leg2_result = leg1_result / leg2_price
        else:
            leg2_price = price2.bid
            leg2_result = leg1_result * leg2_price
            
        # Leg 3
        if triangle.pair3_side == "buy":
            leg3_price = price3.ask
            leg3_result = leg2_result / leg3_price
        else:
            leg3_price = price3.bid
            leg3_result = leg2_result * leg3_price
            
        # Calculate profit
        end_amount = leg3_result
        profit_pct = (end_amount - start_amount) / start_amount * 100
        
        if profit_pct < self.config.min_profit_pct:
            return None
            
        # Estimate fees (3 legs)
        total_fee_pct = self.config.taker_fee * 3 * 100
        net_profit_pct = profit_pct - total_fee_pct
        
        if net_profit_pct < self.config.min_net_profit_pct:
            return None
            
        # Calculate max size (limited by liquidity)
        max_size = self._calculate_max_size(
            price1, price2, price3,
            triangle.pair1_side, triangle.pair2_side, triangle.pair3_side,
        )
        
        if max_size < self.config.min_size_usd:
            return None
            
        self._opp_counter += 1
        
        return TriangularOpportunity(
            id=f"TRI-{self._opp_counter:08d}",
            exchange=self.exchange,
            triangle=triangle,
            detected_at=datetime.now(),
            leg1_pair=triangle.pair1,
            leg1_side=triangle.pair1_side,
            leg1_price=leg1_price,
            leg1_size=start_amount,
            leg2_pair=triangle.pair2,
            leg2_side=triangle.pair2_side,
            leg2_price=leg2_price,
            leg2_size=leg1_result,
            leg3_pair=triangle.pair3,
            leg3_side=triangle.pair3_side,
            leg3_price=leg3_price,
            leg3_size=leg2_result,
            start_amount=start_amount,
            end_amount=end_amount,
            profit_pct=profit_pct,
            profit_amount=(end_amount - start_amount) * max_size,
            net_profit_pct=net_profit_pct,
            net_profit_amount=(net_profit_pct / 100) * max_size,
            max_size=max_size,
            estimated_fees=total_fee_pct / 100 * max_size,
            confidence=min(1.0, net_profit_pct / 0.5),
            expires_at=datetime.now() + timedelta(seconds=self.config.opportunity_ttl_seconds),
        )
    
    def _calculate_max_size(
        self,
        price1: ExchangePrice,
        price2: ExchangePrice,
        price3: ExchangePrice,
        side1: str,
        side2: str,
        side3: str,
    ) -> float:
        """Calculate maximum executable size in USD."""
        # Get available liquidity on each leg
        if side1 == "buy":
            size1 = price1.ask_size * price1.ask
        else:
            size1 = price1.bid_size * price1.bid
            
        if side2 == "buy":
            size2 = price2.ask_size * price2.ask
        else:
            size2 = price2.bid_size * price2.bid
            
        if side3 == "buy":
            size3 = price3.ask_size * price3.ask
        else:
            size3 = price3.bid_size * price3.bid
            
        # Max is minimum across all legs
        max_size = min(size1, size2, size3, self.config.max_size_usd)
        return max_size
    
    def _cleanup_expired(self):
        """Remove expired opportunities."""
        now = datetime.now()
        expired = [
            opp_id for opp_id, opp in self._opportunities.items()
            if opp.expires_at and now > opp.expires_at
        ]
        for opp_id in expired:
            del self._opportunities[opp_id]
    
    def get_opportunities(
        self,
        min_profit_pct: float = 0.0,
    ) -> List[TriangularOpportunity]:
        """Get active opportunities."""
        opps = [
            opp for opp in self._opportunities.values()
            if opp.is_valid and opp.net_profit_pct >= min_profit_pct
        ]
        opps.sort(key=lambda x: x.net_profit_pct, reverse=True)
        return opps
    
    def get_triangle_info(self) -> List[Dict[str, Any]]:
        """Get info about tracked triangles."""
        return [
            {
                "path": f"{t.base}->{t.intermediate}->{t.quote}",
                "pairs": [t.pair1, t.pair2, t.pair3],
            }
            for t in self._triangles
        ]


class MultiExchangeTriangularScanner:
    """
    Scans multiple exchanges for triangular arbitrage.
    """
    
    def __init__(self, config: Optional[TriangularConfig] = None):
        self.config = config or TriangularConfig()
        self._detectors: Dict[Exchange, TriangularArbDetector] = {}
        
    def add_exchange(
        self,
        exchange: Exchange,
        pairs: List[str],
    ):
        """Add exchange with available pairs."""
        detector = TriangularArbDetector(exchange, self.config)
        detector.set_available_pairs(pairs)
        self._detectors[exchange] = detector
        
    def update_price(self, price: ExchangePrice):
        """Update price for exchange."""
        if price.exchange in self._detectors:
            self._detectors[price.exchange].update_price(price)
    
    def scan_all(self) -> Dict[Exchange, List[TriangularOpportunity]]:
        """Scan all exchanges for opportunities."""
        results = {}
        for exchange, detector in self._detectors.items():
            opps = detector.scan()
            if opps:
                results[exchange] = opps
        return results
    
    def get_best_opportunities(
        self,
        limit: int = 10,
    ) -> List[TriangularOpportunity]:
        """Get best opportunities across all exchanges."""
        all_opps = []
        for detector in self._detectors.values():
            all_opps.extend(detector.get_opportunities())
            
        all_opps.sort(key=lambda x: x.net_profit_pct, reverse=True)
        return all_opps[:limit]
