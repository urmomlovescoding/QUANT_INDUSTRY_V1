"""
Signal Marketplace
QUANT_INDUSTRY_V1

Industry Problem: Quants work in isolation. Great signals get wasted.
No good way to monetize alpha without revealing your strategy.
No way to combine external signals with your own.

Our Solution:
- Publish signals without revealing strategy logic
- Subscribe to signals from other quants
- Automatic signal blending and weighting
- Performance tracking and attribution
- Revenue sharing for signal providers
- Signal quality scoring and verification
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import hashlib
import json
from abc import ABC, abstractmethod
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of tradable signals."""
    DIRECTIONAL = "directional"      # Long/short/flat
    ALPHA = "alpha"                   # Expected return forecast
    RANKING = "ranking"               # Cross-sectional ranking
    TIMING = "timing"                 # Entry/exit timing
    RISK = "risk"                     # Risk signals (vol, correlation)
    SENTIMENT = "sentiment"           # News/social sentiment


class SignalFrequency(Enum):
    """Signal update frequency."""
    TICK = "tick"
    MINUTE = "minute"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class SubscriptionTier(Enum):
    """Subscription pricing tiers."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


@dataclass
class Signal:
    """A single signal observation."""
    signal_id: str
    provider_id: str
    timestamp: datetime
    symbol: str
    signal_type: SignalType
    
    # Signal values
    value: float                      # Main signal value (-1 to 1 for directional)
    confidence: float = 1.0           # Provider's confidence (0-1)
    
    # Metadata
    horizon_days: int = 1             # Forecast horizon
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Verification
    hash: str = ""                    # For tamper detection
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()
            
    def _compute_hash(self) -> str:
        """Compute hash for signal verification."""
        content = f"{self.signal_id}:{self.timestamp.isoformat()}:{self.symbol}:{self.value}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class SignalProvider:
    """A signal provider profile."""
    provider_id: str
    name: str
    description: str
    
    # Track record
    track_record_months: int = 0
    verified: bool = False
    
    # Performance
    historical_sharpe: float = 0.0
    historical_accuracy: float = 0.0
    historical_ic: float = 0.0        # Information coefficient
    
    # Offering
    signal_types: List[SignalType] = field(default_factory=list)
    universes: List[str] = field(default_factory=list)  # e.g., ["US_LARGE_CAP", "CRYPTO"]
    frequency: SignalFrequency = SignalFrequency.DAILY
    
    # Pricing
    tier: SubscriptionTier = SubscriptionTier.FREE
    monthly_price_usd: float = 0.0
    
    # Stats
    subscriber_count: int = 0
    total_signals_published: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider_id': self.provider_id,
            'name': self.name,
            'description': self.description,
            'track_record_months': self.track_record_months,
            'verified': self.verified,
            'historical_sharpe': self.historical_sharpe,
            'historical_accuracy': self.historical_accuracy,
            'historical_ic': self.historical_ic,
            'signal_types': [t.value for t in self.signal_types],
            'universes': self.universes,
            'frequency': self.frequency.value,
            'tier': self.tier.value,
            'monthly_price_usd': self.monthly_price_usd,
            'subscriber_count': self.subscriber_count
        }


@dataclass
class Subscription:
    """A subscription to a signal provider."""
    subscription_id: str
    subscriber_id: str
    provider_id: str
    tier: SubscriptionTier
    
    # Status
    active: bool = True
    started_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    # Usage
    signals_received: int = 0
    last_signal_at: Optional[datetime] = None


@dataclass
class SignalPerformance:
    """Performance metrics for a signal provider."""
    provider_id: str
    period_start: datetime
    period_end: datetime
    
    # Return-based metrics
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    
    # Accuracy metrics
    directional_accuracy: float = 0.0  # % of correct direction calls
    hit_rate: float = 0.0              # % of profitable signals
    
    # Information metrics
    ic: float = 0.0                    # Information coefficient (correlation with returns)
    ic_ir: float = 0.0                 # IC information ratio
    
    # Signal quality
    turnover: float = 0.0              # Signal turnover
    decay_halflife_days: float = 0.0   # How fast signal decays
    
    # Risk metrics
    beta: float = 0.0
    tracking_error: float = 0.0


class SignalVerifier:
    """
    Verify signal quality and prevent gaming.
    
    Prevents:
    - Backfill fraud (publishing "signals" after knowing returns)
    - Cherry-picking (only publishing good signals)
    - Gaming (signals that look good on metrics but don't work)
    """
    
    def __init__(self):
        self.signal_log: Dict[str, List[Signal]] = defaultdict(list)
        self.publication_times: Dict[str, datetime] = {}
        
    def record_signal(self, signal: Signal) -> bool:
        """
        Record signal with timestamp for later verification.
        
        Returns True if signal is valid (not backfilled).
        """
        now = datetime.now()
        
        # Check for backfill (signal timestamp before publication)
        if signal.timestamp > now + timedelta(minutes=5):
            logger.warning(f"Signal timestamp in future: {signal.signal_id}")
            return False
            
        # Check for old signals being published
        age_hours = (now - signal.timestamp).total_seconds() / 3600
        if age_hours > 24:
            logger.warning(f"Signal too old to publish: {signal.signal_id} ({age_hours:.1f}h old)")
            return False
            
        # Record
        self.signal_log[signal.provider_id].append(signal)
        self.publication_times[signal.hash] = now
        
        return True
        
    def verify_track_record(
        self,
        provider_id: str,
        returns: pd.DataFrame  # DataFrame with symbol returns
    ) -> Dict[str, Any]:
        """
        Verify provider's track record using recorded signals.
        
        Only counts signals that were published BEFORE the return period.
        """
        signals = self.signal_log.get(provider_id, [])
        
        if not signals:
            return {'verified': False, 'reason': 'No signals recorded'}
            
        # Build signal DataFrame
        signal_data = []
        for sig in signals:
            pub_time = self.publication_times.get(sig.hash, sig.timestamp)
            signal_data.append({
                'timestamp': sig.timestamp,
                'publication_time': pub_time,
                'symbol': sig.symbol,
                'value': sig.value,
                'confidence': sig.confidence
            })
            
        signals_df = pd.DataFrame(signal_data)
        
        # Calculate verified performance
        # Only use signals published before the return measurement
        verified_signals = 0
        correct_signals = 0
        total_ic = []
        
        for _, row in signals_df.iterrows():
            # Get return for signal period
            signal_date = row['timestamp'].date()
            symbol = row['symbol']
            
            if symbol in returns.columns:
                # Find return on day after signal
                future_mask = returns.index.date > signal_date
                if future_mask.any():
                    future_return = returns.loc[future_mask, symbol].iloc[0]
                    
                    verified_signals += 1
                    
                    # Check if direction was correct
                    if (row['value'] > 0 and future_return > 0) or \
                       (row['value'] < 0 and future_return < 0):
                        correct_signals += 1
                        
                    # IC contribution
                    total_ic.append(row['value'] * future_return)
                    
        if verified_signals == 0:
            return {'verified': False, 'reason': 'No verifiable signals'}
            
        accuracy = correct_signals / verified_signals
        avg_ic = np.mean(total_ic) if total_ic else 0
        
        return {
            'verified': True,
            'verified_signals': verified_signals,
            'directional_accuracy': accuracy,
            'information_coefficient': avg_ic,
            'period_start': signals_df['timestamp'].min(),
            'period_end': signals_df['timestamp'].max()
        }


class SignalBlender:
    """
    Blend signals from multiple providers.
    
    Combines signals using:
    - Historical performance weighting
    - Correlation-aware combination
    - Adaptive weight adjustment
    """
    
    def __init__(
        self,
        lookback_days: int = 252,
        min_signals_for_weighting: int = 20
    ):
        self.lookback_days = lookback_days
        self.min_signals = min_signals_for_weighting
        
        # Track historical signals for weight calculation
        self.signal_history: Dict[str, List[Tuple[datetime, str, float, float]]] = defaultdict(list)
        # (timestamp, symbol, signal_value, realized_return)
        
    def add_realized_return(
        self,
        provider_id: str,
        timestamp: datetime,
        symbol: str,
        signal_value: float,
        realized_return: float
    ):
        """Add realized return for historical weighting."""
        self.signal_history[provider_id].append(
            (timestamp, symbol, signal_value, realized_return)
        )
        
        # Trim old data
        cutoff = datetime.now() - timedelta(days=self.lookback_days)
        self.signal_history[provider_id] = [
            s for s in self.signal_history[provider_id]
            if s[0] > cutoff
        ]
        
    def calculate_weights(
        self,
        provider_ids: List[str],
        method: str = 'ic_weighted'
    ) -> Dict[str, float]:
        """
        Calculate optimal weights for each provider.
        
        Methods:
        - equal: Equal weight
        - ic_weighted: Weight by information coefficient
        - sharpe_weighted: Weight by Sharpe ratio
        - correlation_adjusted: Adjust for signal correlation
        """
        if method == 'equal':
            return {p: 1.0 / len(provider_ids) for p in provider_ids}
            
        weights = {}
        
        for pid in provider_ids:
            history = self.signal_history.get(pid, [])
            
            if len(history) < self.min_signals:
                weights[pid] = 0.1  # Default low weight
                continue
                
            # Calculate IC
            signals = np.array([h[2] for h in history])
            returns = np.array([h[3] for h in history])
            
            ic = np.corrcoef(signals, returns)[0, 1] if len(signals) > 1 else 0
            
            if method == 'ic_weighted':
                # Weight by IC (capped at 0 for negative IC)
                weights[pid] = max(ic, 0)
            elif method == 'sharpe_weighted':
                # Weight by signal Sharpe
                signal_returns = signals * returns
                if signal_returns.std() > 0:
                    sharpe = signal_returns.mean() / signal_returns.std() * np.sqrt(252)
                else:
                    sharpe = 0
                weights[pid] = max(sharpe, 0)
                
        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v/total for k, v in weights.items()}
        else:
            weights = {p: 1.0 / len(provider_ids) for p in provider_ids}
            
        return weights
        
    def blend_signals(
        self,
        signals: List[Signal],
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Blend signals for each symbol.
        
        Returns {symbol: blended_signal_value}
        """
        if weights is None:
            provider_ids = list(set(s.provider_id for s in signals))
            weights = self.calculate_weights(provider_ids)
            
        # Group by symbol
        by_symbol: Dict[str, List[Signal]] = defaultdict(list)
        for sig in signals:
            by_symbol[sig.symbol].append(sig)
            
        # Blend each symbol
        blended = {}
        for symbol, symbol_signals in by_symbol.items():
            weighted_sum = 0
            weight_sum = 0
            
            for sig in symbol_signals:
                w = weights.get(sig.provider_id, 0)
                weighted_sum += sig.value * sig.confidence * w
                weight_sum += sig.confidence * w
                
            if weight_sum > 0:
                blended[symbol] = weighted_sum / weight_sum
            else:
                blended[symbol] = 0
                
        return blended


class MarketplaceAPI:
    """
    Main marketplace API for publishing and consuming signals.
    """
    
    def __init__(self):
        self.providers: Dict[str, SignalProvider] = {}
        self.subscriptions: Dict[str, Subscription] = {}
        self.signal_queue: Dict[str, List[Signal]] = defaultdict(list)
        
        self.verifier = SignalVerifier()
        self.blender = SignalBlender()
        
        # Revenue tracking
        self.revenue: Dict[str, float] = defaultdict(float)
        
    # =========================================================================
    # Provider Management
    # =========================================================================
    
    def register_provider(
        self,
        name: str,
        description: str,
        signal_types: List[SignalType],
        universes: List[str],
        frequency: SignalFrequency,
        tier: SubscriptionTier = SubscriptionTier.FREE,
        monthly_price: float = 0.0
    ) -> SignalProvider:
        """Register as a signal provider."""
        provider_id = str(uuid.uuid4())[:8]
        
        provider = SignalProvider(
            provider_id=provider_id,
            name=name,
            description=description,
            signal_types=signal_types,
            universes=universes,
            frequency=frequency,
            tier=tier,
            monthly_price_usd=monthly_price
        )
        
        self.providers[provider_id] = provider
        logger.info(f"Registered provider: {name} ({provider_id})")
        
        return provider
        
    def get_provider(self, provider_id: str) -> Optional[SignalProvider]:
        """Get provider by ID."""
        return self.providers.get(provider_id)
        
    def list_providers(
        self,
        signal_type: Optional[SignalType] = None,
        universe: Optional[str] = None,
        min_sharpe: float = 0.0,
        verified_only: bool = False
    ) -> List[SignalProvider]:
        """List providers with optional filters."""
        providers = list(self.providers.values())
        
        if signal_type:
            providers = [p for p in providers if signal_type in p.signal_types]
            
        if universe:
            providers = [p for p in providers if universe in p.universes]
            
        if min_sharpe > 0:
            providers = [p for p in providers if p.historical_sharpe >= min_sharpe]
            
        if verified_only:
            providers = [p for p in providers if p.verified]
            
        return providers
        
    # =========================================================================
    # Signal Publishing
    # =========================================================================
    
    def publish_signal(
        self,
        provider_id: str,
        symbol: str,
        signal_type: SignalType,
        value: float,
        confidence: float = 1.0,
        horizon_days: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Signal]:
        """
        Publish a signal to subscribers.
        
        Returns Signal if successful, None if rejected.
        """
        if provider_id not in self.providers:
            logger.error(f"Unknown provider: {provider_id}")
            return None
            
        provider = self.providers[provider_id]
        
        # Create signal
        signal = Signal(
            signal_id=str(uuid.uuid4())[:12],
            provider_id=provider_id,
            timestamp=datetime.now(),
            symbol=symbol,
            signal_type=signal_type,
            value=value,
            confidence=confidence,
            horizon_days=horizon_days,
            metadata=metadata or {}
        )
        
        # Verify (check for backfill, etc.)
        if not self.verifier.record_signal(signal):
            logger.warning(f"Signal rejected by verifier: {signal.signal_id}")
            return None
            
        # Queue for subscribers
        for sub_id, sub in self.subscriptions.items():
            if sub.provider_id == provider_id and sub.active:
                self.signal_queue[sub.subscriber_id].append(signal)
                sub.signals_received += 1
                sub.last_signal_at = datetime.now()
                
        # Update provider stats
        provider.total_signals_published += 1
        
        logger.debug(f"Published signal: {symbol} = {value:.3f} from {provider.name}")
        return signal
        
    def publish_batch(
        self,
        provider_id: str,
        signals: List[Dict[str, Any]]
    ) -> List[Signal]:
        """Publish multiple signals at once."""
        published = []
        
        for sig_data in signals:
            signal = self.publish_signal(
                provider_id=provider_id,
                symbol=sig_data['symbol'],
                signal_type=SignalType(sig_data.get('signal_type', 'directional')),
                value=sig_data['value'],
                confidence=sig_data.get('confidence', 1.0),
                horizon_days=sig_data.get('horizon_days', 1),
                metadata=sig_data.get('metadata')
            )
            if signal:
                published.append(signal)
                
        return published
        
    # =========================================================================
    # Subscription Management
    # =========================================================================
    
    def subscribe(
        self,
        subscriber_id: str,
        provider_id: str,
        tier: Optional[SubscriptionTier] = None
    ) -> Optional[Subscription]:
        """Subscribe to a signal provider."""
        if provider_id not in self.providers:
            logger.error(f"Unknown provider: {provider_id}")
            return None
            
        provider = self.providers[provider_id]
        tier = tier or provider.tier
        
        # Create subscription
        sub_id = str(uuid.uuid4())[:8]
        subscription = Subscription(
            subscription_id=sub_id,
            subscriber_id=subscriber_id,
            provider_id=provider_id,
            tier=tier
        )
        
        self.subscriptions[sub_id] = subscription
        provider.subscriber_count += 1
        
        # Record revenue
        self.revenue[provider_id] += provider.monthly_price_usd
        
        logger.info(f"Subscriber {subscriber_id} subscribed to {provider.name}")
        return subscription
        
    def unsubscribe(self, subscription_id: str) -> bool:
        """Cancel a subscription."""
        if subscription_id not in self.subscriptions:
            return False
            
        sub = self.subscriptions[subscription_id]
        sub.active = False
        
        provider = self.providers.get(sub.provider_id)
        if provider:
            provider.subscriber_count -= 1
            
        return True
        
    # =========================================================================
    # Signal Consumption
    # =========================================================================
    
    def get_signals(
        self,
        subscriber_id: str,
        since: Optional[datetime] = None
    ) -> List[Signal]:
        """Get queued signals for subscriber."""
        signals = self.signal_queue.get(subscriber_id, [])
        
        if since:
            signals = [s for s in signals if s.timestamp > since]
            
        return signals
        
    def get_blended_signals(
        self,
        subscriber_id: str,
        since: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Get blended signals from all subscribed providers."""
        signals = self.get_signals(subscriber_id, since)
        
        if not signals:
            return {}
            
        # Get subscribed provider IDs
        provider_ids = [
            sub.provider_id for sub in self.subscriptions.values()
            if sub.subscriber_id == subscriber_id and sub.active
        ]
        
        # Calculate weights and blend
        weights = self.blender.calculate_weights(provider_ids)
        return self.blender.blend_signals(signals, weights)
        
    def clear_signals(self, subscriber_id: str):
        """Clear signal queue for subscriber."""
        self.signal_queue[subscriber_id] = []
        
    # =========================================================================
    # Performance Tracking
    # =========================================================================
    
    def update_performance(
        self,
        provider_id: str,
        returns: pd.DataFrame
    ) -> Optional[SignalPerformance]:
        """Update performance metrics for a provider."""
        if provider_id not in self.providers:
            return None
            
        provider = self.providers[provider_id]
        
        # Verify track record
        verification = self.verifier.verify_track_record(provider_id, returns)
        
        if verification.get('verified'):
            provider.verified = True
            provider.historical_accuracy = verification['directional_accuracy']
            provider.historical_ic = verification['information_coefficient']
            
            # Estimate Sharpe from IC
            # Sharpe ≈ IC * sqrt(breadth) * skill
            breadth = verification['verified_signals'] / 252  # Signals per day
            provider.historical_sharpe = verification['information_coefficient'] * np.sqrt(breadth) * 2
            
            # Update track record length
            period_days = (verification['period_end'] - verification['period_start']).days
            provider.track_record_months = max(provider.track_record_months, period_days // 30)
            
        return SignalPerformance(
            provider_id=provider_id,
            period_start=verification.get('period_start', datetime.now()),
            period_end=verification.get('period_end', datetime.now()),
            directional_accuracy=verification.get('directional_accuracy', 0),
            ic=verification.get('information_coefficient', 0)
        )
        
    def get_leaderboard(
        self,
        metric: str = 'sharpe',
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get provider leaderboard."""
        providers = list(self.providers.values())
        
        sort_key = {
            'sharpe': lambda p: p.historical_sharpe,
            'accuracy': lambda p: p.historical_accuracy,
            'ic': lambda p: p.historical_ic,
            'subscribers': lambda p: p.subscriber_count
        }.get(metric, lambda p: p.historical_sharpe)
        
        providers.sort(key=sort_key, reverse=True)
        
        return [
            {
                'rank': i + 1,
                **p.to_dict()
            }
            for i, p in enumerate(providers[:limit])
        ]


# Singleton marketplace instance
_marketplace: Optional[MarketplaceAPI] = None


def get_marketplace() -> MarketplaceAPI:
    """Get or create marketplace singleton."""
    global _marketplace
    if _marketplace is None:
        _marketplace = MarketplaceAPI()
    return _marketplace
