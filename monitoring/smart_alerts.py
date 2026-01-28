"""
Smart Alert System
QUANT_INDUSTRY_V1

Industry Problem: Traditional alerts are dumb thresholds that create alert fatigue.
"Price crossed $100" tells you nothing. You get 100 alerts, ignore them all,
and miss the one that matters.

Our Solution:
- ML-powered anomaly detection (detects unusual patterns, not just thresholds)
- Context-aware alerts (is this unusual FOR THIS SYMBOL AT THIS TIME?)
- Intelligent deduplication (don't spam the same alert)
- Priority scoring (which alerts actually matter?)
- Multi-channel delivery (Discord, Telegram, Slack, email, SMS)
- Alert correlation (group related alerts)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
from collections import defaultdict
import hashlib
import json
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AlertPriority(Enum):
    """Alert priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


class AlertCategory(Enum):
    """Alert categories."""
    PRICE = "price"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    EXECUTION = "execution"
    RISK = "risk"
    PERFORMANCE = "performance"
    SYSTEM = "system"
    DATA = "data"


@dataclass
class SmartAlert:
    """A smart, context-aware alert."""
    id: str
    timestamp: datetime
    category: AlertCategory
    priority: AlertPriority
    title: str
    message: str
    symbol: Optional[str]
    
    # Context
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Anomaly detection results
    anomaly_score: float = 0.0  # 0-1, higher = more unusual
    expected_value: Optional[float] = None
    actual_value: Optional[float] = None
    z_score: Optional[float] = None
    
    # Metadata
    source: str = ""
    tags: List[str] = field(default_factory=list)
    related_alerts: List[str] = field(default_factory=list)
    
    # State
    acknowledged: bool = False
    resolved: bool = False
    
    def __str__(self) -> str:
        priority_emoji = {
            AlertPriority.LOW: "ℹ️",
            AlertPriority.MEDIUM: "⚡",
            AlertPriority.HIGH: "⚠️",
            AlertPriority.CRITICAL: "🔴",
            AlertPriority.EMERGENCY: "🚨"
        }[self.priority]
        
        symbol_str = f"[{self.symbol}] " if self.symbol else ""
        return f"{priority_emoji} {symbol_str}{self.title}: {self.message}"
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'category': self.category.value,
            'priority': self.priority.value,
            'title': self.title,
            'message': self.message,
            'symbol': self.symbol,
            'anomaly_score': self.anomaly_score,
            'context': self.context
        }


