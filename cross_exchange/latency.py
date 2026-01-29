"""
Latency Monitoring and Optimization
===================================
Tracks and analyzes latency across exchanges for optimal execution.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from collections import deque
import logging
import statistics

from .price_feeds import Exchange

logger = logging.getLogger(__name__)


class LatencyType(Enum):
    """Types of latency measurements."""
    FEED = "feed"  # Price feed latency
    ORDER = "order"  # Order submission latency
    FILL = "fill"  # Time to fill
    CANCEL = "cancel"  # Cancel latency
    ROUNDTRIP = "roundtrip"  # Full roundtrip


@dataclass
class LatencyMeasurement:
    """Single latency measurement."""
    exchange: Exchange
    latency_type: LatencyType
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExchangeLatency:
    """Latency statistics for an exchange."""
    exchange: Exchange
    
    # Feed latency
    feed_latency_p50: float = 0.0
    feed_latency_p95: float = 0.0
    feed_latency_p99: float = 0.0
    
    # Order latency
    order_latency_p50: float = 0.0
    order_latency_p95: float = 0.0
    order_latency_p99: float = 0.0
    
    # Fill latency
    fill_latency_p50: float = 0.0
    fill_latency_p95: float = 0.0
    fill_latency_p99: float = 0.0
    
    # Samples
    num_samples: int = 0
    measurement_period_hours: float = 0.0
    
    # Reliability
    uptime_pct: float = 100.0
    error_rate_pct: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange.value,
            "feed_latency_p50": self.feed_latency_p50,
            "feed_latency_p95": self.feed_latency_p95,
            "order_latency_p50": self.order_latency_p50,
            "order_latency_p95": self.order_latency_p95,
            "fill_latency_p50": self.fill_latency_p50,
            "fill_latency_p95": self.fill_latency_p95,
            "num_samples": self.num_samples,
            "uptime_pct": self.uptime_pct,
        }


@dataclass
class LatencyStats:
    """Aggregated latency statistics."""
    exchanges: Dict[Exchange, ExchangeLatency]
    
    # Cross-exchange
    fastest_exchange: Optional[Exchange] = None
    slowest_exchange: Optional[Exchange] = None
    avg_latency_diff_ms: float = 0.0
    
    # Arb impact
    latency_arb_risk_pct: float = 0.0  # % of opps lost to latency
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchanges": {e.value: s.to_dict() for e, s in self.exchanges.items()},
            "fastest_exchange": self.fastest_exchange.value if self.fastest_exchange else None,
            "slowest_exchange": self.slowest_exchange.value if self.slowest_exchange else None,
            "avg_latency_diff_ms": self.avg_latency_diff_ms,
            "latency_arb_risk_pct": self.latency_arb_risk_pct,
        }


@dataclass
class LatencyConfig:
    """Configuration for latency monitoring."""
    # History
    max_samples_per_exchange: int = 10000
    measurement_window_hours: float = 24.0
    
    # Alerting
    feed_latency_alert_ms: float = 100.0
    order_latency_alert_ms: float = 500.0
    
    # Percentiles to track
    percentiles: List[float] = field(default_factory=lambda: [50, 95, 99])


class LatencyMonitor:
    """
    Monitors and analyzes latency across exchanges.
    
    Tracks:
    - Feed latency (time from exchange to receipt)
    - Order submission latency
    - Fill times
    - Reliability metrics
    """
    
    def __init__(self, config: Optional[LatencyConfig] = None):
        self.config = config or LatencyConfig()
        
        # Measurements by exchange and type
        self._measurements: Dict[Exchange, Dict[LatencyType, deque]] = {}
        
        # Error tracking
        self._errors: Dict[Exchange, deque] = {}
        
        # Last seen timestamps
        self._last_seen: Dict[Exchange, datetime] = {}
        
    def _ensure_exchange(self, exchange: Exchange):
        """Initialize data structures for exchange."""
        if exchange not in self._measurements:
            self._measurements[exchange] = {
                lt: deque(maxlen=self.config.max_samples_per_exchange)
                for lt in LatencyType
            }
            self._errors[exchange] = deque(maxlen=1000)
            
    def record_feed_latency(
        self,
        exchange: Exchange,
        latency_ms: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record feed latency measurement."""
        self._ensure_exchange(exchange)
        
        measurement = LatencyMeasurement(
            exchange=exchange,
            latency_type=LatencyType.FEED,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )
        
        self._measurements[exchange][LatencyType.FEED].append(measurement)
        self._last_seen[exchange] = datetime.now()
        
        # Check alert threshold
        if latency_ms > self.config.feed_latency_alert_ms:
            logger.warning(f"High feed latency on {exchange.value}: {latency_ms:.1f}ms")
    
    def record_order_latency(
        self,
        exchange: Exchange,
        latency_ms: float,
        order_id: str = "",
    ):
        """Record order submission latency."""
        self._ensure_exchange(exchange)
        
        measurement = LatencyMeasurement(
            exchange=exchange,
            latency_type=LatencyType.ORDER,
            latency_ms=latency_ms,
            metadata={"order_id": order_id},
        )
        
        self._measurements[exchange][LatencyType.ORDER].append(measurement)
        
        if latency_ms > self.config.order_latency_alert_ms:
            logger.warning(f"High order latency on {exchange.value}: {latency_ms:.1f}ms")
    
    def record_fill_latency(
        self,
        exchange: Exchange,
        latency_ms: float,
        order_id: str = "",
    ):
        """Record fill latency (time from order to fill)."""
        self._ensure_exchange(exchange)
        
        measurement = LatencyMeasurement(
            exchange=exchange,
            latency_type=LatencyType.FILL,
            latency_ms=latency_ms,
            metadata={"order_id": order_id},
        )
        
        self._measurements[exchange][LatencyType.FILL].append(measurement)
    
    def record_error(self, exchange: Exchange, error: str):
        """Record an error for reliability tracking."""
        self._ensure_exchange(exchange)
        self._errors[exchange].append({
            "timestamp": datetime.now(),
            "error": error,
        })
    
    def get_exchange_latency(
        self,
        exchange: Exchange,
        hours: Optional[float] = None,
    ) -> ExchangeLatency:
        """Get latency statistics for exchange."""
        self._ensure_exchange(exchange)
        
        hours = hours or self.config.measurement_window_hours
        cutoff = datetime.now() - timedelta(hours=hours)
        
        def get_percentiles(measurements: deque) -> Dict[int, float]:
            recent = [
                m.latency_ms for m in measurements
                if m.timestamp > cutoff
            ]
            
            if not recent:
                return {p: 0.0 for p in self.config.percentiles}
                
            result = {}
            for p in self.config.percentiles:
                try:
                    result[p] = statistics.quantiles(recent, n=100)[int(p) - 1]
                except (statistics.StatisticsError, IndexError):
                    result[p] = recent[0] if recent else 0.0
            return result
        
        feed_pct = get_percentiles(self._measurements[exchange][LatencyType.FEED])
        order_pct = get_percentiles(self._measurements[exchange][LatencyType.ORDER])
        fill_pct = get_percentiles(self._measurements[exchange][LatencyType.FILL])
        
        # Count samples
        num_samples = sum(
            len([m for m in measurements if m.timestamp > cutoff])
            for measurements in self._measurements[exchange].values()
        )
        
        # Calculate error rate
        recent_errors = [
            e for e in self._errors[exchange]
            if e["timestamp"] > cutoff
        ]
        error_rate = len(recent_errors) / max(1, num_samples) * 100
        
        # Calculate uptime
        expected_updates = hours * 3600 / 0.1  # Assume 100ms update rate
        actual_updates = len([
            m for m in self._measurements[exchange][LatencyType.FEED]
            if m.timestamp > cutoff
        ])
        uptime = min(100, actual_updates / max(1, expected_updates) * 100)
        
        return ExchangeLatency(
            exchange=exchange,
            feed_latency_p50=feed_pct.get(50, 0),
            feed_latency_p95=feed_pct.get(95, 0),
            feed_latency_p99=feed_pct.get(99, 0),
            order_latency_p50=order_pct.get(50, 0),
            order_latency_p95=order_pct.get(95, 0),
            order_latency_p99=order_pct.get(99, 0),
            fill_latency_p50=fill_pct.get(50, 0),
            fill_latency_p95=fill_pct.get(95, 0),
            fill_latency_p99=fill_pct.get(99, 0),
            num_samples=num_samples,
            measurement_period_hours=hours,
            uptime_pct=uptime,
            error_rate_pct=error_rate,
        )
    
    def get_all_stats(self) -> LatencyStats:
        """Get statistics for all exchanges."""
        exchanges = {}
        
        for exchange in self._measurements.keys():
            exchanges[exchange] = self.get_exchange_latency(exchange)
            
        if not exchanges:
            return LatencyStats(exchanges={})
            
        # Find fastest/slowest
        feed_latencies = [
            (e, s.feed_latency_p50)
            for e, s in exchanges.items()
            if s.feed_latency_p50 > 0
        ]
        
        if feed_latencies:
            fastest = min(feed_latencies, key=lambda x: x[1])[0]
            slowest = max(feed_latencies, key=lambda x: x[1])[0]
            latencies = [l for _, l in feed_latencies]
            avg_diff = max(latencies) - min(latencies)
        else:
            fastest = slowest = None
            avg_diff = 0
            
        return LatencyStats(
            exchanges=exchanges,
            fastest_exchange=fastest,
            slowest_exchange=slowest,
            avg_latency_diff_ms=avg_diff,
        )
    
    def get_exchange_ranking(self) -> List[Tuple[Exchange, float]]:
        """Rank exchanges by combined latency score."""
        rankings = []
        
        for exchange in self._measurements.keys():
            stats = self.get_exchange_latency(exchange)
            
            # Combined score (lower is better)
            score = (
                stats.feed_latency_p50 * 0.4 +
                stats.order_latency_p50 * 0.3 +
                stats.fill_latency_p50 * 0.3
            )
            
            # Penalize errors
            score *= (1 + stats.error_rate_pct / 100)
            
            rankings.append((exchange, score))
            
        rankings.sort(key=lambda x: x[1])
        return rankings
    
    def estimate_arb_latency(
        self,
        buy_exchange: Exchange,
        sell_exchange: Exchange,
    ) -> Dict[str, float]:
        """Estimate total latency for arb between two exchanges."""
        buy_stats = self.get_exchange_latency(buy_exchange)
        sell_stats = self.get_exchange_latency(sell_exchange)
        
        # P50 estimate (optimistic)
        p50_estimate = (
            buy_stats.order_latency_p50 +
            sell_stats.order_latency_p50 +
            max(buy_stats.fill_latency_p50, sell_stats.fill_latency_p50)
        )
        
        # P95 estimate (realistic)
        p95_estimate = (
            buy_stats.order_latency_p95 +
            sell_stats.order_latency_p95 +
            max(buy_stats.fill_latency_p95, sell_stats.fill_latency_p95)
        )
        
        # P99 estimate (worst case)
        p99_estimate = (
            buy_stats.order_latency_p99 +
            sell_stats.order_latency_p99 +
            max(buy_stats.fill_latency_p99, sell_stats.fill_latency_p99)
        )
        
        return {
            "p50_ms": p50_estimate,
            "p95_ms": p95_estimate,
            "p99_ms": p99_estimate,
            "buy_exchange": buy_exchange.value,
            "sell_exchange": sell_exchange.value,
        }
    
    def get_latency_history(
        self,
        exchange: Exchange,
        latency_type: LatencyType,
        hours: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """Get latency history for charting."""
        self._ensure_exchange(exchange)
        
        cutoff = datetime.now() - timedelta(hours=hours)
        measurements = self._measurements[exchange][latency_type]
        
        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "latency_ms": m.latency_ms,
            }
            for m in measurements
            if m.timestamp > cutoff
        ]


