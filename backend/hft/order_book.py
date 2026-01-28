"""
QUANT INDUSTRY - Order Book Microstructure Analysis
====================================================
HFT-grade order book analysis:
- Level 2 order book representation
- Bid-ask imbalance signals
- Order flow toxicity (VPIN)
- Price impact estimation
- Liquidity metrics
- Queue position modeling

This is what separates retail from institutional.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Deque

import numpy as np

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BID = "bid"
    ASK = "ask"


@dataclass
class PriceLevel:
    """Single price level in order book"""
    price: float
    size: int
    order_count: int = 1
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def notional(self) -> float:
        return self.price * self.size


@dataclass
class OrderBookSnapshot:
    """Point-in-time order book snapshot"""
    timestamp: datetime
    symbol: str
    bids: List[PriceLevel]  # Sorted descending (best bid first)
    asks: List[PriceLevel]  # Sorted ascending (best ask first)
    
    @property
    def best_bid(self) -> Optional[PriceLevel]:
        return self.bids[0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[PriceLevel]:
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
        return float('inf')
    
    @property
    def spread_bps(self) -> float:
        if self.mid_price > 0:
            return (self.spread / self.mid_price) * 10000
        return float('inf')
    
    @property
    def weighted_mid(self) -> float:
        """Size-weighted mid price (microprice)"""
        if self.best_bid and self.best_ask:
            bid_size = self.best_bid.size
            ask_size = self.best_ask.size
            total = bid_size + ask_size
            if total > 0:
                return (self.best_bid.price * ask_size + self.best_ask.price * bid_size) / total
        return self.mid_price


@dataclass
class OrderBookMetrics:
    """Comprehensive order book metrics"""
    timestamp: datetime
    symbol: str
    
    # Basic metrics
    mid_price: float
    spread: float
    spread_bps: float
    microprice: float
    
    # Depth metrics
    bid_depth_5: float      # Total size at top 5 bid levels
    ask_depth_5: float      # Total size at top 5 ask levels
    bid_depth_10: float
    ask_depth_10: float
    
    # Imbalance metrics
    imbalance_1: float      # (bid - ask) / (bid + ask) at level 1
    imbalance_5: float      # Aggregated over 5 levels
    imbalance_10: float
    
    # Pressure metrics
    bid_pressure: float     # Weighted bid pressure
    ask_pressure: float     # Weighted ask pressure
    net_pressure: float     # bid - ask pressure
    
    # Liquidity metrics
    depth_ratio: float      # bid_depth / ask_depth
    order_count_ratio: float
    
    # Queue metrics
    bid_queue_position: float  # Estimated queue position
    ask_queue_position: float
    
    def to_features(self) -> Dict[str, float]:
        """Convert to ML feature dict"""
        return {
            "spread_bps": self.spread_bps,
            "microprice_delta": (self.microprice - self.mid_price) / self.mid_price * 10000 if self.mid_price > 0 else 0,
            "imbalance_1": self.imbalance_1,
            "imbalance_5": self.imbalance_5,
            "imbalance_10": self.imbalance_10,
            "net_pressure": self.net_pressure,
            "depth_ratio": self.depth_ratio,
            "log_depth_ratio": np.log(self.depth_ratio) if self.depth_ratio > 0 else 0,
        }


class OrderBook:
    """
    Real-time order book with microstructure analysis.
    
    Features:
    1. Efficient updates (O(log n))
    2. Imbalance signals
    3. Depth analysis
    4. Price impact estimation
    
    Usage:
    ------
    >>> book = OrderBook("AAPL")
    >>> 
    >>> # Update from L2 data
    >>> book.update_level(OrderSide.BID, price=150.00, size=1000)
    >>> book.update_level(OrderSide.ASK, price=150.05, size=500)
    >>> 
    >>> # Get metrics
    >>> metrics = book.get_metrics()
    >>> print(f"Imbalance: {metrics.imbalance_1:.2f}")
    >>>
    >>> # Estimate price impact
    >>> impact = book.estimate_impact(side=OrderSide.BID, size=5000)
    >>> print(f"Expected slippage: {impact:.4f}")
    """
    
    def __init__(
        self,
        symbol: str,
        max_levels: int = 20,
        history_size: int = 1000
    ):
        """
        Initialize order book.
        
        Args:
            symbol: Trading symbol
            max_levels: Maximum depth levels to track
            history_size: Number of historical snapshots to keep
        """
        self.symbol = symbol
        self.max_levels = max_levels
        
        # Current book state
        self.bids: Dict[float, PriceLevel] = {}
        self.asks: Dict[float, PriceLevel] = {}
        
        # Sorted price lists for efficient access
        self._bid_prices: List[float] = []
        self._ask_prices: List[float] = []
        
        # History
        self.history: Deque[OrderBookSnapshot] = deque(maxlen=history_size)
        self.metrics_history: Deque[OrderBookMetrics] = deque(maxlen=history_size)
        
        # Trade history for VPIN
        self.trades: Deque[Tuple[datetime, float, int, str]] = deque(maxlen=10000)
        
        self.last_update = datetime.now()
        
        logger.info(f"OrderBook initialized: {symbol}, {max_levels} levels")
    
    def update_level(
        self,
        side: OrderSide,
        price: float,
        size: int,
        order_count: int = 1
    ):
        """
        Update a single price level.
        
        Args:
            side: BID or ASK
            price: Price level
            size: New size (0 = remove level)
            order_count: Number of orders at level
        """
        book = self.bids if side == OrderSide.BID else self.asks
        prices = self._bid_prices if side == OrderSide.BID else self._ask_prices
        
        if size == 0:
            # Remove level
            if price in book:
                del book[price]
                prices.remove(price)
        else:
            # Add/update level
            if price not in book:
                # Insert in sorted position
                if side == OrderSide.BID:
                    # Bids sorted descending
                    idx = 0
                    while idx < len(prices) and prices[idx] > price:
                        idx += 1
                    prices.insert(idx, price)
                else:
                    # Asks sorted ascending
                    idx = 0
                    while idx < len(prices) and prices[idx] < price:
                        idx += 1
                    prices.insert(idx, price)
            
            book[price] = PriceLevel(
                price=price,
                size=size,
                order_count=order_count,
                timestamp=datetime.now()
            )
        
        # Trim to max levels
        while len(prices) > self.max_levels:
            removed_price = prices.pop()
            if removed_price in book:
                del book[removed_price]
        
        self.last_update = datetime.now()
    
    def record_trade(
        self,
        price: float,
        size: int,
        aggressor: str = "unknown"  # "buy" or "sell"
    ):
        """Record a trade for flow analysis"""
        self.trades.append((datetime.now(), price, size, aggressor))
    
    def get_snapshot(self) -> OrderBookSnapshot:
        """Get current order book snapshot"""
        bids = [self.bids[p] for p in self._bid_prices[:self.max_levels] if p in self.bids]
        asks = [self.asks[p] for p in self._ask_prices[:self.max_levels] if p in self.asks]
        
        snapshot = OrderBookSnapshot(
            timestamp=self.last_update,
            symbol=self.symbol,
            bids=bids,
            asks=asks
        )
        
        self.history.append(snapshot)
        return snapshot
    
    def get_metrics(self) -> OrderBookMetrics:
        """Calculate comprehensive order book metrics"""
        snapshot = self.get_snapshot()
        
        # Basic metrics
        mid = snapshot.mid_price
        spread = snapshot.spread
        spread_bps = snapshot.spread_bps
        microprice = snapshot.weighted_mid
        
        # Depth calculations
        def sum_depth(levels: List[PriceLevel], n: int) -> float:
            return sum(l.size for l in levels[:n])
        
        bid_depth_5 = sum_depth(snapshot.bids, 5)
        ask_depth_5 = sum_depth(snapshot.asks, 5)
        bid_depth_10 = sum_depth(snapshot.bids, 10)
        ask_depth_10 = sum_depth(snapshot.asks, 10)
        
        # Imbalance calculations
        def calc_imbalance(bid_size: float, ask_size: float) -> float:
            total = bid_size + ask_size
            if total > 0:
                return (bid_size - ask_size) / total
            return 0.0
        
        imbalance_1 = calc_imbalance(
            snapshot.bids[0].size if snapshot.bids else 0,
            snapshot.asks[0].size if snapshot.asks else 0
        )
        imbalance_5 = calc_imbalance(bid_depth_5, ask_depth_5)
        imbalance_10 = calc_imbalance(bid_depth_10, ask_depth_10)
        
        # Pressure (weighted by inverse distance from mid)
        def calc_pressure(levels: List[PriceLevel], mid: float) -> float:
            if mid <= 0 or not levels:
                return 0.0
            pressure = 0.0
            for level in levels[:10]:
                distance = abs(level.price - mid) / mid
                if distance > 0:
                    pressure += level.size / (1 + distance * 100)
            return pressure
        
        bid_pressure = calc_pressure(snapshot.bids, mid)
        ask_pressure = calc_pressure(snapshot.asks, mid)
        net_pressure = bid_pressure - ask_pressure
        
        # Ratios
        depth_ratio = bid_depth_10 / ask_depth_10 if ask_depth_10 > 0 else 1.0
        
        bid_orders = sum(l.order_count for l in snapshot.bids[:10])
        ask_orders = sum(l.order_count for l in snapshot.asks[:10])
        order_count_ratio = bid_orders / ask_orders if ask_orders > 0 else 1.0
        
        # Queue position (simplified estimate)
        bid_queue = sum(l.size for l in snapshot.bids[:3]) / 3 if len(snapshot.bids) >= 3 else 0
        ask_queue = sum(l.size for l in snapshot.asks[:3]) / 3 if len(snapshot.asks) >= 3 else 0
        
        metrics = OrderBookMetrics(
            timestamp=self.last_update,
            symbol=self.symbol,
            mid_price=mid,
            spread=spread,
            spread_bps=spread_bps,
            microprice=microprice,
            bid_depth_5=bid_depth_5,
            ask_depth_5=ask_depth_5,
            bid_depth_10=bid_depth_10,
            ask_depth_10=ask_depth_10,
            imbalance_1=imbalance_1,
            imbalance_5=imbalance_5,
            imbalance_10=imbalance_10,
            bid_pressure=bid_pressure,
            ask_pressure=ask_pressure,
            net_pressure=net_pressure,
            depth_ratio=depth_ratio,
            order_count_ratio=order_count_ratio,
            bid_queue_position=bid_queue,
            ask_queue_position=ask_queue
        )
        
        self.metrics_history.append(metrics)
        return metrics
    
    def estimate_impact(
        self,
        side: OrderSide,
        size: int,
        method: str = "linear"
    ) -> float:
        """
        Estimate price impact of a market order.
        
        Args:
            side: BUY (lift asks) or SELL (hit bids)
            size: Order size
            method: "linear" or "sqrt" (square root model)
            
        Returns:
            Estimated price impact as decimal (0.001 = 10 bps)
        """
        snapshot = self.get_snapshot()
        
        if side == OrderSide.BID:
            # Buying: consume asks
            levels = snapshot.asks
        else:
            # Selling: consume bids (reversed - worst to best)
            levels = snapshot.bids
        
        if not levels:
            return 0.01  # Default 1% impact if no book
        
        reference_price = levels[0].price
        remaining_size = size
        weighted_price = 0.0
        total_filled = 0
        
        for level in levels:
            if remaining_size <= 0:
                break
            
            fill_size = min(remaining_size, level.size)
            weighted_price += level.price * fill_size
            total_filled += fill_size
            remaining_size -= fill_size
        
        if total_filled == 0:
            return 0.01
        
        avg_fill_price = weighted_price / total_filled
        
        # Calculate impact
        if side == OrderSide.BID:
            impact = (avg_fill_price - reference_price) / reference_price
        else:
            impact = (reference_price - avg_fill_price) / reference_price
        
        return max(impact, 0)
    
    def calculate_vpin(
        self,
        bucket_size: int = 50,
        n_buckets: int = 50
    ) -> float:
        """
        Calculate Volume-synchronized Probability of Informed Trading (VPIN).
        
        VPIN measures order flow toxicity - high VPIN = more informed traders.
        
        Args:
            bucket_size: Volume per bucket
            n_buckets: Number of buckets for calculation
            
        Returns:
            VPIN value [0, 1], higher = more toxic flow
        """
        if len(self.trades) < bucket_size * n_buckets:
            return 0.5  # Neutral if insufficient data
        
        # Classify trades as buy/sell
        buys = []
        sells = []
        
        for timestamp, price, size, aggressor in self.trades:
            if aggressor == "buy":
                buys.append(size)
                sells.append(0)
            elif aggressor == "sell":
                buys.append(0)
                sells.append(size)
            else:
                # Unknown - split 50/50
                buys.append(size / 2)
                sells.append(size / 2)
        
        # Create volume buckets
        buckets_buy = []
        buckets_sell = []
        
        current_buy = 0
        current_sell = 0
        current_volume = 0
        
        for b, s in zip(buys, sells):
            current_buy += b
            current_sell += s
            current_volume += b + s
            
            if current_volume >= bucket_size:
                buckets_buy.append(current_buy)
                buckets_sell.append(current_sell)
                current_buy = 0
                current_sell = 0
                current_volume = 0
        
        if len(buckets_buy) < n_buckets:
            return 0.5
        
        # Calculate VPIN using last n_buckets
        buckets_buy = buckets_buy[-n_buckets:]
        buckets_sell = buckets_sell[-n_buckets:]
        
        total_imbalance = sum(abs(b - s) for b, s in zip(buckets_buy, buckets_sell))
        total_volume = sum(b + s for b, s in zip(buckets_buy, buckets_sell))
        
        if total_volume == 0:
            return 0.5
        
        vpin = total_imbalance / total_volume
        return vpin
    
    def get_signal(self) -> Dict[str, float]:
        """
        Get trading signal from order book state.
        
        Returns:
            Dict with signal strength and confidence
        """
        metrics = self.get_metrics()
        
        # Combine signals
        signals = []
        
        # Imbalance signal (positive = buy pressure)
        imbalance_signal = (metrics.imbalance_1 * 0.5 + 
                          metrics.imbalance_5 * 0.3 + 
                          metrics.imbalance_10 * 0.2)
        signals.append(("imbalance", imbalance_signal))
        
        # Microprice signal
        if metrics.mid_price > 0:
            microprice_signal = (metrics.microprice - metrics.mid_price) / metrics.mid_price * 1000
            signals.append(("microprice", np.clip(microprice_signal, -1, 1)))
        
        # Pressure signal
        total_pressure = metrics.bid_pressure + metrics.ask_pressure
        if total_pressure > 0:
            pressure_signal = metrics.net_pressure / total_pressure
            signals.append(("pressure", pressure_signal))
        
        # Combine into final signal
        if signals:
            weights = {"imbalance": 0.4, "microprice": 0.35, "pressure": 0.25}
            final_signal = sum(weights.get(name, 0.33) * value for name, value in signals)
        else:
            final_signal = 0.0
        
        # Calculate confidence based on spread and depth
        spread_confidence = max(0, 1 - metrics.spread_bps / 50)  # Lower spread = higher confidence
        depth_confidence = min(1, (metrics.bid_depth_5 + metrics.ask_depth_5) / 10000)
        confidence = (spread_confidence + depth_confidence) / 2
        
        return {
            "signal": np.clip(final_signal, -1, 1),
            "confidence": confidence,
            "imbalance": imbalance_signal,
            "spread_bps": metrics.spread_bps,
            "vpin": self.calculate_vpin() if len(self.trades) > 100 else 0.5
        }


@dataclass
class MarketMicrostructureFeatures:
    """Features for ML models from microstructure"""
    # Book features
    spread_bps: float
    microprice_delta_bps: float
    imbalance_1: float
    imbalance_5: float
    imbalance_10: float
    depth_ratio_log: float
    bid_pressure_norm: float
    ask_pressure_norm: float
    
    # Flow features
    vpin: float
    trade_imbalance: float  # Recent buy vs sell volume
    
    # Volatility features
    mid_price_volatility: float
    spread_volatility: float
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for ML"""
        return np.array([
            self.spread_bps,
            self.microprice_delta_bps,
            self.imbalance_1,
            self.imbalance_5,
            self.imbalance_10,
            self.depth_ratio_log,
            self.bid_pressure_norm,
            self.ask_pressure_norm,
            self.vpin,
            self.trade_imbalance,
            self.mid_price_volatility,
            self.spread_volatility
        ])
    
    @staticmethod
    def feature_names() -> List[str]:
        return [
            "spread_bps", "microprice_delta_bps",
            "imbalance_1", "imbalance_5", "imbalance_10",
            "depth_ratio_log", "bid_pressure_norm", "ask_pressure_norm",
            "vpin", "trade_imbalance",
            "mid_price_volatility", "spread_volatility"
        ]


