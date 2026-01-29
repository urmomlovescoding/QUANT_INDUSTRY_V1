"""
Arbitrage Opportunity Detection
===============================
Detects and evaluates cross-exchange arbitrage opportunities.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable, Tuple
from enum import Enum
import logging
from collections import defaultdict
import statistics

from .price_feeds import (
    Exchange, ExchangePrice, AggregatedBook, MultiExchangeFeed, AssetType
)

logger = logging.getLogger(__name__)


class ArbType(Enum):
    """Types of arbitrage opportunities."""
    SPATIAL = "spatial"  # Same asset, different exchanges
    TRIANGULAR = "triangular"  # A->B->C->A
    STATISTICAL = "statistical"  # Mean reversion based
    FUTURES_SPOT = "futures_spot"  # Basis arbitrage
    FUNDING_RATE = "funding_rate"  # Perpetual funding
    CEX_DEX = "cex_dex"  # Centralized vs decentralized


class ArbStatus(Enum):
    """Status of arbitrage opportunity."""
    DETECTED = "detected"
    VALIDATED = "validated"
    EXECUTING = "executing"
    EXECUTED = "executed"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class ArbOpportunity:
    """Detected arbitrage opportunity."""
    id: str
    arb_type: ArbType
    symbol: str
    detected_at: datetime
    
    # Buy side
    buy_exchange: Exchange
    buy_price: float
    buy_size: float
    
    # Sell side
    sell_exchange: Exchange
    sell_price: float
    sell_size: float
    
    # Profit metrics
    gross_profit_pct: float  # Before costs
    net_profit_pct: float  # After estimated costs
    profit_usd: float
    
    # Size constraints
    max_size: float  # Maximum executable size
    
    # Costs
    estimated_fees: float = 0.0
    estimated_slippage: float = 0.0
    transfer_cost: float = 0.0
    
    # Timing
    expected_duration_seconds: float = 0.0
    expires_at: Optional[datetime] = None
    
    # Status
    status: ArbStatus = ArbStatus.DETECTED
    confidence: float = 0.0  # 0-1
    
    # Risk factors
    execution_risk: float = 0.0  # 0-1
    liquidity_risk: float = 0.0  # 0-1
    timing_risk: float = 0.0  # 0-1
    
    @property
    def spread_bps(self) -> float:
        """Spread in basis points."""
        mid = (self.buy_price + self.sell_price) / 2
        return (self.sell_price - self.buy_price) / mid * 10000 if mid > 0 else 0
    
    @property
    def is_valid(self) -> bool:
        """Check if opportunity is still valid."""
        if self.status in (ArbStatus.EXPIRED, ArbStatus.FAILED, ArbStatus.EXECUTED):
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return self.net_profit_pct > 0
    
    @property
    def risk_adjusted_profit(self) -> float:
        """Profit adjusted for risk."""
        risk_factor = 1 - (self.execution_risk + self.liquidity_risk + self.timing_risk) / 3
        return self.net_profit_pct * risk_factor
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "arb_type": self.arb_type.value,
            "symbol": self.symbol,
            "detected_at": self.detected_at.isoformat(),
            "buy_exchange": self.buy_exchange.value,
            "buy_price": self.buy_price,
            "sell_exchange": self.sell_exchange.value,
            "sell_price": self.sell_price,
            "spread_bps": self.spread_bps,
            "gross_profit_pct": self.gross_profit_pct,
            "net_profit_pct": self.net_profit_pct,
            "profit_usd": self.profit_usd,
            "max_size": self.max_size,
            "confidence": self.confidence,
            "status": self.status.value,
            "risk_adjusted_profit": self.risk_adjusted_profit,
        }


@dataclass
class ArbConfig:
    """Configuration for arbitrage detection."""
    # Profit thresholds
    min_gross_profit_pct: float = 0.1  # 0.1%
    min_net_profit_pct: float = 0.05  # 0.05%
    min_profit_usd: float = 10.0
    
    # Size constraints
    min_size_usd: float = 100.0
    max_size_usd: float = 100_000.0
    
    # Fee estimates (per side)
    default_maker_fee: float = 0.001  # 0.1%
    default_taker_fee: float = 0.001  # 0.1%
    
    # Exchange-specific fees
    exchange_fees: Dict[Exchange, Dict[str, float]] = field(default_factory=dict)
    
    # Slippage estimates
    default_slippage_bps: float = 5.0
    
    # Transfer costs
    transfer_costs: Dict[str, float] = field(default_factory=dict)
    
    # Timing
    opportunity_ttl_seconds: float = 5.0
    cooldown_seconds: float = 1.0
    
    # Risk thresholds
    max_execution_risk: float = 0.5
    max_liquidity_risk: float = 0.5


class ArbDetector:
    """
    Detects arbitrage opportunities across exchanges.
    
    Monitors price feeds and identifies:
    - Spatial arbitrage (buy low, sell high across exchanges)
    - Price discrepancies accounting for fees and slippage
    - Size-constrained opportunities
    """
    
    def __init__(
        self,
        feed: MultiExchangeFeed,
        config: Optional[ArbConfig] = None,
    ):
        self.feed = feed
        self.config = config or ArbConfig()
        
        self._opportunities: Dict[str, ArbOpportunity] = {}
        self._opportunity_history: List[ArbOpportunity] = []
        self._callbacks: List[Callable[[ArbOpportunity], None]] = []
        self._opp_counter = 0
        self._last_detection: Dict[str, datetime] = {}
        
        # Register for feed updates
        self.feed.register_callback(self._on_book_update)
        
    def register_callback(self, callback: Callable[[ArbOpportunity], None]):
        """Register callback for new opportunities."""
        self._callbacks.append(callback)
        
    def _notify(self, opportunity: ArbOpportunity):
        """Notify callbacks of opportunity."""
        for cb in self._callbacks:
            try:
                cb(opportunity)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _on_book_update(self, book: AggregatedBook):
        """Handle aggregated book update."""
        # Check cooldown
        symbol = book.symbol
        if symbol in self._last_detection:
            elapsed = (datetime.now() - self._last_detection[symbol]).total_seconds()
            if elapsed < self.config.cooldown_seconds:
                return
                
        # Detect opportunities
        opps = self._detect_spatial_arb(book)
        
        for opp in opps:
            if opp.is_valid:
                self._opportunities[opp.id] = opp
                self._notify(opp)
                
        self._last_detection[symbol] = datetime.now()
        self._cleanup_expired()
    
    def _detect_spatial_arb(self, book: AggregatedBook) -> List[ArbOpportunity]:
        """Detect spatial arbitrage opportunities."""
        opportunities = []
        
        if not book.has_cross:
            return opportunities
            
        # Get all exchange pairs
        exchanges = list(book.prices.keys())
        
        for buy_exchange in exchanges:
            buy_price = book.prices[buy_exchange]
            if buy_price.is_stale:
                continue
                
            for sell_exchange in exchanges:
                if buy_exchange == sell_exchange:
                    continue
                    
                sell_price = book.prices[sell_exchange]
                if sell_price.is_stale:
                    continue
                    
                # Check if profitable: buy at ask, sell at bid
                buy_at = buy_price.ask
                sell_at = sell_price.bid
                
                if sell_at <= buy_at:
                    continue  # No opportunity
                    
                # Calculate gross profit
                gross_profit_pct = (sell_at - buy_at) / buy_at * 100
                
                if gross_profit_pct < self.config.min_gross_profit_pct:
                    continue
                    
                # Calculate max size (limited by liquidity on both sides)
                max_size = min(
                    buy_price.ask_size,
                    sell_price.bid_size,
                )
                
                # Check depth for larger sizes
                size_value = max_size * buy_at
                if size_value < self.config.min_size_usd:
                    continue
                    
                max_size = min(max_size, self.config.max_size_usd / buy_at)
                
                # Calculate costs
                fees = self._calculate_fees(
                    buy_exchange, sell_exchange, max_size * buy_at
                )
                slippage = self._estimate_slippage(
                    buy_price, sell_price, max_size
                )
                transfer_cost = self._get_transfer_cost(book.symbol)
                
                total_cost_pct = (fees + slippage + transfer_cost) / (max_size * buy_at) * 100
                net_profit_pct = gross_profit_pct - total_cost_pct
                
                if net_profit_pct < self.config.min_net_profit_pct:
                    continue
                    
                profit_usd = (net_profit_pct / 100) * max_size * buy_at
                
                if profit_usd < self.config.min_profit_usd:
                    continue
                    
                # Calculate risks
                execution_risk = self._calculate_execution_risk(buy_price, sell_price)
                liquidity_risk = self._calculate_liquidity_risk(buy_price, sell_price, max_size)
                timing_risk = self._calculate_timing_risk(buy_price, sell_price)
                
                # Create opportunity
                self._opp_counter += 1
                opp = ArbOpportunity(
                    id=f"ARB-{self._opp_counter:08d}",
                    arb_type=ArbType.SPATIAL,
                    symbol=book.symbol,
                    detected_at=datetime.now(),
                    buy_exchange=buy_exchange,
                    buy_price=buy_at,
                    buy_size=max_size,
                    sell_exchange=sell_exchange,
                    sell_price=sell_at,
                    sell_size=max_size,
                    gross_profit_pct=gross_profit_pct,
                    net_profit_pct=net_profit_pct,
                    profit_usd=profit_usd,
                    max_size=max_size,
                    estimated_fees=fees,
                    estimated_slippage=slippage,
                    transfer_cost=transfer_cost,
                    expires_at=datetime.now() + timedelta(seconds=self.config.opportunity_ttl_seconds),
                    confidence=self._calculate_confidence(net_profit_pct, execution_risk),
                    execution_risk=execution_risk,
                    liquidity_risk=liquidity_risk,
                    timing_risk=timing_risk,
                )
                
                opportunities.append(opp)
                
        return opportunities
    
    def _calculate_fees(
        self,
        buy_exchange: Exchange,
        sell_exchange: Exchange,
        value: float,
    ) -> float:
        """Calculate trading fees for both legs."""
        buy_fee = self.config.exchange_fees.get(
            buy_exchange, {}
        ).get("taker", self.config.default_taker_fee)
        
        sell_fee = self.config.exchange_fees.get(
            sell_exchange, {}
        ).get("taker", self.config.default_taker_fee)
        
        return value * (buy_fee + sell_fee)
    
    def _estimate_slippage(
        self,
        buy_price: ExchangePrice,
        sell_price: ExchangePrice,
        size: float,
    ) -> float:
        """Estimate slippage for given size."""
        # Use depth if available
        if buy_price.asks and sell_price.bids:
            buy_slippage = buy_price.depth_at_size(size, "ask") - buy_price.ask
            sell_slippage = sell_price.bid - sell_price.depth_at_size(size, "bid")
            return (buy_slippage + sell_slippage) * size
            
        # Default estimate
        mid = (buy_price.mid + sell_price.mid) / 2
        return mid * size * self.config.default_slippage_bps / 10000
    
    def _get_transfer_cost(self, symbol: str) -> float:
        """Get transfer cost for asset."""
        # Extract base asset
        base = symbol.split("/")[0] if "/" in symbol else symbol[:3]
        return self.config.transfer_costs.get(base, 0.0)
    
    def _calculate_execution_risk(
        self,
        buy_price: ExchangePrice,
        sell_price: ExchangePrice,
    ) -> float:
        """Calculate execution risk (0-1)."""
        risk = 0.0
        
        # Latency risk
        max_latency = max(buy_price.latency_ms, sell_price.latency_ms)
        if max_latency > 100:
            risk += 0.3
        elif max_latency > 50:
            risk += 0.15
            
        # Spread risk
        avg_spread = (buy_price.spread_bps + sell_price.spread_bps) / 2
        if avg_spread > 20:
            risk += 0.3
        elif avg_spread > 10:
            risk += 0.15
            
        return min(1.0, risk)
    
    def _calculate_liquidity_risk(
        self,
        buy_price: ExchangePrice,
        sell_price: ExchangePrice,
        size: float,
    ) -> float:
        """Calculate liquidity risk (0-1)."""
        risk = 0.0
        
        # Size vs available liquidity
        buy_fill_ratio = size / buy_price.ask_size if buy_price.ask_size > 0 else 1.0
        sell_fill_ratio = size / sell_price.bid_size if sell_price.bid_size > 0 else 1.0
        
        max_ratio = max(buy_fill_ratio, sell_fill_ratio)
        
        if max_ratio > 1.0:
            risk += 0.5
        elif max_ratio > 0.5:
            risk += 0.25
        elif max_ratio > 0.25:
            risk += 0.1
            
        return min(1.0, risk)
    
    def _calculate_timing_risk(
        self,
        buy_price: ExchangePrice,
        sell_price: ExchangePrice,
    ) -> float:
        """Calculate timing/staleness risk (0-1)."""
        max_age = max(
            (datetime.now() - buy_price.timestamp).total_seconds(),
            (datetime.now() - sell_price.timestamp).total_seconds(),
        )
        
        if max_age > 2.0:
            return 0.5
        elif max_age > 1.0:
            return 0.3
        elif max_age > 0.5:
            return 0.15
            
        return 0.0
    
    def _calculate_confidence(
        self,
        net_profit_pct: float,
        execution_risk: float,
    ) -> float:
        """Calculate confidence score (0-1)."""
        # Higher profit = higher confidence
        profit_score = min(1.0, net_profit_pct / 0.5)  # Max at 0.5%
        
        # Lower risk = higher confidence
        risk_score = 1 - execution_risk
        
        return (profit_score * 0.6 + risk_score * 0.4)
    
    def _cleanup_expired(self):
        """Remove expired opportunities."""
        now = datetime.now()
        expired = []
        
        for opp_id, opp in self._opportunities.items():
            if opp.expires_at and now > opp.expires_at:
                opp.status = ArbStatus.EXPIRED
                self._opportunity_history.append(opp)
                expired.append(opp_id)
                
        for opp_id in expired:
            del self._opportunities[opp_id]
            
        # Trim history
        if len(self._opportunity_history) > 10000:
            self._opportunity_history = self._opportunity_history[-5000:]
    
    def get_active_opportunities(
        self,
        min_profit_pct: float = 0.0,
        min_confidence: float = 0.0,
    ) -> List[ArbOpportunity]:
        """Get active opportunities with filters."""
        opps = [
            opp for opp in self._opportunities.values()
            if opp.is_valid
            and opp.net_profit_pct >= min_profit_pct
            and opp.confidence >= min_confidence
        ]
        
        # Sort by risk-adjusted profit
        opps.sort(key=lambda x: x.risk_adjusted_profit, reverse=True)
        return opps
    
    def get_opportunity(self, opp_id: str) -> Optional[ArbOpportunity]:
        """Get specific opportunity by ID."""
        return self._opportunities.get(opp_id)
    
    def mark_executed(self, opp_id: str):
        """Mark opportunity as executed."""
        if opp_id in self._opportunities:
            self._opportunities[opp_id].status = ArbStatus.EXECUTED
            self._opportunity_history.append(self._opportunities[opp_id])
            del self._opportunities[opp_id]
    
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get detection statistics."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [
            opp for opp in self._opportunity_history
            if opp.detected_at > cutoff
        ]
        
        if not recent:
            return {"period_hours": hours, "opportunities": 0}
            
        executed = [opp for opp in recent if opp.status == ArbStatus.EXECUTED]
        
        return {
            "period_hours": hours,
            "opportunities": len(recent),
            "executed": len(executed),
            "avg_profit_pct": statistics.mean(opp.net_profit_pct for opp in recent),
            "max_profit_pct": max(opp.net_profit_pct for opp in recent),
            "total_profit_usd": sum(opp.profit_usd for opp in executed),
            "avg_confidence": statistics.mean(opp.confidence for opp in recent),
            "by_symbol": self._group_by_symbol(recent),
        }
    
    def _group_by_symbol(
        self,
        opportunities: List[ArbOpportunity],
    ) -> Dict[str, int]:
        """Group opportunities by symbol."""
        counts = defaultdict(int)
        for opp in opportunities:
            counts[opp.symbol] += 1
        return dict(counts)