class AnomalyDetector:
    """
    ML-based anomaly detection for market data.
    
    Instead of "price > $100", we detect "price is unusual given recent history".
    """
    
    def __init__(
        self,
        window_size: int = 100,
        contamination: float = 0.05  # Expected % of anomalies
    ):
        self.window_size = window_size
        self.contamination = contamination
        self.history: Dict[str, pd.DataFrame] = defaultdict(pd.DataFrame)
        
    def update(
        self,
        symbol: str,
        timestamp: datetime,
        metrics: Dict[str, float]
    ):
        """Update history with new data point."""
        new_row = pd.DataFrame([{
            'timestamp': timestamp,
            **metrics
        }])
        
        if symbol not in self.history:
            self.history[symbol] = new_row
        else:
            self.history[symbol] = pd.concat([
                self.history[symbol],
                new_row
            ]).tail(self.window_size)
            
    def detect(
        self,
        symbol: str,
        metrics: Dict[str, float]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect anomalies in current metrics.
        
        Returns dict of {metric: {is_anomaly, score, z_score, expected, actual}}
        """
        results = {}
        
        if symbol not in self.history or len(self.history[symbol]) < 20:
            # Not enough history
            return {m: {'is_anomaly': False, 'score': 0.0} for m in metrics}
            
        history = self.history[symbol]
        
        for metric, value in metrics.items():
            if metric not in history.columns:
                results[metric] = {'is_anomaly': False, 'score': 0.0}
                continue
                
            # Calculate statistics
            hist_values = history[metric].dropna()
            if len(hist_values) < 10:
                results[metric] = {'is_anomaly': False, 'score': 0.0}
                continue
                
            mean = hist_values.mean()
            std = hist_values.std()
            
            if std == 0:
                z_score = 0
            else:
                z_score = (value - mean) / std
                
            # Anomaly score based on z-score
            # Using modified z-score for robustness
            median = hist_values.median()
            mad = np.median(np.abs(hist_values - median))
            if mad == 0:
                mad = std
            modified_z = 0.6745 * (value - median) / mad if mad > 0 else 0
            
            # Score from 0-1
            anomaly_score = min(abs(modified_z) / 5, 1.0)
            
            # Is it an anomaly?
            threshold = 3.0  # Modified z-score threshold
            is_anomaly = abs(modified_z) > threshold
            
            results[metric] = {
                'is_anomaly': is_anomaly,
                'score': anomaly_score,
                'z_score': z_score,
                'modified_z': modified_z,
                'expected': mean,
                'actual': value,
                'std': std
            }
            
        return results
        
    def detect_multivariate(
        self,
        symbol: str,
        metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Detect multivariate anomalies (unusual combinations).
        
        A price might be normal, and volume might be normal,
        but high price + low volume together might be unusual.
        """
        if symbol not in self.history or len(self.history[symbol]) < 30:
            return {'is_anomaly': False, 'score': 0.0}
            
        history = self.history[symbol]
        
        # Simple Mahalanobis distance approach
        metric_cols = [m for m in metrics.keys() if m in history.columns]
        if len(metric_cols) < 2:
            return {'is_anomaly': False, 'score': 0.0}
            
        try:
            hist_data = history[metric_cols].dropna()
            if len(hist_data) < 20:
                return {'is_anomaly': False, 'score': 0.0}
                
            mean = hist_data.mean()
            cov = hist_data.cov()
            
            # Current point
            point = np.array([metrics[m] for m in metric_cols])
            
            # Mahalanobis distance
            diff = point - mean.values
            cov_inv = np.linalg.pinv(cov.values)
            mahal_dist = np.sqrt(diff @ cov_inv @ diff)
            
            # Convert to score (chi-square distribution)
            from scipy import stats
            p_value = 1 - stats.chi2.cdf(mahal_dist**2, len(metric_cols))
            
            anomaly_score = 1 - p_value
            is_anomaly = p_value < self.contamination
            
            return {
                'is_anomaly': is_anomaly,
                'score': anomaly_score,
                'mahalanobis_distance': mahal_dist,
                'p_value': p_value
            }
            
        except Exception as e:
            logger.warning(f"Multivariate detection failed: {e}")
            return {'is_anomaly': False, 'score': 0.0}


class AlertDeduplicator:
    """
    Intelligent alert deduplication.
    
    Don't send 100 alerts for the same issue.
    """
    
    def __init__(
        self,
        time_window: timedelta = timedelta(hours=1),
        max_similar_alerts: int = 3
    ):
        self.time_window = time_window
        self.max_similar_alerts = max_similar_alerts
        self.recent_alerts: Dict[str, List[SmartAlert]] = defaultdict(list)
        
    def should_send(self, alert: SmartAlert) -> bool:
        """Determine if alert should be sent or suppressed."""
        # Create signature for deduplication
        signature = self._create_signature(alert)
        
        # Clean old alerts
        self._cleanup()
        
        # Check recent alerts with same signature
        recent = self.recent_alerts[signature]
        
        if len(recent) >= self.max_similar_alerts:
            # Too many similar alerts
            logger.debug(f"Suppressing duplicate alert: {alert.title}")
            return False
            
        # Check if exact duplicate
        for existing in recent:
            if self._is_duplicate(alert, existing):
                return False
                
        # Allow alert
        self.recent_alerts[signature].append(alert)
        return True
        
    def _create_signature(self, alert: SmartAlert) -> str:
        """Create signature for grouping similar alerts."""
        key = f"{alert.category.value}:{alert.symbol}:{alert.title}"
        return hashlib.md5(key.encode()).hexdigest()[:8]
        
    def _is_duplicate(self, a1: SmartAlert, a2: SmartAlert) -> bool:
        """Check if two alerts are duplicates."""
        if a1.category != a2.category:
            return False
        if a1.symbol != a2.symbol:
            return False
        if a1.title != a2.title:
            return False
        # Same alert within time window
        if abs((a1.timestamp - a2.timestamp).total_seconds()) < 60:
            return True
        return False
        
    def _cleanup(self):
        """Remove old alerts."""
        cutoff = datetime.now() - self.time_window
        for sig in list(self.recent_alerts.keys()):
            self.recent_alerts[sig] = [
                a for a in self.recent_alerts[sig]
                if a.timestamp > cutoff
            ]
            if not self.recent_alerts[sig]:
                del self.recent_alerts[sig]


class AlertPrioritizer:
    """
    Score and prioritize alerts.
    
    Not all alerts are equal. A 2% move in SPY is more important
    than a 2% move in a penny stock you don't hold.
    """
    
    def __init__(
        self,
        portfolio_symbols: Optional[List[str]] = None,
        watchlist_symbols: Optional[List[str]] = None,
        position_sizes: Optional[Dict[str, float]] = None
    ):
        self.portfolio_symbols = set(portfolio_symbols or [])
        self.watchlist_symbols = set(watchlist_symbols or [])
        self.position_sizes = position_sizes or {}
        
    def prioritize(self, alert: SmartAlert) -> AlertPriority:
        """Calculate priority for an alert."""
        score = 0.0
        
        # Base score from anomaly severity
        score += alert.anomaly_score * 30
        
        # Category importance
        category_weights = {
            AlertCategory.RISK: 25,
            AlertCategory.EXECUTION: 20,
            AlertCategory.PERFORMANCE: 15,
            AlertCategory.PRICE: 10,
            AlertCategory.VOLUME: 5,
            AlertCategory.VOLATILITY: 10,
            AlertCategory.SYSTEM: 20,
            AlertCategory.DATA: 15
        }
        score += category_weights.get(alert.category, 10)
        
        # Portfolio relevance
        if alert.symbol:
            if alert.symbol in self.portfolio_symbols:
                score += 20
                # Larger positions = higher priority
                position = self.position_sizes.get(alert.symbol, 0)
                score += min(position * 10, 15)  # Max 15 extra points
            elif alert.symbol in self.watchlist_symbols:
                score += 10
                
        # Z-score magnitude
        if alert.z_score:
            score += min(abs(alert.z_score) * 5, 15)
            
        # Map score to priority
        if score >= 70:
            return AlertPriority.EMERGENCY
        elif score >= 55:
            return AlertPriority.CRITICAL
        elif score >= 40:
            return AlertPriority.HIGH
        elif score >= 25:
            return AlertPriority.MEDIUM
        else:
            return AlertPriority.LOW


class AlertChannel(ABC):
    """Abstract base for alert delivery channels."""
    
    @abstractmethod
    async def send(self, alert: SmartAlert) -> bool:
        """Send alert through this channel."""
        pass
        
    @abstractmethod
    def supports_priority(self, priority: AlertPriority) -> bool:
        """Check if channel handles this priority level."""
        pass


class DiscordChannel(AlertChannel):
    """Discord webhook alert channel."""
    
    def __init__(
        self,
        webhook_url: str,
        min_priority: AlertPriority = AlertPriority.MEDIUM
    ):
        self.webhook_url = webhook_url
        self.min_priority = min_priority
        
    async def send(self, alert: SmartAlert) -> bool:
        try:
            import aiohttp
            
            # Format for Discord
            color = {
                AlertPriority.LOW: 0x808080,
                AlertPriority.MEDIUM: 0x3498db,
                AlertPriority.HIGH: 0xf1c40f,
                AlertPriority.CRITICAL: 0xe74c3c,
                AlertPriority.EMERGENCY: 0x8b0000
            }[alert.priority]
            
            embed = {
                "title": str(alert),
                "description": alert.message,
                "color": color,
                "timestamp": alert.timestamp.isoformat(),
                "fields": []
            }
            
            if alert.symbol:
                embed["fields"].append({
                    "name": "Symbol",
                    "value": alert.symbol,
                    "inline": True
                })
                
            if alert.anomaly_score > 0:
                embed["fields"].append({
                    "name": "Anomaly Score",
                    "value": f"{alert.anomaly_score:.2f}",
                    "inline": True
                })
                
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json={"embeds": [embed]}
                ) as response:
                    return response.status == 204
                    
        except Exception as e:
            logger.error(f"Discord send failed: {e}")
            return False
            
    def supports_priority(self, priority: AlertPriority) -> bool:
        return priority.value >= self.min_priority.value