class LatencyOptimizer:
    """
    Provides recommendations for optimizing execution latency.
    """
    
    def __init__(self, monitor: LatencyMonitor):
        self.monitor = monitor
        
    def get_optimal_route(
        self,
        symbol: str,
        buy_exchanges: List[Exchange],
        sell_exchanges: List[Exchange],
    ) -> Dict[str, Any]:
        """Find optimal exchange pair for arb execution."""
        best_route = None
        best_score = float('inf')
        
        for buy_ex in buy_exchanges:
            for sell_ex in sell_exchanges:
                if buy_ex == sell_ex:
                    continue
                    
                latency = self.monitor.estimate_arb_latency(buy_ex, sell_ex)
                score = latency["p95_ms"]
                
                if score < best_score:
                    best_score = score
                    best_route = {
                        "buy_exchange": buy_ex,
                        "sell_exchange": sell_ex,
                        "estimated_latency": latency,
                    }
                    
        return best_route or {}
    
    def get_recommendations(self) -> List[Dict[str, str]]:
        """Get latency optimization recommendations."""
        recommendations = []
        stats = self.monitor.get_all_stats()
        
        for exchange, latency in stats.exchanges.items():
            # High feed latency
            if latency.feed_latency_p50 > 50:
                recommendations.append({
                    "exchange": exchange.value,
                    "type": "feed_latency",
                    "severity": "warning" if latency.feed_latency_p50 < 100 else "critical",
                    "message": f"High feed latency ({latency.feed_latency_p50:.0f}ms p50). "
                              "Consider colocating or using faster connection.",
                })
                
            # High error rate
            if latency.error_rate_pct > 1:
                recommendations.append({
                    "exchange": exchange.value,
                    "type": "reliability",
                    "severity": "warning" if latency.error_rate_pct < 5 else "critical",
                    "message": f"High error rate ({latency.error_rate_pct:.1f}%). "
                              "Check API connectivity and rate limits.",
                })
                
            # Low uptime
            if latency.uptime_pct < 99:
                recommendations.append({
                    "exchange": exchange.value,
                    "type": "uptime",
                    "severity": "info",
                    "message": f"Suboptimal uptime ({latency.uptime_pct:.1f}%). "
                              "May be missing market data.",
                })
                
        return recommendations