class OrderBookFeatureEngine:
    """
    Extract ML features from order book data.
    
    Maintains rolling statistics and generates features
    suitable for HFT prediction models.
    """
    
    def __init__(
        self,
        lookback_ticks: int = 100,
        volatility_window: int = 50
    ):
        self.lookback_ticks = lookback_ticks
        self.volatility_window = volatility_window
        
        # Rolling buffers
        self.mid_prices: Deque[float] = deque(maxlen=lookback_ticks)
        self.spreads: Deque[float] = deque(maxlen=lookback_ticks)
        self.imbalances: Deque[float] = deque(maxlen=lookback_ticks)
        self.trade_volumes: Deque[Tuple[float, float]] = deque(maxlen=lookback_ticks)  # (buy, sell)
    
    def update(self, book: OrderBook):
        """Update with new book state"""
        metrics = book.get_metrics()
        
        self.mid_prices.append(metrics.mid_price)
        self.spreads.append(metrics.spread_bps)
        self.imbalances.append(metrics.imbalance_1)
    
    def record_trade(self, size: float, is_buy: bool):
        """Record trade for flow analysis"""
        if is_buy:
            self.trade_volumes.append((size, 0))
        else:
            self.trade_volumes.append((0, size))
    
    def get_features(self, book: OrderBook) -> MarketMicrostructureFeatures:
        """Extract features from current book state"""
        metrics = book.get_metrics()
        
        # Calculate rolling statistics
        if len(self.mid_prices) >= 2:
            returns = np.diff(list(self.mid_prices)) / np.array(list(self.mid_prices)[:-1])
            mid_vol = np.std(returns) * 10000 if len(returns) > 1 else 0
        else:
            mid_vol = 0
        
        spread_vol = np.std(list(self.spreads)) if len(self.spreads) > 1 else 0
        
        # Trade imbalance
        if self.trade_volumes:
            buy_vol = sum(t[0] for t in self.trade_volumes)
            sell_vol = sum(t[1] for t in self.trade_volumes)
            total_vol = buy_vol + sell_vol
            trade_imbalance = (buy_vol - sell_vol) / total_vol if total_vol > 0 else 0
        else:
            trade_imbalance = 0
        
        # Normalize pressures
        total_pressure = metrics.bid_pressure + metrics.ask_pressure
        bid_norm = metrics.bid_pressure / total_pressure if total_pressure > 0 else 0.5
        ask_norm = metrics.ask_pressure / total_pressure if total_pressure > 0 else 0.5
        
        return MarketMicrostructureFeatures(
            spread_bps=metrics.spread_bps,
            microprice_delta_bps=(metrics.microprice - metrics.mid_price) / metrics.mid_price * 10000 if metrics.mid_price > 0 else 0,
            imbalance_1=metrics.imbalance_1,
            imbalance_5=metrics.imbalance_5,
            imbalance_10=metrics.imbalance_10,
            depth_ratio_log=np.log(metrics.depth_ratio) if metrics.depth_ratio > 0 else 0,
            bid_pressure_norm=bid_norm,
            ask_pressure_norm=ask_norm,
            vpin=book.calculate_vpin(),
            trade_imbalance=trade_imbalance,
            mid_price_volatility=mid_vol,
            spread_volatility=spread_vol
        )


# ============== CONVENIENCE FUNCTIONS ==============

def create_order_book(symbol: str) -> OrderBook:
    """Create a new order book"""
    return OrderBook(symbol)


def calculate_book_imbalance(bids: List[Tuple[float, int]], asks: List[Tuple[float, int]], levels: int = 5) -> float:
    """
    Quick imbalance calculation from bid/ask lists.
    
    Args:
        bids: List of (price, size) tuples, best first
        asks: List of (price, size) tuples, best first
        levels: Number of levels to consider
        
    Returns:
        Imbalance [-1, 1], positive = buy pressure
    """
    bid_size = sum(size for _, size in bids[:levels])
    ask_size = sum(size for _, size in asks[:levels])
    total = bid_size + ask_size
    
    if total == 0:
        return 0.0
    
    return (bid_size - ask_size) / total