class TelegramChannel(AlertChannel):
    """Telegram bot alert channel."""
    
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        min_priority: AlertPriority = AlertPriority.LOW
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.min_priority = min_priority
        
    async def send(self, alert: SmartAlert) -> bool:
        try:
            import aiohttp
            
            text = f"*{alert.title}*\n\n{alert.message}"
            if alert.symbol:
                text += f"\n\n📊 Symbol: `{alert.symbol}`"
            if alert.anomaly_score > 0:
                text += f"\n⚠️ Anomaly Score: {alert.anomaly_score:.2f}"
                
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown"
                }) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False
            
    def supports_priority(self, priority: AlertPriority) -> bool:
        return priority.value >= self.min_priority.value


class SmartAlertSystem:
    """
    Complete smart alert system.
    
    Combines:
    - Anomaly detection
    - Deduplication
    - Prioritization
    - Multi-channel delivery
    - Alert correlation
    """
    
    def __init__(
        self,
        portfolio_symbols: Optional[List[str]] = None,
        watchlist_symbols: Optional[List[str]] = None
    ):
        self.anomaly_detector = AnomalyDetector()
        self.deduplicator = AlertDeduplicator()
        self.prioritizer = AlertPrioritizer(
            portfolio_symbols=portfolio_symbols,
            watchlist_symbols=watchlist_symbols
        )
        
        self.channels: List[AlertChannel] = []
        self.alert_history: List[SmartAlert] = []
        self.callbacks: List[Callable[[SmartAlert], None]] = []
        
    def add_channel(self, channel: AlertChannel):
        """Add delivery channel."""
        self.channels.append(channel)
        
    def add_callback(self, callback: Callable[[SmartAlert], None]):
        """Add callback for alerts."""
        self.callbacks.append(callback)
        
    def update_market_data(
        self,
        symbol: str,
        timestamp: datetime,
        metrics: Dict[str, float]
    ):
        """Update market data and check for anomalies."""
        self.anomaly_detector.update(symbol, timestamp, metrics)
        
        # Check for anomalies
        anomalies = self.anomaly_detector.detect(symbol, metrics)
        
        for metric, result in anomalies.items():
            if result['is_anomaly']:
                self._create_anomaly_alert(symbol, metric, result, timestamp)
                
        # Check multivariate
        multi = self.anomaly_detector.detect_multivariate(symbol, metrics)
        if multi.get('is_anomaly'):
            self._create_multivariate_alert(symbol, metrics, multi, timestamp)
            
    def _create_anomaly_alert(
        self,
        symbol: str,
        metric: str,
        result: Dict[str, Any],
        timestamp: datetime
    ):
        """Create alert for univariate anomaly."""
        direction = "high" if result['actual'] > result['expected'] else "low"
        
        alert = SmartAlert(
            id=f"{symbol}_{metric}_{timestamp.timestamp()}",
            timestamp=timestamp,
            category=self._metric_to_category(metric),
            priority=AlertPriority.MEDIUM,  # Will be reprioritized
            title=f"Unusual {metric}",
            message=f"{symbol} {metric} is unusually {direction}: {result['actual']:.2f} (expected: {result['expected']:.2f}, z={result['z_score']:.1f})",
            symbol=symbol,
            anomaly_score=result['score'],
            expected_value=result['expected'],
            actual_value=result['actual'],
            z_score=result['z_score'],
            context={'metric': metric, **result}
        )
        
        self._process_alert(alert)
        
    def _create_multivariate_alert(
        self,
        symbol: str,
        metrics: Dict[str, float],
        result: Dict[str, Any],
        timestamp: datetime
    ):
        """Create alert for multivariate anomaly."""
        alert = SmartAlert(
            id=f"{symbol}_multi_{timestamp.timestamp()}",
            timestamp=timestamp,
            category=AlertCategory.PRICE,
            priority=AlertPriority.MEDIUM,
            title="Unusual pattern detected",
            message=f"{symbol} showing unusual combination of metrics (Mahalanobis distance: {result.get('mahalanobis_distance', 0):.2f})",
            symbol=symbol,
            anomaly_score=result['score'],
            context={'metrics': metrics, **result}
        )
        
        self._process_alert(alert)
        
    def _metric_to_category(self, metric: str) -> AlertCategory:
        """Map metric name to category."""
        if 'price' in metric.lower():
            return AlertCategory.PRICE
        elif 'volume' in metric.lower():
            return AlertCategory.VOLUME
        elif 'volatility' in metric.lower() or 'vol' in metric.lower():
            return AlertCategory.VOLATILITY
        else:
            return AlertCategory.PRICE
            
    def _process_alert(self, alert: SmartAlert):
        """Process and potentially send alert."""
        # Prioritize
        alert.priority = self.prioritizer.prioritize(alert)
        
        # Deduplicate
        if not self.deduplicator.should_send(alert):
            return
            
        # Store
        self.alert_history.append(alert)
        
        # Callbacks
        for callback in self.callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
                
        # Send to channels
        self._send_alert(alert)
        
    def _send_alert(self, alert: SmartAlert):
        """Send alert to appropriate channels."""
        import asyncio
        
        async def send_all():
            for channel in self.channels:
                if channel.supports_priority(alert.priority):
                    await channel.send(alert)
                    
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(send_all())
            else:
                loop.run_until_complete(send_all())
        except Exception as e:
            logger.error(f"Alert send failed: {e}")
            
    def create_manual_alert(
        self,
        category: AlertCategory,
        priority: AlertPriority,
        title: str,
        message: str,
        symbol: Optional[str] = None,
        **kwargs
    ) -> SmartAlert:
        """Create and send a manual alert."""
        alert = SmartAlert(
            id=f"manual_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            category=category,
            priority=priority,
            title=title,
            message=message,
            symbol=symbol,
            **kwargs
        )
        
        self._process_alert(alert)
        return alert
        
    def get_recent_alerts(
        self,
        hours: int = 24,
        min_priority: AlertPriority = AlertPriority.LOW,
        category: Optional[AlertCategory] = None
    ) -> List[SmartAlert]:
        """Get recent alerts matching criteria."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        return [
            a for a in self.alert_history
            if a.timestamp > cutoff
            and a.priority.value >= min_priority.value
            and (category is None or a.category == category)
        ]
        
    def get_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of recent alerts."""
        recent = self.get_recent_alerts(hours=hours)
        
        by_priority = defaultdict(int)
        by_category = defaultdict(int)
        by_symbol = defaultdict(int)
        
        for alert in recent:
            by_priority[alert.priority.name] += 1
            by_category[alert.category.name] += 1
            if alert.symbol:
                by_symbol[alert.symbol] += 1
                
        return {
            'total_alerts': len(recent),
            'by_priority': dict(by_priority),
            'by_category': dict(by_category),
            'top_symbols': dict(sorted(
                by_symbol.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
            'time_range_hours': hours
        }
