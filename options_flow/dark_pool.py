"""
Dark Pool & Block Trade Monitor
===============================
Tracks large block trades and dark pool prints for institutional flow analysis.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
import logging
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


class PrintType(Enum):
    """Classification of dark pool prints."""
    DARK_POOL = "dark_pool"
    BLOCK_TRADE = "block_trade"
    CROSS = "cross"
    SWEEP = "sweep"
    INTERMARKET_SWEEP = "intermarket_sweep"


class PrintSentiment(Enum):
    """Inferred sentiment from print characteristics."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class BlockTrade:
    """Represents a block or dark pool trade."""
    symbol: str
    timestamp: datetime
    price: float
    size: int
    value: float  # price * size
    print_type: PrintType
    exchange: str
    condition_codes: List[str] = field(default_factory=list)
    
    # Price context
    vwap: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    high_of_day: float = 0.0
    low_of_day: float = 0.0
    
    # Volume context  
    avg_daily_volume: int = 0
    volume_at_time: int = 0
    
    # Derived metrics
    premium_to_vwap: float = 0.0
    pct_of_adv: float = 0.0
    
    def __post_init__(self):
        """Calculate derived metrics."""
        if self.vwap > 0:
            self.premium_to_vwap = (self.price - self.vwap) / self.vwap
        if self.avg_daily_volume > 0:
            self.pct_of_adv = self.size / self.avg_daily_volume
    
    @property
    def is_above_vwap(self) -> bool:
        return self.price > self.vwap if self.vwap > 0 else False
    
    @property
    def is_at_ask(self) -> bool:
        return self.price >= self.ask if self.ask > 0 else False
    
    @property
    def is_at_bid(self) -> bool:
        return self.price <= self.bid if self.bid > 0 else False
    
    @property
    def is_dark_pool(self) -> bool:
        return self.print_type == PrintType.DARK_POOL
    
    @property
    def sentiment(self) -> PrintSentiment:
        """Infer sentiment from trade characteristics."""
        signals = []
        
        # Price location
        if self.is_at_ask:
            signals.append(1)
        elif self.is_at_bid:
            signals.append(-1)
        else:
            signals.append(0)
            
        # VWAP premium
        if self.premium_to_vwap > 0.002:  # >0.2% above VWAP
            signals.append(1)
        elif self.premium_to_vwap < -0.002:
            signals.append(-1)
        else:
            signals.append(0)
            
        score = sum(signals)
        if score > 0:
            return PrintSentiment.BULLISH
        elif score < 0:
            return PrintSentiment.BEARISH
        return PrintSentiment.NEUTRAL
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "size": self.size,
            "value": self.value,
            "print_type": self.print_type.value,
            "exchange": self.exchange,
            "sentiment": self.sentiment.value,
            "premium_to_vwap": self.premium_to_vwap,
            "pct_of_adv": self.pct_of_adv,
        }


@dataclass
class DarkPoolLevel:
    """Aggregated dark pool activity at a price level."""
    symbol: str
    price: float
    total_volume: int = 0
    total_value: float = 0.0
    num_prints: int = 0
    bullish_volume: int = 0
    bearish_volume: int = 0
    neutral_volume: int = 0
    first_print: datetime = None
    last_print: datetime = None
    
    @property
    def net_sentiment_volume(self) -> int:
        return self.bullish_volume - self.bearish_volume
    
    @property
    def avg_size(self) -> float:
        return self.total_volume / self.num_prints if self.num_prints > 0 else 0


@dataclass
class DarkPoolConfig:
    """Configuration for dark pool monitoring."""
    # Size thresholds
    min_block_size: int = 10_000  # Minimum shares for block
    min_block_value: float = 100_000  # Minimum $ value
    whale_threshold: float = 1_000_000  # $1M+
    
    # Aggregation
    price_level_tolerance: float = 0.001  # 0.1% for level grouping
    aggregation_window_minutes: int = 60
    
    # Alert thresholds
    unusual_adv_pct: float = 0.01  # 1% of ADV in single print
    premium_alert_threshold: float = 0.005  # 0.5% premium to VWAP
    
    # Pattern detection
    accumulation_min_prints: int = 5
    accumulation_time_window_hours: int = 4


