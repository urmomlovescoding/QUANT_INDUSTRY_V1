"""
QUANT_INDUSTRY_V1 Real-Time Market Microstructure Analysis

Advanced order flow and market microstructure analysis.

Features:
- Order flow imbalance detection
- Toxic flow analysis (VPIN)
- Kyle's Lambda estimation
- LOB (Limit Order Book) dynamics
- Trade classification (Lee-Ready, BVC)
- Information asymmetry metrics
- Market impact estimation
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from enum import Enum
import logging
from collections import deque

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class TradeDirection(Enum):
    """Trade direction classification."""
    BUY = 1
    SELL = -1
    UNKNOWN = 0


@dataclass
class Trade:
    """Single trade record."""
    timestamp: datetime
    price: float
    size: int
    direction: TradeDirection = TradeDirection.UNKNOWN
    aggressor_side: Optional[str] = None  # 'buy' or 'sell'


@dataclass
class Quote:
    """Bid-ask quote."""
    timestamp: datetime
    bid_price: float
    bid_size: int
    ask_price: float
    ask_size: int

    @property
    def mid_price(self) -> float:
        return (self.bid_price + self.ask_price) / 2

    @property
    def spread(self) -> float:
        return self.ask_price - self.bid_price

    @property
    def spread_bps(self) -> float:
        return (self.spread / self.mid_price) * 10000


@dataclass
class OrderBookLevel:
    """Single order book level."""
    price: float
    size: int
    order_count: int = 1


@dataclass
class OrderBook:
    """Full limit order book snapshot."""
    timestamp: datetime
    bids: List[OrderBookLevel]  # Sorted by price descending
    asks: List[OrderBookLevel]  # Sorted by price ascending

    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> float:
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return 0.0

    @property
    def spread(self) -> float:
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return 0.0

    def get_book_imbalance(self, levels: int = 5) -> float:
        """Calculate order book imbalance at top N levels."""
        bid_size = sum(b.size for b in self.bids[:levels])
        ask_size = sum(a.size for a in self.asks[:levels])
        total = bid_size + ask_size
        return (bid_size - ask_size) / total if total > 0 else 0.0


# =============================================================================
# TRADE CLASSIFICATION
# =============================================================================

class TradeClassifier:
    """
    Classify trades as buyer or seller initiated.

    Implements multiple algorithms:
    - Lee-Ready (tick rule + quote rule)
    - Bulk Volume Classification (BVC)
    - Ellis-Michaely-O'Hara (EMO)
    """

    def __init__(self, quote_delay_ms: int = 0):
        self.quote_delay_ms = quote_delay_ms
        self._prev_price = None
        self._prev_mid = None

    def classify_lee_ready(
        self,
        trade: Trade,
        quote: Quote,
    ) -> TradeDirection:
        """
        Lee-Ready algorithm.

        1. If trade price > mid, classify as buy
        2. If trade price < mid, classify as sell
        3. If trade price == mid, use tick rule
        """
        mid = quote.mid_price

        if trade.price > mid:
            direction = TradeDirection.BUY
        elif trade.price < mid:
            direction = TradeDirection.SELL
        else:
            # Tick rule
            if self._prev_price is not None:
                if trade.price > self._prev_price:
                    direction = TradeDirection.BUY
                elif trade.price < self._prev_price:
                    direction = TradeDirection.SELL
                else:
                    direction = TradeDirection.UNKNOWN
            else:
                direction = TradeDirection.UNKNOWN

        self._prev_price = trade.price
        return direction

    def classify_bvc(
        self,
        volume: float,
        price_change: float,
        volatility: float,
    ) -> Tuple[float, float]:
        """
        Bulk Volume Classification.

        Estimates buy/sell volume from aggregate bars.

        Returns: (buy_volume, sell_volume)
        """
        if volatility <= 0:
            return volume / 2, volume / 2

        # Z-score of price change
        z = price_change / volatility

        # CDF approximation
        buy_pct = 0.5 * (1 + np.tanh(0.797884560802865 * z * (1 + 0.0356774 * z * z)))

        return volume * buy_pct, volume * (1 - buy_pct)

    def classify_emo(
        self,
        trade: Trade,
        quote: Quote,
    ) -> TradeDirection:
        """
        Ellis-Michaely-O'Hara algorithm.

        Quote rule first, then tick rule.
        """
        # Quote rule
        if trade.price >= quote.ask_price:
            return TradeDirection.BUY
        elif trade.price <= quote.bid_price:
            return TradeDirection.SELL

        # Tick rule for inside quotes
        if self._prev_price is not None:
            if trade.price > self._prev_price:
                return TradeDirection.BUY
            elif trade.price < self._prev_price:
                return TradeDirection.SELL

        return TradeDirection.UNKNOWN


# =============================================================================
# VPIN - Volume-Synchronized Probability of Informed Trading
# =============================================================================

class VPINCalculator:
    """
    Volume-Synchronized Probability of Informed Trading.

    VPIN measures the imbalance of buy/sell initiated volume
    in volume time (buckets of equal volume).
    """

    def __init__(
        self,
        bucket_size: float = 1000000,  # Volume per bucket
        n_buckets: int = 50,  # Number of buckets for VPIN calculation
        sigma_n: int = 50,  # Lookback for volatility
    ):
        self.bucket_size = bucket_size
        self.n_buckets = n_buckets
        self.sigma_n = sigma_n

        self.current_bucket_volume = 0.0
        self.current_bucket_buy = 0.0
        self.current_bucket_sell = 0.0

        self.buckets: deque = deque(maxlen=n_buckets)
        self.vpin_history: List[float] = []

    def update(
        self,
        volume: float,
        buy_volume: float,
        sell_volume: float,
    ) -> Optional[float]:
        """
        Update VPIN with new trade data.

        Returns VPIN if new bucket completed, else None.
        """
        remaining_volume = volume

        while remaining_volume > 0:
            space_in_bucket = self.bucket_size - self.current_bucket_volume

            if remaining_volume >= space_in_bucket:
                # Fill current bucket
                fill_ratio = space_in_bucket / volume
                self.current_bucket_buy += buy_volume * fill_ratio
                self.current_bucket_sell += sell_volume * fill_ratio
                self.current_bucket_volume = self.bucket_size

                # Complete bucket
                self._complete_bucket()

                remaining_volume -= space_in_bucket
            else:
                # Partial fill
                fill_ratio = remaining_volume / volume
                self.current_bucket_buy += buy_volume * fill_ratio
                self.current_bucket_sell += sell_volume * fill_ratio
                self.current_bucket_volume += remaining_volume
                remaining_volume = 0

        if len(self.buckets) >= self.n_buckets:
            return self._calculate_vpin()
        return None

    def _complete_bucket(self) -> None:
        """Complete current bucket and start new one."""
        imbalance = abs(self.current_bucket_buy - self.current_bucket_sell)
        self.buckets.append(imbalance)

        # Reset
        self.current_bucket_volume = 0.0
        self.current_bucket_buy = 0.0
        self.current_bucket_sell = 0.0

    def _calculate_vpin(self) -> float:
        """Calculate VPIN from bucket history."""
        if len(self.buckets) < self.n_buckets:
            return 0.0

        total_imbalance = sum(self.buckets)
        vpin = total_imbalance / (self.n_buckets * self.bucket_size)

        self.vpin_history.append(vpin)
        return vpin

    def get_vpin_cdf(self, vpin_value: float) -> float:
        """Get CDF of VPIN value based on historical distribution."""
        if len(self.vpin_history) < 10:
            return 0.5

        return np.mean(np.array(self.vpin_history) <= vpin_value)


# =============================================================================
# KYLE'S LAMBDA - Market Impact
# =============================================================================

class KyleLambdaEstimator:
    """
    Estimate Kyle's Lambda - price impact coefficient.

    Lambda measures how much prices move per unit of order flow.
    Higher lambda = less liquid market.
    """

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.price_changes: deque = deque(maxlen=window_size)
        self.order_flows: deque = deque(maxlen=window_size)

    def update(
        self,
        price_change: float,
        signed_volume: float,  # Positive = buy, negative = sell
    ) -> Optional[float]:
        """Update with new observation and estimate lambda."""
        self.price_changes.append(price_change)
        self.order_flows.append(signed_volume)

        if len(self.price_changes) < 10:
            return None

        return self._estimate_lambda()

    def _estimate_lambda(self) -> float:
        """
        Estimate lambda via OLS regression:
        ΔP = λ * Q + ε
        """
        y = np.array(self.price_changes)
        x = np.array(self.order_flows)

        # Avoid division by zero
        x_var = np.var(x)
        if x_var == 0:
            return 0.0

        # Simple OLS
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def estimate_amihud_illiquidity(
        self,
        returns: np.ndarray,
        volumes: np.ndarray,
    ) -> float:
        """
        Amihud illiquidity measure.

        ILLIQ = (1/N) * Σ |r_t| / V_t
        """
        if len(returns) == 0:
            return 0.0

        # Avoid division by zero
        volumes = np.maximum(volumes, 1e-10)

        illiq = np.mean(np.abs(returns) / volumes)
        return illiq * 1e6  # Scale for readability


# =============================================================================
# ORDER FLOW IMBALANCE
# =============================================================================

class OrderFlowImbalanceAnalyzer:
    """
    Analyze order flow imbalance patterns.
    """

    def __init__(self, window_sizes: List[int] = None):
        self.window_sizes = window_sizes or [10, 50, 100, 500]
        self.signed_volumes: deque = deque(maxlen=max(self.window_sizes))

    def update(self, signed_volume: float) -> Dict[str, float]:
        """Update with new signed volume and compute OFI."""
        self.signed_volumes.append(signed_volume)

        results = {}
        volumes = np.array(self.signed_volumes)

        for window in self.window_sizes:
            if len(volumes) >= window:
                ofi = np.sum(volumes[-window:])
                normalized_ofi = ofi / (np.sum(np.abs(volumes[-window:])) + 1e-10)
                results[f'ofi_{window}'] = ofi
                results[f'ofi_normalized_{window}'] = normalized_ofi

        return results

    def compute_ofi_from_quotes(
        self,
        prev_book: OrderBook,
        curr_book: OrderBook,
    ) -> float:
        """
        Order Flow Imbalance from quote changes.

        OFI = ΔB^bid_1 - ΔB^ask_1
        where ΔB = change in depth at best level
        """
        if not prev_book.best_bid or not curr_book.best_bid:
            return 0.0

        # Change in bid
        if curr_book.best_bid.price > prev_book.best_bid.price:
            delta_bid = curr_book.best_bid.size
        elif curr_book.best_bid.price == prev_book.best_bid.price:
            delta_bid = curr_book.best_bid.size - prev_book.best_bid.size
        else:
            delta_bid = -prev_book.best_bid.size

        # Change in ask
        if curr_book.best_ask.price < prev_book.best_ask.price:
            delta_ask = curr_book.best_ask.size
        elif curr_book.best_ask.price == prev_book.best_ask.price:
            delta_ask = curr_book.best_ask.size - prev_book.best_ask.size
        else:
            delta_ask = -prev_book.best_ask.size

        return delta_bid - delta_ask


# =============================================================================
# MICROSTRUCTURE ANALYZER
# =============================================================================

class MicrostructureAnalyzer:
    """
    Comprehensive market microstructure analysis.

    Combines all microstructure metrics into a unified interface.
    """

    def __init__(
        self,
        vpin_bucket_size: float = 1000000,
        lambda_window: int = 100,
    ):
        self.classifier = TradeClassifier()
        self.vpin = VPINCalculator(bucket_size=vpin_bucket_size)
        self.kyle_lambda = KyleLambdaEstimator(window_size=lambda_window)
        self.ofi_analyzer = OrderFlowImbalanceAnalyzer()

        # Historical metrics
        self.spread_history: deque = deque(maxlen=1000)
        self.volume_history: deque = deque(maxlen=1000)
        self.price_impact_history: deque = deque(maxlen=1000)

    def process_trade(
        self,
        trade: Trade,
        quote: Quote,
    ) -> Dict[str, Any]:
        """Process a single trade and return metrics."""
        # Classify trade
        direction = self.classifier.classify_lee_ready(trade, quote)
        trade.direction = direction

        signed_volume = trade.size * direction.value

        # Update order flow imbalance
        ofi_metrics = self.ofi_analyzer.update(signed_volume)

        # BVC classification for volume
        # (simplified - assumes we have price change/volatility)
        buy_vol = trade.size if direction == TradeDirection.BUY else 0
        sell_vol = trade.size if direction == TradeDirection.SELL else 0

        # Update VPIN
        vpin_value = self.vpin.update(trade.size, buy_vol, sell_vol)

        # Store spread
        self.spread_history.append(quote.spread_bps)

        return {
            'direction': direction.name,
            'signed_volume': signed_volume,
            'spread_bps': quote.spread_bps,
            'vpin': vpin_value,
            **ofi_metrics,
        }

    def process_price_volume(
        self,
        price_change: float,
        volume: float,
        signed_volume: float,
    ) -> Dict[str, float]:
        """Process aggregate price/volume data."""
        # Update Kyle's lambda
        lambda_val = self.kyle_lambda.update(price_change, signed_volume)

        # Update volume
        self.volume_history.append(volume)

        # Price impact
        if volume > 0:
            impact = abs(price_change) / volume * 1e6
            self.price_impact_history.append(impact)

        return {
            'kyle_lambda': lambda_val or 0.0,
            'avg_impact': np.mean(list(self.price_impact_history)) if self.price_impact_history else 0.0,
        }

    def get_liquidity_score(self) -> float:
        """
        Compute aggregate liquidity score (0-100).

        Higher = more liquid.
        """
        score = 100.0

        # Spread penalty (lower spread = higher score)
        if self.spread_history:
            avg_spread = np.mean(list(self.spread_history))
            spread_penalty = min(avg_spread * 2, 50)  # Cap at 50
            score -= spread_penalty

        # VPIN penalty (higher VPIN = lower score)
        if self.vpin.vpin_history:
            avg_vpin = np.mean(self.vpin.vpin_history[-50:])
            vpin_penalty = avg_vpin * 100  # Scale
            score -= min(vpin_penalty, 30)

        # Lambda penalty (higher lambda = lower score)
        if len(self.kyle_lambda.price_changes) >= 10:
            lambda_val = self.kyle_lambda._estimate_lambda()
            lambda_penalty = min(abs(lambda_val) * 1e6, 20)
            score -= lambda_penalty

        return max(0, min(100, score))

    def get_toxicity_score(self) -> float:
        """
        Compute flow toxicity score (0-100).

        Higher = more toxic (informed) flow.
        """
        score = 0.0

        # VPIN contribution
        if self.vpin.vpin_history:
            recent_vpin = np.mean(self.vpin.vpin_history[-20:])
            score += recent_vpin * 200  # Scale

        # OFI imbalance contribution
        if len(self.ofi_analyzer.signed_volumes) >= 50:
            recent_volumes = list(self.ofi_analyzer.signed_volumes)[-50:]
            imbalance = abs(sum(recent_volumes)) / (sum(abs(v) for v in recent_volumes) + 1e-10)
            score += imbalance * 50

        return max(0, min(100, score))

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive microstructure summary."""
        return {
            'liquidity_score': self.get_liquidity_score(),
            'toxicity_score': self.get_toxicity_score(),
            'avg_spread_bps': np.mean(list(self.spread_history)) if self.spread_history else 0.0,
            'latest_vpin': self.vpin.vpin_history[-1] if self.vpin.vpin_history else 0.0,
            'kyle_lambda': self.kyle_lambda._estimate_lambda() if len(self.kyle_lambda.price_changes) >= 10 else 0.0,
            'vpin_cdf': self.vpin.get_vpin_cdf(self.vpin.vpin_history[-1]) if self.vpin.vpin_history else 0.5,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'TradeDirection',
    'Trade',
    'Quote',
    'OrderBookLevel',
    'OrderBook',
    'TradeClassifier',
    'VPINCalculator',
    'KyleLambdaEstimator',
    'OrderFlowImbalanceAnalyzer',
    'MicrostructureAnalyzer',
]
