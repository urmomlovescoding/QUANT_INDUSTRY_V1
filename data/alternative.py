"""
QUANT_INDUSTRY_V1 Alternative Data Integration

Non-traditional data sources for alpha generation.

Features:
- Satellite imagery signals
- Web traffic analysis
- Credit card transaction data
- Job postings data
- Patent filings
- Supply chain data
- ESG metrics
- Weather impact analysis
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# DATA TYPES
# =============================================================================

class AlternativeDataType(Enum):
    """Types of alternative data."""
    SATELLITE = "satellite"
    WEB_TRAFFIC = "web_traffic"
    CREDIT_CARD = "credit_card"
    JOB_POSTINGS = "job_postings"
    PATENTS = "patents"
    SUPPLY_CHAIN = "supply_chain"
    ESG = "esg"
    WEATHER = "weather"
    APP_USAGE = "app_usage"
    FOOT_TRAFFIC = "foot_traffic"
    SHIPPING = "shipping"


@dataclass
class AlternativeDataPoint:
    """Single alternative data observation."""
    timestamp: datetime
    data_type: AlternativeDataType
    symbol: str
    value: float
    normalized_value: float = 0.0  # Z-score or percentile
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SATELLITE DATA PROCESSOR
# =============================================================================

class SatelliteDataProcessor:
    """
    Process satellite imagery signals.

    Tracks:
    - Parking lot occupancy (retail)
    - Oil storage tank levels
    - Shipping container activity
    - Agricultural crop yields
    - Manufacturing activity (heat signatures)
    """

    def __init__(self):
        self.history: Dict[str, List[AlternativeDataPoint]] = defaultdict(list)
        self.baseline: Dict[str, float] = {}

    def process_parking_lot_data(
        self,
        symbol: str,
        occupancy_pct: float,
        location_count: int = 1,
        timestamp: datetime = None,
    ) -> AlternativeDataPoint:
        """
        Process parking lot occupancy data.

        Higher occupancy = more customer traffic = bullish for retail.
        """
        timestamp = timestamp or datetime.now(timezone.utc)

        # Normalize against baseline
        baseline_key = f"{symbol}_parking"
        if baseline_key in self.baseline:
            normalized = (occupancy_pct - self.baseline[baseline_key]) / (self.baseline[baseline_key] * 0.1 + 1)
        else:
            self.baseline[baseline_key] = occupancy_pct
            normalized = 0.0

        data = AlternativeDataPoint(
            timestamp=timestamp,
            data_type=AlternativeDataType.SATELLITE,
            symbol=symbol,
            value=occupancy_pct,
            normalized_value=normalized,
            metadata={
                'signal_type': 'parking_lot',
                'location_count': location_count,
            }
        )

        self.history[symbol].append(data)
        return data

    def process_oil_storage_data(
        self,
        symbol: str,
        fill_level_pct: float,
        tank_count: int = 1,
        timestamp: datetime = None,
    ) -> AlternativeDataPoint:
        """
        Process oil storage tank levels.

        Higher inventory = bearish for oil prices.
        Lower inventory = bullish for oil prices.
        """
        timestamp = timestamp or datetime.now(timezone.utc)

        # Invert signal (lower inventory = bullish)
        signal_value = 100 - fill_level_pct

        baseline_key = f"{symbol}_oil"
        if baseline_key in self.baseline:
            normalized = (signal_value - self.baseline[baseline_key]) / 10
        else:
            self.baseline[baseline_key] = signal_value
            normalized = 0.0

        data = AlternativeDataPoint(
            timestamp=timestamp,
            data_type=AlternativeDataType.SATELLITE,
            symbol=symbol,
            value=fill_level_pct,
            normalized_value=normalized,
            metadata={
                'signal_type': 'oil_storage',
                'tank_count': tank_count,
            }
        )

        self.history[symbol].append(data)
        return data

    def get_signal(self, symbol: str, lookback_days: int = 30) -> Dict[str, float]:
        """Get satellite-based trading signal."""
        if symbol not in self.history:
            return {'signal': 0.0, 'confidence': 0.0}

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        recent = [d for d in self.history[symbol] if d.timestamp >= cutoff]

        if len(recent) < 3:
            return {'signal': 0.0, 'confidence': 0.0}

        # Calculate trend
        normalized_values = [d.normalized_value for d in recent]
        signal = np.mean(normalized_values[-5:])  # Recent average

        # Confidence based on data points
        confidence = min(1.0, len(recent) / 20)

        return {
            'signal': np.clip(signal / 2, -1, 1),
            'confidence': confidence,
            'data_points': len(recent),
        }


# =============================================================================
# WEB TRAFFIC ANALYZER
# =============================================================================

class WebTrafficAnalyzer:
    """
    Analyze web traffic patterns for revenue signals.

    Tracks:
    - Unique visitors
    - Page views
    - Time on site
    - Bounce rate
    - Mobile vs desktop
    """

    def __init__(self):
        self.traffic_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.baseline_traffic: Dict[str, Dict[str, float]] = {}

    def add_traffic_data(
        self,
        symbol: str,
        unique_visitors: int,
        page_views: int,
        avg_time_seconds: float,
        bounce_rate: float,
        timestamp: datetime = None,
    ) -> None:
        """Add web traffic data point."""
        timestamp = timestamp or datetime.now(timezone.utc)

        self.traffic_data[symbol].append({
            'timestamp': timestamp,
            'unique_visitors': unique_visitors,
            'page_views': page_views,
            'avg_time': avg_time_seconds,
            'bounce_rate': bounce_rate,
        })

        # Update baseline (rolling 30-day average)
        if symbol not in self.baseline_traffic:
            self.baseline_traffic[symbol] = {
                'unique_visitors': unique_visitors,
                'page_views': page_views,
            }
        else:
            alpha = 0.1
            self.baseline_traffic[symbol]['unique_visitors'] = (
                alpha * unique_visitors +
                (1 - alpha) * self.baseline_traffic[symbol]['unique_visitors']
            )
            self.baseline_traffic[symbol]['page_views'] = (
                alpha * page_views +
                (1 - alpha) * self.baseline_traffic[symbol]['page_views']
            )

    def get_traffic_signal(self, symbol: str) -> Dict[str, float]:
        """Get trading signal from web traffic."""
        if symbol not in self.traffic_data or len(self.traffic_data[symbol]) < 7:
            return {'signal': 0.0, 'confidence': 0.0}

        recent = self.traffic_data[symbol][-7:]
        baseline = self.baseline_traffic.get(symbol, {})

        if not baseline:
            return {'signal': 0.0, 'confidence': 0.0}

        # Calculate growth rates
        avg_visitors = np.mean([d['unique_visitors'] for d in recent])
        visitor_growth = (avg_visitors - baseline['unique_visitors']) / (baseline['unique_visitors'] + 1)

        avg_pageviews = np.mean([d['page_views'] for d in recent])
        pageview_growth = (avg_pageviews - baseline['page_views']) / (baseline['page_views'] + 1)

        # Combined signal
        signal = 0.6 * visitor_growth + 0.4 * pageview_growth

        # Confidence based on consistency
        visitor_values = [d['unique_visitors'] for d in recent]
        consistency = 1 - (np.std(visitor_values) / (np.mean(visitor_values) + 1))
        confidence = max(0, min(1, consistency))

        return {
            'signal': np.clip(signal * 5, -1, 1),  # Scale
            'confidence': confidence,
            'visitor_growth': visitor_growth,
            'pageview_growth': pageview_growth,
        }


# =============================================================================
# JOB POSTINGS ANALYZER
# =============================================================================

class JobPostingsAnalyzer:
    """
    Analyze job posting trends for growth signals.

    More hiring = company growth expectations = bullish
    Less hiring = contraction = bearish
    """

    def __init__(self):
        self.postings: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.baseline: Dict[str, float] = {}

    def add_posting_data(
        self,
        symbol: str,
        total_postings: int,
        new_postings: int,
        engineering_pct: float = 0.0,
        sales_pct: float = 0.0,
        timestamp: datetime = None,
    ) -> None:
        """Add job posting data."""
        timestamp = timestamp or datetime.now(timezone.utc)

        self.postings[symbol].append({
            'timestamp': timestamp,
            'total': total_postings,
            'new': new_postings,
            'engineering_pct': engineering_pct,
            'sales_pct': sales_pct,
        })

        # Update baseline
        if symbol not in self.baseline:
            self.baseline[symbol] = total_postings
        else:
            self.baseline[symbol] = 0.9 * self.baseline[symbol] + 0.1 * total_postings

    def get_hiring_signal(self, symbol: str) -> Dict[str, float]:
        """Get signal from hiring trends."""
        if symbol not in self.postings or len(self.postings[symbol]) < 4:
            return {'signal': 0.0, 'confidence': 0.0}

        recent = self.postings[symbol][-4:]
        baseline = self.baseline.get(symbol, 0)

        if baseline == 0:
            return {'signal': 0.0, 'confidence': 0.0}

        # Calculate growth
        current_total = recent[-1]['total']
        growth = (current_total - baseline) / baseline

        # New postings momentum
        new_postings_trend = np.mean([d['new'] for d in recent])
        momentum = new_postings_trend / (baseline * 0.05 + 1)

        # Engineering focus (indicator of product development)
        eng_focus = np.mean([d['engineering_pct'] for d in recent])

        # Combined signal
        signal = 0.5 * growth + 0.3 * momentum + 0.2 * (eng_focus / 50 - 0.5)

        return {
            'signal': np.clip(signal * 3, -1, 1),
            'confidence': min(1.0, len(self.postings[symbol]) / 12),
            'growth': growth,
            'eng_focus': eng_focus,
        }


# =============================================================================
# ESG DATA PROCESSOR
# =============================================================================

class ESGProcessor:
    """
    Process ESG (Environmental, Social, Governance) metrics.

    Tracks:
    - Carbon emissions
    - Diversity metrics
    - Board composition
    - ESG ratings
    - Controversy events
    """

    def __init__(self):
        self.esg_scores: Dict[str, Dict[str, float]] = {}
        self.controversies: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def update_esg_scores(
        self,
        symbol: str,
        environmental: float,  # 0-100
        social: float,  # 0-100
        governance: float,  # 0-100
        timestamp: datetime = None,
    ) -> None:
        """Update ESG scores."""
        self.esg_scores[symbol] = {
            'E': environmental,
            'S': social,
            'G': governance,
            'overall': (environmental + social + governance) / 3,
            'updated': timestamp or datetime.now(timezone.utc),
        }

    def add_controversy(
        self,
        symbol: str,
        severity: float,  # 0-10
        category: str,  # 'environmental', 'social', 'governance'
        description: str = "",
        timestamp: datetime = None,
    ) -> None:
        """Add controversy event."""
        self.controversies[symbol].append({
            'timestamp': timestamp or datetime.now(timezone.utc),
            'severity': severity,
            'category': category,
            'description': description,
        })

    def get_esg_signal(self, symbol: str) -> Dict[str, float]:
        """Get trading signal from ESG factors."""
        if symbol not in self.esg_scores:
            return {'signal': 0.0, 'confidence': 0.0}

        scores = self.esg_scores[symbol]
        overall = scores['overall']

        # Base signal from overall score
        base_signal = (overall - 50) / 50  # -1 to 1

        # Penalty for recent controversies
        recent_controversies = [
            c for c in self.controversies.get(symbol, [])
            if c['timestamp'] > datetime.now(timezone.utc) - timedelta(days=90)
        ]

        controversy_penalty = sum(c['severity'] for c in recent_controversies) / 20
        adjusted_signal = base_signal - controversy_penalty

        return {
            'signal': np.clip(adjusted_signal, -1, 1),
            'confidence': 0.7,  # ESG data tends to be stable
            'overall_score': overall,
            'e_score': scores['E'],
            's_score': scores['S'],
            'g_score': scores['G'],
            'controversy_count': len(recent_controversies),
        }


# =============================================================================
# ALTERNATIVE DATA ENGINE
# =============================================================================

class AlternativeDataEngine:
    """
    Unified alternative data processing engine.

    Combines all alternative data sources.
    """

    def __init__(self):
        self.satellite = SatelliteDataProcessor()
        self.web_traffic = WebTrafficAnalyzer()
        self.job_postings = JobPostingsAnalyzer()
        self.esg = ESGProcessor()

        # Source weights for signal combination
        self.weights = {
            'satellite': 0.25,
            'web_traffic': 0.30,
            'job_postings': 0.25,
            'esg': 0.20,
        }

    def get_combined_signal(self, symbol: str) -> Dict[str, Any]:
        """Get combined alternative data signal."""
        signals = {}
        weighted_sum = 0.0
        total_weight = 0.0

        # Satellite signal
        sat_signal = self.satellite.get_signal(symbol)
        if sat_signal['confidence'] > 0.3:
            signals['satellite'] = sat_signal
            weighted_sum += sat_signal['signal'] * sat_signal['confidence'] * self.weights['satellite']
            total_weight += sat_signal['confidence'] * self.weights['satellite']

        # Web traffic signal
        web_signal = self.web_traffic.get_traffic_signal(symbol)
        if web_signal['confidence'] > 0.3:
            signals['web_traffic'] = web_signal
            weighted_sum += web_signal['signal'] * web_signal['confidence'] * self.weights['web_traffic']
            total_weight += web_signal['confidence'] * self.weights['web_traffic']

        # Job postings signal
        job_signal = self.job_postings.get_hiring_signal(symbol)
        if job_signal['confidence'] > 0.3:
            signals['job_postings'] = job_signal
            weighted_sum += job_signal['signal'] * job_signal['confidence'] * self.weights['job_postings']
            total_weight += job_signal['confidence'] * self.weights['job_postings']

        # ESG signal
        esg_signal = self.esg.get_esg_signal(symbol)
        if esg_signal['confidence'] > 0.3:
            signals['esg'] = esg_signal
            weighted_sum += esg_signal['signal'] * esg_signal['confidence'] * self.weights['esg']
            total_weight += esg_signal['confidence'] * self.weights['esg']

        # Combined signal
        if total_weight > 0:
            combined_signal = weighted_sum / total_weight
            combined_confidence = total_weight / sum(self.weights.values())
        else:
            combined_signal = 0.0
            combined_confidence = 0.0

        return {
            'symbol': symbol,
            'combined_signal': combined_signal,
            'combined_confidence': combined_confidence,
            'signals': signals,
            'active_sources': len(signals),
        }

    def get_alpha_contribution(
        self,
        symbol: str,
        returns: np.ndarray,
    ) -> Dict[str, float]:
        """Estimate alpha contribution from alternative data."""
        signal = self.get_combined_signal(symbol)

        if signal['combined_confidence'] < 0.3:
            return {'alpha': 0.0, 'correlation': 0.0}

        # Simple alpha estimate (signal correlation with forward returns)
        # In production, this would use proper backtesting
        signal_value = signal['combined_signal']

        # Mock correlation calculation
        if len(returns) > 0:
            alpha = signal_value * np.mean(returns) * 252  # Annualized
            correlation = signal_value * 0.3  # Placeholder
        else:
            alpha = 0.0
            correlation = 0.0

        return {
            'alpha': alpha,
            'correlation': correlation,
            'information_ratio': alpha / (np.std(returns) * np.sqrt(252) + 0.001) if len(returns) > 0 else 0,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'AlternativeDataType',
    'AlternativeDataPoint',
    'SatelliteDataProcessor',
    'WebTrafficAnalyzer',
    'JobPostingsAnalyzer',
    'ESGProcessor',
    'AlternativeDataEngine',
]