class DarkPoolMonitor:
    """
    Monitors dark pool and block trade activity.
    
    Features:
    - Block trade detection and classification
    - Dark pool print aggregation by price level
    - Institutional accumulation/distribution patterns
    - VWAP premium analysis
    - Volume-weighted sentiment tracking
    """
    
    def __init__(self, config: Optional[DarkPoolConfig] = None):
        self.config = config or DarkPoolConfig()
        self._prints: Dict[str, List[BlockTrade]] = defaultdict(list)
        self._levels: Dict[str, Dict[float, DarkPoolLevel]] = defaultdict(dict)
        self._daily_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
    async def process_print(self, trade: BlockTrade) -> Optional[Dict[str, Any]]:
        """
        Process a dark pool or block print.
        
        Returns alert dict if significant, None otherwise.
        """
        # Filter by size
        if trade.size < self.config.min_block_size:
            return None
        if trade.value < self.config.min_block_value:
            return None
            
        # Store print
        self._prints[trade.symbol].append(trade)
        self._update_levels(trade)
        self._update_daily_stats(trade)
        self._cleanup()
        
        # Check for alerts
        alert = self._check_alerts(trade)
        return alert
    
    def _update_levels(self, trade: BlockTrade):
        """Update aggregated price levels."""
        symbol = trade.symbol
        
        # Find or create level (with tolerance)
        level_price = self._find_level_price(symbol, trade.price)
        
        if level_price not in self._levels[symbol]:
            self._levels[symbol][level_price] = DarkPoolLevel(
                symbol=symbol,
                price=level_price,
                first_print=trade.timestamp,
            )
            
        level = self._levels[symbol][level_price]
        level.total_volume += trade.size
        level.total_value += trade.value
        level.num_prints += 1
        level.last_print = trade.timestamp
        
        # Sentiment tracking
        if trade.sentiment == PrintSentiment.BULLISH:
            level.bullish_volume += trade.size
        elif trade.sentiment == PrintSentiment.BEARISH:
            level.bearish_volume += trade.size
        else:
            level.neutral_volume += trade.size
    
    def _find_level_price(self, symbol: str, price: float) -> float:
        """Find existing level within tolerance or return new price."""
        tolerance = price * self.config.price_level_tolerance
        
        for level_price in self._levels[symbol].keys():
            if abs(level_price - price) <= tolerance:
                return level_price
                
        return round(price, 2)
    
    def _update_daily_stats(self, trade: BlockTrade):
        """Update daily aggregated statistics."""
        symbol = trade.symbol
        today = trade.timestamp.date().isoformat()
        
        if today not in self._daily_stats[symbol]:
            self._daily_stats[symbol][today] = {
                "total_volume": 0,
                "total_value": 0.0,
                "num_prints": 0,
                "bullish_volume": 0,
                "bearish_volume": 0,
                "whale_prints": 0,
                "whale_volume": 0,
                "vwap_premium_sum": 0.0,
            }
            
        stats = self._daily_stats[symbol][today]
        stats["total_volume"] += trade.size
        stats["total_value"] += trade.value
        stats["num_prints"] += 1
        stats["vwap_premium_sum"] += trade.premium_to_vwap * trade.size
        
        if trade.sentiment == PrintSentiment.BULLISH:
            stats["bullish_volume"] += trade.size
        elif trade.sentiment == PrintSentiment.BEARISH:
            stats["bearish_volume"] += trade.size
            
        if trade.value >= self.config.whale_threshold:
            stats["whale_prints"] += 1
            stats["whale_volume"] += trade.size
    
    def _check_alerts(self, trade: BlockTrade) -> Optional[Dict[str, Any]]:
        """Check if trade warrants an alert."""
        alerts = []
        
        # Whale alert
        if trade.value >= self.config.whale_threshold:
            alerts.append({
                "type": "whale_print",
                "severity": "high",
                "message": f"🐋 WHALE PRINT: {trade.symbol} {trade.size:,} shares @ ${trade.price:.2f} "
                          f"(${trade.value/1e6:.2f}M) - {trade.sentiment.value.upper()}",
            })
            
        # Unusual ADV %
        if trade.pct_of_adv >= self.config.unusual_adv_pct:
            alerts.append({
                "type": "unusual_size",
                "severity": "medium",
                "message": f"📊 UNUSUAL SIZE: {trade.symbol} {trade.pct_of_adv*100:.1f}% of ADV "
                          f"({trade.size:,} shares)",
            })
            
        # Large VWAP premium
        if abs(trade.premium_to_vwap) >= self.config.premium_alert_threshold:
            direction = "above" if trade.premium_to_vwap > 0 else "below"
            alerts.append({
                "type": "vwap_premium",
                "severity": "medium", 
                "message": f"💰 VWAP PREMIUM: {trade.symbol} {abs(trade.premium_to_vwap)*100:.2f}% {direction} VWAP "
                          f"(${trade.price:.2f} vs ${trade.vwap:.2f})",
            })
            
        if not alerts:
            return None
            
        return {
            "trade": trade.to_dict(),
            "alerts": alerts,
            "timestamp": datetime.now().isoformat(),
        }
    
    def _cleanup(self):
        """Remove old data."""
        cutoff = datetime.now() - timedelta(hours=24)
        
        for symbol in list(self._prints.keys()):
            self._prints[symbol] = [
                p for p in self._prints[symbol] if p.timestamp > cutoff
            ]
            if not self._prints[symbol]:
                del self._prints[symbol]
    
    def get_significant_levels(
        self,
        symbol: str,
        min_volume: int = 0,
        min_prints: int = 2,
    ) -> List[DarkPoolLevel]:
        """
        Get significant dark pool price levels.
        
        These levels often act as support/resistance.
        """
        levels = list(self._levels.get(symbol, {}).values())
        
        # Filter
        filtered = [
            l for l in levels
            if l.total_volume >= min_volume and l.num_prints >= min_prints
        ]
        
        # Sort by volume
        return sorted(filtered, key=lambda l: l.total_volume, reverse=True)
    
    def get_accumulation_distribution(
        self,
        symbol: str,
        hours: int = 4,
    ) -> Dict[str, Any]:
        """
        Analyze accumulation vs distribution patterns.
        
        Returns:
            Dict with accumulation/distribution metrics
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        prints = [p for p in self._prints.get(symbol, []) if p.timestamp > cutoff]
        
        if not prints:
            return {"symbol": symbol, "prints": 0, "signal": "neutral"}
            
        bullish_vol = sum(p.size for p in prints if p.sentiment == PrintSentiment.BULLISH)
        bearish_vol = sum(p.size for p in prints if p.sentiment == PrintSentiment.BEARISH)
        total_vol = sum(p.size for p in prints)
        
        # Calculate weighted VWAP premium
        weighted_premium = sum(p.premium_to_vwap * p.size for p in prints) / total_vol if total_vol > 0 else 0
        
        # Accumulation: bullish > bearish AND buying above VWAP
        # Distribution: bearish > bullish AND selling below VWAP
        
        if bullish_vol > bearish_vol * 1.2 and weighted_premium > 0:
            signal = "accumulation"
            strength = (bullish_vol / max(1, bearish_vol) - 1) * 100
        elif bearish_vol > bullish_vol * 1.2 and weighted_premium < 0:
            signal = "distribution"
            strength = (bearish_vol / max(1, bullish_vol) - 1) * 100
        else:
            signal = "neutral"
            strength = 0
            
        return {
            "symbol": symbol,
            "prints": len(prints),
            "total_volume": total_vol,
            "total_value": sum(p.value for p in prints),
            "bullish_volume": bullish_vol,
            "bearish_volume": bearish_vol,
            "bullish_pct": bullish_vol / total_vol * 100 if total_vol > 0 else 0,
            "weighted_vwap_premium": weighted_premium,
            "signal": signal,
            "strength": strength,
            "hours": hours,
        }
    
    def get_daily_summary(self, symbol: str) -> Dict[str, Any]:
        """Get daily dark pool summary for symbol."""
        today = datetime.now().date().isoformat()
        stats = self._daily_stats.get(symbol, {}).get(today, {})
        
        if not stats:
            return {"symbol": symbol, "date": today, "prints": 0}
            
        total_vol = stats.get("total_volume", 0)
        
        return {
            "symbol": symbol,
            "date": today,
            "prints": stats.get("num_prints", 0),
            "total_volume": total_vol,
            "total_value": stats.get("total_value", 0),
            "bullish_volume": stats.get("bullish_volume", 0),
            "bearish_volume": stats.get("bearish_volume", 0),
            "bullish_pct": stats.get("bullish_volume", 0) / total_vol * 100 if total_vol > 0 else 0,
            "whale_prints": stats.get("whale_prints", 0),
            "whale_volume": stats.get("whale_volume", 0),
            "avg_vwap_premium": stats.get("vwap_premium_sum", 0) / total_vol if total_vol > 0 else 0,
        }
    
    def find_support_resistance(
        self,
        symbol: str,
        current_price: float,
        num_levels: int = 3,
    ) -> Tuple[List[DarkPoolLevel], List[DarkPoolLevel]]:
        """
        Find potential support and resistance from dark pool levels.
        
        Args:
            symbol: Stock symbol
            current_price: Current price
            num_levels: Number of levels to return each side
            
        Returns:
            Tuple of (support_levels, resistance_levels)
        """
        levels = self.get_significant_levels(symbol, min_prints=2)
        
        support = [l for l in levels if l.price < current_price]
        resistance = [l for l in levels if l.price > current_price]
        
        # Sort support descending (closest first), resistance ascending
        support.sort(key=lambda l: l.price, reverse=True)
        resistance.sort(key=lambda l: l.price)
        
        return support[:num_levels], resistance[:num_levels]


class BlockTradeScanner:
    """
    Scans for notable block trades across multiple symbols.
    """
    
    def __init__(self, monitor: Optional[DarkPoolMonitor] = None):
        self.monitor = monitor or DarkPoolMonitor()
        self._watchlist: set = set()
        
    def set_watchlist(self, symbols: List[str]):
        """Set symbols to monitor."""
        self._watchlist = set(s.upper() for s in symbols)
        
    async def scan_prints(
        self,
        prints: List[BlockTrade],
        min_value: float = 500_000,
    ) -> List[Dict[str, Any]]:
        """
        Scan prints for notable activity.
        
        Args:
            prints: List of block trades to analyze
            min_value: Minimum $ value to consider
            
        Returns:
            List of alerts
        """
        alerts = []
        
        # Sort by timestamp
        sorted_prints = sorted(prints, key=lambda p: p.timestamp)
        
        for trade in sorted_prints:
            if self._watchlist and trade.symbol not in self._watchlist:
                continue
                
            if trade.value < min_value:
                continue
                
            result = await self.monitor.process_print(trade)
            if result:
                alerts.append(result)
                
        return alerts
    
    def get_top_prints(
        self,
        symbol: Optional[str] = None,
        hours: int = 24,
        limit: int = 10,
    ) -> List[BlockTrade]:
        """Get top prints by value."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        if symbol:
            prints = self.monitor._prints.get(symbol, [])
        else:
            prints = [p for ps in self.monitor._prints.values() for p in ps]
            
        recent = [p for p in prints if p.timestamp > cutoff]
        return sorted(recent, key=lambda p: p.value, reverse=True)[:limit]
    
    def get_sector_flow(
        self,
        symbol_to_sector: Dict[str, str],
        hours: int = 4,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate dark pool flow by sector.
        
        Args:
            symbol_to_sector: Mapping of symbols to sector names
            hours: Lookback period
            
        Returns:
            Dict of sector -> flow metrics
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        sector_flow = defaultdict(lambda: {
            "bullish_value": 0.0,
            "bearish_value": 0.0,
            "neutral_value": 0.0,
            "num_prints": 0,
            "symbols": set(),
        })
        
        for symbol, prints in self.monitor._prints.items():
            sector = symbol_to_sector.get(symbol, "Unknown")
            
            for p in prints:
                if p.timestamp < cutoff:
                    continue
                    
                sector_flow[sector]["num_prints"] += 1
                sector_flow[sector]["symbols"].add(symbol)
                
                if p.sentiment == PrintSentiment.BULLISH:
                    sector_flow[sector]["bullish_value"] += p.value
                elif p.sentiment == PrintSentiment.BEARISH:
                    sector_flow[sector]["bearish_value"] += p.value
                else:
                    sector_flow[sector]["neutral_value"] += p.value
        
        # Convert sets to lists and add derived metrics
        result = {}
        for sector, data in sector_flow.items():
            total = data["bullish_value"] + data["bearish_value"] + data["neutral_value"]
            result[sector] = {
                **data,
                "symbols": list(data["symbols"]),
                "total_value": total,
                "bullish_pct": data["bullish_value"] / total * 100 if total > 0 else 0,
                "net_sentiment": "bullish" if data["bullish_value"] > data["bearish_value"] else "bearish",
            }
            
        return result
